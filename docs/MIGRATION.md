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
| `t77-staged-vs-published.py` | as-is | as-is | staged-vs-published drift check; unchanged |
| `markdown-gate.mjs` | as-is + fix | as-is | UMBRELLA resolution bug fixed (`HERE/../..` was wrong from `tools/`) |
| `check-inline-math-width.py` | as-is | as-is | estimator; the measured check is `measure-inline-math-width.mjs` |
| `measure-inline-math-width.mjs` | as-is + fix | as-is | same UMBRELLA resolution fix as markdown-gate |
| `vdd_cookbook.py` | as-is | as-is | note: **W3 extends it** — do not rewrite here |
| `audit-claim-set.py` | **modify** | modify | `channel:` optional (missing ⇒ `constructed`); new required `stem:` header on constructed sets; stem-ratio check (every `ratio`/`angle` claim's value justified by the stem's numbers or a cited `derive`); `SELF_TEST_STEM_RATIO` red-team; scrubbed real id fragments in fixture text. **Review F1:** a cited `derive` now justifies only if every literal in its expression is a stem number, a constant {1,2,90,180,360}, or a backed derive's value (transitive, no cycles) — an invented `derive 3 / 2 = 1.5` can no longer rescue a copied ratio |
| `vdd-check.mjs` | **modify** | modify | "page"→"claim" wording; single tight constructed band (ratio ≤ 2 % · angle ≤ 1 ° · residual ≤ 1 %) — `--band raster` dropped; label metrics in `--json` as `labels:`; `--admin` flag > `VIBHAGA_ADMIN` > sibling; new self-test cases. **Review F3:** label metrics are rendered px at each width (viewBox units × render scale), measured to the stroke's EDGE (centreline − half its rendered width), and an unmeasurable bbox fails closed |
| `run-gate.sh` | **modify** | modify | paper assumptions removed (paper_metadata header, S7 manifest join, quarantine/verdicts, split-PDF sha, 1–2 lessons/question rule → ≥1 lesson uuid); kept markup/KaTeX, Sinhala-in-`\text`, structure, flag-true, no-`exam`, figure checks + red-team fixture |
| `check-suite.py` | **modify** | modify | re-pointed at the plugin; the single offline runner — unittest discovery, each tool's `--self-test` (vdd-check SKIPs cleanly without an Admin checkout), `node --test` for `.mjs`, link/trap lint over skills |
| `build-staged.py` (old) | **replace** | replace | new `tools/build-staged.py`: `content.yaml` (or `content.json`) → `staged.json`; deterministic uuid5 ids; refuses duplicate n, **duplicate sibling label (review F2 — same-named parts collide on one uuid5 path)**, unknown lesson/figure key, missing figure file, depth > 2, leaf without approach+final, parts+whole answer, non-bare label, non-uuid lesson |
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
| vector/raster audit-claim-set fixtures in self-tests | kept | the tool still parses those channels; they exercise the shared grammar — no new work |

## Skills & agents

| source @08c09a9 | verdict | what changed / why |
|---|---|---|
| `generate-lesson-questions` → `skills/generate` | **modify** | re-pointed to `tools/`; `build-staged` step added; corpus-refusal rule (refuse grades without a corpus checkout); O/L cards assembled from the G10+G11 *scope cards* via the O/L mapping in Vibhaga-Docs `lessons/ol/mathematics.md` (review F4 — O/L refused until BOTH cards exist), with O/L lesson ids; scope cards live in the PRIVATE corpus `maths/grade-NN/scope-cards/` + `maths/ol/scope-cards/` (W2); "Runs so far" ids scrubbed to a one-line summary; W7 rewrites as the orchestrator |
| `author-question-text` | **modify** | kept §1a (authoring a stem where nothing is printed) + §3 markup law + binding §0 items (e.g. `question_text_sinhala: null`); dropped transcription, furniture quarantine, regime channels; field-corruption lessons kept (silent field corruption is not paper-specific) |
| `structure-question-parts` | **modify** | plan said "as-is"; the paper-side wrapper (S12 contract, printed-label rulings) had to go — the label/depth/duplicate-id law is kept verbatim |
| `read-figure-claim-set` | **modify** | constructed channel only; the claim grammar kept verbatim; new `stem:` header + stem-ratio check documented; printed-figure reading and Audit B source-reading dropped |
| `draw-and-verify-question-vdd` | **modify** | §3/§4 kept; §5 rewritten as drawn-vs-stated (claim-set anchors are canvas coordinates; vdd-check's numeric check + label metrics); live figure uuids scrubbed to generic references; §4.0a layout recipe kept — **this is why `vdd-layout.mjs` is carried** |
| `author-question-answers` | **modify** | D3 independent derivation + second-method check + §4 field-fitting + §4.5 figure trigger + §5a answer-id key trap kept; marking-scheme sourcing dropped (there is none); live counts/ids/stems scrubbed; noted `content.yaml` has no answer-figure key yet (§4.5.5) |
| `critique-onboarded-content` → `agents/qgen-critic.md` | **replace** | custom-subagent format (`agents/<name>.md`); only §1.3 playground mode + the C-checks it needs; marked **draft — W6 completes** |
| `drive-admin-onboarding-ui` → `skills/visual-check` | **replace** | short `/generate` driving section: sign in → card render check → student-preview element shot at 375 px → SIGN OUT with revocation proof; W4 adds the one-command renderer |
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
git grep -nIE 'supabase\.co|adgwjkjxlmumgogilepj|jtrbmmsufghmnrzvcbix'
git grep -nIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
git grep -nP '[\x{0D80}-\x{0DFF}]'
git grep -nIE '\b[0-9a-f]{8}\b' -- skills agents docs
```

| hit class | disposition |
|---|---|
| uuids in `tests/` + `tools/` | **all synthetic** — `00000000-…-4000-8000-…` lesson placeholders, `11111111`/`22222222`/`deadbeef` test constants, uuid5 ids in `staged-golden.json` derived from a synthetic `id_seed`, `6b1c9c6e-…` the uuid5 NAMESPACE constant in `build-staged.py`. **One real job id found and replaced** (`501b9979-…` → `99999999-…` in `test_publish_initial_draft.py`; it was run-12's live job) |
| `supabase.co` / project refs | **0 hits** |
| emails | `user:pass@api.test`, `user@r2.test`, `actor@example.test` — synthetic `.test` domains only ✅ |
| Sinhala | kept only as **generic vocabulary/grammar fixtures**, never question stems: `markdown-gate.mjs` self-test inputs (the gate's Sinhala rules need Sinhala inputs — generic instruction phrases like *"complete the table"*), `run-gate.sh` + `author-question-answers` limb-A drawing-verb **regex**, one-word fixture labels (`භාග` *fractions*, `අක්ෂ` *axis*, `සෙ.මී.` *cm* abbrev), `vdd-layout.mjs` font-load probe `සිංහල`, T128's two vocabulary word-pairs in TRAPS.md |
| 8-hex id fragments in `skills/ agents/ docs/` | **0 hits** |
| hard-coded hosts in `playground-publish.py`/`publish.py`/`_admin_auth.py` | checked — hosts come from `.env.local`/`VIBHAGA_ADMIN_ENV` at runtime only |
