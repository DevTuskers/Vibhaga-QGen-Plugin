#!/usr/bin/env python3
"""check-layout.py — the mechanical readable-layout gate for student-facing text.

    check-layout.py --fields <fields.json>
    check-layout.py <staged.json>

`--fields` takes the `[{id, field, text}]` list written by run-gates build. A positional
staged doc is read through `run-gates.py`'s `staged_fields` so the checker covers the same
stems, parts, approaches and finals without copying its field walk.

Owner ruling (2026-10-13): stems, part texts, approaches and finals must be laid out for
students to read, not shipped as one run-on paragraph. Paragraphs split on a blank line.
Table rows, list items and `$$` display-math blocks do not count as prose; inline math and
backticks are masked only while counting sentences.

Thresholds use Python character count (including inline math): APPROACH/FINAL fail above
180 characters or at 3 sentences, and warn at 2 sentences. STEM/PART fail above 240
characters or at 3 sentences, and warn above 180 characters or at 2 sentences.

Output: one FAIL/WARN per affected paragraph, then `check-layout: F fail(s) · W warn(s) · N fields`.
Exit 1 on any FAIL, 0 otherwise, 2 on usage or unreadable input.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PROG = "check-layout"

PARAGRAPHS = re.compile(r"\n[ \t]*\n")
TABLE_ROW = re.compile(r"^\s*\|")
LIST_ITEM = re.compile(
    r"^\s*([-*+]|\d+[.)]|\(?(?:x|ix|iv|v?i{1,3}|v)[.)])\s",
    re.I,
)
SENTENCE_END = re.compile(r"""(?P<punctuation>[.?!]+)["'”’)\]]*(?=\s|$)""")
# Dotted tokens such as ප.ව., පෙ.ව., and a.m. are abbreviations; [^\s.\d] also
# matches Sinhala marks that \w misses.
DOTTED_ABBREVIATION = re.compile(r"(?:^|\s)[^\s.\d]+(?:\.[^\s.\d]+)+\.$")
# Runs of two or more periods mark fill-in blanks, not sentence ends.
DOT_RUN = re.compile(r"\.{2,}")
# Currency marker periods do not end the sentence.
CURRENCY_ABBREVIATION = re.compile(r"(?:^|[\s(])(?:රු|Rs|rs)\.$")
# The second period in a spaced Sinhala time abbreviation is not a sentence end.
SPACED_TIME_ABBREVIATION = re.compile(r"(?:^|\s)(?:ප|පෙ)\.\s+ව\.$")
# A spaced time abbreviation's first period is followed by the token ව.
SPACED_TIME_PREFIX = re.compile(r"(?:^|\s)(?:ප|පෙ)\.$")
# The following token completes the spaced Sinhala time abbreviation.
SPACED_TIME_SUFFIX = re.compile(r"\s+ව\.")


def field_kind(field: str) -> str:
    """Return the student-facing field kind from the staged-fields field name."""
    if field in ("question_text", "question_text_sinhala"):
        return "STEM"
    if field.endswith(":approach"):
        return "APPROACH"
    if field.endswith(":final"):
        return "FINAL"
    if field.endswith(":text_sinhala") or (
        field.startswith(("sq:", "sq2:")) and field.endswith(":text")
    ):
        return "PART"
    raise ValueError(f"unsupported field name {field!r}")


def prose_for_paragraph(paragraph: str, in_display_math: bool = False) -> tuple[str, bool]:
    """Remove non-prose markdown/display-math lines and join the remaining lines."""
    prose_lines = []
    for line in paragraph.splitlines():
        stripped = line.strip()
        if in_display_math:
            if stripped == "$$":
                in_display_math = False
            continue
        if stripped == "$$":
            in_display_math = True
            continue
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) >= 4:
            continue
        if TABLE_ROW.match(line) or LIST_ITEM.match(line):
            continue
        if stripped:
            prose_lines.append(stripped)
    return " ".join(prose_lines), in_display_math


def mask_inline_runs(text: str) -> str:
    """Replace math and code runs so their punctuation is not counted as prose."""
    text = re.sub(r"\$\$.*?\$\$", "X", text, flags=re.S)
    text = re.sub(r"(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)", "X", text, flags=re.S)
    return re.sub(r"`+.*?`+", "X", text, flags=re.S)


