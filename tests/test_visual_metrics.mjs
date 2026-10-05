import test from "node:test";
import assert from "node:assert/strict";
import { assess, parseClaimSet, arcDelta, angleMarkSpan, angleInSpan, paintVisible } from "../tools/visual-metrics.mjs";

// Synthetic measured labels only — every fixture below is invented; nothing mirrors a real figure.
const L = (over = {}) => ({
  i: 0, text: "x", kind: "text", bbox: [100, 100, 20, 14],
  fontFamily: "Inter, sans-serif", fontSizeU: 18,
  edge_u: 20, stroke_u: 20, geom_u: 5, ...over,
});
const W = (labels, pxPerUnit = 1, width = 375) => [{ width, pxPerUnit, labels }];
const doc = (elements) => ({
  schema: "vibhaga.diagram", schemaVersion: 1,
  canvas: { width: 300, height: 260 }, defaults: { strokeWidth: 2, fontSize: 18 }, elements,
});
const fails = (r) => r.findings.filter((f) => f.severity === "fail");
const rules = (r) => new Set(fails(r).map((f) => f.rule));

test("claim-set parser: anchors, claims, allow, labels (vdd-check grammar)", () => {
  const cs = parseClaimSet(`# comment
labels: "9 : 4" ratio
points: A B
anchors:
  A 0 0
  C 120 80
claims:
  K1 grid 2 by 3 over A C | stem | six squares
  K2 shaded 4 of 6 cells | inferred |
  K3 describe "cell (1,0) is half shaded, the tr corner triangle" | inferred |
allow: label:"9 : 4"
`);
  assert.equal(cs.anchors.A.join(), "0,0");
  assert.equal(cs.anchors.C.join(), "120,80");
  assert.equal(cs.claims.length, 3);
  assert.equal(cs.claims[0].pred, "grid");
  assert.equal(cs.claims[0].args, "2 by 3 over A C");
  assert.ok(cs.allow.includes('label:9 : 4'));
  assert.equal(cs.labels.join(" "), "9 : 4 ratio");
});

test("edge: label 4px from the canvas edge fails, 12px passes", () => {
  const bad = assess({ doc: doc([]), widths: W([L({ edge_u: 4 })]) });
  assert.equal(bad.verdict, "FAIL");
  assert.ok(rules(bad).has("edge"));
  const good = assess({ doc: doc([]), widths: W([L({ edge_u: 12 })]) });
  assert.equal(good.verdict, "PASS");
});

test("edge: unmeasurable bbox fails closed", () => {
  const r = assess({ doc: doc([]), widths: W([L({ edge_u: null })]) });
  assert.equal(r.verdict, "FAIL");
  assert.ok(rules(r).has("edge"));
});

test("edge scales with pxPerUnit: 7u is fine at 375 but fails at 320", () => {
  // 7u × (296/300) ≈ 6.9px < 8 at 320; 7u × (351/300) ≈ 8.2px ≥ 8 at 375.
  const r = assess({ doc: doc([]), widths: W([L({ edge_u: 7 })], 351 / 300, 375) });
  assert.equal(r.verdict, "PASS");
  const r2 = assess({ doc: doc([]), widths: W([L({ edge_u: 7 })], 296 / 300, 320) });
  assert.equal(r2.verdict, "FAIL");
});

test("stroke: a label painted on a stroke fails; 10u clear passes", () => {
  const bad = assess({ doc: doc([]), widths: W([L({ stroke_u: 0.5 })]) });
  assert.ok(rules(bad).has("stroke"));
  const good = assess({ doc: doc([]), widths: W([L({ stroke_u: 10 })]) });
  assert.equal(good.verdict, "PASS");
});

test("target: label 30u from everything (fontSize 18) fails; 10u passes", () => {
  const bad = assess({ doc: doc([]), widths: W([L({ geom_u: 30 })]) });
  assert.ok(rules(bad).has("target"));
  const good = assess({ doc: doc([]), widths: W([L({ geom_u: 10 })]) });
  assert.equal(good.verdict, "PASS");
});

