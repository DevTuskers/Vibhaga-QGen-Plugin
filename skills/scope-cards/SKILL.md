---
name: scope-cards
description: >-
  Draft and curate the per-lesson SCOPE CARDS that live in the private Vibhaga-Maths-Corpus at
  `maths/grade-NN/scope-cards/<NN>-<Slug>.yaml`. A card is the machine-checkable statement of what a
  published lesson teaches — sections, vocabulary, worked examples, exercises, activities, figures,
  summary — plus a hand-curated block saying what it does NOT teach, its prerequisites and its
  difficulty hooks. The `generate` skill reads the card before it reads the lesson; a grade or lesson
  with no passing cards is refused. Use when asked to make, update or check scope cards for a grade
  or lesson, or before generating questions for a grade that has none. Card content never enters
  this public repo.
argument-hint: "[grade] [lesson numbers]"
---

# Lesson scope cards

A scope card lives next to the published lessons in the **private** corpus
(`maths/grade-NN/scope-cards/<NN>-<Slug>.yaml`, plan OD-1), one per published lesson. It is what
`generate` reads before it reads the lesson: the scope statement, the don't-copy list and the
difficulty anchors in one file.

⚠️ **The card stays in the corpus.** Card text is corpus content — never copy it into this public
repo (AGENTS.md hard rule). The tool and this skill refer to the card; they never embed it.

## The file

```yaml
schema_version: 1
grade: 6            # + subject / medium / lesson_number / titles / syllabus_refs / term / periods
source: {file: lessons/<NN>-<Slug>.md, sha256: <hex>}   # pinned to the lesson file
generated:          # tool-owned — `draft` rewrites it every time; never hand-edit
curated:            # agent-written — `draft` preserves it, `check` verifies it
  status: todo | drafted | reviewed
  not_taught: [{concept, why, probes: [...]}]
  prerequisites: [{lesson, why}]
  difficulty_hooks: [{level: M|H, hook}]
```

## Commands (run from the plugin root)

```
python3 tools/scope-cards.py draft --grade 6 [--lessons 1,7] [--corpus PATH]
python3 tools/scope-cards.py check --grade 6 [--corpus PATH]
python3 tools/scope-cards.py --self-test
```

Corpus resolution: `--corpus` → `VIBHAGA_CORPUS` → sibling `../Vibhaga-Maths-Corpus`.
`draft` rebuilds `generated` and `source` for every selected lesson and preserves any existing
`curated:` block (a new card gets `status: todo`). Re-running it on an unchanged corpus is a
byte-identical no-op.

## Curating a card

Open the lesson file and fill `curated:` for each `todo` card:

- **`status: drafted`** once your curation is written; `reviewed` only after a human or fresh-eyes
  pass. `check` refuses `todo`.
- **`not_taught`** — 2–5 concepts a question-writer might reach for that the lesson does NOT teach.
  Each needs ≥1 `probe`: a string that *would* appear in the lesson if the concept were taught —
  the textbook's own Sinhala term, and a symbol or English form where relevant (e.g. degree measure
  → `°`). `check` fails when any probe occurs in the lesson file (NFC-normalized, ASCII
  case-insensitive; whole-word matching for pure-English probes so `ton` can't hit `button`): a
  probe that hits means the concept is probably taught — re-read the lesson and
  fix the item, never swap in a weaker probe. If no probe can honestly be absent, drop the item.
- **`prerequisites`** — earlier lessons whose concepts this lesson's worked examples actually use:
  `grade-06/05` form for the same grade (must be an existing, lower-numbered card) or
  `grade-NN:<free text>` for an earlier grade. An empty list is fine.
- **`difficulty_hooks`** — 2–4 items, `level: M` or `H`, each naming the non-routine move this lesson
  makes possible (e.g. compare an angle with a right angle — not with a degree figure). These anchor
  the R/M/H difficulty rubric in the plan's appendix:
  [plans/2026-09-29-question-generation-plugin.md](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/plans/2026-09-29-question-generation-plugin.md).

Then **`check --grade N` must exit 0** — one line per card plus a
`check: N card(s) · k passed · 0 failed` totals line. It fails on a stale `source.sha256`, a hand
edit inside `generated`, a `todo` status, a probe that occurs in the lesson, a bad prerequisite, and
wrong hook count or level.

## Refusals (exit 2)

- no corpus checkout — resolve with `--corpus` or `VIBHAGA_CORPUS`;
- a grade with no `maths/grade-NN/README.md` + `manifest.yaml` — the grade is not published;
- a manifest `included_lessons` entry with no lesson file;
- `--exam ol` — O/L scope needs complete grade-10 AND grade-11 card sets, and composition is plan
  OD-3 (not implemented); the refusal message says which is missing.

## How `generate` uses a card

`generate` §2 step 1 reads the card first:

- **scope statement** = `sections` + `summary` + `vocabulary` + `not_taught`;
- **don't-copy list** = `worked_examples` + `exercises` (headings, anchors, item excerpts);
- **difficulty rubric anchors** = `difficulty_hooks`, read against the R/M/H rubric in the plan
  appendix linked above;
- `source.sha256` pins the lesson version the curation was checked against — `check` re-verifies it.
