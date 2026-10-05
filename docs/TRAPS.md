# TRAPS — cross-cutting traps the vibhaga-qgen plugin inherits

The subset of Vibhaga-Docs `_maths-onboarding/TRAPS.md` that the moved skills and tools still cite,
plus the traps this plan mandated (T5, T9, T77, T125, T136, T142). Skill-local traps (T-S4-*, T-S5-*,
T-S6a-*, T-S6b-*, T-S8-*) live inside their own skills' §Traps sections. Paper-era mechanics in the
stories below (PDF reads, printed figures, manifests) are historical narrative — the *rule* survives:
a stale cache, an unrecorded id, a flag that lives on the row but not the doc.

| # | the rule in one line |
|---|---|
| T4 | a `204` from `/auth/v1/logout` is not proof of revocation |
| T5 | Hyperdrive's query cache is not invalidated by writes (~75 s) |
| T9 | record generated ids BEFORE you publish — the response merely echoes them |
| T13 | watch a check fire on a deliberately broken fixture before you trust it |
| T14 | `hasSwallowedMarkup` is `false` on an odd number of `$` |
| T25 | a separate agent turn is not something one agent can do to itself |
| T30 | `$`-parity and `hasSwallowedMarkup` never look INSIDE the delimiters |
| T34 | faithful part labels are a defect when you ship a subset |
| T56 | a checksum detects drift WITHIN a repo — nothing compared the two repos |
| T61 | a security fix made two surfaces disagree, and the review surface stated the opposite |
| T70 | a "settle" by sample-equality is a race — a gate that reds at random gets re-run |
| T74 | coverage and false positives measured at different severities = a gate green while blocking nothing |
| T77 | a write to the published row but not the staged doc reverts itself on the next publish |
| T96 | a schema-legal field the renderer ignores is a figure that lies |
| T98 | an `angleMark` label can render on the OPPOSITE side of the vertex |
| T99 | a collapsed segment is invisible to every check that counts elements |
| T104 | the wrong answer that agrees with its own figure — no structural gate can see it |
| T114 | a summary line computed AFTER a display filter cannot fail |
| T125 | a figure's `a11y.description` can state the answer the item asks for |
| T128 | a correct "never" rule applied beyond its real constraint manufactures its own defect |
| T136 | a constructed claim set that "passes" because you read the footer, not the exit code |
| T142 | the playground publish raises the flag on the ROW, not in the staged doc |
| T-QG-1 | a skill whose frontmatter is not valid YAML is silently dropped by the CLI — `devin plugins info` + the frontmatter lint are the check |
| T-QG-2 | a claim set that records the DRAWN ratio passes every audit line — the stem's own numbers must drive the figure, and the value be justified by them |
| T-QG-4 | a drift check whose READ side knows a narrower shape than the write path reports a clean publish as failed |
| T-QG-5 | a width-invariant rule measured per width can straddle its own threshold — a label row says `ok:false` while the figure verdict says PASS |
| T-QG-6 | a reader role with SELECT on `auth.*` sees ZERO rows under policy-less RLS — a revocation count reads "revoked" while sessions are live |
| T-QG-7 | a gate that is never wired into the chain cannot fail it — a `$$…$$` on one line passed build, validate, publish and both visual checks; only the critic's standalone markdown-gate saw it |
| T-QG-8 | two variants of one blueprint in a batch read as ONE question to a student — build-staged refuses a second question carrying a batch-mate's `blueprint_id` (across sessions variants count as distinct) |
| T-QG-12 | a medium-conditional label rule ships figures that can never render on the other medium — drawn diagram text is simple English on EVERY medium (ADR 0021) |

---
## T4 — A `204` from `/auth/v1/logout` is not proof of revocation

**Looked true:** signed out, got a `204`, session gone.
**Actually:** sessions survive. A 12-day-old admin session with `not_after = NULL` was found live on
2026-07-27's credentials, on an admin plane with **no network gate**.
**The check:** re-query `auth.sessions` **and** `auth.refresh_tokens` for the user and confirm **zero
rows**. This check paid for itself: it found a stale session from an unrelated incident.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T4 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T5 — Hyperdrive's query cache is not invalidated by writes (~75 s)

**Looked true:** the sign-off failed — the question is still hidden from students right after clearing it.
**Actually:** the read was cached. The same question published unflagged returned `200` at t+0 s.
**The check:** verify a write with a **direct `SELECT`**, not through the API. ⚠️ And warn the operator:
someone who clears a flag, sees nothing, and reaches for **Publish changes** to force it will trigger the
*destructive* verb — which re-raises the flag and silently undoes their own sign-off.

⚠️ **Addendum 2026-09-27 — the same cache stales a server-side GATE, not only a verification read.** The playground's archived rule (`409 batch_archived`) read its guard row with a plain `SELECT` through Hyperdrive, so a tab opened before archiving saved **and published** on the archived session for ~30–90 s, and a just-reopened session still read as archived. Any read that decides whether a write is allowed must bypass the cache: include a STABLE function (Vibhaga-API#56: `AND now() IS NOT NULL`) or use a cache-disabled Hyperdrive binding. *(Phase 5 critique, Vibhaga-Admin#87.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T5 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T9 — The publish response is not load-bearing, but recording ids first is

**Looked true:** you can recover a bad publish from the response.
**Actually:** ids are **client-generated**, so they exist before the request. If the response is lost, the
ids are still recoverable four other ways — but only if you wrote them down.
**The check:** record `question_id`s **before** publishing. See the rollback runbook.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T9 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T13 — The R2 mechanical gate catches OCR-confusables, NOT a wrong digit

**Looked true:** the born-digital gate works — seed a corrupt fixture, it fires.
**Actually:** measured on a real page — `37 → 3S` **fires**, `37 → 31` produces **zero findings**. The gate
is a control against *glyph-confusable* corruption only. Seed only the confusable case and you will
wrongly conclude you are protected against transcription error.
**The check:** a red-team fixture must include a **digit-for-digit** case, and its expected result must be
recorded as **"blind"** so nobody later reads the pass as coverage.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T13 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T14 — `hasSwallowedMarkup` is `false` on an odd number of `$`

**Looked true:** the swallowed-markup gate catches unbalanced maths delimiters.
**Actually:** `Take $\pi as 22/7. Find $x$.` returns **`false`** — so the *instruction line* silently
renders as maths with no warning.
**The check:** an even-`$`-parity check is a **separate, mandatory** gate. Do not treat
`hasSwallowedMarkup` as covering delimiter balance.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T14 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T25 — "A separate agent turn" is not something one agent can do to itself.

**Looked true:** S2b §6 asks for two transcriptions at different dpi and crop framing, "in a separate
agent turn, with no access to A". Run 2 varied both, produced B, and B agreed with A on every token of
both pages. Two independent passes, perfect agreement — the strongest possible result.
**Actually:** the agreement is worthless as evidence. One context wrote both. Having just written A, the
reader cannot unsee it, and cannot distinguish "B re-derived this glyph" from "B recalled it". §6 names
this exact failure — *"the same model, in the same context, shown the same pixels, will reproduce its own
misread"* — and then proposes a mechanism that changes the **pixels** and not the **reader**.
⇒ **Two of the three decorrelation levers are self-serve; the load-bearing one is not.** A transcription
whose second pass came from the same context must be recorded as **one channel**, and the F-R1 fixture
pass over it recorded as **blind** (T13). Genuine independence has to be *delegated* — the orchestrator
spawns a separate agent for B and hands it the renders and nothing else — or bought from a different
algorithm entirely (see T26).

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T25 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T30 — `$`-parity and `hasSwallowedMarkup` never look INSIDE the delimiters.

**Looked true:** the two mandatory markup gates (**T14**) cover authored maths.
**Actually:** both only inspect delimiter *structure*. `Find $\fract{1}{2}$ now.` has balanced `$`, is
swallowing nothing, and **passes both** — then KaTeX throws and the child sees red error text. Measured
with the repo's own `katex@0.17.0`.
**The check:** compile every `math` segment with the repo's own KaTeX at `throwOnError: true` as a
**third** gate. It is three lines, and it is the only one of the three that can see a mistyped macro.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T30 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T34 — Paper-faithful part labels are a defect when you onboard a subset.

