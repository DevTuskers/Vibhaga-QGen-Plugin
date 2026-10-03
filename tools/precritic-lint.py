#!/usr/bin/env python3
"""precritic-lint.py — the mechanical pre-critic pass over a generate run dir (W9 item G).

    precritic-lint.py <run> --card KEY=NN [--card …] --grade N [--cards-dir DIR]

`<run>` is the generate §2 actor dir (`content.yaml`, `specs/figures.json`, `figures/`). Each
`--card KEY=NN` binds a `content.yaml` `lessons:` key to a lesson's scope card, resolved as
`maths/grade-<grade>/scope-cards/<NN>-*.yaml` under the corpus (`VIBHAGA_CORPUS` → the sibling
`Vibhaga-Maths-Corpus` — scope-cards' own resolution, imported not copied), or as
`<cards-dir>/<NN>-*.yaml` when `--cards-dir` is given (exam pools lay their cards elsewhere).

Checks:

  (a) FAIL — a `not_taught` PROBE from a listed card appearing in any question's stem, part
      text, approach or final — a case-insensitive substring match on NFC + ASCII-folded text
      (scope-cards' probe_norm). A printed probe means the concept may actually be taught —
      the card's curator checked ABSENCE in the lesson, not in the question. Prints the
      question/part, the probe and the card.

  (b) WARN — a figure spec's `description` (a11y) containing a digit token equal to a value
      the figure carries as READABLE content, taken from its emitted claim set
      `figures/<figure_id>-claims.txt`: number-line `at v x y` values, `shaded n of m` n,
      `stage k shows d dots` d, pictograph row counts (symbols and items). T125: the a11y
      description must not hand over what a part asks the student to read off the figure.

  (c) WARN (heuristic) — a question tags a lesson KEY but none of its parts' text/approach
      (a part-less question: stem + approach + final) contains any of that card's cleaned
      vocabulary terms or a section-title word of ≥4 characters. A smell, not a proof —
      printed as `heuristic` so nobody treats it as a gate.

Output: one FAIL/WARN line each, then `precritic-lint: F fail(s) · W warn(s)`.
Exit 1 on any FAIL, else 0 — warns never block, same contract as validate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("scope_cards", TOOLS / "scope-cards.py")
sc = importlib.util.module_from_spec(_spec)          # corpus resolution + probe_norm — reused
_spec.loader.exec_module(sc)

PROG = "precritic-lint"

# claim-set lines that carry a value the student reads off the figure (item G-b)
READABLE_RES = (
    # the claim file carries `@anchor` resolved to coordinates: `at 30 216.12 62.94` — requiring
    # the two trailing numbers keeps a prose `at 2 per symbol` (pictograph describe) from matching
    (re.compile(r"\bat\s+(-?\d+(?:\.\d+)?)\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?"), (1,)),
    (re.compile(r"\bshaded\s+(\d+(?:\.\d+)?)\s+of\s+\d+\s+cells"), (1,)),   # shaded_grid n of m
    (re.compile(r"\bstage\s+\d+\s+shows\s+(\d+(?:\.\d+)?)\s+dots"), (1,)),  # dot_pattern d
    (re.compile(r"\bshows\s+(\d+(?:\.\d+)?)\s+symbols\s+—\s+(\d+(?:\.\d+)?)\s+items"), (1, 2)),
)
DIGIT_TOKEN = re.compile(r"\d+(?:\.\d+)?")
WORD_RE = re.compile(r"[^\W\d_]+")        # letters only, any script


def die(msg: str) -> "None":
    print(f"{PROG}: {msg}", file=sys.stderr)
    sys.exit(2)


def cards_dir_for(args) -> Path:
    if args.cards_dir:
        d = Path(args.cards_dir)
        if not d.is_dir():
            die(f"--cards-dir {d} is not a directory")
        return d
    corpus = sc.resolve_corpus(argparse.Namespace(corpus=None))
    return sc.grade_dir(corpus, args.grade) / "scope-cards"


def load_cards(args) -> dict[str, dict]:
    """--card KEY=NN entries → {KEY: (card yaml doc, card filename)}."""
    out: dict[str, dict] = {}
    for spec in args.card:
        m = re.fullmatch(r"([A-Za-z0-9_-]+)=(\d+)", spec)
        if not m:
            die(f"--card {spec!r} — want KEY=NN (a content.yaml lessons key = a lesson number)")
        key, nn = m.group(1), int(m.group(2))
        cands = sorted(cards_dir_for(args).glob(f"{nn:02d}-*.yaml"))
        if len(cands) != 1:
            die(f"--card {spec}: {len(cands)} card(s) match {nn:02d}-*.yaml in {cards_dir_for(args)}")
        yaml = sc.import_yaml()
        try:
            doc = yaml.safe_load(cands[0].read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            die(f"{cands[0].name}: card does not parse ({exc})")
        if not isinstance(doc, dict):
            die(f"{cands[0].name}: card is not a YAML mapping")
        out[key] = {"doc": doc, "name": cands[0].name}
    return out


def load_content(run: Path) -> dict:
    for name in ("content.yaml", "content.yml", "content.json"):
        p = run / name
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        if name.endswith(".json"):
            data = json.loads(text)
        else:
            data = sc.import_yaml().safe_load(text)
        if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
            die(f"{name}: want a mapping with a questions: list")
        return data
    die(f"no content.yaml/json in {run}")


def field_texts(q: dict):
    """(id, text) pairs — question stem/approach/final, then per part text/approach/final
    (depth-first, label paths Q3.a.i). Yields nothing for absent/empty fields."""
    qn = f"Q{q.get('n')}"
    for k in ("stem", "approach", "final"):
        if isinstance(q.get(k), str) and q[k].strip():
            yield qn, q[k]

    def walk(parts, prefix):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            pid = f"{prefix}.{p.get('label')}"
            for k in ("text", "approach", "final"):
                if isinstance(p.get(k), str) and p[k].strip():
                    yield pid, p[k]
            yield from walk(p.get("parts"), pid)

    yield from walk(q.get("parts"), qn)


def part_texts(q: dict) -> list[str]:
    """Check (c)'s haystack: every part's text+approach at both depths. A part-less question
    falls back to its stem/approach/final — the answer content lives at question level."""
    texts = []

    def walk(parts):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            for k in ("text", "approach"):
                if isinstance(p.get(k), str):
                    texts.append(p[k])
            walk(p.get("parts"))

    walk(q.get("parts"))
    if not q.get("parts"):
        texts += [t for t in (q.get("stem"), q.get("approach"), q.get("final"))
                  if isinstance(t, str)]
    return texts


def card_terms(card: dict) -> list[str]:
    """The card's cleaned vocabulary + section-title words of ≥4 characters (check c)."""
    gen = card.get("generated") or {}
    terms = []
    for v in gen.get("vocabulary") or []:
        t = sc.clean(sc.GLYPH_BULLET_RE.sub("", str(v))).strip()
        if t and not sc.NOISE_RE.fullmatch(t):
            terms.append(t)
    for s in gen.get("sections") or []:
        for w in WORD_RE.findall(str(s.get("title") or "")):
            if len(w) >= 4:
                terms.append(w)
    return terms


