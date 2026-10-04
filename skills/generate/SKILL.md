---
name: generate
description: The orchestrator for generating new practice questions FROM A LESSON (no source paper) through the Agent Question Playground, as ONE ordered flow — scope cards → a one-line-per-question plan → the lead-authored `content.yaml` → figure templates → visual-check → validate → `doc put` → visual-check `--session` → publish FLAGGED with `tools/playground-publish.py` → SQL proof (queries.sql Q2 + Q3 via `tools/sql-proof.py`) → a fresh `qgen-critic` until SATISFIED → logbook line. Every row lands flagged and hidden from students until a human marks it reviewed. Use when asked to generate, write, create or author questions for a lesson, topic or grade, to "fill a lesson with practice questions", or to run or resume a playground session. Not for onboarding an existing PDF paper — this plugin only generates.
argument-hint: "[grade] [lesson number or name] [how many questions]"
---

# Generate questions from a lesson — the orchestrator

> Moved from Vibhaga-Docs `.devin/skills/generate-lesson-questions` @08c09a9 (see docs/MIGRATION.md);
> rewritten as the orchestrator in W7 (2026-10-02). The S4–S8 skills hold the *rules* of each step;
> this file holds the *order*, who does each step, and the per-run checklist.
>
> Runs so far (ids are kept in the private plan logbook, never here): 2026-09-27 and 2026-09-29 through the
> source skill; 2026-10-02 the W6 red-team batch (4 questions, planted errors — the critic caught both);
> 2026-10-02 W8 dogfood (G6, 10 questions, 8 template figures, 2 critic rounds → SATISFIED);
> 2026-10-03 first run on the W9 tools (G6, 10 questions, 8 figures — 7 hand-drawn through finish(), 1 template; 2 critic rounds → SATISFIED);
> 2026-10-03 first run on the W10 tools (G6, 10 questions, 8 template figures, 0 hand-drawn; `check:` on all 31 leaves; 2 critic rounds → SATISFIED; 0 tool repairs, 1 FRICTION line).
> 2026-10-04 first G7 run on the W11 templates (10 questions, 33 leaves, 10 template figures — 6 from coordinate_plane/parallel_lines/bar_chart — 0 hand-drawn; 2 critic rounds → SATISFIED; 0 tool repairs, 3 FRICTION lines).
> Distilled lessons are folded into the steps below: a lesson that teaches angle types *without degrees*
> demands comparison-with-a-right-angle reasoning; measure label↔canvas-edge clearance, not only
> label↔stroke; a constructed claim set takes its ratios from the **stem** (T-QG-2); the critic is
> image-blind, so the PNG look is the lead's.

Plan: [`plans/2026-09-29-question-generation-plugin.md`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/plans/2026-09-29-question-generation-plugin.md)
(W7; the appendix R/M/H rubric). Cross-cutting traps: [`docs/TRAPS.md`](../../docs/TRAPS.md).

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

**Tools (all existing, none forked):** `tools/run-gates.py` (the build and ship chains) · `tools/scope-cards.py`
(`brief`, `draft`, `check`) · `tools/build-staged.py` · `tools/vdd_templates.py` · `tools/audit-claim-set.py` ·
`tools/vdd-check.mjs` · `tools/visual-check.mjs` · `tools/precritic-lint.py` · `tools/playground-publish.py` ·
`tools/sql-proof.py` (Q2/Q3) · `tools/critic-read.py` (the critic runs it). **Rule skills:** [`scope-cards`](../scope-cards/SKILL.md) ·
[`author-question-text`](../author-question-text/SKILL.md) (S4) · [`structure-question-parts`](../structure-question-parts/SKILL.md) (S5) ·
[`figure-templates`](../figure-templates/SKILL.md) · [`read-figure-claim-set`](../read-figure-claim-set/SKILL.md) (S6a) ·
[`draw-and-verify-question-vdd`](../draw-and-verify-question-vdd/SKILL.md) (S6b) · [`visual-check`](../visual-check/SKILL.md) ·
[`author-question-answers`](../author-question-answers/SKILL.md) (S8) · the `qgen-critic` agent
([`agents/qgen-critic.md`](../../agents/qgen-critic.md)).

