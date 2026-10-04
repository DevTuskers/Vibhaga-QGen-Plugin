#!/usr/bin/env python3
"""blueprint.py — instantiate ONE parameterised question into a content.yaml item.

    blueprint.py instantiate <file> --seed N --n Q [--spec-out specs/figures.json]
    blueprint.py --self-test

A blueprint is one parameterised question in its own YAML file (actor-authored, run-local —
it feeds a paste into `questions:`, it is never a build input itself):

    blueprint:
      id: rect-split                   # required, ^[a-z0-9][a-z0-9-]*$
      params:                          # names ^[a-z][a-z0-9_]+$ (>= 2 chars)
        ln: {range: [6, 20], step: 2}  # inclusive ints; step default 1
        wd: {choices: [3, 4, 5]}       # numbers only
      where: ["ln > wd + 1"]           # all must be True; >= 0 entries
      derived:                         # name -> expression over params/earlier derived; ordered
        per: "2 * (ln + wd)"
      figure:                          # optional — one specs/figures.json entry, with slots
        template: rectangle_points
        length: "{ln}"
        width: "{wd}"
      question:                        # a normal content.yaml question minus `n`, with slots
        lessons: [L07]
        stem: "A rectangle is ${ln}\\,\\text{cm}$ by ${wd}\\,\\text{cm}$."
        parts:
          - label: a
            text: "Find its perimeter."
            approach: "$2({ln}+{wd})$"
            final: "${per}\\,\\text{cm}$"
            check: "{ln} + {ln} + {wd} + {wd} == {per}"
            level: M

The rules (owner-settled, 2026-10-03):

- SLOTS — `{name}` where `name` is a declared param or derived is replaced. A slot-shaped
  group naming nothing declared is refused (`undeclared slot — typo?`) unless it is LaTeX —
  `{` right after a `\\command`, `}`, `^` or `_` (`\\text{cm}`, `\\frac{1}{2}`, `x^{ab}`).
  A slot directly inside `\\text{…}`, `\\mathrm{…}` or `\\operatorname{…}` — the `{`
  immediately preceded by that command — is ambiguous and refused. A DECLARED slot in a
  brace-significant spot (after `^`, `_`, `}` or a `\\command`) keeps its braces —
  `x^{ln}` → `x^{12}`, never `x^12`. A string value that is exactly one slot (`"{ln}"`) becomes the typed
  number inside a figure spec (`length: "{ln}"` → a number for vdd_templates); in the question
  tree it becomes the formatted string, since build-staged requires strings there. Every other
  substitution is textual.

- EXPRESSIONS — `where`, `derived` and the post-substitution `check:` strings run through
  check-answers' AST-whitelist evaluator, imported not copied: param/derived names are bound as
  Constants before evaluation, the whitelisted function names stay callable, and anything else
  refuses (unknown name → refuse; the whitelist is not loosened).

- NUMBER FORMAT — an int prints as itself; an integral float prints as an int; any other value
  must be exact to 4 decimals (`abs(v*1e4 - round(v*1e4)) < 1e-9`) and prints as the shortest
  decimal — anything worse refuses with "derived <name>=<v> is not exact — tighten the
  constraints".

- SAMPLING — `random.Random(seed)`; each draw picks every param uniformly from its values and is
  rejected until all `where` hold; after 2000 draws the run gives up. Same seed ⇒ byte-identical
  output.

- CHECKS — answers-as-code is the point: every leaf carries `check:` (a blueprint without one on
  a leaf refuses), and after substitution each must evaluate to True — a False or an error exits
  1 naming the seed and the leaf: the blueprint is wrong, not the draw.

- OUTPUT — stdout gets the question as a YAML list item to paste under `questions:`, carrying
  `n`, `blueprint_id`, `blueprint_seed` (actor-only keys — build-staged validates them and never
  emits them) and, when the blueprint has a figure, `figure: Q<Q>` plus a leading
  `# figures: add  Q<Q>: figures/Q<Q>.json` comment. The figure spec gets `figure_id: Q<Q>` and,
  when it has none of its own, the instantiated question stem. The instance is ALWAYS built into
  a temp dir via vdd_templates first — a TemplateError refuses here, not at run-gates — and
  `--spec-out` merges the spec into that JSON list (created when absent; a duplicate figure_id
  refuses).

Exit 0 printed · exit 1 a leaf check failed · exit 2 refused (bad file/shape, forged
question keys, undeclared or ambiguous slot, unknown name, non-exact or non-finite derived,
non-bool or impossible `where`, missing `check:`, template error, duplicate figure_id).
"""
from __future__ import annotations

