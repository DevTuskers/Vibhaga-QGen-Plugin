#!/usr/bin/env python3
"""Draft and check one lesson's coverage grid, without a database connection.

    lesson-blueprint.py build CARD --out blueprint.yaml
    lesson-blueprint.py check blueprint.yaml --coverage mapped-rows.yaml

Fill `cells` with feasible combinations, not a Cartesian product. Each cell has
`id`, `section` (an id from the skeleton), `skill`, `task_chain` and every
axis in `axes`. The optional coverage export is a list or a mapping with a
`questions` list; map its live `question_id` rows to `cell_id` by review.
Unmapped rows are counted separately, not assumed to cover a cell.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import yaml

AXES = {
    "representation": ("word", "table", "graph", "diagram"),
    "unknown_direction": ("forward", "reverse", "find-error", "justify", "decide"),
    "band": ("easy", "medium", "hard"),
    "format": ("structured", "mcq", "short"),
}
KEY = re.compile(r"[a-z0-9][a-z0-9-]*")


def read(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def is_text(value):
    return isinstance(value, str) and bool(value.strip())


def build(card_path):
    raw = card_path.read_bytes()
    card = yaml.safe_load(raw)
    if not isinstance(card, dict) or card.get("schema_version") != 1:
        raise ValueError("expected a version 1 scope card")
    generated, curated = card.get("generated"), card.get("curated")
    if (not isinstance(generated, dict) or not isinstance(curated, dict)
            or not isinstance(generated.get("sections"), list)
            or not isinstance(generated.get("vocabulary"), list)
            or not isinstance(curated.get("difficulty_hooks"), list)):
        raise ValueError("scope card needs sections, vocabulary and difficulty_hooks")
    sections = []
    for i, section in enumerate(generated["sections"], 1):
        if not isinstance(section, dict) or not is_text(section.get("title")):
            raise ValueError(f"invalid card section {i}")
        sections.append({**section, "id": f"s{i}"})
    return {
        "lesson": {"grade": card.get("grade"), "number": card.get("lesson_number"),
                   "card_sha256": hashlib.sha256(raw).hexdigest()},
        "sections": sections,
        "difficulty_hooks": curated["difficulty_hooks"],
        "vocabulary": generated["vocabulary"],
        "axes": {name: list(values) for name, values in AXES.items()},
        "cells": [],
    }


def validate(doc, *, draft=False):
    if not isinstance(doc, dict) or not isinstance(doc.get("lesson"), dict):
        raise ValueError("blueprint needs a lesson mapping")
    lesson = doc["lesson"]
    if (type(lesson.get("grade")) is not int or not 6 <= lesson["grade"] <= 11
            or type(lesson.get("number")) is not int or lesson["number"] < 1
            or not isinstance(lesson.get("card_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", lesson["card_sha256"])):
        raise ValueError("lesson needs grade 6–11, a positive lesson number and a scope card SHA-256")
    if doc.get("axes") != {name: list(values) for name, values in AXES.items()}:
        raise ValueError("unexpected blueprint axes")
    sections = doc.get("sections")
    if not isinstance(sections, list):
        raise ValueError("sections must be a list")
    section_ids = set()
    for section in sections:
        if (not isinstance(section, dict) or not is_text(section.get("id"))
                or not is_text(section.get("title")) or section["id"] in section_ids):
            raise ValueError("sections need unique ids and nonempty titles")
        section_ids.add(section["id"])
    if any(not isinstance(doc.get(key), list) for key in ("difficulty_hooks", "vocabulary")):
        raise ValueError("difficulty_hooks and vocabulary must be lists")
    cells = doc.get("cells")
    if not isinstance(cells, list) or (not cells and not draft):
        raise ValueError("fill at least one feasible blueprint cell")
    ids, combinations = {}, set()
    for idx, cell in enumerate(cells, 1):
        if not isinstance(cell, dict):
            raise ValueError(f"cell {idx}: expected a mapping")
        key = cell.get("id")
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in ids:
            raise ValueError(f"cell {idx}: expected a unique lowercase cell id")
        if not is_text(cell.get("section")) or cell["section"] not in section_ids:
            raise ValueError(f"{key}: unknown section")
        if not all(is_text(cell.get(axis)) for axis in ("skill", "task_chain")):
            raise ValueError(f"{key}: skill and task_chain are required")
        for axis, values in AXES.items():
            if cell.get(axis) not in values:
                raise ValueError(f"{key}: {axis} must be one of {', '.join(values)}")
        coords = tuple(" ".join(cell[axis].casefold().split())
                       for axis in ("skill", "task_chain", *AXES))
        if coords in combinations:
            raise ValueError(f"{key}: duplicate cell coordinates")
        combinations.add(coords)
        ids[key] = cell
    return ids


def report_room(cells, coverage):
    if isinstance(coverage, dict):
        coverage = coverage.get("questions")
    if not isinstance(coverage, list):
        raise ValueError("coverage must be a list of question rows")
    covered, unmapped, seen = set(), set(), set()
    for row in coverage:
        if not isinstance(row, dict) or not is_text(row.get("question_id")):
            raise ValueError("each coverage row needs a question_id")
        if row.get("status", "published") != "published" or row.get("needs_human_review", False):
            continue
        question_id = row["question_id"]
        if question_id in seen:
            raise ValueError(f"duplicate coverage question_id: {question_id}")
        seen.add(question_id)
        key = row.get("cell_id")
        if key is None:
            unmapped.add(question_id)
            continue
        if not is_text(key) or key not in cells:
            raise ValueError(f"{question_id}: unknown cell_id {key!r}")
        band = row.get("difficulty_band")
        if band is not None and band != cells[key]["band"]:
            raise ValueError(f"{question_id}: difficulty_band does not match {key}")
        covered.add(key)
    print(f"Covered cells: {len(covered)}/{len(cells)}; unmapped live rows: {len(unmapped)}")
    for band in AXES["band"]:
        room = [key for key, cell in cells.items() if cell["band"] == band and key not in covered]
        print(f"{band}: {len(room)} uncovered" + (f" ({', '.join(room)})" if room else ""))
    return covered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("build")
    draft.add_argument("card", type=Path)
    draft.add_argument("--out", type=Path)
    check = commands.add_parser("check")
    check.add_argument("--coverage", type=Path)
    check.add_argument("blueprint", type=Path)
    check.add_argument("--out", type=Path, help="write a copy marked with current coverage")
    args = parser.parse_args()
    try:
        doc = build(args.card) if args.command == "build" else read(args.blueprint)
        cells = validate(doc, draft=args.command == "build")
        if args.command == "check":
            covered = report_room(cells, read(args.coverage) if args.coverage else [])
            if args.coverage:
                for key, cell in cells.items():
                    cell["covered"] = key in covered
        if args.out or args.command == "build":
            out = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
            if args.out:
                args.out.write_text(out, encoding="utf-8")
            else:
                sys.stdout.write(out)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.exit(2, f"lesson-blueprint: {exc}\n")


if __name__ == "__main__":
    main()