def is_abbreviation(text: str, match: re.Match[str]) -> bool:
    """Return whether a sentence-end match is a non-ending abbreviation or marker."""
    head = text[:match.start()] + match.group().rstrip("\"'”’)]")
    if DOT_RUN.search(match.group("punctuation")):
        return True
    if DOTTED_ABBREVIATION.search(head) or CURRENCY_ABBREVIATION.search(head):
        return True
    if SPACED_TIME_ABBREVIATION.search(head):
        return True
    return bool(
        SPACED_TIME_PREFIX.search(head)
        and SPACED_TIME_SUFFIX.match(text, match.end())
    )


def sentence_count(prose: str) -> int:
    """Count prose sentence endings and any final unterminated sentence."""
    text = mask_inline_runs(prose)
    matches = [match for match in SENTENCE_END.finditer(text) if not is_abbreviation(text, match)]
    trailing = text[matches[-1].end():] if matches else text
    return len(matches) + int(bool(trailing.strip()))


def thresholds(kind: str) -> tuple[int, int, bool]:
    """Return (failure length, warning length, length warning enabled)."""
    if kind in ("APPROACH", "FINAL"):
        return 180, 180, False
    return 240, 180, True


def findings(fields: list[dict]) -> tuple[list[str], int, int]:
    lines = []
    fail_count = 0
    warn_count = 0
    for item in fields:
        kind = field_kind(item["field"])
        in_display_math = False
        for paragraph_number, paragraph in enumerate(PARAGRAPHS.split(item["text"]), 1):
            prose, in_display_math = prose_for_paragraph(paragraph, in_display_math)
            if not prose:
                continue
            length = len(prose)
            sentences = sentence_count(prose)
            fail_limit, warn_limit, length_warns = thresholds(kind)
            reasons = []
            if length > fail_limit:
                reasons.append(f"{length} chars > {fail_limit}")
            if sentences >= 3:
                reasons.append(
                    f"{sentences} sentences in one paragraph — one step per paragraph, "
                    "blank line between"
                )
            if reasons:
                severity = "FAIL"
                fail_count += 1
            else:
                warnings = []
                if length_warns and length > warn_limit:
                    warnings.append(f"{length} chars > {warn_limit}")
                if sentences == 2:
                    warnings.append("2 sentences in one paragraph — one step per paragraph, blank line between")
                if not warnings:
                    continue
                severity = "WARN"
                reasons = warnings
                warn_count += 1
            snippet = prose[:60].replace('"', r'\"')
            lines.append(
                f'{severity} {item["id"]} {item["field"]} ¶{paragraph_number}: '
                f'{"; ".join(reasons)} — "{snippet}…"'
            )
    return lines, fail_count, warn_count


def fields_from_staged(staged: dict) -> list[dict]:
    spec = importlib.util.spec_from_file_location("run_gates_for_layout", TOOLS / "run-gates.py")
    if spec is None or spec.loader is None:
        raise ValueError("could not load tools/run-gates.py")
    run_gates = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_gates)
    return run_gates.staged_fields(staged)


def read_input(path: str, fields_mode: bool) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    fields = payload if fields_mode else fields_from_staged(payload)
    if not isinstance(fields, list):
        raise ValueError("input must produce a list of fields")
    for item in fields:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str) for key in ("id", "field", "text")
        ):
            raise ValueError("each field must contain string id, field and text values")
    return fields


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=PROG)
    parser.add_argument("--fields", help="[{id, field, text}] fields JSON")
    parser.add_argument("staged", nargs="?", help="staged.json (loads fields via run-gates.py)")
    args = parser.parse_args(argv)
    if bool(args.fields) == bool(args.staged):
        parser.error("provide exactly one of --fields <fields.json> or <staged.json>")

    path = args.fields or args.staged
    try:
        fields = read_input(path, fields_mode=bool(args.fields))
        output, fails, warns = findings(fields)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, ImportError) as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return 2

    for line in output:
        print(line)
    print(f"{PROG}: {fails} fail(s) · {warns} warn(s) · {len(fields)} fields")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