import argparse
import ast
import copy
import importlib.util
import json
import math
import os
import random
import re
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # dataclass et al. resolve cls.__module__ through sys.modules
    spec.loader.exec_module(mod)
    return mod


ca = _load("check_answers", "check-answers.py")   # the whitelist evaluator — reused, never copied

BP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")     # the same contract build-staged validates
NAME_RE = re.compile(r"^[a-z][a-z0-9_]+$")          # >= 2 chars by construction
SLOT_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")   # slot-SHAPED — declared names are
                                                     # lowercase ≥2, so {l}/{L}/{Ln} land in
                                                     # the undeclared branch, not verbatim
CMD_GROUP_RE = re.compile(r"\\[A-Za-z]+$")      # `\command{` — a LaTeX group, not a slot
TEXT_GROUPS = ("\\text", "\\mathrm", "\\operatorname")
MAX_DRAWS = 2000


class EvalError(Exception):
    """A whitelist refusal — the expression itself is malformed."""


class ArithError(Exception):
    """A runtime error on one draw's values (e.g. a division by zero)."""


def die(msg: str) -> "None":
    print(f"blueprint: {msg}", file=sys.stderr)
    sys.exit(2)


def fail_check(msg: str) -> "None":
    """A leaf check failed — the blueprint is wrong, not the draw."""
    print(f"blueprint: {msg}", file=sys.stderr)
    sys.exit(1)


def import_yaml():
    try:
        import yaml
        return yaml
    except ImportError:
        die("PyYAML is not installed — `pip install pyyaml`")


# -------------------------------------------------------------------------------------------------
# The blueprint file — shape and expression-name validation up front
# -------------------------------------------------------------------------------------------------
def load_blueprint(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        die(f"no such file: {path}")
    yaml = import_yaml()
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        die(f"{p.name}: YAML parse error: {e}")
    if not isinstance(doc, dict) or not isinstance(doc.get("blueprint"), dict):
        die(f"{p.name}: top level must be a mapping carrying a 'blueprint' mapping")
    bp = doc["blueprint"]
    unknown = set(bp) - {"id", "params", "where", "derived", "figure", "question"}
    if unknown:
        die(f"{p.name}: unknown blueprint keys {sorted(unknown)}")

    bid = bp.get("id")
    if not isinstance(bid, str) or not BP_ID_RE.fullmatch(bid):
        die(f"blueprint.id {bid!r} must match {BP_ID_RE.pattern}")

    params = bp.get("params")
    if not isinstance(params, dict) or not params:
        die("blueprint.params must be a nonempty {name: spec} mapping — this is the parameterised part")
    values: dict[str, list] = {}
    for name, spec in params.items():
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            die(f"param name {name!r} must match {NAME_RE.pattern} (>= 2 chars)")
        if not isinstance(spec, dict):
            die(f"params.{name}: a mapping with 'range' or 'choices'")
        if set(spec) - {"range", "choices", "step"}:
            die(f"params.{name}: unknown keys {sorted(set(spec) - {'range', 'choices', 'step'})}")
        if ("range" in spec) == ("choices" in spec):
            die(f"params.{name}: exactly one of 'range' / 'choices'")
        if "range" in spec:
            r = spec["range"]
            if not isinstance(r, list) or len(r) != 2 \
                    or not all(isinstance(x, int) and not isinstance(x, bool) for x in r):
                die(f"params.{name}.range must be [lo, hi] — two ints")
            step = spec.get("step", 1)
            if not isinstance(step, int) or isinstance(step, bool) or step <= 0:
                die(f"params.{name}.step must be a positive int (got {step!r})")
            vals = list(range(r[0], r[1] + 1, step))
            if not vals:
                die(f"params.{name}: range {r} with step {step} yields no values")
        else:
            vals = spec["choices"]
            if not isinstance(vals, list) or not vals:
                die(f"params.{name}.choices must be a nonempty list")
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool)
                       and math.isfinite(x) for x in vals):
                die(f"params.{name}.choices: finite numbers only")

        values[name] = vals

    where = bp.get("where") or []
    if not isinstance(where, list) or not all(isinstance(w, str) for w in where):
        die("blueprint.where must be a list of expression strings")

    derived = bp.get("derived") or {}
    if not isinstance(derived, dict):
        die("blueprint.derived must be a mapping")
    names = set(values)
    for name, expr in derived.items():
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            die(f"derived name {name!r} must match {NAME_RE.pattern}")
        if name in values:
            die(f"derived name {name!r} shadows a param")
        if not isinstance(expr, str):
            die(f"derived.{name} must be an expression string (got {expr!r})")
        names.add(name)

    figure = bp.get("figure")
    if figure is not None and not isinstance(figure, dict):
        die("blueprint.figure must be a specs/figures.json-style mapping")

    question = bp.get("question")
    if not isinstance(question, dict):
        die("blueprint.question must be a mapping — a content.yaml question minus `n`")
    forged = set(question) & {"n", "blueprint_id", "blueprint_seed", "figure"}
    if forged:
        die(f"blueprint.question must not carry {sorted(forged)} — `n` comes from --n, "
            f"blueprint_id/blueprint_seed are emitted by instantiate, and the figure comes "
            f"only from blueprint.figure")
    if _parts_too_deep(question.get("parts")):
        die("blueprint.question: parts nested deeper than 2 levels — build-staged refuses "
            "that shape anyway; flatten the blueprint's parts")
    if not isinstance(question.get("stem"), str) or not question["stem"].strip():
        die("blueprint.question.stem is required")

    return {"id": bid, "params": values, "where": where, "derived": derived,
            "figure": figure, "question": question}


