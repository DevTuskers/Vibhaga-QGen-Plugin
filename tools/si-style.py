#!/usr/bin/env python3
"""Warning-only checks for mechanical Sinhala-writing smells in content.yaml."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

UNITS = {"cm", "mm", "m", "km", "g", "kg", "l", "ml", "rs"}
LATIN = re.compile(r"\b[A-Za-z]+\b")
PASSIVE = re.compile(r"(?:කරනු|දෙනු|ලබනු|දක්වනු)\s+ලැබේ")


def strip_markup(text: str) -> str:
    text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    text = re.sub(r"\$.*?\$", " ", text, flags=re.S)
    return text.replace("`", " ")


def field_warnings(text: str) -> list[str]:
    plain = strip_markup(text)
    warnings = []
    if plain.count("වන අතර") > 1:
        warnings.append('more than one "වන අතර"')
    if PASSIVE.search(plain):
        warnings.append("passive construction")
    for sentence in re.split(r"[.?!]+|\n\s*\n", plain):
        words = sentence.split()
        if len(words) > 30:
            warnings.append(f"sentence has {len(words)} words (max 30)")
    for match in LATIN.finditer(plain):
        word = match.group(0)
        if word.lower() in UNITS or re.fullmatch(r"[A-Z]{1,3}", word):
            continue
        if len(word) == 1 and plain[match.end():match.end() + 1] == "(":
            continue
        warnings.append(f"Latin word {word!r}")
    if "කරුණාකර" in plain:
        warnings.append("contains කරුණාකර")
    return warnings


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    args = ap.parse_args(argv)
    path = Path(args.run) / "content.yaml"
    try:
        if yaml is None:
            print("si-style: PyYAML unavailable; no checks run")
            return 0
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("content.yaml is not a mapping")
        for field, value in sinhala_fields(data):
            findings = field_warnings(value)
            for finding in findings:
                print(f"  WARN {field}: {finding}")
            print(f"si-style: {len(findings)} warn(s) · {field}")
    except Exception as exc:  # warning-only stage must not block build
        print(f"si-style: unable to check {path}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
