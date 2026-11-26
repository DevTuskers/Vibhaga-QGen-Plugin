#!/usr/bin/env python3
"""precritic-lint.py — the mechanical pre-critic pass over a generate run dir (W9 item G).

    precritic-lint.py <run> [--card KEY=NN …] [--grade N] [--cards-dir DIR]
                            [--all-probes] [--rubric easy|medium|medium-hard|by-band] [--existing FILE …]

`<run>` is the generate §2 actor dir (`content.yaml`, `specs/figures.json`, `figures/`). Each
`--card KEY=NN` binds a `content.yaml` `lessons:` key to a lesson's scope card, resolved as
`maths/grade-<grade>/scope-cards/<NN>-*.yaml` under the corpus (`VIBHAGA_CORPUS` → the sibling
`Vibhaga-Maths-Corpus` — scope-cards' own resolution, imported not copied), or as
`<cards-dir>/<NN>-*.yaml` when `--cards-dir` is given (exam pools lay their cards elsewhere).
An unknown key from the top-level `content.yaml` `lessons:` mapping is refused.

Checks:

  (a) FAIL — a `not_taught` PROBE appearing in a question's stem, part text, approach or
      final — a case-insensitive substring match on NFC + ASCII-folded text
      (scope-cards' probe_norm). A printed probe means the concept may actually be taught —
      the card's curator checked ABSENCE in the lesson, not in the question. Prints the
      question/part, the probe and the card. **Per-question by default (W12):** each
      question is checked only against the cards bound to the lesson keys its `lessons:`
      list tags — a probe of a card the question never tags is not its business. The
      opt-in `--all-probes` restores the old run-wide behaviour (every bound card against
      every question). A `lessons:` key with no bound `--card` draws one WARN per
      (question, key) — its not_taught probes were not checked.

  (b) WARN — a figure spec's `description` (a11y) containing a digit token equal to a value
      the figure carries as READABLE content, taken from its emitted claim set
      `figures/<figure_id>-claims.txt`: number-line `at v x y` values, `shaded n of m` n,
      `stage k shows d dots` d, pictograph row counts (symbols and items). T125: the a11y
      description must not hand over what a part asks the student to read off the figure.

  (c) WARN (heuristic) — a question tags a lesson KEY but none of its parts' text/approach
      (a part-less question: stem + approach + final) contains any of that card's cleaned
      `phrases` or `vocabulary` terms or a section-title word — scope-cards' enough_letters
      floors apply first (a card term needs ≥2 letters when Sinhala-bearing, ≥3 pure ASCII;
      a section word ≥3 Sinhala / ≥4 ASCII — a tiny conjunction matched every question and
      silenced the WARN). Cards without `phrases` still work. A smell, not a proof —
      printed as `heuristic` so nobody treats it as a gate.

  (d) `--rubric easy|medium|medium-hard` — checks the selected difficulty band from leaf `level:`
      keys, or (f) FAIL — a student field missing its `*_si` twin, a Sinhala codepoint in
      the English side, or an English-prose copy in the `_si` side (build-staged's rule).
      keys (R|M/H, actor-only — build-staged never emits them): every question ≥3 leaf
      parts; at most one R per question and only as part (a), i.e. its first leaf in
      document order; the last leaf is H; ≥60 % of the set's RATED leaves M/H and ≥30 % H —
      both fractions are set-wide. A leaf with no `level` is a WARN and counts in no
      denominator, so it can never drive a FAIL.

  (e) duplicate fingerprint: digits masked (`42`→`##`), whitespace tokens, Jaccard of each
      question's stem+part texts against every existing row's `stem_excerpt` and the bound
      cards' worked-example excerpts and exercise items. ≥0.6 → WARN naming the row or card item,
      never its text — the same task with new numbers is a duplicate (decision 0001: no embeddings).

  (g) FAIL — Sinhala text inside KaTeX `\\text{}` (D7 / S4 §0.4, S8 §0.8). Prose and maths
      are separate nodes; Sinhala belongs in prose outside `$…$`, never in `\\text{}`.

  (h) FAIL — `approach` or `approach_si` opening with an announcement prefix ('Answer:' /
      'පිළිතුර:') (S8 §4.1: the approach teaches the method; it is not an answer key).

Output: one FAIL/WARN line each, then `precritic-lint: F fail(s) · W warn(s)`.
Exit 1 on any FAIL, else 0 — warns never block, same contract as validate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("scope_cards", TOOLS / "scope-cards.py")
sc = importlib.util.module_from_spec(_spec)          # corpus resolution + probe_norm — reused
_spec.loader.exec_module(sc)

_spec2 = importlib.util.spec_from_file_location("build_staged", TOOLS / "build-staged.py")
bs = importlib.util.module_from_spec(_spec2)         # bilingual_problem — the same 0024 rule
_spec2.loader.exec_module(bs)                        # build-staged refuses on, never copied

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
MATH_SPAN = re.compile(r"(?<!\\)(\$\$|\$)(?!\$)(.+?)(?<!\\)\1(?!\$)", re.S)
BARE_ASSIGNMENT = re.compile(r"(?<![\w\\])[A-Za-z]\s*=\s*[−+-]?\d")
NUMBER = r"[−-]?\d+(?:\.\d+)?"
EN_RANGE = re.compile(rf"\b(?:between|from)\s+\$?({NUMBER})\$?(?:\s*[a-z]{{1,3}})?\s+(?:and|to)\s+\$?({NUMBER})", re.I)
SI_RANGE = re.compile(rf"\$?({NUMBER})\$?(?:\s*[a-z]{{1,3}})?\s+සිට\s+\$?({NUMBER})")
PROOF_REQUEST = re.compile(r"\b(?:explain why|give (?:a|the) (?:visual )?reason|justify your answer)\b", re.I)
BOUND_MARK = re.compile(r"\b(?:marked (?:plot |window )?(?:bounds?|limits?|endpoints?)|bound markers?)\b", re.I)
GRAPH_FEATURES = {
    "vertex": r"\b(?:vertex|turning point)\b|හැරුම් ලක්ෂ්‍ය",
    "root": r"\b(?:roots?|zeros?|x[ -]intercepts?|crosses the x[ -]axis)\b|මූලයන්?",
    "y-intercept": r"\b(?:y[ -]intercept|crosses the y[ -]axis)\b|y අන්තඃඛණ්ඩ",
}
FEATURE_NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
REPAYMENT = re.compile(r"\b(?:repayment|instal[l]?ment|payment)\b", re.I)
UNCHANGED = re.compile(r"\b(?:unchanged|stays? the same|remains? the same)\b", re.I)


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


def all_student_fields(q: dict):
    """Yield (field_path, text) for every student-facing string field on q and its parts
    (stem, stem_si, text, text_si, approach, approach_si, final, final_si)."""
    qn = f"Q{q.get('n')}"
    for k in ("stem", "stem_si", "approach", "approach_si", "final", "final_si"):
        val = q.get(k)
        if isinstance(val, str) and val.strip():
            yield f"{qn}.{k}", val

    def walk(parts, prefix):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            lbl = p.get("label")
            pid = f"{prefix}.{lbl}" if lbl else prefix
            for k in ("text", "text_si", "approach", "approach_si", "final", "final_si"):
                val = p.get(k)
                if isinstance(val, str) and val.strip():
                    yield f"{pid}.{k}", val
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
            for k in ("text", "approach", "text_si", "approach_si"):
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
    """Check (d) — the plan appendix's medium–hard set rules from leaf `level:` keys.
    "Part (a)" is document order's first leaf; the M/H and H fractions are SET-wide over
    the rated leaves — a leaf with no `level` is a WARN and counts in no denominator."""
    fails = warns = 0
    all_rated = []
    for q in questions:
        lv = leaf_levels(q)
        names = [n for n, _ in lv]
        levels = [l for _, l in lv]
        qn = f"Q{q.get('n')}"
        if len(lv) < 3:
            fails += 1
            log(f"  FAIL {qn}: {len(lv)} leaf part(s) — medium-hard wants ≥3")
        r_at = [i for i, l in enumerate(levels) if l == "R"]
        if len(r_at) > 1:
            fails += 1
            log(f"  FAIL {qn}: {len(r_at)} R parts — medium-hard allows one, and only as "
                f"part (a), i.e. the first part")
        elif r_at and r_at[0] != 0:
            fails += 1
            log(f"  FAIL {qn}: the R part is {names[r_at[0]]} — medium-hard allows it "
                f"only as part (a), i.e. the first part")
        if levels and levels[-1] not in (None, "H"):
            fails += 1
            log(f"  FAIL {qn}: last part {names[-1]} is {levels[-1]} — medium-hard ends on H")
        elif levels and levels[-1] is None:
            warns += 1
            log(f"  WARN {qn}: last part has no level — cannot check it is H")
        for name, l in lv:
            if l is None:
                warns += 1
                log(f"  WARN {name}: no level — the rubric cannot see it")
            else:
                all_rated.append(l)
    mh = sum(1 for l in all_rated if l in ("M", "H"))
    if all_rated and mh / len(all_rated) < 0.6:
        fails += 1
        log(f"  FAIL set: {mh}/{len(all_rated)} rated leaves are M/H — medium-hard wants "
            f"≥60%")
    h = sum(1 for l in all_rated if l == "H")
    if all_rated and h / len(all_rated) < 0.3:
        fails += 1
        log(f"  FAIL set: {h}/{len(all_rated)} rated leaves are H — medium-hard wants "
            f"≥30% H overall")
    return fails, warns


def rubric_easy(questions: list, log) -> tuple[int, int]:
    fails = warns = 0
    for q in questions:
        levels = leaf_levels(q)
        qn = f"Q{q.get('n')}"
        if len(levels) > 3:
            fails += 1
            log(f"  FAIL {qn}: {len(levels)} leaf part(s) — easy allows at most 3")
        for name, level in levels:
            if level is None:
                warns += 1
                log(f"  WARN {name}: no level — the easy rubric cannot check it")
            elif level != "R":
                fails += 1
                log(f"  FAIL {name}: level {level} — easy requires R")
    return fails, warns


def rubric_medium(questions: list, log) -> tuple[int, int]:
    fails = warns = 0
    for q in questions:
        levels = leaf_levels(q)
        qn = f"Q{q.get('n')}"
        if not 2 <= len(levels) <= 4:
            fails += 1
            log(f"  FAIL {qn}: {len(levels)} leaf part(s) — medium wants 2–4")
        rated = [level for _, level in levels if level is not None]
        if "M" not in rated:
            fails += 1
            log(f"  FAIL {qn}: no M leaf — medium requires at least one M")
        for name, level in levels:
            if level is None:
                warns += 1
                log(f"  WARN {name}: no level — the medium rubric cannot check it")
            elif level == "H":
                fails += 1
                log(f"  FAIL {name}: level H — medium does not allow H")
    return fails, warns


def card_terms(card: dict) -> list[str]:
    """The card's cleaned `phrases` ∪ `vocabulary` + section-title words (check c) — each
    through scope-cards' enough_letters: a term needs ≥2 letters when Sinhala-bearing / ≥3
    ASCII, a section word ≥3 Sinhala / ≥4 ASCII — anything smaller would match everything."""
    gen = card.get("generated") or {}
    terms = []
    for v in (gen.get("phrases") or []) + (gen.get("vocabulary") or []):
        t = sc.clean(sc.GLYPH_BULLET_RE.sub("", str(v))).strip()
        if t and not sc.NOISE_RE.fullmatch(t) and sc.enough_letters(t):
            terms.append(t)
    for s in gen.get("sections") or []:
        for w in WORD_RE.findall(str(s.get("title") or "")):
            if sc.enough_letters(w, "section"):
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


def wording_warnings(q: dict):
    fields = dict(all_student_fields(q))
    stem = q.get("stem") or ""
    loan = all(re.search(rf"\b{word}\b", stem, re.I) for word in ("principal", "interest"))
    math_ids = {False: set(), True: set()}
    for where, text in fields.items():
        math_ids[where.endswith("_si")].update(
            m[2] for m in MATH_SPAN.finditer(text) if re.fullmatch("[A-Z]", m[2]))
    for where, text in fields.items():
        is_si = where.endswith("_si")
        prose = MATH_SPAN.sub(" ", text)
        if BARE_ASSIGNMENT.search(prose):
            yield where, "put a bare variable assignment in inline math"
        ids = math_ids[is_si]
        bare = sorted(ids.intersection(re.findall(r"(?<!\w)[A-Z](?!\w)", prose)) - ({"A", "I"} if not is_si else set()))
        if len(ids) >= 2 and bare:
            yield where, f"consistent notation: use inline math for {', '.join(bare)} as elsewhere in the question"
        if loan and where.endswith(".stem"):
            for sentence in re.split(r"(?<=[.!?])\s+|\n", prose):
                if (REPAYMENT.search(sentence) and UNCHANGED.search(sentence)
                        and not re.search(r"\b(?:principal|interest|total)\b", sentence, re.I)):
                    yield where, "specify whether principal, interest, or the total payment stays unchanged"
                    break
    prepartitioned = (q.get("figure") and re.search(
        r"\b(?:split|partition(?:ed|s)?|subdivid(?:ed|es)|(?:rectangular|square) sections?)\b",
        q.get("stem") or "", re.I))
    for where, en in fields.items():
        if where.endswith("_si"):
            continue
        si = fields.get(where + "_si", "")
        en_ranges = [r.replace("−", "-") for pair in EN_RANGE.findall(en) for r in pair]
        si_ranges = [r.replace("−", "-") for pair in SI_RANGE.findall(si) for r in pair]
        if en_ranges and si_ranges and en_ranges != si_ranges:
            yield where + "_si", "explicit numeric range endpoints disagree with the English"
        if where.endswith(".text") and PROOF_REQUEST.search(en):
            final = fields.get(where.removesuffix(".text") + ".final")
            if final and not WORD_RE.search(MATH_SPAN.sub("", final)):
                yield where, "the prompt asks for a reason, but the final is math only"
        if (re.search(r"\b(?:finished|printed|completed) by (?:then|that (?:time|point))\b", en, re.I)
                and re.search(r"ඒ වන විට[^.?!\n]{0,45}\sවන\s", si)):
            yield where + "_si", "check completed vs ongoing action against the English"
        if where.endswith(".approach") and re.search(r"\bgradient in .+ per .+ is\b", en, re.I):
            if "ලෙස ගත් විට අනුක්‍රමණය" in si:
                yield where + "_si", "state the gradient directly in units per interval"
        if (q.get("difficulty") != "easy" and where.endswith(".text")
                and re.search(r"\b(?:product|difference|sum) of (?:two )?(?:binomials|products|expressions)\b", en, re.I)
                and re.search(r"(?:^|[.!?]\s+)(?:expand|collect|substitute)\b", en, re.I)):
            yield where, "check whether the prompt gives away multiple method steps"
        if (prepartitioned and q.get("difficulty") != "easy" and where.endswith(".text")
                and re.search(r"\barea\b", en, re.I)
                and re.search(r"\b(?:simplified|expanded) expression\b", en, re.I)):
            yield where, "check whether the pre-partitioned figure gives away the area method"


def scaffold_key(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(str.maketrans({"−": "-", "–": "-", "×": "*"}))
    text = re.sub(r"\^?\{(\d+)\}", r"\1", text)
    return re.sub(r"[\s$\\^]", "", text).lower()


def scaffold_tasks(text):
    operations = {
        "expand": r"expand|expansion of",
        "factor": r"factor(?:ise|ize)?|factor(?:isation|ization) of",
        "simplify": r"simplify|simplification of",
    }
    sinhala = {"expand": r"ප්‍රසාරණය\s+කරන්න",
               "factor": r"සාධක\s*වලට\s+වෙන්\s+කරන්න",
               "simplify": r"සුළු\s+කරන්න"}
    spans = list(MATH_SPAN.finditer(text))
    for i, span in enumerate(spans):
        prefix = re.split(r"[.?!।]", text[spans[i - 1].end() if i else 0:span.start()])[-1]
        suffix = re.split(r"[.?!।]", text[span.end():spans[i + 1].start() if i + 1 < len(spans) else len(text)], maxsplit=1)[0]
        for task, verbs in operations.items():
            instruction = sinhala[task]
            if (re.search(rf"\b(?:{verbs})\s+$", prefix, re.I)
                    or re.search(rf"{instruction}:?\s+$", prefix)
                    or re.match(rf"\s+{instruction}(?=\W|$)", suffix)):
                yield task, scaffold_key(span[2])


def scaffold_matches(q: dict, sources):
    """Find an explicitly asked algebra operation whose exact expression recurs in a source."""
    sources = [(name, is_exercise, set(scaffold_tasks(text)))
               for name, text, is_exercise in sources if isinstance(text, str)]
    for where, text in all_student_fields(q):
        if not where.endswith(".text"):
            continue
        for task, expression in scaffold_tasks(text):
            if len(expression) < 5 or not re.search("[a-z]", expression):
                continue
            hits = [(name, hard) for name, hard, tasks in sources if (task, expression) in tasks]
            if hits:
                source, hard = max(hits, key=lambda hit: hit[1])
                yield where, hard, f"exact algebra scaffold also appears in {source}; review task overlap"


def staged_figure_uses(content: dict) -> dict:
    """figure KEY → [staged ids] — where content.yaml attaches each `figures:` entry. A
    question's `figure:` → `Q<n>`; a part's → `Q<n>.<label path joined by '.'>` — the ids
    visual-check's staged-doc walk emits, so the check 'does the FILE stem equal the staged
    id' can run before the audits. Keys never referenced return no ids (unused keys are
    build-staged's call, not ours)."""
    uses: dict[str, list[str]] = {}

    def parts(nodes, prefix):
        for p in nodes or []:
            if not isinstance(p, dict):
                continue
            pid = f"{prefix}.{p.get('label')}"
            if p.get("figure"):
                uses.setdefault(p["figure"], []).append(pid)
            parts(p.get("parts"), pid)

    for i, q in enumerate(content.get("questions") or []):
        if not isinstance(q, dict):
            continue
        n = q.get("n")
        qid = f"Q{n}" if isinstance(n, int) and not isinstance(n, bool) else f"Q{i + 1}"
        if q.get("figure"):
            uses.setdefault(q["figure"], []).append(qid)
        parts(q.get("parts"), qid)
    return uses