def _parts_too_deep(parts, depth: int = 1) -> bool:
    """build-staged's rules, mirrored at load: every part entry is a mapping; parts may nest
    one level, never two."""
    for p in parts or []:
        if not isinstance(p, dict):
            die(f"blueprint.question: a part entry is not a mapping (got {p!r}) — "
                f"every part is {{label, text, approach, final, parts?}}")
        if p.get("parts"):
            if depth >= 2 or _parts_too_deep(p["parts"], depth + 1):
                return True
    return False


# -------------------------------------------------------------------------------------------------
# Expressions — check-answers' evaluator with param/derived names bound as constants
# -------------------------------------------------------------------------------------------------
def eval_expr(expr: str, env: dict, ctx: str):
    """→ the expression's value under check-answers' whitelist. EvalError on a syntax error, an
    unknown name or a whitelist refusal (callers map it to their own exit); ArithError on a
    value-level failure."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise EvalError(f"{ctx}: syntax error in expression {expr!r} — {e.msg}") from e
    if sum(1 for _ in ast.walk(tree)) > ca.MAX_NODES:
        raise EvalError(f"{ctx}: expression {expr!r} exceeds {ca.MAX_NODES} AST nodes")
    unknown = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
                      and n.id not in env and n.id not in ca.FUNCS})
    if unknown:
        raise EvalError(f"{ctx}: unknown name(s) {', '.join(unknown)} in expression {expr!r} — "
                        f"known: params/derived ({', '.join(sorted(env)) or 'none'}) plus the "
                        f"whitelisted functions ({', '.join(sorted(ca.FUNCS))})")

    class Bind(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in env:
                return ast.copy_location(ast.Constant(env[node.id]), node)
            return node                    # a whitelisted function name — _eval resolves it

    tree = ast.fix_missing_locations(Bind().visit(tree))
    try:
        with ca._deadline(ca.EVAL_SECONDS):
            return ca._eval(tree)
    except ca.Refuse as e:
        raise EvalError(str(e)) from e
    except Exception as e:                                # noqa: BLE001 — reported, never raised raw
        raise ArithError(str(e)) from e


def fmt(v, name: str) -> str:
    """A value's printable form: int digits, an integral float as an int, otherwise exact to
    <= 4 decimals as the shortest decimal — non-finite and anything worse is a refusal."""
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float) and math.isfinite(v):
        if v.is_integer():
            return str(int(v))
        if abs(v * 1e4 - round(v * 1e4)) < 1e-9:
            return f"{v:.4f}".rstrip("0").rstrip(".")
    die(f"derived {name}={v} is not exact — tighten the constraints")


# -------------------------------------------------------------------------------------------------
# Slots — {name} substitution inside strings, whole-slot strings to typed values
# -------------------------------------------------------------------------------------------------
def sub_string(s: str, env: dict, ctx: str) -> str:
    out, pos = [], 0
    for m in SLOT_RE.finditer(s):
        name = m.group(1)
        pre = s[:m.start()]
        if name not in env:
            # \text{cm}, \frac{a}{b}, x^{ab}, a_{bc} — a brace group after a \command,
            # `}`, `^` or `_` is LaTeX, not a slot; anything else slot-shaped and
            # undeclared is almost certainly a typo — refuse it.
            if CMD_GROUP_RE.search(pre) or pre.endswith(("}", "^", "_")):
                continue
            die(f"{ctx}: undeclared slot {{{name}}} — typo? (declare it in params/derived)")
        if pre.endswith(TEXT_GROUPS):
            die(f"{ctx}: slot {{{name}}} sits directly inside a \\text/\\mathrm/\\operatorname "
                f"group — ambiguous, refusing")
        out.append(s[pos:m.start()])
        # braces stay when LaTeX needs the group: `{` after `^`/`_`/`}` or a `\command` —
        # `x^{ln}` → `x^{12}`, never `x^12`.
        keep = CMD_GROUP_RE.search(pre) or pre.endswith(("^", "_", "}"))
        v = fmt(env[name], name)
        out.append(f"{{{v}}}" if keep else v)
        pos = m.end()
    out.append(s[pos:])
    return "".join(out)


def sub_value(v, env: dict, ctx: str, whole_typed: bool = False):
    """Deep slot substitution. A string that is exactly one slot (`"{ln}"`) becomes the typed
    value ONLY inside a figure spec (`whole_typed`) — `length: "{ln}"` must be a number for
    vdd_templates. In the question tree the same string becomes the formatted string, because
    build-staged requires stem/text/approach/final to stay strings."""
    if isinstance(v, str):
        m = SLOT_RE.fullmatch(v)
        if m and m.group(1) in env:
            name = m.group(1)
            return env[name] if whole_typed else fmt(env[name], name)
        return sub_string(v, env, ctx)
    if isinstance(v, list):
        return [sub_value(x, env, ctx, whole_typed) for x in v]
    if isinstance(v, dict):
        return {k: sub_value(x, env, ctx, whole_typed) for k, x in v.items()}
    return v


# -------------------------------------------------------------------------------------------------
# Sampling + instantiation
# -------------------------------------------------------------------------------------------------
def sample(bp: dict, seed: int) -> dict:
    """→ one accepted draw {param: value}. random.Random(seed); every param drawn uniformly;
    a draw is rejected until all `where` hold; MAX_DRAWS then give up."""
    rng = random.Random(seed)
    names = list(bp["params"])
    for _ in range(MAX_DRAWS):
        env = {nm: rng.choice(bp["params"][nm]) for nm in names}
        ok = True
        for w in bp["where"]:
            try:
                r = eval_expr(w, env, f"where {w!r}")
            except EvalError as e:
                die(str(e))                            # a malformed `where` is a blueprint defect
            except ArithError:
                ok = False                             # e.g. a division by this draw's zero — reject
                break
            if not isinstance(r, bool):
                die(f"where {w!r} must evaluate to True/False (got {r!r}) — "
                    f"a constraint is a comparison, not a value")
            if not r:
                ok = False                             # every `where` must hold — literally True
                break
        if ok:
            return env
    die(f"no draw satisfied `where` in {MAX_DRAWS} tries (seed {seed}) — "
        f"the constraints are impossible or too tight")


def question_leaves(q: dict) -> list[tuple[str, dict]]:
    """→ [(leaf name, node)] — a part-less question is its own leaf."""
    out = []

    def walk(parts, prefix):
        for p in parts:
            if not isinstance(p, dict):
                die(f"question: a part entry is not a mapping (got {p!r})")
            path = f"{prefix}.{p.get('label', '?')}"
            if p.get("parts"):
                walk(p["parts"], path)
            else:
                out.append((path.lstrip("."), p))

    if q.get("parts"):
        walk(q["parts"], "")
    else:
        out.append(("the question", q))
    return out


def instantiate(bp: dict, seed: int, n: int) -> tuple[dict, dict | None]:
    """→ (question item, figure spec | None). Every check must pass or it never returns."""
    env = sample(bp, seed)
    for name, expr in bp["derived"].items():
        try:
            v = eval_expr(expr, env, f"derived {name!r}")
        except (EvalError, ArithError) as e:
            die(f"derived {name!r} = {expr!r} could not be evaluated — {e}")
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            die(f"derived {name!r} evaluated to {v!r} — derived values must be numbers")
        if isinstance(v, float) and not math.isfinite(v):
            die(f"derived {name!r} evaluated to {v!r} — non-finite; tighten the constraints")
        env[name] = v

    q = sub_value(copy.deepcopy(bp["question"]), env, "question")
    fid = f"Q{n}" if bp["figure"] is not None else None
    out = {"n": n, "blueprint_id": bp["id"], "blueprint_seed": seed}
    for k, v in q.items():                # question.figure can't exist — load refused it
        out[k] = v
        if k == "stem" and fid:
            out["figure"] = fid
    if fid and "figure" not in out:
        out["figure"] = fid

    # checks — a leaf without one refuses; a False/erroring one fails naming seed + leaf
    leaves = question_leaves(out)
    missing = [name for name, leaf in leaves
               if not isinstance(leaf.get("check"), str) or not leaf["check"].strip()]
    if missing:
        die(f"blueprint {bp['id']!r}: no `check:` on leaf/leaves {', '.join(missing)} — "
            f"answers-as-code is the point")
    for name, leaf in leaves:
        try:
            ok = eval_expr(leaf["check"], {}, f"check on leaf {name!r}")
        except (EvalError, ArithError) as e:
            fail_check(f"check on leaf {name!r} (seed {seed}) errored — {e}")
        if ok is not True:
            fail_check(f"check on leaf {name!r} (seed {seed}) evaluates to {ok!r}, not True")

    spec = None
    if bp["figure"] is not None:
        spec = sub_value(copy.deepcopy(bp["figure"]), env, "figure", whole_typed=True)
        spec["figure_id"] = fid
        if not spec.get("stem"):
            spec["stem"] = out["stem"]
    return out, spec


# -------------------------------------------------------------------------------------------------
# The figure — build the instance so a bad draw is caught here, not at run-gates
# -------------------------------------------------------------------------------------------------
def build_figure(spec: dict, out_dir: Path) -> None:
    """Build the instantiated spec into `out_dir` via vdd_templates — TemplateError refuses."""
    vdd = _load("vdd_templates", "vdd_templates.py")
    spec = dict(spec)
    kind = spec.pop("template", None)
    if kind not in vdd.BUILDERS:
        die(f"figure {spec.get('figure_id')}: unknown template {kind!r} "
            f"(known: {', '.join(sorted(vdd.BUILDERS))})")
    vdd.vc.reset_ids()
    try:
        b = vdd.BUILDERS[kind](**spec)
    except vdd.TemplateError as e:
        die(f"figure {spec.get('figure_id', '<no figure_id>')}: {e}")
    except TypeError as e:
        die(f"figure {spec.get('figure_id', '<no figure_id>')}: spec keys do not fit "
            f"template {kind!r} — {e}")
    b.write(out_dir)


def merge_spec(path: str, spec: dict) -> None:
    """--spec-out: append the spec to that JSON list (create if absent; a duplicate figure_id
    refuses)."""
    p = Path(path)
    rows = []
    if p.is_file():
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            die(f"--spec-out {p}: not valid JSON — {e}")
        if not isinstance(rows, list):
            die(f"--spec-out {p}: must be a JSON list of figure specs")
    if any(isinstance(r, dict) and r.get("figure_id") == spec["figure_id"] for r in rows):
        die(f"--spec-out {p}: figure_id {spec['figure_id']!r} already present — refusing a duplicate")
    ordered = {"template": spec["template"], "figure_id": spec["figure_id"], "stem": spec["stem"]}
    ordered.update({k: v for k, v in spec.items() if k not in ordered})
    rows.append(ordered)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)                                 # atomic — a crash never halves the file


def cmd_instantiate(args) -> int:
    bp = load_blueprint(args.file)
    q, spec = instantiate(bp, args.seed, args.n)
    if spec is not None:
        with tempfile.TemporaryDirectory() as tmp:
            build_figure(spec, Path(tmp))          # bad instance caught here, not at run-gates
        if args.spec_out:
            merge_spec(args.spec_out, spec)
        fid = spec["figure_id"]
        print(f"# figures: add  {fid}: figures/{fid}.json")
    yaml = import_yaml()
    sys.stdout.write(yaml.safe_dump([q], sort_keys=False, allow_unicode=True))
    return 0


# -------------------------------------------------------------------------------------------------
# --self-test — the real suite is tests/test_blueprint.py; this is a smoke run over the fixture.
# -------------------------------------------------------------------------------------------------
def self_test() -> int:
    fixture = ROOT / "tests" / "fixtures" / "blueprint.yaml"
    if not fixture.is_file():
        print(f"blueprint --self-test: FAIL (no fixture at {fixture})")
        return 1
    fails = 0

    def check(ok, label):
        nonlocal fails
        if ok:
            print(f"  PASS  {label}")
        else:
            fails += 1
            print(f"  FAIL  {label}")

    bp = load_blueprint(str(fixture))
    q7, spec7 = instantiate(bp, 7, 3)
    check(instantiate(bp, 7, 3) == (q7, spec7), "same seed ⇒ identical output")
    check(any(instantiate(bp, s, 3)[0] != q7 for s in range(8)), "some other seed ⇒ a different draw")
    check(q7["n"] == 3 and q7["blueprint_id"] == bp["id"] and q7["blueprint_seed"] == 7,
          "emitted item carries n + blueprint_id + blueprint_seed")
    check(spec7 is not None and spec7["figure_id"] == "Q3" and isinstance(spec7["length"], int),
          "figure spec: figure_id Q3 + whole-slot typed number")
    check(all("{ln}" not in json.dumps(x) for x in (q7, spec7)), "no slot survives substitution")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            build_figure(spec7, Path(tmp))
            check(True, "figure instance builds via vdd_templates")
        except SystemExit:
            check(False, "figure instance builds via vdd_templates")
    bad = dict(bp, where=["ln < 0"])
    try:
        instantiate(bad, 1, 1)
        check(False, "impossible `where` gives up with exit 2")
    except SystemExit as e:
        check(e.code == 2, "impossible `where` gives up with exit 2")
    print(f"blueprint --self-test: {'PASS' if not fails else f'{fails} FAIL'}")
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="blueprint.py",
        description="instantiate one parameterised question blueprint into a content.yaml item")
    ap.add_argument("command", nargs="?", choices=["instantiate"])
    ap.add_argument("file", nargs="?", help="the blueprint YAML file")
    ap.add_argument("--seed", type=int, help="the sampling seed — same seed, same question")
    ap.add_argument("--n", type=int, help="the question number Q the item is instantiated as")
    ap.add_argument("--spec-out", help="merge the figure spec into this specs/figures.json list")
    ap.add_argument("--self-test", action="store_true",
                    help="offline smoke run over tests/fixtures/blueprint.yaml")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.command != "instantiate":
        die("a command is required: instantiate")
    if not args.file:
        die("instantiate needs a blueprint file")
    if args.seed is None:
        die("--seed N is required")
    if args.n is None:
        die("--n Q is required")
    if args.n < 1:
        die("--n must be >= 1 — it is the question number Q the item is instantiated as")
    return cmd_instantiate(args)


if __name__ == "__main__":
    sys.exit(main())
