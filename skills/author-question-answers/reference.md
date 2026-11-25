# author-question-answers — examples and troubleshooting

[Operational rules](SKILL.md). Open this reference for examples or to diagnose a failure.

## Number-line answer example

### ⭐ 4.1b The `approach` that was TRUE and still produced a wrong answer — read this one

⚠️ **A published, human-signed answer once shipped the exact COMPLEMENT of the right answer, and its
`approach` contained nothing false.** Synthetic retelling of the shape: the figure is a number line
open at −2, filled at 2, with two heavy parts running **outwards** — the set is `$x < -2$ or
$x \ge 2$`. The shipped `approach` read `Open circle at -2 (excluded), closed circle at 2
(included).` and the shipped `final` was the bounded interval between them.

| what it says | true? |
|---|---|
| there is an open circle at −2, and open means excluded | ✅ true |
| there is a closed circle at 2, and closed means included | ✅ true |
| *(nothing about which way either heavy part runs)* | — **the omission is the defect** |

The two facts it states are correct. The fact it never states — the **direction** each heavy part
runs — is the one that inverted the answer: an `approach` naming two endpoints and stopping reads as
the **bounded interval between them**, and the stored figure and `a11y.description` were consistent
with that wrong reading, so every gate was green.

⇒ **The rule, and it generalises past number lines:**

1. ⭐ **An `approach` that lists the parts of a figure is not an `approach`. State what the parts
   MEAN for the answer.** *"Open at −2, closed at 2"* is an inventory; *"both heavy parts run
   outwards, so the set is …"* is a method.
2. ⚠️ **Name every load-bearing property, including the ones that are about DIRECTION, ORDER or
   ORIENTATION** — the properties a reader supplies from habit if you leave them out. A bounded
   interval is the *default reading* of two named endpoints, so silence about direction is not
   neutral: **it asserts the default.**
3. ⚠️ **A partial `approach` is not a partial answer, it is a wrong one.** Nobody reads *"open at
   −2, closed at 2"* and asks *"…running which way?"*. Judge your `approach` by what a reader will
   conclude from it, not by whether each clause survives a fact-check.
4. **Test it with one point.** Take a value your `approach` does not mention and ask whether the
   reader would put it in or out. **0** settles the example in one step: on no heavy part, and the
   bounded interval contains it. That single point falsifies the wrong answer — the §3 second-method
   rule.

## Spatial reasoning example

##### ⚠️ The spatial-reasoning temptation, and why it does not fire

A former third limb — *"the reasoning is spatial and prose cannot LOCATE the construction"* — was
demoted to a negative: it never fired on a real item, its entire evidence was a refusal, and two
independent critiques reported it pulling on answers that should not have one.

**The refusal, worked:** a rectilinear step shape whose perimeter comes from *"the rectangle that
just encloses it"*. That phrase **locates the construction uniquely in words**, so the answer is
prose plus a value. Three different items of that shape would each fire on a naive *"could a diagram
help?"* — and three enclosing-rectangle figures would be three redundant figures.

⇒ **The test, when you feel the pull:** write the construction as one sentence. **Unambiguous ⇒ no
figure.** Drawability is NOT the objection; redundancy is. It re-promotes to a limb on a positive
instance, not on an argument — if you meet one where the construction genuinely cannot be located in
a sentence, record it for the lead.

## 5. Traps — stories with the catch

Cross-cutting traps: [`docs/TRAPS.md`](../../docs/TRAPS.md). These are this skill's own.

### T-S8-1 — The badge that means nothing
**Looked true:** the row says `status = 'verified'`, so the answer has been checked.
**Actually:** publish hardcodes `'verified'` on every answer it writes — and it *must*, because
`solvableExists()` requires it and nothing could ever promote an `unverified` row. The status is a
*servability* flag wearing the word "verified". The real marker is **`verified_by IS NULL`**.
**The check:** ask `verified_by`, never `status`.

### T-S8-2 — The re-publish that un-signs a human
**Looked true:** re-publishing a question refreshes it harmlessly.
**Actually:** publish `DELETE`s and re-inserts the answer sub-tree, so a human's `verified_by` is
destroyed. The server **re-raises `needs_human_review`** whenever it is about to — which is right,
and also means a no-op re-publish of a signed card silently pulls it out of the student feed.
**The check:** re-publish only what you actually changed, and read `reflagged` back from the publish
response. A re-publish that changes anything at all — one character of one `approach` — still
destroys every sign-off on that question.

### T-S8-3 — The answer that publishes into a void
**Looked true:** the answer was authored and the question published, so the student can reveal it.
**Actually:** if the `answer_id` was not a valid UUID, the mapper `continue`d past it — silently. The
question row exists, `answers` has no row, `solvableExists()` is false, and the question is **absent
from the feed and every browse count** with nothing reported.
**The check:** after publishing, count the rows, do not trust the response:
`SELECT count(*) FROM answers WHERE question_id = '<id>';`

### T-S8-4 — The empty answer that says "solvable"
**Looked true:** an answer row exists, so the question has an answer.
**Actually:** an empty row (no approach, no final, no diagram) makes `WorkedAnswer` render `null` —
but still satisfies `solvableExists()`. The student finds the question, taps Reveal, gets an empty
panel.
**The check:** §6 check 5. A run that makes it non-zero has shipped a dead end.

### T-S8-5 — The self-consistent derivation
**Looked true:** the answer was recomputed independently and matched, so the numbers are right.
**Actually:** the recompute started from the same numbers, so a wrong input propagates through both
passes into a beautifully consistent wrong answer — published with a verified badge.
**The check:** method 2 must be *structurally* different (§3). If you find yourself checking your
arithmetic, you are checking the wrong thing.

### T-S8-6 — The flag that hides the question you just fixed
**Looked true:** the flag was cleared, so the question is live — but the student page still 404s.
**Actually:** Hyperdrive's query cache is not write-invalidated for **~75 s** (**T5**). The read is
stale, not wrong.
**The check:** verify with a **direct `SELECT`**, then wait. ⚠️ **And warn the operator**: someone
who clears a flag, sees nothing, and reaches for **Publish changes** triggers the *destructive* verb
— re-raising the flag and silently undoing their own sign-off (T-S8-2).

### T-S8-7 — Authoring `steps` because the field is still there
**Looked true:** `answers.steps` exists in the schema and Web still renders it.
**Actually:** the editor was removed, the Admin client **deletes** `kind`/`steps` from every answer
on save, and the Web renderer survives only for pre-existing rows. Author one and it is stripped on
the next save through the UI — silently.
**The check:** `jq '[.. | objects | select(has("steps")) | select((.steps|length)>0)] | length'` →
`0`. Put the working in `approach`, multi-line. (`build-staged` refuses unknown keys, so the build
path cannot produce one.)

### T-S8-8 — The answer that describes the figure it should have been
**Looked true:** the answer is written, `final` is non-empty, the row is not empty, every check
passes, and the student sees prose. Nothing anywhere reports a defect.
**Actually:** the sentence in `final` is a **description of an artefact**, because the answer *is*
the artefact and there was no instruction to draw it — an answer field containing an instruction to
the student to draw the answer. **Invisible to every gate in both directions**: `isEmptyAnswer` is
false, `solvableExists()` is true, the markdown gate passes, and the absence of a figure is not a
defect any check looks for.
**The check:** §6 check 8, and §4.5's limb-A test on your own draft: *read the sentence you just
wrote and ask whether it states a value or describes a picture.* If it describes a picture, draw the
picture.
