---
name: figure-templates
description: >-
  Build a generated question's figure from ONE of the eighteen stem-checked templates in
  `tools/vdd_templates.py` — grid polygon, shaded grid, rays-from-a-point, number line,
  pictograph, rectangle-with-points, house pentagon, cuboid, dot pattern, circle points,
  two-circle points, circles in a circle, abacus, sorting rings, shape row, coordinate
  plane, parallel lines, bar chart — instead of
  hand-drawing VDD. The builder takes the stem's own numbers (refusing any it cannot find
  there), computes the geometry from them, and emits the `channel: constructed` claim set
  itself, so the figure and the claim set can never drift apart (T-QG-2). Use at the
  "Figure" step of `generate`, or whenever a question's figure matches a catalogue entry.
  Hand-draw with `vdd_cookbook.py` only when no template fits.
---

# Figure templates — `tools/vdd_templates.py`

**Why this exists (T-QG-2).** On 2026-09-29 a cuboid was drawn 1.5:1 while the stem said
5:2 — and Audit A passed, because the claim set had recorded the *drawn* ratio and agreed
with itself. The audit can only catch a copied ratio when the claim set's numbers are
required to come from the STEM. A template enforces that by construction: the caller passes
stem values, `require_stem` checks each against the same regex the audit runs over `stem:`,
geometry is computed from those numbers, and the claim set is emitted by the same code.

## When a template, when hand-draw

- **Match the catalogue below** → use the template. It emits `<id>.json` (the VDD doc),
  `<id>.anchors.json` and `<id>-claims.txt` in one step — the claim set needs no editing.
- **The figure's SHAPE doesn't match any entry** (a triangle net, a clock face, a
  thermometer) → hand-draw with `vdd_cookbook.py` and author the claim set yourself per
  `read-figure-claim-set` §3. Never stretch a template past its contract to force a match.
  (Bar charts and coordinate planes used to be hand-draw examples — both are templates
  now, including the **read-the-figure mode**: `coords="figure"` / `values="figure"` marks
  the values `ev inferred` instead of stem-checking them, so a "read the graph" question
  is honest about the student reading them off.)
- **The stem doesn't state a number the template needs** → the builder raises
  `TemplateError` (`length=1.5 is not a number the stem states`). Fix the spec — pass the
  stem's value — or drop the figure. Do not retype the drawn number into a spec.

## Hand-drawing through `finish()`

When no template fits, still build through `vdd_templates.finish()` — never emit the three
files by hand. The run's `handdraw.py` builds the element list with `vdd_cookbook.py`
helpers and calls

```python
vt.finish(kind="<nearest kind>", figure_id="Q5", stem=stem, elements=el, anchors=anchors,
          points=[...], segments=[...], claims=claims, ask=ask,
          title=…, description=…, scale="…", medium="sinhala")
```

so the canvas fit, the label-clearance pre-flight and the claim-set emission are the
templates' own — `finish()` writes `<id>.json`, `<id>.anchors.json`, `<id>-claims.txt` in
one step and `run-gates build` audits the result exactly like a template figure (a missing
`<id>-claims.txt` fails the stage).

### `finish()` API card

```python
vt.finish(kind=…, figure_id=<staged id>, stem=…, elements, anchors, points, segments,
          claims, ask, title, description, scale, medium,
          budget=None, departures=None, ambiguous=None, contested=None)
```

