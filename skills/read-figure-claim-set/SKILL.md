---
name: read-figure-claim-set
description: >-
  Use FIRST whenever a generated maths question carries a figure — before any drawing exists.
  Author a CLAIM SET — a plain-text document of falsifiable propositions (points, segments,
  collinearity, angles, ratios, every label verbatim) plus the canvas anchors they are stated
  against — on channel `constructed`, with a `stem:` header carrying the stem text. The output is
  TEXT, deliberately — a second agent can audit "A, C, E collinear · right angle at B · labels
  A B C D E F" for sufficiency and consistency WITHOUT seeing a drawing, and `audit-claim-set.py`
  recomputes every numeric claim against the anchors and against the stem's own numbers (a drawn
  ratio the stem does not justify is refused). Owns "the figure was claimed wrong" and states
  which claims the answer depends on. Use before drawing any diagram for a generated question.
argument-hint: "[question number] [figure id]"
---

# Claim a figure before drawing it (S6a — constructed channel)

> Moved from Vibhaga-Docs `.devin/skills/read-figure-claim-set` @08c09a9; paper-only sections removed
> (see docs/MIGRATION.md). **Every figure here is `channel: constructed`** — there is no printed figure to
> read, so the source skill's §2.1/§2.2 (vector/raster reading), §2.0 (per-figure wave), §2.4's capture-
> correction half, Audit B's source-reading rationale and its page-side traps are all gone. What remains is
> the claim grammar, the constructed-channel rules, and the audits that need no page.

> **Why this exists as its own skill.** The figure-understanding half of the pipeline used to end in a
> drawing made by the same agent that read the page — uncheckable by anyone else (**T25** in Vibhaga-Docs).
> The constructed case has the same shape: the agent who decides what the figure *is* is the agent who
> draws it. ⇒ **This skill's deliverable is TEXT, and that is the entire point.** A claim set is a list of
> propositions about the figure you are about to draw. A second agent — or a script — can take *"A, C, E
> are collinear"*, or *"len AB / len BC = 2.5"*, and say **no**. It cannot do that with an `<svg>`.

**Consumes:** the question's authored stem (which becomes the `stem:` header) and the figure's intended
role in the question.
**Emits:** one **claim set** per figure (§3) — and nothing else. **No VDD.** (On a `constructed` set the
anchors ARE canvas coordinates, in the frame `source:` declares — that is the one difference from the
paper side, where anchors were source-page points.)
⚠️ **"Per figure" includes an ANSWER's figure** — usually answer figures are constructed too; §2.3's rules
apply with the variant notes below.

---

## 0. Non-negotiables (read first)

1. ⚠️ **A claim you did not derive is `inferred`, and an `inferred` claim needs a reason.** Every claim
   carries one of **`stem` · `inferred` · `measured` · `printed`** (§3.2). This tag is the most
   load-bearing field in the format: it is what separates *"the stem says 5:2"* from *"I chose to draw it
   3:2"*. On a constructed set the honest tags are `stem` (the question states it), `inferred` (a
   construction choice, with its reason — e.g. "canvas arm chosen so the angle opens upward"), and
   `derive`-backed arithmetic. `measured` applies only on an answer figure that re-reads the question
   figure's scale; `printed` only where the question figure *is* redrawn apparatus.
2. ⚠️ **Every numeric claim must be justified by the STEM, and `audit-claim-set.py` enforces it.** A
   `ratio len AB / len CD = v` claim passes only if some pair of stem numbers `a, b` has `a/b ≈ v`, or the
   claim cites `derive Kn` whose value matches **and whose literals are backed**: every numeric literal in
   the cited derive's expression must be a stem number, a canonical constant (`1`, `2`, `90`, `180`,
   `360`), or the value of another backed derive (transitively, no cycles) — an invented
   `derive 3 / 2 = 1.5` does not rescue a copied 1.5 when the stem says 5 and 2; the failure names the
   unbacked literal. `angle … = v` likewise. The failure message says the value
   is not justified by the stem — *"drawn ratio copied?"* — and names the claim id. The red-team this
   exists for: a cuboid-face figure drawn 1.5:1 for a 5:2 stem passed the OLD audit because its anchors
   agreed with its claim — claim and drawing were self-consistently wrong together.
3. **You do not draw.** Anchors are canvas coordinates as you intend them, in a named frame; element
   types, budgets and `a11y` are the drawing skill's
   ([`draw-and-verify-question-vdd`](../draw-and-verify-question-vdd/SKILL.md)). A claim set that already
   contains VDD elements has destroyed the only thing that made it auditable.
4. ⚠️ **Every claim must be falsifiable, and stated so it can be checked WITHOUT the drawing.** Two tests
   for any line you write: could a reader who has not seen your drawing learn something from it? and
   **could someone check it and find it wrong?** *"The figure shows a rectangle"* fails both.
   *"∠ABC = 90°, construction"* passes both.
