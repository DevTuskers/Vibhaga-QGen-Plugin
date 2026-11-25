# Hand-drawn figure API

[Template selection and workflow](SKILL.md).

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
