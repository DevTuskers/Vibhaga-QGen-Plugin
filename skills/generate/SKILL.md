---
name: generate
description: The orchestrator for generating new practice questions FROM A LESSON (no source paper) through the Agent Question Playground, as ONE ordered flow — scope cards (and, for a grade with no named lesson, a coverage snapshot that picks the thinnest lessons) → a one-line-per-question plan → the lead-authored `content.yaml` → figure templates → visual-check → validate → `doc put` → visual-check `--session` → publish FLAGGED with `tools/playground-publish.py` → SQL proof (queries.sql Q2 + Q3 via `tools/sql-proof.py`) → a fresh `qgen-critic` until SATISFIED → logbook line. Every row lands flagged and hidden from students until a human marks it reviewed. Use when asked to generate, write, create or author questions for a lesson, topic or grade, to "fill a lesson with practice questions", to fill the least-covered lessons of a grade, or to run or resume a playground session. Not for onboarding an existing PDF paper — this plugin only generates.
argument-hint: "[grade] [lesson number or name] [how many questions]"
---

# Generate questions from a lesson — the orchestrator

## Quick run (lean, ~10 questions — target 2–3 ACUs; owner ruling 2026-10-20)

This run is self-contained: read **this section and AGENTS.md**; use its linked rules and steps as needed.
Open an S4–S8 skill only when a step needs a rule you do not know (a figure or a failing gate).
`T=tools/playground-publish.py`, `A=wt/<topic>/actor`. A ~10-question run targets **2–3 ACUs**; start the
generation session and its one critic in **Normal** mode. No figures unless a question needs one. Never re-read
a skill or corpus file already read; allow one `build` + one `ship` per fix round.

