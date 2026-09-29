---
name: author-question-answers
description: Author a verified-looking worked answer that is actually right — derive it independently (D3), confirm it by a genuinely second method, and fit the whole thing into `approach` + `final` in content.yaml (emitted as `approach` + `final_answer_latex` by build-staged; the `steps` array is dead). Provenance goes to the working notes, never to `approach`, which students read; `verified_by` is never written by anything but a human clicking "Mark reviewed". Use when writing, checking, correcting or reviewing the answer/solution/marking of a generated maths question.
argument-hint: "[question number or part]"
---

# Author a question's answers

> **Moved from Vibhaga-Docs `.devin/skills/author-question-answers` @08c09a9; paper-only sections removed (see docs/MIGRATION.md).** There is no marking scheme and no source paper — every answer is a D3 independent derivation (§3).

**Consumes:** the stems/parts being authored in `content.yaml` (the `generate` skill's spec).
**Emits:** `approach` + `final` per leaf — emitted by `tools/build-staged.py` as `answers[{answer_id,
approach, final_answer_latex}]` on part-less questions and `sub_answer{sub_answer_id, approach,
final_answer_latex}` inside each leaf sub-question — plus `ingestion_metadata.needs_human_review =
true`, which the builder sets on every question.

> **The one failure this skill owns: a wrong answer wearing a verified badge.** Every answer publish
> writes lands with `answers.status = 'verified'` — an `unverified` status would make the question
> permanently unservable (`solvableExists()` requires `'verified'` and nothing could ever promote
> it). So the badge is not evidence, and the only thing standing between a hallucinated method and a
> child revising from it is what you do in §3.

---

## 0. Non-negotiables (read first)

1. **Everything you derive ships `needs_human_review: true`.** `build-staged` sets
   `ingestion_metadata.needs_human_review: true` on every question it emits — publish reads it via
   `truthyFlag`, which **fails closed** (`truthyFlag(undefined)` is `false` … wait, inverted: an
   *absent* flag publishes UNFLAGGED and student-visible, so the builder setting it explicitly is
   what keeps D3 honest). **D3 + OD-4**: a derived answer may not publish unflagged.
2. **Never write `verified_by`. By any route.** Publish deliberately never stamps it, and the *only*
   act that does is a human clicking **"Mark reviewed"** in Admin. The promise is
   **`verified_by IS NULL` ⇒ no human signed this**. Breaking it costs the platform its only trust
   marker.
3. **Provenance goes in the working notes, never in `approach`.** `approach` is rendered to the
   student verbatim. "Derived by agent; cross-checked by substitution" is an operational note, not a
   teaching sentence.
4. **`approach` + `final_answer_latex`, and nothing else.** The worked-`steps` editor was removed;
   the Admin client *strips* `kind`/`steps` from every answer on save. Do not author one — and
   `build-staged` refuses unknown keys, so it cannot slip through anyway.
5. **Two independent routes to the answer, always** (§3). A single derivation that checks out against
   itself is the failure with extra steps: *"self-consistency is the trap, not the safeguard."*
6. **Never re-publish to "refresh" an answer.** Publish `DELETE`s and re-inserts the whole answer
   sub-tree, which destroys `verified_by` — the server compensates by **re-raising the review flag**
   whenever it is about to destroy a human signature. A no-op "Publish changes" on a signed card
   silently un-publishes it from the student's point of view.
7. **An empty answer still makes the question "solvable".** `solvableExists()` only asks whether a
   `'verified'` row exists; the Web `WorkedAnswer` renders `null` when the row has no approach, no
   final and no diagram. A blank answer row puts the question in the feed and shows the student
   **nothing** on Reveal.
8. **Two markup gates, not one** — `hasSwallowedMarkup` **plus** an even-`$`-parity check, because
   `hasSwallowedMarkup` returns `false` on an odd number of `$` (`Take $\pi as 22/7. Find $x$.`
   passes it and the instruction line then renders as maths). `approach` and `final` are two of the
   fields `run-gate.sh` covers. Never Sinhala inside `\text{}`.
9. ⚠️ **Decide, per answer, whether the ANSWER needs its own figure — and the default is NO.** §4.5
   is the rule; it is a decision you make and record rather than one you may skip. ⚠️ **The
   over-eager failure is the more expensive one:** a figure that adds nothing is worse than none — it
   costs the student a second look at a picture they have already read, and a reviewer an
   attestation.

---

## 1. Stable facts — and the three invariants

Code facts worth carrying (re-derive line numbers before citing them — they move):

- **Publish never signs** — `verified_by`/`verified_at` are `null, null` on both `answers` and
  `sub_answers` inserts; clearing the flag via "Mark reviewed" is the signature (three targeted
  `UPDATE`s, no sub-tree delete).
- **A publish that destroys a signature re-raises the flag** (`reflagged` in the response).
- **Malformed answer ids are skipped, not rejected** — `continue; // skip malformed; never block
  publish on one answer`, on both levels (§5a).
- **Whole-question `answers` is not declared in the save schema** — unvalidated and uncapped;
  sub-question answers are capped at 20.
- **The student-visibility filter** is `needs_human_review = false AND status='published' AND
  <verified answer exists>` — assembled via `solvableExists()` in the feed and browse counts.

### ✅ 1.1 The three invariants — a run that makes any non-zero has shipped a silent defect

| # | Invariant | Why zero is load-bearing |
|---|---|---|
| **V1** | Rows with a non-empty `steps` array | the editor is gone and Admin strips `kind`/`steps` on save — a non-zero is working that vanishes between save and publish |
| **V2** | Fully empty rows (no `approach`, no `final_answer_latex`, no `diagram_dsl`) | the row still satisfies `solvableExists()` — the question is in the feed and shows the student **nothing** on Reveal |
| **V3** | `approach` values containing provenance text | `approach` renders to the student verbatim — "derived by agent" in a child's revision notes |

---

## 2. Sourcing: there is exactly one route

No marking scheme, no answer key, no source paper. **D3 independent derivation + a second-method
check (§3) is the only route**, for every answer. If your two methods disagree, **do not publish** —
record the question as unresolved in the working notes and report it to the lead rather than arguing
one method into place.

---

## 3. Independent derivation and the second-method check (D3)

**Method 1** is how you would teach it. **Method 2 must not be method 1 re-run** — that is the trap:
an "independent recompute" recomputes *from the same number* and is perfectly self-consistent. A
second method is one that would produce a *different wrong answer* if the first were wrong.

| Question shape | Method 1 | A genuinely independent Method 2 |
|---|---|---|
| Solve an equation | rearrange and solve | **substitute the answer back** into the original |
| Simplify / evaluate | apply the operator precedence | evaluate numerically at a value, both sides |
| Mensuration (area, perimeter, volume) | the formula | decompose into parts and re-add; **check the units and the order of magnitude** |
| Geometry (angles) | angle chase | independent constraint — angle sum, exterior angle, the figure's own `angleMark` labels |
| Ratio / percentage / scale | scale up | scale back down and confirm you land on the given quantity |
| Number properties (divisibility, Euler) | the rule | enumerate the concrete case |
| Time / date / measure | add the components | convert wholly to one unit, compute, convert back |

**Cheap invariants that catch real errors, every time:** the units come out right; the magnitude is
plausible for the context (a schoolbag does not weigh 71 tonnes); a probability is in [0,1]; a length
is positive; the answer type matches what was asked ("how many metres" is a number of metres, not cm).

**Record in the working notes** (not in `approach`): method 1, method 2, and the fact that they
agreed. If the gate or a later reviewer asks "how do we know", the notes are the answer.

---

## 4. Fitting it into two fields

You author `approach:` and `final:` in `content.yaml`; `build-staged` emits
`approach`/`final_answer_latex` on the right node with a deterministic uuid5 id. Everything below
about the two columns applies to what you type.

### 4.1 `approach` — the method, in the student's language

- **One short paragraph, or a few short lines.** Multi-line is normal and good (§4.1c).
- **Teach, don't announce.** The north star is learning, not answer-checking.
- **Match the question's language.** A Sinhala question gets a Sinhala approach — plain text, maths
  in `$…$`, **never Sinhala inside `\text{}`**.
- **Never** put in it: provenance, "the scheme says", your confidence, a reference to another
  question, or an apology.

Good shape: `Angles of a triangle sum to $180^\circ$: $x = 180^\circ - 125^\circ - 35^\circ$.`

### ⚠️ 4.1a Markdown — `approach` is the field most likely to lose content

`approach` is prose with newlines in a maths corpus — exactly the shape markdown acts on.
**`author-question-text` §3 is the rule set and it applies here verbatim** — `\vert` not `\|` inside
a cell, an empty cell rather than a row of dots, `1)`/`1.`/a bare year at line start, `>` needing
`$>5$`, four-space indent becoming a code block that kills every `$…$` on the line. Two shapes bite
an `approach` specifically:

| you write | ⚠️ what the student gets | write instead |
|---|---|---|
| `x = 3` ⏎ `- 5 = -2` | **a bullet list, and the minus sign is DELETED** | `$-5 = -2$` — which also gives a real `−` |
| `124` ⏎ `+ 295` ⏎ `-----` | a bullet list: **the `+` AND the rule line are both gone** | `$+295$` recovers the `+` but **not** the rule line — for a vertical sum, **use a VDD** |

✅ **What you have gained:** a real table for genuinely tabular working, and a real numbered list for
a genuinely sequential method. Write tables with **edge pipes** (`| a | b |`) — without them a table
is textually identical to prose that became one.

⚠️ **Run the markdown gate over `approach` and `final` as well as over the stem** — `run-gate.sh`
takes every authored field; an answer is not exempt because it is short.

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

### ⭐ 4.1c Lay the `approach` out for a phone — one step per paragraph

⚠️ **An owner ruling on a published answer:** *"format the answer so that students can read it
easily; now it feels cluttered."* The answer was **correct** and passed every gate — it was also one
371-character paragraph. A 15-year-old reads an `approach` on a **375 px** screen, one paragraph at
a time, while working. **Correct is necessary; readable is the product.**

The rules, and each one is a blank line you were about to leave out:

| rule | write | ⚠️ not |
|---|---|---|
| **One step per paragraph.** A paragraph is one idea: one definition, one substitution, one result. Separate paragraphs with a **blank line** — a single newline is only a line break | *the formula* ⏎⏎ *the substitution* ⏎⏎ *the result* | the same three sentences in one paragraph |
| **Every computation on its own line**, one equation per line. A chain of equalities may stay on one line while it fits; a chain of *steps* may not | `$30 \div 15 = 2$` ⏎⏎ `$30 \div 3 = 10$` | `… $30 \div 1 = 30$, $30 \div 15 = 2$, $30 \div 3 = 10$ …` |
| **Given → rule → substitution → result**, in that order, each its own paragraph | what is given ⏎⏎ the formula ⏎⏎ the numbers going in ⏎⏎ the value coming out | result first, justification after |
| **A list is a list.** Five tallies, four cases: one item per line as a `-` bullet list | `- 30 – 34: 4` ⏎ `- 34 – 38: 6` | items joined by `·`, `;` or *"and"* inside a sentence |
| **A table stands alone**: a one-line lead-in, a blank line, the table, a blank line | `The completed table:` ⏎⏎ `\| … \|` | a sentence that runs straight into `\| … \|` |
| **Cap a prose paragraph at ~2 sentences / ~180 characters.** Longer means two ideas sharing a paragraph — split it | | |
| ⭐ **Keep one inline `$…$` run under ~300 px at 375 px** — about 22 digits-and-operators, or 6 comma-separated numbers. Inline KaTeX **never wraps** (`.katex` is `whitespace-nowrap` in both renderers), so a long inline chain is **cut off** at the right edge of a phone. Display math (`$$…$$`) gets a scroll container, but a student scrolling a formula sideways is the last resort: split at an `=` first; state a sum's result instead of listing its terms when a table already shows them | `$\sum fx = 1216$` | `$\sum fx = 96 + 180 + 400 + 396 + 144 = 1216$` |
| **Name what the figure shows before you use it** — *"the cut-out circle passes through O, so its diameter is the radius"* is a paragraph of its own, before the arithmetic. ⚠️ **And name only what the student can SEE** — a helper point from your claim set is printed nowhere on the figure | | the fact buried inside the substitution line; a helper label from your own claim set |

⚠️ **This does not relax §4.1's rules** — no provenance, the student's language, maths in `$…$` — and
it does not relax **§4.1a**: a `-` at line start is a bullet **on purpose** here, so `$-5$` still
needs its dollars, and a table still needs edge pipes and a blank line on each side.

⚠️ **The box and the font size depend on the FIELD, and the estimator does not know that.** On
Vibhaga-Web a stem renders at 18 px in a 301 px box (375 px viewport), a sub-part's text at 16 px in
265 px, a whole-question answer at **14 px** in 301 px, a sub-answer at **14 px in 239 px** (the
disclosure panel's padding), and depth-2 parts lose another ~36 px. ⇒ **Measure, don't estimate,
whenever a run is within ~60 px of its box:** `tools/measure-inline-math-width.mjs --fields
<[{id, field, text}]>` renders every run through the real shared renderer at the field's font size
and reports CLIP / TIGHT / fits; field ids `question_text` · `sq:<id>:text` · `sq2:` ·
`a:<id>:approach|final` · `sa:` · `sa2:` pick the row. The estimator (`run-gate.sh` /
`check-inline-math-width.py`) stays the cheap first pass. Practical rule for a **sub-answer** line:
~15 digits-and-operators — the ~22 above is a STEM number.

⚠️ **A defined term gets its correct definition BEFORE it is used.** *Complementary / supplementary /
adjacent / alternate / corresponding …* — a swapped definition has shipped with the wrong definition
taught in the approach. Check the term against the lesson corpus before you write it into a method.

**Mechanical checks — §6 #9 and #10.** An `approach` whose longest **prose** paragraph exceeds 180
characters is a finding (#9); an inline `$…$` run estimated at ≥ 330 px is a finding and 270–330 px
is borderline (#10 — look at a borderline one in the 375 px preview before deciding). They are smell
thresholds like the figure element budget, not schema limits.

### 4.2 `final` — the answer, and only the answer

⚠️ **`final` must carry its own `$…$` fences, and the markdown gate cannot tell you that.** Bare
LaTeX is valid markdown — it is just text — so a whole batch can pass the gate and still render
literal characters to a student, caught only by `SELECT`ing the live column *after publish*.
⇒ Fence every LaTeX-bearing value, then **compile it** — the gate does **not** run KaTeX.
**"0 BLOCKED" answers one failure mode, not "is this the right format for this column".**

- Shapes: `$x = 20^\circ$`, `$25\,\text{cm}$`, `$x < -2$ or $x \ge 2$`, `3 L 500 ml`, `348, 288`.
  **A value field may hold a disjunction in plain words (`or`), not only a single closed
  expression.** ⚠️ A ~100-character value is a multi-part answer in one field — if yours is heading
  past ~50, ask whether the question is really multipart and the answers belong on the parts (§4.3).
- **It is not LaTeX-only despite the name** — plain text and Sinhala are fine in the same marker
  syntax as everywhere else.
- **Do not add your own `$` wrapper around an already-wrapped value**, and do not wrap plain Sinhala
  in `$…$`.
- **Include the unit** when the question asks for one. `25` and `25 cm` are different answers.

### 4.3 Where the answer attaches

| The question is | Write the answer on |
|---|---|
| single-part | the question's own `approach:`/`final:` — emitted to `answers[]` |
| multipart | **each leaf part's own `approach:`/`final:`** — emitted to that sub-question's `sub_answer`, which is what the student sees folded under that part |

`build-staged` refuses a question carrying both `parts` and a whole `approach`/`final`, and refuses a
leaf part without the pair — decide deliberately which level the answer lives at.

⚠️ **Never put the same answer in both `node.sub_answer` and `node.answers[]`** — they are merged,
the id inserts twice, and the whole publish transaction rolls back (`structure-question-parts` §0.5).

### 4.4 The emitted shape

```jsonc
// emitted by build-staged — you author approach:/final:, the builder mints the ids
{ "answer_id": "…uuid5…", "approach": "Angles of a triangle sum to $180^\\circ$: …",
  "final_answer_latex": "$x = 20^\\circ$", "diagram_dsl": null }
// no `kind`, no `steps` — dead fields
```

⚠️ **A malformed `answer_id` does not fail the publish — it is silently skipped.** A typo'd UUID
publishes the question **with no answer**, which makes it unservable (no `'verified'` row ⇒
`solvableExists()` false ⇒ absent from the feed and every browse count) with no error anywhere. The
builder's uuid5 ids make the hand-typed-UUID class impossible on the build path; on any hand-edited
doc, record ids **before** publishing (T9).

### 4.5 ⭐ Does this answer need a FIGURE? The trigger, and its negative

⚠️ **The capability exists at both answer levels and almost nothing uses it — decide anyway, and
record the decision.** `answers.diagram_dsl` and `sub_answers.diagram_dsl` are built, published,
rendered fields. An answer figure is also the most over-proposed artefact in the suite, so the rule
below is a *gate*, not an invitation.

#### 4.5.1 The question to ask — and it is NOT a keyword

⭐ **Ask what the answer IS, not what the stem SAYS.** Four steps, in this order, per answer —
including per sub-answer:

| # | do this | and then |
|---|---|---|
| **1** | **Write the answer as text first** — `approach` + `final`. ⚠️ **Do not decide about a figure before the text exists**; the text is the evidence | you now have something to test |
| **2** | **Read your own `final`.** Does it *state a value*, *name an object*, or *describe a picture*? | describes a picture ⇒ **limb A**, stop · states a value ⇒ step 3 · **names an object in the question's figure** ⇒ also step 3 |
| **3** | ⛔ **CHECK LIMB B'S THREE PRECONDITIONS FIRST, ALL of them:** **(a)** the stem NAMES an apparatus or method (*"using a number line"*, *"on the graph"*) · **(b)** the figure the student is looking at (§4.5.1a) supplies that apparatus **BLANK** — the answer is not already drawn on it · **(c)** your own worked step *happens on* it. **If any one fails, go to step 4.** Only if all three hold: **name the elements your answer would add**, and write the list down | all three hold **and** at least one named element *carries the answer* ⇒ **limb B**. Any fails, or the list is empty or only labels/highlights ⇒ **no figure** |
| **4** | **Write your method's key construction as one sentence** and ask whether that sentence puts it in exactly one place. ⚠️ If it is a MOTION rather than a place (rotate and count coincidences; unroll the curved surface), ask whether a student can *perform* it from the sentence | unambiguous, or performable ⇒ **no figure** (§4.5.3) |

⚠️⚠️ **STEP 3 WITHOUT ITS PRECONDITIONS FIRES ON EVERYTHING, MEASURED.** An earlier version kept only
*"name the elements your answer would add"*, and applied literally it fired on a large fraction of
figures. **You can always add something** — a highlight of the very thing being read is an addition.
**The gate is not "can I add?" — it is "did the stem hand me a blank apparatus and does my step
happen on it?"** That is why (a)–(c) are conjuncts and the *"what would I add"* list is step 3's
second half.

**The first limb that fires wins. If none fires the answer is text-only, and that is the normal,
correct outcome for the large majority of answers.**

#### 4.5.1a ⚠️ *"The figure the student is looking at"* — which figure step 3 means

> **It is the figure on the level the answer attaches to, OR its parent's, OR a sibling part's —
> whichever the student has in front of them when they read this part.** If there is none at any of
> those, step 3 cannot fire and you go to step 4.

⚠️ **And the converse:** a blank apparatus on the parent does **not** make every part's answer a
limb-B candidate — if no part's stem names the apparatus, precondition (a) fails and all are
correctly text-only.

⚠️ **Why not a keyword list.** A sweep for drawing words (`draw|sketch|construct|shade|plot|mark`)
across real stems returns mostly false positives — "marks" means exam scores, "marked" means priced
at, "drawn to a scale of 1:500" describes the given, and the sharpest real case contained **no
drawing verb at all** in the ask (the verb was in the *answer* text). A keyword list is a negative
test that fails open on every shape you did not enumerate. **The same keyword also carries opposite
verdicts**: *"using a number line"* where the figure is blank and the step is a move on it (✅ limb
B), *"draw a number line and mark …"* with no question figure (✅ limb A), *"write the inequality
represented on the number line"* where the figure already carries the answer (❌ — precondition b),
and a figure-bearing question whose parts never name the line (❌ — precondition a). **The keyword is
identical; the verdict is not.**

#### 4.5.2 The two limbs

| limb | fires when — **all conjuncts** | the test you can actually apply |
|---|---|---|
| ⭐ **A — the artefact IS the answer** | the ask is satisfied by producing a drawing, so there is no value to state | ⭐ **Read the `final` you just wrote** (or `approach`'s last line). If it is a sentence *about* an artefact rather than a value — *"…have been marked on the number line"*, *"Draw 25 dots as 5 rows and 5 columns"*, *"as shown in the figure"* — **the answer is the figure and your text is standing in for it.** Draw it, and let the text shrink to a one-line statement of what the figure shows |
| ⭐ **B — the method is a MOVE on a blank apparatus** | ⛔ **(a)** the stem NAMES an apparatus or method · **(b)** the figure the student is looking at supplies it **BLANK** · **(c)** your own worked step *happens on* it | ⭐ **Only after (a)–(c) hold**, name the elements the answer would ADD. If at least one *carries the answer* — a jump, a shaded region, an open-vs-closed endpoint — limb B fires. ⚠️ **A HIGHLIGHT IS NOT AN ADDITION**, and "an auxiliary line" is struck from the list: it makes every perimeter answer fire |

⭐ **The sharpest discriminator: same figure class, opposite verdicts.** Two items can both be *"a
growing pattern drawn as its first stages"* — the one whose ask is **the general term** (`$3n$`) gets
no figure (a fourth stage adds nothing to a formula); the one whose ask is **the next stage itself**
is limb A. **The figure does not decide it; the ask does.**

#### 4.5.3 ⚠️ The negative, stated plainly

**Most answers must stay text-only.** Do not draw when:

- the apparatus **is not blank** — the figure already contains what you would draw (precondition b);
- **the stem does not name an apparatus for the method** (precondition a — the largest refused class:
  a figure being *present* is not the stem *naming* it);
- your figure would differ from the question's only in **labels or a highlight** — a highlight of the
  thing being read is not an addition;
- the answer is a **value, a set, an equation or an interval in symbols**, or it **names an object in
  the figure**;
- the answer is **tabular** — there is no table primitive in the VDD union; the right channel is a
  **GFM table in `approach`** (§4.1a);
- the answer is a **graph on a grid** or a **ruler-and-compass construction** — those are figure
  classes you should not author either; decline in `content.yaml`.

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

##### ⚠️ Limb B fired, but the addition falls OUTSIDE the question's frame

If the answer's own values fall outside the question figure's range, the answer figure is
**STANDALONE, not extending** — `draw-and-verify-question-vdd` §3.7.1 forbids re-scaling an extending
figure, so draw the apparatus at the range the *answer* needs and say so in the claim set's
`departures:`. Check this before you draw — the apparatus tax does not apply to a standalone figure
and the budget maths changes.

⚠️ **The cost of over-firing lands on people.** An answer figure is a second `<figure>` in the
reveal panel directly under the question's own; a redundant one reads as *the same picture again* —
the student's Reveal buys them nothing and a reviewer is asked to attest a figure that says nothing.

#### 4.5.4 The mechanical probe — for your own draft, and for the batch

The limb-A test is a regex, so a gate can run it (over a staged doc: §6 check 8 — every answer whose
`final_answer_latex` describes an artefact while carrying no figure). ⚠️ **A probe is not the
trigger.** It catches limb A only, because limb A leaves a trace in the text. **Limb B is a
judgement and you must make it per answer** — the probe cannot see an answer that needed a jump drawn
and whose `final` correctly reads `$6$`.

#### 4.5.5 Where it goes, and who draws it

- **The figure is drawn by `draw-and-verify-question-vdd` §3.7, not by you**, from a constructed
  claim set (`read-figure-claim-set` §2.3). **Do not hand-write a `diagram_dsl` into an answer** —
  nothing on the write path validates VDD, and doing it here skips the claim set, the audit and the
  numeric check in one step.
- ⚠️ **`content.yaml` has no answer-figure key yet** — `figure:` attaches only to a question or part
  node (`build-staged` puts it on `diagram_dsl`, not inside `answers`). An answer that needs a figure
  today is a **recorded decision for the lead** (the builder must grow a key, e.g. `answer.figure`),
  not something to hand-patch into `staged.json` — record which limb fired in the working notes.
- **It attaches to the answer, at the level the answer sits at** (§4.3): `answers[].diagram_dsl` for
  a whole-question answer, the sub-question's `sub_answer.diagram_dsl` for a per-part answer.
- ⚠️ **A diagram-only answer is legal and servable**, but **do not empty the row** — keep a one-line
  `final` beside the figure (§0.7).

---

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

---

## 5a. ⚠️ The answer-id key depends on WHERE the answer hangs — and BOTH directions drop in silence

Nothing else in the suite says this, and getting it wrong either way is **completely silent**. The
two collectors each read exactly one key and `continue` on a miss:

| The answer hangs on | The key that is read | A wrong key means |
|---|---|---|
| a **sub-question** (`sub_questions[].answers[]`, or `node.sub_answer`) | **`sub_answer_id`** | keyed `answer_id` ⇒ **skipped** |
| the **whole question** (`questions[].answers[]`) | **`answer_id`** | keyed `sub_answer_id` ⇒ **skipped** |

⚠️ **The reciprocal is real:** a whole-question answer keyed `sub_answer_id` is dropped just as
silently as a sub-answer keyed `answer_id` — `sub_answer_id` is not a fallback, not a warning, not an
error. Each direction has its own independent silent failure. Either way the outcome is identical and
invisible: the answer is skipped with no error, the question publishes with **no servable answer**,
`solvableExists()` is false, and the question is **absent from the feed and every browse count** with
nothing reported. Measured by running the real publish mapper on a fixture — both failing rows
returned normally with an empty answer set; no exception, no warning, no non-zero exit.

```jsonc
"sub_questions": [
  { "sub_question_id": "…", "label": "(i)", "text": "…",
    "sub_answer": { "sub_answer_id": "…", "approach": "…", "final_answer_latex": "…" } }
],
"answers": [ { "answer_id": "…", "approach": "…", "final_answer_latex": "…" } ]
//            ^^^^^^^^^ NOT `sub_answer_id`
```

⚠️ **And a `sub_answer_id` on a whole-question answer is not merely ignored — it can also roll back
the publish.** If the same object is reachable from both `node.sub_answer` and `node.answers[]` the
two are *merged*, the id inserts twice, and the whole transaction rolls back
(`structure-question-parts` §0.5).

## 6. Verify (definition of done, per staged doc)

The staged doc is what this skill emits (via `build-staged`) and the only thing the gate reads.
Mechanical checks over `staged.json` — **each must print `0` or `[]`**, and every one is a failure
mode from §0 or §5 that is **silent** on the far side of a publish. **Walk the list; do not carry a
count of it in prose.**

### ⚠️ 6.0 Run every check over the PUBLISH SET, not over the document

**Set `$IDS` to the ids you are about to pass to `publish`, and scope every check to them.** The
staged doc is the whole batch; a publish is a subset (`question_ids`). A check that walks
`.questions[]` silently assumes the two are the same. ⚠️ **A signed live question legitimately has no
`ingestion_metadata` and no flag** — re-flagging it is a **false positive**, and the expensive kind:
*a check that cries wolf on correct content trains the next agent to ignore it*. Scoping costs one
`--argjson` and removes the whole class. Check #3 may stay whole-document — a `verified_by` anywhere
in a staged doc is a real finding with no known producer.

```bash
IDS='["<id>","<id>"]'      # exactly the ids you will pass to publish

# 1. Every question routed to publish carries an answer somewhere in its tree (T-S8-3). Prints the
#    question_numbers with none — a published question with no verified answer is absent from the feed
#    and every browse count. SCOPED: unscoped it fires on stems whose answers are still unauthored.
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | select([.. | objects | select(has("answer_id") or has("sub_answer_id"))] | length == 0)
     | .question_number]' staged.json          # must be []

# 2. Sub-question answers are keyed `sub_answer_id`, whole-question answers `answer_id` (§5a).
#    Each wrong direction is dropped in SILENCE — this is a pair of calls.
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | .. | objects | select(has("sub_question_id")) | (.answers[]? + (.sub_answer // empty | [.]))
     | select(has("sub_answer_id") | not)] | length' staged.json    # 0 — or the equivalent over your doc shape
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | .answers[]? | select(has("answer_id") | not)] | length' staged.json          # 0

# 3. You never sign. WHOLE-DOCUMENT on purpose — a hit anywhere is a real finding.
jq '[.. | objects | select(has("verified_by") or has("verified_at"))] | length' staged.json

# 4. No `steps`, and no `kind: "steps"` (T-S8-7).
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | .. | objects | select((.steps // [] | length) > 0 or .kind == "steps")] | length' staged.json

# 5. No answer is fully empty — approach, final and diagram all absent (§0.7, T-S8-4).
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | .. | objects | select(has("answer_id") or has("sub_answer_id"))
     | select(((.approach // "")|gsub("^\\s+|\\s+$";"")) == ""
          and ((.final_answer_latex // "")|gsub("^\\s+|\\s+$";"")) == ""
          and (.diagram_dsl // null) == null)] | length' staged.json

# 6. No provenance in `approach` — rendered to the student verbatim (§0.3).
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | .. | objects | select(has("answer_id") or has("sub_answer_id"))
     | select((.approach // "") | test("marking scheme|derived|source:|page [0-9]";"i"))] | length' staged.json

# 7. Everything you authored is flagged (§0.1, D3 + OD-4). An absent flag publishes UNFLAGGED —
#    truthyFlag(undefined) is false. SCOPED: a signed live question legitimately has no flag.
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | select(.ingestion_metadata.needs_human_review != true) | .question_number]' staged.json  # []

# 8. ⭐ THE LIMB-A PROBE (§4.5.4). Every answer whose `final_answer_latex` describes an ARTEFACT
#    while carrying no figure — an answer that IS a drawing, shipped as a sentence about a drawing.
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | .. | objects | select(has("answer_id") or has("sub_answer_id"))
     | select((.diagram_dsl // null) == null)
     | select((.final_answer_latex // "")
              | test("draw|shade|mark|plot|sketch|figure|diagram|අඳින්න|ඇඳ|ලකුණු කර";"i"))
     | (.answer_id // .sub_answer_id)]' staged.json     # must be []

# 9. ⭐ LAYOUT (§4.1c). Every answer whose longest PROSE paragraph — table rows and list items
#    excluded — is over 180 characters. A wall of text on a 375 px screen; split it.
jq --argjson ids "$IDS" '[.questions[] | select(.question_id | IN($ids[]))
     | .. | objects | select(has("answer_id") or has("sub_answer_id"))
     | select([ (.approach // "") | split("\n\n")[] | select(test("^\\s*[|*-]") | not) | length ] | max > 180)
     | (.answer_id // .sub_answer_id)]' staged.json     # must be []

# 10. ⭐ INLINE-MATH WIDTH (§4.1c). Estimates every inline `$…$` run in the scoped questions' stems,
#     part texts, approaches and finals; exit 1 at >= 330 px, lists 270–330 px borderline.
python3 tools/check-inline-math-width.py staged.json --ids "$(echo "$IDS" | jq -r 'join(",")')"
#     ⚠️ Then MEASURE the borderline ones — the estimator over- and under-flags per field:
node tools/measure-inline-math-width.mjs --fields fields.json   # 0 CLIP required
```

⚠️ **Check 8 catches limb A only, and passing it is not the trigger.** Limb B leaves no trace in the
text. §4.5 is a decision you record per answer; check 8 is the one part a machine can see.

⚠️ **Watch each one fire once, on a deliberately broken copy.** An assertion nobody has seen fail is
a claim, not a check. ⚠️ **And watch the TRUE POSITIVE still fire after you scope it** — a fix that
stops the false positive and also stops the true positive converts a noisy check into a silent one,
which is worse than the bug.

- [ ] ⭐ **Every `approach` reads one step per paragraph on a 375 px screen** (§4.1c): computations
      on their own lines, lists as lists, a table on its own, no prose paragraph over ~180 chars.
- [ ] ⭐ **No inline `$…$` run is cut off at 375 px** (§4.1c): check #10 exited 0, and each
      borderline run was looked at in the preview.
- [ ] Every check prints `0` / `[]`, read back out of the file you are about to hand to the gate —
      not the values you meant to write — **with `$IDS` set to the publish set** (§6.0).
- [ ] ⚠️ **`$IDS` is the set you actually pass to `publish`** — assert the scoped count equals the
      set's length; a typo'd id makes a question **silently unchecked**.
- [ ] ⭐ **§4.5's trigger was applied to every answer, and the outcome recorded** — which limb fired,
      or *"text-only"* with the one-line reason. **An unrecorded decision is indistinguishable from
      a decision nobody made.**
- [ ] Two structurally different derivations agreed, both recorded in the working notes (§3). ⚠️ **A
      recompute is not a second method** (T-S8-5): if the two disagree, the question is unresolved —
      no answer is published.
- [ ] `hasSwallowedMarkup` is `false` for `approach` and `final`; **even-`$`-parity** also run on
      both (`hasSwallowedMarkup` is blind to odd `$`); no Sinhala inside `\text{}`.
- [ ] The unit is present where the question asks for one, and `final` is not double-`$` wrapped
      (§4.2).
- [ ] Every figure referenced by `figure:` exists and passed `vdd-check` before staging.

### 6.1 Deferred post-publish read-back

After a publish, the read-back belongs to the operator/critic turn: `verified_by` is still NULL on
everything derived · the flagged question is genuinely withheld (⚠️ outside the ~75 s Hyperdrive
cache window — T5/T-S8-6) · the answer rows actually exist (T-S8-3) · sub-answers survived (§5a).
⚠️ **Never "fix" a finding with Publish changes** — it destroys and re-inserts the whole answer
sub-tree and re-raises the flag on a signed card (T-S8-2).

---

## 7. Keep this skill alive

- **Pin maxima, absolutes and zeroes. Never pin an average or a fraction** — a growing corpus moves
  every average, and each move costs a spurious "STOP and re-derive". §1.1's three invariants are
  what the table is *for*.
- **Re-derive every line-number cite, don't trust it** — cites in this family of skills have been
  wrong in ways that inverted their meaning. `sed -n '<N>p' <file>` and *read the line*.
- **Record what the second-method check actually caught** — §3's value is entirely empirical.
- ⚠️ **§4.5 is the rule with the least evidence behind it** — every run should record which limb
  fired, on which item, and whether the figure was worth drawing, including *"none, all text-only"*.
  A run that produces no answer figures should say why rather than leaving the question
  re-discoverable.

Cross-cutting traps go to [`docs/TRAPS.md`](../../docs/TRAPS.md).
