#!/usr/bin/env python3
"""Blocking check: Sinhala maths terms in content.yaml/staged docs must match
terms/si-maths-terms.yaml (the corpus-cited dictionary).

Flags, per *_si field:
  * a banned MT artifact string (dictionary `banned:` section)
  * an English dictionary term present in the paired English field whose Sinhala
    field does not use the dictionary rendering for that grade (or any grade when
    the grade is unknown)
  * a near-miss spelling of a dictionary headword when the EN term is present

Exit 0 clean, 1 with findings, 2 on usage/IO errors.
"""
from __future__ import annotations

import argparse
import difflib
import functools
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("check-si-terms: pyyaml required")

ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT / "terms" / "si-maths-terms.yaml"

SINHALA = re.compile(r"[අ-ෆඟ-෴][අ-෴\u200d]*")
LATEX = re.compile(r"\$\$.*?\$\$|\$.*?\$", re.S)
JOINERS = str.maketrans("", "", "\u200d\u200c")


def norm(text: str) -> str:
    """Drop ZWJ/ZWNJ: corpus conjuncts (e.g. අස්‍රය) are typed inconsistently."""
    return text.translate(JOINERS)


def strip_markup(text: str) -> str:
    return norm(LATEX.sub(" ", text).replace("`", " "))


@functools.lru_cache(maxsize=None)
def en_pattern(term: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z])(?<!non-)" + re.escape(term) + r"(?![A-Za-z])", re.I)


def si_tokens(text: str):
    for m in SINHALA.finditer(strip_markup(text)):
        yield norm(m.group(0))


def headword(si: str) -> str:
    return si.split()[0]


def term_present(si: str, text: str) -> bool:
    """Phrase-level presence tolerant of inflection: every dictionary word must
    appear in order, adjacent, optionally extended by Sinhala suffixes."""
    plain = strip_markup(text)
    si = norm(si)
    if si in plain:
        return True
    pat = r"\s+".join(re.escape(w) + r"[අ-෴]*" for w in si.split())
    return re.search(pat, plain) is not None


def near_miss(si_hw: str, text: str, ratio: float = 0.82):
    si_hw = norm(si_hw)
    for tok in si_tokens(text):
        if tok == si_hw:
            continue
        if abs(len(tok) - len(si_hw)) <= max(3, len(si_hw) // 2):
            r = difflib.SequenceMatcher(None, tok, si_hw).ratio()
            if r >= ratio:
                return tok
    return None


def iter_pairs(node, path="", qid=None, part=None):
    """Yield (field_id, en_text, si_text) for every en/*_si|*_sinhala pair."""
    if isinstance(node, dict):
        if qid is None and node.get("n") is not None:
            qid = f"Q{node['n']}"
        p = part
        if qid and node.get("label") and ".parts" in path:
            p = ".".join((p, str(node["label"]))) if p else str(node["label"])
        for key, val in node.items():
            if isinstance(val, str) and (key.endswith("_si") or key.endswith("_sinhala")):
                base = key[: -len("_si")] if key.endswith("_si") else key[: -len("_sinhala")]
                en = node.get(base)
                ident = (qid or path or "content") + ("." + p if p else "")
                yield f"{ident}.{key}", en if isinstance(en, str) else "", val
            else:
                yield from iter_pairs(val, f"{path}.{key}" if path else str(key), qid, p)
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from iter_pairs(child, f"{path}[{i}]", qid, part)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Enforce the si-maths-terms dictionary")
    ap.add_argument("doc", help="content.yaml or staged doc to check")
    ap.add_argument("--grade", type=int, default=None,
                    help="grade the doc targets; when omitted, a rendering valid "
                         "in ANY grade is accepted")
    ap.add_argument("--dict", default=str(DICT_PATH))
    args = ap.parse_args(argv)

    dictionary = yaml.safe_load(Path(args.dict).read_text(encoding="utf-8"))
    doc = yaml.safe_load(Path(args.doc).read_text(encoding="utf-8"))
    grade = args.grade or (doc.get("grade") if isinstance(doc, dict) else None)

    banned = {norm(k): v for k, v in (dictionary.get("banned") or {}).items()}
    findings = []

    for field_id, en_text, si_text in iter_pairs(doc):
        plain_si = strip_markup(si_text)
        for bad, info in banned.items():
            if norm(bad) in plain_si:
                findings.append(
                    f"{field_id}: banned term '{bad}' (en: {info.get('en')}) "
                    f"— use '{info.get('use')}'")
        if not en_text:
            continue
        en_plain = strip_markup(en_text)
        terms = dictionary.get("terms") or {}
        spans = {t: [m.span() for m in en_pattern(t).finditer(en_plain)]
                 for t in terms}
        spans = {t: s for t, s in spans.items() if s}
        for term, hits in spans.items():
            # a term matched only inside a longer dictionary term's match is a
            # use of the compound, not the shorter word — whether the compound
            # is taught at this grade or not ("north" inside "north-east";
            # "square" inside "square root")
            hits = [h for h in hits
                    if not any(len(other) > len(term) and
                               os <= h[0] <= h[1] <= oe
                               for other, ohs in spans.items()
                               for os, oe in ohs)]
            if not hits:
                continue
            entry = terms[term]
            grades = entry.get("grades") or {}
            wanted = {g: v for g, v in grades.items()
                      if grade is None or int(g) == int(grade)}
            if not wanted:  # term exists but not taught at this grade
                continue
            accepted = []
            formats = []
            for g, v in wanted.items():
                if v.get("format"):
                    formats.append(v["format"])
                else:
                    accepted.append(v["si"])
                    accepted.extend(v.get("alt") or [])
            if any(term_present(a, plain_si) for a in accepted) or \
                    any(re.search(f, plain_si) for f in formats):
                continue
            # near-miss spelling of any accepted headword?
            miss = None
            for a in accepted:
                m = near_miss(headword(a), si_text)
                if m:
                    miss = (m, a)
                    break
            if miss:
                findings.append(
                    f"{field_id}: '{term}' rendered '{miss[0]}' — dictionary "
                    f"spelling is '{miss[1]}'")
            else:
                shown = " / ".join(dict.fromkeys(accepted)) or \
                    " / ".join(dict.fromkeys(v["si"] for v in wanted.values()
                                           if v.get("format")))
                findings.append(
                    f"{field_id}: English term '{term}' present but the Sinhala "
                    f"does not use the dictionary rendering '{shown}'")

    for f in findings:
        print(f"FAIL {f}")
    if findings:
        print(f"\ncheck-si-terms: {len(findings)} violation(s) — see "
              "terms/si-maths-terms.yaml (banned/terms) for the corpus-cited forms")
        return 1
    print(f"check-si-terms: OK ({args.doc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