test("target: a word label (≥3-letter run, any script) is a header/legend — skipped", () => {
  // 60u from everything must NOT fail: Sinhala word, English word, mixed — but "8 m" (the only
  // letters are the 2-letter unit) still must.
  for (const text of ["සඳුදා", "Monday", "අඟහරුවාදා"]) {
    const r = assess({ doc: doc([]), widths: W([L({ text, geom_u: 60 })]) });
    assert.equal(r.verdict, "PASS", text);
    assert.equal(r.labels[0].target_u, null, text); // not evaluated
  }
  const unit = assess({ doc: doc([]), widths: W([L({ text: "8 m", geom_u: 30 })]) });
  assert.ok(rules(unit).has("target"));
});

test("target: an AREA label (its claim names region_…) is skipped — edge/stroke still measured", () => {
  const cs = parseClaimSet('claims:\n  K1 label "7" names region_a | inferred |\n');
  const far = assess({ doc: doc([]), widths: W([L({ text: "7", geom_u: 40 })]), claims: cs });
  assert.equal(far.verdict, "PASS");
  assert.equal(far.labels[0].target_u, null);
  const onStroke = assess({ doc: doc([]), widths: W([L({ text: "7", geom_u: 40, stroke_u: 0.5 })]), claims: cs });
  assert.ok(rules(onStroke).has("stroke"));
  // the same glyph bound to an ordinary target is still measured
  const cs2 = parseClaimSet('claims:\n  K1 label "7" names AB | inferred |\n');
  assert.ok(rules(assess({ doc: doc([]), widths: W([L({ text: "7", geom_u: 40 })]), claims: cs2 })).has("target"));
});

test("target: a far point label fails even when it is short", () => {
  const d = doc([{ id: "pA", type: "point", at: [50, 50], r: 3, label: "A" }]);
  const r = assess({ doc: d, widths: W([L({ text: "A", bbox: [220, 220, 12, 12], geom_u: 5 })]) });
  assert.equal(r.verdict, "FAIL");
  assert.ok(rules(r).has("target"));
});

test("target: a point label named like a word is STILL checked against its point", () => {
  const d = doc([{ id: "pZ", type: "point", at: [50, 50], r: 3, label: "Zed" }]);
  const r = assess({ doc: d, widths: W([L({ text: "Zed", bbox: [220, 220, 24, 12] })]) });
  assert.ok(rules(r).has("target"));
});

test("target: a point label measured against ITS point, not the nearest paint", () => {
  const d = doc([{ id: "pA", type: "point", at: [50, 50], r: 3, label: "A" }]);
  const far = assess({ doc: d, widths: W([L({ text: "A", bbox: [200, 200, 20, 14], geom_u: 5 })]) });
  assert.ok(rules(far).has("target"));
  const near = assess({ doc: d, widths: W([L({ text: "A", bbox: [58, 44, 12, 12], geom_u: 40 })]) });
  assert.equal(near.verdict, "PASS"); // geom_u=40 is ignored — the point target governs
});

test("target: ONE result per label — the least-quantised width governs rows and the finding", () => {
  // A canvas-unit distance is width-invariant, but the DOM box is re-measured per width and px
  // rounding wobbles it: a number-line point label read 26.8u at 320 (inside the 27u bound) and
  // 27.1u at 768 (outside) — rows and finding disagreed. The largest pxPerUnit is the least
  // quantised measurement, so it governs every row AND the finding.
  const d = doc([{ id: "pA", type: "point", at: [50, 50], r: 3, label: "A" }]);
  const at = (distU) => [45, 50 - distU - 10, 10, 10];   // point's x inside the box: pure dy
  const bad = assess({
    doc: d,
    widths: [
      { width: 320, pxPerUnit: 0.66, labels: [L({ text: "A", bbox: at(26.8) })] },
      { width: 375, pxPerUnit: 0.78, labels: [L({ text: "A", bbox: at(27.5) })] },
      { width: 768, pxPerUnit: 1.7, labels: [L({ text: "A", bbox: at(27.1) })] },
    ],
  });
  assert.equal(bad.verdict, "FAIL");
  assert.ok(rules(bad).has("target"));
  assert.ok(bad.labels.every((row) => row.target_u === 27.1 && row.ok === false));
  // …and agreement in the other direction: governed under the bound, every row ok.
  const good = assess({
    doc: d,
    widths: [
      { width: 320, pxPerUnit: 0.66, labels: [L({ text: "A", bbox: at(26.8) })] },
      { width: 768, pxPerUnit: 1.7, labels: [L({ text: "A", bbox: at(25.9) })] },
    ],
  });
  assert.equal(good.verdict, "PASS");
  assert.ok(good.labels.every((row) => row.target_u === 25.9 && row.ok === true));
});

