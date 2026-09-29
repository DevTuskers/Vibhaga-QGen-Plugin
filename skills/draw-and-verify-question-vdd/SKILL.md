---
name: draw-and-verify-question-vdd
description: Draw a VDD figure for a question — usually inside Vibhaga-Admin's onboarding-review Edit mode for the question, sub-question or answer — from the claim set the read-figure-claim-set skill emitted (constructed channel: the geometry is authored from the stem's stated values and the claim set's anchors, then proven by audit + render). Use when a figure must be created or corrected — a printed-mark fidelity claim, a missing drawing, or a field found unusable on inspection. Never draw without a claim set; never save without a render.
---

> **Moved from Vibhaga-Docs `.devin/skills/draw-and-verify-question-vdd` @08c09a9; paper-only sections removed (see docs/MIGRATION.md).** Figure source-reading references now point at `skills/read-figure-claim-set`.

Emits `diagram_dsl` on the question, a sub-question, an answer or a sub-answer.

## 0. What you are agreeing to when you draw

- ⭐ **Drawing is mandatory.** A claim set that exists and is not drawn is exactly the failure the
  `generate` skill refuses on — the same gate applies here, element by element: if the claim set
  lists a segment, a label, a mark, it is drawn, or the figure does not publish. The element union
  is wide — line, polyline, polygon, arrow, point, text, math, circle, rect, path, ellipse, arc,
  angleMark, tickMark, parallelMark — and nothing in it is a *print*. If a truly unavailable shape
  blocks the figure, stop and report it to the lead with the exact missing element.
- **The PUT path silently drops an invalid figure** (§2). The persisted shape is the only truth —
  validate it before write (§4.1, run it yourself), confirm after publish that the student page shows
  an `<svg>` (T-S6b-4), and re-check after any later correction.
- **`a11y` is required, not optional** (§3.3): `title` non-empty and specific, `description` present,
  both ENGLISH (OD-12).
- **Legal is not rendered.** `safeParse` passing does not mean the figure shows what you meant —
  render it (§4.2, run it yourself).
- **Language-neutral labels** (§4.4, OD-11): no `$`, no backtick, no Sinhala in any `text`/`math`
  label; numbers, expressions and point names only.
- **A genuinely NOT-to-scale figure says so** in a `text` element or `a11y.title` (§3.5, §4.4).
- **Element budget: ≤ 32 is the outer edge** — a denser figure is a routing signal, not a drawing
  challenge (§3.4).
- ⭐ **`checkDiagram()` is ADVISORY, never a gate** (§0.8). It compares the drawing against its own
  labels and can be wrong on a correct figure — a published, correct figure produces warnings. Report
  its warnings, explain them against the claim set, and never let it block a publish that §5 passed.
- ⭐ **There is no imported-figure path.** The Admin UI's Excalidraw canvas drops elements it cannot
  convert (a diamond, a pasted shape — T-S6b-1). Figures are authored as VDD JSON from the claim set,
  validated, rendered, and written through the API. Do not trust "it was on the canvas".

## 1. What is stable

The rules worth carrying into any reader's head, with what they did NOT say — claims that
circulated while this file was written and that measurement disproved:

| the fact | what it did NOT mean |
|---|---|
| `diagram_dsl` lives on **four** levels: `questions`, `sub_questions`, `answers`, `sub_answers` | a figure has a sibling to copy — none of these inherit from any other |
| `a11y` is optional in the schema | acceptable: an absent `a11y` ships an unnamed image to a screen reader |
| strict `parseVdd` in Web — any element-level fault → the whole figure falls back to *"Diagram coming soon"* | tolerant: it is strict at every level, and the fallback is a calm permanent placeholder (T-S6b-4) |
| `angleMark` `variant: "right"` fills **none** (`fill:"none"`, transparent) | what a right-angle mark usually needs — the §3.2 mapping names it anyway, so verify and prefer the opaque `rect` (T-S6b-3) |
| every figure renders on **white** (`bg-white p-3` in the student renderer) | theme-aware: the student figure area ignores dark mode |
| `a11y.title`/`description` are ENGLISH (OD-12); the schema has no `si`/`en` variant | a rule this skill invented: it matches the product, which has one language-neutral slot |
| `<FigureNotes>` on the Admin card tells the reviewer what `checkDiagram()` and the a11y scan said | acceptance: a document `checkDiagram()` cannot parse still publishes — the notes are advisory, the PUT is not a gate |
| `a11y.description` runs ~85–540 characters on healthy figures | free text: a SHORT description is a smell, an EMPTY one a defect — walk the claim set's `segments`, marks and `labels` and you have written it |

## 2. Three paths, three different dangers

| | Excalidraw canvas | Copy/paste | Path C — VDD JSON → `PUT /onboard` |
|---|---|---|---|
| available on | every `diagram_dsl` field in onboarding edit mode | same | any field, any time |
| silently drops | an unsupported Excalidraw type — **diamond, image, library shapes** (`excalidraw-adapter.ts` `default: break`, T-S6b-1) | anything the same converter cannot carry | ⚠️ **the whole figure**: a doc `parseVddDocument` rejects → `diagram_dsl` stays empty on a `200 OK`. Always `SELECT` back (T-S6b-4) |
| traps | a dark canvas lies about stroke colours (T-S6b-5); refused paint values are NEUTRALISED, not kept (T-S6b-7); "supported by the canvas" ≠ "survives the save" | same converter, same holes | a mistake is *stored* — the document is the figure |
| validating today | "Save" refuses on `unsupportedExcalidrawTypes` | same | nothing — validate it yourself (§4.1) |

Path C — author the JSON in the working dir, write `meta.diagram_dsl` in the publish payload — is the
auditable one, and the one this skill's verification section (§5) is built around.

## 3. Draw from the claim set

### 3.1 Construction, not transformation — this is what makes it THIS skill

On the constructed channel there is no source drawing to copy: the claim set's anchors ARE the
canvas coordinates (read-figure-claim-set §2.3), placed so the stated ratios and angles come out
true. Two rules follow:

**Construct dependent points from the claims, never by rounding convenience.** The `points` block
anchors the free vertices; every dependent point is **constructed** from the claim set's `angle`,
`parallel`, `ratio`, `equal` and `collinear` claims — solve the geometry, place the point, then run
the claims back against YOUR drawing (§5). A point placed "about there" will fail the numeric check
the moment a claim names it — and `vdd-check` recomputes every claim from the drawing.

**The anchors are a contract, not a suggestion.** If you move an anchor to make the drawing prettier
and the claim set still carries the old coordinates, the audit reads a different figure from the one
you drew. Edit the claim set AND the drawing together; `departures:` is where a deliberate change is
declared (§3.6).

#### 3.1a Orientation and framing contract — what must stay true through a canvas change

