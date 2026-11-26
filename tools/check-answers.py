#!/usr/bin/env python3
"""tools/check-answers.py — answers as code: evaluate every leaf's `check:` expression.

  check-answers.py <content.yaml | run dir>          a dir's content.yaml/.yml/.json is found

content.yaml may carry two actor-only keys on any leaf (a question with no parts, or a leaf
part) — `build-staged` never emits them:

  check:  a Python arithmetic expression that must evaluate to True — e.g.
          `check: "40 * 23 == 920"` or `check: "divmod(925, 40) == (23, 5)"`. Whitelist:
          numbers, + - * / // % **, unary -, comparisons (chained ok), and/or/not,
          parentheses, tuple/list literals (constant indexing ok; tuple comparisons
          like `(a, b) == (1, 2)` count), and calls to
          ceil floor divmod min max abs sum round sorted int len. Nothing else — no
          names, no attributes. The check must contain at least one comparison, and
          every comparison must compute something — a bare `True` or a constant-only
          compare (`1 == 1`, `1 < 2`, `(1, 2) == (1, 2)`) re-derives nothing and is
          refused. A leaf can instead declare `check: "none — <reason>"` (an em dash
          or ` - `): the reason after the dash must strip to ≥10 characters, and the
          leaf is counted separately in the summary as unchecked-by-declaration —
          for classification/naming answers where nothing computes. Resource
          bounds: every intermediate |number| ≤ 10**15, every list/tuple ≤ 1000
          elements (a `seq * n` repetition is refused before it allocates), |exp| ≤
          1000 on `**`, and a 2 s wall-clock backstop per leaf (SIGALRM, POSIX).
  level:  R | M | H — the leaf's difficulty on the plan appendix rubric (read by
          precritic-lint --rubric).

For each `check:` leaf the tool also checks coverage: every number in the leaf's `final`
(after stripping `$` and LaTeX commands) must occur as a literal in the check or equal the
value of some Call/BinOp in it — uncovered numbers WARN (the final could still be right but
the check doesn't reach it). Leaves without `check:` WARN one line each — a classification
answer legitimately has none.

Summary `check-answers: N checked · F false · W warn · M without check · U unchecked
(check: none)`; exit 1 on any False or eval error, else 0.
"""
import argparse
import ast
import contextlib
import math
import re
import signal
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def _bs():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_staged", TOOLS / "build-staged.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def die(msg: str) -> "None":
    sys.stderr.write(f"check-answers: {msg}\n")
    sys.exit(2)


# ---------------------------------------------------------------------------
# The expression evaluator — an AST whitelist, never eval()
# ---------------------------------------------------------------------------
FUNCS = {"ceil": math.ceil, "floor": math.floor, "divmod": divmod, "min": min, "max": max,
         "abs": abs, "sum": sum, "round": round, "sorted": sorted, "int": int,
         "len": len}
_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b}
_CMP = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b}
MAX_NODES = 200          # a check is one line of arithmetic — bigger is a mistake or worse
MAX_POW = 1000           # |exponent| cap so `10**(10**8)` cannot hang the gate
MAX_ABS = 10 ** 15       # every intermediate number stays small — big-int bombs die at birth
MAX_SEQ = 1000           # every intermediate list/tuple stays short — `[1]*10**9` never exists
EVAL_SECONDS = 2         # wall-clock backstop per leaf, on top of the structural caps
NONE_CHECK = re.compile(r"^none\s*(?:—|-)\s*(.+)$", re.S)


class Refuse(ValueError):
    """A construct outside the whitelist, or a resource bound hit."""


def _cap(v):
    """Refuse any intermediate value that escaped the bounds — |number| > MAX_ABS or
    a list/tuple longer than MAX_SEQ."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        if abs(v) > MAX_ABS:
            raise Refuse(f"value too large — |{v:g}| exceeds {MAX_ABS:g}")
        return v
    if isinstance(v, complex):
        raise Refuse("complex numbers are out of scope")
    if isinstance(v, (list, tuple)) and len(v) > MAX_SEQ:
        raise Refuse(f"sequence too long — {len(v)} elements exceed {MAX_SEQ}")
    return v


@contextlib.contextmanager
def _deadline(seconds: int):
    """SIGALRM backstop around one leaf's evaluation (POSIX only — elsewhere the
    structural caps are the whole defence)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return
    def _alarm(_sig, _frm):
        raise Refuse(f"evaluation took over {seconds}s — timed out")
    prev = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev)