def _feature_values(text, kind):
    text = str(text or "").replace("−", "-").replace("–", "-").replace("$", "")
    pair_pattern = rf"\(\s*({FEATURE_NUMBER})\s*,\s*({FEATURE_NUMBER})\s*\)"
    pairs = {tuple(map(float, pair)) for pair in re.findall(pair_pattern, text)}
    if kind == "vertex":
        return pairs
    coordinates = {(x,) for x, y in pairs if y == 0} if kind == "root" else {(y,) for x, y in pairs if x == 0}
    return coordinates | {(float(n),) for n in re.findall(FEATURE_NUMBER, re.sub(pair_pattern, "", text))}


def _described_values(text, kind):
    pattern = "|".join(f"(?P<{key.replace('-', '_')}>{words})" for key, words in GRAPH_FEATURES.items())
    for clause in re.split(r";|\n|(?<=[.])\s+", text):
        features = list(re.finditer(pattern, clause, re.I))
        for i, match in enumerate(features):
            if match.lastgroup == kind.replace("-", "_"):
                end = features[i + 1].start() if i + 1 < len(features) else len(clause)
                yield from _feature_values(clause[match.end():end], kind)


def _visible_element(el):
    return (isinstance(el, dict) and el.get("opacity", 1) != 0
            and (el.get("stroke") or {}).get("width", 1) != 0
            and (el.get("stroke") or {}).get("color") not in ("none", "transparent"))


