# vibhaga-qgen — always-on rules

This plugin generates maths practice questions for vibhaga.lk and publishes them to an Admin
playground session. There is **no source paper**: every number comes from the lesson corpus and the
stem you author. These rules hold in every session that loads the plugin.

## Generation rules
1. **Flagged-only.** Every generated row lands FLAGGED (`needs_human_review = true`) with
   `verified_by` NULL on every answer and sub-answer. Only a human clicking "Go live" in Admin
   clears it. No tool, query or agent lowers a flag or writes `verified_by`.
2. **Lesson content comes only from the corpus checkout**, never from an API. Resolve it as
   `VIBHAGA_CORPUS` env → sibling `<plugin>/../Vibhaga-Maths-Corpus`. No published lesson (or no scope
   card) for the grade → refuse. Never hand-edit the corpus.
3. **Two or more lessons tagged ⇒ each one is used.** At least one part's solution needs a concept
   from each tagged lesson. A tag the working never touches is a defect, not a bonus.
4. **Stay inside the scope card.** Nothing on its `not_taught` list, no later-grade notation.
5. **Prove by SQL, not by the API.** Use `queries.sql` (Q2 post-publish proof, Q3 Auth revocation —
   same merged project, actor asserted to exist AND to be an admin first). Never select token
   values.
6. **Drawn diagram text is simple English, never Sinhala** (ADR 0021 —
   `Vibhaga-Docs/decisions/0021-english-only-diagram-text.md`; TRAPS T-QG-12 supersedes T-S6b-6).
   This includes point letters, labels, text elements, math latex, axis/category/series/value
   titles and units. Undrawn a11y `title`/`description` keep the question's medium.
   Because both media share one diagram, prefer single English letters or standard maths symbols
   explained in the bilingual stems/parts over English prose; this is a recommendation, not a ban.
7. **Bilingual.** Every stem, part text, approach and final is written in English AND Sinhala
   (`*_si` keys); build-staged refuses a missing or copied side; queries.sql Q2b proves both landed.
8. **Student text is laid out for reading.** Stems, part texts, approaches and finals use one
   idea/step per paragraph with a blank line between; put every computation on its own line and
   separate a stem's setup from its task. `run-gates build` runs `tools/check-layout.py`; any FAIL
   stops the build. Owner ruling: 2026-10-13. See
   [`author-question-text` §5](skills/author-question-text/SKILL.md#5-writing-the-stem) and
   [`author-question-answers` §4.1c](skills/author-question-answers/SKILL.md#-41c-lay-the-approach-out-for-a-phone--one-step-per-paragraph).
9. **Plans start from creative signals.** Before sketching a plan, the writer gathers sourced, school-appropriate
   real-world signals by web search and anchors every plan line to one, with a short students/teachers rubric
   ([`creative-signals`](skills/creative-signals/SKILL.md), generate step 2b). Real figures stated as fact are true
   (TRAPS T155). The copy check still runs on every line.
10. **In Sinhala, follow translated technical terms immediately with the English term in brackets**
    (e.g. `වෙන්කිරීම් කුට්ටි (allocation blocks)`), even for standard curriculum terms. This covers
    IT/ICT, hardware/peripherals, data storage/systems, calculator/device interfaces and engineering.
    For everyday IT terms and acronyms use English or natural transliteration (mouse / මවුසය, RAM),
    never outdated, unnatural or overly literal Sinhala.
11. **Independent critics.** Use a fresh context with paths only (T25), never a self-review in the
    authoring context. Devin cloud follows [Devin runtime](skills/generate/devin-runtime.md).
    Other hosts (Gemini CLI, Claude Code, Codex, …) use native subagents or fresh conversations
    and can run content and diagram critics concurrently when supported.

## Session discipline
- **Session names follow the standard** (owner ruling 2026-10-15): `G<grade> Maths · <Easy|Medium|Hard> · <N>Q · <d Mon YYYY, h:mm AM/PM>`
  — `·` is U+00B7 with a space each side, the time is the creation time in Asia/Colombo
  (`TZ=Asia/Colombo date '+%-d %b %Y, %-I:%M %p'`), and there is **no medium indicator**, no lesson
  list and no extra words — e.g. `G8 Maths · Easy · 10Q · 15 Oct 2026, 3:05 PM`. A misnamed session
  is renamed via the session PATCH (`name` field), never recreated.
- **One image per `read` call.** An image is seen only if the result shows it. Log what you saw at
  once; never re-read an image already confirmed. A read that came back without the image may be
  retried once, alone; after that, change approach.
- **Lean by default.** Follow the generate skill's Quick run; no figures unless a question needs one.

## Public repo — never commit production content
- No real question text, corpus or scope-card text, real UUIDs, email addresses, or anything that
  identifies the Supabase projects (hosts, refs) or workers.dev hosts. Fixtures use synthetic
  placeholders (`00000000-0000-4000-8000-0000000000NN`, `auth.example.test`).

## Configuration — resolution order, never absolute paths
- `Vibhaga-Admin` checkout: `--admin PATH` flag → `VIBHAGA_ADMIN` env → sibling
  `<plugin>/../Vibhaga-Admin`.
- Admin credentials: `Vibhaga-Admin/.env.local` (or `VIBHAGA_ADMIN_ENV`), read at runtime, never
  printed.
- Lesson corpus: `VIBHAGA_CORPUS` env → sibling `<plugin>/../Vibhaga-Maths-Corpus`.

## Offline test commands
Before every commit — doc lint plus only the tests reached by the files changed since `origin/main`:
```
PYTHONDONTWRITEBYTECODE=1 VIBHAGA_ADMIN_ENV=/nonexistent/offline-test-only \
  python3 tools/check-suite.py --quick
```
Before every push and before asking for a merge — the full suite (parallel on every core;
`--jobs 1` runs it serially):
```
PYTHONDONTWRITEBYTECODE=1 VIBHAGA_ADMIN_ENV=/nonexistent/offline-test-only \
  python3 tools/check-suite.py
```

## Layout
`tools/` scripts · `tests/` unittest + node --test suites · `tests/fixtures/` synthetic fixtures ·
`skills/` slash-command skills · `agents/` subagents · `queries.sql` · `docs/MIGRATION.md`,
`docs/TRAPS.md`.