def _eval(node):
    """_eval_node under the resource caps — every value a node produces is bounded,
    so nothing downstream of it can be huge."""
    return _cap(_eval_node(node))


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise Refuse(f"constant {node.value!r} — only numbers")
    if isinstance(node, ast.Name):
        if node.id in FUNCS:
            return FUNCS[node.id]
        raise Refuse(f"name '{node.id}' — only {', '.join(sorted(FUNCS))} are callable")
    if isinstance(node, ast.Call):
        if node.keywords:
            raise Refuse("keyword arguments")
        f = _eval(node.func)
        if f not in FUNCS.values():
            raise Refuse("call target is not a whitelisted function")
        return f(*[_eval(a) for a in node.args])
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow):
            if not isinstance(b, (int, float)) or isinstance(b, bool) \
                    or abs(b) > MAX_POW:
                raise Refuse(f"** exponent {b!r} — |exp| must be ≤ {MAX_POW}")
            return a ** b                        # result itself is capped by _eval
        op = _BIN.get(type(node.op))
        if op is None:
            raise Refuse(f"operator {type(node.op).__name__}")
        if isinstance(node.op, ast.Mult):
            # refuse `seq * n` before it allocates — a billion-element list is an OOM,
            # and MemoryError is not an Exception so it would escape the per-leaf catch
            for seq, n in ((a, b), (b, a)):
                if isinstance(seq, (list, tuple)) and isinstance(n, int) \
                        and not isinstance(n, bool) \
                        and len(seq) * max(n, 0) > MAX_SEQ:
                    raise Refuse(f"sequence repetition — {len(seq)} × {n} would "
                                 f"exceed {MAX_SEQ} elements")
        return op(a, b)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_eval(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +_eval(node.operand)
        if isinstance(node.op, ast.Not):
            return not _eval(node.operand)
        raise Refuse(f"unary {type(node.op).__name__}")
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(vals)
        if isinstance(node.op, ast.Or):
            return any(vals)
        raise Refuse("boolean operator")
    if isinstance(node, ast.Compare):
        left = _eval(node.left)
        for op, comp in zip(node.ops, node.comparators):
            f = _CMP.get(type(op))
            if f is None:
                raise Refuse(f"comparison {type(op).__name__}")
            right = _eval(comp)
            if not f(left, right):
                return False
            left = right
        return True
    if isinstance(node, (ast.Tuple, ast.List)):
        vals = [_eval(e) for e in node.elts]
        return tuple(vals) if isinstance(node, ast.Tuple) else vals
    if isinstance(node, ast.Subscript):
        # trivial literal indexing only: (23, 5)[0] / [1, 2][1]
        if not isinstance(node.value, (ast.Tuple, ast.List)) \
                or not isinstance(node.slice, ast.Constant) \
                or not isinstance(node.slice.value, int):
            raise Refuse("subscript — only a tuple/list literal indexed by a constant")
        return _eval(node.value)[node.slice.value]
    raise Refuse(f"{type(node).__name__} is not in the whitelist")


def _literal(node) -> bool:
    """A parse-time constant: a Constant, a tuple/list of literals, or a bare ± sign on
    one (`-5` is a literal, not a computation). Anything else — BinOp, Call, Subscript,
    `not`, unary applied to a computed operand — counts as computed."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(_literal(e) for e in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _literal(node.operand)
    return False


def parse_check(expr: str, where: str):
    """→ ast.Expression — raises Refuse on anything outside the whitelist, too big,
    or trivially satisfied (no comparison / an all-literal comparison)."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise Refuse(f"syntax: {e.msg}") from e
    except (RecursionError, MemoryError) as e:
        raise Refuse("too deeply nested") from e
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise Refuse(f"more than {MAX_NODES} nodes")
    # walk once so refusal lands before any evaluation
    for n in ast.walk(tree):
        if isinstance(n, (ast.Attribute, ast.Starred, ast.NamedExpr, ast.Await,
                          ast.Lambda, ast.IfExp, ast.Dict, ast.Set, ast.JoinedStr,
                          ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp,
                          ast.Yield, ast.YieldFrom, ast.Slice)):
            raise Refuse(f"{type(n).__name__} is not in the whitelist")
    comps = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)]
    if not comps:
        raise Refuse("the check has no comparison — it never tests a derived value")
    for c in comps:
        if all(_literal(s) for s in (c.left, *c.comparators)):
            raise Refuse(f"constant-only comparison {ast.unparse(c)!r} — at least one "
                         f"side must compute something")
    return tree