def _marker_matches(el, feature, claims):
    axis, value = feature.get("axis"), feature.get("value")
    if axis not in ("x", "y") or not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    axes = re.findall(r"\baxis ([A-Z])([A-Z]) from (" + FEATURE_NUMBER + r") to (" + FEATURE_NUMBER + ")", claims)
    anchors = {p: (float(x), float(y)) for p, x, y in re.findall(
        rf"^\s*([A-Z])\s+({FEATURE_NUMBER})\s+({FEATURE_NUMBER})\s*$", claims, re.M)}
    i = 0 if axis == "x" else 1
    for a, b, start, end in axes:
        if a not in anchors or b not in anchors or anchors[a][i] == anchors[b][i]:
            continue
        if abs(anchors[a][1 - i] - anchors[b][1 - i]) > 0.1 or float(start) == float(end):
            continue
        t = (value - float(start)) / (float(end) - float(start))
        if not 0 <= t <= 1:
            continue
        position = anchors[a][i] + t * (anchors[b][i] - anchors[a][i])
        if el.get("type") == "line":
            points = el.get("points") or []
            if len(points) == 2 and points[0] != points[1] and all(abs(p[i] - position) <= 1 for p in points):
                return True
        if feature.get("kind") == "bound-marker" and el.get("type") == "point" and el.get("r", 3) > 0:
            if len(el.get("at") or ()) == 2 and abs(el["at"][i] - position) <= 1:
                return True
    return False