**Looked true:** transcribe the paper's own scheme (S5 §3.4, as written), so a question shipping printed
parts `III` and `IV` is labelled `III`, `IV`.
**Actually:** the student has no paper. Run 4 shipped one question whose parts read **`III, IV`**, one
**`b) I…III`** with no `a)`, and one **`I, IV, V`**. Every part faithful, every answer correct, and three of
seven questions presented as broken — the owner's first reaction on seeing them. **Nothing was wrong with
the content**, which is exactly why no content gate could see it.
**The check:** label for the reader, not for provenance — **contiguous from the start of the scheme, over
the parts you actually shipped**. Traceability belongs to `question_number` and to S7's manifest.
⇒ **Owner ruling, 2026-08-14:** *"students never see the paper — they are the customer."* Now S5 §3.4 and
S13's **C9**.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T34 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T56 — A checksum detects drift WITHIN a repo. Nothing was comparing the two repos.

**Looked true:** the Admin↔Web renderer lock-step is enforced — three (now four) byte-identical files plus
`SHARED_CONTRACT_SHA256` committed in both repos, hashing all of them, itself included, and a critique
failed to defeat it in **36** attempts across two rounds.
**Actually:** the mechanism compares each repo to **its own** committed constant. Phase 1 grew the shared
table from **143** to **161** vectors and added a **fourth** shared file (`ContentMarkdown.tsx`) in Web
only. Admin stayed at 143 across three files. **Both repos' suites were green**, each against its own
checksum, for a whole release — the exact divergence the lock-step exists to prevent, invisible to it,
because nothing ever compared the two constants to each other. `diff`-ing the files across repos was
documented as "the five-second check" and was therefore a *human* step in a mechanism sold as automatic.
**The check:** treat the shared checksum as a **cross-repo** constant, not a per-repo one — the cheap
version is `shasum` over the shared files in both checkouts (or `grep SHARED_CONTRACT_SHA256` in both) as
part of any change to the contract, and the real fix is one CI job that fails when the two values differ.
⇒ **Ask what a tripwire compares. A hash of a file against a constant in the same commit cannot see a
second repo.** *(`decisions/0012`, `technical/content-text-syntax.md` Lock-step.)*