# ---------------------------------------------------------------------------
# `final` coverage — every number in the final must be reachable from the check
# ---------------------------------------------------------------------------
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
LATEX_RE = re.compile(r"\\[a-zA-Z]+|[${}^_~]")


WORKED_MATH = re.compile(r"\$\$(.*?)\$\$|\$([^$\n]+)\$|\\\((.*?)\\\)|\\\[(.*?)\\\]", re.S)
WORKED_LITERAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
WORKED_OPERATORS = re.compile(r"[\d.()+*/\s-]+")
ROUNDING_PLACES = {"unit": 0, "whole number": 0, "ten": 1, "hundred": 2,
                   "thousand": 3, "ten thousand": 4, "hundred thousand": 5,
                   "million": 6, "tenth": -1, "hundredth": -2, "thousandth": -3}
def _rounding_places(text):
    places = {exp for name, exp in ROUNDING_PLACES.items()
              if re.search(rf"\bnearest\s+{name}\b(?!\s+thousand)", text, re.I)}
    for value in re.findall(r"\bnearest\s+(1[\d,\u2009\u202f]*|0\.0*1)(?!\w|\.\d)", text, re.I):
        literal = re.sub(r"[,\u2009\u202f]", "", value)
        if re.fullmatch(r"10*|0\.0*1", literal):
            places.add(Decimal(literal).adjusted())
    return places


def _worked_normalise(text: str) -> str:
    text = text.translate(str.maketrans({"−": "-", "×": "*", "÷": "/", "·": "*"}))
    text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+",
                  lambda m: "**(" + m[0].translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")) + ")",
                  text)
    text = re.sub(r"\\(?:times|cdot)\b", "*", text)
    text = re.sub(r"\\div\b", "/", text)
    text = re.sub(r"\\approx\b", "≈", text)
    text = re.sub(r"\\(?:left|right)\b|\\[,;! ]", "", text)
    frac = re.compile(r"\\(?:d?frac|tfrac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
    for _ in range(12):
        expanded = frac.sub(r"((\1)/(\2))", text)
        if expanded == text:
            break
        text = expanded
    return text.replace("^", "**").replace("{", "(").replace("}", ")").strip()


def _worked_value(text: str):
    if len(text) > 400 or not WORKED_OPERATORS.fullmatch(text):
        raise Refuse("not closed arithmetic")
    tree = ast.parse(text, mode="eval")
    nodes = list(ast.walk(tree))
    operators = (ast.Expression, ast.Constant, ast.UnaryOp, ast.UAdd, ast.USub, ast.BinOp,
                 ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
    if len(nodes) > MAX_NODES or any(not isinstance(node, operators) for node in nodes):
        raise Refuse("unsupported arithmetic")
    return _eval(tree)


def check_worked_math(approach, approach_si):
    """Yield (field, status, link) for explicit adjacent arithmetic equalities."""
    for field, text in (("approach", approach), ("approach_si", approach_si)):
        if not isinstance(text, str):
            continue
        spans = []
        place = None
        for paragraph in re.split(r"\n\s*\n", text):
            places = _rounding_places(paragraph)
            if places:
                place = next(iter(places)) if len(places) == 1 else None
            spans.extend((next(g for g in match.groups() if g is not None), place)
                         for match in WORKED_MATH.finditer(paragraph))
            spans.extend((line.strip().removesuffix(".").strip(), place)
                         for line in WORKED_MATH.sub("", paragraph).splitlines()
                         if re.match(r"\s*[\d.(+−-]", line))
        for span, place in spans:
            parts = re.split(r"\s*([=≈])\s*", _worked_normalise(span))
            for left, op, right in zip(parts[::2], parts[1::2], parts[2::2]):
                link = f"{left} {op} {right}"
                try:
                    a, b = _worked_value(left), _worked_value(right)
                    if op == "≈":
                        if not WORKED_LITERAL.fullmatch(right):
                            raise Refuse("approximation has no stated decimal precision")
                        exponent = place
                        if exponent is None:
                            if "." in right:
                                exponent = -len(right.partition(".")[2])
                            else:
                                exponent = len(right) - len(right.rstrip("0")) if b else 0
                        precision = Decimal(1).scaleb(exponent)
                        ok = Decimal(str(a)).quantize(precision, rounding=ROUND_HALF_UP) == Decimal(right)
                    else:
                        ok = abs(a - b) <= 4 * max(math.ulp(a), math.ulp(b))
                except (Refuse, ArithmeticError, SyntaxError, ValueError, TypeError, RecursionError):
                    yield field, "unchecked", link
                else:
                    yield field, "ok" if ok else "false", link


def final_numbers(final: str) -> list[float]:
    return [float(m) for m in NUM_RE.findall(LATEX_RE.sub(" ", final or ""))]


def covered_values(tree) -> list[float]:
    """Literals in the check + the value of every Call/BinOp in it."""
    vals = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))]
    for n in ast.walk(tree):
        if isinstance(n, (ast.Call, ast.BinOp)):
            try:
                v = _eval(n)
            except Exception:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append(v)
    return vals


