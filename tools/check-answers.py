#!/usr/bin/env python3
"""tools/check-answers.py — answers as code: evaluate every leaf's `check:` expression.

  check-answers.py <content.yaml | run dir>          a dir's content.yaml/.yml/.json is found

content.yaml may carry two actor-only keys on any leaf (a question with no parts, or a leaf
part) — `build-staged` never emits them:

  check:  a Python arithmetic expression that must evaluate to True — e.g.
          `check: "40 * 23 == 920"` or `check: "divmod(925, 40) == (23, 5)"`. Whitelist:
          numbers, + - * / // % **, unary -, comparisons (chained ok), and/or/not,
          parentheses, tuple/list literals (constant indexing ok), and calls to
          ceil floor divmod min max abs sum round sorted int. Nothing else — no names,
          no attributes. The check must contain at least one comparison, and every
          comparison must compute something — a bare `True` or a constant-only
          compare (`1 == 1`, `1 < 2`, `(1, 2) == (1, 2)`) re-derives nothing and is
          refused. Resource
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

Summary `check-answers: N checked · F false · W warn · M without check`; exit 1 on any
False or eval error, else 0.
"""
import argparse
import ast
import contextlib
import math
import re
import signal
import sys
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
         "abs": abs, "sum": sum, "round": round, "sorted": sorted, "int": int}
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

    checked = false = warns = missing = 0
    for name, node in leaves(spec):
        expr = node.get("check")
        if expr is None:
            missing += 1
            print(f"WARN {name}: no check — nothing re-derives this leaf")
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
          f"{missing} without check")
    return 1 if false else 0


if __name__ == "__main__":
    sys.exit(main())
