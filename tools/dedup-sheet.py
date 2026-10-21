#!/usr/bin/env python3
"""Build a read-only copy-check sheet from lesson cards and live question rows."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUERIES = HERE.parent / "queries.sql"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


critic_read = load_module("critic_read_for_dedup", HERE / "critic-read.py")
scope_cards = load_module("scope_cards_for_dedup", HERE / "scope-cards.py")


def die(message: str, code: int = 2) -> None:
    print(f"dedup-sheet: {message}", file=sys.stderr)
    raise SystemExit(code)


def run_psql(pg: dict[str, str], sql: str, variables: dict[str, str],
             runner=subprocess.run) -> list[str]:
    argv = ["psql", "-X", "-A", "-t", "-q", "-w", "-v", "ON_ERROR_STOP=1"]
    for key, value in variables.items():
        argv.extend(["-v", f"{key}={value}"])
    argv.extend(["-f", "-"])
    try:
        proc = runner(argv, input=sql, capture_output=True, text=True,
                      env={**os.environ, **pg})
    except FileNotFoundError:
        die("psql is not on PATH", 1)
    if proc.returncode:
        tail = proc.stderr.strip().splitlines()
        die("psql failed" + (f": {tail[-1]}" if tail else ""), 1)
    return [line for line in proc.stdout.splitlines() if line.strip()]


def card_path(spec: str, grade: int, corpus: str | None) -> tuple[str, Path]:
    if "=" not in spec:
        die(f"--card {spec!r} must be KEY=NN")
    key, number = spec.split("=", 1)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key) or not number.isdigit():
        die(f"--card {spec!r} must be KEY=NN")
    args = argparse.Namespace(grade=grade, corpus=corpus)
    try:
        return key, scope_cards.resolve_card_arg(number, args)
    except (SystemExit, OSError) as exc:
        if isinstance(exc, SystemExit):
            raise
        die(f"cannot resolve card {spec}: {exc}")


def display_value(item, *keys) -> str:
    if isinstance(item, dict):
        for key in keys:
            value = item.get(key)
            if value:
                return str(value)
    return str(item or "")


def excerpt(text: str, limit: int = 240) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def load_card(cpath: Path) -> dict:
    yaml = scope_cards.import_yaml()
    data = yaml.safe_load(cpath.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        die(f"{cpath.name}: scope card must be a mapping")
    return data


def lookup_lesson(pg: dict[str, str], grade: int, number: int, runner) -> str:
    sql = ("BEGIN TRANSACTION READ ONLY;\n"
           "SELECT lesson_id::text FROM lessons "
           "WHERE grade = :'grade'::int AND sort_order = :'lesson_number'::int * 10 "
           "AND subject = 'Mathematics';\nROLLBACK;\n")
    rows = run_psql(pg, sql, {"grade": str(grade), "lesson_number": str(number)}, runner)
    if len(rows) != 1 or not re.fullmatch(r"[0-9a-fA-F-]{36}", rows[0]):
        die(f"lesson lookup for grade {grade} lesson {number:02d} returned {len(rows)} ids")
    return rows[0]


def live_rows(pg: dict[str, str], lesson_id: str, runner) -> list[dict]:
    text = QUERIES.read_text(encoding="utf-8")
    start = text.index("-- Q1c —")
    select = text.index("SELECT jsonb_build_object(", start)
    end = text.index("\n\n\n-- ===", select)
    query = text[select:end].strip().rstrip(";")
    sql = f"BEGIN TRANSACTION READ ONLY;\n{query};\nROLLBACK;\n"
    lines = run_psql(pg, sql, {"lesson_id": lesson_id}, runner)
    try:
        return [json.loads(line) for line in lines]
    except ValueError as exc:
        die(f"Q1c returned invalid JSON: {exc}", 1)


def render_lesson(key: str, number: int, card: dict, rows: list[dict], plan, similar) -> list[str]:
    generated = card.get("generated") or {}
    curated = card.get("curated") or {}
    sections = generated.get("sections") or []
    worked = generated.get("worked_examples") or []
    exercises = generated.get("exercises") or []
    activities = generated.get("activities") or []
    hooks = curated.get("difficulty_hooks") or []
    lines = [f"## L{number:02d} · {key}",
             f"live rows {len(rows)} · sections {len(sections)} · worked examples {len(worked)} · "
             f"exercises {len(exercises)} · activities {len(activities)} · difficulty_hooks {len(hooks)}", ""]
    for label, marker, items in (
        ("Worked examples", "WE", worked),
        ("Exercises", "EX", exercises),
        ("Activities", "ACT", activities),
    ):
        lines += [f"### {label}"]
        for index, item in enumerate(items, 1):
            item_id = display_value(item, "id", "number", "key", "heading") or str(index)
            heading = display_value(item, "heading", "title", "name", "section") or f"{label[:-1]} {index}"
            body = display_value(item, "excerpt", "text", "description", "content")
            lines.append(f"- `L{number:02d}·{marker}{item_id}` **{heading}** — {excerpt(body)}")
        if not items:
            lines.append("- none")
        lines.append("")
    lines.append("### Live question rows")
    for row in rows:
        qid = row.get("question_id")
        lines.append(f"- `{qid}` · {row.get('status')} · Q{row.get('question_number')}")
        lines.append(f"  - EN: {row.get('stem_english') or ''}")
        lines.append(f"  - SI: {row.get('stem_sinhala') or ''}")
        for part in row.get("parts") or []:
            lines.append(f"  - `{part.get('label')}` EN: {part.get('text_english') or ''}")
            lines.append(f"    SI: {part.get('text_sinhala') or ''}")
    if plan is not None:
        lines += ["", "### Plan lines"]
        plan_items = plan if isinstance(plan, list) else (
            plan.get("items", []) if isinstance(plan, dict) else [])
        similar_items = similar.get("results", []) if isinstance(similar, dict) else []
        similar_by_key = {item.get("key"): item for item in similar_items
                          if isinstance(item, dict) and item.get("key")}
        for item in plan_items:
            key_name = item.get("key") if isinstance(item, dict) else None
            lines.append(f"- {json.dumps(item, ensure_ascii=False)}")
            neighbours = (similar_by_key.get(key_name) or {}).get("neighbours", [])
            if not neighbours:
                lines.append("  - similar neighbours: none")
            for neighbour in neighbours:
                lines.append(f"  - similar {neighbour.get('score')} · {neighbour.get('question_id')}: "
                             f"{neighbour.get('stem')}")
                for part in neighbour.get("parts") or []:
                    lines.append(f"    - {part}")
    if similar is not None and plan is None:
        lines += ["", "### Similar neighbours"]
        lines.append(json.dumps(similar, ensure_ascii=False, indent=2))
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grade", type=int, required=True)
    ap.add_argument("--card", action="append", default=[], required=True, metavar="KEY=NN")
    ap.add_argument("--lesson-id", action="append", default=[], metavar="KEY=UUID")
    ap.add_argument("--plan")
    ap.add_argument("--similar")
    ap.add_argument("--db-env")
    ap.add_argument("--corpus")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    explicit = {}
    for spec in args.lesson_id:
        if "=" not in spec:
            die(f"--lesson-id {spec!r} must be KEY=UUID")
        key, lesson_id = spec.split("=", 1)
        if not re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", lesson_id):
            die(f"--lesson-id {spec!r} has an invalid UUID")
        explicit[key] = lesson_id
    plan = None
    if args.plan:
        plan = scope_cards.import_yaml().safe_load(Path(args.plan).read_text(encoding="utf-8"))
    similar = json.loads(Path(args.similar).read_text(encoding="utf-8")) if args.similar else None
    url = critic_read.resolve_db_url(args.db_env)
    pg = critic_read.pg_env_from_url(url)
    out = [f"# Dedup sheet · grade {args.grade}", ""]
    for spec in args.card:
        key, number = spec.split("=", 1)
        n = int(number)
        _, cpath = card_path(spec, args.grade, args.corpus)
        card = load_card(cpath)
        lesson_id = explicit.get(key) or card.get("lesson_id") or lookup_lesson(pg, args.grade, n, subprocess.run)
        if not re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}",
                            str(lesson_id)):
            die(f"lesson id for {key} is not a UUID")
        out.extend(render_lesson(key, n, card, live_rows(pg, str(lesson_id), subprocess.run), plan, similar))
        out.append("")
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(f"dedup-sheet: {len(args.card)} lesson(s) → {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
