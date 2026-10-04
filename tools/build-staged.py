#!/usr/bin/env python3
"""build-staged.py — content.yaml (the lead-authored generation spec) → staged.json {"questions":[...]}.

New for vibhaga-qgen (replaces the paper-side build-staged.py + yaml-from-staged.py — those compiled a
staged doc out of an extraction run; here the author IS the source). Usage:

    build-staged.py content.yaml [--out staged.json] [--ids-out ids.json]
    build-staged.py content.json [--out staged.json] [--ids-out ids.json]  # JSON input needs no PyYAML

`--ids-out` additionally writes the bare JSON list of question_ids in question order — exactly the
file `playground-publish.py publish --ids-file` consumes (non-empty unique uuids).

content.yaml shape (keys in `lessons:`/`figures:` are local names resolved by the builder):

    id_seed: "w0-session"                    # required — feeds every deterministic id
    lessons: {L07: <lesson uuid>, L09: <uuid>}   # key → real lesson uuid
    figures: {F1: figures/q1.json}               # key → VDD JSON file, relative to this file
    questions:
      - n: 1
        lessons: [L07, L09]
        stem: "A cuboid face is 5 cm by 2 cm. Find its area."
        figure: F1                              # optional → question diagram_dsl
        blueprint_id: "rect-split"              # optional, actor-only — tools/blueprint.py's
        blueprint_seed: 7                       #   provenance (a pair; never emitted; at most
                                                #   ONE variant per blueprint per batch)
        approach: "…"                           # only when there are NO parts (whole-question answer)
        final: "…"
        parts:
          - label: a                            # BARE label — "(a)", "a)", "a." are refused
            text: "…"
            figure: F2                          # optional → sub-question diagram_dsl
            approach: "…"
            final: "…"
            parts: [ … ]                        # optional second level — depth 2 is the cap

Output item shape = the staged-doc schema Vibhaga-API serves (`api/src/shared/staged-question.ts` +
`onboarding/publish.ts buildQuestionRows`/`collectSubAnswers`):
question_id · question_number (JSON number) · sort_order · is_multipart · question_text ·
question_text_sinhala: null · lesson_ids (uuids) · diagram_dsl · answers[{answer_id, approach,
final_answer_latex}] only on part-less questions · sub_questions[{sub_question_id, label, sort_order,
text, text_sinhala, diagram_dsl, sub_answer{sub_answer_id, approach, final_answer_latex},
sub_questions}] · ingestion_metadata {needs_human_review: true} · NO exam key anywhere (0018 PD-6 —
scope lives on the batch row, never on a question).

ids are uuid5(NAMESPACE, f"{id_seed}/q{n}" for the question, + "/<label-path>" per part,
+ "+answer" for the (sub-)answer) — two runs on the same spec are byte-identical.

⚠️ IDENTITY IS THE SEED + NUMBER + LABEL PATH. After a first publish, keep `id_seed`, `n` and every
label stable: renumbering or relabelling a part creates NEW uuids, and publish writes NEW rows that
orphan the published ones — it does not rename in place. (Sibling labels must therefore be unique —
two parts labelled `a` under one parent collide on the same sub_question_id, and the builder refuses.)

Exit 0 wrote the doc · exit 2 refused (duplicate n · duplicate sibling label · unknown lesson/figure
key · missing figure file · parts deeper than 2 · leaf part without approach+final · a question
carrying both parts and a whole answer · non-bare label · non-uuid lesson · two questions sharing a
blueprint_id · malformed spec).
"""
import argparse
import json
import re
import sys
import uuid
from pathlib import Path

# uuid4 generated once for this tool — a fixed namespace makes every output id deterministic.
NAMESPACE = uuid.UUID("6b1c9c6e-3d5e-4f2a-9b8c-7d0e1f2a3b4c")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
BARE_LABEL = re.compile(r"^[0-9A-Za-z]+$")   # "(a)", "a)", "a.", "a :" — anything punctuated is not bare