Every figure has **three coordinate frames**: the **claim-set frame** (the anchors as audited),
the **VDD canvas frame** (the numbers in `diagram_dsl`), and the **student's screen**. Moving
between frames is legal only as a uniform similarity — rotation, translation, uniform scale,
exactly one, applied to every element — plus label placement that keeps each label upright and bound
to its feature.

- **Orientation:** the canvas frame may differ from the claim-set frame by one documented rotation +
  uniform scale (e.g. recentring a figure in its canvas). Record the matrix or `angleDegrees`/`pivot`
  you applied; anything the layout changed is a departure (§3.6). Do **not** apply the transform
  piecemeal — a figure rotated except for one label is a defect no check sees until the render.
- **Point-label binding moves with the points.** A label's offset from its point transforms as a
  vector, not as a fixed "right and up".
- **Framing:** centre the complete visible ink — every stroke, glyph and marker, not just the
  polygon bounds — with balanced clearance at every target width (320 · 375 · 768 px). Both the
  stored document and the reviewer's normalized view (§4.2b) must show the same framing.
- **`vdd-layout.mjs` is the explicit helper for this** (§4.0a): it applies a declared
  orientation/framing transform, measures the ink on both render paths, and refuses geometry it
  cannot certify. Use it whenever you reframe an existing document rather than eyeballing the move.

### 3.2 The element-mapping table

Claims are semantic; elements are geometric. The map most of them take:

| claim set says | draw | ⚠️ the catch |
|---|---|---|
| `segment AB`, `polyline P-Q-R`, `arrow AB` | `line` / `polyline` / `arrow` | a `line` is **exactly** 2 points; a closed 3-point line is a 2-point `polygon` and parses out (§4.3) |
| `angle ABC = θ` | `angleMark` or the wedge + `text` | `angleMark`'s own `label` can render 180° out (**T98**) — a separate `text` element placed inside the angle is the reliable label |
| `right ABC` | `rect` mark at B, or `angleMark` `variant: "right"` | the variant is `fill:"none"` (§1) — a ray inside the angle shows straight through it; draw an **opaque white `rect`** when the claim set says `paint … opaque` or any ray crosses the mark (T-S6b-3) |
| `equal AB CD` / `parallel AB CD` | `tickMark` / `parallelMark` on both segments | the marks are the claim — a missing mark is a missing given |
| `len AB = l` | `side_label` / `dimension` (cookbook) | the number sits mid-segment, OUTSIDE the figure's ink (T98's family: a label is bound by proximity) |
| `point P`, `P on segment QR` | `point` | `r: 0` still renders a `<circle>` in the DOM — coverage by shape count lies (§4.2) |
| `circle centre O radius r`, `sector`, `segment` | `circle` / `arc`; a FILLED sector or segment is a ≤ 2°-sampled `polygon` under an `arc` rim | **never a `path`** for a fill unless nothing else can draw it — the normalizer's `path` branch is the trap T-S6b-9 shipped |
| free text / "not to scale" | `text` | no `$`, no backtick, language-neutral (§4.4) |
| maths | `math` with `latex` | Sinhala inside `latex` is forbidden — the `\text{}` rule |

The cookbook (`tools/vdd_cookbook.py`, `--self-test`, `--demo <dir>`) already knows most of these:
`polygon_sides`, `vertex_labels`, `angle_label`, `right_angle_mask` (opaque), `right_angle_mark`,
`tick_marks`/`parallel_marks`, `filled_sector`/`filled_segment`/`filled_polygon`, `grid`,
`number_line`, `dimension`, `side_label`, `venn`, `pie`, `compass_rose`, `axes`, and the solvers
(`triangle_from_angles`, `foot_of_perpendicular`, `intersect`, `point_at_angle`). W3 extends it.
Keep the canvas ≤ ~360 wide — it is scaled to the phone.

### 3.3 `a11y`: `title` is the figure's name, `description` is its transcript

`a11y.title` is a **name, not a caption**: short, and it names the figure — *"Number line for −2 and
5"*, *"Right-angled triangle ABC (not to scale)"*. What it is not:

| ~~title~~ | why |
|---|---|
| ~~`Diagram`~~ | the placeholder string; **0** rows should carry it — keep it that way |
| ~~`Question 4`~~ | names the question, not the figure |

`description` is the longer form: **state the parts a sighted student can see and an unsighted one
cannot** — which points are joined, which angle is marked, what is labelled. The claim set is the
script for it: walk `segments`, the mark claims and `labels`, in that order, and you have written
it. A short description is a smell; an empty one is a defect.

⚠️ **A description can be wrong in a way no schema check can see.** Every comparative word —
*"steeper"*, *"larger"*, *"above"*, *"between"* — is a claim: the claim set either has it or you are
inventing it. On a question about parallel lines a wrong comparative is read by exactly the students
who cannot see the figure.

**OD-12:** `a11y.title`/`description` have **no `si`/`en` variant**, so a Sinhala-medium student
using a screen reader hears an **English** description while the question is read in Sinhala.
**Write English. Do not invent `title_si`.**

⚠️ **Two labels reach the student and they are not the same string.** The outer `<figure>` carries a
hardcoded generic `aria-label` from the call site (*"Question diagram"*, *"Answer diagram"*) while
your `a11y.title` lands on the inner `role="img"` and `a11y.description` becomes the SVG `<desc>`.
Your title is the only informative name in the tree — and on an answer figure, do not repeat the
word "answer" (§3.7.3).

### 3.4 The element budget

- **≤ 12** — normal.
- **13–32** — fine when the figure is genuinely dense (a number line is ticks + labels).
- **> 32** — **stop and ask what you are drawing.** Past this point you are almost always reproducing
  a construction, a graph-paper plot or a log-table extract — a routing signal, not a limit: decline
  the figure in `content.yaml` rather than heroically drawing it.

Keep the canvas small and honest: the renderer uses `aspectRatio: W / H` with container-query units,
so the numbers only need to be *proportionally* right.

### 3.5 The scale rule, in one line

**Draw the claim set's geometry, which on a constructed figure is the stem's stated geometry.** If
the claim set's `scale:` says the figure is deliberately not to scale, reproduce the **claimed**
values and say *"not to scale"* — in a `text` element, in the stem, or in `a11y.title`. A `text`
element reading *"not to scale"* renders exactly as written.

### 3.6 Write your departures back

Anything you drew that the claim set does not declare — an added right-angle mark, a vertex dot, a
straightened line, a widened gap so two labels do not collide — goes into the claim set's
`departures:` list with a reason. If your departures are not written down, the critic will find them
and call them defects, and it will be right to.

### 3.7 ⭐ Drawing an ANSWER figure — where this skill's assumptions change

⚠️ **This skill's emit line says "on the question, a sub-question or an answer", and the rules above
were written for a figure authored alongside a question.** An answer figure is different: it is drawn
*after* the question exists, usually **on top of** a question figure the student is already looking
at. `author-question-answers` §4.5 decides *whether* an answer needs a figure; this section is *how*
to draw one.