test("aspect: a figure over 2× as tall as wide fails — a phone screen can't hold it", () => {
  const tall = doc([]);
  tall.canvas = { width: 66, height: 426 }; // the W8 1×10 shaded grid — rendered 375×2253
  const bad = assess({ doc: tall, widths: W([]) });
  assert.equal(bad.verdict, "FAIL");
  assert.ok(rules(bad).has("aspect"));
  assert.equal(bad.aspect.ratio, 6.45);
  const wide = doc([]);
  wide.canvas = { width: 426, height: 213 };
  const good = assess({ doc: wide, widths: W([]) });
  assert.equal(good.aspect.ratio, 0.5);
  assert.ok(!rules(good).has("aspect"));
});

test("aspect: the measured 375 viewBox governs when present, not doc.canvas", () => {
  const d = doc([]); // canvas 300×260 — under 2.0 by itself
  const tall = assess({ doc: d, widths: [{ width: 375, pxPerUnit: 1, viewBox: [0, 0, 100, 250], labels: [] }] });
  assert.equal(tall.aspect.ratio, 2.5);
  assert.ok(rules(tall).has("aspect"));
});

test("arc (explicit sweep): numeral inside the drawn span passes, opposite side fails", () => {
  const d = doc([
    { id: "arcB", type: "arc", center: [100, 100], r: 40, start: 0, end: 90, sweep: "cw" },
  ]);
  // Label centre at polar 45° from the centre, distance 50 (within r + 1.5·18 = 67).
  const cx = 100 + 50 * Math.SQRT1_2, cy = 100 + 50 * Math.SQRT1_2;
  const inside = assess({ doc: d, widths: W([L({ text: "60°", bbox: [cx - 5, cy - 5, 10, 10] })]) });
  assert.equal(inside.verdict, "PASS");
  assert.ok(inside.arcs && inside.arcs.checked === 1);
  // Opposite side of the vertex: polar 225° — inside the proximity window but outside [0°,90°].
  const ox = 100 - 50 * Math.SQRT1_2, oy = 100 - 50 * Math.SQRT1_2;
  const outside = assess({ doc: d, widths: W([L({ text: "60°", bbox: [ox - 5, oy - 5, 10, 10] })]) });
  assert.equal(outside.verdict, "FAIL");
  assert.ok(rules(outside).has("arc"));
  assert.match(fails(outside).find((f) => f.rule === "arc").message, /arcB/);
});

test("arc (unlabelled angleMark): same both ways", () => {
  const d = doc([
    { id: "mB", type: "angleMark", vertex: [100, 100], from: [150, 100], to: [100, 150], r: 24, arcs: 1 },
  ]);
  const inside = assess({ doc: d, widths: W([L({ text: "x", bbox: [110, 110, 8, 8], fontSizeU: 14 })]) });
  assert.equal(inside.verdict, "PASS"); // polar 45° inside [0°,90°]
  const outside = assess({ doc: d, widths: W([L({ text: "x", bbox: [96, 76, 8, 8], fontSizeU: 14 })]) });
  assert.equal(outside.verdict, "FAIL"); // polar −90°: above the vertex, outside the mark
  assert.ok(rules(outside).has("arc"));
});

test("arc: a capital label is a point name, not an angle numeral — never evaluated", () => {
  const d = doc([
    { id: "arcB", type: "arc", center: [100, 100], r: 40, start: 0, end: 90, sweep: "cw" },
    { id: "pA", type: "point", at: [60, 60], r: 3, label: "A" },
  ]);
  const r = assess({ doc: d, widths: W([L({ text: "A", bbox: [60, 60, 10, 10], geom_u: 10 })]) });
  assert.equal(r.arcs, null);
  assert.equal(r.verdict, "PASS");
});