5. ⚠️ **Name the claims the ANSWER depends on** (`load-bearing:`, §3.4). A claim set that does not say
   which claims carry the answer hands the drawing skill and the critic a flat list with no priorities.
6. **A mark is a claim, and so is its absence.** If the figure you intend has no right-angle mark at a
   corner you claim is right, write `right` **and** declare the mark (or its absence, in `none:`/
   `departures:`) — the drawing and the claim must say the same thing.
7. **Language-neutral labels only, verbatim.** The labels you intend to draw, exactly (`A`, `35°`, `x`,
   and `"7 cm"` — ⚠️ **a label containing a space is double-quoted**, in `labels` and in its claim;
   §3.1). There is one `diagram_dsl` per node and no `value_sinhala`, so a figure cannot hold two
   languages.
8. **No PNG, ever.** `decisions/0001` PD3: a raster image is never a student's diagram.

---

## 2. The channel is `constructed` — what that costs and what it buys

### 2.3 ⭐ The CONSTRUCTED claim set — question-side and answer-side

⭐ **DECIDED (paper side, binding here): this skill applies to a constructed figure, with a variant, and
is never bypassed.** The variant needs no new predicate and no change to `audit-claim-set.py`. The
headers carry the difference:

| header | meaning on `channel: constructed` |
|---|---|
| `source:` | ⚠️ **the FRAME the anchors are in**, and where it came from — *"constructed; frame is the question's own canvas, 504 × 146, y down"*, or *"extends the question figure `figures/q3.json`; frame is that figure's own canvas"* for an answer figure. `source:` is checked for **presence**, so this is legal and it is the one line that tells a reader which kind of claim set they are holding |
| `channel:` | ⭐ **`constructed`** — and it is load-bearing: `constructed` REQUIRES at least one `derive` claim (audit check 2c), because it is the flag that says *"no source reaches the claims that are the answer"*. ⚠️ In this plugin `channel:` is **optional** and defaults to `constructed`; when present, an unknown value is still refused |
| `stem:` | ⭐ **NEW for this plugin — REQUIRED on a constructed set.** The question's stem text (wraps like other headers). The stem-ratio check (§0.2) justifies every `ratio`/`angle` numeric claim against the ASCII decimals in this text — `5:2` in the stem gives numbers 5 and 2 — or against a cited `derive` claim's value, and that derive's own literals must trace back to the same stem numbers (§0.2) |
| `scale:` | the declared drawing scale (§3.3) — *"drawn to scale"* or *"NOT to scale"*, with the site it applies to |

**The evidence tags do the rest:**

| tag | on a constructed claim | why it is the right tag |
|---|---|---|
| `stem` | a value the question states — every ratio/angle the figure must honour | unchanged from §3.2 |
| ⭐ `inferred` | **every construction choice the stem does not force** — arm direction, which side is longer where it is free, a label's placement | ⚠️ and `inferred` **requires a reason** (§3.2), so the format already forces you to write down *why*. On an answer-side set the `inferred` claims **are the answer** — a claim set with no `inferred` claims described the question's figure and called it an answer |
| `derive` | the construction arithmetic — `derive 180 - 50 = 130` for an arm's direction, `derive 4 - (-2) = 6` for the answer's own computation | REQUIRED on every constructed set (check 2c); on a number line it also binds the arrow's landing (§3.2) |
| `measured` | a value taken off the question figure to keep the answer to its scale | answer-side only |

⚠️ **`inferred` is not a weaker `stem`, and it must not be laundered into one.** If the stem does not fix
a value, the figure's freedom is a *choice* — say it is one.

⛔ **STATE IT PLAINLY: the CONSTRUCTED case has WEAKER verification than a read one, and the stem-ratio
check is the floor that was missing.** On a printed figure a second reader could check the claim set
against the page and the page was ground truth. On a constructed figure there is no page — the only
anchors against the claim's *content* are (a) the stem's numbers, which the stem-ratio check enforces,
and (b) the `derive` chain. The counter-example that proved the floor was missing (paper side,
2026-08-30): an internally consistent claim set drew an arrow landing on **5** where the ask was
`4 - (-2)` — **78 assertions, 0 failures, exit 0**, byte-identical to the correct set's footer, until
check 2c and now the stem-ratio check were written for exactly that shape.

| the claim set | result |
|---|---|
| correct — arrow lands on 6, `derive 4 - (-2) = 6` | **0 failures, exit 0**, and it *prints* the projection: `arrow S -> T projects onto K1's scale as 4.00 -> 5.99, and K22 derives 6` |
| ⛔ **draws 5, claims 6** | **FAIL, exit 1** — the move must LAND on the value the answer claims |
| ⛔ **draws 5, claims 5** (the consistent liar) | **FAIL, exit 1** — `derive 4 - (-2) = 5` evaluates to 6 |
| ⛔ **rectangle drawn 1.5:1 for a 5:2 stem** | **FAIL, exit 1** — `1.5 is not justified by the stem (drawn ratio copied?)` — the NEW stem-ratio check |