#### 3.7.1 Three shapes, and they have different rules

| shape | when | the rule |
|---|---|---|
| **STANDALONE** — no figure exists for the answer to sit on (question level, parent and siblings all have none) | the artefact **is** the answer (*"draw a number line and mark −2 and 5"*) | you are free. Choose the canvas, the range and the scale for legibility. ⚠️ The apparatus tax below does NOT apply |
| ⭐ **EXTENDING** — the question's figure exists and the answer happens **on** it | the move, the shading, the open-vs-closed endpoint | ⚠️ **reproduce that figure in the SAME frame, range, pitch, labels and orientation** (§3.1a), then add the answer. A student reads the two one under the other; any difference in the apparatus reads as a *second, different* figure and the correspondence — which is the whole point — is gone |
| ⭐ **CONTINUING** — the question's figure shows a **sequence** and the answer is its **next member** | the question figure shows stages 1..n (e.g. a dot pattern) and the answer is stage n+1 | ⚠️ **Match the UNIT, not the whole apparatus**: the same dot radius, the same pitch, the same baseline, so stage 5 reads as belonging to the same pattern. **Do not re-draw stages 1..n** — the student has them. A free-hand redraw at a different scale reads as a different pattern |

⚠️ **There is no overlay.** An answer figure is its own `VddDocument` in its own `<figure>`, rendered
**below** the question's, not on top of it — so *"extending"* means **re-drawing the apparatus in
full**. That has a price:

⚠️ **THE APPARATUS TAX — for an EXTENDING figure ONLY.** The element budget is 32 (§3.4), so the
usable budget for an extending answer figure is `32 − (the question figure's element count)`. A
23-element question figure leaves 9 elements for the answer itself — measured on a real number-line
answer, 27 elements of which 23 were the apparatus and **4** the answer's own content.

⛔ **AND PICK THE SHAPE BEFORE THE BUDGET.** A big question figure is a reason to draw the *unit*
(CONTINUING) rather than a reason to give up — a 30-element dot pattern has no apparatus tax at all
if the answer is the next dot row. Check which of the three shapes you are in BEFORE you compute.

#### 3.7.2 ⭐ Weight, not extent — the thing rendering taught

⚠️ **Measured by rendering at 320 px: an extending answer figure is mostly the question's figure, so
the addition cannot be told apart by SIZE and must be told apart by WEIGHT.** A number-line hop whose
length is fixed by the maths may be a fifth of the picture — and at 2 px floating free of the ticks
it is *invisible*, reading as the same figure with a dot on it. The fix, measured:

- **Put the added elements ON the apparatus they refer to**, not floating near it. A hop between the
  ticks for 4 and 6 must start and end at those ticks' own coordinates.
