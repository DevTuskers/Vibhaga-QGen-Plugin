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
 *             bbox→point; standalone point letters must favour their own dot and cap the gap
 *             from the box to that dot. Dimension labels are checked against their claimed segments;
 *             unbound words and area labels are skipped, and other labels use nearest paint.
 *   arc     — an angle numeral/variable (^\d+(\.\d+)?°?$ | ^[a-z]°?$ | ^[α-ωθ]°?$) whose centre's polar
 *             angle from the vertex lies outside the DRAWN span of every arc / unlabelled angleMark
 *             within r + 1.5·fontSizeU (labelled angleMarks are skipped — the renderer places those)
 *   shaded  — only with a `grid R by C over P Q` claim: measured fill area inside the grid bbox vs
 *             claimed cells (`shaded N of M cells` + 0.5 × `describe "…half shaded…"`)
 *   font    — KaTeX math labels mixed with <text> labels, or >1 computed fontFamily among texts
 */
import { readFileSync } from "node:fs";

export const { ownLeaderMinPx: OWN_LEADER_MIN_PX, tickMaxGapPx: TICK_MAX_GAP_PX } =
  JSON.parse(readFileSync(new URL("./vdd-clearance.json", import.meta.url), "utf8"));
export const EDGE_MIN_PX = 8;
export const STROKE_MIN_PX = 6;
export const TARGET_FACTOR = 1.5;
const GRAPH_POINT_GAP_FACTOR = 0.72;
// The widest template search starts at 26u and can advance 36u, plus rendered-box slack.
const POINT_GAP_MAX = 64;
const TARGET_MARGIN = 0.25;
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
    const m = l.trim().match(/^([A-Z]\d*)\s+(-?[\d.]+)\s+(-?[\d.]+)$/);
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
function recordedPointGap(meta, glyph) {
  let scale = 1;
  while (meta && typeof meta === "object") {
    const gap = meta.pointLabelGaps?.[glyph];
    if (Number.isFinite(gap)) return gap * scale;
    if (meta.layoutMetadataSchema !== "vdd-layout-metadata-v1"
        || meta.inputMetadataRole !== "INPUT_PROVENANCE" || !meta.inputMetadataPresent) break;
    const step = meta.inputCanvasScale ?? 1;
    if (!Number.isFinite(step) || step <= 0) break;
    scale *= step;
    meta = meta.inputMetadata;
  }
  return 0;
}
const distToSegment = (p, [a, b]) => {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)));
  return dist(p, [a[0] + t * dx, a[1] + t * dy]);
};
const dimensionToken = (s) => s?.replace(/[−–]/g, "-").replace(/\s+/g, "");
const distBoxToSegment = (box, [a, b]) => {
  let lo = 0, hi = 1;
  for (let i = 0; i < 2; i++) {
    const delta = b[i] - a[i], min = box[i], max = min + box[i + 2];
    if (!delta) {
      if (a[i] < min || a[i] > max) hi = -1;
      continue;
    }
    const enter = (min - a[i]) / delta, exit = (max - a[i]) / delta;
    lo = Math.max(lo, Math.min(enter, exit));
    hi = Math.min(hi, Math.max(enter, exit));
  }
  if (lo <= hi) return 0;
  const [x, y, w, h] = box;
  return Math.min(distPointToBox(a, box), distPointToBox(b, box),
    ...[[x, y], [x + w, y], [x, y + h], [x + w, y + h]].map((p) => distToSegment(p, [a, b])));
};

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
 * alpha-0 (#rgba/#rrggbbaa trailing 00, a fourth rgb/hsl component or explicit `/ 0`) are not paint; anything
 * unrecognised counts as paint so a weird value errs toward measuring (a fail surfaced to a human
 * rather than silently passed).
 */
export function paintVisible(value) {
  if (value == null) return false;
  const s = String(value).trim().toLowerCase();
  if (!s || s === "none" || s === "transparent") return false;
  if (/^#[0-9a-f]{4}$|^#[0-9a-f]{8}$/.test(s)) return !/00$/.test(s);
  const alpha = s.match(/^(?:rgba?|hsla?)\((?:[^,()]+,){3}\s*([\d.]+%?)\s*\)$/) ??
    s.match(/^(?:rgba?|hsla?|lab|lch|oklab|oklch|color|color-mix)\(.*\/\s*([\d.]+%?)\s*\)$/);
  return !alpha || parseFloat(alpha[1]) !== 0;
}

/** Effective fill visibility on an element (fill.opacity × element.opacity × defaults.opacity > 0). */
function hasVisibleFill(el, defaults) {
  const color = el.fill?.color ?? defaults?.fillColor ?? "none";
  if (!paintVisible(color)) return false;
  const op = (el.fill?.opacity ?? 1) * (el.opacity ?? defaults?.opacity ?? 1);
  return op > 0;
}

export function visibleLine(el, defaults) {
  return el?.type === "line" && el.display !== "none" && el.style?.display !== "none" &&
    (el.opacity ?? defaults?.opacity ?? 1) > 0 && (el.stroke?.opacity ?? 1) > 0 &&
    (el.stroke?.width ?? defaults?.strokeWidth ?? 2) > 0 &&
    paintVisible(el.stroke?.color ?? defaults?.strokeColor ?? "black");
}

export function tickOwners(doc, cs) {
  const elements = new Map((doc?.elements ?? []).map((el) => [el.id, el]));
  const axes = new Map();
  for (const c of cs?.claims ?? []) {
    const a = c.pred === "axis" && c.args.match(/^([A-Z])([A-Z]) from (\S+) to (\S+)$/);
    if (a && cs.anchors[a[1]] && cs.anchors[a[2]])
      axes.set(a.slice(1, 3).join(""), [cs.anchors[a[1]], cs.anchors[a[2]], +a[3], +a[4]]);
  }
  const midpoint = (el) => visibleLine(el, doc?.defaults)
    ? el.points[0].map((v, i) => (v + el.points[1][i]) / 2) : null;
  const out = new Map();
  for (const c of cs?.claims ?? []) {
    if (c.pred !== "tick-label") continue;
    const [axis, rawValue, ticks, labelId, side] = c.args.split(/\s+/);
    const label = elements.get(labelId);
    const [tick, second] = (ticks ?? "").split(":").map((id) => elements.get(id));
    const at = midpoint(tick);
    const value = Number(rawValue);
    const rule = { axis, side, at, value, labelId, valid: false };
    out.set(labelId, rule);
    if (!at || label?.type !== "text" || Number(label.value) !== value || !/^[-\d.]+$/.test(label.value))
      continue;
    if (axis === "origin") {
      const [x, y] = [...axes.values()].filter(([, , lo, hi]) => lo <= 0 && hi >= 0)
        .map(([p, q, lo, hi]) => p.map((v, i) => v + (q[i] - v) * -lo / (hi - lo)));
      const other = midpoint(second);
      rule.valid = value === 0 && other && x && y && dist(at, x) < 1 && dist(at, y) < 1 &&
        dist(at, other) < 1;
    } else if (axes.has(axis)) {
      const [p, q, lo, hi] = axes.get(axis);
      const t = (value - lo) / (hi - lo);
      const expected = p.map((v, i) => v + (q[i] - v) * t);
      const horizontal = Math.abs(p[1] - q[1]) < 1;
      const vertical = Math.abs(p[0] - q[0]) < 1;
      rule.dimension = horizontal ? 0 : 1;
      rule.valid = t >= 0 && t <= 1 && dist(at, expected) < 1 && (
        (horizontal && ["above", "below"].includes(side) && Math.abs(tick.points[0][0] - tick.points[1][0]) < 1) ||
        (vertical && ["left", "right"].includes(side) && Math.abs(tick.points[0][1] - tick.points[1][1]) < 1));
    }
  }
  return out;
}

function tickSeatWrong(owner, label, owners, labels, scale) {
  if (!owner.valid || !owner.side || !label.bbox) return true;
  const b = label.bbox;
  const centre = [b[0] + b[2] / 2, b[1] + b[3] / 2];
  const [x, y] = owner.at;
  if (distPointToBox(owner.at, b) * scale > TICK_MAX_GAP_PX) return true;
  if ((owner.side.includes("left") && b[0] + b[2] >= x) ||
      (owner.side.includes("right") && b[0] <= x) ||
      (owner.side.includes("above") && b[1] + b[3] >= y) ||
      (owner.side.includes("below") && b[1] <= y)) return true;
  if (owner.axis === "origin") {
    if (!owner.side.endsWith("-left")) return true;
    const xLabels = [...owners.values()].filter((r) => r.valid && r.dimension === 0);
    const yLabels = [...owners.values()].filter((r) => r.valid && r.dimension === 1);
    const sameRow = xLabels.length && xLabels.every((r) => {
      const other = labels.get(r.labelId)?.bbox;
      return other && Math.abs(other[1] + other[3] - (b[1] + b[3])) <= 2;
    });
    const sameColumn = yLabels.length && yLabels.every((r) => {
      const other = labels.get(r.labelId)?.bbox;
      return other && Math.abs(other[0] + other[2] - (b[0] + b[2])) <= 2;
    });
    const nearOriginY = Math.max(b[1] - y, y - b[1] - b[3], 0) <= b[3];
    if (!sameRow && !(sameColumn && nearOriginY)) return true;
    return [...owners.values()].some((r) => {
      if (!r.valid || r.axis === "origin" || (sameRow ? r.dimension !== 0 : r.dimension !== 1)) return false;
      const i = r.dimension;
      // Zero occupies a corner; its projection need not be centered but must
      // be less than one labelled interval from the axes' crossing.
      const offset = centre[i] - owner.at[i], tickOffset = r.at[i] - owner.at[i];
      return tickOffset * offset > 0 && Math.abs(tickOffset) <= Math.abs(offset);
    });
  }
  const i = owner.dimension;
  const own = Math.abs(centre[i] - owner.at[i]);
  return own > 3 || [...owners.values()].some((r) => r !== owner && r.valid &&
    (r.axis === owner.axis || r.axis === "origin") && Math.abs(centre[i] - r.at[i]) <= own);
}

function junctions(elements) {
  const vertices = [], lines = [];
  for (const el of elements) {
    if (!["line", "arrow", "polygon", "polyline", "rect"].includes(el.type) ||
        /^(?:g[vh]|t[xy])\d+$/.test(el.id ?? "") || el.stroke?.width === 0 || el.opacity === 0) continue;
    const { x, y, width, height } = el;
    const pts = el.type === "rect" ? [[x, y], [x + width, y], [x + width, y + height], [x, y + height], [x, y]]
      : el.type === "polygon" ? [...el.points, el.points[0]] : el.points;
    if (el.type !== "polyline") vertices.push(...pts);
    lines.push(...pts.slice(1).map((b, i) => [el, pts[i], b]));
  }
  for (let i = 0; i < lines.length; i++) {
    const [el, a, b] = lines[i];
    for (let j = i + 1; j < lines.length; j++) {
      const [other, c, d] = lines[j];
      if (el === other) continue;
      const u = [b[0] - a[0], b[1] - a[1]], v = [d[0] - c[0], d[1] - c[1]];
      const cross = u[0] * v[1] - u[1] * v[0];
      if (Math.abs(cross) < 1e-9) continue;
      const [x, y] = [c[0] - a[0], c[1] - a[1]];
      const t = (x * v[1] - y * v[0]) / cross, s = (x * u[1] - y * u[0]) / cross;
      if (t >= 0 && t <= 1 && s >= 0 && s <= 1) vertices.push([a[0] + t * u[0], a[1] + t * u[1]]);
    }
  }
  return vertices;
}

function arrowHeadGap(arrow, trace, defaults) {
  if (arrow?.type !== "arrow" || !["end", "both"].includes(arrow.head) ||
      !["line", "polyline"].includes(trace?.type)) return -Infinity;
  const [start, tip] = arrow.points;
  const length = dist(start, tip);
  if (!length) return -Infinity;
  const u = (tip[0] - start[0]) / length, v = (tip[1] - start[1]) / length;
  const local = ([x, y]) => [(x - tip[0]) * u + (y - tip[1]) * v, -(x - tip[0]) * v + (y - tip[1]) * u];
  const size = arrow.headSize ?? 7 * (arrow.stroke?.width ?? defaults?.strokeWidth ?? 2);
  const head = [-0.9 * size, -0.4 * size, 0.9 * size, 0.8 * size];
  const path = trace.points.map(local);
  return path.slice(1).reduce((gap, b, i) => Math.min(gap, distBoxToSegment(head, [path[i], b])),
    Infinity) - (trace.stroke?.width ?? defaults?.strokeWidth ?? 2) / 2;
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
  // header/legend and is not measured; an AREA label — its `label` claim names a `region_…`
  // target (a Venn region's item or count, W14) — names the region it sits in, whose roomiest
  // point is legitimately far from every outline, so it is not measured either (edge and stroke
  // still are); anything else's target is the nearest painted geometry.
  const areaLabels = new Set();
  const claimPoints = new Map();
  const claimSegments = new Map();
  const segments = new Map((cs?.segments ?? [])
    .filter((s) => /^[A-Z]{2}$/.test(s) && cs.anchors?.[s[0]] && cs.anchors?.[s[1]]
      && dist(cs.anchors[s[0]], cs.anchors[s[1]]) > 0)
    .map((s) => [s, [cs.anchors[s[0]], cs.anchors[s[1]]]]));
  const marked = elements.filter((el) => el.type === "point" && el.r > 0).map((el) => el.at);
  const segmentKey = (name) => segments.has(name) ? name : [...name].reverse().join("");
  const axes = new Set((cs?.claims ?? []).filter((c) => c.pred === "axis")
    .flatMap((c) => c.args.match(/^[A-Z]{2}(?=\s)/)?.[0] ?? [])
    .map((s) => segments.has(s) ? s : [...s].reverse().join("")));
  const coordinateGraph = axes.size >= 2;
  for (const c of cs?.claims ?? []) {
    const scaled = c.pred === "scale-length" && String(c.args).match(/^([A-Z]{2}) = (.+)$/);
    if (scaled && segments.has(segmentKey(scaled[1]))) {
      const token = dimensionToken(scaled[2]);
      const candidates = claimSegments.get(token) ?? [];
      candidates.push(segmentKey(scaled[1]));
      claimSegments.set(token, candidates);
    }
    const m = c.pred === "label" && String(c.args).match(/^"(.*)" names (\S+)$/);
    if (!m) continue;
    const [, glyph, name] = m;
    if (name.startsWith("region_")) areaLabels.add(glyph);
    const anchor = cs.anchors?.[name];
    const dot = anchor && marked.find((pt) => dist(pt, anchor) < 1);
    if (dot) {
      const candidates = claimPoints.get(glyph) ?? [];
      candidates.push(dot);
      claimPoints.set(glyph, candidates);
    }
    const side = segmentKey(name);
    if (segments.has(side) && !axes.has(side)) {
      const token = dimensionToken(glyph);
      const candidates = claimSegments.get(token) ?? [];
      candidates.push(side);
      claimSegments.set(token, candidates);
    }
  }
  const pointsById = new Map(), dimensionsById = new Map();
  const byElementId = new Map(elements.map((el) => [el.id, el]));
  const mobileScale = Math.min(1, ...widths.map((w) => w.pxPerUnit).filter((p) => p > 0));
  for (const c of cs?.claims ?? []) {
    const [target, id, limit, callout] = c.args.split(/\s+/);
    if (c.pred === "point-label") pointsById.set(id, [cs.anchors[target], Number(limit), target]);
    if (c.pred === "dimension-label") dimensionsById.set(id, [byElementId.get(target), Number(limit), target, callout]);
    if (c.pred === "axis-clearance") {
      const [arrow, gap, ...traces] = c.args.split(/\s+/);
      const scale = Math.min(...widths.map((w) => w.pxPerUnit).filter((p) => p > 0));
      for (const trace of traces) {
        if (arrowHeadGap(byElementId.get(arrow), byElementId.get(trace), doc?.defaults) * scale < Number(gap))
          push("axis-clearance", "fail", `trace ${trace} approaches the ${arrow} arrowhead (needs ${gap} rendered px)`);
      }
    }
  }
  const crossings = pointsById.size ? junctions(elements) : [];
  const ticks = tickOwners(doc, cs);
  const targetOf = (l, ppu, labels) => {
    if (ticks.has(l.elementId)) {
      const tick = ticks.get(l.elementId);
      return { d: null, via: `tick ${tick.axis}`, ambiguous: labels && tickSeatWrong(tick, l, ticks, labels, mobileScale) };
    }
    const bound = pointsById.get(l.elementId);
    if (bound && l.bbox) {
      const [at, limit, target] = bound;
      if (!at || !ppu) return { d: null, ambiguous: true, via: `point ${target}` };
      const centre = [l.bbox[0] + l.bbox[2] / 2, l.bbox[1] + l.bbox[3] / 2];
      const own = dist(centre, at);
      const ambiguous = [...marked, ...crossings].some((v) => dist(v, at) > 2 &&
        dist(centre, v) <= own + TARGET_MARGIN * l.fontSizeU);
      return { d: distPointToBox(at, l.bbox), ambiguous, limit: limit / mobileScale, via: `point ${target}` };
    }
    const dimension = dimensionsById.get(l.elementId);
    if (dimension && l.bbox) {
      const [leader, limit, target, callout] = dimension;
      const via = `leader ${target}`;
      if (!visibleLine(leader, doc?.defaults) || !ppu) return { d: null, ambiguous: true, via };
      const [a, b] = leader.points;
      const midpoint = a.map((v, i) => (v + b[i]) / 2);
      if (callout) {
        const connector = byElementId.get(callout);
        const points = connector?.points;
        if (!visibleLine(connector, doc?.defaults) ||
            !points?.some((p) => dist(p, midpoint) <= 0.1))
          return { d: null, ambiguous: true, via };
        const tip = points.find((p) => dist(p, midpoint) > 0.1);
        if (!tip || dist(tip, midpoint) * mobileScale > 40)
          return { d: null, ambiguous: true, via };
        return { d: distPointToBox(tip, l.bbox), limit: 8 / mobileScale, via };
      }
      return { d: distPointToBox(midpoint, l.bbox), limit: Math.min(limit, 18) / mobileScale, via };
    }
    if (l.bbox && pointByLabel.has(l.text))
      return { d: distPointToBox(pointByLabel.get(l.text), l.bbox), via: `point ${JSON.stringify(l.text)}` };
    if (l.bbox) {
      const [x, y, w, h] = l.bbox;
      const centre = [x + w / 2, y + h / 2];
      const points = claimPoints.get(l.text);
      if (points?.length === 1) {
        const own = dist(centre, points[0]);
        const ambiguous = marked.some((pt) => dist(pt, points[0]) > 1
          && dist(centre, pt) <= own + TARGET_MARGIN * l.fontSizeU);
        const graphGap = GRAPH_POINT_GAP_FACTOR * l.fontSizeU;
        const limit = coordinateGraph && graphGap > 0
          ? Math.min(POINT_GAP_MAX, Math.max(graphGap, recordedPointGap(doc?.meta, l.text)))
          : POINT_GAP_MAX;
        return { d: distPointToBox(points[0], l.bbox),
          via: `claimed point ${JSON.stringify(l.text)}`, ambiguous, limit };
      }
      if (WORD_LABEL_RE.test(l.text ?? "") || areaLabels.has(l.text)) return { d: null, skipped: true };
      const sides = claimSegments.get(dimensionToken(l.latex)) ?? claimSegments.get(dimensionToken(l.text));
      if (sides?.length) {
        const intended = sides.map((s) => [s, distToSegment(centre, segments.get(s))])
          .sort((a, b) => a[1] - b[1])[0][0];
        const side = segments.get(intended);
        const d = distToSegment(centre, side);
        const [a, b] = side;
        const ambiguous = [...segments].some(([name, [p, q]]) => name !== intended
          && ![...intended].some((point) => name.includes(point))
          && Math.abs((b[0] - a[0]) * (q[1] - p[1]) - (b[1] - a[1]) * (q[0] - p[0])) < 1
          && distToSegment(centre, [p, q]) <= d + TARGET_MARGIN * l.fontSizeU);
        return { d: distBoxToSegment(l.bbox, side), via: `claimed segment ${intended}`, ambiguous };
      }
    }
    if (WORD_LABEL_RE.test(l.text ?? "") || areaLabels.has(l.text)) return { d: null, skipped: true };
    return { d: l.geom_u ?? null, via: "the nearest painted geometry" };
  };
  for (const w of widths) {
    const byId = new Map((w.labels ?? []).map((l) => [l.elementId, l]));
    for (const [id, owner] of ticks) {
      if (tickSeatWrong(owner, byId.get(id) ?? {}, ticks, byId, mobileScale))
        push("tick-label", "fail",
          `label ${id}: ${owner.value} is not seated at its own ${owner.axis} tick on the ${owner.side} side at ${w.width}px`,
          String(owner.value));
    }
    for (const id of [...pointsById.keys(), ...dimensionsById.keys()])
      if (!byId.get(id)?.bbox) push("target", "fail", `bound label ${id} did not render at ${w.width}px`);
  }
  const targetBad = (l, tg) => !tg.skipped && (tg.ambiguous || (tg.d != null
    && (tg.limit != null ? tg.d > tg.limit : l.fontSizeU > 0 && tg.d > TARGET_FACTOR * l.fontSizeU)));

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
    for (const [i, c] of best) targetByLabel.set(i, { l: c.l, tg: targetOf(c.l, c.ppu) });
  }
  const targetRes = (l) => targetByLabel.get(l.i) ?? { l, tg: targetOf(l) };

  // ── edge + stroke, per label per width (rendered px) ─────────────────────────────────────────
  const rows = [];
  for (const w of widths) {
    const ppu = w.pxPerUnit;
    const labelsById = new Map((w.labels ?? []).map((l) => [l.elementId, l]));
    for (const l of w.labels ?? []) {
      const edge_px = l.edge_u == null || ppu == null ? null : l.edge_u * ppu;
      const dimension = dimensionsById.get(l.elementId);
      const relaxed = dimension && l.strokeByElement && ppu;
      const soft = relaxed ? new Set([dimension[2], dimension[3]]) : null;
      const rendered = relaxed ? Object.entries(l.strokeByElement).map(([id, u]) => [u * ppu, soft.has(id) ? OWN_LEADER_MIN_PX : STROKE_MIN_PX]) : [];
      const stroke_px = l.stroke_u == null || ppu == null ? null : l.stroke_u * ppu;
      const violation = relaxed ? rendered.find(([gap, min]) => gap < min) :
        stroke_px !== null && stroke_px < STROKE_MIN_PX ? [stroke_px, STROKE_MIN_PX] : null;
      const tr = pointsById.has(l.elementId) || dimensionsById.has(l.elementId) || ticks.has(l.elementId)
        ? { l, tg: targetOf(l, ppu, labelsById) } : targetRes(l);
      if ((pointsById.has(l.elementId) || dimensionsById.has(l.elementId)) && targetBad(l, tr.tg))
        declared("target", `label ${JSON.stringify(l.text)} is detached from or ambiguous at ${tr.tg.via} at ${w.width}px`, l.text);
      const row = {
        i: l.i,
        text: l.text,
        kind: l.kind,
        width: w.width,
        edge_px: round1(edge_px),
        stroke_px: round1(stroke_px),
        target_u: tr.tg.skipped ? null : round1(tr.tg.d),
        target_via: ticks.has(l.elementId) ? `tick ${ticks.get(l.elementId).axis}` : tr.tg.via ?? null,
        binding: ticks.has(l.elementId) || (tr.tg.via && tr.tg.via !== "the nearest painted geometry")
          ? "bound" : tr.tg.skipped ? "not-applicable" : "fallback",
        geom_u: round1(l.geom_u),
        fontSizeU: round1(l.fontSizeU),
        ok: edge_px !== null && edge_px >= EDGE_MIN_PX && !violation && !targetBad(tr.l, tr.tg),
      };
      rows.push(row);
      if (edge_px === null)
        edgeOrStroke("edge", false, `label ${JSON.stringify(l.text)}: bbox unmeasurable at ${w.width}px — failing closed`, l.text);
      else if (edge_px < EDGE_MIN_PX)
        edgeOrStroke("edge", false, `label ${JSON.stringify(l.text)}: ${round1(edge_px)}px from the canvas edge at ${w.width}px (< ${EDGE_MIN_PX}px)`, l.text);
      if (violation)
        edgeOrStroke("stroke", false, `label ${JSON.stringify(l.text)}: ${round1(violation[0])}px from stroke geometry at ${w.width}px (< ${violation[1]}px)`, l.text);
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
    if (pointsById.has(l.elementId) || dimensionsById.has(l.elementId) || ticks.has(l.elementId)) continue;
    const tr = targetRes(l);
    if (targetBad(tr.l, tr.tg)) {
      if (!allow.has(`label:${l.text}`)) targetFails++;
      const bound = tr.tg.limit == null
        ? `${TARGET_FACTOR}× fontSize ${round1(tr.l.fontSizeU)}u`
        : `${round1(tr.tg.limit)}u box gap`;
      const reason = tr.tg.ambiguous
        ? `could name another target near ${tr.tg.via}`
        : `${round1(tr.tg.d)}u from ${tr.tg.via} (> ${bound})`;
      declared("target", `label ${JSON.stringify(l.text)}: ${reason}`, l.text);
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
  // 375 record — the phone-width plate — else the least-quantised plate (max pxPerUnit), else the
  // doc's canvas).
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