All are carried as `--self-test` fixtures and **must be seen to fail** — run it and read
`ALL MUTATIONS BEHAVED`. ⚠️ **And what the checks still cannot do:** they cannot tell you the *derivation*
is the right one for the question — `derive 4 + 2 = 6` also passes. That is `author-question-answers` §3's
two-method check, and it is why the audit is a floor rather than a gate. The remaining independent check
is the `qgen-critic` agent's content pass after publish.

⚠️ **And `load-bearing:` changes meaning in a useful way.** On a question figure it names the claims the
answer *depends on*. On an answer figure it names the claims that **are** the answer. **If `load-bearing:`
cites only `stem`/`printed` claims, the figure is not an answer figure.**

---

## 3. ⭐ The claim-set format

One claim set per figure. Plain text, in a fenced block, committed beside the run's ledger (a claim set
that lives only in a chat turn is indistinguishable from never having claimed the figure).

### 3.1 The header, the inventories, and the anchors

```
figure:   q1                        # the id content.yaml's figures: key, the claim set and the VDD carry
source:   constructed; frame is the question's own canvas, 200 x 120, y down
channel:  constructed
stem:     A cuboid has a face 5 cm long and 2 cm wide. Find the ratio of the face's sides.
ask:      1  ratio of length to width
labels:   A B C D "5 cm" "2 cm"
points:   A B C D
segments: AB BC CD DA
anchors:                            # canvas px, y down — the DRAWABLE half
  A 20 20
  B 180 20
  C 180 100
  D 20 100
```

⚠️ **`labels` is a verbatim inventory, not a description.** It is the cheapest audit in the whole
pipeline: a second agent counts the glyphs you intend to draw and compares the *set*. ⚠️ And **do not
write the number of them** anywhere — walk the list.

⛔ **A POINT NAME IS EXACTLY ONE `[A-Z]`. This is MANDATORY and enforced** — the predicate regexes are
`([A-Z])`, so `M4`, `P5`, `Ar`, `A1`, `P'` are all **wrong**: a two-character name is read as a **pair of
points** (`segment M4: two declared endpoints` fails and closure reports `unknown: ['M','P']`), and `Ar`'s
`A` is never even seen as a point. ⇒ **26 points per figure, `A`–`Z`, no digits, no primes, no suffixes.**
If a figure needs more than 26 named positions you are enumerating instead of claiming — see §3.5's
*"do not enumerate 30 dots as 30 claims"* and use `stage` / `grid` / `describe`. ⚠️ **Claim IDS take
digits (`K4b`) and point names do not** — the two grammars look alike and are not: `ID_GRAMMAR` is
`[A-Z]\d+[a-z]?`.

⚠️ **QUOTING, decided once, because this is an interface.** A label containing a space is
**double-quoted** in `labels` and in its `label` claim; everything else is bare. Tokenising is `shlex`
(POSIX), so `labels: A B C "7 cm" "18 cm" 125°` is five labels, not seven.

⚠️ **The inventories MAY WRAP over several lines** — every line of an inventory section is joined before
tokenising. **`ask:` does NOT wrap: it is ONE part per physical line** — a wrapped `ask:` continuation
parses as a phantom part and `audit-claim-set.py` fails it.

⚠️ **`segments` is one entry per STROKE you intend to draw**, and it is the entry that catches a deleted
side: the paper side lost a triangle's `AB` by collapsing six strokes into three elements, with every
schema check green. The `segments` inventory is what makes that mechanically detectable (Audit C, §5.3).

### 3.2 The claims

One claim per line: `ID  predicate  args  |  evidence  |  note`.

⚠️ **The line shape is load-bearing, because the parser uses it instead of guessing:**

| rule | why |
|---|---|
| **Claim id: one capital, digits, an optional single lower-case suffix** — `K1` · `K23` · `K4b`. ⚠️ Not `k24`, `K24.`, `(K24)`, `KK24`, `K24ab`, `K-24` or `24` | ids are validated, never sniffed. `audit-claim-set.py` rejects a bad id **loudly** rather than deciding the line must be something else |
| **A claim starts at the same column as the first claim in the block** (2 spaces, by convention) | every line at or left of that column **is** a claim and **must** carry both `\|` separators |
| **A wrapped note is a HANGING indent — at least 6 columns further in** | anything in between is refused as ambiguous |
| **Ids are unique** | a duplicate is a parse error, not a last-one-wins |

