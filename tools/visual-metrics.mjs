/**
 * visual-metrics.mjs — the PURE verdict half of `tools/visual-check.mjs`: no browser, no I/O.
 * It takes (a) the VDD document, (b) the optional claim set, and (c) the in-page label
 * measurement visual-check collects from real Chromium on Admin's /diagtest host page, and
 * returns a PASS/FAIL verdict with named findings. Unit-tested by tests/test_visual_metrics.mjs.
 *
 * Label measurement input shape (per width): { width, pxPerUnit, labels: [{i, text, kind,
 * bbox:[x,y,w,h] in CANVAS units|null, fontFamily, fontSizeU, edge_u, stroke_u, geom_u}] }.
 * `*_u` values are canvas units; rendered px = u × pxPerUnit. edge/stroke thresholds are in
 * RENDERED px (same as vdd-check); target/arc/shaded are scale-invariant canvas-unit rules.
 *
 * Rules:
 *   edge    — label bbox < 8 rendered px from the canvas edge
 *   stroke  — label bbox < 6 rendered px from a stroked primitive's EDGE (centreline − width/2)
 *   target  — label far from what it names: a label equal to a `point` element's label is measured
 *             bbox→point; any other label uses geom_u (nearest painted primitive). > 1.5·fontSizeU fails
 *   arc     — an angle numeral/variable (^\d+(\.\d+)?°?$ | ^[a-z]°?$ | ^[α-ωθ]°?$) whose centre's polar
 *             angle from the vertex lies outside the DRAWN span of every arc / unlabelled angleMark
 *             within r + 1.5·fontSizeU (labelled angleMarks are skipped — the renderer places those)
 *   shaded  — only with a `grid R by C over P Q` claim: measured fill area inside the grid bbox vs
 *             claimed cells (`shaded N of M cells` + 0.5 × `describe "…half shaded…"`)
 *   font    — KaTeX math labels mixed with <text> labels, or >1 computed fontFamily among texts
 */
export const EDGE_MIN_PX = 8;
export const STROKE_MIN_PX = 6;
export const TARGET_FACTOR = 1.5;
// One shared bound — the same figure-taller-than-a-phone-screen limit vdd_templates.py's finish()
// refuses at build time and vdd-check.mjs fails on the doc's canvas. Aspect is preserved from
// canvas to render, so any of the three sees the same ratio.
export const ASPECT_MAX = 2.0;
export const ARC_TOLERANCE_DEG = 2;
export const SHADED_TOLERANCE = 0.1; // cells
export const ARC_LABEL_RE = /^(\d+(\.\d+)?°?|[a-z]°?|[α-ωθ]°?)$/;
// A label with a run of ≥3 letters in ANY script is a header/legend (Sinhala row names, English
// words), not the name of a piece of geometry — the target rule skips it. Units ("cm", "ml") are
// 2 letters and stay checked. Point labels are ALWAYS checked against their own point.
export const WORD_LABEL_RE = /[\p{L}\p{M}]{3,}/u;

