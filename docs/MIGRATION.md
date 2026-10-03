# MIGRATION — what came over from Vibhaga-Docs, and what happened to it

Session W0 of the vibhaga-qgen plugin. Source: `Vibhaga-Docs@08c09a9`, tools from
`.devin/skills/_maths-onboarding/`, skills from `.devin/skills/<name>/SKILL.md`. Plan:
`Vibhaga-Docs/plans/2026-09-29-question-generation-plugin.md` §W0.

**Counts:** 14 tools carried (4 modified, 1 new, 9 as-is incl. 1 restored dependency) ·
8 test files carried/new + 4 fixtures · 7 skills (all modified or replaced) · 1 agent (extracted) ·
1 traps doc (22 of ~140 traps carried) · **13 tools + 5 tests + ~25 skills dropped**.

## Tools

| source @08c09a9 | verdict | plan's first verdict | what changed / why |
|---|---|---|---|
| `playground-publish.py` | as-is | as-is | self-test fixture path fixed to run from `tools/`; still the only write path |
| `publish.py` | **as-is** | drop | ⚠️ **plan correction** — `playground-publish.py` imports it (`_pub.Api`, `Refuse`, `finish`, `merge_questions`, `num_norm`, `strip_server_hints`, `norm_scope`, `parse_kv`, `dump`, `t77_subprocess`, `load_db_url`, `read_env`, `find_up`, `ids_of`, `merge_ids`). Kept as a library dependency |
| `_admin_auth.py` | as-is | as-is | credentials from `.env.local`/`VIBHAGA_ADMIN_ENV` at runtime, never printed |
| `t77-staged-vs-published.py` | as-is | as-is | staged-vs-published drift check. **W6 fix:** staged sub-answers are collected from `sub_answer` (the singular object build-staged emits) *and* `answers[]` — reading only the list false-failed a clean publish (T-QG-4); pinned by `tests/test_t77_sub_answer_shapes.py` |
| `markdown-gate.mjs` | as-is + fix | as-is | UMBRELLA resolution bug fixed (`HERE/../..` was wrong from `tools/`) |
| `check-inline-math-width.py` | as-is | as-is | estimator; the measured check is `measure-inline-math-width.mjs` |
| `measure-inline-math-width.mjs` | as-is + fix | as-is | same UMBRELLA resolution fix as markdown-gate |
| `vdd_cookbook.py` | as-is | as-is | note: **W3 extends it** — do not rewrite here |
| `audit-claim-set.py` | **modify** | modify | `channel:` optional (missing ⇒ `constructed`); new required `stem:` header on constructed sets; stem-ratio check (every `ratio`/`angle` claim's value justified by the stem's numbers or a cited `derive`); `SELF_TEST_STEM_RATIO` red-team; scrubbed real id fragments in fixture text. **Review F1:** a cited `derive` now justifies only if every literal in its expression is a stem number, a constant {1,2,90,180,360}, or a backed derive's value (transitive, no cycles) — an invented `derive 3 / 2 = 1.5` can no longer rescue a copied ratio |
| `vdd-check.mjs` | **modify** | modify | "page"→"claim" wording; single tight constructed band (ratio ≤ 2 % · angle ≤ 1 ° · residual ≤ 1 %) — `--band raster` dropped; label metrics in `--json` as `labels:`; `--admin` flag > `VIBHAGA_ADMIN` > sibling; new self-test cases. **Review F3:** label metrics are rendered px at each width (viewBox units × render scale), measured to the stroke's EDGE (centreline − half its rendered width), and an unmeasurable bbox fails closed |
| `run-gate.sh` | **modify** | modify | paper assumptions removed (paper_metadata header, S7 manifest join, quarantine/verdicts, split-PDF sha, 1–2 lessons/question rule → ≥1 lesson uuid); kept markup/KaTeX, Sinhala-in-`\text`, structure, flag-true, no-`exam`, figure checks + red-team fixture |
| `check-suite.py` | **modify** | modify | re-pointed at the plugin; the single offline runner — unittest discovery, each tool's `--self-test` (vdd-check SKIPs cleanly without an Admin checkout), `node --test` for `.mjs`, link/trap lint over skills |
| `build-staged.py` (old) | **replace** | replace | new `tools/build-staged.py`: `content.yaml` (or `content.json`) → `staged.json`; deterministic uuid5 ids; refuses duplicate n, **duplicate sibling label (review F2 — same-named parts collide on one uuid5 path)**, unknown lesson/figure key, missing figure file, depth > 2, leaf without approach+final, parts+whole answer, non-bare label, non-uuid lesson. **W7:** `--ids-out FILE` also writes the bare `question_ids` list in question order — the exact `--ids-file` shape `playground-publish.py publish` consumes |
| `vdd-layout.mjs` | **keep** | drop (default) | plan said drop unless a kept skill section cites it — `draw-and-verify-question-vdd` **§4.0a** is the explicit-layout recipe for reframing an existing document (§3.1a's contract); kept with its `test_vdd_layout.mjs`; Admin default made HERE-relative |
| `test_vdd_layout.mjs` | keep | drop (with tool) | `node --test` suite, runs offline |
| `yaml-from-staged.py` | drop | drop/replace | the inverse direction; not needed by the generation path |
| `anatomy.py` | drop | drop | paper-anatomy mapping — no paper |
| `bands.py` | drop | drop | printed-figure tolerance bands — constructed channel only now |
| `crop.py` | drop | drop | PDF page crops — no paper |
| `qmap.py` | drop | drop | paper question map — no paper |
| `paper-prep.py` + `test_paper_preflight.py` | drop | drop | PDF preflight — no paper |
| `reconcile.py` + `test_reconcile_adjudication.py` | drop | drop | paper↔staged reconciliation — no paper |
| `run-state.py` + `test_run_state_lifecycle.py` | drop | drop | paper-run state machine — playground sessions track their own state |
| `sweep-missed-parts.py` | drop | drop | missed-part sweep over printed papers |
| `s8-brief.py` | drop | drop | figure-readers' brief compiler — claim sets stay actor artefacts |
| `apply-answers.py` + `test_apply_answers.py` | drop | drop | answer-application over paper pipeline — answers authored inline now |
| `AUTHORING-YAML.md` | drop | drop | superseded by `content.yaml` documented in `build-staged.py` + `generate` skill |
| `orchestrate.md` | drop | drop | the S1–S13 paper pipeline; W7 writes the generation orchestrator |
| `TRAPS.md` | extract | partial | `docs/TRAPS.md` — the 6 mandated traps (T5, T9, T77, T125, T136, T142) + every trap still cited by kept text (T4, T13, T14, T25, T30, T34, T56, T61, T70, T74, T96, T98, T99, T104, T114, T128) = **22 traps**; ids/stems scrubbed |
| `scope-cards.py` | — **new (W2)** | new | lesson scope cards: `draft` emits the tool-owned `generated:` block (sections, vocabulary, worked examples, exercises, activities, figure kinds, summary) pinned to the lesson's sha256, preserving `curated:`; `check` verifies schema, staleness, probe grounding, prerequisites and hooks; `--exam ol` refused until OD-3. **W9:** `brief` prints the ~80-line per-card reading brief (header shas, sections, vocabulary, worked examples, exercises, activities, figure_kinds, the whole curated block) — the generate step-1 read |
| `vdd_templates.py` | — **new (W3)** | — | the nine stem-checked figure builders: grid polygon, shaded grid, rays-from-a-point, number line, pictograph, rectangle-with-points, house pentagon, cuboid, dot pattern. Each takes the stem's numbers (`require_stem` against the audit's own regex), computes the geometry from them, fits the canvas, pre-flights label clearance (≥6 px to strokes / ≥8 px to the edge at the narrowest render width, real align/baseline semantics — the card surface's wider normalize is modelled), then emits the `constructed` claim set with its own derive backing (T-QG-2: a claim set must never be copied off the drawing). CLI: `list`, `build spec.json`, `--self-test` (all nine → audit; wired into `check-suite.py` Part B) |
| `visual-check.mjs` | — **new (W4)** | — | batch figure/question render through the REAL Admin `/diagtest` page (W7: `claimsFor` lives in `session-db.mjs`; `--claims-dir` also tries `<id>-claims.txt`) (real `globals.css`, next/font, `html[data-theme]` light+dark) + an esbuild bundle of the real `DiagramRenderer` — the host page matters because `--font-sans` never exists in vdd-check's bare harness and KaTeX `math` labels are HTML overlays, not `<text>` (T-QG-3). Inputs: staged docs, VDD files, dirs. Per figure: per-width label metrics + PNGs, one verdict line, `report.json`. **`--session <id>` replaces the plan's `--admin <session>`** — `--admin` is the plugin-wide checkout flag. `--self-test` is a LIVE check, deliberately not in `check-suite.py` (the suite runs `VIBHAGA_ADMIN_ENV=/nonexistent` so nothing touches a credentials file, and a spawned `next dev` would load `.env.local`). **W9:** mode 1 also writes `<out>/contact-light-375.png` (via `contact-sheet.mjs`), prints each figure's light-375 pixel size in its verdict line, and gains the `aspect` rule (render taller than 2× its width FAILs — the same canvas `vdd_templates`/`vdd-check` refuse) |
| `visual-metrics.mjs` | — **new (W4)** | — | the pure rules module behind visual-check (no browser): `assess()` computes edge/stroke/target/arc/shaded/font verdicts from in-page measurements + a claim set; `node --test` coverage in `tests/test_visual_metrics.mjs` |
| `session-db.mjs` | — **new (W4)** | — | pure helpers for `--session`'s revocation proof: `q3Block` slices queries.sql Q3's SELECT to its terminating `;`, `pgEnvFromUrl` splits `VIBHAGA_ADMIN_AUTH_DB_URL` into `PG*` env vars for psql (nothing on argv — a password there leaks into `ps`; `-f -` on stdin so `:'actor_id'` interpolates — `psql -c` does not). **W7:** also carries `claimsFor` (moved out of `visual-check.mjs` so it is testable offline) — `--claims-dir` now resolves `<id>-claims.txt` (the `vdd_templates.py` filename) after `<id>.claims.txt` |
| `critic-read.py` | — **new (W6)** | — | the critic's one-command read of a playground batch: slices Q4a/b/c out of `queries.sql` (asserts a single SELECT, no write tokens), runs each read-only via psql with the URL split into `PG*` env vars (never argv — the `pgEnvFromUrl` approach ported to Python), and writes `q4a.json` / `q4b.jsonl` / `q4c.jsonl` plus `fields.json` (markdown-gate input), `hashes.txt` and `figures.txt`. DB URL: `--db-env` → `DATABASE_URL` → `publish.load_db_url` (the source is announced on stderr, never the value) (reused, not copied). **W7:** its messages go through a `PROG` prefix so `sql-proof.py` can reuse `slice_block`/`pg_env_from_url`/`resolve_db_url` under its own name. **W9:** `hashes <sid>` subcommand prints the `Q<n> <sha256>` lines alone; `--previous <dir\|hashes file>` restricts fields/figures to changed-or-new questions and writes `carried.txt` — the re-critique-only-what-changed path (profile §6) |
| `sql-proof.py` | — **new (W7)** | — | runs queries.sql Q2 (content DB, post-publish proof) and Q3 (Admin Auth project, revocation proof) read-only via psql and exits on their `ok` column: slices each block out of the real `queries.sql` (local guard — one statement starting WITH or SELECT, no write token), URL → `PG*` env never argv, prints a `key=value` counts line then `q2/q3: ok` or `NOT ok — <failing counts>`; `--out` writes a counts JSON. q3 URL: `--auth-env` → `VIBHAGA_ADMIN_AUTH_DB_URL` env → the line in `.env.local` (`VIBHAGA_ADMIN_ENV`-aware). **W9:** psql failures print the `ERROR:`/`FATAL:` line + the last 3 stderr lines, with a grant hint on `permission denied for schema auth` |
| `contact-sheet.mjs` | — **new (W9)** | — | playwright helper loaded only for visual-check mode 1's contact sheet (or `--contact-sheet-only <dir>`): builds the captioned `<img>` page, screenshots it, reports natural size |
| `precritic-lint.py` | — **new (W9)** | — | the mechanical pre-critic pass over a run dir: (a) FAIL on any `not_taught` probe in any stem/part/approach/final, (b) WARN when an a11y `description` carries a number the figure itself prints (from its claim set — T125), (c) WARN on the lesson-vocabulary heuristic. Exit 1 on any FAIL |
| `run-gates.py` | — **new (W9)** | — | the two gate chains of generate §2: `build <run>` = template build → audit + vdd-check per figure → build-staged → visual-check mode 1 → precritic-lint (when `--card`); `ship <run>` = validate → doc put → doc get compare → visual-check `--session` → publish dry-run → publish → q2. Existing tools as subprocesses, never a lowered flag; stops at the first failing stage with its last ~15 lines; `gates.json` records every exit code; a Q3 `NOT ok` propagates exit 5 |

## Tests & fixtures

| source @08c09a9 | verdict | what changed |
|---|---|---|
| `test_playground_publish.py` | as-is | import/`HERE` paths fixed |
| `test_admin_access.py` | **modify** | real hosts/emails scrubbed to `*.test` / `example.test` synthetic values; tests green |
| `test_publish_initial_draft.py` | as-is + scrub | carried because it passes offline; one **real production job uuid replaced** with `99999999-…` (hygiene) |
| `test_run_gate_figures.py` | modify | synthetic fixtures only |
| `test_run_gate_formats.py` | modify | synthetic fixtures only |
| `test_audit_stem_ratio.py` | **new** | subprocess check: `-bad.txt` exits non-zero citing the claim, `-good.txt` exits 0 |
| `test_build_staged.py` | **new** | golden `staged.json`, determinism, every refusal |
| `tests/fixtures/{content.yaml,staged-golden.json,figures/}` | **new** | synthetic spec + golden output; `00000000-0000-4000-8000-…` placeholder lesson uuids |
| `tests/fixtures/stem-ratio-{bad,good}.txt` | **new** | the red-team fixture pair for the stem-ratio check |
| `test_scope_cards.py` + `tests/fixtures/scope-corpus/` | — **new (W2)** | offline suite over a synthetic 2-lesson corpus (English filler, structural keywords only): draft fields, byte-identical rerun, curated preservation, every `check` failure mode, every exit-2 refusal |
| `test_visual_metrics.mjs` | — **new (W4)** | `node --test` over synthetic docs + synthetic measurements — every rule both ways; runs in the offline suite via the `tests/*.mjs` glob |
| `test_session_db.mjs` | — **new (W4)** | `node --test` for `session-db.mjs` — the Q3 slice and the URL→`PG*` split on synthetic SQL/URLs. **W7:** + `claimsFor` `<id>-claims.txt` resolution under `--claims-dir` |
| `test_vdd_templates.py` | — **new (W3)** | per-template claim-set assertions + audit exit-0 sweep over the synthetic self-test specs; the T-QG-2 red team (5:2 stem → 5:2 drawing; a hand-altered `= 1.5` claim with rescaled anchors exits non-zero naming the claim id; `length=1.5` against a 5:2 stem → `TemplateError`); every refusal path |
| `test_sql_proof.py` | — **new (W7)** | real queries.sql Q2/Q3 slice to one guarded statement each; a fake `psql` shell stub on PATH → ok=t exit 0 / ok=f exit 1 naming the failing counts / non-zero exit 1; non-uuid and `--expected 0` exit 2; q3 with no URL source exit 2; the URL never reaches argv |
| `test_contact_sheet.mjs` · `test_precritic_lint.py` · `test_run_gates.py` · `test_template_sweep.py` | — **new (W9)** | contact-sheet HTML builder + path resolution (pure functions, no browser); the lint's FAIL/WARN rules on a synthetic corpus + run dir; the gate chains with the subprocess runner injected (stage order, stop-at-first-failure, doc-compare ignore list, exit propagation); the 431-case parameter sweep over all nine builders |
| vector/raster audit-claim-set fixtures in self-tests | kept | the tool still parses those channels; they exercise the shared grammar — no new work |

## Skills & agents

| source @08c09a9 | verdict | what changed / why |
|---|---|---|
| `generate-lesson-questions` → `skills/generate` | **modify** | re-pointed to `tools/`; `build-staged` step added; corpus-refusal rule (refuse grades without a corpus checkout); O/L cards assembled from the G10+G11 *scope cards* via the O/L mapping in Vibhaga-Docs `lessons/ol/mathematics.md` (review F4 — O/L refused until BOTH cards exist), with O/L lesson ids; scope cards live in the PRIVATE corpus `maths/grade-NN/scope-cards/` + `maths/ol/scope-cards/` (W2); "Runs so far" ids scrubbed to a one-line summary; W7 rewrites as the orchestrator |
| `author-question-text` | **modify** | kept §1a (authoring a stem where nothing is printed) + §3 markup law + binding §0 items (e.g. `question_text_sinhala: null`); dropped transcription, furniture quarantine, regime channels; field-corruption lessons kept (silent field corruption is not paper-specific) |
| `structure-question-parts` | **modify** | plan said "as-is"; the paper-side wrapper (S12 contract, printed-label rulings) had to go — the label/depth/duplicate-id law is kept verbatim |
| `read-figure-claim-set` | **modify** | constructed channel only; the claim grammar kept verbatim; new `stem:` header + stem-ratio check documented; printed-figure reading and Audit B source-reading dropped |
| `draw-and-verify-question-vdd` | **modify** | §3/§4 kept; §5 rewritten as drawn-vs-stated (claim-set anchors are canvas coordinates; vdd-check's numeric check + label metrics); live figure uuids scrubbed to generic references; §4.0a layout recipe kept — **this is why `vdd-layout.mjs` is carried** |
| `draw-and-verify-question-vdd` → `SKILL.md` + `reference.md` | **split (2026-09-30)** | split first on a wrong hypothesis — the 57 KB file skipped `devin plugins info`, so a ~50 KB size cap was suspected; the 38 KB split still failed. **Real cause:** the frontmatter was not valid YAML (an unquoted `: ` inside the plain-scalar `description`) — fixed with a `>-` folded block, and a frontmatter lint added to `check-suite.py` (T-QG-1). Split kept: long-form material lives verbatim in `reference.md` (§3.7.2–3.7.4, §4.0a, §5.4–5.5, §6 traps) with pointer lines in `SKILL.md` |
| `author-question-answers` | **modify** | D3 independent derivation + second-method check + §4 field-fitting + §4.5 figure trigger + §5a answer-id key trap kept; marking-scheme sourcing dropped (there is none); live counts/ids/stems scrubbed; noted `content.yaml` has no answer-figure key yet (§4.5.5) |
| `critique-onboarded-content` → `agents/qgen-critic.md` | **replace** | custom-subagent format (`agents/<name>.md`); only §1.3 playground mode + the C-checks it needs; marked **draft — W6 completes** |
| `drive-admin-onboarding-ui` → `skills/visual-check` | **replace** | rewritten command-first (W4): mode 1 `visual-check.mjs` batch render + measure through `/diagtest`, the LOOK-one-PNG rule and the not-caught list; the manual drive survives as mode 2 `--session <id>` (sign in → student-preview element shots light+dark → sign out → Q3 revocation proof, PENDING when `VIBHAGA_ADMIN_AUTH_DB_URL` is unset) |
| `skills/scope-cards` | — **new (W2)** | card curation skill (probe grounding, prerequisite forms, difficulty hooks); `generate` §0.1 + §2 step 1 updated to read the card first — a grade with no scope cards is refused |
| `skills/figure-templates` | — **new (W3)** | when a template covers the figure vs hand-draw with the cookbook; the nine-entry catalogue (inputs, stem-checked numbers, emitted claims, limits); the spec → build → audit-claim-set → vdd-check workflow; pointer lines added where figures are first discussed in `generate`, `read-figure-claim-set`, `draw-and-verify-question-vdd` |
| all other `.devin/skills/*` (S1–S15 paper suite, admin-job, coverage, transcription, etc.) | **drop** | paper-pipeline skills with no generation analogue |

## Deliberately kept paper-era mentions

- `docs/TRAPS.md` trap stories reference PDFs/printed figures/manifests as *historical narrative* — the
  rules (stale cache, unrecorded id, flag on the row not the doc) are pipeline-neutral.
- `skills/author-question-answers` keeps the marking-scheme *name* only inside the §6 check-6 regex
  (`marking scheme|derived|source:|page [0-9]` — a provenance detector) and one "no marking scheme"
  statement.
- `tools/{audit-claim-set,publish,playground-publish,vdd-check}` reference vector/raster channels in
  code paths and self-tests — the parsers accept them even though the plugin only produces
  `constructed`.

## Hygiene scan — commands and results (re-run 2026-09-29; raw output `wt/qgen-w0/hygiene.txt`)

```
git grep -nIE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
git grep -nIE "supabase\.co|$CONTENT_REF|$ADMIN_AUTH_REF"   # refs from your private env, never written here
git grep -nIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
git grep -nP '[\x{0D80}-\x{0DFF}]'
git grep -nIE '\b[0-9a-f]{8}\b' -- skills agents docs
```

| hit class | disposition |
|---|---|
| uuids in `tests/` + `tools/` | **all synthetic** — `00000000-…-4000-8000-…` lesson placeholders, `11111111`/`22222222`/`deadbeef` test constants, uuid5 ids in `staged-golden.json` derived from a synthetic `id_seed`, `6b1c9c6e-…` the uuid5 NAMESPACE constant in `build-staged.py`. **One real job id found and replaced** (`501b9979-…` → `99999999-…` in `test_publish_initial_draft.py`; it was run-12's live job) |
| `supabase.co` / project refs | **0 hits** outside this section. ⚠️ 2026-09-30: the scan command itself had the two refs written in literally (a self-inflicted hit the scan could not see); replaced by env variables. They remain in git history before this commit. |
| emails | `user:pass@api.test`, `user@r2.test`, `actor@example.test` — synthetic `.test` domains only ✅ |
| Sinhala | kept only as **generic vocabulary/grammar fixtures**, never question stems: `markdown-gate.mjs` self-test inputs (the gate's Sinhala rules need Sinhala inputs — generic instruction phrases like *"complete the table"*), `run-gate.sh` + `author-question-answers` limb-A drawing-verb **regex**, one-word fixture labels (`භාග` *fractions*, `අක්ෂ` *axis*, `සෙ.මී.` *cm* abbrev), `vdd-layout.mjs` font-load probe `සිංහල`, T128's two vocabulary word-pairs in TRAPS.md |
| 8-hex id fragments in `skills/ agents/ docs/` | **0 hits** |
| hard-coded hosts in `playground-publish.py`/`publish.py`/`_admin_auth.py` | checked — hosts come from `.env.local`/`VIBHAGA_ADMIN_ENV` at runtime only |
