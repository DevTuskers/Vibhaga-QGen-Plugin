#!/usr/bin/env python3
"""Blocking notation check for Sinhala units in a run's content fields."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

UNIT_WORDS = (
    "මිලිමීටර්", "මිලිමීටර", "සෙන්ටිමීටර්", "සෙන්ටිමීටර",
    "කිලෝමීටර්", "කිලෝමීටර", "මීටර්", "මීටර", "මිලිග්‍රෑම්",
    "කිලෝග්‍රෑම්", "ග්‍රෑම්", "මිලිලීටර්", "මිලිලීටර", "ලීටර්", "ලීටර",
)
WORD_UNIT = "(?:" + "|".join(UNIT_WORDS) + ")[\\u0D80-\\u0DFF]*"
UNIT_ABBREVIATION = (
    r"(?:සෙ\.\s*මී\.?|මි\.\s*මී\.?|කි\.\s*මී\.?|"
    r"කි\.\s*ග්‍රෑ\.?|මි\.\s*ග්‍රෑ\.?|ග්‍රෑ\.?|මි\.\s*ලී\.?|ලී\.?)"
)
UNIT_WITH_PREFIX = rf"(?:(?:ඝන|වර්ග)\s+)?{WORD_UNIT}"
UNIT_AFTER_DIGIT = re.compile(
    rf"(?<!\d)\d+(?:[.,]\d+)?\s*(?P<unit>{WORD_UNIT}|{UNIT_ABBREVIATION})(?!\w)"
)
UNIT_BEFORE_DIGIT = re.compile(
    rf"(?<!\w)(?P<unit>{UNIT_WITH_PREFIX})\s+\d+(?:[.,]\d+)?"
)
UNIT_BEFORE_MATH = re.compile(
    rf"(?<!\w)(?P<unit>{UNIT_WITH_PREFIX})\s+$"
)
UNIT_AFTER_MATH = re.compile(
    rf"^\s*(?P<unit>{WORD_UNIT}|{UNIT_ABBREVIATION})(?!\w)"
)
TRANSLITERATED_UNIT = re.compile(r"(?<!\w)(?P<unit>ක්ම්|ක්මී|ම්ම්|ක්ග්|ම්ග්|ම්ල්)(?!\w)")


def sinhala_fields(content: dict):
    def walk(value, path, qid=None, part=None):
        if isinstance(value, dict):
            if qid is None and value.get("n") is not None:
                qid = f"Q{value['n']}"
            if qid and value.get("label") and ".parts" in path:
                part = ".".join((part, str(value["label"]))) if part else str(value["label"])
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key.endswith("_si") and isinstance(child, str):
                    identifier = qid or path or "content"
                    if part:
                        identifier += f".{part}"
                    yield f"{identifier}.{key}", child
                else:
                    yield from walk(child, child_path, qid, part)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, f"{path}[{index}]", qid, part)

    yield from walk(content, "")


def field_hits(text: str) -> list[str]:
    matches = []
    segments = re.split(r"(\$[^$]*\$)", text)
    for index, segment in enumerate(segments):
        for pattern in (UNIT_AFTER_DIGIT, UNIT_BEFORE_DIGIT, TRANSLITERATED_UNIT):
            matches.extend(match.group(0) for match in pattern.finditer(segment))
        if index % 2:
            if index:
                before = UNIT_BEFORE_MATH.search(segments[index - 1])
                if before:
                    matches.append(f"{before.group('unit')} {segment}")
            if index + 1 < len(segments):
                after = UNIT_AFTER_MATH.match(segments[index + 1])
                if after:
                    matches.append(f"{segment}{after.group(0)}")
    return matches


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", help="content.yaml path or a run directory containing content.yaml")
    args = ap.parse_args(argv)
    path = Path(args.path)
    if path.is_dir():
        path = path / "content.yaml"
    if yaml is None:
        print("unit-notation: PyYAML unavailable", file=sys.stderr)
        return 2
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("content is not a mapping")
    except Exception as exc:  # noqa: BLE001
        print(f"unit-notation: unable to read {path}: {exc}", file=sys.stderr)
        return 2

    failures = 0
    for field, value in sinhala_fields(data):
        for hit in field_hits(value):
            failures += 1
            question_part, separator, field_name = field.rpartition(".")
            if not separator:
                question_part, field_name = "content", field
            print(
                f"FAIL {question_part} {field_name}: {hit} — write the unit as the English symbol "
                "after the number, e.g. $4$ cm; not සෙන්ටිමීටර් $4$"
            )
    print(f"unit-notation: {failures} fail(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