test("arc: a numeral produced by a LABELLED angleMark is skipped (the renderer placed it)", () => {
  const d = doc([
    { id: "mB", type: "angleMark", vertex: [100, 100], from: [150, 100], to: [100, 150], r: 24, label: "45°" },
    { id: "arcB", type: "arc", center: [100, 100], r: 40, start: 0, end: 90, sweep: "cw" },
  ]);
  // Centre on the reflex side (polar 225°) — would fail against arcB if it were evaluated.
  const r = assess({ doc: d, widths: W([L({ text: "45°", bbox: [60, 60, 12, 8] })]) });
  assert.equal(r.verdict, "PASS");
  assert.equal(r.arcs, null);
});

// The Q3 geometry: three rays from one vertex, two small interior arcs, and one large REFLEX arc.
// With the old "inside any nearby span" check the reflex arc covers every direction near the
// vertex, so a numeral could never fail — the owner-arc + shared-arc clauses make it non-vacuous.
const O = [148, 104];
const q3arcs = () =>
  doc([
    { id: "arc1", type: "arc", center: O, r: 34, start: -45, end: 90 },
    { id: "arc2", type: "arc", center: O, r: 60, start: 90, end: 180 },
    { id: "arc3", type: "arc", center: O, r: 86, start: -45, end: 90, sweep: "ccw" },
  ]);
const numeralAt = (txt, r, deg) => {
  const t = (deg * Math.PI) / 180;
  const x = O[0] + r * Math.cos(t), y = O[1] + r * Math.sin(t);
  return L({ text: txt, bbox: [x - 5, y - 5, 10, 10] });
};

test("arc (Q3 shape): each numeral inside its own wedge's arc passes", () => {
  const r = assess({
    doc: q3arcs(),
    widths: W([numeralAt("1", 20, 22.5), numeralAt("2", 45, 135), numeralAt("3", 70, 202.5)]),
  });
  assert.equal(r.verdict, "PASS");
  assert.equal(r.arcs.checked, 3);
});

test("arc: numeral reflected through the vertex shares the reflex arc's owner — fails", () => {
  const r = assess({
    doc: q3arcs(),
    // "1" reflected through O lands in arc3's wedge, on top of numeral "3"'s territory.
    widths: W([numeralAt("1", 20, 202.5), numeralAt("2", 45, 135), numeralAt("3", 70, 202.5)]),
  });
  assert.equal(r.verdict, "FAIL");
  assert.match(fails(r).find((f) => f.rule === "arc").message, /arc3 carries 2 numerals/);
});

test("arc: numeral rotated 60° past its arc's end lands on the next arc's wedge — fails", () => {
  const r = assess({
    doc: q3arcs(),
    // arc1 ends at 90°; "1" rotated to 150° is inside arc2's wedge (arc2 = its owner) alongside "2".
    widths: W([numeralAt("1", 20, 150), numeralAt("2", 45, 135), numeralAt("3", 70, 202.5)]),
  });
  assert.equal(r.verdict, "FAIL");
  assert.match(fails(r).find((f) => f.rule === "arc").message, /arc2 carries 2 numerals/);
});

test("arc: a numeral in a direction no near arc covers fails the outside-span clause", () => {
  // Drop the reflex arc — now (180°,315°) is uncovered and a numeral there has no owner span.
  const d = doc([
    { id: "arc1", type: "arc", center: O, r: 34, start: -45, end: 90 },
    { id: "arc2", type: "arc", center: O, r: 60, start: 90, end: 180 },
  ]);
  const r = assess({ doc: d, widths: W([numeralAt("1", 20, 240), numeralAt("2", 45, 135)]) });
  assert.equal(r.verdict, "FAIL");
  const f = fails(r).find((x) => x.rule === "arc");
  assert.match(f.message, /outside its own arc arc1/); // arc1's 90° endpoint is the nearest drawn curve
});

