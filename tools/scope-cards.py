#!/usr/bin/env python3
"""scope-cards.py — lesson scope cards for the vibhaga-qgen plugin (W2).

A scope card lives in the PRIVATE corpus at `maths/grade-NN/scope-cards/NN-<Slug>.yaml`, one per
published lesson. It is the compact, machine-checkable statement of what a lesson teaches — the
`generate` skill reads it before authoring (scope statement + don't-copy list + difficulty rubric
anchors). The card has three parts:

  top matter   grade / subject / medium / lesson_number / titles / syllabus_refs / term / periods
               + `source: {file, sha256}` — pinned to the lesson file's current sha
  generated    tool-owned — sections, vocabulary, worked examples, exercises, activities, figure
               kinds/counts, summary. `draft` rewrites it every time; a hand edit fails `check`.
  curated      agent-written — status, not_taught (with probes grounded in absence), prerequisites,
               difficulty_hooks. `draft` preserves an existing `curated:` block unchanged.

Usage:

    scope-cards.py draft --grade 6 [--lessons 1,7] [--corpus PATH]
    scope-cards.py check --grade 6 [--corpus PATH]
    scope-cards.py draft|check --exam ol      # refused — O/L composition is plan OD-3
    scope-cards.py --self-test

Corpus resolution: `--corpus` → `VIBHAGA_CORPUS` → sibling `<plugin>/../Vibhaga-Maths-Corpus`.

Exit 0 success · exit 1 `check` found card failures · exit 2 refusal (no corpus, grade dir without
README+manifest, a manifest lesson with no lesson file, --exam ol, bad arguments).

The only Sinhala in this file is the set of structural heading keywords the corpus format defines
(see plugin AGENTS.md — public repo, no real corpus text anywhere).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Structural Sinhala keywords — heading/bold markers defined by the corpus format itself. These
# are the ONLY Sinhala strings allowed in this public repo; no real lesson text may appear here.
KW_EXAMPLE = "නිදසුන"          # worked-example heading: ####/### නිදසුන N
KW_EXERCISE = "අභ්‍යාසය"       # exercise heading: #### N.M අභ්‍යාසය / #### මිශ්‍ර අභ්‍යාසය
KW_ACTIVITY = "ක්‍රියාකාරකම"  # activity heading: #### ක්‍රියාකාරකම N
KW_SUMMARY = "සාරාංශය"         # summary heading: ###/## සාරාංශය
KW_STEP = "පියවර"              # activity step marker: **පියවර N**
KW_FIGURE = "රූපය"             # figure caption marker: **N රූපය**

EXCERPT_EXAMPLE = 200
EXCERPT_ITEM = 140
VOCAB_MAX = 60

ANCHOR_RE = re.compile(r'^\s*<a id="([^"]+)"\s*/?>\s*(?:</a>)?\s*$')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
FIGTBL_RE = re.compile(r'^(Figure|Table)\s+—')
COMMENT_RE = re.compile(r'^\s*<!--')
IMG_LINE_RE = re.compile(r'^\s*\[?!\[')
META_RE = re.compile(r'^\s*\*\*(Source|Description|Concepts|Source text):\*\*')
TABLE_ROW_RE = re.compile(r'^\s*\|')
TAG_RE = re.compile(r'^\s*</?(table|thead|tbody|tfoot|tr|td|th|caption|colgroup|col)[\s>]')
BOLD_RE = re.compile(r'\*\*([^*\n]+)\*\*')
BULLET_RE = re.compile(r'^[-*]\s+')
# Corpus summary items are `- ` bullets whose text opens with a decorative glyph — `**•**`, `●`,
# `•` (optionally bold-wrapped, optionally doubled) — which is furniture, not content.
GLYPH_BULLET_RE = re.compile(r'^\s*(?:\*\*)?[•●]+(?:\*\*)?\s*')
ASCII_WORD_RE = re.compile(r'^[a-z ]+$')
NUMPARA_RE = re.compile(r'^\(\d+\)|^\d+[.)]\s')
SECNUM_RE = re.compile(r'^\s*(\d+(?:\s*\.\s*\d+)*)(?:\s+|$)')
NOISE_RE = re.compile(r'[\d\W_]+')
LESSON_FILE_RE = re.compile(r'^(\d+)-.*\.md$')
SAME_GRADE_RE = re.compile(r'^grade-(\d+)/(\d+)$')
PRIOR_GRADE_RE = re.compile(r'^grade-(\d+):(.+)$')

DROP_MARKERS = {"Source:", "Description:", "Concepts:", "Source text:"}
CARD_CURATED_KEYS = {"status", "not_taught", "prerequisites", "difficulty_hooks"}
STATUSES = ("todo", "drafted", "reviewed")
LEVELS = ("M", "H")


def die(msg: str) -> "None":
    print(f"scope-cards: {msg}", file=sys.stderr)
    sys.exit(2)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def ascii_lower(s: str) -> str:
    """Case-insensitive for ASCII only — Sinhala has no case."""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in s)


def probe_norm(s: str) -> str:
    return ascii_lower(nfc(s))


def probe_occurs(probe: str, lesson_text_nfc: str) -> bool:
    """A pure-ASCII alphabetic probe matches on word boundaries — `ton` must not fire on
    `button`. Sinhala probes and anything containing digits or symbols stay substring
    matches. NFC + ASCII case-fold applies in both paths."""
    p = probe_norm(probe)
    if ASCII_WORD_RE.fullmatch(p):
        rx = re.compile(r"(?<![a-z0-9])" + r"\s+".join(re.escape(w) for w in p.split())
                        + r"(?![a-z0-9])")
        return rx.search(lesson_text_nfc) is not None
    return p in lesson_text_nfc


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_yaml():
    try:
        import yaml
        return yaml
    except ImportError:
        die("PyYAML is not installed — `pip install pyyaml`")


def dump_card(doc: dict) -> str:
    yaml = import_yaml()
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1_000_000)


# -------------------------------------------------------------------------------------------------
# Lesson parsing. The corpus format: `### N.M` section headings (`##`/`###` may carry සාරාංශය);
# `####` sub-headings are worked examples (නිදසුන), exercises (N.M අභ්‍යාසය, මිශ්‍ර අභ්‍යාසය),
# activities (ක්‍රියාකාරකම), `#### Figure —`/`#### Table —` blocks, or generic subsections. Every
# unit carries an `<a id>` anchor on the line(s) before it. Figure/Table blocks run: heading,
# markdown or HTML table, image link, **Source:**, **Description:**, **Source text:** bullets,
# **Concepts:** tag list. In two lessons (14, 15) worked examples sit at `###` level.
# -------------------------------------------------------------------------------------------------
def split_frontmatter(text: str) -> tuple[str | None, str]:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, text


def consume_block(lines: list[str], i: int) -> tuple[list[str], int]:
    """Consume a `#### Figure —`/`#### Table —` block starting at line i (the heading line).
    Returns (concepts, next_index). The block ends at the first line that is not part of the
    figure/table structure — usually the next heading or body prose after **Concepts:**."""
    concepts: list[str] = []
    in_source_text = False
    in_html_table = False
    j = i + 1
    while j < len(lines):
        line = lines[j]
        if HEADING_RE.match(line):
            break
        if not line.strip() or ANCHOR_RE.match(line) or COMMENT_RE.match(line):
            j += 1
            continue
        if in_html_table:
            if "</table>" in line:
                in_html_table = False
            j += 1
            continue
        if "<table" in line:
            in_html_table = True
            j += 1
            continue
        if TABLE_ROW_RE.match(line) or TAG_RE.match(line) or IMG_LINE_RE.match(line):
            j += 1
            continue
        m = META_RE.match(line)
        if m:
            name = m.group(1)
            if name == "Source text":
                in_source_text = True
            else:
                in_source_text = False
                if name == "Concepts":
                    value = line.split("**Concepts:**", 1)[1].strip()
                    concepts = [c.strip() for c in value.split(",") if c.strip()]
            j += 1
            continue
        if in_source_text and BULLET_RE.match(line.strip()):
            j += 1
            continue
        break
    return concepts, j


def parse_elements(body: str) -> list[dict]:
    """Reduce the lesson body to an element stream: anchor / heading / figure / table / body."""
    elems: list[dict] = []
    last_anchor = None
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = ANCHOR_RE.match(line)
        if m:
            last_anchor = m.group(1)
            elems.append({"kind": "anchor", "id": m.group(1)})
            i += 1
            continue
        if not line.strip() or COMMENT_RE.match(line):
            i += 1
            continue
        h = HEADING_RE.match(line)
        if h:
            level, text = len(h.group(1)), h.group(2).strip()
            fm = FIGTBL_RE.match(text)
            if fm:
                concepts, i = consume_block(lines, i)
                elems.append({"kind": fm.group(1).lower(), "anchor": last_anchor,
                              "concepts": concepts})
                continue
            elems.append({"kind": "heading", "level": level, "text": text,
                          "anchor": last_anchor})
            i += 1
            continue
        elems.append({"kind": "body", "text": line})
        i += 1
    return elems


def clean(text: str) -> str:
    """Strip markdown images/links, <a id> anchors, comments and inline tags; collapse whitespace."""
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'<!--.*?-->', '', text)
    text = re.sub(r'</?(a|span|sub|sup|em|strong|b|i)\b[^>]*>', '', text)
    return " ".join(text.split())


def clip(text: str, limit: int) -> str:
    return text[:limit]


def classify_heading(text: str) -> str | None:
    """A specialized heading kind, or None for a plain/generic heading."""
    if KW_EXAMPLE in text:
        return "example"
    if KW_EXERCISE in text:
        return "exercise"
    if KW_ACTIVITY in text:
        return "activity"
    return None


def section_number(text: str) -> str | None:
    m = SECNUM_RE.match(text)
    if not m:
        return None
    return re.sub(r"\s+", "", m.group(1))


def section_title(text: str, number: str | None) -> str:
    if number is None:
        return text
    return SECNUM_RE.sub("", text, count=1).strip()


def span_end(elems: list[dict], start: int, level: int) -> int:
    """A worked example / activity runs to the next heading at its level or higher.
    Figure/Table blocks are elements of their own and never end a span."""
    j = start + 1
    while j < len(elems):
        el = elems[j]
        if el["kind"] == "heading" and el["level"] <= level:
            return j
        j += 1
    return len(elems)


def exercise_span_end(elems: list[dict], start: int) -> int:
    """An exercise runs to the next `###`(or higher) heading or the next exercise/activity
    `####` heading — a නිදසුන or generic `####` INSIDE it is exercise content, not a boundary."""
    j = start + 1
    while j < len(elems):
        el = elems[j]
        if el["kind"] == "heading":
            if el["level"] <= 3 or KW_EXERCISE in el["text"] or KW_ACTIVITY in el["text"]:
                return j
        j += 1
    return len(elems)


def body_excerpt(elems: list[dict], start: int, level: int, limit: int = EXCERPT_EXAMPLE) -> str:
    end = span_end(elems, start, level)
    parts = []
    for el in elems[start + 1:end]:
        if el["kind"] == "body":
            t = re.sub(BULLET_RE, "", el["text"].strip())
            if t:
                parts.append(t)
    return clip(clean(" ".join(parts)), limit)


def exercise_items(elems: list[dict], start: int) -> list[str]:
    """Top-level `- ` list items and numbered `(N)`/`N.` paragraphs in the exercise span.
    Continuation lines join the current item; figure/table blocks are not body lines."""
    end = exercise_span_end(elems, start)
    items: list[str] = []
    for el in elems[start + 1:end]:
        if el["kind"] != "body":
            continue
        t = el["text"].strip()
        if BULLET_RE.match(t):
            items.append(re.sub(BULLET_RE, "", t))
        elif NUMPARA_RE.match(t):
            items.append(t)
        elif items:
            items[-1] += " " + t
    return [clip(clean(x), EXCERPT_ITEM) for x in items]


def summary_items(elems: list[dict], start: int, level: int) -> list[str]:
    end = span_end(elems, start, level)
    items: list[str] = []
    for el in elems[start + 1:end]:
        if el["kind"] != "body":
            continue
        t = el["text"].strip()
        if BULLET_RE.match(t):
            items.append(GLYPH_BULLET_RE.sub("", re.sub(BULLET_RE, "", t)))
        elif items:
            items[-1] += " " + t
    return [clean(x) for x in items]


def collect_vocabulary(body: str) -> list[str]:
    """Bold **terms** as printed, first-seen order, deduped — minus the corpus's structural
    markers, step/figure labels, pure digits/punctuation, and anything over VOCAB_MAX chars."""
    out, seen = [], set()
    for m in BOLD_RE.finditer(body):
        term = m.group(1).strip()
        if not term or term in seen or term in DROP_MARKERS or len(term) > VOCAB_MAX:
            continue
        if re.match(r"^" + KW_STEP + r"\s*\d", term) or re.match(r"^\d+\s*" + KW_FIGURE, term):
            continue
        if NOISE_RE.fullmatch(term):
            continue
        seen.add(term)
        out.append(term)
    return out


def build_generated(body: str, elems: list[dict]) -> dict:
    sections, wexs, exs, acts = [], [], [], []
    figure_kinds: dict[str, int] = {}
    figures = tables = 0
    summary: list[str] = []
    current_section: str | None = None

    for idx, el in enumerate(elems):
        kind = el["kind"]
        if kind in ("figure", "table"):
            if kind == "figure":
                figures += 1
            else:
                tables += 1
            for c in el["concepts"]:
                figure_kinds[c] = figure_kinds.get(c, 0) + 1
            continue
        if kind != "heading":
            continue
        level, text, anchor = el["level"], el["text"], el["anchor"]
        cls = classify_heading(text)
        if level in (2, 3) and cls is None:
            if re.match(r"^Source\b", text):
                continue
            num = section_number(text)
            sections.append({"number": num, "title": section_title(text, num)})
            if num is not None:
                current_section = num
            if text.startswith(KW_SUMMARY):
                summary = summary_items(elems, idx, level)
            continue
        if cls is None:
            continue
        sec = section_number(text) or current_section
        if cls == "example":
            wexs.append({"section": sec, "heading": text, "anchor": anchor,
                         "excerpt": body_excerpt(elems, idx, level)})
        elif cls == "exercise":
            exs.append({"section": sec, "heading": text, "anchor": anchor,
                        "items": exercise_items(elems, idx)})
        elif cls == "activity":
            acts.append({"section": sec, "heading": text, "anchor": anchor,
                         "excerpt": body_excerpt(elems, idx, level)})

    return {
        "sections": sections,
        "vocabulary": collect_vocabulary(body),
        "worked_examples": wexs,
        "exercises": exs,
        "activities": acts,
        "figure_kinds": [{"concept": c, "count": n} for c, n in figure_kinds.items()],
        "figures": figures,
        "tables": tables,
        "summary": summary,
    }


# -------------------------------------------------------------------------------------------------
# Card build
# -------------------------------------------------------------------------------------------------
def build_card(lesson_path: Path) -> dict:
    yaml = import_yaml()
    text = lesson_path.read_text(encoding="utf-8")
    fm_text, body = split_frontmatter(text)
    fm = yaml.safe_load(fm_text) if fm_text else {}
    if not isinstance(fm, dict):
        fm = {}
    elems = parse_elements(body)
    return {
        "schema_version": 1,
        "grade": fm.get("grade"),
        "subject": fm.get("subject"),
        "medium": fm.get("medium"),
        "lesson_number": fm.get("lesson_number"),
        "title_en": fm.get("title_en"),
        "title_si": fm.get("title_si"),
        "syllabus_refs": fm.get("syllabus_refs") or [],
        "term": fm.get("term"),
        "periods": fm.get("periods"),
        "source": {"file": f"lessons/{lesson_path.name}", "sha256": sha256_file(lesson_path)},
        "generated": build_generated(body, elems),
    }


def skeleton_curated() -> dict:
    return {"status": "todo", "not_taught": [], "prerequisites": [], "difficulty_hooks": []}


# -------------------------------------------------------------------------------------------------
# Corpus / grade resolution
# -------------------------------------------------------------------------------------------------
def resolve_corpus(args) -> Path:
    if getattr(args, "corpus", None):
        p = Path(args.corpus)
    elif os.environ.get("VIBHAGA_CORPUS"):
        p = Path(os.environ["VIBHAGA_CORPUS"])
    else:
        p = ROOT.parent / "Vibhaga-Maths-Corpus"
    p = p.resolve()
    if not p.is_dir():
        die(f"no corpus at {p} — pass --corpus or set VIBHAGA_CORPUS")
    return p


def grade_dir(corpus: Path, grade: int) -> Path:
    return corpus / "maths" / f"grade-{grade:02d}"


def manifest_lessons(gd: Path) -> list[int]:
    yaml = import_yaml()
    data = yaml.safe_load((gd / "manifest.yaml").read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        die(f"{gd / 'manifest.yaml'}: not a mapping")
    included = data.get("included_lessons") or []
    out = []
    for v in included:
        if not isinstance(v, int) or isinstance(v, bool):
            die(f"{gd / 'manifest.yaml'}: included_lessons entry {v!r} is not an integer")
        out.append(v)
    return out


def lesson_files(gd: Path) -> dict[int, Path]:
    out = {}
    ldir = gd / "lessons"
    if not ldir.is_dir():
        return out
    for p in sorted(ldir.glob("*.md")):
        m = LESSON_FILE_RE.match(p.name)
        if m:
            out[int(m.group(1))] = p
    return out


def require_grade(corpus: Path, grade: int) -> tuple[Path, list[int], dict[int, Path]]:
    """Refuse (exit 2) unless the grade is published: README.md + manifest.yaml present, and
    every manifest `included_lessons` entry has a lesson file."""
    gd = grade_dir(corpus, grade)
    missing = [n for n in ("README.md", "manifest.yaml") if not (gd / n).is_file()]
    if missing:
        die(f"grade {grade}: no published grade in {gd} — missing {', '.join(missing)}")
    included = manifest_lessons(gd)
    files = lesson_files(gd)
    gone = [n for n in included if n not in files]
    if gone:
        die(f"grade {grade}: manifest included_lessons with no lesson file: "
            + ", ".join(f"{n:02d}" for n in gone))
    return gd, sorted(included), files


def refuse_ol(corpus: Path) -> None:
    """--exam ol needs complete grade-10 AND grade-11 card sets; composition is plan OD-3."""
    missing = []
    for g in (10, 11):
        gd = grade_dir(corpus, g)
        if not (gd / "manifest.yaml").is_file():
            missing.append(f"grade-{g:02d} (no published grade)")
            continue
        cards = gd / "scope-cards"
        included = manifest_lessons(gd)
        if not cards.is_dir():
            missing.append(f"grade-{g:02d} (no scope-cards dir, {len(included)} lessons)")
            continue
        have = {p.stem.split("-", 1)[0] for p in cards.glob("*.yaml")}
        want = {f"{n:02d}" for n in included}
        if have < want:
            missing.append(f"grade-{g:02d} ({len(have & want)}/{len(want)} cards)")
    if missing:
        die("--exam ol: O/L scope needs complete grade-10 and grade-11 card sets — missing: "
            + "; ".join(missing))
    die("--exam ol: O/L composition not implemented yet (plan OD-3)")


# -------------------------------------------------------------------------------------------------
# draft
# -------------------------------------------------------------------------------------------------
def parse_lesson_sel(value: str | None, included: list[int]) -> list[int]:
    if not value:
        return included
    sel = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            sel.append(int(part))
        except ValueError:
            die(f"--lessons: {part!r} is not a lesson number")
    unknown = [n for n in sel if n not in included]
    if unknown:
        die(f"--lessons: not published in this grade: "
            + ", ".join(f"{n:02d}" for n in unknown))
    return sel


def cmd_draft(args) -> int:
    corpus = resolve_corpus(args)
    if args.exam:
        refuse_ol(corpus)
    gd, included, files = require_grade(corpus, args.grade)
    sel = parse_lesson_sel(args.lessons, included)
    cards = gd / "scope-cards"
    cards.mkdir(exist_ok=True)
    yaml = import_yaml()
    written = unchanged = 0
    for nn in sel:
        lp = files[nn]
        card = build_card(lp)
        out = cards / f"{lp.stem}.yaml"
        curated = None
        if out.is_file():
            try:
                old = yaml.safe_load(out.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 — never clobber a hand-curated block
                die(f"{out.name}: existing card does not parse ({exc}) — fix or remove it by hand")
            curated = old.get("curated") if isinstance(old, dict) else None
        card["curated"] = curated if isinstance(curated, dict) else skeleton_curated()
        text = dump_card(card)
        if out.is_file() and out.read_text(encoding="utf-8") == text:
            unchanged += 1
            print(f"draft: unchanged {out.name}")
        else:
            out.write_text(text, encoding="utf-8")
            written += 1
            print(f"draft: wrote {out.name}")
    print(f"draft: {len(sel)} lesson(s) · {written} written · {unchanged} unchanged")
    return 0


# -------------------------------------------------------------------------------------------------
# check
# -------------------------------------------------------------------------------------------------
def schema_problems(data, grade: int, lesson_name: str) -> list[str]:
    probs = []
    if not isinstance(data, dict):
        return ["card is not a YAML mapping"]
    if data.get("schema_version") != 1:
        probs.append("schema_version must be 1")
    if data.get("grade") != grade:
        probs.append(f"grade must be {grade} (got {data.get('grade')!r})")
    for key in ("subject", "medium", "title_en", "title_si"):
        if not isinstance(data.get(key), str) or not data[key]:
            probs.append(f"{key} must be nonempty text")
    for key in ("lesson_number", "term", "periods"):
        if not isinstance(data.get(key), int) or isinstance(data.get(key), bool):
            probs.append(f"{key} must be an integer")
    if not isinstance(data.get("syllabus_refs"), list):
        probs.append("syllabus_refs must be a list")
    src = data.get("source")
    if not isinstance(src, dict):
        probs.append("source must be a mapping")
    else:
        if src.get("file") != f"lessons/{lesson_name}":
            probs.append(f"source.file must be lessons/{lesson_name} (got {src.get('file')!r})")
        if not isinstance(src.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", src["sha256"] or ""):
            probs.append("source.sha256 must be 64 lowercase hex")
    if not isinstance(data.get("generated"), dict):
        probs.append("generated must be a mapping")
    if not isinstance(data.get("curated"), dict):
        probs.append("curated must be a mapping")
    return probs


def curated_problems(curated: dict, lesson_text_nfc: str, card_lesson: int,
                     grade: int, cards: Path) -> list[str]:
    probs = []
    extra = set(curated) - CARD_CURATED_KEYS
    if extra:
        probs.append(f"curated: unknown keys {sorted(extra)}")
    status = curated.get("status")
    if status not in STATUSES:
        probs.append(f"curated.status must be one of {STATUSES} (got {status!r})")
    elif status == "todo":
        probs.append("curated.status is todo — curate the card")

    nt = curated.get("not_taught")
    if not isinstance(nt, list):
        probs.append("curated.not_taught must be a list")
        nt = []
    if not 2 <= len(nt) <= 5:
        probs.append(f"curated.not_taught must have 2-5 entries (got {len(nt)})")
    for i, item in enumerate(nt):
        where = f"not_taught[{i}]"
        if not isinstance(item, dict):
            probs.append(f"{where}: must be a mapping")
            continue
        if not isinstance(item.get("concept"), str) or not item["concept"].strip():
            probs.append(f"{where}: concept is required")
        if not isinstance(item.get("why"), str) or not item["why"].strip():
            probs.append(f"{where}: why is required")
        probes = item.get("probes")
        if not isinstance(probes, list) or not probes or \
                not all(isinstance(p, str) and p.strip() for p in probes):
            probs.append(f"{where}: needs at least one nonempty probe")
            continue
        for p in probes:
            if probe_occurs(p, lesson_text_nfc):
                probs.append(f"{where}: probe {p!r} OCCURS in the lesson — "
                             f"if the term is printed, the concept may be taught")

    pre = curated.get("prerequisites")
    if not isinstance(pre, list):
        probs.append("curated.prerequisites must be a list")
        pre = []
    for i, item in enumerate(pre):
        where = f"prerequisites[{i}]"
        if not isinstance(item, dict):
            probs.append(f"{where}: must be a mapping")
            continue
        if not isinstance(item.get("why"), str) or not item["why"].strip():
            probs.append(f"{where}: why is required")
        ref = item.get("lesson")
        if not isinstance(ref, str):
            probs.append(f"{where}: lesson must be 'grade-NN/MM' or 'grade-NN:<text>'")
            continue
        m = SAME_GRADE_RE.match(ref)
        if m:
            gg, nn = int(m.group(1)), int(m.group(2))
            if gg != grade:
                probs.append(f"{where}: same-grade form grade-NN/MM must use this grade ({grade:02d})")
            elif nn >= card_lesson:
                probs.append(f"{where}: {ref} is not a lower-numbered lesson")
            elif not list(cards.glob(f"{nn:02d}-*.yaml")):
                probs.append(f"{where}: no scope card for {ref}")
            continue
        m = PRIOR_GRADE_RE.match(ref)
        if m:
            gg = int(m.group(1))
            if gg >= grade:
                probs.append(f"{where}: prior-grade form needs grade < {grade} (got {gg:02d})")
            elif not m.group(2).strip():
                probs.append(f"{where}: prior-grade form needs free text after the colon")
            continue
        probs.append(f"{where}: unrecognised lesson ref {ref!r}")

    hooks = curated.get("difficulty_hooks")
    if not isinstance(hooks, list):
        probs.append("curated.difficulty_hooks must be a list")
        hooks = []
    if not 2 <= len(hooks) <= 4:
        probs.append(f"curated.difficulty_hooks must have 2-4 entries (got {len(hooks)})")
    for i, item in enumerate(hooks):
        where = f"difficulty_hooks[{i}]"
        if not isinstance(item, dict):
            probs.append(f"{where}: must be a mapping")
            continue
        if item.get("level") not in LEVELS:
            probs.append(f"{where}: level must be one of {LEVELS} (got {item.get('level')!r})")
        if not isinstance(item.get("hook"), str) or not item["hook"].strip():
            probs.append(f"{where}: hook is required")
    return probs


def check_card(cpath: Path, lesson_path: Path, grade: int, lesson_number: int,
               cards: Path, lesson_text_nfc: str) -> list[str]:
    yaml = import_yaml()
    try:
        data = yaml.safe_load(cpath.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"card does not parse: {exc}"]
    probs = schema_problems(data, grade, lesson_path.name)
    if isinstance(data, dict) and isinstance(data.get("lesson_number"), int) \
            and data["lesson_number"] != lesson_number:
        probs.append(f"lesson_number must be {lesson_number} (got {data['lesson_number']})")
    if not probs:
        if data["source"]["sha256"] != sha256_file(lesson_path):
            probs.append("source.sha256 is stale — the lesson file changed since the card was drafted")
        if data["generated"] != build_card(lesson_path)["generated"]:
            probs.append("generated differs from what draft would emit — re-run draft "
                         "(generated is tool-owned)")
        probs += curated_problems(data["curated"], lesson_text_nfc, lesson_number, grade, cards)
    return probs


def cmd_check(args) -> int:
    corpus = resolve_corpus(args)
    if args.exam:
        refuse_ol(corpus)
    gd, included, files = require_grade(corpus, args.grade)
    cards = gd / "scope-cards"
    n_cards = n_ok = n_fail = 0
    for nn in included:
        lp = files[nn]
        n_cards += 1
        exact = cards / f"{lp.stem}.yaml"
        cands = sorted(cards.glob(f"{nn:02d}-*.yaml")) if cards.is_dir() else []
        cpath = exact if exact.is_file() else (cands[0] if len(cands) == 1 else None)
        if cpath is None:
            n_fail += 1
            print(f"{nn:02d}-<no card> FAIL: no scope card for lessons/{lp.name}")
            continue
        lesson_text = probe_norm(lp.read_text(encoding="utf-8"))
        probs = check_card(cpath, lp, args.grade, nn, cards, lesson_text)
        if probs:
            n_fail += 1
            print(f"{cpath.name} FAIL: " + " · ".join(probs))
        else:
            n_ok += 1
            print(f"{cpath.name} OK")
    if cards.is_dir():
        expected = {files[n].stem for n in included}
        for p in sorted(cards.glob("*.yaml")):
            if p.stem not in expected:
                n_cards += 1
                n_fail += 1
                print(f"{p.name} FAIL: card has no published lesson")
    print(f"check: {n_cards} card(s) · {n_ok} passed · {n_fail} failed")
    return 1 if n_fail else 0


# -------------------------------------------------------------------------------------------------
# --self-test — the real suite is tests/test_scope_cards.py; this is a smoke run over the fixture.
# -------------------------------------------------------------------------------------------------
def self_test() -> int:
    fixture = ROOT / "tests" / "fixtures" / "scope-corpus"
    if not fixture.is_dir():
        print(f"scope-cards --self-test: SKIP (no fixture corpus at {fixture})")
        return 0
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "corpus"
        shutil.copytree(fixture, work)
        ns = argparse.Namespace(grade=6, lessons=None, corpus=str(work), exam=None)
        if cmd_draft(ns) != 0:
            fails += 1
            print("  FAIL draft")
        cards = sorted((work / "maths" / "grade-06" / "scope-cards").glob("*.yaml"))
        if len(cards) != 2:
            fails += 1
            print(f"  FAIL expected 2 cards, got {len(cards)}")
        snap = {p.name: p.read_bytes() for p in cards}
        if cmd_draft(ns) != 0 or any(p.read_bytes() != snap[p.name] for p in cards):
            fails += 1
            print("  FAIL rerun is not byte-identical")
        yaml = import_yaml()
        for p in cards:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            doc["curated"] = {"status": "drafted", "not_taught": [
                {"concept": "absent-thing", "why": "not in the fixture lesson",
                 "probes": ["qq-not-a-word"]},
                {"concept": "absent-other", "why": "also absent from the fixture lesson",
                 "probes": ["ww-not-a-word"]}],
                "prerequisites": [], "difficulty_hooks": [
                    {"level": "M", "hook": "hook one"}, {"level": "H", "hook": "hook two"}]}
            p.write_text(dump_card(doc), encoding="utf-8")
        if cmd_check(ns) != 0:
            fails += 1
            print("  FAIL check on curated fixture cards")
    print("scope-cards --self-test: " + ("PASS" if not fails else f"{fails} FAIL"))
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="scope-cards.py",
        description="lesson scope cards: draft from corpus lessons, then check curated cards")
    ap.add_argument("command", nargs="?", choices=["draft", "check"])
    ap.add_argument("--grade", type=int, help="grade number (e.g. 6 → maths/grade-06)")
    ap.add_argument("--exam", choices=["ol"], help="exam scope — only 'ol' is defined, and it is refused until plan OD-3")
    ap.add_argument("--lessons", help="draft only these lesson numbers, e.g. 1,7")
    ap.add_argument("--corpus", help="corpus checkout (else VIBHAGA_CORPUS, else sibling Vibhaga-Maths-Corpus)")
    ap.add_argument("--self-test", action="store_true", help="offline smoke run over tests/fixtures/scope-corpus")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.exam:
        refuse_ol(resolve_corpus(args))
    if not args.command:
        die("a command is required: draft | check")
    if args.grade is None:
        die("--grade N is required for draft/check")
    if args.command == "draft":
        return cmd_draft(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
