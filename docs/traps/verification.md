# Verification traps

[Trap index](../TRAPS.md).

<a name="t56"></a>

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

<a name="t61"></a>

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

<a name="t70"></a>

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

<a name="t74"></a>

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

<a name="t114"></a>

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

<a name="t-qg-1"></a>

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