# `check`/`level` are actor-only keys on leaves — the answers-as-code expression and the R/M/H
# rubric level (tools/check-answers.py, precritic-lint --rubric). `blueprint_id`/`blueprint_seed`
# are actor-only keys on questions — they record which blueprint + draw produced the item
# (tools/blueprint.py); two questions from one blueprint in a batch are refused. build-staged
# validates their shape and never emits them into staged.json.
BP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")   # the same contract tools/blueprint.py enforces
Q_KEYS = {"n", "lessons", "stem", "figure", "approach", "final", "parts", "check", "level",
          "blueprint_id", "blueprint_seed"}
P_KEYS = {"label", "text", "figure", "approach", "final", "parts", "check", "level"}
TOP_KEYS = {"id_seed", "lessons", "figures", "questions"}


def die(msg):
    print(f"build-staged: {msg}", file=sys.stderr)
    sys.exit(2)


def load_spec(path):
    text = Path(path).read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError:
            die("PyYAML is not installed and the input is not .json — `pip install pyyaml` or pass content.json (JSON is a YAML subset)")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            die(f"YAML parse error: {exc}")
    if not isinstance(data, dict):
        die("spec must be a mapping at the top level")
    return data


def is_uuid(value):
    return isinstance(value, str) and UUID_RE.match(value) is not None


def q_id(seed, *path):
    return str(uuid.uuid5(NAMESPACE, "/".join([seed, *path])))