| predicate | args | means |
|---|---|---|
| `collinear` | `P Q R` | P, Q, R lie on one straight line, **in that order** |
| `angle` | `P Q R = v` | the angle at vertex Q between QP and QR is `v` degrees |
| `right` | `P Q R` | the angle at Q is a right angle |
| `ratio` | `len PQ / len RS = v` | a length ratio — the only scale claim that survives a canvas change |
| `parallel` | `PQ RS` | PQ is parallel to RS |
| `equal` | `PQ RS` | equal lengths |
| `on` | `P QR` | P lies on the segment QR — the canonical spelling is `K1 on P QR`. ⚠️ **The only way to say betweenness**: in `collinear P Q R` the points are **ordered along the line**, so Q is between P and R by construction. Do not write the word *between* as a claim |
| `inside` | `P angle Q R S` | P lies strictly inside the named angle (its vertex is R) |
| `label` | `"txt" names X` | a drawn glyph, and the point / segment / angle / region it names |
| `arrow` | `P -> Q` | a drawn arrowhead, and which end carries it |
| `circle` | `centre O through P` | |
| `arc` | `centre O from P to Q` | |
| `shaded` | `region P Q R …` · `<n> of <m> cells` | a filled or hatched region, or a count of shaded grid cells |
| `free-text` | `"txt" beside PQ` | drawn prose or a unit that names no point |
| `gradient` | `PQ = v` · `PQ steeper than RS` | ⚠️ **a comparative is a claim.** A published figure's `a11y.description` once called one line *"steeper"* than two others whose gradients were **1.73 vs 4.02** — on a parallel-lines question, read by exactly the students who cannot see the figure |
| `axis` | `PQ from <v0> to <v1>` | a numbered scale along segment PQ (a number line, an axis). ⛔ **P AND Q MUST BE THE TWO EXTREME *LABELLED TICKS*, NOT THE DRAWN ENDS** — see the block below. `P` and `Q` **are** the values `v0` and `v1`, which is what makes every other tick's position calculable |
| `tick` | `PQ step <v>` | the tick interval on that scale. Checked: `(v1-v0)/step` must be a whole number of steps, **and the numeric `labels` must be exactly that arithmetic sequence** |
| `at` | `<value> <x> <y>` | the drawn position of one value on a scale. ⚠️ **Checked against the position `axis` + `tick` IMPLY** (≤1% of the axis length). This is the claim that makes a numbered scale auditable rather than merely parseable |
| `interval` | `open\|closed <v0> to <v1> on PQ` | a marked range — the heavy part of a number line, and whether its ends are included. Checked: ordered, and inside the axis. ⭐ **An `interval` whose end reaches the axis's own drawn end is how UNBOUNDEDNESS is written** — pair it with the `arrow` claim for that end. ⚠️ **`interval` is where the DIRECTION of the marked part lives, and direction is the whole content of a number line** — a live published answer once shipped the complement of its own figure with every gate green |
| `grid` | `<rows> by <cols> over P Q` | a rectangular array of equal cells (an area model) |
| `stage` | `<n> shows <what>` | one term of a growing pattern (stick/dot patterns: *"stage 3 shows 9 sticks"*) |
| `describe` | `"prose"` | ⚠️ **the fallback for a figure whose meaning is not geometric** (§3.5). Free prose. It is not auditable against anchors and the auditor says so — use it deliberately, not to avoid work |
| `paint` | `PQ solid\|dashed\|dotted [opaque]` | the line style of a segment or a mark. ⚠️ **In a maths figure this is MEANING, not decoration** — a dashed edge is a hidden or construction edge, and an **opaque** mark hides what crosses it |
| `none` | `<element type names>` — e.g. `none tickMark parallelMark angleArc arrow shaded` | ⚠️ **the negative inventory**: none of the named classes appears in the figure. Write one for every mark class the element union can draw, so a *missing* mark is as visible as an invented one |
| ⭐ `derive` | `<expr> = <value>` | ⚠️ **REQUIRED on `channel: constructed`** (§2.3). The construction's own arithmetic, as a bare evaluable expression — `derive 4 - (-2) = 6`. **Two things are checked and they close two different doors:** `<expr>` must really evaluate to `<value>`, **and** an `arrow` claim's end, projected onto the `axis` scale, must LAND on `<value>` (within a quarter step). ⚠️ **`arrow`'s endpoints are anchor-checked to make that possible** |

**Evidence, one per claim — this is the field the format rests on:**

