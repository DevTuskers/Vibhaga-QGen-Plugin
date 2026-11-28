#!/usr/bin/env python3
"""Expand a reviewed family to content.yaml and a private variants ledger.

    family-expand.py FAMILY --count 12 --seed 5 --out content.yaml --ledger variants.yaml

The spec declares `id`, `cell_id`, `id_seed`, `difficulty`, `lessons`, `params`,
`constraints`, `solver` and a normal `question` without `n` (see the fixture).
Solver entries are ordered exact arithmetic expressions over parameters and
earlier entries. Constraints use the existing answers-as-code whitelist.
Optional `figure` is an existing VDD builder template; pass `--figures-out` for
the figure specs JSON that run-gates reads. Bilingual `figure_refs` can use
`figure.figure_id` as a local alias, or use one shared key if the alias is
omitted; the expansion binds that key to the generated figure on each variant.
Keep these outputs in the run directory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import random
import re
import sys
import unicodedata
from fractions import Fraction
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent
loader = importlib.util.spec_from_file_location("question_blueprint", TOOLS / "blueprint.py")
bp = importlib.util.module_from_spec(loader)
loader.loader.exec_module(bp)
bs = bp.ca._bs()

MAX_SPACE = 100_000
IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def positive_int(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def domains(params):
    if not isinstance(params, dict) or not params:
        raise ValueError("params must be a nonempty mapping")
    result = {}
    for name, spec in params.items():
        if not isinstance(name, str) or not bp.NAME_RE.fullmatch(name) or name in bp.ca.FUNCS:
            raise ValueError(f"invalid parameter name {name!r}")
        if not isinstance(spec, dict):
            raise ValueError(f"{name}: expected a parameter mapping")
        if set(spec) in ({"range"}, {"range", "step"}):
            bounds = spec["range"]
            if (not isinstance(bounds, list) or len(bounds) != 2
                    or not all(type(x) is int and abs(x) <= bp.ca.MAX_ABS for x in bounds)):
                raise ValueError(f"{name}: expected an inclusive integer range [lo, hi]")
            step = positive_int(spec.get("step", 1), f"{name}.step")
            values = range(bounds[0], bounds[1] + 1, step)
        elif set(spec) == {"choices"} and isinstance(spec["choices"], list):
            values = spec["choices"]
        else:
            raise ValueError(f"{name}: declare range (optional step) or choices")
        if not values or len(values) > MAX_SPACE:
            raise ValueError(f"{name}: empty or oversized parameter domain")
        if any(type(x) is not int or abs(x) > bp.ca.MAX_ABS for x in values):
            raise ValueError(f"{name}: choices and range values must be bounded integers")
        result[name] = tuple(dict.fromkeys(values))
    if math.prod(map(len, result.values())) > MAX_SPACE:
        raise ValueError(f"parameter space exceeds {MAX_SPACE}; tighten the ranges")
    return result


def solve(expr, env):
    if not isinstance(expr, str) or len(expr) > 400 or "**" in expr:
        raise ValueError("solver expressions use bounded exact +, -, *, / arithmetic")
    def bind(match):
        name = match.group()
        if name not in env:
            raise ValueError(f"unknown solver name {name!r}")
        value = Fraction(env[name])
        return f"({value.numerator}/{value.denominator})"
    return bp.ca._worked_value(IDENTIFIER.sub(bind, expr).strip(), exact=True)


def display(value):
    if not isinstance(value, Fraction) or value.denominator == 1:
        return str(int(value))
    if 10_000 % value.denominator == 0:
        whole, digits = divmod(abs(value.numerator) * (10_000 // value.denominator), 10_000)
        return (("-" if value < 0 else "") + f"{whole}.{digits:04d}").rstrip("0")
    sign = "-" if value < 0 else ""
    return sign + r"\frac{" + str(abs(value.numerator)) + "}{" + str(value.denominator) + "}"


def render(value, env, *, typed=False, arithmetic=False):
    if isinstance(value, str):
        slot = bp.SLOT_RE.fullmatch(value)
        if typed and slot and slot[1] in env:
            number = Fraction(env[slot[1]])
            if 10_000 % number.denominator != 0:
                raise ValueError(f"figure slot {slot[1]} must be an integer or terminating decimal")
            return int(number) if number.denominator == 1 else float(number)
        def replace(match):
            name = match[1]
            prefix = value[:match.start()]
            latex_group = bp.CMD_GROUP_RE.search(prefix) or prefix.endswith(("^", "_", "}"))
            if name not in env:
                if latex_group:
                    return match[0]
                raise ValueError(f"unknown template slot {{{name}}}")
            if prefix.endswith(bp.TEXT_GROUPS):
                raise ValueError(f"ambiguous template slot {{{name}}} directly inside a LaTeX text group")
            result = f"({env[name]})" if arithmetic else display(env[name])
            return "{" + result + "}" if latex_group else result
        return bp.SLOT_RE.sub(replace, value)
    if isinstance(value, dict):
        return {key: render(item, env, typed=typed, arithmetic=key == "check") for key, item in value.items()}
    if isinstance(value, list):
        return [render(item, env, typed=typed) for item in value]
    return value


def validate_template(node, solver, depth=0):
    fields = ("stem", "stem_si") if depth == 0 else ("text", "text_si")
    if not isinstance(node, dict):
        raise ValueError("question and parts must be mappings")
    parts = node.get("parts", [])
    if not isinstance(parts, list) or (parts and depth >= 2):
        raise ValueError("parts must be lists nested at most two levels")
    if not parts or (depth and any(key in node for key in ("approach", "final"))):
        fields += ("approach", "approach_si", "final", "final_si")
        for side in ("final", "final_si"):
            if not isinstance(node.get(side), str) or not (set(bp.SLOT_RE.findall(node[side])) & solver):
                raise ValueError(f"{side} must use a computed solver slot")
        if not parts:
            fields += ("check",)
            slots = set(bp.SLOT_RE.findall(node["final"] + node["final_si"])) & solver
            if not isinstance(node.get("check"), str) or not slots <= set(bp.SLOT_RE.findall(node["check"])):
                raise ValueError("check must verify the solver slots used in both finals")
    for key in fields:
        if not isinstance(node.get(key), str) or not node[key].strip():
            raise ValueError(f"question template needs nonempty {key}")
    for part in parts:
        validate_template(part, solver, depth + 1)


def surface_key(question, figure=None):
    def text(node):
        return [node.get(k, "") for k in ("stem", "stem_si", "text", "text_si")] + [
            field for part in node.get("parts", []) for field in text(part)
        ]
    clean = "\n".join(" ".join(unicodedata.normalize("NFC", s).casefold().split()) for s in text(question))
    if figure is not None:
        payload = {key: value for key, value in figure.items() if key != "figure_id"}
        clean += "\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def figure_references(node):
    pair = node.get("figure_refs")
    if isinstance(pair, dict):
        for language in ("english", "sinhala"):
            refs = pair.get(language)
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, dict) and isinstance(ref.get("figure"), str):
                        yield ref
    for child in node.get("parts", []):
        yield from figure_references(child)


def bind_figure_refs(question, alias, figure_id):
    refs = list(figure_references(question))
    if alias is None:
        names = {ref["figure"] for ref in refs}
        if len(names) > 1:
            raise ValueError("figure_refs use multiple keys; declare the template alias with figure.figure_id")
        alias = next(iter(names), None)
    for ref in refs:
        if ref["figure"] == alias:
            ref["figure"] = figure_id


def expand(spec, count, seed, first, history=()):
    if not isinstance(spec, dict):
        raise ValueError("expected a family mapping")
    family, cell = spec.get("id"), spec.get("cell_id")
    if not all(isinstance(x, str) and bp.BP_ID_RE.fullmatch(x) for x in (family, cell)):
        raise ValueError("id and cell_id must be lowercase keys")
    count, first = positive_int(count, "count"), positive_int(first, "first question number")
    limit = positive_int(spec.get("variant_limit", 30), "variant_limit")
    colliding = [row for row in history if row["family_id"] == family]
    if count + len(colliding) > limit:
        raise ValueError(f"{family}: requested and previous variants exceed limit {limit}")
    id_seed, difficulty, lessons = (spec.get(key) for key in ("id_seed", "difficulty", "lessons"))
    if (not isinstance(id_seed, str) or not id_seed.strip() or difficulty not in ("easy", "medium", "hard")
            or not isinstance(lessons, dict) or len(lessons) != 1
            or not all(bs.is_uuid(value) for value in lessons.values())):
        raise ValueError("id_seed, valid difficulty and exactly one lesson UUID are required")
    question, figure = spec.get("question"), spec.get("figure")
    if not isinstance(question, dict) or question.get("lessons") != list(lessons):
        raise ValueError("question.lessons must name the sole lesson key")
    if {"n", "blueprint_id", "blueprint_seed", "figure", "difficulty"} & set(question):
        raise ValueError("question may not override generated numbers, blueprint keys, figure or difficulty")
    if figure is not None and (not isinstance(figure, dict) or not isinstance(figure.get("template"), str)):
        raise ValueError("figure needs a VDD template")

    values = domains(spec.get("params"))
    solver = spec.get("solver")
    if not isinstance(solver, dict) or not solver or any(
            not isinstance(name, str) or not bp.NAME_RE.fullmatch(name) or name in values
            for name in solver):
        raise ValueError("solver must map new slot names to ordered exact arithmetic expressions")
    constraints = spec.get("constraints", [])
    if not isinstance(constraints, list) or not all(isinstance(x, str) for x in constraints):
        raise ValueError("constraints must be expression strings")
    validate_template(question, set(solver))
    max_den = positive_int(spec.get("max_denominator", 100), "max_denominator")
    max_abs = positive_int(spec.get("max_abs", 10_000), "max_abs")

    questions, ledger, figures = [], [], []
    seen_numbers = {tuple(row["number_key"]) for row in colliding}
    seen_surface = {row["surface_sha256"] for row in history}
    draws = list(itertools.product(*values.values()))
    rng = random.Random(seed)
    rng.shuffle(draws)
    for draw in draws:
        number_key = tuple(sorted(draw))
        if number_key in seen_numbers or any(abs(x) > max_abs for x in draw):
            continue
        params = dict(zip(values, draw))
        allowed = [bp.eval_expr(expr, params, "constraint") for expr in constraints]
        if any(type(ok) is not bool for ok in allowed):
            raise ValueError("constraints must return booleans")
        if not all(allowed):
            continue
        env = dict(params)
        for name, expr in solver.items():
            env[name] = solve(expr, env)
        answers = {name: env[name] for name in solver}
        if any(x.denominator > max_den or abs(x) > max_abs for x in answers.values()):
            continue
        item = render(question, env)
        fig = render(figure, env, typed=True) if figure is not None else None
        surface = surface_key(item, fig)
        if surface in seen_surface:
            continue
        n = first + len(questions)
        for label, leaf in bp.question_leaves(item):
            tree = bp.ca.parse_check(leaf["check"], f"q{n} {label}")
            with bp.ca._deadline(bp.ca.EVAL_SECONDS):
                check = bp.ca._eval(tree)
            if check is not True:
                raise ValueError(f"q{n} {label}: independent check did not pass for {params}")
        if fig is not None:
            fid = f"Q{n}"
            bind_figure_refs(item, fig.get("figure_id"), fid)
            figures.append({**fig, "figure_id": fid, "stem": fig.get("stem") or item["stem"]})
            item["figure"] = fid
        questions.append({"n": n, "difficulty": difficulty, **item})
        ledger.append({"family_id": family, "cell_id": cell, "n": n, "seed": seed,
                       "question_id": bs.q_id(id_seed.strip(), f"q{n}"),
                       "params": params, "number_key": list(number_key), "surface_sha256": surface,
                       "answers": {name: str(value) for name, value in answers.items()}})
        seen_numbers.add(number_key)
        seen_surface.add(surface)
        if len(questions) == count:
            break
    if len(questions) != count:
        raise ValueError(f"{family}: only {len(questions)} distinct friendly variants for requested {count}")
    content = {"id_seed": id_seed, "difficulty": difficulty, "lessons": lessons, "questions": questions}
    if figures:
        content["figures"] = {fig["figure_id"]: f"figures/{fig['figure_id']}.json" for fig in figures}
    sample_size = min(count, max(3, (count + 9) // 10))
    return content, {"variants": ledger, "sample": sorted(rng.sample(range(first, first + count), sample_size))}, figures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", type=Path)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--prior-ledger", type=Path, action="append", default=[])
    parser.add_argument("--figures-out", type=Path)
    args = parser.parse_args()
    try:
        spec = yaml.safe_load(args.family.read_text(encoding="utf-8"))
        history = [row for path in args.prior_ledger
                   for row in yaml.safe_load(path.read_text(encoding="utf-8"))["variants"]]
        content, ledger, figures = expand(spec, args.count, args.seed, args.first, history)
        if figures and args.figures_out is None:
            raise ValueError("a family with a VDD template requires --figures-out")
        for path, data in ((args.out, content), (args.ledger, ledger)):
            path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        if args.figures_out is not None:
            args.figures_out.write_text(json.dumps(figures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{spec['id']}: {len(ledger['variants'])} variants; sample: {', '.join(map(str, ledger['sample']))}")
    except (OSError, ValueError, SyntaxError, ArithmeticError, TypeError, KeyError,
            yaml.YAMLError, bp.EvalError, bp.ArithError) as exc:
        parser.exit(2, f"family-expand: {exc}\n")


if __name__ == "__main__":
    main()
