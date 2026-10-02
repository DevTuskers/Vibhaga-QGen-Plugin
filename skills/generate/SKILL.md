---
name: generate
description: Generate new practice questions FROM A LESSON (no source paper) through the Agent Question Playground — read the lesson's corpus Markdown through your own checkout (never an API), check what already exists for dedup and style, author stems / parts / constructed figures / answers with the S4–S8 skills, compile the batch with `tools/build-staged.py`, validate server-side until clean, then save and publish with `tools/playground-publish.py`, where every row lands FLAGGED and hidden from students until a human marks it reviewed, and prove what landed by direct SQL. Use when asked to generate, write, create or author questions for a lesson, topic or grade, to "fill a lesson with practice questions", or to run or resume a playground session. Not for onboarding an existing PDF paper — this plugin only generates.
argument-hint: "[grade] [lesson number or name] [how many questions]"
---

# Generate questions from a lesson (playground)

> Moved from Vibhaga-Docs `.devin/skills/generate-lesson-questions` @08c09a9; paper-only sections removed
> (see docs/MIGRATION.md). W7 will rewrite this skill as the full orchestrator.
>
> Runs so far: two playground runs through the source skill (2026-09-27, 2026-09-29 — ids kept in the
> private plan logbook). Their distilled lessons are already in the sections below: a lesson that teaches
> angle types *without degrees* demands comparison-with-a-right-angle reasoning; measure label↔canvas-edge
> clearance, not only label↔stroke; a constructed claim set must take its ratios from the **stem** (a drawn
> 1.5:1 rectangle passed Audit A for a 5:2 stem — the stem-ratio check in `tools/audit-claim-set.py` now
> refuses it).

Written for Phase 6 of
[`plans/2026-09-25-agent-question-playground.md`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/plans/2026-09-25-agent-question-playground.md). Cross-cutting traps live in
[`docs/TRAPS.md`](../../docs/TRAPS.md).

> **Decision:** [`0018`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/decisions/0018-agent-question-generation-playground.md) (paperless playground), on top of
> [`0008`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/decisions/0008-agent-driven-question-onboarding.md) PD-3, [`0009`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/decisions/0009-review-flag-write-controls.md),
> [`0013`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/decisions/0013-student-surface-carries-no-review-status.md) and
> [`0014`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/decisions/0014-agent-bulk-writes-use-the-admin-api.md). The contract is
> `Vibhaga-API/api/openapi.admin.yaml` § `/v1/admin/playground/*`. If this file and the contract disagree, **the contract
> wins**. Fix this file in the same PR.
>
> ⭐ **The flagged-only truth, said once:** every playground publish writes `needs_human_review = true`, whoever authored
> it, agent or human admin (0018 PD-3 / OD-2). A published playground question is **not served to students** until a human
> clicks "Mark reviewed" on the Admin `/generate` page. Nothing in this skill, and nothing the tool can do, lowers that
> flag.

**Tool:** [`tools/playground-publish.py`](../../tools/playground-publish.py). Run `--help` for the
subcommands, and `--self-test` for the offline suite.
**Chains:** [`author-question-text`](../author-question-text/SKILL.md) (S4) ·
[`structure-question-parts`](../structure-question-parts/SKILL.md) (S5) ·
[`read-figure-claim-set`](../read-figure-claim-set/SKILL.md) (S6a, §2.3 constructed channel) ·
[`draw-and-verify-question-vdd`](../draw-and-verify-question-vdd/SKILL.md) (S6b) ·
[`author-question-answers`](../author-question-answers/SKILL.md) (S8) ·
the `qgen-critic` agent ([`agents/qgen-critic.md`](../../agents/qgen-critic.md)) — run by a separate agent after publish, before flags clear.

---

## 0. Non-negotiables (read first)