def resolve_figure(key, figures, base, where):
    if key not in figures:
        die(f"{where}: unknown figure key {key!r} (declared: {sorted(figures) or 'none'})")
    fpath = base / figures[key]
    if not fpath.is_file():
        die(f"{where}: figure file {figures[key]!r} not found (looked at {fpath})")
    try:
        return json.loads(fpath.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        die(f"{where}: figure file {figures[key]!r} is not valid JSON: {exc}")


def answer_pair(node, where, required):
    approach, final = node.get("approach"), node.get("final")
    if (approach is None) != (final is None):
        die(f"{where}: 'approach' and 'final' must come as a pair (got {'approach' if approach is not None else 'final'} only)")
    if required and approach is None:
        die(f"{where}: a leaf part needs 'approach' and 'final'")
    if approach is not None and (not isinstance(approach, str) or not approach.strip()):
        die(f"{where}: 'approach' must be nonempty text")
    if final is not None and (not isinstance(final, str) or not final.strip()):
        die(f"{where}: 'final' must be nonempty text")
    return approach is not None


def check_sibling_labels(children, where):
    """Two same-labelled siblings would collide on the same id — the label is part of the uuid5 path.
    Refuse before any row is built. (Missing/non-bare labels are left for build_part's own refusal.)"""
    seen = set()
    for child in children:
        lab = child.get("label") if isinstance(child, dict) else None
        if not isinstance(lab, str):
            continue
        lab = lab.strip()
        if lab in seen:
            die(f"{where}: duplicate part label {lab!r} among siblings — labels key the "
                f"sub_question_id, so two same-named parts collide")
        seen.add(lab)


def check_meta(node, where):
    """`level` ∈ {R,M,H} and `check` a string — on LEAVES only: on a node with `parts`
    either key would be silently ignored (leaves()/leaf_levels() never visit containers),
    so it is refused rather than let look checked."""
    if node.get("parts") and \
            (node.get("check") is not None or node.get("level") is not None):
        die(f"{where}: 'check'/'level' are leaf-only keys — this node has 'parts'")
    lvl = node.get("level")
    if lvl is not None and lvl not in ("R", "M", "H"):
        die(f"{where}: level must be one of R, M, H (got {lvl!r})")
    chk = node.get("check")
    if chk is not None and not isinstance(chk, str):
        die(f"{where}: check must be a string expression (got {chk!r})")


def build_part(node, base_id, sort_order, depth, figures, base, where):
    if not isinstance(node, dict):
        die(f"{where}: a part must be a mapping")
    unknown = set(node) - P_KEYS
    if unknown:
        die(f"{where}: unknown part keys {sorted(unknown)} (allowed: {sorted(P_KEYS)})")
    check_meta(node, where)
    label = node.get("label")
    if not isinstance(label, str) or not BARE_LABEL.match(label.strip() or " "):
        die(f'{where}: label must be BARE text — write "a" not "(a)", "a)" or "a." (got {label!r})')
    label = label.strip()
    text = node.get("text")
    if not isinstance(text, str) or not text.strip():
        die(f"{where}: part 'text' is required")
    if depth > 2:
        die(f"{where}: parts nest at most 2 levels deep")
    children = node.get("parts") or []
    if not isinstance(children, list):
        die(f"{where}: 'parts' must be a list")
    check_sibling_labels(children, where)
    has_answer = answer_pair(node, where, required=not children)
    part_base = f"{base_id}/{label}"
    out = {
        "sub_question_id": q_id(part_base),
        "label": label,
        "sort_order": sort_order,
        "text": text,
        "text_sinhala": None,
        "diagram_dsl": resolve_figure(node["figure"], figures, base, where) if node.get("figure") else None,
    }
    if has_answer:
        out["sub_answer"] = {"sub_answer_id": q_id(part_base, "+answer"),
                             "approach": node["approach"], "final_answer_latex": node["final"]}
    out["sub_questions"] = [
        build_part(child, part_base, i, depth + 1, figures, base, f"{where}.{child.get('label', i) if isinstance(child, dict) else i}")
        for i, child in enumerate(children)
    ]
    return out


def build_question(node, index, figures, lessons, base, seed):
    where = f"questions[{index}]"
    if not isinstance(node, dict):
        die(f"{where}: a question must be a mapping")
    unknown = set(node) - Q_KEYS
    if unknown:
        die(f"{where}: unknown question keys {sorted(unknown)} (allowed: {sorted(Q_KEYS)})")
    check_meta(node, f"{where} (q{node.get('n')})")
    n = node.get("n")
    if not isinstance(n, int) or isinstance(n, bool):
        die(f"{where}: 'n' must be an integer question number (got {n!r})")
    qbase = f"q{n}"
    bp_id, bp_seed = node.get("blueprint_id"), node.get("blueprint_seed")
    if (bp_id is None) != (bp_seed is None):
        die(f"{where} (q{n}): blueprint_id and blueprint_seed come as a pair "
            f"(tools/blueprint.py emits both)")
    if bp_id is not None:
        if not isinstance(bp_id, str) or not BP_ID_RE.fullmatch(bp_id):
            die(f"{where} (q{n}): blueprint_id must match {BP_ID_RE.pattern} (got {bp_id!r})")
        if not isinstance(bp_seed, int) or isinstance(bp_seed, bool):
            die(f"{where} (q{n}): blueprint_seed must be an int (got {bp_seed!r})")
    stem = node.get("stem")
    if not isinstance(stem, str) or not stem.strip():
        die(f"{where} (q{n}): 'stem' is required")
    lesson_keys = node.get("lessons")
    if not isinstance(lesson_keys, list) or not lesson_keys:
        die(f"{where} (q{n}): 'lessons' must be a nonempty list of lesson keys")
    lesson_ids = []
    for key in lesson_keys:
        if key not in lessons:
            die(f"{where} (q{n}): unknown lesson key {key!r} (declared: {sorted(lessons) or 'none'})")
        lesson_ids.append(lessons[key])
    children = node.get("parts") or []
    if not isinstance(children, list):
        die(f"{where} (q{n}): 'parts' must be a list")
    check_sibling_labels(children, f"{where} (q{n})")
    if children and (node.get("approach") is not None or node.get("final") is not None):
        die(f"{where} (q{n}): a question carries either parts OR a whole answer — 'approach'/'final' are only for a part-less question")
    has_answer = answer_pair(node, f"{where} (q{n})", required=not children)
    seed_q = f"{seed}/{qbase}"
    out = {
        "question_id": q_id(seed_q),
        "question_number": n,
        "sort_order": index,
        "is_multipart": bool(children),
        "question_text": stem,
        "question_text_sinhala": None,
        "lesson_ids": lesson_ids,
        "diagram_dsl": resolve_figure(node["figure"], figures, base, f"{where} (q{n})") if node.get("figure") else None,
    }
    if has_answer:
        out["answers"] = [{"answer_id": q_id(seed_q, "+answer"),
                           "approach": node["approach"], "final_answer_latex": node["final"]}]
    else:
        out["answers"] = []
    if children:
        out["sub_questions"] = [
            build_part(child, seed_q, i, 1, figures, base, f"{where} (q{n}).{child.get('label', i) if isinstance(child, dict) else i}")
            for i, child in enumerate(children)
        ]
    out["ingestion_metadata"] = {"needs_human_review": True}
    return out


def build(spec_path):
    spec_path = Path(spec_path)
    spec = load_spec(spec_path)
    unknown = set(spec) - TOP_KEYS
    if unknown:
        die(f"spec: unknown top-level keys {sorted(unknown)} (allowed: {sorted(TOP_KEYS)})")
    seed = spec.get("id_seed")
    if not isinstance(seed, str) or not seed.strip():
        die("spec: 'id_seed' is required (a stable string — it feeds every deterministic id)")
    lessons = spec.get("lessons") or {}
    if not isinstance(lessons, dict):
        die("spec: 'lessons' must be a {key: lesson-uuid} mapping")
    for key, value in lessons.items():
        if not is_uuid(value):
            die(f"spec: lessons.{key} = {value!r} is not a uuid — real lesson uuids come from `playground-publish lessons` or the corpus")
    figures = spec.get("figures") or {}
    if not isinstance(figures, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in figures.items()):
        die("spec: 'figures' must be a {key: relative-path} mapping")
    questions = spec.get("questions")
    if not isinstance(questions, list) or not questions:
        die("spec: 'questions' must be a nonempty list")
    base = spec_path.resolve().parent
    out = []
    seen = {}
    seen_blueprints = {}                       # blueprint_id -> (index, question_number)
    for i, node in enumerate(questions):
        q = build_question(node, i, figures, lessons, base, seed.strip())
        if q["question_number"] in seen:
            die(f"duplicate question number n={q['question_number']} (first at {seen[q['question_number']]})")
        seen[q["question_number"]] = f"questions[{i}]"
        if isinstance(node, dict) and node.get("blueprint_id") is not None:
            bp_id = node["blueprint_id"]
            if bp_id in seen_blueprints:
                j, m = seen_blueprints[bp_id]
                die(f"questions[{j}] (q{m}) and questions[{i}] (q{q['question_number']}) both "
                    f"instantiate blueprint '{bp_id}' — owner ruling 2026-10-03: at most one "
                    f"variant per blueprint per batch")
            seen_blueprints[bp_id] = (i, q["question_number"])
        out.append(q)
    return {"questions": out}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="build-staged.py", description="content.yaml → staged.json for a generated question batch")
    ap.add_argument("spec", help="content.yaml (or content.json — needs no PyYAML)")
    ap.add_argument("--out", help="output staged.json path (default: staged.json beside the spec; '-' for stdout)")
    ap.add_argument("--ids-out", help="also write the JSON list of question_ids in question order — the exact file playground-publish.py publish --ids-file consumes")
    args = ap.parse_args(argv)
    if not Path(args.spec).is_file():
        die(f"no such spec file: {args.spec}")
    doc = build(Path(args.spec))
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    if args.out == "-":
        sys.stdout.write(text)
    else:
        out = Path(args.out) if args.out else Path(args.spec).resolve().parent / "staged.json"
        out.write_text(text, encoding="utf-8")
        print(f"build-staged: wrote {out} ({len(doc['questions'])} question(s))")
    if args.ids_out:
        ids = Path(args.ids_out)
        ids.write_text(json.dumps([q["question_id"] for q in doc["questions"]], indent=1) + "\n",
                       encoding="utf-8")
        print(f"build-staged: wrote {ids} ({len(doc['questions'])} question id(s), in question order)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