1. `python3 tools/qgen-setup.py` → `export VIBHAGA_ADMIN_ENV=/dev/shm/qgen-admin.env` (one command; prints names only).
2. `python3 $T coverage --grade <g> --subject Mathematics --pairs --out $A/coverage-before.json` → pick the lessons
   the request needs (default 2–3) — None/Thin with room left; prefer a strong scope card
   (`python3 tools/scope-cards.py brief …`). Apply the [Room left and stop rule](#room-left-and-stop-rule).
3. Read each chosen lesson's full [Copy check](#copy-check) sheet with `python3 tools/dedup-sheet.py --grade <g>
   --card <key>=<NN> --out $A/dedup-sheet.md`. Plan 10 one-liners → `$A/plan-items.yaml` → `python3 $T similar
   --grade <g> --items $A/plan-items.yaml --out $A/similar-plan.json`; each line names its closest item and why
   the **task** differs. Re-run `python3 tools/dedup-sheet.py --grade <g> --card <key>=<NN>
   --plan $A/plan-items.yaml --similar $A/similar-plan.json --out $A/dedup-sheet.md` to pair every plan line
   with its neighbours before the critic. Apply [Difficulty bands](#difficulty-bands).
   See [T143–T154](../../docs/TRAPS.md). Tips: Hard Q stems may leave R only as part (a) and must end on an H
   leaf; `number_line` takes only non-negative endpoints and needs every drawn number (incl. step `1`) written in
   the stem — write `$0, 1, 2, \ldots, 8$`; a maths-only `approach_si` identical to English fails Q2b
   (`part_approach_no_sinhala`) — always add a Sinhala sentence to the approach.
3b. **Plan critic** — follow [Plan-stage critic](#plan-stage-critic): one fresh `qgen-critic` session, Normal
   mode, `Mode: plan`; paths only. Replace every REPLACE line, then rerun `similar` and the dedup sheet. A second
   plan round is only for changed lines; then the stop rule applies. Create the session only when every line is OK.
4. Write `$A/content.yaml` (bilingual, readable layout, required `difficulty: easy|medium|hard`; questions may override it; `check:` on every leaf). **No figures by default**; only
   add one when the question cannot be asked without it, and use a template (`figure-templates`).
5. `python3 tools/run-gates.py build $A --medium <medium> --grade <g> --card <key>=<NN>`
   → exit 0. Rubric defaults from content difficulty (easy→easy, medium→medium, hard→medium-hard); a mixed batch (`difficulty: medium` + per-question `difficulty: hard`) defaults to `--rubric by-band`, which checks each question against its own band (Hard: R only as (a), last leaf H); `--rubric` overrides. Build also runs warning-only `si-style.py`; a figureless run skips figure stages.
6. `session create --name "<standard name>" --scope "grade=<g>,subject=Mathematics,medium=<medium>" --lessons <ids> --difficulty <content band>
   --ledger $A/ledger.json` → `run-gates.py ship …` (takes ~5 min for 10 questions; run in the background, not
   under a short timeout) → `sql-proof.py q2 <sid> --expected 10` (`q2: ok`, `q2b: ok`) →
   `embeddings-refresh --grade <g> --subject Mathematics`.
7. **One** fresh `qgen-critic` session for all 10, **Normal** mode, paths only. Fix BLOCKER/MAJOR; MINORs only if
   one-line, otherwise owner notes. **Sinhala-fluency MINORs are must-fix: apply the critic's rewrite.** Round 2
   uses a fresh critic with `Previous report:`, changed questions only. See [Sinhala fluency](../../agents/qgen-critic.md).
8. Coverage after, logbook line, report in plain English.

Authoring lessons from earlier runs (see [T143–T154](../../docs/TRAPS.md)):
- Sinhala key terms come from the lesson (T143); a stem must not give away what a part asks (T144).
- Vary part patterns (T145); `check:` must compute from the question (T146).
- Keep names outside maths spans (T147); shared maths-only Sinhala is stored once (T148).
- Keep yes/no answers in their own paragraph (T149); keep units in Sinhala prose or shared maths (T150).
- Keep Sinhala words outside maths spans (T151); provide medium-appropriate figure descriptions that do not give answers (T152).
- Count available figure cells before asking for more (T153).

Generation history: [docs/MIGRATION.md](../../docs/MIGRATION.md#generate-skill-history-2026-10-21). Cross-cutting traps:
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
> clicks **Go live** on the Admin `/generate` page. Nothing in this skill, and nothing the tools can do, lowers that
> flag.

**Tools:** use the existing commands; never fork them. Each authoring step links to its rule skill.

---

## 0. Non-negotiables (read first)

1. **The lesson comes from your own checkout of `Vibhaga-Maths-Corpus`, never from the API.** There is no lesson-content
   endpoint (0018 PD-4), and there must not be one. Resolve the checkout via `VIBHAGA_CORPUS` or the sibling
   `../Vibhaga-Maths-Corpus` of this plugin. Read `maths/grade-NN/README.md` first: only lessons it lists as published
   are sources. **No published README for the grade → REFUSE; do not guess the lesson list. A lesson also needs a scope
   card** in `maths/grade-NN/scope-cards/` ([`scope-cards`](../scope-cards/SKILL.md)) — **a grade or lesson with no
   scope cards is refused.** Never hand-edit the corpus.
2. **Every question stays inside the lesson, the grade and the syllabus** — nothing on the card's `not_taught`, no
   later-grade notation. Two or more lessons tagged ⇒ each is used by at least one part's solution (AGENTS rule 3).
   Tag with the `lesson_id` from the live taxonomy (`lessons` subcommand), never a guessed uuid.
3. **Dedup before you author, against everything.** Apply [Copy check](#copy-check). `questions list --lesson-id <id>
   --all` returns every tagged row, including drafts, flagged, papered or paperless (0018 PD-4). `similar` also
   searches untagged rows and other lessons. Run it before authoring and critic Q4e after publish; scores only rank,
   so the verdict is yours and the critic's.
4. **Every staged question carries `ingestion_metadata.needs_human_review: true`, and no `exam` key.** `build-staged`
   writes the flag; `playground-publish` refuses both before a save (0014 PD-1 guard-rail 4; 0018 PD-6).
5. **Record ids before they matter (T9).** The session id goes into the ledger the moment `session create` returns; the
   publish set is written to the ledger before the first publish request (the tool does it). There is no delete for an
   agent: Admin's "Delete permanently" is an owner act. An unrecorded id is recoverable only by `source_batch_id`.
6. **Prove rows by direct SQL, never only through the API.** Hyperdrive's query cache can be ~75 s stale (**T5**).
7. **No tool lowers a flag.** `clear-review` and `unflag-review` refuse by design: sign-off is a human act in the headed
   UI (0014 PD-2, 0009). `unpublish` sets the row back to `draft`. It deletes nothing.
8. **An archived session is read-only.** Every write gets `409 batch_archived` except the re-open
   (`PATCH {status: "active"}`), which the tool does not offer. Re-open on Admin `/generate`, or create a new session.
9. **The critic gets paths, never hints, never actor files (T25).** Keep every actor artefact where the critic is not
   pointed (§2 layout).
10. **Production runs never repair tools.** On tool friction mid-run (a refusal you route around, a flag that is
    missing, a gate that skipped), write ONE line to `wt/<topic>/FRICTION.md` — `symptom · workaround · suspected
    fix` — and continue with the workaround. Tool fixes land in a separate tooling session and their own PR.
11. **Blueprint variants: at most one per batch** (owner ruling 2026-10-03). A question family reused with new
    numbers counts as distinct across sessions but never twice in one session — vary the task, not only the digits
    (precritic-lint `--existing` watches for exactly this).

## 1. Stable facts — and how to re-verify them

| Fact | Where to re-verify |
|---|---|
| A "session" (API) is a `question_batches` row (DB). Its staged doc is R2 `playground/<id>/questions.json`. Published rows carry `source_batch_id = <id>` and `source_paper_id IS NULL`. | plan §Schema; `Vibhaga-DB/src/vibhaga_db/models.py` `QuestionBatch` |
| Session create: the schema requires only `name` and `medium`. The server also enforces `grade` XOR `exam`, a catalogued `subject` for the scope, and that every `lesson_id` exists in scope. `lesson_ids` is intent only (OD-4). The tool requires at least one lesson. | `openapi.admin.yaml` `PlaygroundSessionMeta` + POST description |
| `PUT …/questions` is a whole-doc replace. A save may **raise** the flag but never lower it. A client `exam` is stripped. | `openapi.admin.yaml` PUT description; `Vibhaga-API/api/src/shared/staged-question.ts` |
| `validate` errors: shape, duplicate `question_number`/ids, `is_multipart` agreement, the 2-level cap, invalid VDD, refused paints, a missing `a11y.title`, nonexistent or out-of-scope lessons. A missing `a11y.description` is only a **warning**. | `openapi.admin.yaml` `/playground/validate`, `ValidateReport` |
| Publish forces the flag on every row and re-validates the chosen questions (`400 validation_failed`). `dry_run` returns `signatures_at_risk`. Omitting `question_ids` publishes **all**, so the tool always sends them. | `openapi.admin.yaml` `/sessions/{id}/publish` |
| `questions list` returns summaries: `stem_excerpt` is the first 240 characters of `question_text`. | `openapi.admin.yaml` `PlaygroundQuestionSummary` |
| `build-staged` ids are uuid5 of `id_seed` + `n` + the label path. Renumbering or relabelling after a publish mints NEW rows and orphans the published ones (no rename). | `tools/build-staged.py` docstring |

## 2. The flow

### Who does what

| Step | Owner | Why |
|---|---|---|
| 1 scope statement · 2 dedup judgment · 3 plan | **lead** | judgment: what the lesson teaches, what counts as a copy |
| 4 `content.yaml` — stems, parts, answers, figure specs (which template, which stem numbers) | **lead** | the content *is* the product; a delegated stem or answer is unreviewed authorship |
| 5–6 `run-gates.py build` · 7 session create · 8–11 `run-gates.py ship` · 12 pre-critic lint FAILs | mechanical (delegable: give exact commands and the run dir; ask for exit codes + the quoted lines) | each is one command whose exit code is the verdict |
| 6b the contact sheet look | **lead** | the six metric rules miss wrong-edge labels, legibility, the wrong arc (visual-check "LOOK") |
| 13 critic spawn, finding triage, R/M/H comparison · 14 fix decisions · 15 logbook line | **lead** | independence and judgment; the critic is not told what you doubt |

### Run layout (set once)

```
wt/<topic>/actor/     content.yaml · figures/ · specs/ · staged.json · ids.json · ledger.json · notes.md · RUN.md
wt/<topic>/vc/        visual-check mode-1 output (report.json + PNGs) — the critic IS pointed here
wt/<topic>/vc-session/ visual-check mode-2 output
wt/<topic>/critic/    critic reports r1.md, r2.md … and its rows/ — never the actor dir
```

Run every command from the plugin root. `T=tools/playground-publish.py`, `A=wt/<topic>/actor` (absolute paths in
practice). ⚠️ **Running the plugin from a worktree** (`wt/qgen-plugin-*`) breaks the sibling resolution: export
`VIBHAGA_ADMIN`, `VIBHAGA_WEB` and `VIBHAGA_CORPUS` to the real checkouts, and `VIBHAGA_ADMIN_ENV` to
`Vibhaga-Admin/.env.local` — markdown-gate, vdd-check and visual-check otherwise SKIP or fail to start, and pass the
same two checkout paths in the critic's spawn prompt.

### The steps

1. **Read the scope card, then the lesson.** `python3 tools/scope-cards.py brief <NN> --grade <g>` prints the
   ~80-line brief for the card — sections, vocabulary, the `phrases` term bank, worked examples, exercises,
   activities, `figure_kinds` and the whole curated block. The card *is* the scope statement: `sections` + `summary`
   + `vocabulary` + `not_taught` say what is and is not taught; `phrases` is the mined bank of the lesson's own
   language (emphasis terms, section-title words, recurring words — grade-wide document frequency keeps the
   lesson-common filler out) — write stems in it, and expect `precritic-lint.py` to warn when a tagged question
   uses none of it; [Copy check](#copy-check) is the don't-copy list; `figure_kinds` are reusable
   *kinds* of figure; `difficulty_hooks` anchor R/M/H. Then open the lesson file **only at the sections and anchors
   the plan uses** — `grep -n` the card's `source.file` for the section headings and each figure's
   `**Description:**` — never read it whole. Write the scope statement into `notes.md`.
   - **O/L:** composed from the G10 + G11 *scope cards* via Vibhaga-Docs `lessons/ol/mathematics.md`, tagged with O/L
     lesson ids (owner ruling 2026-09-29). **Refused until BOTH card sets exist** (plan OD-3). Never copy a card into
     this public repo.
2. **Coverage, taxonomy and what exists.** First the snapshot: `python3 $T coverage --grade <g> --subject Mathematics
   --pairs --out $A/coverage-before.json` (read-only; every taxonomy lesson listed, thinnest first, `None` = 0 rows,
   `Thin` = 1..`--thin` (default 2); `flagged` = still awaiting review, hidden from students; `pairs` = two-lesson
   cells the lesson sits in). Add `--status all` and `--needs-human-review false` runs when the student-visible picture
   matters — the default `published` view counts flagged rows too. If the default view says `None 0 · Thin 0` but the
   ask wants None/Thin lessons, re-run with `--thin <lowest count present>` (e.g. `--thin 3`) and say in the logbook
   line which threshold picked the lessons. **When the ask names a grade but no lesson, the
   coverage picks:** the lessons the request needs (default 2–3), preferring `None`/`Thin` with room left and a
   strong scope card; skip a lesson whose card cannot carry the batch and say why in `notes.md`. Apply
   [Room left and stop rule](#room-left-and-stop-rule). A deliberate two-lesson
   question may fill a missing natural pair cell (both lessons used in
   the working — AGENTS rule 3); the API lists only the cells that exist, so a missing one is your judgment, named in
   the plan line. Coverage reads the API (Hyperdrive, ~75 s stale — T5): it chooses lessons; it never proves rows.
   `python3 $T lessons --grade 6 --subject Mathematics` → the `lesson_id`.
   `python3 tools/dedup-sheet.py --grade <g> --card <key>=<NN> --out $A/dedup-sheet.md` → every live row and each
   card example, exercise and activity, with full text. Read the sheet before planning; note the closest item and how
   the task differs for each plan line. Apply [Room left and stop rule (T3)](#room-left-and-stop-rule).
3. **Plan — one line per question** in `notes.md`, before any authoring:
   `Q<n> · <skill / section> · <R/M/H per part> · closest: <question_id> (<score>) — differs because <task, not numbers> · figure: <template | hand-draw | none>`
   **Similarity check (decision 0026), before step 4.** Sketch each planned question as `{key, stem, parts}` in
   `$A/plan-items.yaml` (a list; one-sentence stem + one line per part is enough) and run
   `python3 $T similar --grade <g> --subject Mathematics --items $A/plan-items.yaml --out $A/similar-plan.json`
   (`--exam <slug>` for an exam pool). It prints the 5 nearest published questions per item with a score, flags a
   `WARN` if any pool row has no vector yet (run `embeddings-refresh` for the pool, then re-run). Read each
   neighbour's stem and parts (`questions show <id>` for the full row) and fill `closest:` with the top one; when a
   neighbour asks for the **same sequence of tasks** (e.g. "find the bearing · reverse it · walk back") with a new
   story or new numbers, change the plan, not the wording. A low similarity score is **not** a pass. Re-run
   `similar --items $A/content.yaml` once the spec is written.
   (a coverage-picked lesson may cite its before-count, e.g. `L26 Triangle Constructions (0 before)`).
   Check the set against [Difficulty bands](#difficulty-bands) and against AGENTS rule 3 for every multi-lesson tag.
   A figure that has nothing
   derivable (a pure shape to name) is dropped or put to the owner, never given an invented claim.
   Re-run `tools/dedup-sheet.py --grade <g> --card <key>=<NN> --plan $A/plan-items.yaml
   --similar $A/similar-plan.json --out $A/dedup-sheet.md` so each plan line and its neighbours are on the
   sheet before the plan critic.
   - **An H part is not just a longer chain** (owner ruling 2026-10-04, plan OD-8). If every step is a move the
     lesson's worked examples show in that order — "find the 9th term" by continuing the steps, "list the
     factors and pick the most" — it is M, and the critic will rate it so. Give each H part one real trigger:
     an unfamiliar situation the lesson never shows, a reverse step (given the result, find the input), a
     decision after the arithmetic, or a "why / why not" justification. Write the trigger into the plan line
     (`H: reverse`, `H: decide`, `H: justify`, `H: new context`).
### Plan-stage critic

3b. **Plan critic (one fresh `qgen-critic` session, Normal mode, `Mode: plan`).** Pass it only paths: `plan-items.yaml`, `similar-plan.json`, `dedup-sheet.md` and the cards. It answers per plan line `OK` or `REPLACE — <reason>`. Replace every REPLACE line, then re-run `similar` and the dedup sheet. A second plan round is allowed only for the lines that changed; after that the stop rule applies. Create the session only once every line is OK. This catches copies while a fix costs one line, before the build, ship and SQL.
4. **Author `content.yaml`** (`id_seed`, `lessons:` key map, `figures:` key map, `questions:`
   with `n`, `lessons`, `stem`, `figure`, `parts[label, text, figure, approach, final]`; `build-staged.py` docstring):
   - **Stem** — [`author-question-text`](../author-question-text/SKILL.md) §1a + §3: `$…$`/`$$…$$`, never Sinhala
     inside KaTeX `\text{}`; lay out stems and part texts per §5. Since 0024 every stem, part text,
     approach and final is authored in BOTH English and Sinhala: `stem`/`stem_si`, part `text`/`text_si`,
     leaf `approach`/`approach_si`, `final`/`final_si` — the Sinhala side natural everyday Sinhala, the
     English side plain school English, same numbers/steps; maths-only text (`$x = 4$`) may be identical
     (author-question-text §0.6). `build-staged.py` refuses a missing or copied side.
   - **Structure** — [`structure-question-parts`](../structure-question-parts/SKILL.md) §0 + §2: bare unique labels,
     depth ≤ 2. Choose `id_seed`, `n` and labels once — they are the row identity.
   - **Answers** — [`author-question-answers`](../author-question-answers/SKILL.md) §3 (independent derivation + a
     genuine second method), §4.1c (one step per paragraph for the approach; T-QG-14), §4.2 (answer first in the final),
     §4 (`approach` + `final` only; provenance goes to `notes.md`, never to `approach`), §5a.
     Two actor-only keys now ride on every leaf: `check:` — a small arithmetic expression that must be True
     (`check: "40 * 23 == 920"`, or `divmod(925, 40) == (23, 5)`; numbers, `+ - * / // % **`, comparisons
     incl. tuple comparisons, `and/or/not`, `ceil floor divmod min max abs sum round sorted int len` —
     check-answers.py's docstring is the whitelist) and `level:` — `R`|`M`|`H`, the rubric level. A leaf
     whose answer computes nothing declares `check: "none — <reason>"` (reason ≥10 chars after the
     dash; counted separately, not WARNed). Every number in `final` should be reachable from the
     check. Both keys are leaf-only — a part that has `parts` cannot carry them (build-staged refuses).
     `build-staged` never emits either key.
   - **Figure specs** — for each planned figure, one entry in `$A/specs/figures.json` per
     [`figure-templates`](../figure-templates/SKILL.md) (the stem's own numbers; the builder refuses any it cannot find).
     ⚠️ **`figure_id` = the figure's staged id** — `Q<n>` for a question figure, `Q<n>.<label>` for a part figure
     (`Q3.b`); an answer figure is `….ans<k>` — and the `figures:` key in `content.yaml` points at
     `figures/<figure_id>.json`. visual-check finds a staged figure's claim set as `<figure_id>-claims.txt` (or
     `.claims.txt`) under `--claims-dir`; any other name leaves it
     claims-less (warned, not failed) and the shaded/grid checks silently skip.
     No template fits → hand-draw: claim set first, `channel: constructed`, a `stem:` header and ≥1 `derive`
     ([`read-figure-claim-set`](../read-figure-claim-set/SKILL.md) §2.3), then
     [`draw-and-verify-question-vdd`](../draw-and-verify-question-vdd/SKILL.md) §3–§5. A real `a11y.title` and
     `a11y.description`, and the description never states what is asked (**T125**).
   - **Blueprints** — when one stem should be re-rolled with different numbers (a parameterised question the
     owner wants re-drawn per session), author it once as a blueprint YAML and instantiate it:
     `python3 tools/blueprint.py instantiate <file> --seed N --n Q [--spec-out $A/specs/figures.json]` prints a
     `questions:` item to paste in (it carries `blueprint_id`/`blueprint_seed` provenance — actor-only keys
     build-staged validates and never emits). **At most one variant per blueprint per batch** — a second
     question with the same `blueprint_id` is refused (**T-QG-8**). The emitted item is an ordinary question
     afterwards: every gate and the critic see it like any other.
5. **Build figures, then the doc** (mechanical) — one command runs the whole segment:
   `python3 tools/run-gates.py build $A --medium <medium> --card <lesson-key>=<NN> --grade <g>` — stops at the
   first failing stage with its last ~15 lines, prints one `Q<n> audit ok · vdd-check ok · vc PASS WxH` line per
   figure, and writes `$A/gates.json`. (Drop `--card` and the pre-critic lint is skipped — say so.) What it runs:
   ```
   python3 tools/vdd_templates.py build $A/specs/figures.json --out $A/figures/   # skipped when the file is absent/[]
   python3 tools/audit-claim-set.py <id>-claims.txt                    # each: exit 0 — EVERY figure:
   node tools/vdd-check.mjs <id>.json --claims <id>-claims.txt --medium <medium>  # specs ∪ content.yaml's
                                                                   # figures: files (hand-drawn ones too);
                                                                   # a missing <id>-claims.txt fails here
   python3 tools/build-staged.py $A/content.yaml --out $A/staged.json --ids-out $A/ids.json
   python3 tools/check-answers.py $A                                 # every leaf's `check:` must be True
   node tools/markdown-gate.mjs --fields $A/fields.json              # every text field; any BLOCKED fails (T-QG-7)
   python3 tools/check-layout.py --fields $A/fields.json              # stems, parts, approaches, finals; 0 FAIL (T-QG-14)
   node tools/visual-check.mjs $A/staged.json --claims-dir $A/figures --out wt/<topic>/vc   # mode 1, incl. contact sheet
   python3 tools/precritic-lint.py $A --card <key>=<NN> --grade <g>                          # when --card was passed
                     [--rubric easy|medium|medium-hard] [--existing $A/existing*.json]        # auto-added by run-gates
   ```
   A failing gate is fixed in the spec or the builder input, never by hand-editing an emitted file (T-QG-2).
6. **visual-check mode 1** (inside `run-gates build`; standalone:
   `node tools/visual-check.mjs $A/staged.json --claims-dir $A/figures --out wt/<topic>/vc`)
   → exit 0, and no `no claim set` warning. **6b, lead:** open `wt/<topic>/vc/contact-light-375.png` **once** —
   every figure's light-375 render at native size with its id captioned — and write one line per figure into
   `notes.md` the moment it is seen (what it shows; anything wrong; its pixel dimensions from the verdict line).
   Open a single figure's `light-375.png` only when the sheet shows a problem or is too small to judge — still one
   image per `read`. A defect → back to step 4/5.
7. **Create the session** (once): `python3 $T session create --name "G<g> Maths · <Easy|Medium|Hard> · <N>Q · <d Mon YYYY, h:mm AM/PM>" --scope grade=<g>,subject=Mathematics,medium=<medium> --lessons <ids> --ledger $A/ledger.json`.
   The name follows the owner standard (ruling 2026-10-15): `·` is U+00B7 with a space each side, the
   time is the session's creation time from `TZ=Asia/Colombo date '+%-d %b %Y, %-I:%M %p'`, and there
   is **no medium indicator**, no lesson list and no extra words — e.g. `G8 Maths · Easy · 10Q · 15 Oct 2026, 3:05 PM`.
   A misnamed session is renamed via the session PATCH (`name` field), never recreated.
   Copy the printed id into `RUN.md` now.
8. **Validate until clean** — steps 8–11 in one command (the default):
   `python3 tools/run-gates.py ship $A --sid <sid> --scope <same as step 7> --session-check` — runs validate →
   `doc put` → `doc get` (compares against `staged.json`, ignoring the server-added `published`/`published_at`) →
   visual-check `--session` → publish dry-run → publish → Q2, quoting each tool's key lines and stopping at the
   first failure; exit 5 propagates a `q3: NOT ok`. The per-step commands below are what it runs — use them singly
   when only one stage needs re-running.
   `python3 $T validate <sid> --staged $A/staged.json` → exit 0. Fix every error; fix every
   warning or write why it stays.
9. **Save and see it:** `python3 $T doc put <sid> --staged $A/staged.json --ledger $A/ledger.json`, then
   `doc get <sid> --out $A/server.json` and confirm it is the doc you meant. Then
   `node tools/visual-check.mjs --session <sid> --staged $A/staged.json --claims-dir $A/figures --out wt/<topic>/vc-session` (headed; signs in, shoots every question's
   student preview light + dark, signs out, runs Q3) → exit 0, no `CLIPPED`. `--staged` + `--claims-dir`
   matter: the local staged.json IS the server doc (doc get just proved it), so each rendered figure
   assesses against ITS claim set — `allow:`/`departures:` apply in the live preview exactly as in
   mode 1.
10. **Publish, flagged:**
    `python3 $T publish <sid> --staged $A/staged.json --scope <same as step 7> --ids-file $A/ids.json --ledger $A/ledger.json --dry-run --accept-signatures 0`
    — `signatures_at_risk` is 0 on a new session. Then the same without `--dry-run` — keep
    `--accept-signatures 0` on the real publish too; it refuses (exit 4) without it. Exit 0 is the only success; quote
    "published k/n", "read-back 1: staged doc confirms …", `t77: N question(s) · N comparisons · 0 mismatch(es)` and
    "provenance: N id(s) · OK". Exit 1 = staged and live disagree; the run is failed until they agree (**T77**).
    After the logout the tool runs Q3 itself when a DB URL resolves — the transition-era
    `VIBHAGA_ADMIN_AUTH_DB_URL` sources, else the content-DB chain (`DATABASE_URL` env → the admin env file's `DATABASE_URL` line → `Vibhaga-DB/.env`; no manual export needed when `VIBHAGA_ADMIN_ENV` carries it):
    `q3: ok` (counts land in the ledger under the session) · `q3: PENDING — no DB URL source; …`
    (prove by hand, step 11) · `q3: NOT ok — <counts>` turns an otherwise-successful write into exit 5.
    **Then refresh the similarity vectors** for the pool so the critic's Q4e (and the next run's `similar`) sees
    these rows: `python3 $T embeddings-refresh --grade <g> --subject Mathematics` → `remaining 0`. It writes only
    derived vectors, never content; a 502 `embedding_unavailable` does not undo the publish — retry it later.
11. **Prove it by SQL:** `python3 tools/sql-proof.py q2 <sid> --expected <N> --out $A/q2.json` → `q2: ok` AND
    `q2b: ok` (both lines come from the one `q2` command — there is no `q2b` subcommand; Q2b is the 0024 bilingual-completeness proof — every stem and approach has both sides;
    flagged, published, paperless, scope, 0 signed, 0 unanswered leaves). Q3 is now automatic: every **write**
    subcommand's logout runs it (step 10) — on a `q3: PENDING` line (no URL source at all) run the Q3
    `SELECT`, actor id substituted, through the Supabase MCP `execute_sql` on the **content**
    project (the Admin Auth project is merged into it — there is one Supabase project now), and record its
    row (`actor_exists`, `sessions`, `active_refresh_tokens`, `actor_is_admin`, `ok`) in `q3.json` by
    hand — same `ok` rule; never `PENDING` at done. `actor_is_admin` is what makes a bare uid count as
    evidence: only an admin identity's revocation proves the tool's sign-out. A psql
    `function qgen.q3 does not exist` or a `permission denied` means the one-time setup below was
    not run. Leave the questions published and flagged.

    **One-time Q3 setup:** run as `postgres` on the merged project; see
    [docs/Q3-SETUP.md](../../docs/Q3-SETUP.md).
12. **Pre-critic lint** — `run-gates build --card` already ran `tools/precritic-lint.py`; re-run it standalone
    (`python3 tools/precritic-lint.py $A --card <key>=<NN> --grade <g>`) after any `content.yaml` edit. Fix every
    FAIL (`not_taught` probe found in a stem/part/approach/final — per question by default: a question
    answers only to the cards its `lessons:` keys tag; `--all-probes` is the old run-wide check) and look at each WARN (a11y `description`
    carrying a figure's readable number — T125; the vocabulary heuristic) before the critic sees the batch.
    `--existing` may WARN a blueprint variant against a row from another session — expected: across sessions
    variants count as distinct (owner ruling 2026-10-03; within a batch build-staged already refused, T-QG-8).
13. **Critique — a fresh `qgen-critic`** ([`agents/qgen-critic.md`](../../agents/qgen-critic.md)). Spawn it with
    **paths only**, in exactly this shape:
    ```
    Critique playground batch <sid> per your profile. Paths: plugin <plugin checkout>; corpus <corpus checkout>;
    content-DB env <Vibhaga-DB/.env>; visual-check output <wt/<topic>/vc>; write the report to
    <wt/<topic>/critic/rN.md> — the exact file path (not a directory; the critic passes the corpus
    checkout to critic-read itself). [VIBHAGA_ADMIN=<Admin checkout> VIBHAGA_WEB=<Web checkout> — when the plugin is
    not a sibling of them, e.g. a worktree.] [Chunk: questions <n..m>.] [Previous report: <path>.]
    ```
    Never `content.yaml`, claim sets, staged docs, notes or a hint about which items you doubt (**T25**). **One
    critic for the whole batch** (≤ 12 questions — profile §7), started as a separate session in **Normal** mode,
    not Fusion (owner ruling 2026-10-20: fresh eyes kept, cost cut). The critic is
    **image-blind**: its could-not-check list names the figure look, which step 6b already covered — say so in the
    ledger, do not re-open the PNGs. Compare its R/M/H with your plan line: a gap of more than one level on a part is a
    MINOR. `critic-read.py` also writes `brief.txt` beside the rows — the session's own scope pack — so the critic
    opens the lesson Markdown only at the sections a finding needs, never whole.
14. **Fix and re-critique until SATISFIED.** SATISFIED = 0 BLOCKER and 0 MAJOR. Fix every BLOCKER/MAJOR; fix a
    MINOR only when it is a one-line edit, otherwise write it down as an owner note (with the reason) — a MINOR
    alone never buys another critic round (lean runs, owner ruling 2026-10-20). A fix is: edit `content.yaml` (same `id_seed`, `n`, labels) → `run-gates.py build` → 6b (only
    for a figure that changed) → `run-gates.py ship` (`doc put`; `--session-check` only if a figure or stem changed)
    → Q2 each time; Q3 runs itself after every write, or by MCP after the **last** republish on a `q3: PENDING`
    laptop. Then `python3 tools/critic-read.py hashes <sid>` prints `Q<n> <sha256>` per question — diff it against
    the previous round's hashes and re-spawn a **fresh** critic, with `Previous report: <path>`, only for chunks
    holding ≥1 changed question; a chunk with no changes carries its verdict (record that in the ledger — profile
    §6: CARRIED / FIXED / OPEN / REGRESSED by hash). Never ask the same critic twice. **Sinhala-fluency MINORs are must-fix: apply the critic's rewrite.**
15. **Logbook line** — one dated entry in the plan logbook (private Docs repo): session id, N questions / parts /
    figures, the publish and Q2/Q3 lines, the coverage before → after diff (§5 item 5), critic rounds and verdicts,
    owner questions, effort. Add an ID-free line to
    [MIGRATION.md](../../docs/MIGRATION.md#generate-skill-history-2026-10-21).

### Per-run checklist — `$A/RUN.md`, ticked as you go

```
- [ ] env: VIBHAGA_ADMIN / VIBHAGA_WEB / VIBHAGA_CORPUS / VIBHAGA_ADMIN_ENV set (worktree) or siblings confirmed
- [ ] 1 scope statement in notes.md (card file + lesson file + sha256)
- [ ] 2 coverage-before.json saved · lessons picked (None/Thin + card) __ ; dedup: existing.json rows = __ ; stems compared: __
- [ ] 3 plan: N lines, rubric checked, rule 3 checked · similar-plan.json saved, every line names its closest row
- [ ] 4 content.yaml + second-method results per leaf in notes.md
- [ ] 5 run-gates build exit 0 — gates.json: audit + vdd-check per figure (hand-drawn too), staged.json, ids.json = N ids, check-answers, markdown-gate 0 BLOCKED, layout 0 FAIL, mode 1, lint
- [ ] FRICTION.md lines: __
- [ ] 6 contact-light-375.png logged — one line per figure (__ of __)
- [ ] 7 session id: ________ (in ledger.json AND here — before any further write, T9)
- [ ] 8–11 run-gates ship exit 0: validate clean · doc get matches staged · --session no CLIPPED · signatures_at_risk 0
      · publish k/n + read-back + t77 + provenance quoted in notes.md · q2: ok · q3: ok (auto) or PENDING → MCP noted
- [ ] 12 precritic-lint: 0 FAIL · every WARN read
- [ ] 13 critic r1 spawned with paths only · verdict ____
- [ ] 14 rounds: r__ SATISFIED · critic-read hashes diffed · unchanged chunks CARRIED in ledger · every finding FIXED
      or an owner question · Q2 + Q3 ok after the last republish
- [ ] 15 logbook line written · ID-free line added to MIGRATION.md
```

## 3. What makes a generated question fit

The critic grades every part against this table (profile §3) — keep it and the profile in step.

| Check | Fails when |
|---|---|
| In lesson | it needs a concept the lesson does not teach, or a later grade's notation |
| Not a copy | it matches any item in [Copy check](#copy-check) |
| Self-contained | a student cannot answer it from the stem and figure alone (no "see the table on page 87") |
| Answer right | the second method disagrees, or the figure's measured values contradict the stem |
| Figure honest | the drawing *looks* like the claim but measures differently (S6b §5) |
| Language | a missing `*_si` side, a copied side, or it does not use the lesson's own vocabulary as printed |

### Copy check

*What counts as a copy (one definition, used by the writer AND the critic).*

A planned or written question is a **copy** when its task chain (what the student is asked to do, step by step) matches any one of the following. Changing the numbers, names or story does not stop it being a copy.
1. any live row tagged with the same lesson (every row, read in full — not only the `similar` top 5),
2. any of the card's `worked_examples`, `exercises` or `activities`,
3. any `similar` neighbour, whatever its score (the score only ranks the neighbours).
Read all three with `tools/dedup-sheet.py` before planning. Write one line per planned question in `notes.md`: closest item · how the **task** differs.
A match on one part only, where the other parts are new, is a scaffold echo (MINOR). A match on the whole question, or on every part, is a copy (MAJOR).

### Difficulty bands

| Band | Leaf levels | Shape |
|---|---|---|
| Easy | every leaf `R` | 1–3 leaves; each leaf is one idea of the lesson in at most 2 computation steps; friendly numbers |
| Medium | at least one `M`, no `H` | 2–4 leaves; part (a) may be `R` |
| Hard | the existing medium-hard rubric | unchanged |

For an Easy question, "new" means one of these: a context the lesson does not use; an R-level idea from the lesson combined with a different R idea from the same lesson; or a reverse question (given the answer, find the data). If a lesson has no new Easy task left, apply the [Room left and stop rule](#room-left-and-stop-rule).

### Room left and stop rule

- **Room left, not just row count.** Before you keep a thin lesson, read its dedup sheet. If its live rows already use every card section task and every `difficulty_hooks` entry at the target band, the lesson is **full**. Skip it and take the next thin lesson.
- **Stop rule.** If one slot draws two copy MAJORs (from the plan critic or the batch critic), stop rewriting it. Move the slot to a different lesson (`playground-publish.py session update <sid> --lessons …` adds the lesson to the session), or drop the question and tell the owner.

## 4. Traps

- **T142:** Publish through `playground-publish.py`; it re-PUTs and reads back the flagged doc. ([TRAPS.md](../../docs/TRAPS.md), T142)
- **T5:** API lists may be stale; prove writes by SQL. ([TRAPS.md](../../docs/TRAPS.md), T5)
- **T9:** Record session and question ids before writes; recovery without them needs `source_batch_id`. ([TRAPS.md](../../docs/TRAPS.md), T9)
- **T77 / T-QG-4:** PUT before publish; verify staged/live agreement after it. ([TRAPS.md](../../docs/TRAPS.md), T77, T-QG-4)
- **T-QG-2:** Build claims from stem numbers; never self-validate a drawn ratio. ([TRAPS.md](../../docs/TRAPS.md), T-QG-2)
- **T25:** Give the critic paths only, never hints or actor files. ([TRAPS.md](../../docs/TRAPS.md), T25)
- **T-QG-8:** One blueprint variant per batch; roll another in a later session. ([TRAPS.md](../../docs/TRAPS.md), T-QG-8)

## 5. Verify (definition of done, per run)

1. `RUN.md` is fully ticked; `notes.md` holds the scope statement, the dedup evidence, one plan line per question and
   one look line per figure.
2. `validate` exits 0 on the final staged doc; every warning is fixed or explained.
3. Every figure: `channel: constructed` claim set with a `stem:` header, `audit-claim-set.py` exit 0, `vdd-check.mjs`
   0 findings, visual-check mode 1 and `--session` exit 0.
4. `publish` exits 0 with the four quoted lines of step 10 clean.
5. Coverage after: `coverage … --out $A/coverage-after.json` re-run with the same flags as step 2; every picked lesson
   rose by its question count, a two-lesson row raised both lessons and its pair cell, nothing else moved, and the
   student-visible (`--needs-human-review false`) total did not change (every new row is flagged). The diff goes in
   `notes.md` beside Q2 — it is supporting evidence; Q2 is the proof.
6. `sql-proof.py q2` prints `q2: ok` for the final publish (this is the `verified_by IS NULL` proof); absence from the
   student `GET /v1/questions` is supporting evidence only (§1).
7. `sql-proof.py q3` prints `q3: ok` on the merged project for the actor — an admin identity that
   exists there.
8. The last fresh `qgen-critic` reported SATISFIED; every BLOCKER, MAJOR and MINOR on the way is FIXED (republished
   flagged) or recorded as an owner question.
9. The ledger (session id, question ids) is in the run's logbook entry.

## 6. Keep this skill alive

When the playground contract changes (new verb, delete, or a publish that mirrors the flag itself), update §1, §2 and
the tool together, and retire T142 if the server starts writing the flag. When a tool's flags change, update the step
that calls it. When §3 changes, change `agents/qgen-critic.md` §3 in the same PR. Keep dated run history in
[MIGRATION.md](../../docs/MIGRATION.md#generate-skill-history-2026-10-21); session ids stay in the private plan logbook.