test("arc: two numerals inside one arc's wedge fail as shared", () => {
  const d = doc([{ id: "arcB", type: "arc", center: [100, 100], r: 40, start: 0, end: 90, sweep: "cw" }]);
  const at2 = (deg) => {
    const t = (deg * Math.PI) / 180;
    return [100 + 30 * Math.cos(t) - 5, 100 + 30 * Math.sin(t) - 5, 10, 10];
  };
  const r = assess({ doc: d, widths: W([L({ text: "1", bbox: at2(30) }), L({ text: "2", bbox: at2(60) })]) });
  assert.equal(r.verdict, "FAIL");
  assert.match(fails(r).find((f) => f.rule === "arc").message, /arcB carries 2 numerals \("1","2"\)/);
});

test("arc helper semantics mirror DiagramRenderer (sweepArcPath / arcPath + reflex)", () => {
  assert.equal(arcDelta(0, 90, "cw"), 90);
  assert.equal(arcDelta(90, 0, "cw"), 270);      // cw forces the increasing-angle way round
  assert.equal(arcDelta(0, 90, "ccw"), -270);
  assert.equal(arcDelta(0, 90, undefined), 90);  // no sweep: the written delta stands
  assert.equal(arcDelta(0, 720, undefined), 360); // clamped
  const m = angleMarkSpan({ vertex: [0, 0], from: [10, 0], to: [0, 10], reflex: true });
  assert.equal(Math.round(m.start), 0);
  assert.equal(Math.round(m.delta), -270);       // 90° minor → 270° reflex the other way
  assert.ok(angleInSpan(45, 0, 90));
  assert.ok(!angleInSpan(225, 0, 90));
  assert.ok(angleInSpan(91.5, 0, 90));           // ±2° tolerance
  assert.ok(!angleInSpan(93, 0, 90));
});