| tag | means | obligation |
|---|---|---|
| `stem` | the question's stem says so — the figure honours it | quote the phrase (the `stem:` header is where the audit reads the numbers) |
| `measured` | you computed it off an existing figure (answer-side: keeping the question figure's scale) | quote the tolerance |
| `printed` | the claim re-states apparatus being redrawn (answer-side) | quote what is redrawn |
| `inferred` | a construction choice the stem does not force | ⚠️ **state the reason.** An `inferred` claim is the one a critique reads first |

#### ⛔ `axis` is anchored on the two extreme LABELLED TICKS — never on the drawn ends

A number line is almost always drawn **past** its labelled range: the axis bar runs into an arrowhead at
each end, so the ink extends beyond the outermost numeral. Anchoring the axis on the ink's ends is honest
looking and **wrong for this predicate** — it fails two checks at once:

| you write | what fires |
|---|---|
| `axis PQ from -4.94 to 6.27` + `tick PQ step 1` | ⛔ `tick PQ step 1 -> 11.21 / 1 = 11.21, which must be a positive whole number of steps` — the arrowhead tips are not on the lattice the ticks define; and the numeric-label check generates the expected set **from `v0`, `step` and `round((v1-v0)/step)`**, so a non-lattice `v0` makes every drawn numeral "unexpected" |
| `axis PQ from -4 to 5` + `tick PQ step 1`, `P`/`Q` anchored at the **−4** and **5** ticks | ✅ `9 / 1 = 9`, `missing none, unexpected none` — and every intermediate `at <v> <x> <y>` is checked against the implied position (≤1% of the axis length) |

⇒ **The rules:**

1. ⛔ **Anchor `P` and `Q` on the extreme *labelled* ticks.** `v0` and `v1` are the drawn numerals, and the
   whole numeric audit of a scale hangs off that.
2. ⭐ **Carry the extra extent as `arrow`, plus a note — do not discard it.** Declare the two tips as their
   own points with their own anchors (`R`, `S` — single letters) and claim `arrow P -> R` / `arrow Q -> S`,
   noting how far beyond the last numeral the ink runs. ⚠️ **`arrow`'s endpoints are anchor-checked**, so a
   tip with no `anchors` line fails loudly rather than being ignored.
3. ⭐ **An `interval` that reaches the drawn end is how you say the set is UNBOUNDED in that direction**,
   and it must be paired with that end's `arrow`. ⚠️ **This is the load-bearing claim on a number line:**
   *open at −2 running **left*** and *the segment **between** −2 and 2* differ in nothing a reader checks
   except direction. Say which way each heavy part runs, in `interval` and in the `load-bearing:` list.
4. ⚠️ **Write the `paint` claim for the heavy parts.** *"Heavy"* is a **measured class**, not an
   impression — state the stroke widths you intend (`paint PQ opaque`, the VDD `strokeWidth`) so the check
   can separate the classes. Which strokes are heavy IS the answer on a number line.

### 3.3 The scale claim, which is not optional

⚠️ **Whenever the stem's stated value and the drawn value could be read as disagreeing, write `scale:` and
say which the drawing follows.** On a constructed figure the default expectation is **drawn to the stem** —
the stem-ratio check enforces it for ratios and angles. A figure you *intend* to be not-to-scale (a
"sketch" question, a prism's depth edges) is legal **only if declared**, because everything downstream
(the VDD numeric check, the critic, a human reviewer) will otherwise read the difference as your mistake.

```
scale:    NOT to scale — prism depth edges shortened for the canvas; face ABCD is true 5:2 per the stem
```

### 3.4 `load-bearing:` and `unreadable:`

```
load-bearing:
  1 -> K1                        # the ask's part -> the claims it depends on
unreadable: (none)
ambiguous:  (none)                   # ⚠️ a claim TWO readers could disagree on, with the measurement
                                     #    that makes it a judgement rather than a reading
departures: (none)                   # ⚠️ the drawing skill writes back here — anything it drew that the
                                     #    claim set does not declare, with a reason
```

⚠️ **`ambiguous:` is REQUIRED — `(none)` is a valid value, silence is not.** `audit-claim-set.py` lists it
in `REQUIRED_HEADERS`, and it is the **only** machine-readable way to say *"this failure is adjudicated"*:
a claim named there still gets checked and still gets its number printed, reports **`ADJDCT`** rather than
`FAIL`, and is **excluded from the exit code**. ⚠️ **A contested claim with no entry is a hard failure, and
that is the point** — you must write the adjudication down to get it.

⚠️ **`ambiguous:` is not a softer `unreadable:`.** `unreadable` means *"I cannot state the value"*;
`ambiguous` means *"the figure is stated and two readers would still call it differently"*. On a
constructed set the honest entry is usually a construction freedom: *"K9: the stem fixes AB:BC = 5:2, the
absolute size is a canvas choice — 160×64 px chosen for the 375 px column"*.

### 3.5 ⚠️ Figures this format does not cover

⚠️ **Do not assume the predicate table covers the figure you want.** The paper side measured its live
corpus and found the original predicate set could not express **45%** of it — number lines, stick and dot
patterns, area models, 3-D solids, pictures — and the uncovered set is exactly where the semantic gate is
silent too. `checkDiagram()`'s two checks are **both** gated on an `angleMark` carrying a numeric label
(`Vibhaga-Admin/src/components/diagram/validate.ts`), and a number line has no `angleMark` at all — so it
returns `[]` whether the figure is right or the **exact complement** of the intended one. ⇒ **On a figure
in one of these classes the claim set is not a nicety — it is the only correctness evidence that exists.**

§3.2 now carries `gradient`, `axis`, `tick`, `interval`, `grid`, `shaded`, `stage` and `describe`, which
between them reach every class measured:

| class | what it needs | verdict |
|---|---|---|
| **A numbered scale** — number line, axis | `axis PQ from -4 to 5` · `tick PQ step 1` · `at <value> <x> <y>` · `interval closed 2 to 5 on PQ` · `label` per numeral | **covered, and AUDITED** — `axis` + `tick` determine every tick's coordinate, each `at` is checked against the implied position, the numeric `labels` must be the arithmetic sequence, `(v1-v0)/step` must be whole, `interval` ordered and inside, no two `label` claims on the same target |
| **A growing pattern** — *"three stages of a stick pattern"* | one `stage <n> shows …` per term, plus the segments/circles of **one** term. ⚠️ **Do not enumerate 30 dots as 30 claims** — the claim is the *rule* | **covered** |
| **An area model** — *"a unit divided into ten equal squares, five coloured"* | `grid 1 by 10 over P Q` · `shaded 5 of 10 cells` | **covered** |
| **A gradient comparison** — two pairs of parallel lines cut by a third | `parallel` + `gradient HG steeper than FE` (and the auditor checks the comparative) | **covered** |
| **A 3-D solid drawn in 2-D** — square-based pyramid | the visible edges as `segment`s, hidden edges as `paint … dashed`, **plus** `describe "a square-based pyramid seen from above-left"` — the *solidity* is not a 2-D claim | **partly: `describe` carries the meaning** |
| **A picture** — *"a face made of circles"* | `circle`/`arc` per shape, **plus** `describe`. There is no geometric fact to audit | **`describe` only** |

⚠️ **The rule when you reach `describe`:** say so **in the claim set**, and say what the reader will not be
able to check. A `describe` claim is invisible to the auditor by construction, so an audit that is mostly
`describe` is an audit of nothing — and that is the signal to ask whether the figure is worth drawing at
all.

---

## 4. ⭐ Worked example — a constructed cuboid-face rectangle

Synthetic (no paper): the stem is *"A cuboid has a face 5 cm long and 2 cm wide. Find the ratio of the
face's length to its width."* The figure is the face.

```
figure:   q1
source:   constructed; frame is the question's own canvas, 200 x 120, y down
channel:  constructed
stem:     A cuboid has a face 5 cm long and 2 cm wide. Find the ratio of the face's length to its width.
ask:      1  ratio of length to width
labels:   A B C D "5 cm" "2 cm"
points:   A B C D
segments: AB BC CD DA
anchors:
  A 20 20
  B 180 20
  C 180 84
  D 20 84

claims:
  K1  right A B C                           | inferred | face of a cuboid is rectangular — and the mark
                                                    will be drawn (see departures if omitted)
  K2  right B C D                           | inferred | same
  K3  ratio len AB / len BC = 2.5           | stem     | "5 cm long and 2 cm wide" — 5/2; the stem-ratio
                                                    check finds 5 and 2 in the stem's numbers and agrees
  K4  ratio len CD / len DA = 2.5           | stem     | opposite sides of a rectangle
  K5  equal AB CD                           | inferred | rectangle
  K6  equal BC DA                           | inferred | rectangle
  K7  label "A" names A                     | inferred | label placement, above-left of the corner
  K8  label "B" names B                     | inferred | label placement, above-right of the corner
  K9  label "C" names C                     | inferred | label placement, below-right of the corner
  K10 label "D" names D                     | inferred | label placement, below-left of the corner
  K11 label "5 cm" names AB                 | stem     | the stem's 5 on the long side
  K12 label "2 cm" names BC                 | stem     | the stem's 2 on the short side
  K13 derive 5 / 2 = 2.5                    | inferred | REQUIRED on constructed (check 2c) — the ratio
                                                    the figure must honour, from the stem's own numbers
  K14 none tickMark parallelMark angleArc arrow shaded | inferred | no marks declared; the right-angle
                                                    marks are drawn by the drawing skill's convention
                                                    (see departures if dropped)

scale:    drawn to scale — AB:BC = 5:2 as the stem states (160 x 64 px of ink at this canvas)
load-bearing:
  1 -> K3, K13                     # the ratio the stem states and the derive that proves the figure honours it
unreadable: (none)
ambiguous:  (none)
departures: (none)                 # the drawing skill fills this in
```

⚠️ **This is exactly the shape the old audit got wrong.** Draw the anchors 160 × 107 px and K3 still reads
`ratio len AB / len BC = 2.5` — anchors and claim disagree so the audit fails — but draw them 160 × 107 px
**and claim `= 1.5`** and the OLD audit passed it (anchors agree with the claim; both are self-consistently
wrong). The stem-ratio check is what refuses the second one: `1.5` is not `a/b` for any pair of stem numbers
and no `derive` claim yields it.

---

## 5. ⭐ What a second agent can check — from the claim set ALONE

### 5.1 Audit A — the claim set on its own (no drawing, no VDD)

Every one of these is mechanical, and every one has caught something real:

- **Closure.** Every point named in a claim is in `points`; every point in `points` has an anchor; every
  glyph in `labels` is bound by exactly one `label` claim; **no two `label` claims name the same target**;
  every point in `segments` is in `points`.
- **Claims vs. anchors.** Recompute every `angle`, `right`, `ratio`, `collinear`, `parallel`, `on`,
  `equal`, `gradient`, `circle`, `arc` and `at` claim from `anchors` alone and diff against the stated
  value. ⚠️ **On a numbered scale this is stronger than it looks**: `axis` + `tick` *determine* every
  tick's coordinate. ⚠️ **A disagreement here is a mis-statement, not a rounding artefact** — the anchors
  and the claims came from the same intent, so they cannot honestly differ.
- **Claims vs. the stem (constructed only).** Every `ratio`/`angle` numeric claim is justified by the
  `stem:` numbers or a `derive` citation (§0.2). This is the check that catches a claim set which is
  self-consistent and wrong for the question.
- **Arithmetic.** Angles at a point on a straight line sum to 180; a triangle's sum to 180; a
  complementary pair to 90; vertical angles are equal.
- **Scale honesty.** A declared not-to-scale site is `scale:`'d (§3.3).
- **Sufficiency for the ask.** For each entry in `ask`, is there a chain of claims that answers it? ⚠️
  **The commonest sufficiency defect is a `load-bearing:` list that cites VALUES where the answer turns on
  an INCIDENCE claim** — an angle or a ratio, where the real dependency is `collinear` / `on` / `right` /
  `inside`. ⇒ **Read each `ask` entry, write the answer in words, and list what the words depend on. If a
  value appears in your list, ask what would change if the value changed — if the answer's *shape* would
  not, the value is not load-bearing.**
- **Evidence discipline.** No `inferred` without a reason. No claim whose evidence is a drawing.
- **Negative inventory.** `none` claims exist for the mark classes the element union can draw.

⭐ **The mechanical part of Audit A is a committed script, so it is a check and not an aspiration:**

```bash
# Paths are from the PLUGIN ROOT. One convention, one cwd.
python3 tools/audit-claim-set.py <claim-set.txt>
python3 tools/audit-claim-set.py --self-test        # ⚠️ run this too — and read ALL MUTATIONS BEHAVED
```

⚠️ **Run it; it prints its own counts** (assertions, claims parsed, how many were checked against the
anchors, and which were recognised-but-not-verifiable). Do not transcribe those numbers into prose.

⚠️ **Watch the one asymmetry it exposes.** Corrupting a *claim* fails **one** assertion; corrupting an
*anchor* fails **many**. ⇒ A single failure is usually a mis-stated claim; a cluster is usually a
mis-placed anchor — and the cluster is the more dangerous of the two, because every claim downstream of
that point inherited the error.

### 5.2 Audit B — text-only sufficiency and consistency (no drawing)

A **different agent gets the claim-set text only** — no rendered figure, no VDD, no stem beyond the
`stem:` header itself. Run Audit A first; its exit 0 is necessary, not sufficient. Work the
`load-bearing:` list **first**, then the `label` claims, then the rest. For **each part of `ask:`**,
judge whether the recorded claims suffice to answer it, check their internal consistency and evidence
qualifications, and explicitly list claims **not checkable from text alone**. Append the reply as
`# AUDIT B`; on disagreement a **fresh** claim set is written by a new reader — never a silent edit.

**Limit:** this audit can expose contradictory or insufficient claims; it **cannot prove the figure is
right**. The remaining checks are the drawing skill's numeric render check (against the claim set's
stated values — drawn vs stem-derived) and the `qgen-critic` agent's post-publish pass. Neither is
replaced by the text-only turn.

### 5.3 Audit C — the claim set against the VDD (needs the JSON, not the picture)

Owned by the drawing skill (§5 there), listed here because it is what the `segments` and `labels`
inventories are *for*: every `segment` claim covered by some element, every `label` claim carried by an
element with that exact string, every geometric claim recomputable from the VDD's own coordinates.

### 5.4 ⚠️ Make it falsifiable — the red-team fixtures for this skill

The fixture discipline applies here:

> **`F-CLAIM`** — take a finished claim set, **corrupt one load-bearing claim** (turn `collinear A C E`
> into `collinear A C F`), hand the claim set **and nothing else** to a separate agent, and confirm Audit
> A's closure or arithmetic step reports it. Then corrupt one **anchor** instead and confirm the
> claims-vs-anchors step reports that. A claim set that survives both corruptions is not being audited;
> it is being read.

`audit-claim-set.py --self-test` carries `F-CLAIM` and the constructed mutations as fixtures and **must be
seen to fail** — and `tests/fixtures/stem-ratio-bad.txt` is the constructed-set red-team: a rectangle
whose anchors and claim agree at **1.5** while the stem says 5:2, which the tool refuses with
*"not justified by the stem (drawn ratio copied?)"*. ⚠️ **A gate never observed to fail has not been
tested** — run it, and read `ALL MUTATIONS BEHAVED`.

⚠️ **And the delegation is the point, not the checklist.** T25 is blunt: *"a separate agent turn is not
something one agent can do to itself."* Running Audit A in the same context that wrote the claim set
proves almost nothing. **The orchestrator spawns the auditor and hands it the claim set text only.**

---

## 6. Traps — stories with the catch

Cross-cutting traps: [`docs/TRAPS.md`](../../docs/TRAPS.md) — in particular **T25** in Vibhaga-Docs
(self-verification is not verification). The paper side's reading traps (endpoint clustering, filter-
invisible marks, glyph-as-space labels) went out with the page; these are what the constructed side keeps:

### T-S6a-C1 — The self-consistent liar needs a second ground truth
**Looked true:** the anchors and the claims agree, so the figure is right.
**Actually:** on a constructed figure the author writes both. The 1.5:1 rectangle for the 5:2 stem was
self-consistent and wrong — claim and anchors were authored from the same misreading of the stem.
**The check:** the `stem:` header is the second ground truth — the stem-ratio check recomputes the claim
against the *stem's numbers*, not the anchors. Keep `stem:` verbatim from the authored stem; an audit
that cannot see it cannot check the figure.

### T-S6a-C2 — `derive` is a floor, not a proof
**Looked true:** `derive 4 + 2 = 6` passes check 2c, so the answer's arithmetic is verified.
**Actually:** 2c checks that the expression evaluates and the drawing lands on it — never that the
expression is the right one for the question. The wrong-but-valid `derive` passes with the wrong figure.
**The check:** the two-method answer derivation (author-question-answers §3) is the real check on the
arithmetic; 2c only binds drawing to claim.

---

## 7. Verify (definition of done for S6a, per figure)

⚠️ **Lines marked ⬦ are GEOMETRY-ONLY** and do not apply to the classes in §3.5 — a number line has no
angles to claim and a picture has no meaningful negative mark inventory. **Say in the claim set which of
them you skipped and why**; skipping one silently is the same defect as failing it.