// ── Claim-set parser — the same grammar as tools/vdd-check.mjs's parseClaimSet (K1 pred args |
// evidence | note), so a claim set feeds both tools unchanged. Only the sections this module reads
// are materialised; the rest are still consumed so the parser never chokes on a real set. ──────────
export function parseClaimSet(text) {
  const lines = String(text).split(/\r?\n/);
  const cs = { labels: [], points: [], segments: [], anchors: {}, claims: [], channel: "vector" };
  let section = null;
  const sectionRe =
    /^(figure|source|channel|read|ask|stem|labels|points|segments|anchors|claims|scale|load-bearing|unreadable|ambiguous|departures|budget|allow):\s*(.*)$/;
  const buf = {};
  for (const raw of lines) {
    const line = raw.replace(/\s+#.*$/, "").replace(/^#.*$/, "");
    if (!line.trim()) continue;
    const m = line.match(sectionRe);
    if (m) {
      section = m[1];
      buf[section] = buf[section] ?? [];
      if (m[2]) buf[section].push(m[2]);
      continue;
    }
    if (section) buf[section].push(line);
  }
  const shlex = (s) => (s.match(/"[^"]*"|\S+/g) ?? []).map((t) => t.replace(/^"|"$/g, ""));
  cs.labels = shlex((buf.labels ?? []).join(" "));
  cs.points = shlex((buf.points ?? []).join(" "));
  cs.segments = shlex((buf.segments ?? []).join(" "));
  cs.channel = ((buf.channel ?? [""])[0] || "vector").trim().split(/\s/)[0];
  // allow differs from the other token lists: a label's TEXT may contain spaces, so
  // `label:"<text>"` must survive as ONE token (shlex alone would split it apart and quote-
  // strip only the outer edge — vdd-check's grammar has the same `label:<text>` entries).
  cs.allow = ((buf.allow ?? []).join(" ").match(/label:"[^"]*"|"[^"]*"|\S+/g) ?? [])
    .map((t) => t.replace(/^label:"(.*)"$/, "label:$1").replace(/^"|"$/g, ""));
  for (const l of buf.anchors ?? []) {
    const m = l.trim().match(/^([A-Z])\s+(-?[\d.]+)\s+(-?[\d.]+)$/);
    if (m) cs.anchors[m[1]] = [Number(m[2]), Number(m[3])];
  }
  for (const l of buf.claims ?? []) {
    const m = l.match(/^\s*([A-Z]\d+[a-z]?)\s+(\S+)\s+([^|]*?)\s*\|\s*(\w+)?/);
    if (!m) continue; // wrapped notes have a hanging indent and no id — skipped
    cs.claims.push({ id: m[1], pred: m[2], args: m[3].trim(), evidence: (m[4] ?? "").trim() });
  }
  return cs;
}

// ── Small geometry helpers ───────────────────────────────────────────────────────────────────────
const round1 = (v) => (v == null ? null : Math.round(v * 10) / 10);
const round2 = (v) => (v == null ? null : Math.round(v * 100) / 100);
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
/** Distance from point p to axis-aligned box bb=[x,y,w,h] (0 when p is inside). */
const distPointToBox = (p, bb) =>
  Math.hypot(
    Math.max(bb[0] - p[0], 0, p[0] - (bb[0] + bb[2])),
    Math.max(bb[1] - p[1], 0, p[1] - (bb[1] + bb[3])),
  );

// ── Arc semantics — MIRROR DiagramRenderer.tsx exactly (Admin src/components/diagram/): ────────────
// · `arc` element → sweepArcPath (lines ~321–345): delta = end − start; `sweep:"cw"` forces the
//   increasing-angle way round (delta<0 → +360), `"ccw"` the decreasing (delta>0 → −360), clamped
//   to ±360; with NO sweep field the written delta stands as authored (it may already be >180°).
// · `angleMark` → angleOf(vertex→from/to) = atan2 degrees, then arcPath (lines ~283–293): delta is
//   normalised to (−180,180] and `reflex` flips it (delta>0 → delta−360, else delta+360). Angles are
//   degrees clockwise from +x in screen coordinates (+y down — arc-geometry.ts header).
// · `rotation` on either element rotates about the mark's vertex/centre, shifting start by +rotation.
// variant:"right" draws a square over the same angular span, so the same span applies.
export function arcDelta(start, end, sweep) {
  let delta = end - start;
  if (sweep === "cw" && delta < 0) delta += 360;
  if (sweep === "ccw" && delta > 0) delta -= 360;
  return Math.max(-360, Math.min(360, delta));
}

export function angleMarkSpan(el) {
  const from =
    (Math.atan2(el.from[1] - el.vertex[1], el.from[0] - el.vertex[0]) * 180) / Math.PI;
  const to = (Math.atan2(el.to[1] - el.vertex[1], el.to[0] - el.vertex[0]) * 180) / Math.PI;
  let delta = to - from;
  while (delta <= -180) delta += 360;
  while (delta > 180) delta -= 360;
  if (el.reflex) delta = delta > 0 ? delta - 360 : delta + 360;
  // Multi-arc marks draw `arcs` concentric curves at r − i·spacing with the renderer's clamped
  // spacing — `arcs > 1 ? Math.min(6, Math.max(0, (r - 2) / (arcs - 1))) : 0` (DiagramRenderer.tsx
  // ~513: a flat −6·i goes negative at small r, and an invalid SVG radius silently drops the arc).
  const nArcs = el.arcs ?? 1, r = el.r ?? 24;
  const spacing = nArcs > 1 ? Math.min(6, Math.max(0, (r - 2) / (nArcs - 1))) : 0;
  const radii = Array.from({ length: nArcs }, (_, i) => r - i * spacing).filter((x) => x > 0);
  return { start: from, delta, radii };
}

/** Is θ (deg, same convention) inside the drawn span [start, start+delta] — ±tol at both ends? */
export function angleInSpan(theta, start, delta, tol = ARC_TOLERANCE_DEG) {
  if (Math.abs(delta) >= 360) return true;
  const rel = (((theta - start) % 360) + 360) % 360; // clockwise offset from the start ray, 0..360
  if (delta >= 0) return rel <= delta + tol || rel >= 360 - tol;
  return rel >= 360 + delta - tol || rel <= tol;
}

// ── Shaded-grid helpers ──────────────────────────────────────────────────────────────────────────
const PATH_ARITY = { M: 2, L: 2, Q: 4, C: 6, A: 7, Z: 0 };
function pathPoints(d) {
  const tokens = String(d ?? "").match(/[MLQCAZ]|[-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?/g) ?? [];
  const out = [];
  let cmd = "M";
  let i = 0;
  while (i < tokens.length) {
    if (PATH_ARITY[tokens[i]] !== undefined) {
      cmd = tokens[i];
      i++;
      continue;
    }
    const n = PATH_ARITY[cmd] ?? 0;
    if (!n) {
      i++;
      continue;
    }
    const a = tokens.slice(i, i + n).map(Number);
    if (a.length < n || a.some((v) => !Number.isFinite(v))) break;
    out.push([a[n - 2], a[n - 1]]);
    i += n;
  }
  return out;
}

/** Element axis-aligned bbox in canvas units (rotation ignored — shaded cells do not rotate). */
function elementBBox(el) {
  const pts = [];
  switch (el.type) {
    case "rect":
      pts.push([el.x, el.y], [el.x + el.width, el.y + el.height]);
      break;
    case "circle":
      pts.push([el.center[0] - el.r, el.center[1] - el.r], [el.center[0] + el.r, el.center[1] + el.r]);
      break;
    case "ellipse":
      pts.push(
        [el.center[0] - el.rx, el.center[1] - el.ry],
        [el.center[0] + el.rx, el.center[1] + el.ry],
      );
      break;
    case "polygon":
    case "polyline":
    case "line":
    case "arrow":
      pts.push(...(el.points ?? []));
      break;
    case "arc":
      pts.push([el.center[0] - el.r, el.center[1] - el.r], [el.center[0] + el.r, el.center[1] + el.r]);
      break;
    case "path":
      pts.push(...pathPoints(el.d));
      break;
    case "point":
    case "text":
    case "math":
      pts.push(el.at ?? [0, 0]);
      break;
    case "angleMark":
      pts.push(el.vertex, el.from, el.to);
      break;
    case "tickMark":
    case "parallelMark":
      pts.push(...(el.on ?? []));
      break;
    default:
      break;
  }
  if (!pts.length) return null;
  return [
    Math.min(...pts.map((p) => p[0])),
    Math.min(...pts.map((p) => p[1])),
    Math.max(...pts.map((p) => p[0])),
    Math.max(...pts.map((p) => p[1])),
  ];
}

/**
 * Filled area of an element in canvas units² — shoelace for polygons and `path` point runs (an
 * approximate bound for A/Q/C segments), rect w×h, circle/ellipse π·r·r. Everything else: 0.
 */
function elementArea(el) {
  switch (el.type) {
    case "rect":
      return Math.abs(el.width * el.height);
    case "circle":
      return Math.PI * el.r * el.r;
    case "ellipse":
      return Math.PI * el.rx * el.ry;
    case "polygon": {
      const p = el.points ?? [];
      let s = 0;
      for (let i = 0; i < p.length; i++) {
        const [x1, y1] = p[i];
        const [x2, y2] = p[(i + 1) % p.length];
        s += x1 * y2 - x2 * y1;
      }
      return Math.abs(s) / 2;
    }
    case "path": {
      const p = pathPoints(el.d); // closed: last→first edge counts, same as a polygon
      let s = 0;
      for (let i = 0; i < p.length; i++) s += p[i][0] * p[(i + 1) % p.length][1] - p[(i + 1) % p.length][0] * p[i][1];
      return Math.abs(s) / 2;
    }
    default:
      return 0;
  }
}

/**
 * Is a paint value VISIBLE ink? Mirrors the failure direction of vdd-check: none/transparent and
 * alpha-0 (#rgba/#rrggbbaa trailing 00, functional `…, 0)` / `…/0)` / `0%`) are not paint; anything
 * unrecognised counts as paint so a weird value errs toward measuring (a fail surfaced to a human
 * rather than silently passed).
 */
export function paintVisible(value) {
  if (value == null) return false;
  const s = String(value).trim().toLowerCase();
  if (!s || s === "none" || s === "transparent") return false;
  if (/^#[0-9a-f]{4}$|^#[0-9a-f]{8}$/.test(s)) return !/00$/.test(s);
  const alpha = s.match(/(?:,|\/)\s*([\d.]+%?)\s*\)$/);
  if (alpha && /^(?:rgba?|hsla?|lab|lch|oklab|oklch|color|color-mix)\(/.test(s) && parseFloat(alpha[1]) === 0)
    return false;
  return true;
}

/** Effective fill visibility on an element (fill.opacity × element.opacity × defaults.opacity > 0). */
function hasVisibleFill(el, defaults) {
  const color = el.fill?.color ?? defaults?.fillColor ?? "none";
  if (!paintVisible(color)) return false;
  const op = (el.fill?.opacity ?? 1) * (el.opacity ?? defaults?.opacity ?? 1);
  return op > 0;
}

// ── The assessment ───────────────────────────────────────────────────────────────────────────────
/**
 * assess({doc, claims, widths, fontsByWidth}) →
 *   { verdict: "PASS"|"FAIL", findings: [{rule, severity:"fail"|"allowed", message, label?}],
 *     labels: [{i, text, kind, width, edge_px, stroke_px, target_u, geom_u, fontSizeU, ok}],
 *     shaded: {claimed, measured, cell, cells}|null, font: {math, text, families}, arcs: {checked}|null,
 *     aspect: {ratio, limit}|null }
 */
export function assess({ doc = null, claims = null, widths = [], fontsByWidth = null }) {
  const cs = typeof claims === "string" ? parseClaimSet(claims) : claims ?? null;
  const elements = Array.isArray(doc?.elements) ? doc.elements : [];
  const allow = new Set(cs?.allow ?? []);
  const findings = [];
  const push = (rule, severity, message, label) => {
    const f = { rule, severity, message };
    if (label !== undefined) f.label = label;
    findings.push(f);
  };
  const declared = (rule, message, text) => {
    // `allow: label:"<text>"` downgrades a label-scoped finding — vdd-check's escape hatch, here
    // applied to edge/stroke/target/arc alike (a bare side-length numeral sitting near a wedge is
    // a legitimate `allow` — otherwise it can trip the arc rule).
    if (allow.has(`label:${text}`)) push(rule, "allowed", `${message} (declared via allow: label:"${text}")`, text);
    else push(rule, "fail", message, text);
  };
  const edgeOrStroke = (rule, ok, message, text) => { if (!ok) declared(rule, message, text); };

  // Elements that PRODUCE a label, by text — used to skip renderer-placed angleMark labels.
  const producersOf = (text, latex) =>
    elements.filter(
      (el) =>
        (el.type === "text" && el.value === text) ||
        (el.type === "point" && el.label === text) ||
        (el.type === "angleMark" && el.label === text) ||
        (el.type === "math" && (el.latex === latex || el.latex === text)),
    );
  const pointByLabel = new Map();
  for (const el of elements)
    if (el.type === "point" && typeof el.label === "string" && !pointByLabel.has(el.label))
      pointByLabel.set(el.label, el.at);

  // a point label's target is its OWN point's `at`; a word label (≥3-letter run, any script) is a
  // header/legend and is not measured; anything else's target is the nearest painted geometry.
  const targetOf = (l) => {
    if (l.bbox && pointByLabel.has(l.text))
      return { d: distPointToBox(pointByLabel.get(l.text), l.bbox), via: `point ${JSON.stringify(l.text)}` };
    if (WORD_LABEL_RE.test(l.text ?? "")) return { d: null, skipped: true };
    return { d: l.geom_u ?? null, via: "the nearest painted geometry" };
  };
  const targetBad = (l, tg) =>
    !tg.skipped && tg.d != null && l.fontSizeU > 0 && tg.d > TARGET_FACTOR * l.fontSizeU;

  // ONE target result per label, shared by the rows and the finding — the distance to the thing
  // a label names is a canvas-unit invariant, but the DOM box is re-measured at every width and
  // px rounding wobbles it ~±0.7u (a number-line point label read 26.8u at 320 and 27.5u at 375,
  // straddling the 1.5×fontSize bound, so the rows said not-ok while no finding fired). Evaluate
  // it once on the LEAST-quantised measurement — the largest pxPerUnit that produced a box.
  const targetByLabel = new Map(); // label index -> { l, tg }
  {
    const best = new Map();
    for (const w of widths)
      for (const l of w.labels ?? []) {
        const c = best.get(l.i);
        if (!c || (!c.l.bbox && l.bbox) || (!!c.l.bbox === !!l.bbox && (w.pxPerUnit || 0) > c.ppu))
          best.set(l.i, { l, ppu: w.pxPerUnit || 0 });
      }
    for (const [i, c] of best) targetByLabel.set(i, { l: c.l, tg: targetOf(c.l) });
  }
  const targetRes = (l) => targetByLabel.get(l.i) ?? { l, tg: targetOf(l) };

  // ── edge + stroke, per label per width (rendered px) ─────────────────────────────────────────
  const rows = [];
  for (const w of widths) {
    const ppu = w.pxPerUnit;
    for (const l of w.labels ?? []) {
      const edge_px = l.edge_u == null || ppu == null ? null : l.edge_u * ppu;
      const stroke_px = l.stroke_u == null || ppu == null ? null : l.stroke_u * ppu;
      const tr = targetRes(l);
      const row = {
        i: l.i,
        text: l.text,
        kind: l.kind,
        width: w.width,
        edge_px: round1(edge_px),
        stroke_px: round1(stroke_px),
        target_u: tr.tg.skipped ? null : round1(tr.tg.d),
        geom_u: round1(l.geom_u),
        fontSizeU: round1(l.fontSizeU),
        ok: edge_px !== null && edge_px >= EDGE_MIN_PX && (stroke_px === null || stroke_px >= STROKE_MIN_PX) && !targetBad(tr.l, tr.tg),
      };
      rows.push(row);
      if (edge_px === null)
        edgeOrStroke("edge", false, `label ${JSON.stringify(l.text)}: bbox unmeasurable at ${w.width}px — failing closed`, l.text);
      else if (edge_px < EDGE_MIN_PX)
        edgeOrStroke("edge", false, `label ${JSON.stringify(l.text)}: ${round1(edge_px)}px from the canvas edge at ${w.width}px (< ${EDGE_MIN_PX}px)`, l.text);
      if (stroke_px !== null && stroke_px < STROKE_MIN_PX)
        edgeOrStroke("stroke", false, `label ${JSON.stringify(l.text)}: ${round1(stroke_px)}px from stroke geometry at ${w.width}px (< ${STROKE_MIN_PX}px)`, l.text);
    }
  }

  // Width-invariant rules (arc, font) run once per label — every width renders the same canvas
  // units, so width[0]'s measurement stands for all. Target is also invariant, but its DOM box
  // estimate wobbles per width — its single result comes from targetByLabel (computed above on
  // the least-quantised width) rather than trusting width[0].
  const firstLabels = widths[0]?.labels ?? [];

  // ── target ───────────────────────────────────────────────────────────────────────────────────
  let targetFails = 0;
  for (const l of firstLabels) {
    const tr = targetRes(l);
    if (targetBad(tr.l, tr.tg)) {
      if (!allow.has(`label:${l.text}`)) targetFails++;
      declared("target", `label ${JSON.stringify(l.text)}: ${round1(tr.tg.d)}u from ${tr.tg.via} (> ${TARGET_FACTOR}× fontSize ${round1(tr.l.fontSizeU)}u)`, l.text);
    }
  }
  const target = { fails: targetFails };

  // ── arc ──────────────────────────────────────────────────────────────────────────────────────
  // Each numeral is associated with ITS arc. The owner is the candidate whose DRAWN CURVE is
  // nearest among the candidates whose span CONTAINS the label's polar angle — the naive "nearest
  // curve overall" false-fires on concentric arcs: a numeral between two rings can sit nearer the
  // smaller arc's endpoint than its own arc's curve (rebuilt Q3's numeral "2": 24.8u to arc1's
  // 90° endpoint vs 30u to arc2's curve — it is arc2's label). A numeral whose polar angle no
  // candidate's span contains fails against the nearest drawn curve; and two numerals resolving
  // to the same owner is its own failure — that is what catches a numeral dropped onto another
  // arc's wedge (rebuild defect D2 lands on top of the reflex arc's own numeral).
  let arcs = null;
  if (doc && firstLabels.length) {
    const candidates = [];
    for (const el of elements) {
      if (el.type === "arc") {
        const start = el.start + (el.rotation ?? 0);
        const delta = arcDelta(el.start, el.end, el.sweep);
        candidates.push({ id: el.id, centre: el.center, start, delta, curves: [el.r] });
      } else if (el.type === "angleMark") {
        // LABELLED marks are candidates too — their curves are drawn all the same; only the
        // mark's own renderer-placed label is skipped as a subject (the `producers` check below).
        const s = angleMarkSpan(el); // .radii mirrors the renderer's clamped multi-arc spacing
        candidates.push({
          id: el.id, centre: el.vertex, start: s.start + (el.rotation ?? 0), delta: s.delta,
          curves: s.radii, rightVariant: el.variant === "right" ? el.r : null,
        });
      }
    }
    const DEG = Math.PI / 180;
    for (const c of candidates) {
      // sample the painted curve(s) — every ~2° of arc; a right-mark's square legs ~every 2u
      c.pts = [];
      if (c.rightVariant) {
        const a = [c.centre[0] + c.rightVariant * Math.cos(c.start * DEG), c.centre[1] + c.rightVariant * Math.sin(c.start * DEG)];
        const b = [c.centre[0] + c.rightVariant * Math.cos((c.start + c.delta) * DEG), c.centre[1] + c.rightVariant * Math.sin((c.start + c.delta) * DEG)];
        const corner = [a[0] + b[0] - c.centre[0], a[1] + b[1] - c.centre[1]];
        for (const [p, q] of [[a, corner], [corner, b]]) {
          const n = Math.max(1, Math.ceil(dist(p, q) / 2));
          for (let i = 0; i <= n; i++) c.pts.push([p[0] + ((q[0] - p[0]) * i) / n, p[1] + ((q[1] - p[1]) * i) / n]);
        }
      } else {
        for (const r of c.curves) {
          const steps = Math.max(2, Math.ceil(Math.abs(c.delta) / 2));
          for (let i = 0; i <= steps; i++) {
            const th = (c.start + (c.delta * i) / steps) * DEG;
            c.pts.push([c.centre[0] + r * Math.cos(th), c.centre[1] + r * Math.sin(th)]);
          }
        }
      }
    }
    const owners = new Map(); // arc id -> [numeral texts]
    arcs = { checked: 0 };
    for (const l of firstLabels) {
      const text = l.text ?? "";
      if (!l.bbox || !(l.fontSizeU > 0) || !ARC_LABEL_RE.test(text)) continue;
      const producers = producersOf(text, l.latex);
      if (producers.length && producers.every((el) => el.type === "angleMark")) continue; // renderer-placed
      const centre = [l.bbox[0] + l.bbox[2] / 2, l.bbox[1] + l.bbox[3] / 2];
      const near = candidates.filter(
        (c) => c.pts.length && dist(centre, c.centre) <= Math.max(...c.curves, c.rightVariant ?? 0) + TARGET_FACTOR * l.fontSizeU,
      );
      if (!near.length) continue;
      arcs.checked++;
      const thetaOf = (c) => (Math.atan2(centre[1] - c.centre[1], centre[0] - c.centre[0]) * 180) / Math.PI;
      const curveDist = (c) => c.pts.reduce((m, p) => Math.min(m, dist(centre, p)), Infinity);
      const covering = near.filter((c) => angleInSpan(thetaOf(c), c.start, c.delta));
      if (!covering.length) {
        const owner = near.reduce((a, b) => (curveDist(a) <= curveDist(b) ? a : b));
        declared("arc",
          `label ${JSON.stringify(text)}: outside its own arc ${owner.id} (nearest drawn arc) — polar ${round1(thetaOf(owner))}°, span ${round1(owner.start)}°→${round1(owner.start + owner.delta)}°`,
          text);
      } else {
        const owner = covering.reduce((a, b) => (curveDist(a) <= curveDist(b) ? a : b));
        owners.set(owner.id, [...(owners.get(owner.id) ?? []), text]);
      }
    }
    for (const [id, texts] of owners)
      if (texts.length > 1) {
        const msg = `arc ${id} carries ${texts.length} numerals (${texts.map((t) => `"${t}"`).join(",")})`;
        if (texts.every((t) => allow.has(`label:${t}`)))
          push("arc", "allowed", `${msg} (all declared via allow)`);
        else push("arc", "fail", msg);
      }
    arcs.owners = Object.fromEntries(owners);
    if (!arcs.checked) arcs = null; // nothing to check against
  }

  // ── shaded (claim-set driven) ────────────────────────────────────────────────────────────────
  // Only fires when the claim set actually CLAIMS a shaded count: `shaded N of M cells` (+ 0.5
  // per `describe "…half shaded…"`). A bare `grid R by C` claim is NOT one — grid_polygon shades
  // its shape decoratively and would measure 21 cells vs an implied 0 (lead review: Q1 rebuild).
  let shaded = null;
  const gridClaim = cs?.claims.find(
    (c) => c.pred === "grid" && /^[\d.]+ by [\d.]+ over [A-Z] [A-Z]$/.test(c.args),
  );
  const shadedClaim = cs?.claims.find(
    (c) => c.pred === "shaded" && /^[\d.]+ of [\d.]+ cells?$/.test(c.args),
  );
  if (gridClaim && shadedClaim) {
    const [, R, C, P, Q] = gridClaim.args.match(/^([\d.]+) by ([\d.]+) over ([A-Z]) ([A-Z])$/);
    const a = cs.anchors[P];
    const b = cs.anchors[Q];
    if (a && b && +C > 0 && +R > 0) {
      const cellW = Math.abs(b[0] - a[0]) / +C;
      const cellH = Math.abs(b[1] - a[1]) / +R;
      const cell = cellW * cellH;
      const halves = cs.claims.filter(
        (c) => c.pred === "describe" && /half shaded/i.test(c.args),
      ).length;
      const claimed = (shadedClaim ? +shadedClaim.args.match(/^([\d.]+)/)[1] : 0) + halves / 2;
      const gb = [
        Math.min(a[0], b[0]) - 1,
        Math.min(a[1], b[1]) - 1,
        Math.max(a[0], b[0]) + 1,
        Math.max(a[1], b[1]) + 1,
      ];
      let area = 0;
      const counted = [];
      for (const el of elements) {
        if (!hasVisibleFill(el, doc?.defaults)) continue;
        const bb = elementBBox(el);
        if (!bb || bb[0] < gb[0] || bb[1] < gb[1] || bb[2] > gb[2] || bb[3] > gb[3]) continue;
        const ea = elementArea(el);
        if (ea > 0) {
          area += ea;
          counted.push(el.id);
        }
      }
      const measured = cell > 0 ? area / cell : 0;
      shaded = { claimed, measured: round2(measured), cell: round2(cell), cells: `${cellW}×${cellH}`, counted };
      if (Math.abs(measured - claimed) > SHADED_TOLERANCE)
        push("shaded", "fail", `shaded area: measured ${round2(measured)} cells vs claimed ${claimed} (grid ${R} by ${C} over ${P} ${Q}, cell ${round2(cell)}u²)`);
    }
  }

  // ── aspect — a figure much taller than wide renders taller than a 375 px phone screen ────────
  // Same bound as the build-time MAX_ASPECT in vdd_templates.py and vdd-check's canvas rule; the
  // render preserves the canvas ratio, so measure it wherever the plate was measured (prefer the
  // 375 record — the phone-width plate — else the widest, else the doc's canvas).
  let aspect = null;
  {
    const w375 =
      widths?.find((w) => w.width === 375) ??
      [...(widths ?? [])].sort((a, b) => (b.pxPerUnit || 0) - (a.pxPerUnit || 0))[0];
    const cw = w375?.viewBox?.[2] ?? doc?.canvas?.width;
    const ch = w375?.viewBox?.[3] ?? doc?.canvas?.height;
    const ratio = cw > 0 && ch > 0 ? ch / cw : null;
    if (ratio != null) {
      aspect = { ratio: round2(ratio), limit: ASPECT_MAX };
      if (ratio > ASPECT_MAX)
        push(
          "aspect",
          "fail",
          `aspect: figure renders ${round2(ratio)}× as tall as wide at ${w375?.width ?? "canvas"} px (> ${ASPECT_MAX}) — a phone screen won't hold it; re-lay it out, e.g. a 1×10 grid as 5×2`,
        );
    }
  }

  // ── font ─────────────────────────────────────────────────────────────────────────────────────
  const normFam = (f) => String(f ?? "").replace(/\s+/g, " ").trim();
  const fams = new Set(
    fontsByWidth
      ? fontsByWidth.flat().map(normFam).filter(Boolean)
      : firstLabels.filter((l) => l.kind === "text").map((l) => normFam(l.fontFamily)).filter(Boolean),
  );
  const mathN = firstLabels.filter((l) => l.kind === "math").length;
  const textN = firstLabels.length - mathN;
  const font = { math: mathN, text: textN, families: [...fams] };
  if (mathN > 0 && textN > 0)
    push("font", "fail", `font mix: KaTeX math ×${mathN} + text ×${textN}`);
  else if (fams.size > 1)
    push("font", "fail", `font mix: text labels use ${fams.size} faces (${[...fams].join(" | ")})`);

  const verdict = findings.some((f) => f.severity === "fail") ? "FAIL" : "PASS";
  return { verdict, findings, labels: rows, shaded, font, arcs, aspect };
}