// shaded_grid convention (tools/vdd_templates.py build_shaded_grid): `shaded N of M cells` counts
// FULL cells; each `describe "…half shaded…"` claim adds 0.5. 4 full + 4 halves → claimed 6.
const shadedClaims = `anchors:
  A 0 0
  C 120 80
claims:
  K1 grid 2 by 3 over A C | stem | six squares of 40 units
  K2 shaded 4 of 6 cells | inferred |
  K3 describe "cell (1,0) is half shaded" | inferred |
  K4 describe "cell (2,0) is half shaded" | inferred |
  K5 describe "cell (0,1) is half shaded" | inferred |
  K6 describe "cell (1,1) is half shaded" | inferred |
`;
const fullRects = [
  { id: "f1", type: "rect", x: 0, y: 0, width: 40, height: 40, fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
  { id: "f2", type: "rect", x: 80, y: 0, width: 40, height: 40, fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
  { id: "f3", type: "rect", x: 40, y: 40, width: 40, height: 40, fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
  { id: "f4", type: "rect", x: 80, y: 40, width: 40, height: 40, fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
];
const halfTriangles = [
  { id: "h1", type: "polygon", points: [[40, 0], [80, 0], [40, 40]], fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
  { id: "h2", type: "polygon", points: [[80, 0], [120, 0], [120, 40]], fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
  { id: "h3", type: "polygon", points: [[0, 40], [0, 80], [40, 80]], fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
  { id: "h4", type: "polygon", points: [[40, 40], [80, 40], [40, 80]], fill: { color: "#e5e7eb" }, stroke: { width: 0 } },
];
const halfAsSquares = halfTriangles.map((t, i) => ({
  id: t.id, type: "rect", x: [40, 80, 0, 40][i], y: [0, 0, 40, 40][i], width: 40, height: 40,
  fill: { color: "#e5e7eb" }, stroke: { width: 0 },
}));

test("shaded: halves drawn as triangles measure 6 cells → PASS; as whole squares measure 8 → FAIL", () => {
  const good = assess({ doc: doc([...fullRects, ...halfTriangles]), claims: shadedClaims, widths: [] });
  assert.equal(good.verdict, "PASS");
  assert.equal(good.shaded.claimed, 6);
  assert.equal(good.shaded.measured, 6);
  const bad = assess({ doc: doc([...fullRects, ...halfAsSquares]), claims: shadedClaims, widths: [] });
  assert.equal(bad.verdict, "FAIL");
  assert.ok(rules(bad).has("shaded"));
  assert.equal(bad.shaded.measured, 8);
});

test("shaded: no grid claim → shaded:null, not a finding; invisible fills do not count", () => {
  const noGrid = assess({ doc: doc(fullRects), claims: "claims:\n  K1 none angleMark | inferred |\n", widths: [] });
  assert.equal(noGrid.shaded, null);
  assert.equal(noGrid.verdict, "PASS");
  const ghost = { id: "g", type: "rect", x: 0, y: 0, width: 40, height: 40, fill: { color: "#e5e7eb", opacity: 0 }, stroke: { width: 0 } };
  const r = assess({ doc: doc([...fullRects, ...halfTriangles, ghost]), claims: shadedClaims, widths: [] });
  assert.equal(r.shaded.measured, 6); // alpha-0 fill ignored
  assert.equal(r.verdict, "PASS");
});

test("font: KaTeX math + <text> labels is a mix; text-only passes; two text faces fail", () => {
  const mix = assess({ doc: doc([]), widths: W([L({ kind: "math", text: "x²" }), L({ i: 1 })]) });
  assert.equal(mix.verdict, "FAIL");
  assert.ok(rules(mix).has("font"));
  assert.match(fails(mix).find((f) => f.rule === "font").message, /KaTeX math ×1 \+ text ×1/);
  const plain = assess({ doc: doc([]), widths: W([L(), L({ i: 1, text: "y" })]) });
  assert.equal(plain.verdict, "PASS");
  const twoFaces = assess({ doc: doc([]), widths: W([L(), L({ i: 1, text: "serifed", fontFamily: "Georgia, serif" })]) });
  assert.ok(rules(twoFaces).has("font"));
});

test("allow: label:\"x\" downgrades edge and stroke findings exactly like vdd-check", () => {
  const t = 'allow: label:"x"\n';
  const r = assess({ doc: doc([]), claims: t, widths: W([L({ edge_u: 4, stroke_u: 0.5 })]) });
  assert.equal(r.verdict, "PASS");
  assert.ok(r.findings.every((f) => f.severity === "allowed"));
  const other = assess({ doc: doc([]), claims: t, widths: W([L({ text: "y", edge_u: 4 })]) });
  assert.equal(other.verdict, "FAIL"); // only "x" is excused
});

test("paintVisible: none/transparent/alpha-0 are not paint", () => {
  for (const v of ["none", "transparent", "#0000", "#11223300", "rgba(1,2,3,0)", "rgb(1 2 3 / 0)", "hsla(9,10%,10%,0%)"])
    assert.equal(paintVisible(v), false, v);
  for (const v of ["#e5e7eb", "rgba(1,2,3,.4)", "rgb(1 2 3 / 50%)", "color-mix(in srgb, red, blue)"])
    assert.equal(paintVisible(v), true, v);
});

// ── round-4 review additions ────────────────────────────────────────────────────────────────────

test("arc: a LABELLED angleMark is still an owner candidate — a second numeral on its wedge fails", () => {
  // The renderer draws the mark's curve and places its own "45°" label — that label is skipped
  // as a subject, but the curve still owns numerals. A free numeral on its wedge must attribute
  // to it; two free numerals there → "carries 2 numerals".
  const d = doc([
    { id: "mL", type: "angleMark", vertex: [100, 100], from: [150, 100], to: [100, 150], r: 24, label: "45°" },
  ]);
  const at = (deg, r) => {
    const t = (deg * Math.PI) / 180;
    return [100 + r * Math.cos(t) - 4, 100 + r * Math.sin(t) - 4, 8, 8];
  };
  const one = assess({ doc: d, widths: W([L({ text: "1", bbox: at(30, 40), fontSizeU: 14 })]) });
  assert.equal(one.verdict, "PASS");
  assert.deepEqual(one.arcs.owners, { mL: ["1"] });
  const two = assess({
    doc: d,
    widths: W([L({ text: "1", bbox: at(30, 40), fontSizeU: 14 }), L({ text: "2", i: 1, bbox: at(60, 44), fontSizeU: 14 })]),
  });
  assert.equal(two.verdict, "FAIL");
  assert.match(fails(two).find((f) => f.rule === "arc").message, /mL carries 2 numerals \("1","2"\)/);
});

test("arc (multi-arc mark): radii mirror the renderer's clamped spacing", () => {
  // DiagramRenderer ~513: spacing = arcs>1 ? min(6, max(0, (r-2)/(arcs-1))) : 0 — a flat −6·i
  // goes negative at small r (an invalid SVG radius silently drops the arc).
  assert.deepEqual(angleMarkSpan({ vertex: [0, 0], from: [10, 0], to: [0, 10], r: 12, arcs: 3 }).radii, [12, 7, 2]);
  assert.deepEqual(angleMarkSpan({ vertex: [0, 0], from: [10, 0], to: [0, 10], r: 24, arcs: 1 }).radii, [24]);
});

test("shaded: a closed path off the origin contributes its FULL area (path ring closes)", () => {
  // M 10 10 → L 30 10 → L 30 30 → L 10 30 → Z is a 20×20 square = 1 cell of the 20×20 grid
  // below. An un-closed shoelace drops the last→first edge and measures 1.25 cells, not 1.
  const d = doc([
    { id: "sq", type: "path", d: "M 10 10 L 30 10 L 30 30 L 10 30 Z", fill: { color: "#e5e7eb" } },
  ]);
  const claims = "anchors:\n  P 0 0\n  Q 40 40\nclaims:\n  K1 grid 2 by 2 over P Q | stem |\n  K2 shaded 1 of 4 cells | stem |\n";
  const r = assess({ doc: d, claims, widths: [] });
  assert.equal(r.shaded.measured, 1);
  assert.equal(r.verdict, "PASS");
});

test("allow: label also downgrades target and arc findings", () => {
  const allow = 'allow: label:"60"\n';
  const d = doc([{ id: "arcB", type: "arc", center: [100, 100], r: 40, start: 0, end: 90, sweep: "cw" }]);
  // a bare "60" numeral OUTSIDE the arc's span (polar 225°) — arc would fail it…
  const arcCase = assess({ doc: d, claims: allow, widths: W([L({ text: "60", bbox: [60, 130, 10, 10], geom_u: 5 })]) });
  assert.equal(arcCase.verdict, "PASS");
  assert.ok(arcCase.findings.some((f) => f.rule === "arc" && f.severity === "allowed"));
  // …and a "60" label far from everything — target would fail it.
  const tgtCase = assess({ doc: doc([]), claims: allow, widths: W([L({ text: "60", geom_u: 40 })]) });
  assert.equal(tgtCase.verdict, "PASS");
  assert.ok(tgtCase.findings.some((f) => f.rule === "target" && f.severity === "allowed"));
});

test("math label fontSizeU is CANVAS units — target/arc thresholds must not scale with pxPerUnit", () => {
  // measure() recovers the math overlay's units font size (cs px = fontSizeU · pxPerUnit). If it
  // were wrongly kept as px, a label at distance 30 with true size 14 would PASS target at
  // ppu 2.6 (threshold 54.6) — the FAIL here pins the correct units (threshold 21).
  const mathLbl = { text: "x", kind: "math", bbox: [200, 100, 12, 8], fontSizeU: 14, geom_u: 30, edge_u: 50, stroke_u: 30 };
  const d = doc([{ id: "arcB", type: "arc", center: [100, 100], r: 40, start: 0, end: 90, sweep: "cw" }]);
  for (const ppu of [0.49, 2.6]) {
    const r = assess({ doc: d, widths: W([mathLbl], ppu) });
    assert.ok(rules(r).has("target"), `ppu ${ppu}: 30u > 1.5·14 must fail`);
    // arc near-window = r + 1.5·fontSizeU = 61u; the label centre is ~112u away at polar ~26.6° —
    // inside the span but beyond the window, so arc must NOT engage (checked 0 → arcs null).
    assert.equal(r.arcs, null, `ppu ${ppu}: a wrongly-scaled fontSizeU would pull the label into the arc window`);
  }
});
