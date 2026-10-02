---
name: figure-templates
description: >-
  Build a generated question's figure from ONE of the nine stem-checked templates in
  `tools/vdd_templates.py` — grid polygon, shaded grid, rays-from-a-point, number line,
  pictograph, rectangle-with-points, house pentagon, cuboid, dot pattern — instead of
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
- **The figure's SHAPE doesn't match any entry** (a triangle net, a bar chart, a clock face)
  → hand-draw with `vdd_cookbook.py` and author the claim set yourself per
  `read-figure-claim-set` §3. Never stretch a template past its contract to force a match.
- **The stem doesn't state a number the template needs** → the builder raises
  `TemplateError` (`length=1.5 is not a number the stem states`). Fix the spec — pass the
  stem's value — or drop the figure. Do not retype the drawn number into a spec.

## Catalogue

| template | you pass | stem-checked | the claim set emits | limits |
|---|---|---|---|---|
| `grid_polygon` | `cell`, `vertices` (grid units), `cols`/`rows`?, `cell_px`, `vertex_labels` | `cell` | `right` per vertex, `grid R by C over P Q`, shoelace + perimeter `derive`s, `none` | axis-aligned edges only |
| `shaded_grid` | `cols`, `rows`, `full=[(c,r)]`, `half=[(c,r,corner)]` | `cols`+`rows` or their product | `grid`, `shaded n of m cells`, per-half `describe`, area `derive`, `none` | half cells: one corner triangle each |
| `rays_from_point` | `rays={A:"NE"}` or numeric bearing, `angles=[(from,to,label,reflex)]`, `north_arrow` | numeric bearings; angle sizes must derive from constants+stem | `angle` per marked angle (citing emitted `derive`s), `describe` for reflex, `label` for centre/tips/north, `none` | bearing names are compass points |
| `number_line` | `v0`, `v1`, `parts_per_unit`, `points={P: 0.4}` | `v0`, `v1`, `parts_per_unit` | `axis … from/to`, `tick … step k`, `at` per point, `label` per numeral+point, `derive 1/parts`, `none`, `budget` when >32 el | integer endpoints; points must sit on the lattice; a wide span labels every `k`-th integer (a divisor of the span, claimed as `tick … step k`) so numerals never crowd |
| `pictograph` | `per_symbol`, `rows=[(label,count)]` | `per_symbol` | `describe` per row's symbol count, `label` per row + `"= n" names key`, `derive n/2`, `none` | counts = whole or half symbols only |
| `rectangle_points` | `length`,`width` (both or neither), `on_points={E:["DC",t]}`, `extra_segments`, `masks`, `aspect` | `length`,`width` when given | `right` ×4, `on` per side point, `ratio len AB / len BC` when stem-backed, `derive` for the fraction, `label`s | no lengths ⇒ ambiguous entry + "NOT to scale" `scale:` |
| `house_pentagon` | `AB`,`BC`,`DA`,`CP`,`PD`, `unit`, `labels={CP:"x m"}` | a side whose label carries a **letter** (`"x m"`) — its numeric value must be a stem number; printed numeric labels are figure content and the geometry is computed from them (the drawing cannot disagree with its own labels — the audit's LABEL-RATIO check enforces it) | `right` ×2, `equal` pairs, stem-justified `ratio`s, side `label` claims (a letter side renders as plain `text` — VDD has no italic and a serif KaTeX label would clash), perimeter `derive` | slants must meet above the body |
| `cuboid` | `length`, `width`, `height`, `unit`, `depth_angle=35`, `depth_scale=0.5` | all three | `derive` + `ratio len DC / len DA` on the LABELLED front-face sides (label-ratio check owns it), `right` ×4, `parallel` classes, `paint` on dashed hidden edges, side `label`s | oblique projection; depth foreshortened — `scale:` says so and the width label on CG is declared in `ambiguous:`; depth_angle ∈ (0,90), depth_scale ∈ (0,1] |
| `dot_pattern` | `stages`, `kind=triangle\|square\|rectangle` | nothing — the counts are the kind's own formula | `stage n shows k dots`, `derive` closed form per stage, `label "(n)"` | 1–8 stages; if `stages` is not a stem number the claim declares that freedom in `ambiguous:` |

Every builder is keyword-only; every spec also takes `figure_id`, `stem`, `medium`
(`"english"`, `"sinhala"`), `ask` (`[["a","text"],…]`), `title`, `description`.
`finish` fits a canvas (the margin grows with the span so the tightest render keeps ≥9 px edge clearance),
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
- **Sinhala in labels is allowed only on a `sinhala`-medium question** — the figure lives
  inside the question's medium (T-S6b-6). Pass `medium="sinhala"` to the builder and
  `--medium sinhala` to `vdd-check` (its rule 3 is medium-conditional — L239). Sinhala in a
  `math.latex` label is **always** refused: KaTeX cannot shape it. The pre-flight refuses
  `$`/backtick in any label regardless of medium.
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

`python3 tools/vdd_templates.py --self-test` builds all nine from synthetic stems and runs
the audit on each — it's wired into `check-suite.py` Part B.