1. **The lesson comes from your own checkout of `Vibhaga-Maths-Corpus`, never from the API.** There is no lesson-content
   endpoint (0018 PD-4), and there must not be one. Resolve the checkout via `VIBHAGA_CORPUS` or the sibling
   `../Vibhaga-Maths-Corpus` of this plugin. Read `maths/grade-06/README.md` (for the grade in scope) first: only
   lessons it lists as published are sources. **If the corpus has no published README for the requested grade, REFUSE
   — do not guess the lesson list. A lesson also needs a scope card** in `maths/grade-NN/scope-cards/` (made by
   [`scope-cards`](../scope-cards/SKILL.md)) — **a grade or lesson with no scope cards is refused.** Then read the
   lesson file itself, including every figure's `**Description:**`. Never hand-edit the corpus.
2. **Every question stays inside the lesson, the grade and the syllabus.** A question that needs a later lesson's idea is
   out of scope, even if the maths is right. Tag it with that lesson's `lesson_id` from the live taxonomy (`lessons`
   subcommand), never a guessed uuid.
3. **Dedup before you author, against everything.** `questions list --lesson-id <id> --all` returns **every** row, drafts
   included, flagged or not, papered or paperless (0018 PD-4). A stem that is the same exercise with the numbers changed
   is a duplicate of the textbook's own exercise, or of an existing question. Change the *task*, not only the numbers.
4. **Every staged question carries `ingestion_metadata.needs_human_review: true`, and no per-question `exam` key.** The
   tool refuses both before a save (0014 PD-1 guard-rail 4; 0018 PD-6: scope lives on the session row).
5. **Record ids before they matter (T9).** The session id goes into the ledger the moment `session create` returns. The
   publish set goes in before the first publish request. There is no delete in v1 (0018 PD-8 / OD-5). An id you did not
   record can only be recovered by a `source_batch_id` search, and only if you still know the session.
6. **Prove rows by direct SQL, never only through the API.** Hyperdrive's query cache can be ~75 s stale (**T5**,
   including its 2026-09-27 addendum). The tool's read-back 2 (T77 plus provenance) does this. Quote its totals line.
7. **The tool never lowers a flag.** `clear-review` and `unflag-review` refuse by design: signing content off is a human
   act in the headed UI (0014 PD-2, 0009). `unpublish` sets the row back to `draft`. It deletes nothing.
8. **An archived session is read-only.** Every write gets `409 batch_archived` except the re-open itself
   (`PATCH {status: "active"}`), and the tool refuses first. The tool has no re-open subcommand. Re-open on the Admin
   `/generate` page if you really mean to continue it. Otherwise create a new session.

## 1. Stable facts — and how to re-verify them

| Fact | Where to re-verify |
|---|---|
| A "session" (API) is a `question_batches` row (DB). Its staged doc is R2 `playground/<id>/questions.json`. Published rows carry `source_batch_id = <id>` and `source_paper_id IS NULL`. | plan §Schema; `Vibhaga-DB/src/vibhaga_db/models.py` `QuestionBatch` |
| Session create: the schema requires only `name` and `medium`. The server also enforces `grade` XOR `exam`, a catalogued `subject` for the scope (government exams have none), and that every `lesson_id` exists in scope. `lesson_ids` defaults to `[]` and is intent only (OD-4). The tool requires at least one lesson. | `openapi.admin.yaml` `PlaygroundSessionMeta` + POST description |
| `PUT …/questions` is a whole-doc replace. A save may **raise** the flag but never lower it. A client `exam` is stripped. | `openapi.admin.yaml` PUT description; `Vibhaga-API/api/src/shared/staged-question.ts` |
| `validate` errors: shape, duplicate `question_number`/ids, `is_multipart` agreement, the 2-level cap, invalid VDD, refused paints, a missing `a11y.title`, and nonexistent or out-of-scope lessons. A missing `a11y.description` is only a **warning**. | `openapi.admin.yaml` `/playground/validate`, `ValidateReport` |
| Publish forces the flag on every row and re-validates the chosen questions (`400 validation_failed`). `dry_run` returns `signatures_at_risk`. Omitting `question_ids` publishes **all**, so the tool always sends them. | `openapi.admin.yaml` `/sessions/{id}/publish` |
| ⚠️ **The publish response does NOT write the raised flag back into the staged doc**; only the flag verbs mirror (`staged_doc_updated`). The tool re-PUTs the doc after each publish and reads it back (**T142**). | T142 |
| Student read path: `SERVABLE` excludes flagged rows, draft rows **and** non-solvable rows (no verified answer), so a flagged question is absent from `/v1/questions`. Absence alone does not prove the flag; the SQL read-back does. | 0013 PD-3; `Vibhaga-API/api/openapi.yaml` `/v1/questions` |
| `questions list` returns summaries: `stem_excerpt` is the first 240 characters of `question_text`, not the stem. | `openapi.admin.yaml` `PlaygroundQuestionSummary` |