def figure_contract_findings(run: Path, content: dict):
    figures = content.get("figures") or {}
    contracts = content.get("figure_features") or {}
    if not isinstance(contracts, dict):
        yield True, "figure_features", "must map figure keys to lists of typed visible features"
        return
    for key in contracts.keys() - figures.keys():
        yield True, key, "visible feature contract names an unknown figure"
    inventory = {}
    seen = {}
    descriptions = {}
    for key in sorted(staged_figure_uses(content).keys() & figures.keys()):
        path = run / figures[key]
        if not path.is_file():
            continue
        figure = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(figure, dict) or not isinstance(figure.get("elements"), list):
            continue
        claim_file = path.with_name(f"{path.stem}-claims.txt")
        if not claim_file.is_file():
            claim_file = run / "figures" / f"{path.stem}-claims.txt"
        claims = claim_file.read_text(encoding="utf-8") if claim_file.is_file() else ""
        elements = {el.get("id"): el for el in figure["elements"] if _visible_element(el)}
        point_names = {el.get("label") for el in elements.values()
                       if el.get("type") == "point"}
        text_names = {el.get("value") for el in elements.values() if el.get("type") == "text"}
        point_names |= {point for point in re.findall(r'\blabel "([A-Z])" names \1\b', claims)
                        if point in text_names}
        slots = {("point", point): False for point in point_names
                 if isinstance(point, str) and re.fullmatch(r"[A-Z]", point) and point != "O"}
        if "O" in point_names:
            slots["point", "O"] = True
        declarations = contracts.get(key, [])
        if not isinstance(declarations, list):
            yield True, key, "figure_features must be a list"
            declarations = []
        for feature in declarations:
            if not isinstance(feature, dict) or not isinstance(feature.get("id"), str):
                yield True, key, "each feature needs an id and a kind"
                continue
            kind, name = feature.get("kind"), feature["id"]
            if kind == "point" and (kind, name) in slots:
                slots[kind, name] |= feature.get("decorative") is True
            elif kind in ("guide", "bound-marker") and (el := elements.get(feature.get("element"))) \
                    and _marker_matches(el, feature, claims):
                slots[kind, name] = True
            else:
                yield True, key, f"{kind} {name}: feature does not bind to its specific visible element"
        a11y = figure.get("a11y") or {}
        description = " ".join(str(a11y.get(k) or "") for k in ("title", "description"))
        if BOUND_MARK.search(description) and not any(k == "bound-marker" for k, _ in slots):
            yield True, path.stem, "a11y describes marked plot bounds without a typed visible bound-marker"
        inventory[key], descriptions[key], seen[key] = slots, description, set()

    def walk(node, path, visible, givens):
        own = node.get("figure")
        if own in inventory:
            visible = (*visible, own)
        pair = node.get("figure_refs")
        if pair is not None and (not isinstance(pair, dict)
                                 or set(pair) != {"english", "sinhala"}
                                 or any(not isinstance(value, list) for value in pair.values())):
            yield True, path, "figure_refs needs both english and sinhala lists"
            pair = None
        referenced = {}
        for medium, suffix in (("english", ""), ("sinhala", "_si")):
            prompt = str(node.get(("text" if "label" in node else "stem") + suffix) or "")
            referenced[medium] = set()
            for ref in (pair or {}).get(medium, []):
                if not isinstance(ref, dict) or not all(isinstance(ref.get(f), str) for f in ("figure", "kind", "id")):
                    yield True, path, f"{medium}: each figure reference needs figure, kind, and id"
                    continue
                key, kind, name = ref["figure"], ref["kind"], ref["id"]
                if key not in visible or (kind, name) not in inventory[key]:
                    yield True, path, f"{medium}: no visible {kind} {name} on figure {key}"
                    continue
                referenced[medium].add((key, kind, name))
                seen[key].add((kind, name))
            for key in visible:
                for kind, name in inventory[key]:
                    if kind == "point" and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", prompt):
                        seen[key].add((kind, name))
        if pair is not None and referenced["english"] != referenced["sinhala"]:
            yield True, path, "English and Sinhala figure_refs must bind the same visible features"

        asks = node.get("figure_asks", [])
        if not isinstance(asks, list) or any(not isinstance(a, str) or a not in GRAPH_FEATURES for a in asks):
            yield True, path, "figure_asks must list vertex, root or y-intercept feature types"
            asks = []
        prompt = " ".join(str(node.get(k) or "") for k in ("text", "text_si", "stem", "stem_si"))
        for kind, pattern in GRAPH_FEATURES.items():
            if kind not in asks and not re.search(pattern, prompt, re.I):
                continue
            finals = set().union(*(_feature_values(node.get(k), kind) for k in ("final", "final_si")))
            for key in visible:
                leaked = set(_described_values(descriptions[key], kind)) & finals
                if leaked - set(_described_values(givens, kind)):
                    yield True, path, f"{key} a11y reveals the asked {kind} answer (T125)"
        for child in node.get("parts") or []:
            if isinstance(child, dict):
                yield from walk(child, f"{path}.{child.get('label')}", visible, givens)

    for q in content["questions"]:
        if isinstance(q, dict):
            givens = " ".join(str(q.get(k) or "") for k in ("stem", "stem_si"))
            yield from walk(q, f"Q{q.get('n')}", (), givens)
    for key, slots in inventory.items():
        for kind, name in sorted(slots.keys() - seen[key]):
            if not slots[kind, name]:
                yield False, key, f"unused named point {name}; reference it or mark it decorative"


