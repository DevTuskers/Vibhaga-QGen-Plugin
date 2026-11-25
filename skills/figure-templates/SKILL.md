---
name: figure-templates
description: >-
  Build a generated question's figure with a VDD template at generate's Figure step.
  Use the template catalogue when the shape fits; otherwise hand-draw through finish().
---

# Figure templates — `tools/vdd_templates.py`

**Why this exists (T-QG-2).** On 2026-09-29 a cuboid was drawn 1.5:1 while the stem said
5:2 — and Audit A passed, because the claim set had recorded the *drawn* ratio and agreed
with itself. The audit can only catch a copied ratio when the claim set's numbers are
required to come from the STEM. A template enforces that by construction: the caller passes
stem values, `require_stem` checks each against the same regex the audit runs over `stem:`,
geometry is computed from those numbers, and the claim set is emitted by the same code.

## When a template, when hand-draw

- **Match the [catalogue](catalogue.md)** → use the template. It emits `<id>.json` (the VDD doc),
  `<id>.anchors.json` and `<id>-claims.txt` in one step — the claim set needs no editing.
- **The figure's SHAPE doesn't match any entry** (a pentagonal-prism net, an
  oblique solid, a thermometer) → hand-draw with `vdd_cookbook.py` and author the claim set yourself per
  `read-figure-claim-set` §3. Never stretch a template past its contract to force a match.
  (Bar charts and coordinate planes used to be hand-draw examples — both are templates
  now, including the **read-the-figure mode**: `coords="figure"` / `values="figure"` marks
  the values `ev inferred` instead of stem-checking them, so a "read the graph" question
  is honest about the student reading them off.)
- **The stem doesn't state a number the template needs** → the builder raises
  `TemplateError` (`length=1.5 is not a number the stem states`). Fix the spec — pass the
  stem's value — or drop the figure. Do not retype the drawn number into a spec.

## Hand-drawing through `finish()`

For parameters, label placement and errors, see the [API card](finish-api.md#finish-api-card).

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

<a name="finish-api-card"></a>
<a name="readiness-continuation-log"></a>

[Catalogue](catalogue.md) · [`finish()` API card](finish-api.md#finish-api-card) · [Readiness log](readiness-log.md#readiness-continuation-log)

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

`python3 tools/vdd_templates.py --self-test` builds all seventy-one from synthetic stems and runs
the audit on each — it's wired into `check-suite.py` Part B.


<a name="solved-scenes-and-two-circle-geometry"></a>

See the catalogue for [solved scenes and two-circle geometry](catalogue.md#solved-scenes-and-two-circle-geometry).