## 2. The loop

Work in `wt/<topic>/` (umbrella worktree rule). Keep a run ledger there: the tool's `--ledger` JSON, plus your own
notes. Every command below reads credentials from `Vibhaga-Admin/.env.local` at run time and never prints them.
`T=tools/playground-publish.py` (run from the plugin root).

1. **Read the scope card, then the lesson.** From the corpus checkout, open the lesson's scope card first
   (`maths/grade-NN/scope-cards/<NN>-<slug>.yaml` — [`scope-cards`](../scope-cards/SKILL.md) drafts and checks them).
   The card *is* your scope statement: `sections` + `summary` + `vocabulary` + `not_taught` say what the lesson does
   and does not teach; `worked_examples` + `exercises` are the don't-copy list; `figure_kinds` say which figures you
   could reuse as a *kind* of figure; `difficulty_hooks` anchor the R/M/H rubric. **A grade or lesson with no scope
   cards is refused** — never author from the lesson file alone. Then read the lesson file itself, including every
   figure's `**Description:**`. Write the scope statement into your notes.
   - **O/L work:** an O/L scope card is assembled from the grade-10 + grade-11 *scope cards* (not the lesson
     files) via the O/L mapping in Vibhaga-Docs `lessons/ol/mathematics.md`, and an O/L question is tagged
     with the O/L lesson ids (owner ruling 2026-09-29). Scope cards live in the PRIVATE corpus at
     `maths/grade-NN/scope-cards/<NN>-<slug>.yaml` and `maths/ol/scope-cards/`; **O/L is refused until BOTH the
     G10 and G11 card sets exist** (composition itself is plan OD-3 — the tool refuses). Never copy a scope card
     into this public repo.
2. **Find the taxonomy and what exists.**
   - `python3 $T lessons --grade 6 --subject Mathematics` gives the `lesson_id`.
   - `python3 $T questions list --lesson-id <id> --all --out existing.json` gives every row already tagged to the lesson.
     The list gives 240-character excerpts. For any row that looks close to a planned question, read the full stem and
     answers with `questions show <id>` before you judge it. Read for duplicates and for house style (Sinhala register,
     markup, answer length).
   - For a dedup signal the API cannot give (e.g. rows tagged with no lesson), use a direct `SELECT` on `questions`
     filtered by scope, never a cached API read.
3. **Plan 3–N questions** that cover *different* skills of the lesson. Write one line each in your notes: skill tested ·
   why it is not a duplicate · whether it needs a figure.
