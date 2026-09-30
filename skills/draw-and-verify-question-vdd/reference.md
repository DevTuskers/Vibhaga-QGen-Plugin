# draw-and-verify-question-vdd — reference material

Verbatim long-form material split out of `SKILL.md` on 2026-09-30 — the single 57.5 KB file did
not load in the Devin CLI (`devin plugins info` listed 7 of 8 skills; suspected ~50 KB per-skill
cap — `docs/TRAPS.md` T-QG-1). **Read `SKILL.md` first;** a pointer line there names the section
here. Section numbers match the skill, and `§N` references below refer back to it.

---

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


---

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


---

## 6. Traps — stories with the catch

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
