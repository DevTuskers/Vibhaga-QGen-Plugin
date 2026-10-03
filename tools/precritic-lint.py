#!/usr/bin/env python3
"""precritic-lint.py — the mechanical pre-critic pass over a generate run dir (W9 item G).

    precritic-lint.py <run> [--card KEY=NN …] [--grade N] [--cards-dir DIR]
                            [--rubric medium-hard] [--existing FILE …]

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

  (d) `--rubric medium-hard` — the plan appendix's set rules, read off the leaf `level:`
      keys (R|M/H, actor-only — build-staged never emits them): every question ≥3 leaf
      parts; at most one R per question and only as its first leaf; the last leaf is H;
      ≥60 % of a question's leaves M/H; ≥30 % H over the whole set. A leaf with no `level`
      is a WARN, never a FAIL — its absence simply cannot prove a rule.

  (e) `--existing FILE …` — duplicate fingerprint: digits masked (`42`→`##`), whitespace
      tokens, Jaccard of each question's stem+part texts against every existing row's
      `stem_excerpt`. ≥0.6 → WARN naming the row — the same task with new numbers is a
      duplicate even when the digits differ (decision 0001: no embeddings).

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
    # `at` comes in two dialects: the builder source writes `at 745 @P` (anchor form) and the
    # written -claims.txt resolves it to coordinates `at 30 216.12 62.94`. The @anchor / trailing
    # two numbers keep a prose `at 2 per symbol` (pictograph describe) from matching.
    (re.compile(r"\bat\s+(-?\d+(?:\.\d+)?)\s+@\w+"), (1,)),                       # `at v @P`
    (re.compile(r"\bat\s+(-?\d+(?:\.\d+)?)\s+-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?"), (1,)),  # `at v x y`
    (re.compile(r"\bshaded\s+(\d+(?:\.\d+)?)\s+of\s+\d+\s+cells"), (1,)),   # shaded_grid n of m
    (re.compile(r"\bstage\s+\d+\s+shows\s+(\d+(?:\.\d+)?)\s+dots"), (1,)),  # dot_pattern d
    (re.compile(r"\bshows\s+(\d+(?:\.\d+)?)\s+symbols\s+—\s+(\d+(?:\.\d+)?)\s+items"), (1, 2)),
)
DIGIT_TOKEN = re.compile(r"\d+(?:\.\d+)?")
WORD_RE = re.compile(r"[^\W\d_]+")        # letters only, any script


def figure_specs(specs) -> list:
    """Normalise a specs/figures.json payload to a list of spec dicts: a bare list passes
    through, a dict keyed by figure_id yields its values, any other dict is one spec.
    run-gates.py imports this so both tools read the same file the same way."""
    if isinstance(specs, dict):
        return list(specs.values()) if all(isinstance(v, dict) for v in specs.values()) \
            else [specs]
    return specs if isinstance(specs, list) else []


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


def leaf_levels(q: dict) -> list[tuple[str, object]]:
    """(leaf id, level-or-None) in document order — a part-less question is one leaf `Q<n>`."""
    out = []

    def walk(parts, prefix):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            pid = f"{prefix}.{p.get('label')}"
            if p.get("parts"):
                walk(p["parts"], pid)
            else:
                out.append((pid, p.get("level")))

    if q.get("parts"):
        walk(q["parts"], f"Q{q.get('n')}")
    else:
        out.append((f"Q{q.get('n')}", q.get("level")))
    return out


STRIP_PUNCT = ".,;:!?()[]{}'\"$*_`~—–-"


def mask_tokens(text: str) -> set[str]:
    """Check (e)'s fingerprint: digits masked to `#` (so a numbers-only variant keeps the same
    token set), whitespace-split, edge punctuation stripped."""
    return {w for raw in re.sub(r"\d+", "#", str(text or "")).split()
            if (w := raw.strip(STRIP_PUNCT))}


def question_surface(q: dict) -> str:
    """The stem + every part's text — check (e)'s fingerprint haystack."""
    out = [str(q.get("stem") or "")]

    def walk(parts):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            out.append(str(p.get("text") or ""))
            walk(p.get("parts"))

    walk(q.get("parts"))
    return " ".join(out)


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def load_existing(path: Path) -> list[dict]:
    """An existing-questions dump → row dicts. Accepts a JSON list, a JSON object holding a
    questions/rows list, or JSONL (one row per line)."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError:
        data = [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(data, dict):
        for k in ("questions", "rows", "results"):
            if isinstance(data.get(k), list):
                data = data[k]
                break
        else:
            data = [data]
    return [r for r in data if isinstance(r, dict)]


def rubric_medium_hard(questions: list, log) -> tuple[int, int]:
    """Check (d) — the plan appendix's medium–hard set rules from leaf `level:` keys."""
    fails = warns = 0
    all_levels = []
    for q in questions:
        lv = leaf_levels(q)
        names = [n for n, _ in lv]
        levels = [l for _, l in lv]
        all_levels += levels
        qn = f"Q{q.get('n')}"
        if len(lv) < 3:
            fails += 1
            log(f"  FAIL {qn}: {len(lv)} leaf part(s) — medium-hard wants ≥3")
        r_at = [i for i, l in enumerate(levels) if l == "R"]
        if len(r_at) > 1:
            fails += 1
            log(f"  FAIL {qn}: {len(r_at)} R parts — medium-hard allows one, and only as "
                f"the first part")
        elif r_at and r_at[0] != 0:
            fails += 1
            log(f"  FAIL {qn}: the R part is {names[r_at[0]]} — medium-hard allows it only "
                f"as the first part")
        if levels and levels[-1] not in (None, "H"):
            fails += 1
            log(f"  FAIL {qn}: last part {names[-1]} is {levels[-1]} — medium-hard ends on H")
        mh = sum(1 for l in levels if l in ("M", "H"))
        if lv and mh / len(lv) < 0.6:
            fails += 1
            log(f"  FAIL {qn}: {mh}/{len(lv)} parts are M/H — medium-hard wants ≥60%")
        for name, l in lv:
            if l is None:
                warns += 1
                log(f"  WARN {name}: no level — the rubric cannot see it")
    h = sum(1 for l in all_levels if l == "H")
    if all_levels and h / len(all_levels) < 0.3:
        fails += 1
        log(f"  FAIL set: {h}/{len(all_levels)} leaves are H — medium-hard wants ≥30% H "
            f"overall")
    return fails, warns


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
        specs = figure_specs(json.loads(specs_path.read_text(encoding="utf-8")))
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

    # (d) set rubric — the leaf `level:` keys against the plan appendix's rules
    if args.rubric == "medium-hard":
        f, w = rubric_medium_hard(questions, log)
        fails += f
        warns += w

    # (e) duplicate fingerprint — digits masked, Jaccard vs each existing row's stem_excerpt
    for path in getattr(args, "existing", []) or []:
        p = Path(path)
        if not p.is_file():
            die(f"--existing {path}: no such file")
        rows = load_existing(p)
        for q in questions:
            qt = mask_tokens(question_surface(q))
            for row in rows:
                rt = mask_tokens(row.get("stem_excerpt") or row.get("question_text") or "")
                j = jaccard(qt, rt)
                if j >= 0.6:
                    warns += 1
                    rid = row.get("question_id") or row.get("id") or "?"
                    log(f"  WARN Q{q.get('n')} ≈ {p.name}:{rid} (Jaccard {j:.2f}, digits "
                        f"masked) — the same task with new numbers is still a duplicate")
    return fails, warns


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="precritic-lint.py",
        description="the mechanical pre-critic pass over a generate run dir (W9 item G)")
    ap.add_argument("run", help="the generate §2 actor dir (content.yaml, specs/, figures/)")
    ap.add_argument("--card", action="append", default=[],
                    help="KEY=NN — bind a content.yaml lessons key to scope card NN (repeatable)")
    ap.add_argument("--grade", type=int,
                    help="grade number — cards resolve under maths/grade-NN/scope-cards/ "
                         "(required with --card unless --cards-dir is given)")
    ap.add_argument("--cards-dir", help="read cards from DIR/<NN>-*.yaml instead of the corpus")
    ap.add_argument("--rubric", choices=["medium-hard"], default=None,
                    help="check the leaf `level:` keys against a set rubric (check d)")
    ap.add_argument("--existing", action="append", nargs="+", default=[], metavar="FILE",
                    help="existing-question dumps (JSON list or JSONL) — digits-masked Jaccard "
                         "duplicate warn against each row's stem_excerpt (check e)")
    args = ap.parse_args(argv)
    args.existing = [str(p) for grp in args.existing for p in grp]
    if args.card and args.grade is None and not args.cards_dir:
        die("--card needs --grade N (or --cards-dir DIR)")
    run = Path(args.run)
    if not run.is_dir():
        die(f"no run dir {run}")
    fails, warns = lint(run, args)
    print(f"{PROG}: {fails} fail(s) · {warns} warn(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