- **Give them a heavier `stroke.width` than the apparatus** — the answer is the thing being revealed
  (3.5 px against the axis's 2 px, in the measured case).
- **Land the addition on the furniture** — hops landing on the tick tops, the landing point a filled
  `circle` at `r: 6`; delete decoration nobody can see (a departure invisible at 320 px is worse than
  none).
- **Put a label on the addition on the far side from the apparatus's own labels.** `"+2"` above a hop
  reads correctly only because it sits adjacent to the hop bar and not the tick row — a label is
  bound by proximity, not by intent (T98's family).
- ⚠️ **Do not author colour.** The defaults are the whole palette (T-S6b-7), so weight and position
  are the only levers you have.

⚠️ **AND THE ONE MISTAKE TO EXPECT: cropping.** The obvious move is to draw only the part of the
apparatus the answer touches — fewer elements, a bigger, clearer move. Rendered side by side at
320 px it is a **better standalone picture and a worse answer**: the tick pitch and range differ from
the question's, so the student compares two number lines instead of watching one being used. ⇒ **On
an extending figure, legibility loses to correspondence.**

#### 3.7.3 `a11y` on an answer figure — the title carries the ANSWER

The §3.3 rules apply unchanged. Two things are different:

1. ⭐ **The title must state what the figure SHOWS, which on an answer figure is the answer.**
   *"Number line marked from -3 to 7"* is a good question-figure title and a lie of omission on the
   answer. Write *"Number line from -3 to 7 with two unit steps right from 4, landing on 6"*. A
   student who cannot see the figure gets the name first and may get nothing else.
2. ⚠️ **The outer `<figure>`'s own label is `"Answer diagram"`, hardcoded at the call site.** The
   tree reads *"Answer diagram"* then your title. **Do not repeat the word "answer" in your title.**

⚠️ **A capability with one instance has that instance AS the instruction** — before copying a live
answer figure's `a11y`, read it: the first one shipped `title = "Diagram"`, `description = ""`, and a
blind student heard *"Answer diagram … Diagram, image"* on a question whose answer **is** the figure.
The review surface already warns (FigureNotes mounts on every answer's DiagramField with an
answer-specific label), so a defective answer figure is now an authoring choice, not an invisible one.

#### 3.7.4 Verifying an answer figure — §5 with one substitution

There is no printed figure to compare against, so the numeric checks substitute as follows, and §5.2
coverage plus §4.2 rendering apply unchanged:

| §5 check | on an answer figure |
|---|---|
| numeric, for the re-drawn apparatus | compare against the **question's figure**, not just internally: same ratios, same pass band. A re-drawn number line whose pitch drifted is a different scale from the question's |
| ⭐ the apparatus's own PROPORTIONS | ⛔ length ratios did **not** catch this, and a live pair proves it: identical axis lengths, every named-point ratio passing, while `text.fontSize` drifted **+73%** and the tick-height-to-axis ratio drifted **69%**. ⇒ **Diff these explicitly, element class by element class: `text.fontSize`, tick length, `stroke.width`, canvas aspect ratio.** They are apparatus *proportions*, not geometry, so no ratio check can see them |
| numeric, for the **added** elements | assert them against the **answer's own arithmetic**: the hop spans `(6−4)/(7−(−3)) = 0.2` of the axis, so `len(hop)/len(axis)` must be `0.2 ± the pass band`. ⚠️ This is a real check and it fires — a hop drawn 4→5 gives 0.1 and passes `safeParse`, `checkDiagram()` and every render assertion |
| §5.2 coverage | unchanged — and worth more here, because the apparatus is re-typed rather than copied: one dropped numeral is a hole in the middle of a number line and nothing else would see it |
| ⭐ the side-by-side | **render the question's figure and the answer's one under the other at 320 px and look.** If you cannot see the difference in one glance, the answer figure adds nothing and the right answer was text-only. This check exists only on the answer side |
| §3.6 `departures:` | **every added element is a departure by construction** — the question's figure contains none of them. List them as one entry with the reason; that is what the answer figure *is* |

---

## 4. Validate before you write

### 4.0 ⭐ ONE COMMAND — `vdd-check.mjs` runs §4.1, §4.2, §4.2b, §5.2 and §5.3 together

```bash
node tools/vdd-check.mjs --self-test            # first, once per session
node tools/vdd-check.mjs q7.json --claims q7-claims.txt --out /tmp/vdd/q7 --json
```

It bundles `@vibhaga/shared/vdd-schema` and Admin's own `validate.ts` / `normalize.ts` /
`DiagramRenderer.tsx` with Admin's esbuild (nothing in `Vibhaga-Admin` is edited or installed; the
bundle is cached by source mtime **+ the tool's own hash**) and runs, in order: `safeParse` ·
`a11y.title` real + `description` present · label hygiene (`$`, backtick, Sinhala) · the ≤ 32 budget ·
`path` elements reported · `checkDiagram()` (advisory) · **normalize consistency** (every element
moved by the same (dx, dy) on the reviewer's card) · **claim-set coverage** (`segments` covered,
`labels` carried once, `points` anchored) · **NUMERIC comparison** of every
`angle`/`right`/`ratio`/`collinear`/`on`/`parallel`/`equal`/`circle` claim recomputed from the claim
set's stated values and canvas anchors and from the drawing, on the single tight band (§5.3) · a
**Chromium render of BOTH code paths** at 320 · 375 · 768 with screenshots and the SVG read back ·
**label metrics**: every `<text>` bbox ≥ 8 rendered px from the canvas edge and ≥ 6 rendered px from
stroke geometry — rendered px at each width (viewBox units shrink on a narrow render), measured to the
stroke's EDGE (centreline − half its width); a bbox that cannot be measured fails closed.
Exit 1 on any hard failure; `--allow K6` downgrades a numeric finding that is a **declared**
departure (write it in `departures:` first). Canvas anchors come from `<figure>.anchors.json` (the
cookbook writes it), `meta.anchors`, or every `point` element labelled with one capital.
**It cannot tell you the claim set's stated geometry is the right geometry** — that judgement is the
read-figure-claim-set skill's, and the critic's re-check remains necessary. And the tool does not
look at the screenshots: you do (§4.2).

**Draw with the cookbook** — `tools/vdd_cookbook.py` (`--self-test`, `--demo <dir>`). **And measure
inline maths with the real renderer**, not the estimator, when a run is anywhere near its box:
`tools/measure-inline-math-width.mjs --fields <[{id, field, text}]>`.

### 4.0a Explicit layout helper recipe

[`tools/vdd-layout.mjs`](../../tools/vdd-layout.mjs) implements §3.1a's layout/framing gates for an
existing document, with its own test suite (`tests/test_vdd_layout.mjs`, `node --test`). It is the
reframing path — not a drawing tool.

```bash
node tools/vdd-layout.mjs --help
node tools/vdd-layout.mjs \
  --input source.json --anchors source.anchors.json --config explicit-layout.json \
  --out /existing/directory/NEW-prefix
# Optional CLI flags: --admin /path/to/Vibhaga-Admin  --headed
```

```json
{"angleDegrees":-3,"pivot":[100,100],"reference":"actor supplied baseline reference","framing":{"mode":"bounded-artwork","declaration":"Finite artwork, not a clipped unbounded region"},"canvas":[400,320],"padding":32,"band":"vector","quantizationBudgetPx":2}
```

- **Frames:** `pivot` and sidecar anchors are in the **input VDD canvas**. Positive angles are
  clockwise in screen x-right/y-down coordinates; `reference` must identify the audited baseline and
  evidence. Stored geometry uses one exact positive uniform similarity; glyph baselines stay upright
  and point-label binding offsets transform. No reflection/shear/nonuniform scale. Matrix convention:
  `[a,b,c,d,e,f]`, `x'=a*x+c*y+e`, `y'=b*x+d*y+f`.
- **Supported subset, not the full VDD union:** `line polyline polygon arrow point text math circle
  rect path`; `rect` becomes a path, including rounded corners. Paths accept absolute **M/L/Q/C/A/Z
  only**. `ellipse arc angleMark tickMark parallelMark`, unknown fields/types and existing nonzero
  local `rotation` refuse: explicitly regenerate/pre-bake supported geometry and verify its
  semantics; do not drop marks or rotation fields to pass. The helper cap is 1–1000 elements; the
  ≤32 budget still applies. Canvas dimensions 80–4096, padding ≥8 and below half the shorter
  dimension.
- **Measurement/gates:** installed Admin dependencies and actual compiled Inter/Noto assets are
  required; nothing is installed. Stored + normalized paths are measured at all three
  student-content widths. Normalization must be a precision-preserving common translation (bounded
  IEEE-754 roundoff) or observed legacy translation plus integer rounding (≤0.5 per axis), within the
  angle/ratio bands and the measured CSS budget. Empty rounding audits require uniform translation;
  collapse, winding, linear-intersection and arrow gates remain active. Optional config `critical`
  adds declared strict constraints
  (`[{"kind":"collinear","points":[["edge-a",0],["edge-b",0],["edge-c",0]]}]`). Optional `claimsText`
  is claim-set **text**, not a path, and checks supported numeric preservation only.
- **Extending pairs — API, not two CLI fits.** In one frame, transform both originals by the same
  explicit matrix into a generous common canvas, `measureUnion` → `fitMeasuredUnion` →
  `compose(fit, orientation)`, then `validateCommonFrame(members, {mode:"common-frame", …})` and
  `writeCommonFrameOutputs`. Never independently rotate/fit/crop the two members.
- **Commit/consume contract:** a run writes `.json`, `.anchors.json`, `.raw.anchors.json`,
  `.layout.json` and **`.manifest.json` LAST**, after payload fsync; all paths must be NEW in an
  existing directory. **Every consumer calls `loadOutputs(prefix)`** — it refuses missing, partial,
  tampered or incompatible bundles. Interrupted payloads are not usable; never overwrite. Active
  `meta.anchors` and the output sidecar are **STORED_OUTPUT_CANVAS**; the byte-preserved raw sidecar
  is **INPUT_VDD_CANVAS**.
- Layout refusal exits 1 with JSON on stdout; invalid inputs exit 2 on stderr. Even exit 0 has
  `semanticApproval:false`: run §4.0/§4.1 and full §5 checks on the manifest-validated output and get
  a fresh visual read at all widths.

### 4.1 `parseVddDocument` + `checkDiagram()` — run them yourself, on path C

The schema is the shared package — **`@vibhaga/shared/vdd-schema`** in `Vibhaga-Admin`'s
`node_modules`. Bundle `checkDiagram()` with the repo's own `esbuild` into a throwaway directory
(do **not** add a dependency, do **not** edit `Vibhaga-Admin`):

```bash
mkdir -p /tmp/vibhaga-vdd
B=Vibhaga-Admin/node_modules/.bin/esbuild
$B Vibhaga-Admin/src/components/diagram/validate.ts --bundle --format=esm --platform=node --outfile=/tmp/vibhaga-vdd/validate.mjs
node -e 'Promise.all([import(require("path").resolve("Vibhaga-Admin/node_modules/@vibhaga/shared/dist/vdd-schema/index.js")), import("/tmp/vibhaga-vdd/validate.mjs")]).then(([v,c])=>{
  const doc = JSON.parse(require("fs").readFileSync("/tmp/vibhaga-vdd/figure.json","utf8"));
  const r = v.parseVddDocument(doc);
  if (!r.ok) { console.error("INVALID", JSON.stringify(r.errors,null,1)); process.exit(1); }
  const t = ((doc.a11y||{}).title||"").trim();
  if (!t || t === "Diagram") { console.error("a11y.title missing or generic"); process.exit(1); }
  console.log("ok:", doc.elements.length, "elements,", JSON.stringify(t));
  console.log("advisory:", JSON.stringify(c.checkDiagram(doc)));   // report, never block
})'
```

A **correct** figure can produce warnings — e.g. *"Angle labelled 125° is drawn ≈ 100°"* on a
deliberately not-to-scale drawing — which is exactly why §0 says advisory. (`checkDiagram()`'s
triangle-angle-sum check needs three numeric labels, so it stays quiet when one label is `x`.)

### 4.2 ⭐ Render the real component and READ THE OUTPUT — the check `safeParse` cannot be

⚠️ **This is the step that separates "the document is legal" from "the figure says what I meant".**
Two surfaces, in order of cost:

**(a) `/diagtest`, for the review surface.** `cd Vibhaga-Admin && npm run dev`, then
`http://localhost:3000/diagtest` — it renders the real components with **no auth and no API**. It
renders **fixtures**, not your document, and you may not edit `Vibhaga-Admin` to add one.

**(b) A throwaway harness, for your own document.** Bundle Admin's real `DiagramRenderer` — the same
component `/diagtest` uses — against a page you control. Symlink Admin's `node_modules` so the
bundler resolves React; nothing in `Vibhaga-Admin` is touched.

```bash
mkdir -p /tmp/vdd-harness && cd /tmp/vdd-harness
A=/path/to/Vibhaga-Admin                    # resolved: --admin flag > $VIBHAGA_ADMIN > sibling checkout
ln -sfn "$A/node_modules" node_modules
cp "$A/node_modules/katex/dist/katex.min.css" .
cat > entry.tsx <<'TSX'
import { createRoot } from "react-dom/client";
import { DiagramRenderer } from "@/components/diagram/DiagramRenderer";
import { parseVddDocument } from "@vibhaga/shared/vdd-schema";
import { checkDiagram } from "@/components/diagram/validate";
const doc = (window as any).__FIGURE__;
const r = parseVddDocument(doc);
if (!r.ok) { console.log("INVALID", JSON.stringify(r.errors)); }
else {
  console.log("advisory", JSON.stringify(checkDiagram(r.value)));
  const host = document.getElementById("fig")!;
  createRoot(host).render(<DiagramRenderer dsl={r.value} />);
}
TSX
"$A/node_modules/.bin/esbuild" entry.tsx --bundle --format=iife --outfile=bundle.js \
  --tsconfig="$A/tsconfig.json" --loader:.tsx=tsx --define:process.env.NODE_ENV='"development"'
```

`index.html` needs `katex.min.css`, a `<div id="fig">` sized to the width you are testing, the
tailwind utilities the renderer uses (`relative absolute w-full h-full inset-0 overflow-hidden
pointer-events-none`), a `<script>` setting `window.__FIGURE__`, then `bundle.js`. Serve it
(`python3 -m http.server`) and drive it with a **headed** Playwright Chromium.

⭐ **4.2b Render EVERY surface, not one.** ⚠️ **The reviewer's card is a different code path from the
student renderer, and a figure verified on one was wrong on the other.**

| surface | code path | what differs |
|---|---|---|
| Vibhaga-Web study view · this harness's `<DiagramRenderer dsl={doc}/>` | the document as stored | canvas = your `canvas` |
| Admin **StudentPreview** and **DiagramField** | parsed document → `normalizeVdd` → `DiagramRenderer` | content refitted to a normalized frame; check the checked-out Admin's normalizer actually preserves your stored canvas — that behaviour has shipped, been broken, and been fixed |
| the OG image (`/q/[id]` share preview) | server-side raster of the same document | nothing you can check here; it follows Web |

The harness renders **both** paths side by side and you read both DOMs:

```tsx
import { normalizeVdd } from "@/components/diagram/normalize";
// … after safeParse:
createRoot(rawHost).render(<DiagramRenderer dsl={r.data} />);                 // student surfaces
createRoot(cardHost).render(<DiagramRenderer dsl={normalizeVdd(r.data)} />); // the reviewer's card
```

and asserts, per element, that the card's translation moved **everything by the same (dx, dy)** — a
fill and the line it abuts must coincide in both renders. ⚠️ **Rounding is the second difference**: a
2°-sampled polygon's vertices can be rounded on the card, reading as a faintly rough edge unless an
`arc` rim is drawn over it (§3.2). Then, after publishing, **open the real card** and read its SVG
once more — the harness bundles the Admin source you have checked out, not the Admin that is deployed.

**Then assert on the SVG, not on your intent:**

```js
// in page.evaluate()
const svg = document.querySelector('[role="img"] svg');
({ ariaLabel: document.querySelector('[role="img"]').getAttribute("aria-label"),
   desc:      svg.querySelector("desc")?.textContent,
   texts:     [...svg.querySelectorAll("text")].map(t => t.textContent),           // every label that RENDERED
   labelXY:   [...svg.querySelectorAll("text")].map(t => [t.textContent, +t.getAttribute("x"), +t.getAttribute("y")]),
   shapes:    svg.querySelectorAll("line,polyline,polygon,circle,ellipse,rect,path").length })
```

- `texts` against your claim-set `labels` — this is how a dropped mark label shows up: two
  `angleMark`s both carrying `label: "90°"`, **one** `<text>` in the output.
- `labelXY` against the angle each label names — an `angleMark` label computed as the arithmetic mean
  of two edge angles points the wrong way when the edges differ by more than 180° (**T98**). The
  workaround is a `text` element (§3.2); **run this check rather than trusting a fix is deployed**.
- `shapes` against your claim-set `segments` — ⚠️ **it over-counts**: a `point` with `r: 0` is still
  a `<circle>` in the DOM, and an arrowhead marker's `<path>` inside `<defs>` counts in every figure.
  Count by tag and scope out `defs`; **a raw total is a smell detector, not the coverage check.**
- ⚠️ **`aria-label` and `desc` are the only thing an unsighted student gets.** Read them as prose
  against §3.3's rule that every comparative word is a claim.

⚠️ **If you masked anything with a `fill` (T-S6b-3), verify at 320 px that the masked ray still reads
as MEETING the vertex.** An opaque mark hides the stroke inside it, so at a phone's width a ray can
look like it stops short of the corner — a different figure. A mark much bigger than ~0.16 × its
adjacent side stops reading; shrink it and re-render.

⚠️ **Look at the picture, too.** Screenshot at **320 · 375 · 768** px and read them: a label
overlapping a line, a label outside its angle, a right-angle mark bisected by a ray were all found
that way. The new label metrics in `vdd-check` (§4.0) measure the first two classes numerically —
the eye still owns the rest.

### 4.3 What the schema rejects that looks fine

- `polygon` with **fewer than 3** points — a closed 3-point line loses its duplicated closing vertex,
  becomes a 2-point "polygon", is saved, then discarded by `parseVdd`, so the figure **simply never
  appeared**, with no error anywhere.
- `line` with anything other than **exactly 2** points.
- `polyline` / `arrow` with fewer than 2.
- `path.d` containing any command outside `M L Q C A Z`.
- a missing or empty `id`, a non-positive canvas dimension, or `schema` ≠ `"vibhaga.diagram"`.

### 4.4 What nothing rejects — so you must

- a **mistyped element type** → publishes `200`, then is skipped by both renderers ⇒ **a triangle
  with no hypotenuse**;
- a **missing `a11y`** ⇒ an image-role element with no accessible name;
- **200 elements**;
- a **`$` or backtick in a `text` label** ⇒ reaches the student verbatim;
- **Sinhala inside a `math` element's `latex`** ⇒ forbidden (`\text{}` rule) and renders as garbage;
- ⚠️ **a claim from the claim set that has no element at all** ⇒ §5.2, and the reason this skill
  exists in the same half as the verification;
- ⚠️ **a drawn number the stem never stated** ⇒ the stem-ratio check in `audit-claim-set.py` (§5.3a)
  is the backstop — every `ratio`/`angle` claim's value must be derivable from the stem's own numbers
  or a cited `derive`, so a copied-anchor mistake is caught before the render ever runs.

---

## 5. ⭐ Verify NUMERICALLY, not by eye

### 5.1 The invariants that survive a canvas change

A VDD lives in its own canvas, so absolute coordinates mean nothing across documents — **ratios and
internal angles do**, and they are exactly what a maths figure means. On the constructed channel the
claim set's anchors are canvas coordinates, so the comparison is direct: **the drawing's geometry
against the claim set's stated values and anchors**, under the §3.1a frame contract (a legitimate
rotation/translation must not fail a raw-coordinate match; ratios and unsigned angles alone cannot
catch a mirror — also check topology, winding/chirality, arrow direction and label attachment).

Check:

- **angles** at every named vertex;
- **length ratios** between named segments (never absolute lengths);
- **collinearity residuals** — a point's perpendicular distance from a line, as a fraction of that
  line's length;
- **parallelism residuals** — the angle between two segments claimed parallel;
- **equal-length residuals** for every `equal` claim.

### 5.2 The claim-set coverage check — the one that catches a deleted side

Text-only. Needs the claim set and the VDD JSON, **not** the picture:

- every `segments` entry is **covered** by some element: an element whose endpoints are the claim's
  two points, or a `line`/`polyline` on which both points lie within tolerance;
- every `labels` glyph appears in exactly one element's `label` / `value` / `latex`;
- every `points` entry has an element that anchors it (a `point`, or a shared endpoint);
- no element the claim set does not account for, unless it is listed in `departures:`.

⚠️ **This is the check whose absence deleted a side from a worked example once** (**T99**): the
element count matched the intent list because the intent list was written by the same reader who
dropped the side. **Count against the claim set, never against your intent.**

### 5.3 The single constructed band

`vdd-check` recomputes every `angle`/`right`/`ratio`/`collinear`/`on`/`parallel`/`equal`/`circle`
claim twice — once from the claim set's own anchors/stated values, once from the drawing — and
compares them on **one band, because every figure is authored on the canvas**:

| channel | band |
|---|---|
| `constructed` (the only channel this plugin draws) | **≤ 2% on a ratio · ≤ 1° on an angle · ≤ 1% on a residual** |

State the pass band before you measure, and record anything outside it as a departure or a defect,
not as noise — a deliberate not-to-scale figure declares `scale:` in the claim set and an
`allow: K<n>` line carries it through the check.

### 5.3a ⭐ The stem-ratio check — drawn-vs-STATED, the check the audit added

The numeric band proves the drawing matches the claim set. It does **not** prove the claim set's
numbers are the stem's — a value copied from the anchors, or invented, matches itself perfectly.
`tools/audit-claim-set.py` closes that gap for `channel: constructed` sets: every `ratio`/`angle`
claim's value must be justified by the numbers in the claim set's required `stem:` header — within
tolerance of some pair of stem numbers — or must cite a `derive Kn` claim whose value matches.
Failure means the drawn number is not justified by the stem (a copied-anchor smell) and the claim id
is named. Run it before `vdd-check`; it is cheaper than a render.

### 5.4 The verification record

Emit it with the figure, and keep it for the orchestrator and later maintenance — **not** as a
substitute for the critic's independent re-check. Include the frame mapping (§3.1a), separate
construction/typography departures, and measured label clearances at each width on both paths. Mark
orientation and framing separately pass/fail/unverified. For extending pairs record the shared
envelope, common translation/viewport scale and on-screen pitch, plus each member's ink-center offset
as a controlled pair-framing exception. A checker exit 0 alone proves neither:

```
figure:   q3i
channel:  constructed
safeParse: pass        a11y.title: "Right-angled triangle ABC with BC produced to D (not to scale)"
advisory:  []          elements: 12 of a 32 budget (4 line, 1 rect, 6 label-only point, 1 text)
scale:     the claim set says NOT to scale, so BOTH visible consequences are in the document —
           `a11y.title` ends "(not to scale)" and a `text` element reads "not to scale" (§3.5)
coverage:  segments 6/6 covered · labels A B C D E F all present · the mark drawn · 0 unaccounted elements
numeric:   4 ratios <= 0.66% · 5 angles <= 0.30° · collinearity residuals below band · vs claim-set anchors
labels:    every <text> ≥ 8 rendered px from canvas edge, ≥ 6 rendered px from stroke edges, at 320 / 375 / 768 px
rendered:  320 / 375 / 768 px, light + dark — labels legible, none overlapping a stroke
departures: the right-angle mark drawn as a white-filled `rect`, not `angleMark variant:"right"` — the
            variant is `fill:"none"` and the ray shows through it (T-S6b-3). Same corner, same size, opaque.
            "(not to scale)" appended to `a11y.title` and a `text` element added — declared by the claim
            set's `scale:` block (§3.5).
```

### 5.5 Orientation/framing fixture checklist

Exercise these positive **and** negative cases when verifying this guidance on figures; record
observed outcomes. This is a checklist, not a claim that `vdd-check` self-tests implement them.

| Case | Must pass | Must fail |
|---|---|---|
| Rotated / re-centred layout | Same figure restored in the documented frame; unchanged ratios/internal angles and inverse-map agreement | Transform applied twice, reflection, or a genuine shape error excused as rotation |
| Intentional oblique / prism | Base/semantic frame correctly oriented while slopes, depth edges, chirality and NOT-to-scale angles survive | Longest-edge leveling that changes meaning; flattening depth; unjustified shear/homography or idealized angles |
| Single bounded figure with off-center long label / arrow / math | Complete visible ink centered with balanced clearance on stored + normalized paths at 320/375/768 | Polygon-only bounds, clipped glyph/arrow/stroke, or invisible helper elements faking normalization bounds |
| Extending question/answer pair | Same frame/range/pitch/proportions and viewport scale; shared visible-ink envelope centered once with common translation, readable additions; individual ink-center offsets recorded as a controlled pair-framing exception | Independent centering/rotation/rescaling/cropping breaks correspondence; normalization changes common scale/shared framing; clipping or hidden pads |

## 6. Traps — stories with the catch

Cross-cutting: [`docs/TRAPS.md`](../../docs/TRAPS.md) — **T96** (legal is not rendered), **T98** (an
`angleMark` label 180° out), **T99** (a collapsed segment), **T61** (a refused paint value is
neutralised, and the two surfaces disagreed about it). These are this skill's own:

### T-S6b-1 — The diamond that renders perfectly and is not saved
**Looked true:** the shape is on the canvas and the preview looks right, so it is in the document.
**Actually:** `excalidrawToVddElements` handles six Excalidraw types and ends with `default: break` —
unknown type → skip, 0 console warnings, no UI signal. The toolbar still offers **diamond** and
**image**, and the Library button loads third-party shapes. Draw one, save, and it is absent from the
stored VDD. Pasting has the same hole.
**The check:** the canvas surfaces `unsupportedExcalidrawTypes` at Save; on path C, run §5.2's
coverage check — and never assume a shape survived because you saw it.

### T-S6b-2 — The gate that could not see the loss it was built for
**Looked true:** the unsupported-type gate covers silent VDD loss.
**Actually:** it inspects **Excalidraw element types only**. Real silent losses used *entirely
supported* types: semantic marks downgraded to `polyline` + `text`, and a closed 3-point line
becoming a 2-point `polygon` the schema rejects — saved, then discarded, the figure never appearing.
**The check:** validate the **document** (`parseVddDocument`), not the element types.

### T-S6b-3 — The right-angle mark you can see through
**Looked true:** `angleMark` with `variant: "right"` is *the* element for a right angle.
**Actually:** the renderer draws that variant as a `polyline` with **`fill: "none"`** —
**transparent** — and a right-angle mark sits *inside* the angle it marks, so **any ray inside that
angle shows straight through it**. Rendered side by side at 320 px, a transparent mark near a ray's
own angle reads as marking the ray's angle instead of the corner's — on a question asking about the
corner's angle.
⚠️ **Compute the containment; do not infer it from "the figure has a mark and some rays".**
**The check:** when the claim set says `paint … opaque`, or any ray lies inside the marked angle,
draw the mark as a **`rect` with `fill: {color: "#ffffff"}` positioned AFTER the lines** — array
order is paint order — instead of, or beneath, the `angleMark`. Then **render both and look**. ⇒
`fill: "none"` on `angleMark` is a real element-union gap with a NAME; *"the union cannot do it"*
without the element name and the workaround you tried is not a reason (§0).

### T-S6b-8 — The answer figure that is the question's figure again
**Looked true:** the answer needed a figure, so it got one; `safeParse` passes, `checkDiagram()` is
silent, coverage finds every claimed segment, the numeric comparison is inside the band, the render
reports every label. **Every check green — several of them green *because* the answer figure
reproduces the question's.**
**Actually:** the addition can be missing, or too faint to see, and nothing above notices: a
number-line answer whose own content is a fifth of the picture shipped 1.2 px dashed risers
**invisible at 320 px** while the hop floated free of the ticks it joined. Reading the SVG could not
catch it — the elements were all there. ⚠️ **And the worse sibling:** a *complete copy* of the
question's figure passes every check perfectly.
**The check:** §3.7.4's side-by-side at 320 px, plus the arithmetic assertion on the added elements.
⇒ **A verification aimed at fidelity cannot see whether you added the thing that was not in the
source** — T99 with the polarity reversed.

### T-S6b-4 — "Diagram coming soon" is not a loading state
**Looked true:** the figure is still rendering, or the API has not returned it yet.
**Actually:** `parseVdd` returned `null` and the renderer fell back to the calm placeholder. It will
say that **forever**. The strict `parseVddDocument` rejects on a wrong `schema` string, a non-numeric
canvas dimension, a non-array `elements`, or any element-level fault — and the whole figure is gone
with no error.
**The check:** after publishing a figure, load the student page and confirm an `<svg>` exists —
`document.querySelector('[data-diagram-id] svg')` — not merely that the card rendered.

### T-S6b-5 — The canvas is light in dark mode, and that is deliberate
**Looked true:** the white slab in a dark dialog is an oversight; `theme="dark"` fixes it.
**Actually:** Excalidraw's theme moves the **canvas** as well as the chrome, so an operator authoring
against a dark canvas picks stroke colours that read there and are near-invisible in the student app,
which renders the figure on **white**.
**The check:** judge stroke colours against the **Live preview** panel (white), never the canvas.

### T-S6b-6 — The bilingual figure that cannot exist (rescoped: medium decides, not "never")
**Looked true:** the question is bilingual, so the figure gets Sinhala labels for the Sinhala medium.
**Actually:** `text.value` is one `z.string()` and there is one `diagram_dsl` per node — a figure
cannot be bilingual. That is the whole constraint; it was over-applied once as *"figures never carry
Sinhala prose"*, which stripped a tally table's headers into declared stem prose and left the
rendered table visibly broken — caught on sight. **On a mono-medium Sinhala question the figure's
structural labels belong IN the figure**: table column headers, row labels, axis/category names —
anything inside the figure border. What stays forbidden: Sinhala inside `math.latex` (KaTeX cannot
shape it), prose captions that belong in the stem regardless of medium, and any Sinhala label on a
figure whose question is not sinhala-medium. `a11y` stays English per **OD-12**. `vdd-check.mjs`
enforces this via `--medium sinhala`; `build-staged` threads the run's scope medium automatically.
**The check:** if a figure needs *prose* to be understood it is the wrong figure; but if removing a
*label* makes a table or chart unreadable, the label was structural — draw it in the question's
medium.

### T-S6b-7 — A refused paint value is NEUTRALISED, and the two surfaces disagreed about it
**Looked true:** the colour hardening landed in both repos, so both show the same figure.
**Actually:** an authored VDD colour used to reach a `fill`/`stroke` unchecked, so a crafted value
could make a student's page fetch an attacker-chosen URL. Both apps now **neutralise** a refused
value — but on the same document Admin once drew **no SVG at all** while Web drew the figure with the
stroke neutralised, so the review surface told a reviewer the opposite of what a student gets
(**T61**).
**The check:** view a figure on **both** surfaces before you accept it; treat *"Admin shows
nothing"* as a finding about Admin rather than about your figure. ⇒ And do not author colours: the
defaults are `#1f2937` on white.

---

### T-S6b-9 — The figure was right on every surface but the one the reviewer uses
**Looked true:** a shaded-semicircle figure passed `safeParse`, `checkDiagram()`, a numeric check,
and a Chromium render of the real `DiagramRenderer` at 320 · 375 · 768 px; the student preview
showed it too. Published.
**Actually:** the owner opened the onboarding card and saw the grey shading standing **30 px to the
right** of the semicircle it belonged to. The card is the one surface that runs `normalizeVdd`
first — a fit-to-content pass that translates every element — and its `translateElement` had
`default: return el` for `path`. The fill was the first live `path` in the corpus, so nothing had
ever exercised that branch; every other element moved −30 px and the path stayed. Three renders,
three green gates, and the reviewer's screen was the one not looked at.
**The check:** §4.2b — render the stored document AND `normalizeVdd(document)` side by side and
assert the card's translation moved every element equally; after publishing, read the deployed card's
SVG. And prefer primitives: a filled curved region is a ≤ 2°-sampled `polygon` under an `arc` rim
(§3.2), not a `path`. The rule stands regardless of any fix, because *"which surfaces run which
code"* is exactly the thing a green harness cannot tell you.

## 7. Verify (definition of done, per figure)

- [ ] A **claim set exists** and this figure was drawn from it (§3) — not from memory, not from an
      unclaimed sketch.
- [ ] Dependent points were **constructed from the claims** (§3.1), and every `collinear` residual in
      the drawing is inside the band (§5.3).
- [ ] ⭐ **`audit-claim-set.py <claim set>` exited 0** — including the stem-ratio check (§5.3a).
- [ ] ⭐ **`vdd-check.mjs <figure> --claims <claim set>` exited 0** (§4.0) — §4.1 + §4.2 + §4.2b +
      §5.2 + §5.3 + label metrics in one run; the lines below are what it asserts.
- [ ] `parseVddDocument` returns `ok` (§4.1) — run, not assumed.
- [ ] `a11y.title` is non-empty, is not `"Diagram"`, and describes the **figure**;
      `a11y.description` is present, English (OD-12), and **every comparative word corresponds to a
      claim** (§3.3).
- [ ] Every label is language-neutral; no `$`, no backtick, no Sinhala in any `text.value` or
      `math.latex`:
      `jq '[.elements[] | select(.type=="text" or .type=="math") | (.value // .latex)]' figure.json`
- [ ] Element count is within budget (§3.4); if > 32 you have justified it or declined the figure.
- [ ] ⚠️ **The figure was RENDERED and the SVG read** (§4.2): `texts` matches the claim set's
      `labels`, every angle label lies **inside** the angle it names (**T98**), and no field you set
      is missing from the output (**T96**).
- [ ] ⭐ **Rendered on BOTH code paths** (§4.2b): the stored document AND `normalizeVdd(doc)`, every
      element translated by the same (dx, dy); after publishing, the deployed card's SVG read once
      more. No `path` element unless nothing else can draw the shape (**T-S6b-9**).
- [ ] ⚠️ **The coverage check passed** (§5.2). **T99** is what this line is for.
- [ ] ⚠️ **The numeric comparison ran** (§5.3), inside the stated band, and its table is in the
      verification record (§5.4).
- [ ] `checkDiagram()` warnings are resolved **or** explained by the claim set's `scale:` (§5.3).
- [ ] Screenshots read at **320 · 375 · 768** px: no label overlapping a stroke, no label outside its
      angle, nothing clipped — and the label metrics agree (≥ 8 rendered px edge, ≥ 6 rendered px stroke).
- [ ] **Orientation passed (§3.1a):** frame applied, evidence retained, upright labels, no invented
      givens/reflection or flattened intentional geometry; exact map and justification recorded.
- [ ] **Framing passed (§3.1a):** complete visible-ink bounds/clearances on stored and normalized
      paths at 320/375/768. No clipping/hidden pads; §5.5 outcomes explicit.
- [ ] `departures:` written back into the claim set, with a reason each (§3.6).
- [ ] ⭐ **If this is an ANSWER figure** (§3.7): `author-question-answers` §4.5 says which limb fired
      · **which of the three shapes** — STANDALONE, EXTENDING or CONTINUING — because the budget and
      fidelity rules differ · an **extending** figure reproduces the apparatus to the same range,
      pitch and labels **and its PROPORTIONS** (`fontSize`, tick length, `stroke.width`, aspect —
      §3.7.4: a live pair drifted **73%** on `fontSize` with every length ratio passing), and fits
      `32 − (the question figure's element count)` · the added elements are **heavier** than the
      apparatus and anchored **on** it · the **side-by-side at 320 px** shows the difference in one
      glance · the claim set carries a **`derive`** claim and `audit-claim-set.py` exits 0 ·
      `a11y.title` states **the answer** (§3.7.3).
- [ ] After publish, a direct `SELECT` shows the document you wrote — ⚠️ **on the right table and
      key**: `questions … question_id`, `sub_questions … sub_question_id`, `answers … answer_id`,
      `sub_answers … sub_answer_id`. Reading `questions` back after writing an answer figure returns
      the QUESTION's figure, or NULL, and either looks like a clean result.
- [ ] The student page shows an actual `<svg>` (T-S6b-4), on the medium the question is scoped to.
      ⚠️ **On an answer figure, Reveal first** — the worked answer is behind the reveal, so a
      collapsed card shows no answer `<svg>` and a check that stops at page load passes on a figure
      that never renders.

---

## 8. Keep this skill alive

Line numbers in `DiagramCanvasInner.tsx`, `excalidraw-adapter.ts` and both renderers have moved
repeatedly — and `vdd.ts` is deleted outright: the schema is `@vibhaga/shared/vdd-schema`. **Re-grep
before citing, and update this file when you find drift.** ⚠️ **Dropped-field and label-placement
traps are a SURFACE to sweep, not bugs to fix once**: render each element type twice, with and
without a field, and diff the SVG — that is how all of them were found. Cross-cutting traps go to
[`docs/TRAPS.md`](../../docs/TRAPS.md); drawing and verification ones belong in §6 here, as a **story
with the catch**. Run `tools/check-suite.py` before every commit.

⚠️ **§3.7 is the section with the least evidence in this file.** Its three-shape table grew from two
shapes because a critique drew the case the two-shape version mis-routed, and the apparatus tax, the
weight-not-extent rule and the side-by-side check each rest on very few measurements. ⇒ **Report what
the next extending figure costs**: the element count of the apparatus re-drawn, the ratio of the
addition to the whole picture, and whether the side-by-side actually caught anything.