def readable_values(claims_text: str) -> set[str]:
    """Values the figure carries as readable content, per the claim-set grammar."""
    vals: set[str] = set()
    for line in claims_text.splitlines():
        for rx, groups in READABLE_RES:
            m = rx.search(line)
            if m:
                vals.update(m.group(g) for g in groups)
    return vals


def lint(run: Path, args, log=print) -> tuple[int, int]:
    content = load_content(run)
    cards = load_cards(args) if args.card else {}
    questions = content["questions"]
    fails = warns = 0

    # (a) not_taught probes must not appear in any question field
    probes = [(key, card["name"], nt.get("concept"), p)
              for key, card in cards.items()
              for nt in ((card["doc"].get("curated") or {}).get("not_taught") or [])
              for p in (nt.get("probes") or [])]
    for q in questions:
        for pid, text in field_texts(q):
            hay = sc.probe_norm(text)
            for key, cname, concept, probe in probes:
                if sc.probe_norm(str(probe)) in hay:
                    fails += 1
                    log(f"  FAIL {pid} · probe {probe!r} (not_taught: {concept}) · {cname}")

    # (b) figure spec descriptions must not hand over readable values (T125)
    specs_path = run / "specs" / "figures.json"
    if specs_path.is_file():
        specs = json.loads(specs_path.read_text(encoding="utf-8"))
        if isinstance(specs, dict):
            specs = list(specs.values()) if all(isinstance(v, dict) for v in specs.values()) \
                else [specs]
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            desc, fid = spec.get("description"), spec.get("figure_id")
            if not isinstance(desc, str) or not isinstance(fid, str):
                continue
            cl = run / "figures" / f"{fid}-claims.txt"
            if not cl.is_file():
                continue
            readable = readable_values(cl.read_text(encoding="utf-8"))
            for tok in DIGIT_TOKEN.findall(desc):
                if tok in readable:
                    warns += 1
                    log(f"  WARN {fid} description digit {tok!r} = a value the figure shows "
                        f"({cl.name}) — T125: a11y must not hand over what a part asks")
    else:
        log(f"  info: no {specs_path.name} — check (b) skipped")

    # (c) tagged-but-unwritten heuristic — needs the question's lesson KEYS
    for q in questions:
        keys = [k for k in (q.get("lessons") or []) if k in cards]
        if not keys:
            continue
        hay = sc.probe_norm(" ".join(part_texts(q)))
        for key in keys:
            terms = card_terms(cards[key]["doc"])
            if terms and not any(sc.probe_norm(t) in hay for t in terms):
                warns += 1
                log(f"  WARN Q{q.get('n')} tags {key} ({cards[key]['name']}) but no part's "
                    f"text/approach uses its vocabulary or section words — heuristic")
    return fails, warns


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="precritic-lint.py",
        description="the mechanical pre-critic pass over a generate run dir (W9 item G)")
    ap.add_argument("run", help="the generate §2 actor dir (content.yaml, specs/, figures/)")
    ap.add_argument("--card", action="append", default=[],
                    help="KEY=NN — bind a content.yaml lessons key to scope card NN (repeatable)")
    ap.add_argument("--grade", type=int, required=True,
                    help="grade number — cards resolve under maths/grade-NN/scope-cards/")
    ap.add_argument("--cards-dir", help="read cards from DIR/<NN>-*.yaml instead of the corpus")
    args = ap.parse_args(argv)
    run = Path(args.run)
    if not run.is_dir():
        die(f"no run dir {run}")
    fails, warns = lint(run, args)
    print(f"{PROG}: {fails} fail(s) · {warns} warn(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