4. **Author each question** as a `content.yaml` spec, then compile it:
   `python3 tools/build-staged.py content.yaml --out staged.json`. The spec keeps human authoring in YAML (lesson keys,
   figure keys, bare part labels) and the builder emits the staged doc — deterministic uuid5 ids, `question_number` as a
   JSON number, explicit `is_multipart`/`sort_order`, `text_sinhala` nulls, the flag on every question, no `exam`
   anywhere — and refuses ambiguous input (see `tools/build-staged.py --help`). The item shape is the onboarding staged
   doc minus `exam`:
   - **Stem:** follow [`author-question-text`](../author-question-text/SKILL.md) §3 (markdown, `$…$`/`$$…$$`, never
     Sinhala inside KaTeX `\text{}`) and §1a, which covers authoring a stem where nothing is printed. That is always
     the case here. ⚠️ **The stem goes in `question_text`, in the session's medium.** For `medium=sinhala` that means the
     Sinhala stem. Leave `question_text_sinhala` null: `0003` PD-C removed its box from the Admin UI, so no human can see
     or repair it ([`author-question-text`](../author-question-text/SKILL.md) §0.6; no prod rows use it). Part text
     goes in `sub_questions[].text`, also in the medium's language.
   - **Structure:** follow [`structure-question-parts`](../structure-question-parts/SKILL.md) §0 and §2.
     `build-staged.py` mints the uuids for you; parts go in `sub_questions`, depth capped at 2, labels bare (`a`, `i` —
     the builder refuses `(a)`/`a)`/`a.`) and unique among siblings (two same-named parts collide on one id).
     ⚠️ **Ids are keyed on `id_seed` + `n` + the label path** — after a first publish keep all three stable:
     renumbering or relabelling mints NEW uuids and publish writes NEW rows that orphan the published ones
     (there is no rename).
   - **Figure** (only where the question needs one): if it matches one of the nine templates in
     [`figure-templates`](../figure-templates/SKILL.md), `tools/vdd_templates.py` builds it and emits the
     claim set itself — the stem's numbers drive the drawing and the claims (T-QG-2). Otherwise: a
     playground figure is never printed, so the claim set is
     `channel: constructed` ([`read-figure-claim-set`](../read-figure-claim-set/SKILL.md) §2.3) with a `stem:` header
     carrying the stem text (the audit's stem-ratio check refuses a drawn ratio the stem does not justify). Its
     `source:` names the frame, e.g. *"constructed; frame is the question's own canvas"*. ⚠️ **A question-side
     constructed figure still needs at least one `derive` claim**, because `audit-claim-set.py` check 2c demands one on
     every `constructed` set. §2.3 wrote `derive` for answer-side arithmetic. On the question side, `derive` records the
     **construction arithmetic the figure is built from**: the arm direction of a 130° angle (`derive 180 - 50 = 130`),
     or a side computed from a stated perimeter. Every element you add is `inferred`, with that reason. If a figure has
     nothing derivable (a pure shape to name), do not invent a claim: drop the figure or put the question to the owner.
     Audit it with `python3 tools/audit-claim-set.py`. Then draw it with
     [`draw-and-verify-question-vdd`](../draw-and-verify-question-vdd/SKILL.md) §3 and verify it with §4 and §5.
     `vdd-check.mjs` renders it through the real components at its default widths (320, 375 and 768 px, the student-facing
     set), and angles and ratios are checked numerically against the claim set; label clearance to the canvas edge and
     to strokes is measured in the same render. A real `a11y.title` and
     `a11y.description` are required: the API errors without the title and warns without the description. The
     description must not give away the answer (**T125**).
   - **Answers:** follow [`author-question-answers`](../author-question-answers/SKILL.md) §3 (independent derivation
     plus a genuine second method), §4 (`approach` + `final_answer_latex` only; provenance goes to the ledger, never to
     `approach`) and §5a (where the answer hangs decides whether it is an `answer_id` or a `sub_answer_id` — the builder
     emits the right one per leaf). There is no marking scheme, so every answer is a D3 derivation.
   - **Tags and flag:** `lesson_ids` resolve from your `lessons:` key map to real lesson uuids;
     `ingestion_metadata: {"needs_human_review": true}` is written by the builder.
5. **Create the session** (once):
   `python3 $T session create --name "<what> — G6 <lesson> <date>" --scope grade=6,subject=Mathematics,medium=sinhala --lessons <lesson_id> --ledger ledger.json`.
   Record the printed id in your notes as well.
6. **Validate until clean:** `python3 $T validate <sid> --staged staged.json` (exit 0 means no errors). Fix every error.
   Read every warning, and fix it unless your notes say why it stays.
7. **Save:** `python3 $T doc put <sid> --staged staged.json --ledger ledger.json`. Then `doc get <sid> --out server.json`
   and confirm the server array is the one you meant to save.
8. **Publish, flagged:**
   - `python3 $T publish <sid> --staged staged.json --scope grade=6,subject=Mathematics,medium=sinhala --ids-file ids.json --ledger ledger.json --dry-run --accept-signatures 0`.
     This is the dry-run. Read `signatures_at_risk`: on a new session it is 0.
   - Then run the same command without `--dry-run`. The tool:
     - checks the session is active and that `--scope` equals the session row;
     - checks that staged equals server and every question is flagged;
     - re-validates;
     - writes the ledger;
     - publishes one id per request;
     - re-PUTs the published and flagged doc after each publish (**T142**);
     - reads the doc back, then runs T77 and the provenance SQL (read-back 2);
     - logs out.
   - Exit 0 is the only success. Exit 1 means a read-back mismatch: the run is failed until staged and live agree
     (**T77**).
9. **Close out:** every network subcommand ends by logging out and printing two revocation queries. After the last one,
   run them against the **Admin Auth** project ([Vibhaga-Docs `AGENTS.md`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/AGENTS.md) § Onboarding-tool verification). Then hand the
   session to a **separate** agent running the `qgen-critic` agent in its
   playground mode. Its inputs are the lesson file plus the rows scoped by `source_batch_id`, and it checks
   correctness, fit to the lesson and duplication, not faithfulness to a paper. Leave the questions published and
   flagged. A human clears them.

## 3. What makes a generated question fit

| Check | Fails when |
|---|---|
| In lesson | it needs a concept the lesson does not teach, or a later grade's notation |
| Not a copy | it is a textbook exercise or an existing row with only the numbers changed |
| Self-contained | a student cannot answer it from the stem and figure alone (no "see the table on page 87") |
| Answer right | the second method disagrees, or the figure's measured values contradict the stem |
| Figure honest | the drawing *looks* like the claim but measures differently (S6b §5) |
| Language | the stem is not in the session's medium, or it does not use the lesson's own vocabulary as printed |

## 4. Traps — stories with the catch

- **T142: published, flagged, and the doc says otherwise.** The Phase 5 page showed a flagged question as green
  "Published" after a reload, because the publish response never wrote the OD-2 flag into the staged doc. A hand-rolled
  curl publish repeats this silently. Use the tool, which re-PUTs the doc and reads it back.
- **T5: the API list said it was there.** A questions list read within ~75 s of a write can be stale. Proof is direct
  SQL.
- **T9: the ids are the undo.** Without the ledger, an unpublish needs someone to find the rows by `source_batch_id`
  first. With it, one command does the job.
- **T77: staged and live disagree.** Publish reads the **server** doc, not your file. The tool refuses a publish while
  your file differs from the server doc (run `doc put` first), and T77 compares staged against live afterwards.

## 5. Verify (definition of done, per session)

1. The notes contain the scope statement (§2 step 1), the dedup evidence (`existing.json` row count and the stems you
   compared) and one line per question (§2 step 3).
2. `validate` exits 0 on the final staged doc. Every warning is fixed or explained.
3. Every figure has a `channel: constructed` claim set with a `stem:` header, `tools/audit-claim-set.py` passes, and
   `tools/vdd-check.mjs` passes at its default widths.
4. `publish` exits 0. Quote its "published k/n" line, the "read-back 1: staged doc confirms …" line, T77's
   `t77: N question(s) · N comparisons · 0 mismatch(es)` line, and the "provenance: N id(s) · OK" line
   (`source_batch_id` = session, `source_paper_id` NULL, flag true, status published). All must be clean.
5. One direct `SELECT` confirms `verified_by IS NULL` on every answer and sub-answer of the session. Also confirm the
   rows are absent from the student `GET /v1/questions` for the lesson. That is supporting evidence only (see §1: the
   student API also hides non-solvable rows).
6. The revocation counts are 0 and 0 on the Admin Auth project, for the actor that exists there.
7. A separate critic ran `qgen-critic` (playground mode), and every BLOCKER, MAJOR and MINOR
   finding is fixed (republish flagged) or recorded as an owner question.
8. The ledger (session id, question ids) is written into the run's logbook entry.

## 6. Keep this skill alive

The route table in §1 was diffed against `openapi.admin.yaml` on 2026-09-27. When the playground contract changes (new
verb, delete, or a publish that mirrors the flag itself), update §1, §2 and the tool together, and retire T142 if the
server starts writing the flag. Add each run's line under "Runs so far" — without session ids in this public repo.