> **Why a checklist and not a `generate-run.py` driver (W7 decision, 2026-10-02).** Every mechanical stage already is
> one command with its own refusals and exit code (`build-staged` refuses ambiguous specs; `playground-publish` owns six
> guard-rails — scope echo, ledger-before-publish, signatures, flag, logout, read-backs). The lead-only steps (plan, spec,
> PNG look, critic judgment) sit *between* them at five points, so a driver could only chain two- or three-command runs
> while re-threading the session id, scope, ledger and ids that `playground-publish` already owns — the fork the plan
> forbids. The two steps with no tool were the ones done by hand and got wrong: Q2/Q3 typed into `psql` (W4's critic
> found a DB URL on psql's argv) and the publish ids file. Those got `tools/sql-proof.py` and `build-staged --ids-out`.
>
> **W9 (2026-10-02):** `tools/run-gates.py` now drives the two segments that have no lead step inside them —
> `build` covers steps 5–6 (and the pre-critic lint when `--card` is given), `ship` covers 8–11. Every lead-only step
> still sits between them — the plan, the spec, the PNG look, the critic judgment — so the W7 decision stands: a chain
> of existing commands, never a forked driver.

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
3. **Dedup before you author, against everything.** `questions list --lesson-id <id> --all` returns **every** row,
   drafts included, flagged or not, papered or paperless (0018 PD-4). The same exercise with the numbers changed is a
   duplicate. Change the *task*, not only the numbers.
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
| ⚠️ **The publish response does NOT write the raised flag back into the staged doc**; only the flag verbs mirror (`staged_doc_updated`). The tool re-PUTs the doc after each publish and reads it back (**T142**). | T142 |
| Student read path: `SERVABLE` excludes flagged, draft **and** non-solvable rows (no verified answer), so a flagged question is absent from `/v1/questions`. Absence alone does not prove the flag; Q2 does. | 0013 PD-3; `Vibhaga-API/api/openapi.yaml` `/v1/questions` |
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
   uses none of it; `worked_examples` + `exercises` are the don't-copy list; `figure_kinds` are reusable
   *kinds* of figure; `difficulty_hooks` anchor R/M/H. Then open the lesson file **only at the sections and anchors
   the plan uses** — `grep -n` the card's `source.file` for the section headings and each figure's
   `**Description:**` — never read it whole. Write the scope statement into `notes.md`.
   - **O/L:** composed from the G10 + G11 *scope cards* via Vibhaga-Docs `lessons/ol/mathematics.md`, tagged with O/L
     lesson ids (owner ruling 2026-09-29). **Refused until BOTH card sets exist** (plan OD-3). Never copy a card into
     this public repo.
2. **Taxonomy and what exists.** `python3 $T lessons --grade 6 --subject Mathematics` → the `lesson_id`.
   `python3 $T questions list --lesson-id <id> --all --out $A/existing.json` → every row on the lesson; for any row close
   to a plan line, `questions show <id>` for the full stem and answers. Read for duplicates and house style (register,
   markup, answer length). queries.sql Q1 is the same list by direct SQL when you need it uncached (T5).
   Record the row count and which stems you compared in `notes.md`.
3. **Plan — one line per question** in `notes.md`, before any authoring:
   `Q<n> · <skill / section> · <R/M/H per part> · not a duplicate because <…> · figure: <template | hand-draw | none>`.
   Check the set against the plan appendix rubric (for "medium–hard": ≥3 parts each, ≤1 R part and only as (a), an H
   part last, ≥60 % M/H and ≥30 % H across the set's levelled parts) and against AGENTS rule 3 for every multi-lesson tag. A figure that has nothing
   derivable (a pure shape to name) is dropped or put to the owner, never given an invented claim.
   - **An H part is not just a longer chain** (owner ruling 2026-10-04, plan OD-8). If every step is a move the
     lesson's worked examples show in that order — "find the 9th term" by continuing the steps, "list the
     factors and pick the most" — it is M, and the critic will rate it so. Give each H part one real trigger:
     an unfamiliar situation the lesson never shows, a reverse step (given the result, find the input), a
     decision after the arithmetic, or a "why / why not" justification. Write the trigger into the plan line
     (`H: reverse`, `H: decide`, `H: justify`, `H: new context`).
4. **Author `content.yaml`** (the 2026-09-29 shape — `id_seed`, `lessons:` key map, `figures:` key map, `questions:`
   with `n`, `lessons`, `stem`, `figure`, `parts[label, text, figure, approach, final]`; `build-staged.py` docstring):
   - **Stem** — [`author-question-text`](../author-question-text/SKILL.md) §1a + §3: `$…$`/`$$…$$`, never Sinhala
     inside KaTeX `\text{}`. The stem goes in `question_text` **in the session's medium**; `question_text_sinhala`
     stays null (author-question-text §0.6). Part text in the medium too.
   - **Structure** — [`structure-question-parts`](../structure-question-parts/SKILL.md) §0 + §2: bare unique labels,
     depth ≤ 2. Choose `id_seed`, `n` and labels once — they are the row identity.
   - **Answers** — [`author-question-answers`](../author-question-answers/SKILL.md) §3 (independent derivation + a
     genuine second method), §4 (`approach` + `final` only; provenance goes to `notes.md`, never to `approach`), §5a.
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
   node tools/visual-check.mjs $A/staged.json --claims-dir $A/figures --out wt/<topic>/vc   # mode 1, incl. contact sheet
   python3 tools/precritic-lint.py $A --card <key>=<NN> --grade <g>                          # when --card was passed
                     [--rubric medium-hard] [--existing $A/existing*.json]                   # auto-added by run-gates
   ```
   A failing gate is fixed in the spec or the builder input, never by hand-editing an emitted file (T-QG-2).
6. **visual-check mode 1** (inside `run-gates build`; standalone:
   `node tools/visual-check.mjs $A/staged.json --claims-dir $A/figures --out wt/<topic>/vc`)
   → exit 0, and no `no claim set` warning. **6b, lead:** open `wt/<topic>/vc/contact-light-375.png` **once** —
   every figure's light-375 render at native size with its id captioned — and write one line per figure into
   `notes.md` the moment it is seen (what it shows; anything wrong; its pixel dimensions from the verdict line).
   Open a single figure's `light-375.png` only when the sheet shows a problem or is too small to judge — still one
   image per `read`. A defect → back to step 4/5.
7. **Create the session** (once): `python3 $T session create --name "<what> — G<g> <lesson> <date>" --scope grade=<g>,subject=Mathematics,medium=<medium> --lessons <ids> --ledger $A/ledger.json`.
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
    After the logout the tool runs Q3 itself when `VIBHAGA_ADMIN_AUTH_DB_URL` resolves: `q3: ok` (counts land in the
    ledger under the session) · `q3: PENDING — no VIBHAGA_ADMIN_AUTH_DB_URL; …` (prove by hand, step 11) ·
    `q3: NOT ok — <counts>` turns an otherwise-successful write into exit 5.
11. **Prove it by SQL:** `python3 tools/sql-proof.py q2 <sid> --expected <N> --out $A/q2.json` → `q2: ok` (count,
    flagged, published, paperless, scope, 0 signed, 0 unanswered leaves). Q3 is now automatic: every **write**
    subcommand's logout runs it (step 10) — on a `q3: PENDING` line (no `VIBHAGA_ADMIN_AUTH_DB_URL`, true on the
    owner's laptop on 2026-10-02) run the Q3 `SELECT`, actor id substituted, through the Supabase MCP `execute_sql`
    on the **Admin Auth** project, and record its row (`actor_exists`, `sessions`, `active_refresh_tokens`,
    `wrong_project`, `ok`) in `q3.json` by hand — same `ok` rule; never `PENDING` at done. A psql
    `function qgen.q3 does not exist` or a `permission denied` means the one-time setup below was
    not run (or psql landed on the wrong project). Leave the questions published and flagged.

    **One-time Admin Auth setup** (run once as `postgres`): Q3 reads through `qgen.q3`, a
    counts-only SECURITY DEFINER function — RLS on `auth.*` has no policies, so a plain reader
    role would see zero rows, and the reader must not be BYPASSRLS. The MCP fallback still works:
    postgres can execute the function.

    ```sql
    create schema if not exists qgen;
    create or replace function qgen.q3(actor uuid)
    returns table(actor_exists bigint, sessions bigint, active_refresh_tokens bigint)
    language sql stable security definer set search_path = '' as $$
      select (select count(*) from auth.users where id = actor),
             (select count(*) from auth.sessions where user_id = actor),
             (select count(*) from auth.refresh_tokens where user_id = actor::text and revoked is not true);
    $$;
    revoke all on function qgen.q3(uuid) from public, anon, authenticated, service_role;
    create role qgen_auth_reader login password '<strong password>';   -- skip if it exists
    grant usage on schema qgen to qgen_auth_reader;
    grant execute on function qgen.q3(uuid) to qgen_auth_reader;
    ```
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
    Never `content.yaml`, claim sets, staged docs, notes or a hint about which items you doubt (**T25**). Above 8
    questions, spawn one critic per chunk of ≤ 8, in parallel (profile §7), and merge the reports yourself. The critic is
    **image-blind**: its could-not-check list names the figure look, which step 6b already covered — say so in the
    ledger, do not re-open the PNGs. Compare its R/M/H with your plan line: a gap of more than one level on a part is a
    MINOR. `critic-read.py` also writes `brief.txt` beside the rows — the session's own scope pack — so the critic
    opens the lesson Markdown only at the sections a finding needs, never whole.
14. **Fix and re-critique until SATISFIED.** Every BLOCKER/MAJOR/MINOR is fixed or written down as an owner question
    (with the reason). A fix is: edit `content.yaml` (same `id_seed`, `n`, labels) → `run-gates.py build` → 6b (only
    for a figure that changed) → `run-gates.py ship` (`doc put`; `--session-check` only if a figure or stem changed)
    → Q2 each time; Q3 runs itself after every write, or by MCP after the **last** republish on a `q3: PENDING`
    laptop. Then `python3 tools/critic-read.py hashes <sid>` prints `Q<n> <sha256>` per question — diff it against
    the previous round's hashes and re-spawn a **fresh** critic, with `Previous report: <path>`, only for chunks
    holding ≥1 changed question; a chunk with no changes carries its verdict (record that in the ledger — profile
    §6: CARRIED / FIXED / OPEN / REGRESSED by hash). Never ask the same critic twice.
15. **Logbook line** — one dated entry in the plan logbook (private Docs repo): session id, N questions / parts /
    figures, the publish and Q2/Q3 lines, critic rounds and verdicts, owner questions, effort. Add a line under "Runs so
    far" above — without ids.

### Per-run checklist — `$A/RUN.md`, ticked as you go

```
- [ ] env: VIBHAGA_ADMIN / VIBHAGA_WEB / VIBHAGA_CORPUS / VIBHAGA_ADMIN_ENV set (worktree) or siblings confirmed
- [ ] 1 scope statement in notes.md (card file + lesson file + sha256)
- [ ] 2 dedup: existing.json rows = __ ; stems compared: __
- [ ] 3 plan: N lines, rubric checked, rule 3 checked
- [ ] 4 content.yaml + second-method results per leaf in notes.md
- [ ] 5 run-gates build exit 0 — gates.json: audit + vdd-check per figure (hand-drawn too), staged.json, ids.json = N ids, check-answers, markdown-gate 0 BLOCKED, mode 1, lint
- [ ] FRICTION.md lines: __
- [ ] 6 contact-light-375.png logged — one line per figure (__ of __)
- [ ] 7 session id: ________ (in ledger.json AND here — before any further write, T9)
- [ ] 8–11 run-gates ship exit 0: validate clean · doc get matches staged · --session no CLIPPED · signatures_at_risk 0
      · publish k/n + read-back + t77 + provenance quoted in notes.md · q2: ok · q3: ok (auto) or PENDING → MCP noted
- [ ] 12 precritic-lint: 0 FAIL · every WARN read
- [ ] 13 critic r1 spawned with paths only · verdict ____
- [ ] 14 rounds: r__ SATISFIED · critic-read hashes diffed · unchanged chunks CARRIED in ledger · every finding FIXED
      or an owner question · Q2 + Q3 ok after the last republish
- [ ] 15 logbook line written · "Runs so far" line added
```

## 3. What makes a generated question fit

The critic grades every part against this table (profile §3) — keep it and the profile in step.

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
- **T5: the API list said it was there.** A questions list read within ~75 s of a write can be stale. Proof is SQL.
- **T9: the ids are the undo.** Without the ledger, an unpublish needs someone to find the rows by `source_batch_id`
  first. With it, one command does the job.
- **T77: staged and live disagree.** Publish reads the **server** doc, not your file. The tool refuses a publish while
  your file differs from the server doc (run `doc put` first), and T77 compares staged against live afterwards.
  **T-QG-4:** T77 once false-failed a clean publish because its read side knew only `answers[]`; fixed — a T77 failure
  is real until shown otherwise.
- **T-QG-2: the claim set agreed with itself.** A hand-drawn 1.5:1 cuboid passed for a 5:2 stem. Templates take the
  stem's numbers; never retype a drawn number into a spec.
- **T25: the hinted critic.** A critic told what to look for is not independent. Paths only, actor dir out of reach.
- **T-QG-8: two variants of one blueprint in a batch read as one question to a student** — same stem, same
  figure kind, only the numbers differ. `build-staged` refuses a second question carrying a batch-mate's
  `blueprint_id`; roll the next variant in a later session.

## 5. Verify (definition of done, per run)

1. `RUN.md` is fully ticked; `notes.md` holds the scope statement, the dedup evidence, one plan line per question and
   one look line per figure.
2. `validate` exits 0 on the final staged doc; every warning is fixed or explained.
3. Every figure: `channel: constructed` claim set with a `stem:` header, `audit-claim-set.py` exit 0, `vdd-check.mjs`
   0 findings, visual-check mode 1 and `--session` exit 0.
4. `publish` exits 0 with the four quoted lines of step 10 clean.
5. `sql-proof.py q2` prints `q2: ok` for the final publish (this is the `verified_by IS NULL` proof); absence from the
   student `GET /v1/questions` is supporting evidence only (§1).
6. `sql-proof.py q3` prints `q3: ok` on the Admin Auth project for the actor that exists there.
7. The last fresh `qgen-critic` reported SATISFIED; every BLOCKER, MAJOR and MINOR on the way is FIXED (republished
   flagged) or recorded as an owner question.
8. The ledger (session id, question ids) is in the run's logbook entry.

## 6. Keep this skill alive

The route table in §1 was diffed against `openapi.admin.yaml` on 2026-09-27. When the playground contract changes (new
verb, delete, or a publish that mirrors the flag itself), update §1, §2 and the tool together, and retire T142 if the
server starts writing the flag. When a tool's flags change, update the step that calls it. When §3 changes, change
`agents/qgen-critic.md` §3 in the same PR. Add each run's line under "Runs so far" — without session ids in this public
repo.