def lint(run: Path, args, log=print) -> tuple[int, int]:
    content = load_content(run)
    cards = load_cards(args) if args.card else {}
    lesson_map = content.get("lessons")
    lesson_keys = list(lesson_map) if isinstance(lesson_map, dict) else []
    for spec in args.card:
        key = spec.partition("=")[0]
        if key not in lesson_keys:
            have = ", ".join(map(str, lesson_keys)) or "(none)"
            die(f"--card {spec}: {key!r} is not a content.yaml lessons key (have: {have})")
    questions = content["questions"]
    fails = warns = 0
    for q in questions:
        for where, message in wording_warnings(q):
            warns += 1
            log(f"  WARN {where}: {message}")
    for hard, where, message in figure_contract_findings(run, content):
        fails += int(hard)
        warns += int(not hard)
        log(f"  {'FAIL' if hard else 'WARN'} {where}: {message}")

    # (a) not_taught probes must not appear in a question field — PER QUESTION by
    # default: a question answers only to the cards its own `lessons:` keys bind (a
    # probe from an untagged lesson's card is not its business). --all-probes is the
    # old run-wide check.
    probes_of = {key: [(card["name"], nt.get("concept"), p)
                       for nt in ((card["doc"].get("curated") or {})
                                  .get("not_taught") or [])
                       for p in (nt.get("probes") or [])]
                 for key, card in cards.items()}
    for q in questions:
        if args.all_probes:
            probes = [(key, *rest)
                      for key, rests in probes_of.items() for rest in rests]
        else:
            tagged = q.get("lessons") or []
            probes = [(key, *rest)
                      for key in tagged if key in probes_of
                      for rest in probes_of[key]]
            for key in tagged:
                if key not in probes_of:
                    warns += 1
                    log(f"  WARN Q{q.get('n')}: lesson key {key!r} has no bound --card — "
                        f"its not_taught probes were not checked")
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
                    f"text/approach uses its vocabulary, phrases or section words — heuristic")

    # (d) set rubric — the leaf `level:` keys against the plan appendix's rules
    rubrics = {"easy": rubric_easy, "medium": rubric_medium, "medium-hard": rubric_medium_hard}
    if args.rubric in rubrics:
        f, w = rubrics[args.rubric](questions, log)
        fails += f
        warns += w
    elif args.rubric == "by-band":
        # a mixed batch (`difficulty: medium` + `difficulty: hard` overrides): each question is
        # checked against its OWN band's rubric; set-wide fractions are per band group
        default = content.get("difficulty")
        for band, name in (("easy", "easy"), ("medium", "medium"), ("hard", "medium-hard")):
            group = [q for q in questions if q.get("difficulty", default) == band]
            if group:
                log(f"  rubric {name}: " + " ".join(f"Q{q.get('n')}" for q in group))
                f, w = rubrics[name](group, log)
                fails += f
                warns += w

    # (f) 0024 bilingual sides — every student field carries its `*_si` twin, in the right
    # script (build-staged.bilingual_problem — the same rule the builder refuses on, run here so
    # the critic sees the failures named rather than the build just dying).
    for q in questions:
        qn = f"Q{q.get('n')}"
        pairs = [(q, "stem", "stem_si", qn)]
        if not q.get("parts"):
            pairs += [(q, "approach", "approach_si", qn), (q, "final", "final_si", qn)]

        def walk_pairs(parts, prefix):
            for p in parts or []:
                if not isinstance(p, dict):
                    continue
                pid = f"{prefix}.{p.get('label')}"
                pairs.append((p, "text", "text_si", pid))
                if not p.get("parts"):
                    pairs.append((p, "approach", "approach_si", pid))
                    pairs.append((p, "final", "final_si", pid))
                walk_pairs(p.get("parts"), pid)

        walk_pairs(q.get("parts"), qn)
        for node, en_key, si_key, where in pairs:
            # a wholly absent answer pair is a different defect (build-staged's leaf check) —
            # flag it only when one side IS present
            if node.get(en_key) is None and node.get(si_key) is None:
                continue
            problem = bs.bilingual_problem(node.get(en_key), node.get(si_key), si_key)
            if problem:
                fails += 1
                log(f"  FAIL {where}: {problem}")

    # (g) Sinhala text inside KaTeX \text{} is forbidden (D7 / S4 §0.4, S8 §0.8).
    # Prose and maths are separate nodes; Sinhala belongs in prose outside $…$, never in \text{}.
    TEXT_SINHALA = re.compile(r"\\text\{[^}]*[\u0D80-\u0DFF]")
    for q in questions:
        for where, val in all_student_fields(q):
            if TEXT_SINHALA.search(val):
                fails += 1
                log(f"  FAIL {where}: Sinhala text inside KaTeX \\text{{}} — prose and maths "
                    f"are separate nodes (D7, S4 §0.4, S8 §0.8)")

    # (h) approach / approach_si opening with announcement prefix ('Answer:' / 'පිළිතුර:').
    # S8 §4.1: The approach teaches the method. It is not an answer key.
    ANNOUNCEMENT_PREFIX = re.compile(r"^\s*(?:Answer|Solution|පිළිතුර|විසඳුම)\s*[:\-–—]")
    for q in questions:
        for where, val in all_student_fields(q):
            if where.endswith((".approach", ".approach_si")) and ANNOUNCEMENT_PREFIX.search(val):
                fails += 1
                log(f"  FAIL {where}: approach opens with an announcement prefix ('Answer:' / 'පිළිතුර:') "
                    f"— teach the method, do not announce (S8 §4.1)")

    # (e) duplicate fingerprint — digits masked, Jaccard vs existing rows and bound card items
    existing_scaffolds = []
    for path in getattr(args, "existing", []) or []:
        p = Path(path)
        if not p.is_file():
            die(f"--existing {path}: no such file")
        rows = load_existing(p)
        for row in rows:
            rid = row.get("question_id") or row.get("id") or "?"
            for key in ("stem_excerpt", "question_text"):
                existing_scaffolds.append((f"{p.name}:{rid}", row.get(key), False))
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
    for q in questions:
        qt = mask_tokens(question_surface(q))
        scaffolds = list(existing_scaffolds)
        for key in (q.get("lessons") or []):
            if key not in cards:
                continue
            gen = cards[key]["doc"].get("generated") or {}
            card_name = cards[key]["name"]
            for index, example in enumerate(gen.get("worked_examples") or [], 1):
                scaffolds.append((f"{card_name} worked example {index}", example.get("excerpt"), False))
                tokens = mask_tokens(example.get("excerpt") or "")
                score = jaccard(qt, tokens)
                if score >= 0.6:
                    heading = example.get("heading") or f"worked example {index}"
                    warns += 1
                    log(f"  WARN Q{q.get('n')} ≈ {card_name} worked example {index} "
                        f"({heading}) (Jaccard {score:.2f}, digits masked) — duplicate "
                        "lesson-item fingerprint")
            for exercise in gen.get("exercises") or []:
                heading = exercise.get("heading") or "exercise"
                for index, item in enumerate(exercise.get("items") or [], 1):
                    scaffolds.append((f"{card_name} exercise {heading} item {index}", item, True))
                    tokens = mask_tokens(item)
                    score = jaccard(qt, tokens)
                    if score >= 0.6:
                        warns += 1
                        log(f"  WARN Q{q.get('n')} ≈ {card_name} exercise {heading} item "
                            f"{index} (Jaccard {score:.2f}, digits masked) — duplicate "
                            "lesson-item fingerprint")
        for where, hard, message in scaffold_matches(q, scaffolds):
            fails += int(hard)
            warns += int(not hard)
            log(f"  {'FAIL' if hard else 'WARN'} {where}: {message}")
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
    ap.add_argument("--all-probes", action="store_true",
                    help="check every question against ALL bound cards' not_taught probes "
                         "(the pre-W12 run-wide behaviour); the default is per-question — "
                         "only the cards the question's lessons: keys bind")
    ap.add_argument("--rubric", choices=["easy", "medium", "medium-hard", "by-band"], default=None,
                    help="check the leaf `level:` keys against a set rubric (check d — R "
                         "only as part (a), i.e. the first part in document order)")
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