# ---------------------------------------------------------------------------
def leaves(spec: dict):
    """→ [(name, node)] in document order — a part-less question is its own leaf."""
    out = []

    def walk(parts, prefix, n):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            path = f"{prefix}.{p.get('label', '?')}"
            if p.get("parts"):
                walk(p["parts"], path, n)
            else:
                out.append((f"Q{n}{path}", p))

    for q in spec.get("questions") or []:
        if not isinstance(q, dict):
            continue
        n = q.get("n")
        if q.get("parts"):
            walk(q["parts"], "", n)
        else:
            out.append((f"Q{n}", q))
    return out


def content_path(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir():
        for name in ("content.yaml", "content.yml", "content.json"):
            if (p / name).is_file():
                return p / name
        die(f"{arg}: no content.yaml/.yml/.json in that run dir")
    if not p.is_file():
        die(f"{arg}: no such file or dir")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(prog="check-answers",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("path", help="content.yaml or a run dir containing one")
    args = ap.parse_args()
    bs = _bs()
    spec = bs.load_spec(content_path(args.path))
    if not isinstance(spec.get("questions"), list):
        die("content: 'questions' must be a list")

    checked = false = warns = missing = unchecked = 0
    worked = dict.fromkeys(("ok", "false", "unchecked"), 0)
    for name, node in leaves(spec):
        for field, status, link in check_worked_math(node.get("approach"), node.get("approach_si")):
            worked[status] += 1
            if status == "false":
                print(f"FAIL {name}.{field}: false worked arithmetic: {link}")
            elif status == "unchecked":
                print(f"UNCHECKED {name}.{field}: unsupported worked arithmetic: {link}")
        expr = node.get("check")
        if expr is None:
            missing += 1
            print(f"WARN {name}: no check — nothing re-derives this leaf")
            continue
        if isinstance(expr, str):
            m = NONE_CHECK.fullmatch(expr.strip())
            if m:
                reason = m.group(1).strip()
                if len(reason) < 10:
                    print(f"FAIL {name}: 'check: none' wants a reason of ≥10 "
                          f"characters after the dash — got {reason!r}")
                    false += 1
                else:
                    unchecked += 1
                continue
        if not isinstance(expr, str):
            print(f"FAIL {name}: check must be a string expression, got {expr!r}")
            checked += 1
            false += 1
            continue
        checked += 1
        try:
            tree = parse_check(expr, name)
            with _deadline(EVAL_SECONDS):
                ok = _eval(tree)
        except Refuse as e:
            print(f"FAIL {name}: check refused — {e}")
            false += 1
            continue
        except Exception as e:
            print(f"FAIL {name}: check eval error — {e}")
            false += 1
            continue
        if ok is not True:
            print(f"FAIL {name}: check evaluates to {ok!r}, not True")
            false += 1
        final = node.get("final")
        if isinstance(final, str):
            covered = covered_values(tree)
            for num in final_numbers(final):
                if not any(num == v for v in covered):
                    warns += 1
                    print(f"WARN {name}: final number {num:g} not covered by check")
    print(f"check-answers: {checked} checked · {false} false · {warns} warn · "
          f"{missing} without check · {unchecked} unchecked (check: none)")
    print(f"worked arithmetic: {worked['ok']} checked · {worked['false']} false · "
          f"{worked['unchecked']} unchecked")
    return 1 if false or worked["false"] else 0


if __name__ == "__main__":
    sys.exit(main())