- [ ] `channel: constructed` (or omitted — it defaults), `source:` names the frame, and the `stem:`
      header carries the question's authored stem text verbatim (§2.3).
- [ ] ⭐ **A `derive <expr> = <value>` claim exists** — the construction arithmetic (question side) or the
      answer's own computation (answer side) — and `audit-claim-set.py` exits 0.
- [ ] Every `ratio`/`angle` numeric claim is justified by the stem's numbers or a `derive` citation — the
      audit enforces it; if you meant the figure NOT-to-scale, `scale:` declares it (§3.3).
- [ ] On an answer-side set, `load-bearing:` cites at least one `inferred` claim (§2.3) — a claim set
      whose load-bearing list is all `stem`/`printed` is the question's figure wearing an answer's name.
- [ ] ⬦ Every mark class the element union can draw has either a claim or a **`none`** claim (§4 K14).
- [ ] Every claim carries an `evidence` tag; every `inferred` claim carries a reason (§3.2).
- [ ] Every label containing a space is **quoted** in `labels` and in its claim (§3.1).
- [ ] Every predicate you used is in §3.2's table. ⚠️ **If a figure needed something that is not there,
      §3.5 is the routing decision** — reach `describe` deliberately, and say what a reader cannot check.
- [ ] `load-bearing:` names, per part of the `ask`, the claims the answer uses — ⚠️ **incidence claims,
      not values** (§5.1). Write each answer in words first.