⚠️ **AND IT HAPPENED AGAIN THE NEXT DAY, IN A NEW PAIR, WITH THIS ENTRY ALREADY WRITTEN.** markdown Phase 3
extracted the VDD **paint grammar** into `src/components/diagram/{colors.ts,colors.test.ts}` — a *security*
rule — with the same self-masking digest, and then asserted in **6 places** (`colors.test.ts:23-24`, both
`AGENTS.md`, the plan, `technical/diagram-dsl-spec.md`, and Web's commit message) that *"a one-sided edit
fails CI in the repo that was NOT edited"*. It does not, and the proof is three commands: append one comment
line to **Web's** copy, recompute **Web's own** digest, run both suites → **both green, `diff -q`
DIVERGED** (Web 44/44 · Admin 1066/1066 when first measured; Web 780/780 · Admin 1090/1090 when re-measured
the next day). What the digest catches is *"edited one of the two files and forgot the
constant"* **inside one checkout**; the one-sided fix it was sold as preventing sails through.
⇒ **The second time a mechanism is copied, its LIMIT must be copied with it** — and the limit belongs in the
test that embodies it, as an assertion rather than a paragraph: `colors.test.ts` now has a test asserting that
its own digest function reads only `join(HERE, name)` and no sibling path, so a green tick cannot be read as
"both apps enforce the same rule". Either build the cross-repo job or write **discipline**, in every one of
the sites that describes it.
⚠️ **THAT ASSERTION IS ITSELF A SOURCE GREP, AND ITS RESIDUAL IS RECORDED RATHER THAN CHASED** (2026-08-22):
it string-matches the body of `paintContractDigest` for `join(HERE, name)` and refuses `../Vibhaga-(Web|Admin)`
and a `*SIBLING*` env var — three shapes somebody thought of. A determined edit can pass all three and still
read a sibling path (another spelling, a variable, a `readdir`), so the green tick means *"nobody wrote one of
those three shapes"*, not *"this digest cannot reach a second checkout"*. Executing the digest under a faked
filesystem would say more, but `colors.test.ts` is one of the two **checksummed, byte-identical** files: every
edit costs a re-copy and a recomputed digest in **both** repos, so the residual was written into
`Vibhaga-Admin/AGENTS.md` instead and the file left untouched. ⇒ **when the fix costs more than the risk,
record the residual where the next reader will look — and say which choice you made.**
*(`Vibhaga-Admin/src/components/diagram/colors.test.ts` — "cannot see a second checkout, so it cannot detect
cross-repo drift".)*
⚠️ superseded 2026-09-26: `colors.ts`, `colors.test.ts` and `vdd.ts` are deleted — the grammar and schema
moved to **`@vibhaga/shared/vdd-schema`** (DevTuskers/Vibhaga-Shared, tag-pinned), so this pair's whole
problem went away with the second copy. The trap itself stands; the surviving byte-identical diagram pair
is `vddFieldVectors.ts` + `lockstep.test.tsx`.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T56 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T61 — A security fix that makes two surfaces disagree, and the review surface stated the opposite of what a student gets.

**Looked true:** an authored VDD colour outside the paint grammar is refused where an AUTHOR can act on it
(Admin's zod schema fails the document, and the review surface says so) and neutralised where a CHILD would
otherwise lose a published figure (Web's renderer paints the default ink). *"Same security outcome, failure
mode chosen per audience"* — written in 5 places and it reads like care.
**Actually:** measured on the **same stored document** in real Chromium, **Admin drew no `<svg>` and printed
*"…not valid VDD, so a student sees no figure here"* while Web drew the figure with the stroke neutralised to
`rgb(31,41,55)`** — and **0** off-site requests on both sides. So the security outcome really was identical,
and the only difference was that the sentence on the attestation surface was **false**: a student sees the
figure. Three more faults came with it: the documented rationale ("the author must be told the document is not
publishable") was false — `Vibhaga-API` types `diagram_dsl: z.unknown().optional()` and `publish.ts` writes it
**raw**; the author was never told **which** value was refused, because `parseVdd` discards `safeParse`'s
issues, so the carefully-worded message was unreachable from every screen; and it fired on legitimate
`color-mix(in srgb, red, blue)`. A fourth, latent: `KEYWORD = /^[a-z]{3,24}$/` admits `inherit`, and with
`canvas.background: "inherit"` under a planted ancestor `background-image` **Chromium issued the GET** — so
the comment claiming a bare identifier *"cannot reference a URL"* was false as written.
**The check:** when one rule is enforced on two surfaces, **render the same input on both and compare what a
human is told**, in a browser, with request interception — the security half (`0` requests) and the copy half
("what does this say happens?") are different assertions and both are cheap. If a divergence is kept, the
copy must describe what actually happens **on that side**. And a refusal nobody can read is not a refusal:
name the value, its path and the mechanism on the surface the author uses.
⇒ **"Fails safe" is not a property of a schema; it is a property of the sentence the human reads.**
*(`Vibhaga-Admin/src/components/diagram/colors.ts` — `refusedPaintsIn`, moved 2026-09-26 to
`@vibhaga/shared/vdd-schema`; `StudentPreview.tsx` —
`FIGURE_PAINT_REFUSED_NOTE`; `e2e/preview-visibility.spec.ts` — "draws the figure, names the refused value,
and fetches nothing".)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T61 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T70 — A "settle" by sample-equality is a race, and a gate that reds at random is a gate people re-run.

**Looked true:** `e2e/focus-ring.spec.ts` — the gate T67 and T68 built — waits for the `box-shadow`
transition before reading, which is one of the three things it says it does that the blind gates did not.
Its `settle()` samples the computed `box-shadow` every 25 ms and returns as soon as two consecutive samples
are **equal**.

**Actually:** two equal samples do not mean "finished", they mean "did not change in 25 ms" — and under
load both samples land before the transition has advanced at all, so `settle()` returns the **pre-transition
base**, which then equals the recorded `base` and the control is reported as having no indicator. Measured
at one HEAD on an **idle** machine, the whole file run twice: **1 of 2 runs failed**, always the same way —

```
controls with no focus indicator with the Preview panel open
Received: BUTTON "Flag for review — question 1"  [self 1:1, behind 1:1, shadow rgba(0,0,0,0) 0 0 0 0, …]
```

`rgba(0,0,0,0) 0 0 0 0` is `Button`'s unfocused `shadow-none`: the sampler never saw the ring at all. It
fails **safe** — a real regression still reds — which is exactly what makes it dangerous: a gate that reds
at random is a gate people re-run, and re-running is how the next real regression gets waved through.

⇒ **Wait on the ANIMATION, not on the sampler.** Two `requestAnimationFrame`s so the transition exists,
then `Promise.allSettled` over `el.getAnimations().map(a => a.finished)`, then two more frames so the final
computed style is committed. ⚠️ `Animation.finished` **rejects** when a transition is cancelled (the next
Tab moves focus away), so it must be `allSettled` and it must be raced against a hard ceiling or an
infinite animation added later hangs the gate. ⚠️ **And the BASELINE needs the same treatment**: the
unfocused stamp is read straight after a `blur()`, which starts its own 130 ms transition, so a mid-flight
"base" is a value no later read can equal. ⚠️ **And there was a second copy** of the same sample-equality
loop in the named-control test — one settle implementation, or the fix is half a fix.

*(`Vibhaga-Admin/e2e/focus-ring.spec.ts` — `SETTLE_FN`.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T70 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T74 — A gate whose coverage and whose false positives are measured at DIFFERENT severities is green when it blocks nothing.

**Looked true:** the markdown gate's acceptance test printed `73/77 surfaced · 0 false positives` on
three independent sets, and every number reproduced. Two severities existed by design — `block` refuses
a publish, `advice` is recorded — and both were exercised by real rows.

**Actually:** the test counted **coverage with `gateFlags`** (a finding at *any* severity) and **false
positives with `gateBlocks`** (blocking only). Nothing asserted that a single finding was blocking. So
the one-line mutant

```js
const block = (code, detail) => out.push({ code, detail, severity: "advice" });
```

produced a **byte-identical green run** — `73/77 · 0 · 0 · 0`, `PASS` — over a gate that refused nothing
at all. Pointed at a batch of seven fields every layer is meant to catch, the real gate reported
`7 BLOCKED` and exit 1; the mutant reported `0 BLOCKED` and **exit 0**, i.e. publish. The reverse was
equally unguarded: promoting the two deliberate advisories to `block` was also green, so the *decision*
to make them advisory was untested in both directions.

⚠️ **The generalisation, which is the useful half: a metric pair chosen for two different purposes will
be chosen at two different strengths, and the gap between them is invisible in the output.** Coverage
wants the broadest signal (did we notice it at all?); false positives want the narrowest (did we
actually stop anyone?). Both readings are defensible in isolation and their combination asserts nothing.
The same shape appears wherever a test has a "detected" count and a "blocked" count, a "warning" and an
"error", or a "reported" and an "enforced" tier.

⇒ **The checks:**

1. **Assert the ENFORCED set, and name every exemption.** Coverage is `filter(gateBlocks)`, with an
   explicit allow-list of the rows that are intentionally advice-only — five here, each with its reason
   in the same table. A row that leaves the list is a regression; a row that no longer needs to be on it
   must be **deleted from the list**, or a stale exemption implies coverage that is no longer needed.
2. **Add an end-to-end assertion that the gate REFUSES something.** A fixture batch of known-corrupt
   fields, asserted to come back non-zero. That single line kills the mutant above, and it is the only
   check here that tests the thing the gate is for.
3. ⚠️ **Mutate the SEVERITY, not only the logic.** A mutation run that deletes predicates and flips
   comparisons will not find this: the predicates are all still there and all still fire. `block →
   advice` and `advice → block` belong in the mutant list of every two-tier gate.
4. ⚠️ **A cap, a fixture set and an allow-list are all self-referential and all need a mutant each.**
   Measured in the same pass: deleting any of the six OD-15 caps, emptying the named legitimate set to
   `[]`, and replacing the allow-list's `has()` with `() => true` were **all green**. Each needed its own
   guard — an over/under fixture pair per cap, a minimum length on the legitimate set, and an exact
   equality between the number of unflagged rows and the size of the allow-list.
5. ⚠️ **Some defects are invisible to any behavioural assertion, and need a COST assertion instead.**
   This gate's normaliser carried a quadratic regex (`/^\s*\|?[\s:|-]+\|?\s*$/`) whose linear
   replacement (`/^[\s:|-]+$/`) accepts **exactly the same language** — verified over 300 000 random
   strings, zero disagreements — so every count was identical either way while the old one took
   **1 958 ms** on a 50 000-character field. An absolute millisecond budget measures the machine that
   ran it, so assert the **scaling ratio**: 4× the input costs ~4× linear and ~16× quadratic.

*(`Vibhaga-Docs/.devin/skills/_maths-onboarding/markdown-gate.mjs`; markdown Phase 5, 2026-08-22.
Companion to **T60** — a test that performs the wiring it verifies — and to **T68**, which is the same
error in a different metric: asking whether an indicator *differs* rather than whether it can be *seen*.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T74 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T77 — A migration that writes the published row but not the STAGED DOC reverts itself on the next publish.

**Looked true:** the content is migrated. `SELECT` shows the new markdown in `sub_questions.text` and
`questions.question_text`, a gate passed the bytes read back out of the database, and the row rendered
correctly in a real browser. Phase 6 checked all of that and was right about all of it.
**Actually:** an onboarded question exists in **two stores** — the live content rows **and** the onboarding
job's **staged document**, which is what the Admin card renders and what `POST /publish` upserts *from*.
The migration wrote the first and not the second, so:

| | staged doc (what the reviewer sees) | published row |
|---|---|---|
| `sub_questions.text <id>` | `Square \| ................` — **no delimiter row** | `\| Square \|  \|` |
| `questions.question_text <id>` | no `---\|---` | has it |

Two consequences, and the second is the dangerous one. **(a)** The review card rendered the *old* text —
correctly, because without a delimiter row it is not a table — so the owner would have signed off dot-runs
while believing they were approving the migrated table. **(b)** ⚠️ **Pressing `Publish changes` would have
overwritten the migrated rows with the stale ones**, silently undoing the migration, with every gate still
green and no error anywhere.

**The check:** after **any** write that does not go through the Admin UI — a migration, a repair, a direct
`UPDATE` — **diff the staged doc against the published rows before a human is asked to review**
(S11 §4.7). And prefer to make the edit in the **staged doc** and re-publish, which is the path that keeps
both stores in step by construction; that is what runs 3 and 4 did for their `question_number` repairs.
⇒ **This is T35's family — the review surface disagreeing with what is stored — reached by a new
mechanism.** T35 said *enumerate every field the batch populated*; T77 adds *and every store that holds it*.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T77 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T96 — A schema-legal field the renderer ignores is a figure that lies.

**Looked true:** the VDD schema accepts `label` on an `angleMark`, so labelling a right angle is supported.
**Actually:** for `variant: "right"` the renderer **never draws the label** (`VddRenderer.tsx:182-187`).
`safeParse` passes, the document is legal, the figure renders — **and the label is silently gone**. That is
S6's founding failure class (*"figure silently missing an element"*) arriving through the schema rather than
through the canvas.
**The check:** ⚠️ **Legal is not rendered.** For every element type and every variant, confirm the fields you
set actually appear in the output SVG — a `safeParse` pass proves the document is well-formed, not that it
draws what you wrote. ⇒ Step 2 also found **no italic on `text`** and **no per-segment stroke width**.

⚠️ **A pair-render sweep then found EIGHT MORE, two of them live in the shipped batch:** `arrow.headSize`
(**ignored, live ×3**), `defaults.fontFamily` (**ignored, live ×9**), `rotation` (**ignored on 11 of 15
element types**), `arc.sweep`, `z`, element `opacity` on fills, `defaults.opacity`, and `groupId`/`link`.
All schema-legal, all `safeParse`-clean, all silently dropped at render. ⇒ **The gap between "the schema
accepts it" and "the renderer draws it" is a SURFACE to sweep, not a bug to fix once.** Render each element
type twice — with and without the field — and diff the SVG. That is how all nine were found.

⚠️ **The "no way to say not to scale" complaint was WRONG, and the correction matters more.** The actor
reported drawing an angle at 41.6° and labelling it 20°. Measured off the printed figure's own
`get_drawings()`: **the paper prints x = 41.72°, y = 48.28° and a "110°" drawn at 131.58°** — **the source is
not to scale, and the VDD reproduced it to 0.15°.** Reproducing the paper's own scale error is correct
behaviour. And VDD *can* say it: four other figures in the same batch place free `text`. ⇒ **Before recording
a tool limitation, check that the tool actually lacks it — a self-accusation is as unreliable as a
self-verification (T25).**

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T96 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T98 — An `angleMark` label can render on the OPPOSITE SIDE of the vertex, and it is live in the spec's own golden fixture.

**Looked true:** an `angleMark` with `label: "58°"` draws its arc at the vertex and its label beside that
arc. T96 already swept the fields the renderer *ignores*; a field it *honours* is fine.
**Actually:** the label position is `bis = ((from + to) / 2) % 360` (Admin `DiagramRenderer.tsx:176`, Web
`VddRenderer.tsx:181`) — the **arithmetic mean of two angles in `(-180, 180]`**, which points the wrong way
whenever the two rays differ by more than 180°. The arc is correct (`arcPath` normalises the sweep); only
the text moves. **Measured 2026-08-26 in real Chromium on `/diagtest`, on the DSL spec's own §7.1
`TRIANGLE` fixture** — the one the tests and the sandbox are built on: at vertex `B`,
`angleOf(A,B) = -98.75°`, `angleOf(C,B) = 172.69°`, difference **271.44°**, so `bis = 36.97°` and the
`58°` label renders **outside the triangle, below-right of B**, where the true bisector is **-143.03°**.
Reading order alone would attach it to the wrong angle on any busier figure. ⚠️ Swapping `from` and `to`
does not help — the mean is symmetric.
⚠️ **PROSPECTIVE, NOT LIVE — and the first write-up of this trap implied otherwise.** Measured 2026-08-28
over every stored `angleMark` in production: **6 of them, and 0 meet the condition.** The largest span is
**99.94°** (a live figure's `angB`, labelled 125°), and the three `variant: "right"` marks are exactly 90°.
⇒ **No student is looking at this defect today.** It is reproducible in the DSL spec's golden `TRIANGLE`
*fixture*, which is a test/sandbox artefact and not published content. The word *"live"* in the first
version of this entry would have been read as *"in production"*, and that was wrong.

```sql
WITH f AS (SELECT diagram_dsl d FROM questions WHERE diagram_dsl IS NOT NULL
    UNION ALL SELECT diagram_dsl FROM sub_questions WHERE diagram_dsl IS NOT NULL
    UNION ALL SELECT diagram_dsl FROM answers      WHERE diagram_dsl IS NOT NULL
    UNION ALL SELECT diagram_dsl FROM sub_answers  WHERE diagram_dsl IS NOT NULL)
SELECT count(*) AS angle_marks, max(span) AS max_span, count(*) FILTER (WHERE span > 180) AS t98_hits
FROM f, jsonb_array_elements(d->'elements') e, LATERAL (SELECT abs(
        degrees(atan2((e->'from'->>1)::float - (e->'vertex'->>1)::float,
                      (e->'from'->>0)::float - (e->'vertex'->>0)::float))
      - degrees(atan2((e->'to'->>1)::float   - (e->'vertex'->>1)::float,
                      (e->'to'->>0)::float   - (e->'vertex'->>0)::float))) AS span) x
WHERE e->>'type' = 'angleMark';        -- 2026-08-28: 6 · 99.94 · 0
```

⚠️ **Keep it anyway, and keep it prospective.** It costs one line in a render check, the condition is
mechanical, and the next figure with a reflex or a wide-span mark meets it. ⇒ **The general shape: a defect
with zero current instances is still worth a named check when the check is cheaper than the audit that
would find it later.** Say *"0 instances today"* rather than dropping it, and never say *"live"* about
something measured in a fixture.

⚠️ **A FIX WAS IN FLIGHT WHEN THIS WAS WRITTEN, AND THAT DOES NOT RETIRE THE CHECK.** Measured
2026-08-26: `origin/main` and `HEAD` carry the mean at **Admin `:176` / Web `:181`**, and both repos'
**working trees**, on a branch called `fix/vdd-renderer-silent-field-drops`, already carried
`const bis = bisectorDeg(from, to, el.reflex);` (Admin `:387`, Web `:395`) — **uncommitted**. ⇒ **Re-grep
before citing either line**, and treat the row as *"which of the two is deployed right now?"* rather than
as a fact. ⚠️ **And do not delete the check when the bug goes**: the bug is one instance of a class
(**T96**) whose surface has to be swept per element type and per field, and a label in the wrong *place* is
invisible to a sweep that only asks whether a field was *dropped*.

**The check:** ⚠️ **read the label's own `x`/`y` out of the SVG and confirm it lies inside the angle it
names** (S6b §4.2 has the `page.evaluate()` snippet). Condition to test for:
`abs(angleOf(from) - angleOf(to)) > 180`. The fix in a document you author is a separate **`text`**
element positioned on the true bisector (measured: the label moved into the angle when that was applied).
⇒ **T96 said "legal is not rendered"; this is its sibling — RENDERED IS NOT RENDERED WHERE YOU MEANT.** A
sweep for dropped fields cannot find a field that is honoured and misplaced, so both sweeps are needed.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T98 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T99 — Collapsing collinear strokes into one element is right; the side you drop while doing it is invisible to every check you have.

**Looked true:** a printed figure's strokes map to VDD elements, so drawing them and counting them against
your intent list is enough. Collapsing `AC` + `CE` into one `line A→E` through C is *better* than two
elements, because the renderer then cannot hinge them apart.
**Actually:** measured while S6b was being written, on the worked example in S6a §4 — six printed strokes
(`AB AC BC BF CD CE`) were collapsed into three `line` elements, and **`AB`, the vertical side of the
triangle, was simply never written.** `VddDocument.safeParse` passed. `checkDiagram()` returned `[]`. The
element count matched the intent list, because the intent list was written by the same reader who dropped
the side. The rendered figure was a *different, entirely plausible* figure — a triangle `BFC` instead of a
right-angled `ABC` with a ray `BF` — and it was found **only by looking at the render**.
⚠️ **And a second element was missing for a different reason, on the same figure.** The printed
**right-angle mark at B** is a `type: "fs"` white-filled rectangle, and the exploratory dump had filtered
`get_drawings()` to `type == "s"`, so the claim set asserted the angle was *"not marked on the page"* and the
drawing omitted the mark. ⇒ **Two mechanisms, one symptom:** an element you collapsed away, and an element
you never saw. Both pass `safeParse`; both change what the figure says.
**The check:** ⚠️ **count against the CLAIM SET, never against your intent** — and make sure the claim set
was written from a dump that filtered nothing (S6a §2.1). S6b §5.2: every `segments` entry in the claim set
must be *covered* by some element (an element whose endpoints are the two named points, or a
`line`/`polyline` on which both lie), every `labels` glyph must appear in exactly one element, every mark
claim must have an element, and no element may be unaccounted for. That check is text-only — claim set plus VDD JSON, no picture — so a
second agent can run it. ⇒ **This is T25 applied to drawing:** an inventory you wrote yourself is not an
independent check of your own work, and *"I counted my elements"* is exactly that.

⚠️ **AND THE SHAPE RECURRED INSIDE THE TOOL BUILT TO CATCH IT, WITHIN A DAY.**
`audit-claim-set.py`'s parser folded any line under `claims:` with no `|` into the *previous* claim's
`note`. Strip the separators from one claim and it **vanished** — 71 assertions, **0 failures, exit 0** —
and S12 §3.2 gates a handoff on exactly that exit code. Found by a critique, not by the self-test, because
every `F-CLAIM` mutation had been a *wrong* claim and none had been a *malformed* one. Now a claim-shaped
line without separators is a hard parse error, and the footer prints `claims parsed: N`.
⇒ ⚠️ **A silent-deletion defect will reappear in the checker you write for it, because the checker's input
is also a document that can lose a line.** Two rules that generalise: **count what you parsed and print
the count**, and **make one mutation MALFORMED, not merely wrong** — a validator that has only ever seen
well-formed bad input has not been tested on the failure mode it exists for.

⚠️⚠️ **AND THE FIX WAS ITSELF THE SAME BUG, ONE LEVEL DOWN — WHICH IS THE MOST USEFUL PART OF THIS ENTRY.**
The repair tested the *shape of the id*: `if the first token does not match [A-Z]\d+[a-z]? then this line
is a note continuation`. Measured the next day against the real worked example, injecting a pipe-less claim
line: **`k24` · `K24.` · `(K24)` · `KK24` · `K24ab` · `K-24` · `24` · `k4b` — 8 of 8 silently swallowed**,
each producing a report **byte-identical to the clean one**. ⚠️ **So "count what you parsed" did not catch
it either: the count was unchanged**, because the smuggled line never became a claim to count.

⇒ ⭐ **THE RULE: A NEGATIVE TEST FAILS OPEN ON EVERY SHAPE YOU DID NOT ENUMERATE; A POSITIVE TEST FAILS
CLOSED.** *"If it does not look like X, treat it as Y"* is a promise about the infinite set of things that
are not X, and you cannot enumerate that set — every mis-typed, mis-cased, bracketed or punctuated id is a
new hole. Invert it: decide what a line **is** from something structural you control, then require the
rest. Here the structural fact is **where the line starts**: the first content line under `claims:` sets the
claim indent, every line at or left of it **is** a claim and must have its separators, and a note
continuation must be a real hanging indent (≥ 6 columns further in) — anything between is refused as
ambiguous rather than guessed. Re-measured across **20 id shapes × 5 indents (0, 2, 4, 6, tab) = 100
combinations: 0 escapes**, and a genuine wrapped note still parses.
⇒ And note *where* the class hides: the same shape is in **S1b's regime chain** (a first-match-wins `if`
ladder whose final `return "R2"` is a negative test — **T17**), in **T93's** OCR filters, and in this
checker's own `else` for unknown predicates, which is now a failure rather than a skip. **Whenever you
write "otherwise, assume", write down what you are assuming about the set you did not name.**

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T99 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T104 — The wrong answer that agrees with its own figure. No gate this suite owns could have caught it, INCLUDING the one nobody has built yet.

**Looked true:** the stored answer follows from the stored diagram, the diagram's `a11y.description`
describes the diagram, and the `approach` states facts that are all individually correct — so the question
is internally coherent and **every gate passes**.

**Actually:** a published grade-10 question drew a heavy segment
**between** an open −2 and a filled 2 and answered `$-2 < x \le 2$`, while the paper prints two
**outward** rays and means **`x < −2` or `x ≥ 2`** — *the exact complement*. It had been live and
**human-signed** (`verified_at 2026-07-04T13:07:23Z`) for eight weeks.

⭐ **THE FINDING IS THE GATE TABLE, NOT THE DEFECT.** Every gate this suite owns was **run against the
defective document** and each one passed it. Measured 2026-08-30, not asserted:

| gate | what it said about the WRONG Q15 | why it is blind |
|---|---|---|
| `VddDocument.safeParse` | ✅ **valid**, 24 elements | it validates *shape*. A heavy line from −2 to +2 and a heavy line from −2 to −∞ are the same schema |
| `checkDiagram()` | **`[]` — not one advisory** | ⚠️ **it has TWO checks, and BOTH are gated on the same thing** — a labelled-vs-drawn angle comparison per `angleMark` (`Vibhaga-Admin/src/components/diagram/validate.ts:34-47`) and a triangle angle sum over exactly three numeric `angleMark` labels (`:49-57`). Both need an `angleMark` carrying a numeric label. **A number line has no `angleMark` at all**, so the only semantic gate in the codebase **cannot fire on this class of figure by construction** — 60 lines, one element type |
| `markdown-gate.mjs --fields` | **0 BLOCKED** | it checks markdown deletion and delimiter hazards. `$-2 < x \le 2$` is perfectly well-formed markdown — and perfectly wrong |
| KaTeX compile (**T30**) · S9 `G4` `$`-parity · `hasSwallowedMarkup` | all pass | `-2 < x \le 2` is valid LaTeX with even `$` and no swallowed markup |
| S11 (structural audit) | would **reconcile perfectly** | it asks *did it land*, never *is it true* |
| `stagedQuestionSignature` / **T77** drift | **no drift** | equality between two stores says nothing about either being right |
| ⭐ **an answer-vs-figure self-consistency check** — *the obvious thing to build* | ⛔ **WOULD HAVE PASSED IT TOO** | the figure drew `-2 < x ≤ 2`, the answer said `-2 < x ≤ 2`, the `a11y.description` said *"the segment **between them** highlighted"*, and the `approach` named exactly the two facts that were right. **Four artefacts, mutually consistent, all four wrong.** |

⚠️ **The last row is the entry.** The natural response to a wrong answer beside a wrong figure is *"add a
check that the answer follows from the figure"* — and that check was **already satisfied** by the defect.
**A self-consistency check is not a correctness check.** S8 §0.5 already says this about two *derivations*
of one answer; this is the same failure one level up, across four *artefacts*, and it is worse, because the
four look like independent evidence.

⭐ **AND THE DECISIVE EVIDENCE WAS A DIRECTION, WHICH NO DATABASE COLUMN RECORDS.** What settled it was
`page.get_drawings()` on the source page: path **#31** is a **1.4173 pt** stroke running x **78.01 →
161.80** (i.e. −4.883 → **−2.000**, *leftwards*, into the arrowhead), and path **#33** is `type:"s"` with
`fill=None`. Nothing in `questions`, `answers`, `diagram_dsl` or the staged doc stores *which way the
printed ray ran*. ⇒ **A defect whose evidence exists only outside the system cannot be gated from inside
it.** The only thing that caught this was S13 — an independent read of the source page.

⇒ **The checks:**

1. ⭐ **Before building a gate, ask what the defect's evidence IS and whether the gate can see it.** Write
   down the single datum that settles the case; if it is not a column, a file or an HTTP response the gate
   can reach, the gate cannot fire and building it buys a false assurance. **This is the question that
   would have stopped "answer-vs-figure consistency" being proposed as the fix.**
2. **The gate that WOULD work, and it is cheap:** for a figure carrying an S6a **`axis` / `interval`**
   claim set, **sample points** — parse the answer's inequality and test the claim set's `interval`
   membership at each labelled tick. It runs off the *stored* VDD plus the *stored*
   `final_answer_latex`, needs no page, and **it fires here on one point: 0 is on no heavy part and
   `-2 < x ≤ 2` contains 0.** (This is S8 §3's "second method" as a machine check —
   [S6a](../skills/read-figure-claim-set/SKILL.md) §3.2 owns the `interval` predicate.)
3. ⛔ **ITS PRECONDITION IS THE WHOLE POINT: an S6a CLAIM SET MUST EXIST.** The claim set is the only
   artefact that says *what the printed figure means*, independently of the drawing. **Without it the
   check degenerates into comparing the drawing with itself** — which is exactly the passing
   self-consistency check above, wearing a different name. ⇒ **"We will add the sampling gate" is not a
   plan unless S6a ran.** A figure with no claim set is not gateable for correctness, and that fact should
   be reported as a limit rather than left to be discovered by a student.
4. ⚠️ **State a semantic gate's SCOPE, or an operator reads `[]` as "the figure is fine".**
   `checkDiagram()` is **two** checks, and both are gated on an `angleMark` with a numeric label
   (`validate.ts:34-47`, `:49-57`) — so it is silent on
   number lines, sectors, grids, patterns and area models: **9 of the 20** figures live when
   [S6a](../skills/read-figure-claim-set/SKILL.md) §3.5 took its census (2026-08-26; **22** live today) fall in
   classes it cannot reach at all. An undocumented scope makes an empty
   result look like a clean bill of health (**T102**, one level up: there the gate had no *input*; here it
   has no *jurisdiction*).
5. **Read the page.** Every other row of that table was cheap and green; the one thing that worked cost a
   `get_drawings()` call on the PDF.

*(Found 2026-08-30 by S13 `critique-onboarded-content` auditing three grade-10 questions from the retired
`Vibhaga-Ingestion` pipeline. The corrected answer, figure and `a11y` are live today; the wording of S8 **§4.1b** is the worked `approach` half of this entry.
⚠️ **The signature was destroyed by the fix, and that was the point, not the cost** — it attested to the
complement. Companion to **T94/T100** — a defect no check was looking for — and to **T13**: three of the
gates in that table had never been watched fail on *this class* of figure, so "they pass" was a claim.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T104 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T114 — A gate's summary line that is computed AFTER a display filter cannot fail, and looked exactly like one that can

**Looked true:** `measure-inline-math-width.mjs … --min 9999` printed *"… · 0 CLIP (at or over the field's box)"* on every
Phase-4 batch, so the round's width gate was green nine times.
**Actually:** `clips` was incremented inside the loop that printed rows, and `--min` filtered the rows BEFORE that loop, so
with `--min 9999` nothing was counted and the line always said 0. The batch outcome happened to be right (re-measured at
`--min 0` across all 983 live fields / 1 775 runs: 0 CLIP — because the authors and the S13 critiques had run at `--min 0`),
but the gate the actor was reading was decorative — **T13**'s shape (a gate never observed to fail) wearing a measured
number. Found by the run-10 author, who got "0 CLIP" at 9999 and "1 CLIP" at 0 on the same file.
**The check:** a summary count is computed over ALL inputs before any display filter; CLIP rows are always printed whatever
`--min` says (fixed 2026-09-06); and every gate you add gets a fixture you have SEEN fail through the same command line you
will use in anger — `--min 9999` on a known-clipping field must say 1.
*(S9 gate block, S8 §6 #10.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T114 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T125 — A question figure's `a11y.description` can state the answer the item asks for

**Looked true (run 13, S13 chunk I-11-20, 2026-09-10):** the a11y checks (S6b §0.3/§3.3, vdd-check item 2, S13 C4)
verify the title is real and the description non-empty — i.e. *the figure is honestly described*.
**Actually:** the stored concave-octagon figure on a "count the acute and reflex angles" item described itself as
*"the four tips are acute (about 72 degrees each), the left and right points are obtuse (about 106 degrees), and the
two notches are reflex (about 290 degrees)"* — a screen-reader student is **read the classified answer** that a
sighted student must still work out vertex by vertex. Every green a11y gate passes it because the text is accurate;
the failure is that it is accurate *about the answer*, not the apparatus.
**The check:** for a **question** figure, read `a11y.title` + `description` against the item's own ask — if the item
asks for a count/classification/measure, the description must carry shape and direction without naming the classes
or stating the counts (the asymmetry with §3.2's answer-figure rule — *"the title must state the answer"* — is the
point: question describes the apparatus, answer states the result). Report as MINOR (pedagogical leak, not a wrong
answer) unless the item is otherwise unusable without the leak.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T125 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T128 — A correct "never" rule applied beyond its real constraint manufactures its own defect

**Looked true (run 13, S6b ii01a/ii01b, 2026-09-11):** T-S6b-6 says a figure cannot be bilingual (one
`diagram_dsl`, one `text.value`), so the claim-set labels and drawings removed every Sinhala word — the
tally table's 3 column headers + 5 row names, the pictograph's 5 day names — and declared stem prose bound
them by position instead.
**Actually:** the constraint is *bilingual*, not *Sinhala*. These questions are mono-medium Sinhala — no
second-medium sibling will ever render the figure — so stripping structural labels left a printed table's
header row and label column EMPTY on the student's page: a figure that no longer matched the paper and
needed a prose paragraph to stand in for ink. The owner saw it instantly. The paper's own
`සෙවසතුවක්`-as-`ඝනවස්තුවක්` ruling the same day is the text-side twin: fidelity governs *content*, not
misspellings — a printed non-word resolves to the standard textbook term (declared), while a real variant
(`ගණත`, `හාවිත`) stays as printed.
**The check:** before applying a `never`/`always` rule, name the constraint it protects and test whether
this case trips *the constraint* (here: a second medium consuming the DSL — impossible), not just the
literal wording. vdd-check's hygiene rule is now medium-aware (`--medium sinhala`) — ⚠️ *superseded
by ADR 0021 (T-QG-12): drawn text is simple English on every medium, the flag no longer widens it* —
and claim sets carry
`budget:`/`allow:` so build-staged can run the whole suite without per-figure flag juggling.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T128 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T136 — A constructed claim set that "passes" Audit A because you read its footer, not its exit code

**Looked true:** ten constructed answer-figure claim sets, each run through `audit-claim-set.py` in a shell loop with
`| tail -4` — every footer read *"recognised, NOT verifiable here: …"* and the loop's own exit code was 0.
**Actually:** every one of the ten had **exited 1**. `tail` swallowed the failures, and a `for` loop's exit status is
its last command's (the `tail`). The failures were format, not content, and all three are specific to a `constructed`
set written from run 1's template: (1) a `labels:` inventory with no `label "<glyph>" names <target>` claim per glyph
(the tool checks glyph → claim closure — run 1's sets bound every declared label); (2) `points:`/`segments:` declared
with an empty `anchors:` block — a constructed figure has no PAGE anchors, so the **canvas** coordinates go in
`anchors:`, exactly as the tool's own `SELF_TEST_CONSTRUCTED` fixture does, and Audit A then verifies the `equal` /
`right` / `parallel` / `on` / `ratio` / `angle` claims against them instead of skipping them; (3) `derive` values must
be exact to 1e-9 (`80 / 60 = 1.3333` fails; `80 * 3 = 240` or `216 * 216 / 3 = 15552` passes — pick an expression whose
value is exact).
**The check:** never pipe a gate through `tail`/`grep` without capturing `${PIPESTATUS[0]}` (or run it once per file
and print `exit=$?`); and for a constructed set, fill `anchors:` with the canvas coordinates you will draw at — it turns
Audit A from a parser into a geometry check (62–97 assertions per figure on the run below).

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T136 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T142 — The playground publish raises the flag on the ROW, not in the staged doc

**Looked true:** every playground publish forces `needs_human_review = true` (0018 OD-2), so after a publish "the question is flagged" everywhere. The onboarding flag verbs mirror into the staged doc and say so (`staged_doc_updated`).
**Actually:** the publish response has no `staged_doc_updated` field, and the server does not write the forced flag back into `playground/<id>/questions.json`. A doc saved with the flag down stays down in R2 while the live row is up. The Phase 5 page then showed a flagged, withheld question as green "Published" after a reload. It was fixed client-side by `persistPublishOutcome` (Vibhaga-Admin#87), and any other client (curl, script, agent) reopens the hole.
**The check:** after every real publish, PUT the doc back with `published: true` and the flag `true` on every id in `question_ids ∪ reflagged ∪ reraised`. Then GET it and assert both fields per id. `playground-publish.py publish` does this (read-back 1) before its SQL read-back. Cited by `generate` §1/§4. *(Phase 5 critique finding; tool guard added in Phase 6, 2026-09-27.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T142 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

## T-QG-1 — The skill that never loaded: frontmatter that is not valid YAML is dropped silently

**Looked true:** `skills/draw-and-verify-question-vdd/SKILL.md` was committed alongside the other seven
skills, so the CLI loads it like the other seven.
**Actually:** `devin plugins info` listed **7 of 8** skills — the file was silently skipped, no error at
install. The first suspect was size (57.5 KB vs ≤ 46.5 KB for every loading skill), so the file was split
— **and the 38 KB SKILL.md still did not load**. The size hypothesis was wrong. The real cause: the
`description:` was a **plain scalar containing `constructed channel: the geometry…`** — an unquoted
`: ` inside a plain scalar is a YAML mapping error (*"mapping values are not allowed here"*), and a skill
whose frontmatter does not parse is dropped with no error, no warning. The fix was two lines:
`description: >-` (a folded block) and nothing else.
**The check:** two gates — count the skills in `devin plugins info` after adding or editing a SKILL.md,
and the **`check-suite.py` frontmatter lint**, which runs `yaml.safe_load` on every
`skills/*/SKILL.md` + `agents/*.md` frontmatter and requires non-empty `name`/`description` strings (for
skills, `name` must equal the directory name). Quote or fold any description that contains a colon.
⚠️ **The wrong-hypothesis split was kept** — `reference.md` holds the long-form material and SKILL.md is
smaller for it; a wrong theory can still leave a good diff, but a second guess after the first one fails
is a loop, not a fix: when the explanation doesn't predict, instrument the parse, not the file.

*Source: this plugin — observed 2026-09-30 on `skills/draw-and-verify-question-vdd` (7 of 8 skills in `devin plugins info`).*

---

## T-QG-2 — The claim set agreed with itself: the audit can't see a figure built to its own record

**Looked true:** the generated cuboid's claim set recorded `ratio len AB / len BC = 1.5`, the anchors
agreed, `audit-claim-set.py` reported a pass — so the figure was right.
**Actually:** the stem said **5:2**. The claim set had been written down from the *drawing*, not from
the stem — Audit A then recomputed every numeric claim against the very anchors that carried the same
wrong value and found self-consistency, so the render it gate-kept passed too. A claim set authored
from its own figure is a tautology: every check inside the loop agrees, and the only witness that could
disagree — the stem's own numbers — was never consulted. That is why `audit-claim-set.py` now REQUIRES
a `stem:` header on every `constructed` set and refuses a `ratio`/`angle` claim whose value the stem's
numbers (or a transitively backed `derive`) do not justify.
⚠️ **The stem-pair check alone has a hole: the incident stem itself stated 5, 3 AND 2 — and
`3 / 2 = 1.5` IS stem-justified.** Three further checks close it (review R1 + critique R3):
**LABEL-RATIO** — a ratio claimed on segments carrying numeric labels (`label "5 cm" names DC`)
must equal the *labelled* numbers' ratio; **MIS-CITATION** — a `derive Kn` cited in the note must
exist *and* match the claimed value; and the **DRAWN-VS-LABEL pair check** — every *pair* of
segments carrying numeric labels must have a drawn anchor ratio equal to the printed ratio, so the
forge that claims 1.5 on the *unlabelled parallel* edge while "5 cm"/"2 cm" print on the other face
still fails (the labels are ground truth the claim cannot route around). A deliberately
foreshortened edge — an oblique-projection depth edge — is declared by naming its *label claim's*
id in `ambiguous:`. (And the dodge that binds the numeric labels to names `segments:` never
declared — a face diagonal `AC` — fails outright: a two-capital label target must be a declared
segment, so the pair check can always measure it.) This is why `cuboid` (and
`house_pentagon`/`rectangle_points` where labels exist) claim the ratio on the
**labelled** segments. And it is why `tools/vdd_templates.py`
exists at all: a template takes the stem's numbers, refuses any parameter the stem never states
(`require_stem`), computes the geometry FROM them, and emits the claim set itself — there is no hand
step where the drawn ratio can be copied into the claims.
**The check:** for any figure a template can build, build it — the numbers come from the stem by
construction. For a hand-built claim set, write every `ratio`/`angle` value from the STEM text first,
then draw to it; if the drawing you have in mind doesn't match the stem's numbers, the drawing is
wrong, not the stem. Never read a value off the canvas back into a claim (that is the draw→claim→audit
loop that passed 1.5 vs 5:2). Cited by `figure-templates` and `generate` §4.

*Source: this plugin — the 2026-09-29 cuboid incident; the audit change landed in W0 (`audit-claim-set.py`
check 2d) and the templates in W3.*

---

## T-QG-3 — The label metric that never saw the math label: KaTeX overlays are HTML, not `<text>`

**Looked true:** a five-sided figure with four `<text>` side labels and one `math` label passed
every gate — `vdd-check` reported its label metrics clean, the render audit passed, so the figure
was signed off.
**Actually:** two independent blind spots hid the same defect. (1) DiagramRenderer draws a `math`
element as a **KaTeX HTML overlay** inside the figure's `[role="img"]` container — not an SVG
`<text>`, not a `<foreignObject>` — so vdd-check's label metric (a `svg.querySelectorAll("text")`
walk) never measured it at all. (2) vdd-check renders in a bare harness with no `--font-sans`
variable, while DiagramRenderer's text stack is `var(--font-sans, …)` — so a **serif KaTeX face
sitting among sans `<text>` labels**, and a math label drawn **−2.5 px into a stroke**, both
passed every gate. Measured on the 2026-09-29 house-pentagon figure (described synthetically —
no stem text, no ids): `font mix: KaTeX math ×1 + text ×4` plus the math label's centre inside a
slant edge. The same render also showed text labels clipped to 4.7 px from the canvas edge and
sitting 1.3 px off strokes — invisible to every check that ran.
**The check:** `tools/visual-check.mjs` renders through the real Admin `/diagtest` page — real
`globals.css`, real next/font (Inter + Noto Sans Sinhala resolve `--font-sans`), real
`html[data-theme]` — and its in-page measurement collects *both* `<text>` runs and `.katex`
overlays, converting overlay client-rects through `svg.getScreenCTM().inverse()`. Rules:
`font` (any math+text mix or two text faces → FAIL), `stroke` (a math label's bbox is measured
against strokes like any other label). Cited by `visual-check`.

*Source: this plugin — W4, 2026-09-30; the stored production figure failed on first real render
through `/diagtest`.*

---

## T-QG-4 — The drift check that never saw the answer: the read side knew a narrower shape than the write path

**Looked true:** a playground publish loop ended `published 4/4`, `read-back 1: staged doc confirms
4 published + flagged`, `provenance: 4 id(s) · OK` — then `t77: 4 question(s) · 92 comparisons ·
12 mismatch(es)`, every line `Q<n>.<part>.sa[<id>]: live row not in staged`. The run read as FAILED.
**Actually:** those live `sub_answers` rows WERE the staged ones — the printed ids matched the staged
doc's uuid5 `sub_answer_id`s exactly. `build-staged.py` emits a part's answer as the singular
`sub_answer` object (the shape `publish.ts collectSubAnswers` accepts beside `answers[]`), but
`t77-staged-vs-published.py` collected staged sub-answers only from `s.answers` — so every
sub-answer the publish wrote looked unclaimed, and none of their approach/final/diagram_dsl fields
were ever compared (92 vs the correct 128 comparisons). Question level needed no fix: build-staged
emits only `answers[]` there and the API reads only that.
**The check:** t77 now folds `s.sub_answer` ahead of `s.answers[]` — `collectSubAnswers`' own order —
before comparing. A staged doc carrying BOTH keys for one answer still flags (the duplicate pops the
live row once, then reports `missing live`), which is the double-insert refusal the staged schema
warns about. Pinned by `tests/test_t77_sub_answer_shapes.py`.

*Source: this plugin — W6, 2026-10-02; found on the first publish of a batch whose parts all carried
the singular form.*

## T-QG-5 — The label row that disagreed with the verdict: one rule, three measurements

**Looked true:** visual-check reported a number-line figure `verdict: PASS` with `findings: []` —
while its own per-width label rows said `ok:false` at 375 and 768 for every point label.
**Actually:** the `target` rule is a canvas-unit invariant (a point label >1.5×fontSize from its
own point), but the DOM box was re-measured at every render width and px quantisation moved the
distance across the bound — 26.8u at 320, 27.5u at 375. Rows folded each width's measurement; the
finding sampled only width[0], so the same label both failed and passed.
**The check:** one target result per label, computed on the least-quantised width, now governs the
rows and the finding alike (`visual-metrics.mjs`); `build_number_line`'s point-label lift was
retuned to the measured DOM box reach (~0.5·fontSize, not the text-run bound) — pinned by
`tests/test_visual_metrics.mjs` and `tests/test_vdd_templates.py`.

*Source: this plugin — W8 dogfood, 2026-10-02.*

## T-QG-6 — The revocation check that saw zero rows: policy-less RLS hides `auth.*` entirely

**Looked true:** Q3's direct `count(*)` over `auth.sessions`/`auth.refresh_tokens` returned 0 —
"a clean logout".
**Actually:** RLS is enabled on `auth.users`, `auth.sessions` and `auth.refresh_tokens` with **no
policies**, so any role that is not BYPASSRLS sees zero rows — sessions or no sessions. A plain
reader role cannot observe revocation at all.
**The check:** Q3's `actor_exists = 1` guard is what caught it — the same reader saw zero users
too, so `ok` went false instead of silently passing. The fix is `qgen.q3(actor uuid)`, a
counts-only SECURITY DEFINER function owned by postgres (one-time setup: generate step 11); the
reader gets USAGE on schema `qgen` + EXECUTE, never a grant on `auth.*` — and never BYPASSRLS.

*Source: this plugin — W9, 2026-10-03.*

## T-QG-7 — The gate chain that never ran the markdown gate

**Looked true:** build green, validate clean, `--session` previews clean, published — the doc
was fine.
**Actually:** a display-math run written `$$…$$` on ONE line mid-paragraph round-trips to
`$…$` under the renderer's parser and flags `displayMathInline` — and NONE of build, validate,
publish, or either visual-check ever ran `markdown-gate.mjs`. Only the critic's standalone
`--fields` invocation caught it, one round in.
**The check:** run-gates `build` now runs the gate itself — it writes `<run>/fields.json` (the
same field set `run-gate.sh`'s `fields_py` produces: stems + sinhala, part texts, every
approach/final) and any `BLOCKED` field stops the chain before publish ever sees it. Shape that
passes: `$$` and `$$` on their OWN lines around the math. A gate that lives only in the critic's
hands is a story for TRAPS, not a safeguard.

*Source: this plugin — W9 run, 2026-10-03.*

## T-QG-8 — Two variants of one blueprint read as one question to a student

**Looked true:** a blueprint is a parameterised question — instantiate it twice with different
seeds and the batch has two different questions.
**Actually:** same stem, same parts, same figure kind — only the numbers differ. On the page a
student sees the same question twice. (Owner ruling 2026-10-03.)
**The check:** `build-staged` refuses a batch where two questions carry the same `blueprint_id`
— at most one variant per blueprint per batch. Instantiate the second variant in a LATER run:
across sessions variants count as distinct, so `precritic-lint --existing` may still WARN a
fresh variant against a row from another session — expected, read the WARN and move on.

*Source: this plugin — W10d, owner ruling 2026-10-03.*

## T-QG-9 — The floater sweep that can never land in the pocket it was given

**Looked true:** `finish()`'s `_near` floater search tries 16 directions × fixed 6-unit steps
around the anchor — if a clear spot exists near the dot, the sweep finds it.
**Actually:** it only finds spots its fixed-step grid happens to hit. A coordinate-plane point
surrounded by grid lines leaves a clear pocket that is a thin SLIVER — (cell − label − 2×
clearance) ≈ 1–6 units tall centred mid-cell — and the sweep steps past it at every distance.
`stroke-clearance rule rejected 112 of 112` meant "your sweep granularity never sampled the
pocket", not "no pocket exists". Same trap for labels that must sit between a segment and a
neighbouring anchor (`own-anchor` eats everything outside a narrow band).
**The check:** labels whose legal positions are pockets between strokes — grid-cell letters on
`coordinate_plane`, the `MN` foot letters and `"3 cm"` value on `parallel_lines` — are placed as
FIXED texts by `_pick_label_spot`, which evaluates candidate centres against exactly the rules
`finish()` will apply (stroke gap, label gap, own-anchor) and picks the best. `_near` floaters
stay for spots with real freedom (endpoints, axis letters) — the origin's `O` and `0` are
pocket-seated too, because a floater's sweep stacked `O` on top of `0` (W11 review).

*Update 2026-10-04 (owner ruling):* a point letter may sit **over** the faint ruling lines when
the pockets run out — "if they are visible, that is fine". `coordinate_plane` keeps the
clear-pocket search as pass 1; only when a letter (or the `O`) seats nowhere at any size does a
fallback pass treat the `gv*`/`gh*` ruling lines as non-obstacles (axes, ticks, joins, dots,
labels and the edge still count), and then ALL the figure's letters draw in the accent colour
`#1d4ed8` — one ink per figure — with a `describe` claim recording it. `vdd-check` and
`visual-check` exempt exactly those ids (the structural marker — never colour or width) from the
label↔stroke rule, and `finish()`'s pre-flight does the same. The old measured-limit refusal
(`x_max ≥ 7` refuses with `grid`+letters) is gone: the whole 10×10 envelope builds; a refusal now
means even the fallback found no seat.

*Source: this plugin — W11, 2026-10-04.*

## T-QG-10 — Clearance scales UP in units, the target rule does NOT

**Looked true:** a label placed `clearance + padding` units from a stroke is safe — the padding
is tiny and the stroke rule is the tightest one anyway.
**Actually:** `_clearance_units(px, span)` converts rendered px to canvas units at ~`px/s`
(s = 294/span once the figure outgrows the plate), so on a wide canvas "8 px clear of the axis"
becomes a ~19-unit gap. visual-check's **target** rule measures a short label's distance to the
nearest painted geometry in CANVAS units and fails past `1.5 × fontSize` — it does not scale.
The two rules squeeze from opposite ends: `bar_chart` category labels sat ~23u under the
baseline (fail >21u) and the coordinate plane's `"0"` at the numeral-column corner sat ~29u
from the origin (fail >22.5u — the diagonal seat multiplies the required gap by √2).
**The check:** any fixed label 1–2 glyphs long must be seated with BOTH constraints in the
score: stroke/label gaps ≥ the scaled clearance AND box-to-nearest-paint ≤ `1.5·size`. The
"0" shares the point-letter pocket search for exactly this reason; corner seats that must
clear two perpendicular strokes can be unreachable — seat it hugging ONE axis instead.

*Source: this plugin — W11, 2026-10-04.*

## T-QG-11 — `| inferred` unhooks a value from the stem with no trace

**Looked true:** a `reads P v on XY` claim's evidence word is bookkeeping — `stem` means the
stem states it, `inferred` means it doesn't — and either way the VALUE is still checked.
**Actually:** the stem-justification check only bites on `ev stem`. Flipping `reads A 4 on OY`
from `| stem` to `| inferred` in a stem-mode claim set passed the whole audit — the value was
then justified by NOTHING (measured and verified on a W11 stem-mode coordinate plane).
**The check:** in a `constructed` set a `reads` claim whose evidence is not `stem` FAILS unless
the set carries the read-the-figure declaration — a `describe` claim whose text says the values
are "figure content". Both W11 figure modes emit that line word for word; a set in stem mode
never does, so a flipped evidence word dies. (Same round: a `parallelMark`'s chevrons are real
strokes — the transversal crosses every line AT ITS CENTRE, so a mark's default `at` = 0.5 sits
on the crossing; the builder probes `at` positions until the marks clear it and MN by 8 px.)

*Source: this plugin — W11 review round 1, 2026-10-04.*

## T-QG-12 — The medium-conditional label rule that shipped a figure a second medium cannot render

**Looked true (first G7 run, session f040ebb5, 2026-10-04):** T-S6b-6 as rescoped made drawn label
language a function of the question's `medium` — so on a sinhala-medium run the Q5/Q6 bar charts
shipped with Sinhala category names and axis titles, and every gate (`medium='sinhala'` builder
check, `vdd-check --medium sinhala` rule 3) passed them as correct.
**Actually:** a figure is one `diagram_dsl` consumed by whichever medium renders it — a chart whose
categories are Sinhala can never be reused or previewed on an English surface without redrawing, and
the Sinhala-shaping/KaTeX risks stayed live in review surfaces that render it regardless of scope.
The rule that was meant to protect the mono-medium case also *blessed* the content that defeats
re-use. ADR 0021 closes it: **every piece of text drawn in a figure is simple English on every
medium** — point letters, labels, axis/category/series/value titles, units, card/ring texts. The
a11y `title`/`description` are not drawn and keep the question's medium.
**The check:** `_check_label_texts` (vdd_templates.py) and `vdd-check.mjs` rule 3 refuse any
codepoint U+0D80–U+0DFF in drawn text unconditionally — the message names the label and cites
`diagram text must be simple English (ADR 0021)`. `--medium` is still accepted (other checks and
the flag's callers keep working); it no longer widens the label rule.

*Source: this plugin — W12, 2026-10-04 (session f040ebb5, Q5/Q6 bar charts).*

## T-QG-13 — The wide frame that starved the overlap, and the region label "far from its target"

**What happened (W14, `venn_sets`).** Two traps in one template. (1) Two five-letter words in A∩B
refused at every radius up to 150 units although the lens holds them at 130 standalone: the
universal rectangle carried the full label-band padding on its LEFT and RIGHT too, the canvas grew,
the clearance in units grew with it (T-QG-10), and the lens lost more than the bigger circle gave.
Side padding only has to keep the frame off the outlines — the label bands are top and bottom.
(2) A one-token count seated at its region's roomiest point is ~30 units from every outline, so
visual-check's `target` rule (a label within 1.5 × fontSize of what it names) failed every Venn
count: the rule assumes a label names a STROKE, and a region item names an AREA.
**The check:** the venn frame's side pad is `clr + 6`; region tokens bind `label "g" names
region_<key>[_j]`, and `visual-metrics.mjs` skips the `target` rule for exactly those `region_…`
targets — edge and stroke still measure them, no `allow:` line is involved, so nothing else is
waived. A trefoil's overlap regions hold about one short token each at a readable size; the
template says so when it refuses.

*Source: this plugin — W14, 2026-10-05.*