- **Floating labels** — put `"_near": [x, y]` (the anchor it labels, element coords) and
  optional `"_gap"` (units from the anchor to the box's near edge, default 14) on a `text`
  element; its `at` is ignored and finish() places it: 16 directions × `_gap…_gap+36`,
  first candidate keeping — in rendered px — ≥8 to every stroke edge, ≥4 to every other
  label, its centre ≥6 nearer `_near` than every other floater's anchor or dot centre, and
  on the same side of every unfilled circle/closed polygon/rect as `_near` (OUTSIDE one
  `_near` sits ON, i.e. within 2 units of; `_region: false` keeps a decorative outline out
  of the rule — a small unfilled marker around an anchor must not trap its label). No
  candidate → `TemplateError` naming the rule that failed most. After the sweep the fit
  re-runs with every placed box and any floater now failing is re-searched (≤2 passes); a
  floater the final pre-flight still refuses errors `floating label 'D' was placed at …
  but fails <rule> at the final scale — raise _gap or widen the figure`. `_`-keys are
  stripped before the doc is written, and finish() never mutates your `elements`/`anchors`
  — a raise leaves them untouched.
- **Fixed labels** get the same own-anchor rule as a pre-flight check: for
  `label "g" names P` with P an anchor, the glyph's box centre must beat every *other*
  anchor a label claim names by ≥3 rendered px — else `label 'D' is nearer anchor G than
  its own D`. Fix by moving it, or hand it to the search with `_near`.
- **Region points**: `vt.region_point({"left": (c, r), "right": (c2, r2)}, inside=[…],
  outside=[…], prefer=(x, y), margin=15, avoid=[pts], min_sep=30, step=2)` → the point
  nearest `prefer` on the first expanding ring (outward at `step`) holding a valid point —
  ≥margin inside/outside the named circles and ≥min_sep from `avoid`;
  `vt.on_circle_point(c, r, deg)` → a point ON the outline (0° = E, y down);
  `vt.membership_claims("D", p, circles)` → the `describe "D lies inside the right circle
  and outside the left circle"` claim tuple to append to `claims`.
- **Claim forms** — `label "g" names <token>` (one distinct token per drawn glyph —
  `names ringA` on six numerals binds nothing), `circle centre X radius r` (measured
  against the drawn circle element) or `circle centre X through A B` (2–3 REAL
  on-outline anchors whose centre distances are compared — one verifies nothing),
  `describe "…"`, `reads P v on XY` (a marked/printed value read off an axis segment —
  point names are `[A-Z]\d*` so `T1`…`Tn` bar-top anchors work), `nonparallel AB CD`
  (the two segments stay ≥5° off parallel),
  `derive a op b = v`, `none …`, plus `shaded`/`grid`/`stage`/`paint`/`tick`/`right` as the
  templates use them.
- **Errors → fix**: `~N rendered px from stroke geometry` / `…from the canvas edge` /
  `labels X and Y are ~N rendered px apart` → move the label or give it `_near`;
  `is nearer anchor G than its own D` → it sits nearer another claimed anchor;
  `found no clear spot` → widen `_gap` or the geometry; `no `label` claim` → every drawn
  glyph needs one (math overlays are declared in `describe` prose instead).
- dots are filled `circle` elements + separate `text` labels (a filled circle is a dot to
  the same-region rule, not a region); a numeral floating inside a region far from any
  paint still fails visual-check's `target` rule — put it in a thin stroke-only `rect`
  "card" so the paint it belongs to is near; `budget:` + `departures:` is the honest
  escape when an element count legitimately tops 32.

```python
el = [vc.circle(cL, R, id="L"), vc.circle(cR, R, id="R")]
circles = {"left": (cL, R), "right": (cR, R)}
anchors = {}
claims = [("circle centre L radius 100", "inferred", "left ring"),
          ("circle centre R radius 100", "inferred", "right ring")]
for nm, ins, outs in (("P", ["left"], ["right"]), ("Q", ["right"], ["left"])):
    p = anchors[nm] = vt.region_point(circles, inside=ins, outside=outs, prefer=cL)
    el += [{"type": "circle", "id": "d" + nm, "center": list(p), "r": 4,
            "fill": {"color": "#000"}},
           {"type": "text", "id": "t" + nm, "at": [0, 0], "value": nm,
            "align": "middle", "baseline": "middle", "_near": list(p)}]
    claims += [(f'label "{nm}" names {nm}', "stem", "a dot"),
               *vt.membership_claims(nm, p, circles)]
b = vt.finish(kind="two_circles", figure_id="Q3", stem=stem, elements=el, anchors=anchors,
              points=list(anchors), segments=[], claims=claims, ask=ask, title=…,
              description=…, scale="…")
```

| template | you pass | stem-checked | the claim set emits | limits |
|---|---|---|---|---|
| `grid_polygon` | `cell`, `vertices` (grid units), `cols`/`rows`? (default = the shape's own extent), `cell_px`, `vertex_labels`, `axis={"through":[[x,y],[x,y]]}` | `cell` | `right` per vertex, `grid R by C over P Q`, shoelace + perimeter `derive`s, `paint`/`describe` for a drawn axis, `none` | axis-aligned edges only; vertex labels seat outside the polygon (a notch/reflex corner labels inside the notch — needs ~40+ px cells, 1-cell slots ~76+); `axis` must run vertical/horizontal/±45° and is mirror-symmetric-asserted unless `assert_symmetric: False` |
| `shaded_grid` | `cols`, `rows`, `full=[(c,r)]`, `half=[(c,r,corner)]` | `cols`+`rows` or their product | `grid`, `shaded n of m cells`, per-half `describe`, area `derive`, `none` | half cells: one corner triangle each |
| `rays_from_point` | `rays={A:"NE"}` or numeric bearing, `angles=[(from,to,label,reflex)]`, `north_arrow` | numeric bearings; angle sizes must derive from constants+stem | `angle` per marked angle (citing emitted `derive`s), `describe` for reflex, `label` for centre/tips/north, `none` | bearing names are compass points |
| `number_line` | `v0`, `v1`, `parts_per_unit`, `points={P: 0.4}` | `v0`, `v1`, `parts_per_unit` | `axis … from/to`, `tick … step k`, `at` per point, `label` per numeral+point, `derive 1/parts`, `none`, `budget` when >32 el | integer endpoints; points must sit on the lattice; a wide span labels every `k`-th integer (a divisor of the span, claimed as `tick … step k`) so numerals never crowd |
| `pictograph` | `per_symbol`, `rows=[(label,count)]` | `per_symbol` | `describe` per row's symbol count, `label` per row + `"= n" names key`, `derive n/2`, `none` | counts = whole or half symbols only |
| `rectangle_points` | `length`,`width` (both or neither), `on_points={E:["DC",t]}`, `extra_segments`, `masks`, `aspect` | `length`,`width` when given | `right` ×4, `on` per side point, `ratio len AB / len BC` when stem-backed, `derive` for the fraction, `label`s | no lengths ⇒ ambiguous entry + "NOT to scale" `scale:` |
| `house_pentagon` | `AB`,`BC`,`DA`,`CP`,`PD`, `unit`, `labels={CP:"x m"}` | a side whose label carries a **letter** (`"x m"`) — its numeric value must be a stem number; printed numeric labels are figure content and the geometry is computed from them (the drawing cannot disagree with its own labels — the audit's LABEL-RATIO check enforces it) | `right` ×2, `equal` pairs, stem-justified `ratio`s, side `label` claims (a letter side renders as plain `text` — VDD has no italic and a serif KaTeX label would clash), perimeter `derive` | slants must meet above the body |
| `cuboid` | `length`, `width`, `height`, `unit`, `depth_angle=35`, `depth_scale=0.5` | all three | `derive` + `ratio len DC / len DA` on the LABELLED front-face sides (label-ratio check owns it), `right` ×4, `parallel` classes, `paint` on dashed hidden edges, side `label`s | oblique projection; depth foreshortened — `scale:` says so and the width label on CG is declared in `ambiguous:`; depth_angle ∈ (0,90), depth_scale ∈ (0,1] |
| `dot_pattern` | `stages`, `kind=triangle\|square\|rectangle` | nothing — the counts are the kind's own formula | `stage n shows k dots`, `derive` closed form per stage, `label "(n)"` | 1–8 stages; if `stages` is not a stem number the claim declares that freedom in `ambiguous:` |
| `circle_points` | `points={P:{where:"in"\|"on"\|"out", label?, deg?}}`, `r`, `labelled=False` for unlabelled stones | nothing — counts are figure content | `circle centre Z through <on-dots>` when ≥2 real on-dots exist, else `radius r`, a membership `describe` per dot, `label` per glyph, `derive in+on+out=total` | point names are single capitals; on-dots pin `deg` or take the fixed angle pattern |
| `two_circles_points` | `points={P:{in:["L","R"], on:"L"\|"R"\|null, label?}}`, `r`, `overlap` | nothing — counts are figure content | `circle centre L/R through <on-dots>` or `radius r` per circle, membership `describe`s via `membership_claims` ("left"/"right" circle), `label`s, `derive` | overlap ∈ (0,1); a point can't be `on` a circle it's also `in`; `L`/`R` are reserved names |
| `circles_in_circle` | `n_in`, `n_out`, `R`, `r` | nothing — counts are figure content | `circle centre Z radius R`, `describe` per side, `derive n_in+n_out` | small circles stay ≥10 units clear of the big stroke and each other — overcrowd refuses |
| `abacus` | `place_values=[…]` left→right, `beads=[…]` parallel, `bead_r` | nothing — printed values are figure content | `label "<v>" names rod<i>`, `describe` per rod's bead count, `derive Σ beads·value` | a rod holds 0–9 beads — >9 refuses (the lesson's own rule); distinct place values |
| `sorting_rings` | `groups=[(name, [items])]`, `ring_gap` | nothing — item texts are figure content | `label` per ring + per item card (`names ring<i>`/`it<i>_<j>`), `describe` per ring, `derive` count sum | 2–3 rings (three lay out 2 + 1); default-size text, cards/rings grow to fit; distinct names and item glyphs |
| `shape_row` | `shapes=[(letter, kind)]`, `cell_w`, `row_h` | nothing — kinds are figure content | `circle centre` for round kinds, `describe` per shape (sides/corners/curved), `label` per letter, `derive` curved+straight | kinds: circle, small_circle, square, rectangle, triangle, oval, semicircle; 3 per row; letters are single capitals |
| `coordinate_plane` | `x_max`,`y_max` ≤10, `points={A:(x,y)}`, `join=[[…]]`, `closed`, `sym_axis={"x"\|"y":k}`, `guides=[…]`, `grid`, `origin_label`, `coords="stem"\|"figure"` | each point's x,y (and the `sym_axis` value) when `coords="stem"` | `axis`/`tick`/`right` on OX/OY, `reads P v on OX`/`OY` per coordinate (and the sym midline's two ends), `paint dashed` on the sym axis, `describe` for guides and the figure-mode declaration, `label` per point/axis letter/numeral; join edges are declared `segments` only | integer first-quadrant points; points can't sit on the axis anchors (O/X/Y); grid lines are real strokes — a crowded interior point's letter refuses. Measured (W12): with `grid` on, lettered pockets need ~44-unit cells — up to **6×6** (5×8, 4×9 also fit); **`x_max ≥ 7` refuses** — drop `grid` or the letters |
| `parallel_lines` | `lines=["AB",…]` 2–4, `parallel=[[class],…]` 1–2, `direction`, `crossing="PQ"`, `distance={"between","value","unit"}`, `length` | `distance.value` | `parallel`/`nonparallel` per pair + the transversal's, `label` per letter, distance: `on M/N`, `right M N D`, `label "v unit" names MN` | unclassed lines tilt ≥12° without crossing others; crossing must stay ≥5° off every line; distance needs the pair adjacent in `lines` |
| `bar_chart` | `categories` 2–8, `series=[{"name","values"}]` 1–3, `step`, `v_max`, `values="stem"\|"figure"`, `value_title`, `category_title`, `gridlines`, `orientation="v"\|"h"` | `step`; every value when `values="stem"` | `reads T<i> v on OY` per bar (0-value bars read the baseline), `axis OY … step`, `label`s for category/title/legend glyphs; with `orientation="h"` the same claims read `on OX` (bars run right, categories stack up the y axis, first category nearest the origin) | every value a multiple of step/2 and ≤ v_max; numerals never thin — crowded axis refuses; series/category/other-glyph names must be glyph-distinct; `"h"` refuses when the label gutter leaves <160 units for the value axis or the rows would exceed the 540-unit canvas height |

Every builder is keyword-only; every spec also takes `figure_id`, `stem`, `medium`
(`"english"`, `"sinhala"`), `ask` (`[["a","text"],…]`), `title`, `description`.
`finish` fits a canvas (the margin grows with the span so the tightest render keeps ≥9 px edge clearance),
refuses a canvas more than **2× as tall as wide** (`aspect` — a 1×10 shaded grid renders ~375×2253,
taller than a phone screen; re-lay it out, e.g. 5×2 — `vdd-check` and visual-check's `aspect` rule
fail it too),
runs the **label-clearance pre-flight** (every label ≥6 rendered px to stroke edges, ≥8 px
to the canvas edge — measured in RENDERED px on the narrowest plate, `PLATE_INNER` = 294 px =
320 − 2×12 pad − 2×1 border, thresholds scaling by `1/s` with `s = min(1, 294/canvas_width)`;
label boxes model the real DOM `getBBox` — a `dominantBaseline="middle"` text's box is ~1.22 em
biased UP, `MID_UP`/`MID_DOWN` in the file), then emits the claim set.

## Numbers and the stem

- `require_stem(stem, **kw)` — each value must appear as a number token in the stem text
  (same `\d+(\.\d+)?` regex `audit-claim-set.py` uses). A miss raises `TemplateError`.
- Numbers that live ON the figure — pictograph counts, printed side labels like `8 m`,
  marked point values — are figure content (the corpus convention), not stem claims. Only a
  value a label CANNOT restate (the `x m` side) or a bare dimension parameter is
  stem-checked.
- A `ratio`/`angle` claim must be stem-justified *in the claim set itself*: a stem-number
  pair, or a cited `derive` whose literals are stem numbers, the constants {1,2,90,180,360},
  or another backed derive. `rays_from_point` emits its own backing chain automatically.
- **An `ask` part must map to the load-bearing claims.** The claim set's `load-bearing:`
  section lists every ask part → the claims the answer hangs on. Templates emit that for
  you; when you pick `ask` parts in the spec, pick the parts the figure actually serves.
- **Every piece of DRAWN text is simple English on every medium** (ADR 0021 —
  supersedes T-S6b-6's medium condition): point letters, labels, text elements, math
  latex, axis/category/series/value titles, units. The builder and `vdd-check` rule 3
  refuse any Sinhala codepoint in drawn text regardless of `medium` — categories like
  "සඳුදා" ship as "Mon". The a11y `title`/`description` are NOT drawn: they keep the
  question's medium. The pre-flight refuses `$`/backtick in any label regardless of
  medium.
- **The spec's `description` (a11y) must not narrate what a part asks the student to read off
  the figure** — which or how many cells are shaded, a marked point's value. Say "some cells
  are shaded" instead (T125). A W8 critic caught a shaded-grid description that handed over
  the count.

## Workflow

```bash
python3 tools/vdd_templates.py list                    # the catalogue
python3 tools/vdd_templates.py build spec.json --out out/
```

`spec.json` is an object or a list of objects, each `{"template": "<kind>", "figure_id":
"q8", "stem": "<stem text>", "ask": [["a", "…"]], …params}`. Output per figure:
`out/q8.json`, `out/q8.anchors.json`, `out/q8-claims.txt`. ⚠️ Inside a `generate` run, set `figure_id` to the
figure's **staged id** (`Q8`, `Q8.b`) — visual-check resolves a staged doc's claim sets as
`<claims-dir>/<staged id>-claims.txt`, so any other name leaves the figure claims-less. Then the gates, in order:

```bash
python3 tools/audit-claim-set.py out/q8-claims.txt                 # claim audit (exit 0)
node tools/vdd-check.mjs out/q8.json --claims out/q8-claims.txt \
     --medium sinhala --out render-q8 --json                       # real render (exit 0, 0 findings);
                                                                   # --medium = the question's medium
```

Then **look at one render PNG per figure once** (`render-q8/render-375.png`): the render is
the truth — a label on a stroke or outside its angle is only visible by sight. If the render
fails a label clearance, fix the template input or the builder — never hand-edit the emitted
files (the claim set and the drawing would drift again).

Then run the batch render — `node tools/visual-check.mjs out/` —
[`visual-check`](../visual-check/SKILL.md) puts every figure through the real `/diagtest` page
(the real `--font-sans` stack + KaTeX overlays + dark theme that vdd-check's bare harness lacks)
and measures labels against its five rules; it is the live check before the figure joins a
staged doc.

`python3 tools/vdd_templates.py --self-test` builds all eighteen from synthetic stems and runs
the audit on each — it's wired into `check-suite.py` Part B.