- [ ] `ambiguous:` carries every claim two readers could call differently, **with the measurement** (§3.4).
- [ ] **Audit A ran, and it ran in a separate agent turn** with the claim set text and nothing else
      (§5.1, §5.4). Its findings are attached or resolved. ⚠️ Failures may be *correct* — a contested claim
      in `ambiguous:` is expected to fail the mechanical check.
- [ ] ⚠️ **The claim set says, in as many words, that the constructed case is verified more weakly**, and
      names the VDD numeric check plus `qgen-critic` as the remaining evidence (§5.2).
- [ ] `unreadable:` is empty, or each entry names what is undecidable and what you tried (§3.4).
- [ ] The claim set is **committed** beside the run's ledger, not left in a turn.
- [ ] Handed to [`draw-and-verify-question-vdd`](../draw-and-verify-question-vdd/SKILL.md) — with **no**
      VDD and **no** element types in it (§0.3).

---

## 8. Keep this skill alive

The claim-set format is an **interface**, so a change to it is a change to the drawing skill and to
`tools/audit-claim-set.py` — never a local edit. **Append** to §3.2's predicate table rather than
renumbering anything; a renumbered list breaks every inbound `§` citation. Run `tools/check-suite.py`
before every commit. Cross-cutting traps go to [`docs/TRAPS.md`](../../docs/TRAPS.md); claim-set ones
belong in §6 here, written as a **story with the catch**.
