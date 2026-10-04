#!/usr/bin/env node
/**
 * THE ONE-COMMAND VERIFIER for a Vibhaga Diagram DSL (VDD) figure — `draw-check`.
 * (Moved from Vibhaga-Docs `.devin/skills/_maths-onboarding/vdd-check.mjs`; there is no source
 * paper in this plugin — every figure is authored on the canvas against a constructed claim set.)
 *
 *     node tools/vdd-check.mjs figure.json \
 *          [--claims q7-claims.txt] [--anchors figure.anchors.json] \
 *          [--out /tmp/vdd-out] [--widths 320,375,768] [--no-render] [--headed] [--json] \
 *          [--allow K5,"label:7 cm"] [--medium sinhala] [--admin /path/to/Vibhaga-Admin]
 *     node tools/vdd-check.mjs --self-test
 *
 * Vibhaga-Admin resolution: `--admin PATH` > `VIBHAGA_ADMIN` env > `<plugin>/../Vibhaga-Admin`.
 * It runs, in order, every mechanical check the draw-and-verify skill prescribes, against the REAL
 * Admin sources (bundled with Admin's own esbuild — nothing in Vibhaga-Admin is edited or installed):
 *
 *   1. `parseVddDocument` (@vibhaga/shared)   (S6b §4.1 — nothing on any write path validates VDD)
 *   2. `a11y.title` real + non-generic, `a11y.description` present        (S6b §0.3, §3.3)
 *   3. label hygiene: no `$`, no backtick, no Sinhala in any DRAWN text (every medium —
 *      ADR 0021; a11y title/description are exempt)                      (S6b §0.5–0.6)
 *   4. element budget (≤ 32 is a smell threshold, not a schema cap)         (S6b §3.4)
 *   4b. canvas aspect — height/width > 2.0 renders taller than a 375 px phone screen (no override)
 *   5. `path` elements reported (avoid unless nothing else can draw it)     (T-S6b-9)
 *   6. `checkDiagram()` — ADVISORY, printed, never blocking                  (S6b §0.8)
 *   7. normalize consistency — `normalizeVdd(doc)` must move EVERY element by the same (dx, dy)
 *      (the reviewer's card runs it; Q22's `path` did not move with the rest — T-S6b-9, §4.2b)
 *   8. claim-set COVERAGE — every `segments` entry covered by an element, every `labels` glyph
 *      carried by exactly one element, every `points` entry anchored          (S6b §5.2, T99)
 *   9. NUMERIC comparison — every angle / ratio / collinear / parallel / equal / right / on claim
 *      recomputed from the drawing's CANVAS anchors and diffed against BOTH the claim set's
 *      STATED value (the stem-derived number) and its CLAIM-SET anchors (canvas coordinates for a
 *      constructed set), against the single tight band (ratio ≤ 2 % · angle ≤ 1° · residual ≤ 1 %)
 *  10. RENDER on BOTH code paths (the stored document = student surfaces; `normalizeVdd(doc)` = the
 *      Admin card) at 320 · 375 · 768 px in real Chromium, screenshots to --out, and the SVG read:
 *      every claim-set label rendered as a `<text>`, `aria-label` and `<desc>` resolve, and every
 *      `<text>` label's bbox measured ≥ 8 rendered px from the canvas edge and ≥ 6 rendered px from
 *      stroke geometry — rendered px at each width (viewBox units × render scale), measured to the
 *      stroke's EDGE (centreline − half its rendered width); the templates' faint ruling lines
 *      (gv<n>/gh<n> `line` ids) are exempt — a letter may sit over them (owner ruling 2026-10-04);
 *      an unmeasurable bbox fails closed
 *      (declare an intentional departure with an `allow: label:"<text>"` claim-set line)
 *
 * CANVAS ANCHORS (for 8–9). The drawing's named points, in canvas coordinates, come from — in
 * priority order — `--anchors a.json` (`{"A":[x,y],…}`), the document's `meta.anchors` (same shape;
 * `meta` is schema-legal and never rendered), or every `point` element whose `label` is one capital
 * letter. `vdd-cookbook.py` writes `<figure>.anchors.json` beside every figure it generates.
 *
 * EXIT CODE: 1 on any hard failure (1–5, 7–10); 0 otherwise. Advisories never fail it — and under
 * `--no-render` the directed-arrow paint check degrades to a WARN (run once rendered per arrow figure;
 * `build-staged --vdd-check` relies on this so arrow figures don't wedge the build).
 * `--json` also writes `<out>/report.json` for the verification record — including
 * `labels: [{text, edge_px, stroke_px, ok}]` aggregated across surfaces and widths.
 *
 * ⚠️ The check can prove the document is legal, coherent with its claim set and rendered; it cannot
 * prove the claim set's numbers match the stem. That is `audit-claim-set.py`'s stem-ratio check.
 */
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import { ASPECT_MAX, paintVisible } from "./visual-metrics.mjs";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// This file lives at <plugin-checkout>/tools/ — Vibhaga-Admin is the plugin's SIBLING by default.
const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const flag = (name) => args.includes(name);
const ADMIN = path.resolve(opt("--admin") ?? process.env.VIBHAGA_ADMIN ?? path.join(HERE, "..", "..", "Vibhaga-Admin"));
const die = (msg) => { console.error(`vdd-check: ${msg}`); process.exit(2); };

if (!fs.existsSync(path.join(ADMIN, "package.json"))) die(`no Vibhaga-Admin at ${ADMIN} (pass --admin PATH or set VIBHAGA_ADMIN)`);
const ESBUILD = path.join(ADMIN, "node_modules/.bin/esbuild");
if (!fs.existsSync(ESBUILD)) die(`no esbuild at ${ESBUILD} — run \`npm ci\` in Vibhaga-Admin`);

// ── 0. Bundle Admin's own schema / validator / normalizer for node (cached by source mtime) ─────────
const CACHE = path.join(os.tmpdir(), "vibhaga-vdd-check");
fs.mkdirSync(CACHE, { recursive: true });
// The entries are written into the cache dir, so bare imports (`react-dom/client`, the jsx runtime,
// `@vibhaga/shared`) resolve through a symlink to Admin's own node_modules — the SAME React the app
// renders with. Recreate it every run: a link made under a different VIBHAGA_ADMIN keeps pointing at
// that checkout's node_modules and silently resolves the wrong (or a missing) package.
const NM = path.join(CACHE, "node_modules");
// rmSync, not existsSync+rmSync: a DANGLING symlink (a VIBHAGA_ADMIN path removed since the last
// run) reads as "missing" to existsSync and the re-create then EEXISTs.
try { if (fs.lstatSync(NM).isSymbolicLink()) fs.unlinkSync(NM); else fs.rmSync(NM, { recursive: true, force: true }); } catch (e) { if (e.code !== "ENOENT") throw e; }
fs.symlinkSync(path.join(ADMIN, "node_modules"), NM, "dir");
const SRC = path.join(ADMIN, "src/components/diagram");
// The schema + paint grammar moved to the installed @vibhaga/shared package (2026-09-26; Admin's
// vdd.ts / colors.ts are deleted) — the cache key tracks its dist alongside the still-local files.
const SHARED_SCHEMA = path.join(ADMIN, "node_modules/@vibhaga/shared/dist/vdd-schema");
if (!fs.existsSync(SHARED_SCHEMA)) die(`no @vibhaga/shared under ${ADMIN}/node_modules — the schema moved out of src/ on 2026-09-26; run \`npm ci\` in an Admin checkout that carries the package`);
function stamp() {
  return [
    ...["validate.ts", "normalize.ts", "DiagramRenderer.tsx"].map((f) => path.join(SRC, f)),
    ...["index.js", "parse.js", "types.js", "colors.js"].map((f) => path.join(SHARED_SCHEMA, f)),
  ].map((f) => fs.statSync(f).mtimeMs.toFixed(0)).join("-");
}
const SELF_HASH = crypto.createHash("sha1").update(fs.readFileSync(fileURLToPath(import.meta.url))).digest("hex").slice(0, 8); // entries live in this file
const NODE_BUNDLE = path.join(CACHE, `lib-${stamp()}-${SELF_HASH}.mjs`);
if (!fs.existsSync(NODE_BUNDLE)) {
  const entry = path.join(CACHE, "lib-entry.ts");
  fs.writeFileSync(entry, `export { parseVddDocument, safeColor } from "@vibhaga/shared/vdd-schema";
export { checkDiagram } from "@/components/diagram/validate";
export { normalizeVdd } from "@/components/diagram/normalize";
`);
  execFileSync(ESBUILD, [entry, "--bundle", "--format=esm", "--platform=node", `--outfile=${NODE_BUNDLE}`,
    `--alias:@=${path.join(ADMIN, "src")}`, "--log-level=error"]);
}
const lib = await import(pathToFileURL(NODE_BUNDLE).href);

// ── Geometry helpers (shared by the numeric check and the coverage check) ─────────────────────────
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const len = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const angDeg = (v) => (Math.atan2(v[1], v[0]) * 180) / Math.PI;
/** Interior angle at Q between QP and QR, in degrees (0..180). */
function angleAt(P, Q, R) {
  const a = sub(P, Q), b = sub(R, Q);
  const d = a[0] * b[0] + a[1] * b[1], m = Math.hypot(...a) * Math.hypot(...b);
  if (m === 0) return NaN;
  return (Math.acos(Math.max(-1, Math.min(1, d / m))) * 180) / Math.PI;
}
/** Perpendicular distance of Q from line PR as a fraction of |PR| (collinearity residual). */
function offLine(P, Q, R) {
  const L = len(P, R); if (L === 0) return NaN;
  return Math.abs((R[0] - P[0]) * (P[1] - Q[1]) - (P[0] - Q[0]) * (R[1] - P[1])) / L / L;
}
function parallelResidual(P, Q, R, S) {
  let d = Math.abs(angDeg(sub(Q, P)) - angDeg(sub(S, R))) % 180;
  return Math.min(d, 180 - d);
}
/** Is X on segment PQ (within tol, as a fraction of |PQ|), including the ends? */
function onSegment(X, P, Q, tol) {
  const L = len(P, Q); if (L === 0) return len(X, P) <= tol * 10;
  const t = ((X[0] - P[0]) * (Q[0] - P[0]) + (X[1] - P[1]) * (Q[1] - P[1])) / (L * L);
  if (t < -tol || t > 1 + tol) return false;
  return offLine(P, X, Q) <= tol;
}
/** The closed edge chain a point-coverage check walks — rect corners, closed polygon, else the points. */
function edgeChain(el) {
  if (el.type === "rect")
    return [[el.x, el.y], [el.x + el.width, el.y], [el.x + el.width, el.y + el.height], [el.x, el.y + el.height], [el.x, el.y]];
  if (el.type === "polygon") return [...el.points, el.points[0]];
  return el.points;
}
/** Is P within 1.5 units of a curved rim — circle, ellipse (radial) or arc (also inside its sweep)? */
function onRim(el, P) {
  if (el.type === "circle") return Math.abs(len(el.center, P) - el.r) <= 1.5;
  if (el.type === "ellipse") {
    const d = Math.hypot((P[0] - el.center[0]) / el.rx, (P[1] - el.center[1]) / el.ry);
    return Math.abs((d - 1) * Math.min(el.rx, el.ry)) <= 1.5;
  }
  if (el.type === "arc") {
    if (Math.abs(len(el.center, P) - el.r) > 1.5) return false;
    const a = (angDeg(sub(P, el.center)) + 360) % 360, s = (el.start + 360) % 360, e = (el.end + 360) % 360;
    return s <= e ? a >= s && a <= e : a >= s || a <= e;
  }
  return false;
}

// ── Claim-set parsing (the subset the drawing can be checked against; S6a §3) ─────────────────────
function parseClaimSet(text) {
  const lines = text.split(/\r?\n/);
  const cs = { labels: [], points: [], segments: [], anchors: {}, claims: [], channel: "vector" };
  let section = null;
  const sectionRe = /^(figure|source|channel|read|ask|stem|labels|points|segments|anchors|claims|scale|load-bearing|unreadable|ambiguous|departures|budget|allow):\s*(.*)$/;
  const buf = {};
  for (const raw of lines) {
    const line = raw.replace(/\s+#.*$/, "").replace(/^#.*$/, "");
    if (!line.trim()) continue;
    const m = line.match(sectionRe);
    if (m) { section = m[1]; buf[section] = (buf[section] ?? []); if (m[2]) buf[section].push(m[2]); continue; }
    if (section) buf[section].push(line);
  }
  const shlex = (s) => (s.match(/"[^"]*"|\S+/g) ?? []).map((t) => t.replace(/^"|"$/g, ""));
  cs.labels = shlex((buf.labels ?? []).join(" "));
  cs.points = shlex((buf.points ?? []).join(" "));
  cs.segments = shlex((buf.segments ?? []).join(" "));
  cs.channel = ((buf.channel ?? [""])[0] || "vector").trim().split(/\s/)[0];
  cs.budget = Number((buf.budget ?? [""])[0]) || null;  // claim-set-declared element budget — the why lives in departures:
  cs.allow = shlex((buf.allow ?? []).join(" "));        // claim-set-declared numeric departures — same rule
  for (const l of buf.anchors ?? []) {
    const m = l.trim().match(/^([A-Z]\d*)\s+(-?[\d.]+)\s+(-?[\d.]+)$/);   // W11: digit-suffixed points (T1..Tn)
    if (m) cs.anchors[m[1]] = [Number(m[2]), Number(m[3])];
  }
  for (const l of buf.claims ?? []) {
    const m = l.match(/^\s*([A-Z]\d+[a-z]?)\s+(\S+)\s+([^|]*?)\s*\|\s*(\w+)?/);
    if (!m) continue;           // wrapped notes have a hanging indent and no id — skipped
    cs.claims.push({ id: m[1], pred: m[2], args: m[3].trim(), evidence: (m[4] ?? "").trim() });
  }
  return cs;
}

/** Evaluate the geometric claims this tool understands against a {name:[x,y]} anchor map. */
function evalClaims(cs, A, elements = []) {
  const out = [];
  const has = (...ps) => ps.every((p) => A[p]);
  for (const c of cs.claims) {
    let m;
    if (c.pred === "angle" && (m = c.args.match(/^([A-Z]) ([A-Z]) ([A-Z]) = (-?[\d.]+)$/))) {
      if (has(m[1], m[2], m[3])) out.push({ id: c.id, kind: "angle", claim: `angle ${m[1]}${m[2]}${m[3]}`, stated: +m[4], value: angleAt(A[m[1]], A[m[2]], A[m[3]]), evidence: c.evidence });
    } else if (c.pred === "right" && (m = c.args.match(/^([A-Z]) ([A-Z]) ([A-Z])$/))) {
      if (has(m[1], m[2], m[3])) out.push({ id: c.id, kind: "angle", claim: `right ${m[1]}${m[2]}${m[3]}`, stated: 90, value: angleAt(A[m[1]], A[m[2]], A[m[3]]), evidence: c.evidence });
    } else if (c.pred === "ratio" && (m = c.args.match(/^len ([A-Z])([A-Z]) \/ len ([A-Z])([A-Z]) = (-?[\d.]+)$/))) {
      if (has(m[1], m[2], m[3], m[4])) out.push({ id: c.id, kind: "ratio", claim: `len ${m[1]}${m[2]} / len ${m[3]}${m[4]}`, stated: +m[5], value: len(A[m[1]], A[m[2]]) / len(A[m[3]], A[m[4]]), evidence: c.evidence });
    } else if (c.pred === "collinear" && (m = c.args.match(/^([A-Z]) ([A-Z]) ([A-Z])$/))) {
      if (has(m[1], m[2], m[3])) out.push({ id: c.id, kind: "residual", claim: `collinear ${m[1]}${m[2]}${m[3]}`, stated: 0, value: offLine(A[m[1]], A[m[2]], A[m[3]]), evidence: c.evidence });
    } else if (c.pred === "on" && (m = c.args.match(/^([A-Z])(?:\s+on)?\s+([A-Z])([A-Z])$/))) {
      // `K1 on E AB` is the corpus spelling (every committed claim set); `K1 on E on AB` was the doc-table
      // spelling nobody wrote — both tolerated here; `audit-claim-set.py` accepts only the first.
      // Note: this checks collinearity only, not betweenness — audit-claim-set checks `inside` on its anchors.
      if (has(m[1], m[2], m[3])) out.push({ id: c.id, kind: "residual", claim: `${m[1]} on ${m[2]}${m[3]}`, stated: 0, value: offLine(A[m[2]], A[m[1]], A[m[3]]), evidence: c.evidence });
    } else if (c.pred === "parallel" && (m = c.args.match(/^([A-Z])([A-Z]) ([A-Z])([A-Z])$/))) {
      if (has(m[1], m[2], m[3], m[4])) out.push({ id: c.id, kind: "angle", claim: `parallel ${m[1]}${m[2]} ${m[3]}${m[4]}`, stated: 0, value: parallelResidual(A[m[1]], A[m[2]], A[m[3]], A[m[4]]), evidence: c.evidence });
    } else if (c.pred === "equal" && (m = c.args.match(/^([A-Z])([A-Z]) ([A-Z])([A-Z])$/))) {
      if (has(m[1], m[2], m[3], m[4])) out.push({ id: c.id, kind: "ratio", claim: `equal ${m[1]}${m[2]} ${m[3]}${m[4]}`, stated: 1, value: len(A[m[1]], A[m[2]]) / len(A[m[3]], A[m[4]]), evidence: c.evidence });
    } else if (c.pred === "circle" && (m = c.args.match(/^centre ([A-Z]) through ([A-Z])(?: ([A-Z]))?(?: ([A-Z]))?$/))) {
      const pts = [m[2], m[3], m[4]].filter(Boolean);
      if (has(m[1], ...pts) && pts.length > 1) for (const p of pts.slice(1))
        out.push({ id: c.id, kind: "ratio", claim: `circle ${m[1]}: |${m[1]}${p}| / |${m[1]}${pts[0]}|`, stated: 1, value: len(A[m[1]], A[p]) / len(A[m[1]], A[pts[0]]), evidence: c.evidence });
    } else if (c.pred === "circle" && (m = c.args.match(/^centre ([A-Z]) radius (\d+(?:\.\d+)?)$/))) {
      // `radius` is measured against the DRAWN element, not against anchors — every circle
      // element whose centre sits at the anchor is compared (concentric rings each get a
      // row), and a claim naming a centre with no circle there is a hard failure, not a
      // silent skip (`elements` here is already filtered to visible geometry)
      if (has(m[1])) {
        const hits = elements.filter((el) => el.type === "circle" && len(el.center, A[m[1]]) <= 1.5);
        if (hits.length) for (const el of hits)
          out.push({ id: c.id, kind: "ratio", claim: `circle ${m[1]}: ${el.id}.r / stated ${m[2]}`, stated: 1, value: el.r / +m[2], evidence: c.evidence });
        else out.push({ id: c.id, kind: "fail", claim: `circle ${m[1]}: no circle centred at ${m[1]}`, stated: NaN, value: NaN, evidence: c.evidence });
      }
    }
  }
  return out;
}

// ── Element coordinate extraction (for the normalize check and coverage) ─────────────────────────
function coords(el) {
  switch (el.type) {
    case "rect": return [[el.x, el.y], [el.x + el.width, el.y + el.height]];
    case "circle": case "ellipse": case "arc": return [el.center];
    case "line": case "polyline": case "polygon": case "arrow": return el.points;
    case "point": case "text": case "math": return [el.at];
    case "angleMark": return [el.vertex, el.from, el.to];
    case "tickMark": case "parallelMark": return el.on;
    case "path": {
      const out = []; const tok = el.d.match(/[MLQCAZ]|[-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?/g) ?? [];
      const AR = { M: 2, L: 2, Q: 4, C: 6, A: 7, Z: 0 }; let cmd = "M", i = 0;
      while (i < tok.length) { if (AR[tok[i]] !== undefined) { cmd = tok[i]; i++; continue; } const n = AR[cmd] ?? 0; if (!n) { i++; continue; }
        const a = tok.slice(i, i + n).map(Number); const s = cmd === "A" ? 5 : 0; for (let k = s; k < n; k += 2) out.push([a[k], a[k + 1]]); i += n; }
      return out;
    }
    default: return [];
  }
}
function labelOf(el) { return el.type === "text" ? el.value : el.type === "math" ? el.latex : el.type === "point" ? el.label : el.type === "angleMark" ? el.label : undefined; }

// ── The checks ─────────────────────────────────────────────────────────────────────────────────────
function checkDocument(doc, cs, canvasAnchors) {
  const fails = [], notes = [], advisory = [];
  const r = lib.parseVddDocument(doc);
  if (!r.ok) { fails.push(`safeParse: ${JSON.stringify(r.errors.slice(0, 5))}`); return { fails, notes, advisory, parsed: null }; }
  const d = r.value;
  notes.push(`safeParse: pass · ${d.elements.length} elements · canvas ${d.canvas.width}×${d.canvas.height}`);
  const title = (d.a11y?.title ?? "").trim(), desc = (d.a11y?.description ?? "").trim();
  if (!title || title === "Diagram" || /^question \d+$/i.test(title)) fails.push(`a11y.title missing or generic: ${JSON.stringify(title)}`);
  if (!desc) fails.push("a11y.description is empty — a screen-reader student gets nothing beyond the title");
  else if (desc.length < 85) notes.push(`⚠️ a11y.description is ${desc.length} chars — the live band is 85–542; short is a smell`);
  const byType = {};
  for (const el of d.elements) {
    byType[el.type] = (byType[el.type] ?? 0) + 1;
    const s = labelOf(el);
    if (typeof s === "string") {
      if (/[$`]/.test(s)) fails.push(`element ${el.id}: label ${JSON.stringify(s)} contains $ or a backtick — reaches the student raw`);
      // ADR 0021 (supersedes the T-S6b-6 medium condition): every piece of text DRAWN in a
      // figure is simple English on EVERY medium — one diagram_dsl per node renders on all
      // media, so a Sinhala label is refused regardless of --medium. The a11y
      // title/description are not drawn — they stay in the question's medium and are exempt.
      // Sinhala inside math.latex also fails: KaTeX cannot shape it (D7 class).
      if (/[\u0D80-\u0DFF]/.test(s)) {
        if (el.type === "math") fails.push(`element ${el.id}: math label ${JSON.stringify(s)} contains Sinhala — diagram text must be simple English (ADR 0021); KaTeX cannot shape Sinhala either`);
        else fails.push(`element ${el.id}: label ${JSON.stringify(s)} contains Sinhala — diagram text must be simple English (ADR 0021)`);
      }
    }
    // angleMark labels (both variants) DO render since the 2026-08-28 renderer fix (measured 2026-09-05 in
    // this harness: "90°" on a variant:"right" mark rendered as <text>, inside the angle, on both surfaces).
    // The render step below asserts it; nothing to fail here.
  }
  // canvas taller than ASPECT_MAX × wide renders taller than a phone screen on the 375 px plate —
  // W8: a 1×10 shaded grid came out 375×2253 and nothing flagged it. No override: re-lay it out.
  if (d.canvas.height > ASPECT_MAX * d.canvas.width)
    fails.push(`aspect: canvas ${d.canvas.width}×${d.canvas.height} is ${(d.canvas.height / d.canvas.width).toFixed(1)}× as tall as wide (> ${ASPECT_MAX}) — re-lay it out, e.g. a 1×10 grid as 5×2`);
  notes.push(`elements by type: ${Object.entries(byType).map(([k, v]) => `${v} ${k}`).join(", ")}`);
  // `--budget N` raises the smell threshold for ONE figure whose claim set justifies it in `departures:` (e.g. six small
  // printed triangles that are one question part: 34 elements is the floor, run 10 II-01 I, 2026-09-06). Never a default.
  const budget = Number(opt("--budget", String(cs?.budget ?? 32)));
  if (d.elements.length > budget) fails.push(`element budget: ${d.elements.length} > ${budget} — justify (--budget N or a 'budget: N' claim-set line + a departures: line), or route the item to S7 as skipped: (S6b §3.4)`);
  else if (d.elements.length > 32) notes.push(`element budget raised to ${budget} (${opt("--budget") ? "--budget" : "claim-set 'budget:' line"}): ${d.elements.length} elements — the claim set's departures: must say why`);
  if (byType.path) notes.push(`⚠️ ${byType.path} path element(s) — prefer polygon/arc/circle/line; a path is second-class on the card (T-S6b-9)`);
  try { advisory.push(...lib.checkDiagram(d).map((a) => `${a.id}: ${a.message}`)); } catch (e) { notes.push(`checkDiagram threw: ${e.message}`); }

  // 7. normalize consistency
  const n = lib.normalizeVdd(d);
  const deltas = [];
  d.elements.forEach((el, i) => {
    const a = coords(el), b = coords(n.elements[i]);
    if (a.length !== b.length) { fails.push(`normalize: element ${el.id} changed coordinate count`); return; }
    a.forEach((p, k) => deltas.push({ id: el.id, dx: b[k][0] - p[0], dy: b[k][1] - p[1] }));
  });
  if (deltas.length) {
    const dx = deltas[0].dx, dy = deltas[0].dy;
    const stray = deltas.filter((q) => Math.abs(q.dx - dx) > 1.01 || Math.abs(q.dy - dy) > 1.01);
    if (stray.length) fails.push(`normalize: ${[...new Set(stray.map((s) => s.id))].join(", ")} moved by a different (dx,dy) than the rest — on the reviewer's card they will sit apart (T-S6b-9)`);
    else notes.push(`normalize: every element translated by (${dx.toFixed(1)}, ${dy.toFixed(1)}) → card canvas ${n.canvas.width}×${n.canvas.height} (rounding ≤ 1 px)`);
  }

  // 8–9. claim set
  const numeric = [], coverage = [];
  if (cs) {
    const labelsInDoc = d.elements.map(labelOf).filter((s) => typeof s === "string");
    for (const g of cs.labels) {
      const k = labelsInDoc.filter((s) => s === g).length;
      if (k === 0) fails.push(`coverage: label ${JSON.stringify(g)} is in the claim set and on no element`);
      else if (k > 1) notes.push(`⚠️ coverage: label ${JSON.stringify(g)} appears on ${k} elements`);
    }
    const extra = labelsInDoc.filter((s) => !cs.labels.includes(s));
    if (extra.length) notes.push(`⚠️ labels on the drawing that the claim set does not list (declare as departures unless they are 'not to scale'): ${extra.map((s) => JSON.stringify(s)).join(" ")}`);
    const A = canvasAnchors;
    const anchored = Object.keys(A);
    const missingAnch = cs.points.filter((p) => !A[p]);
    if (missingAnch.length) fails.push(`coverage: no canvas anchor for point(s) ${missingAnch.join(" ")} — pass --anchors, set meta.anchors, or add a label-only point element`);
    const tol = 0.01;
    // the same visibility rule the label check uses — an element that paints nothing
    // covers nothing and cannot back a `radius` claim: stroke none/0-width/zero-alpha
    // (paintVisible knows `#rrggbb00`/`rgba(…,0)`), element or stroke opacity 0, a
    // label-less r:0 point, a zero-size rim. Only fillable types can paint via fill.
    const strokeVisible = (el) => {
      const width = el.stroke?.width ?? d.defaults?.strokeWidth ?? 2;
      const opacity = (el.stroke?.opacity ?? 1) * (el.opacity ?? d.defaults?.opacity ?? 1);
      const color = lib.safeColor(el.stroke?.color, lib.safeColor(d.defaults?.strokeColor, "#1f2937"));
      return width > 0 && opacity > 0 && paintVisible(color);
    };
    const fillVisible = (el) => {
      if (!el.fill) return false;
      const color = lib.safeColor(el.fill.color, lib.safeColor(d.defaults?.fillColor, "none"));
      return (el.fill.opacity ?? 1) * (el.opacity ?? d.defaults?.opacity ?? 1) > 0 &&
        paintVisible(color);
    };
    const paints = (el) => {
      if ((el.opacity ?? d.defaults?.opacity ?? 1) <= 0) return false;
      if (el.type === "point") return el.r > 0 || !!el.label;
      if (["circle", "arc"].includes(el.type)) {
        if (!(el.r > 0)) return false;
        return el.type === "circle" ? strokeVisible(el) || fillVisible(el) : strokeVisible(el);
      }
      if (el.type === "ellipse") {
        if (!(el.rx > 0 && el.ry > 0)) return false;
        return strokeVisible(el) || fillVisible(el);
      }
      if (["rect", "polygon", "path"].includes(el.type)) return strokeVisible(el) || fillVisible(el);
      if (["line", "polyline", "arrow"].includes(el.type)) return strokeVisible(el);
      return true;
    };
    const strokes = d.elements.map((el, index) => {
      if (!["line", "polyline", "polygon", "arrow"].includes(el.type)) return null;
      if (!strokeVisible(el)) return null;
      let pts = el.points.map((p) => p.map((v) => Math.round(v * 1000) / 1000));
      if (!pts.every((p) => p.every(Number.isFinite))) return null;
      if (el.rotation) {
        const center = [0, 1].map((k) => (Math.min(...el.points.map((p) => p[k])) + Math.max(...el.points.map((p) => p[k]))) / 2);
        const [cx, cy] = center.map((v) => Math.round(v * 1000) / 1000), r = Math.round(el.rotation * 1000) / 1000 * Math.PI / 180;
        pts = pts.map(([x, y]) => [cx + (x - cx) * Math.cos(r) - (y - cy) * Math.sin(r), cy + (x - cx) * Math.sin(r) + (y - cy) * Math.cos(r)]);
      }
      return { el, index, pts };
    }).filter(Boolean);
    for (const seg of cs.segments) {
      const [P, Q] = [seg[0], seg[1]];
      if (!A[P] || !A[Q]) continue;
      const directions = cs.claims.filter((c) => c.pred === "arrow").map((c) => c.args.match(/^([A-Z])\s*->\s*([A-Z])$/))
        .filter((m) => m && ((m[1] === P && m[2] === Q) || (m[1] === Q && m[2] === P)));
      const candidates = [];
      strokes.forEach(({ el, index, pts }) => {
        if (directions.length) {
          const head = el.head ?? "end", endpointTol = Math.min(1.5, len(A[P], A[Q]) * tol);
          if (el.type !== "arrow" || !["end", "both"].includes(head) || !(endpointTol > 0)) return;
          if (new Set(pts.map((p) => p.join(","))).size !== pts.length || len(pts[0], pts.at(-1)) <= 1e-6) return;
          if (!directions.every((m) =>
            (len(pts[0], A[m[1]]) <= endpointTol && len(pts.at(-1), A[m[2]]) <= endpointTol) ||
            (head === "both" && len(pts.at(-1), A[m[1]]) <= endpointTol && len(pts[0], A[m[2]]) <= endpointTol))) return;
          notes.push(`coverage: arrow ${el.id} covers ${seg} by one continuous chain, true endpoints and declared direction; paint requires browser verification`);
        } else {
          const chain = el.type === "polygon" ? [...pts, pts[0]] : pts;
          if (!chain.some((p, i) => i + 1 < chain.length && len(p, chain[i + 1]) > 1e-6 && onSegment(A[P], p, chain[i + 1], tol) && onSegment(A[Q], p, chain[i + 1], tol))) return;
        }
        candidates.push([index]);
      });
      if (directions.length) for (const shaft of strokes) {
        if (!["line", "polyline"].includes(shaft.el.type)) continue;
        const endpoints = [shaft.pts[0], shaft.pts.at(-1)], L = len(...endpoints), endpointTol = Math.min(1.5, len(A[P], A[Q]) * tol);
        if (!(L > 1e-6) || !(endpointTol > 0)) continue;
        const axis = sub(endpoints[1], endpoints[0]).map((v) => v / L);
        const along = (p) => sub(p, endpoints[0]).reduce((sum, v, k) => sum + v * axis[k], 0);
        if (!shaft.pts.every((p, i) => onSegment(p, ...endpoints, 1e-6) && (!i || along(p) - along(shaft.pts[i - 1]) > 1e-6))) continue;
        const heads = directions.map((m) => {
          const forward = len(endpoints[0], A[m[1]]) <= endpointTol && len(endpoints[1], A[m[2]]) <= endpointTol;
          const reverse = len(endpoints[1], A[m[1]]) <= endpointTol && len(endpoints[0], A[m[2]]) <= endpointTol;
          if (!forward && !reverse) return [];
          const tip = endpoints[forward ? 1 : 0], unit = axis.map((v) => forward ? v : -v);
          return strokes.filter((head) => {
            if (head.index === shaft.index || head.el.type !== "polyline" || head.pts.length !== 3 || len(head.pts[1], tip) > 1e-6) return false;
            const wings = [head.pts[0], head.pts[2]].map((p) => sub(p, tip));
            const back = wings.map((v) => v[0] * unit[0] + v[1] * unit[1]);
            const side = wings.map((v) => unit[0] * v[1] - unit[1] * v[0]);
            return back.every((v) => v < -1e-6 && v > -L) && side[0] * side[1] < -1e-6;
          }).map((head) => head.index);
        });
        const assemblies = heads.reduce((groups, options) => groups.flatMap((group) => options.map((index) => [...new Set([...group, index])])), [[shaft.index]]);
        if (assemblies.length) notes.push(`coverage: composed arrow ${shaft.el.id} covers ${seg} with a continuous straight shaft and joined chevron; all component paints require browser verification`);
        candidates.push(...assemblies);
      }
      coverage.push({ segment: seg, directed: directions.length > 0, candidates });
      if (!candidates.length) fails.push(`coverage: segment ${seg} has no eligible line/polyline/polygon/arrow through both ${P} and ${Q} with any declared arrow direction (T99 — the deleted side)`);
    }
    for (const p of anchored) {
      const hit = d.elements.some((el) => paints(el) &&
        (coords(el).some((c) => len(c, A[p]) <= 1.5) ||
         (["line", "polyline", "polygon", "arrow", "rect"].includes(el.type) &&
          (() => { const pts = edgeChain(el); for (let i = 0; i + 1 < pts.length; i++) if (onSegment(A[p], pts[i], pts[i + 1], 0.01)) return true; return false; })()) ||
         onRim(el, A[p])));
      if (!hit && cs.points.includes(p)) fails.push(`coverage: point ${p} is anchored at (${A[p]}) but no element passes within 1.5 px of it`);
    }
    if (cs.segments.length) notes.push(`coverage: segments ${cs.segments.length} checked · labels ${cs.labels.length} checked · points ${cs.points.length}`);
    // numeric — drawn canvas geometry vs BOTH the claim set's STATED value (the stem-derived
    // number) and its CLAIM-SET anchors (canvas coordinates for a constructed set)
    const claimed = evalClaims(cs, cs.anchors, d.elements.filter(paints)), drawn = evalClaims(cs, A, d.elements.filter(paints));
    // a claim with a numeric-capable pred that produced no evaluation was silently skipped — a typo'd
    // args string or a missing anchor would otherwise be invisible (the hole W15's grammar fix exposed)
    const evaluated = new Set(claimed.map((p) => p.id));
    const skipped = cs.claims.filter((c) => ["angle", "right", "ratio", "collinear", "on", "parallel", "equal", "circle"].includes(c.pred) && !evaluated.has(c.id));
    if (skipped.length) notes.push(`⚠️ numeric: ${skipped.length} claim(s) did not evaluate — check the args grammar and that every point is anchored: ${skipped.map((c) => `${c.id} ${c.pred} ${c.args}`).join("; ")}`);
    const B = { ratio: 0.02, angle: 1, residual: 0.01 };   // the single tight band — every figure is authored on the canvas
    for (const pc of claimed) {
      if (pc.kind === "fail") {
        fails.push(`numeric ${pc.id} ${pc.claim} — the claim names a circle the drawing does not draw (or draws invisibly)`);
        continue;
      }
      const dc = drawn.find((x) => x.id === pc.id && x.claim === pc.claim);
      if (!dc || !Number.isFinite(pc.value) || !Number.isFinite(dc.value)) continue;
      let diff, vs, other, ok, unit;
      if (pc.kind === "angle") {
        const ds = Math.abs(dc.value - pc.stated), dq = Math.abs(dc.value - pc.value);
        [diff, vs, other] = ds >= dq ? [ds, "stated", pc.stated] : [dq, "claimed", pc.value];
        ok = Math.max(ds, dq) <= B.angle; unit = "°";
      } else if (pc.kind === "ratio") {
        const ds = Math.abs(dc.value - pc.stated) / Math.abs(pc.stated || 1), dq = Math.abs(dc.value - pc.value) / Math.abs(pc.value || 1);
        [diff, vs, other] = ds >= dq ? [ds, "stated", pc.stated] : [dq, "claimed", pc.value];
        ok = Math.max(ds, dq) <= B.ratio; unit = "rel";
      } else { diff = dc.value; vs = "stated"; other = pc.stated; ok = diff <= B.residual; unit = "of length"; }
      numeric.push({ id: pc.id, claim: pc.claim, evidence: pc.evidence, stated: pc.stated, claimed: pc.value, drawn: dc.value, diff, vs, unit, ok });
      if (!ok) fails.push(`numeric ${pc.id} ${pc.claim}: drawn ${fmt(dc.value)} vs ${vs} ${fmt(other)} — ${pc.kind === "ratio" ? (diff * 100).toFixed(2) + "%" : fmt(diff) + unit} outside the band. If this is a DECLARED departure (exact thirds, a straightened line) write it in departures: + an 'allow: ${pc.id}' claim-set line (or re-run with --allow ${pc.id})`);
    }
    notes.push(`numeric: ${numeric.length} claim(s) compared against the stated values and claim-set anchors on the tight band (ratio ≤ ${B.ratio * 100}% · angle ≤ ${B.angle}° · residual ≤ ${B.residual * 100}%)`);
  } else notes.push("⚠️ no --claims: coverage and numeric checks skipped — S6b §5.2/§5.3 not done");
  return { fails, notes, advisory, numeric, coverage, parsed: d, normalized: n };
}
const fmt = (v) => (Math.abs(v) < 0.01 && v !== 0 ? v.toExponential(2) : (+v.toFixed(3)).toString());

// ── 10. Render both surfaces in Chromium ───────────────────────────────────────────────────────────
async function render(doc, cs, outDir, widths, headed, coverage = []) {
  const RENDER_BUNDLE = path.join(CACHE, `render-${stamp()}-${SELF_HASH}.js`);
  if (!fs.existsSync(RENDER_BUNDLE)) {
    const entry = path.join(CACHE, "render-entry.tsx");
    fs.writeFileSync(entry, `import { createRoot } from "react-dom/client";
import { DiagramRenderer } from "@/components/diagram/DiagramRenderer";
import { parseVddDocument } from "@vibhaga/shared/vdd-schema";
import { normalizeVdd } from "@/components/diagram/normalize";
const doc = (window as any).__FIGURE__;
const r = parseVddDocument(doc);
if (!r.ok) { (window as any).__INVALID__ = r.errors; }
else {
  createRoot(document.getElementById("student")!).render(<DiagramRenderer dsl={r.value} />);
  createRoot(document.getElementById("card")!).render(<DiagramRenderer dsl={normalizeVdd(r.value)} />);
}
`);
    execFileSync(ESBUILD, [entry, "--bundle", "--format=iife", "--jsx=automatic", `--outfile=${RENDER_BUNDLE}`,
      `--alias:@=${path.join(ADMIN, "src")}`, "--loader:.css=empty", "--define:process.env.NODE_ENV=\"production\"",
      "--resolve-extensions=.tsx,.ts,.js", "--log-level=error"]);
  }
  const katex = path.join(ADMIN, "node_modules/katex/dist/katex.min.css");
  const html = (w) => `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/katex.min.css">
<style>body{margin:0;font-family:Inter,system-ui,sans-serif;background:#fff}.relative{position:relative}.absolute{position:absolute}.w-full{width:100%}.h-full{height:100%}.inset-0{inset:0}.overflow-hidden{overflow:hidden}.pointer-events-none{pointer-events:none}
.box{width:${w}px;padding:12px;box-sizing:border-box;border:1px dashed #ccc;margin:8px}.cap{font:12px sans-serif;color:#666;margin:0 0 4px}</style></head>
<body><div class="box"><p class="cap">student surfaces (stored document) · ${w} px</p><div id="student"></div></div>
<div class="box"><p class="cap">Admin card (normalizeVdd) · ${w} px</p><div id="card"></div></div>
<script>window.__FIGURE__=${JSON.stringify(doc)};</script><script src="/bundle.js"></script></body></html>`;
  const files = { "/katex.min.css": fs.readFileSync(katex), "/bundle.js": fs.readFileSync(RENDER_BUNDLE) };
  const server = http.createServer((req, res) => {
    const u = req.url.split("?")[0];
    if (files[u]) { res.setHeader("content-type", u.endsWith(".css") ? "text/css" : "text/javascript"); return res.end(files[u]); }
    const m = u.match(/^\/w(\d+)\.html$/); if (m) { res.setHeader("content-type", "text/html"); return res.end(html(+m[1])); }
    res.statusCode = 404; res.end();
  });
  await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
  const port = server.address().port;
  const { chromium } = await import(pathToFileURL(path.join(ADMIN, "node_modules/playwright/index.mjs")).href);
  const browser = await chromium.launch({ headless: !headed });
  const results = []; const fails = [];
  try {
    for (const w of widths) {
      const page = await browser.newPage({ viewport: { width: w + 32, height: 1400 } });
      await page.goto(`http://127.0.0.1:${port}/w${w}.html`);
      await page.waitForFunction(() => document.querySelectorAll('[role="img"] svg').length === 2 || (window).__INVALID__, null, { timeout: 15000 }).catch(() => {});
      const read = await page.evaluate(() => {
        if (window.__INVALID__) return { invalid: window.__INVALID__ };
        const surf = (id) => {
          const host = document.getElementById(id); const img = host.querySelector('[role="img"]'); const svg = img?.querySelector("svg");
          if (!svg) return null;
          const scope = (sel) => [...svg.querySelectorAll(sel)].filter((e) => !e.closest("defs"));
          const desc = svg.querySelector("desc"); const by = img.getAttribute("aria-describedby");
          const painted = window.__FIGURE__.elements.map((el, index) => ({ el, index }));
          if (painted.some(({ el }) => typeof el.z === "number")) painted.sort((a, b) => (a.el.z ?? 0) - (b.el.z ?? 0) || a.index - b.index);
          const shapes = painted.filter(({ el }) => el.type !== "math"), groups = [...svg.children].filter((e) => e.tagName.toLowerCase() === "g");
          const canvas = document.createElement("canvas"); canvas.width = canvas.height = 1;
          const ctx = canvas.getContext("2d", { willReadFrequently: true });
          const ancestors = []; for (let e = img; e; e = e.parentElement) ancestors.unshift(e);
          const background = () => {
            ctx.globalAlpha = 1; ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, 1, 1);
            for (const e of ancestors) { ctx.fillStyle = getComputedStyle(e).backgroundColor; ctx.fillRect(0, 0, 1, 1); }
          };
          background(); const bg = [...ctx.getImageData(0, 0, 1, 1).data];
          const visibleStrokes = groups.length !== shapes.length ? [] : shapes.flatMap(({ el, index }, i) => {
            if (!["line", "polyline", "polygon", "arrow"].includes(el.type)) return [];
            const node = groups[i].querySelector("line,polyline,polygon"); if (!node) return [];
            const style = getComputedStyle(node);
            if (!(parseFloat(style.strokeWidth) > 0) || style.stroke === "none" || style.visibility !== "visible" || style.display === "none") return [];
            background(); ctx.globalAlpha = Number(style.strokeOpacity) * Number(style.opacity);
            ctx.fillStyle = "transparent"; ctx.fillStyle = style.stroke; ctx.fillRect(0, 0, 1, 1);
            return [...ctx.getImageData(0, 0, 1, 1).data].some((v, k) => k < 3 && v !== bg[k]) ? [index] : [];
          });
          // The templates' faint ruling lines — `line` elements whose id is the gv<n>/gh<n>
          // convention grid_polygon, shaded_grid and coordinate_plane all emit — are exempt
          // from the label↔stroke rule ONLY (owner ruling 2026-10-04: a point letter may sit
          // over the ruling when no clear pocket exists). The marker is structural (the id
          // prefix), never colour or width; axes, ticks, joins and dots still measure. The
          // g↔element mapping is the same positional one visibleStrokes uses, so a render
          // whose <g> count doesn't match gets NO exemption rather than a guessed one.
          const gridNodes = new Set();
          if (groups.length === shapes.length)
            shapes.forEach(({ el }, i) => {
              if (el.type === "line" && /^g[vh]\d+$/.test(String(el.id ?? "")))
                for (const n of groups[i].querySelectorAll("line,polyline,polygon,path,circle,rect,ellipse")) gridNodes.add(n);
            });
          // label metrics, in RENDERED px at this width: getBBox returns viewBox user units, so every
          // distance goes through pxPerUnit (a canvas wider than the render shrinks units into px).
          // Every <text> bbox's min distance to the canvas edge (fail < 8 px) and to any stroke
          // geometry — sampled with getPointAtLength, measured to the stroke's EDGE (centreline minus
          // half its rendered stroke-width; fail < 6 px). No exclusions besides the ruling lines
          // above; an intentional attachment is
          // declared via `allow: label:"<text>"`. An unmeasurable bbox fails CLOSED.
          const vb = svg.viewBox?.baseVal;
          const pxPerUnit = vb && vb.width ? svg.getBoundingClientRect().width / vb.width : null;
          const strokes = scope("line,polyline,polygon,path,circle,rect,ellipse").filter((s) => !gridNodes.has(s));
          const labelMetrics = scope("text").map((t) => {
            let bb; try { bb = t.getBBox(); } catch { bb = null; }
            if (!bb || !pxPerUnit) return { text: t.textContent, edge_px: null, stroke_px: null, ok: false };
            const edge = Math.min(bb.x - vb.x, bb.y - vb.y, vb.x + vb.width - (bb.x + bb.width), vb.y + vb.height - (bb.y + bb.height)) * pxPerUnit;
            let stroke = Infinity;
            for (const s of strokes) {
              let L; try { L = s.getTotalLength(); } catch { continue; }
              if (!Number.isFinite(L) || L <= 0) continue;
              const sw = (parseFloat(getComputedStyle(s).strokeWidth) || 0) * pxPerUnit;
              const n = Math.max(8, Math.min(64, Math.ceil(L / 4)));
              for (let i = 0; i <= n; i++) {
                const p = s.getPointAtLength((L * i) / n);
                const dx = Math.max(bb.x - p.x, 0, p.x - (bb.x + bb.width));
                const dy = Math.max(bb.y - p.y, 0, p.y - (bb.y + bb.height));
                stroke = Math.min(stroke, Math.hypot(dx, dy) * pxPerUnit - sw / 2);
              }
            }
            const edge_px = +edge.toFixed(1), stroke_px = stroke === Infinity ? null : +stroke.toFixed(1);
            return { text: t.textContent, edge_px, stroke_px, ok: edge_px >= 8 && (stroke_px === null || stroke_px >= 6) };
          });
          return {
            visibleStrokes,
            ariaLabel: img.getAttribute("aria-label"), descLength: desc?.textContent?.length ?? 0,
            descResolves: !!(by && document.getElementById(by)),
            viewBox: svg.getAttribute("viewBox"),
            texts: scope("text").map((t) => t.textContent),
            labelXY: scope("text").map((t) => [t.textContent, +t.getAttribute("x"), +t.getAttribute("y")]),
            labels: labelMetrics,
            shapes: { line: scope("line").length, polyline: scope("polyline").length, polygon: scope("polygon").length, circle: scope("circle").length, rect: scope("rect").length, path: scope("path").length, ellipse: scope("ellipse").length },
            markers: { start: scope("[marker-start]").length, end: scope("[marker-end]").length },
            dashed: scope("line,polyline,polygon,path,circle").filter((e) => { const v = getComputedStyle(e).strokeDasharray; return v && v !== "none"; }).length,
            fills: scope("polygon,circle,rect,path").map((e) => getComputedStyle(e).fill).filter((f) => f && f !== "none" && f !== "rgba(0, 0, 0, 0)"),
            widthPx: svg.getBoundingClientRect().width, heightPx: svg.getBoundingClientRect().height,
          };
        };
        return { student: surf("student"), card: surf("card") };
      });
      const shot = path.join(outDir, `render-${w}.png`);
      await page.screenshot({ path: shot, fullPage: true });
      results.push({ width: w, shot, ...read });
      if (read.invalid) fails.push(`render: document INVALID in the browser: ${JSON.stringify(read.invalid).slice(0, 200)}`);
      for (const s of ["student", "card"]) {
        const r = read[s]; if (!r) { fails.push(`render ${w}px: no <svg> on the ${s} surface (T-S6b-4 — 'Diagram coming soon' forever)`); continue; }
        for (const c of coverage) if (c.candidates.length && !c.candidates.some((indices) => indices.every((i) => r.visibleStrokes.includes(i))))
          fails.push(`render ${w}px ${s}: coverage segment ${c.segment} has no candidate with visible stroke paint against the canvas`);
        if (!r.ariaLabel) fails.push(`render ${w}px ${s}: role=img has no aria-label`);
        if (!r.descResolves) fails.push(`render ${w}px ${s}: aria-describedby does not resolve to the <desc>`);
        for (const l of r.labels ?? []) {
          if (l.edge_px === null) fails.push(`label ${JSON.stringify(l.text)}: render ${w}px ${s} bbox could not be measured — failing closed (a label that cannot be measured cannot be proven clear; declare 'allow: label:${JSON.stringify(l.text)}' only if intentional)`);
          else if (l.edge_px < 8) fails.push(`label ${JSON.stringify(l.text)}: render ${w}px ${s} bbox is ${l.edge_px}px from the canvas edge (< 8px — move it in or declare 'allow: label:${JSON.stringify(l.text)}')`);
          if (l.stroke_px !== null && l.stroke_px < 6) fails.push(`label ${JSON.stringify(l.text)}: render ${w}px ${s} bbox is ${l.stroke_px}px from stroke geometry (< 6px — move it clear or declare 'allow: label:${JSON.stringify(l.text)}')`);
        }
        if (cs) for (const g of cs.labels) if (!r.texts.includes(g)) fails.push(`render ${w}px ${s}: label ${JSON.stringify(g)} did not render as <text> (rendered: ${r.texts.map((t) => JSON.stringify(t)).join(" ")})`);
      }
      if (read.student && read.card && JSON.stringify(read.student.texts) !== JSON.stringify(read.card.texts)) fails.push(`render ${w}px: the two surfaces rendered different label sets`);
      await page.close();
    }
  } finally { await browser.close(); server.close(); }
  return { results, fails };
}

// ── Main ───────────────────────────────────────────────────────────────────────────────────────────
async function main() {
  if (flag("--self-test")) return selfTest();
  const file = args.find((a) => !a.startsWith("--") && a.endsWith(".json") && !["--anchors", "--claims", "--out", "--widths", "--allow", "--admin"].includes(args[args.indexOf(a) - 1]));
  if (!file) die("usage: vdd-check.mjs figure.json [--claims c.txt] [--anchors a.json] [--out dir] [--widths 320,375,768] [--no-render] [--headed] [--allow K5,\"label:text\"] [--admin path] [--json]");
  const doc = JSON.parse(fs.readFileSync(file, "utf8"));
  const cs = opt("--claims") ? parseClaimSet(fs.readFileSync(opt("--claims"), "utf8")) : null;
  let anchors = {};
  const anchorsFile = opt("--anchors") ?? (fs.existsSync(file.replace(/\.json$/, ".anchors.json")) ? file.replace(/\.json$/, ".anchors.json") : null);
  if (anchorsFile) anchors = JSON.parse(fs.readFileSync(anchorsFile, "utf8"));
  else if (doc.meta?.anchors) anchors = doc.meta.anchors;
  for (const el of doc.elements ?? []) if (el.type === "point" && /^[A-Z]$/.test(el.label ?? "") && !anchors[el.label]) anchors[el.label] = el.at;
  const allow = [...(opt("--allow", "") || "").split(",").filter(Boolean), ...(cs?.allow ?? [])];
  const outDir = opt("--out", path.join(os.tmpdir(), "vdd-check-out", path.basename(file, ".json")));
  fs.mkdirSync(outDir, { recursive: true });
  const rep = checkDocument(doc, cs, anchors);
  let renderRep = null;
  if (!flag("--no-render") && rep.parsed) {
    renderRep = await render(doc, cs, outDir, (opt("--widths", "320,375,768")).split(",").map(Number), flag("--headed"), rep.coverage);
    rep.fails.push(...renderRep.fails);
  } else if (rep.coverage?.some((c) => c.directed && c.candidates.length)) {
    rep.notes.push("WARN: --no-render skips directed-arrow paint verification — a head styled invisible would pass here; run `vdd-check` WITHOUT --no-render once per arrow figure before publishing");
  }
  // declared departures: `allow: K5` downgrades that numeric finding; `allow: label:"<text>"`
  // downgrades edge/stroke findings on that label (each must appear in the claim set's departures:)
  rep.fails = rep.fails.filter((f) => !allow.some((id) => f.startsWith(`numeric ${id} `) ||
    (id.startsWith("label:") && f.startsWith(`label ${JSON.stringify(id.slice(6))}:`))));
  if (allow.length) rep.notes.push(`--allow: findings on ${allow.join(", ")} downgraded to declared departures (they must appear in the claim set's departures:)`);
  // print
  const H = path.basename(file);
  console.log(`\n== vdd-check ${H}`);
  for (const n of rep.notes) console.log(`   ${n}`);
  if (rep.numeric?.length) {
    console.log("   numeric (drawn vs stated & claim-set anchors):");
    for (const q of rep.numeric) console.log(`     ${q.ok ? "ok  " : "FAIL"} ${q.id.padEnd(4)} ${q.claim.padEnd(34)} stated ${fmt(q.stated).padStart(9)}  drawn ${fmt(q.drawn).padStart(9)}  Δ ${q.unit === "rel" ? (q.diff * 100).toFixed(2) + "%" : fmt(q.diff) + (q.unit === "°" ? "°" : "")}  [${q.evidence}]`);
  }
  if (rep.advisory?.length) { console.log("   checkDiagram advisory (never blocking — explain via the claim set's scale:):"); for (const a of rep.advisory) console.log(`     · ${a}`); }
  else if (rep.parsed) console.log("   checkDiagram advisory: []");
  if (renderRep) for (const r of renderRep.results) {
    console.log(`   render ${r.width}px → ${r.shot}`);
    for (const s of ["student", "card"]) { const x = r[s]; if (!x) continue;
      console.log(`     ${s.padEnd(7)} viewBox ${x.viewBox} · ${x.widthPx.toFixed(0)}×${x.heightPx.toFixed(0)}px · texts ${JSON.stringify(x.texts)} · shapes ${JSON.stringify(x.shapes)} · markers ${x.markers.start}/${x.markers.end} · dashed ${x.dashed} · fills ${JSON.stringify(x.fills)} · desc ${x.descLength} chars ${x.descResolves ? "resolves" : "DOES NOT RESOLVE"}`); }
  }
  if (rep.fails.length) { console.log(`\n   ⛔ ${rep.fails.length} FAILURE(S):`); for (const f of rep.fails) console.log(`     ✗ ${f}`); }
  else console.log("\n   ✅ no failures — now LOOK at the screenshots (S6b §4.2: a label on a stroke, a label outside its angle, a clipped edge are only visible by sight)");
  // one-line label verdict per figure + worst-case label metrics for --json
  const labelRows = [];
  if (renderRep) {
    const byText = new Map();
    for (const r of renderRep.results) for (const s of ["student", "card"]) for (const l of r[s]?.labels ?? []) {
      const cur = byText.get(l.text) ?? { text: l.text, edge_px: Infinity, stroke_px: null, ok: true };
      cur.edge_px = Math.min(cur.edge_px, l.edge_px ?? Infinity);
      if (l.stroke_px !== null) cur.stroke_px = cur.stroke_px === null ? l.stroke_px : Math.min(cur.stroke_px, l.stroke_px);
      cur.ok = cur.ok && l.ok;
      byText.set(l.text, cur);
    }
    labelRows.push(...byText.values());
    if (labelRows.length) {
      const minEdge = Math.min(...labelRows.map((l) => l.edge_px)), minStroke = Math.min(...labelRows.map((l) => l.stroke_px ?? Infinity));
      const bad = labelRows.filter((l) => !l.ok).length;
      console.log(`   labels: ${labelRows.length} <text> checked · min edge ${minEdge === Infinity ? "—" : minEdge + "px"} · min stroke ${minStroke === Infinity ? "—" : minStroke + "px"} — ${bad ? `${bad} FAIL` : "ok"}`);
    }
  }
  if (flag("--json")) fs.writeFileSync(path.join(outDir, "report.json"), JSON.stringify({ file, fails: rep.fails, notes: rep.notes, advisory: rep.advisory, numeric: rep.numeric, labels: labelRows, render: renderRep?.results ?? null }, null, 1));
  process.exit(rep.fails.length ? 1 : 0);
}

// ── Self-test: a check nobody has seen fail is a claim (T13) ──────────────────────────────────────
async function selfTest() {
  const tri = {
    schema: "vibhaga.diagram", schemaVersion: 1, canvas: { width: 300, height: 260 }, defaults: { strokeColor: "#1f2937", strokeWidth: 2, fontSize: 18 },
    a11y: { title: "Right-angled triangle ABC with the right angle at B", description: "A triangle with vertices A (top), B (bottom left) and C (bottom right); the angle at B is a right angle, marked with a square. AB is vertical, BC is horizontal, AC is the hypotenuse." },
    elements: [
      { id: "AB", type: "line", points: [[60, 40], [60, 220]] }, { id: "BC", type: "line", points: [[60, 220], [240, 220]] }, { id: "AC", type: "line", points: [[60, 40], [240, 220]] },
      { id: "rB", type: "angleMark", vertex: [60, 220], from: [60, 40], to: [240, 220], r: 16, variant: "right" },
      { id: "pA", type: "point", at: [60, 40], r: 0, label: "A", labelOffset: [-14, 0] }, { id: "pB", type: "point", at: [60, 220], r: 0, label: "B", labelOffset: [-14, 14] }, { id: "pC", type: "point", at: [240, 220], r: 0, label: "C", labelOffset: [14, 14] },
    ],
  };
  const claims = `figure: t\nchannel: constructed\nstem: A right-angled triangle ABC has the right angle at B, with AB equal to BC.\nask: x\nlabels: A B C\npoints: A B C\nsegments: AB BC AC\nanchors:\n  A 100 100\n  B 100 190\n  C 190 190\nclaims:\n  K1 right A B C | stated |\n  K2 ratio len BC / len AB = 1.000 | stated |\n  K3 angle B A C = 45.00 | stated |\nscale: to scale\nload-bearing:\n  x -> K1\nunreadable: (none)\nambiguous: (none)\ndepartures: (none)\n`;
  const cs = parseClaimSet(claims);
  const anchors = { A: [60, 40], B: [60, 220], C: [240, 220] };
  let ok = true; const t = (name, cond) => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}`); if (!cond) ok = false; };
  const good = checkDocument(tri, cs, anchors);
  t("correct triangle: 0 failures", good.fails.length === 0);
  t("numeric: 3 claims compared", good.numeric.length === 3);
  const noAB = { ...tri, elements: tri.elements.filter((e) => e.id !== "AB") };
  t("deleted side AB → coverage fails (T99)", checkDocument(noAB, cs, anchors).fails.some((f) => f.includes("segment AB")));
  const skew = { ...tri, elements: tri.elements.map((e) => (e.id === "AC" || e.id === "AB" ? { ...e, points: e.points.map((p) => (p[0] === 60 && p[1] === 40 ? [90, 40] : p)) } : e)) };
  t("apex moved 30 px → numeric fails", checkDocument(skew, cs, { ...anchors, A: [90, 40] }).fails.some((f) => f.startsWith("numeric")));
  const noTitle = { ...tri, a11y: { title: "Diagram", description: tri.a11y.description } };
  t("generic title → fails", checkDocument(noTitle, cs, anchors).fails.some((f) => f.includes("a11y.title")));
  const dollar = { ...tri, elements: [...tri.elements, { id: "t", type: "text", at: [150, 130], value: "$x$" }] };
  t("$ in a label → fails", checkDocument(dollar, cs, anchors).fails.some((f) => f.includes("$ or a backtick")));
  const bad = { ...tri, elements: [...tri.elements, { id: "p2", type: "polygon", points: [[0, 0], [1, 1]] }] };
  t("2-point polygon → safeParse fails", checkDocument(bad, cs, anchors).fails.some((f) => f.startsWith("safeParse")));
  const missingLabel = { ...tri, elements: tri.elements.filter((e) => e.id !== "pC") };
  t("label C dropped → coverage fails", checkDocument(missingLabel, cs, { ...anchors }).fails.some((f) => f.includes('label "C"')));
  const tall = { ...tri, canvas: { width: 66, height: 426 } };
  t("canvas 66×426 (h/w 6.5) → aspect fails", checkDocument(tall, cs, anchors).fails.some((f) => f.startsWith("aspect:")));
  const wide = { ...tri, canvas: { width: 426, height: 213 } };
  t("canvas 426×213 (h/w 0.5) → no aspect fail", !checkDocument(wide, cs, anchors).fails.some((f) => f.startsWith("aspect:")));
  // an anchor ON a drawn outline is covered without an r:0 marker — circle rim, ellipse rim,
  // rect edge, arc inside its sweep (the W10c shape_row letter anchors sit on outlines)
  const ringDoc = { ...tri, elements: [{ id: "c1", type: "circle", center: [150, 130], r: 80 }] };
  const onePt = (x, y, extra) => parseClaimSet(`points: A\nanchors:\n A ${x} ${y}\nclaims:\n${extra ?? ""}`);
  const noCover = (fails) => fails.some((f) => f.startsWith("coverage: point A"));
  t("anchor on a circle rim counts as covered", !noCover(checkDocument(ringDoc, onePt(230, 130), { A: [230, 130] }).fails));
  t("anchor 6 px off the rim is uncovered", noCover(checkDocument(ringDoc, onePt(236, 130), { A: [236, 130] }).fails));
  const ellDoc = { ...tri, elements: [{ id: "e1", type: "ellipse", center: [150, 130], rx: 60, ry: 30 }] };
  t("anchor on an ellipse rim counts as covered", !noCover(checkDocument(ellDoc, onePt(150, 160), { A: [150, 160] }).fails));
  const rectDoc = { ...tri, elements: [{ id: "r1", type: "rect", x: 100, y: 100, width: 80, height: 40 }] };
  t("anchor on a rect edge counts as covered", !noCover(checkDocument(rectDoc, onePt(140, 140), { A: [140, 140] }).fails));
  const arcDoc = { ...tri, elements: [{ id: "a1", type: "arc", center: [150, 130], r: 80, start: -180, end: 0 }] };
  t("anchor on an arc inside its sweep counts as covered", !noCover(checkDocument(arcDoc, onePt(150, 50), { A: [150, 50] }).fails));
  t("anchor on the arc's circle but outside its sweep is uncovered", noCover(checkDocument(arcDoc, onePt(150, 210), { A: [150, 210] }).fails));
  // `circle centre X radius r` is evaluated against the drawn element with that centre
  const radCs = onePt(150, 130, " K1 circle centre A radius 80 | inferred |\n");
  const radOk = checkDocument(ringDoc, radCs, { A: [150, 130] });
  t("radius claim evaluates when drawn r matches", radOk.numeric.length === 1 && radOk.numeric[0].ok && !radOk.fails.some((f) => f.startsWith("numeric")));
  const radBad = checkDocument({ ...tri, elements: [{ id: "c1", type: "circle", center: [150, 130], r: 90 }] }, radCs, { A: [150, 130] });
  t("radius claim fails when drawn r disagrees", radBad.fails.some((f) => f.startsWith("numeric K1")));
  // invisible geometry neither covers an anchor nor backs a radius claim
  const ghostCircle = { ...tri, elements: [{ id: "c1", type: "circle", center: [150, 130], r: 80, stroke: { width: 0 } }] };
  t("anchor on an invisible circle's rim is uncovered", noCover(checkDocument(ghostCircle, onePt(230, 130), { A: [230, 130] }).fails));
  const ghostDot = { ...tri, elements: [{ id: "p1", type: "point", at: [230, 130], r: 0 }] };
  t("a label-less r:0 point covers nothing", noCover(checkDocument(ghostDot, onePt(230, 130), { A: [230, 130] }).fails));
  const noCirc = checkDocument({ ...tri, elements: [] }, radCs, { A: [150, 130] });
  t("radius claim with no circle at the centre is a FAIL", noCirc.fails.some((f) => f.includes("no circle centred at A")));
  const ghostRad = checkDocument(ghostCircle, radCs, { A: [150, 130] });
  t("radius claim against an invisible circle is a FAIL", ghostRad.fails.some((f) => f.includes("no circle centred at A")));
  // zero-alpha colours (#rrggbbaa, rgba(…,0)) neither cover nor back a radius claim
  const alphaHex = { ...tri, elements: [{ id: "c1", type: "circle", center: [150, 130], r: 80, stroke: { color: "#00000000" } }] };
  t("anchor on a zero-alpha-hex circle rim is uncovered", noCover(checkDocument(alphaHex, onePt(230, 130), { A: [230, 130] }).fails));
  t("zero-alpha-hex circle cannot back a radius claim",
    checkDocument(alphaHex, radCs, { A: [150, 130] }).fails.some((f) => f.includes("no circle centred at A")));
  const alphaRgba = { ...tri, elements: [{ id: "c1", type: "circle", center: [150, 130], r: 80, stroke: { color: "rgba(0,0,0,0)" } }] };
  t("rgba(…,0) stroke neither covers nor backs a radius claim",
    noCover(checkDocument(alphaRgba, onePt(230, 130), { A: [230, 130] }).fails) &&
    checkDocument(alphaRgba, radCs, { A: [150, 130] }).fails.some((f) => f.includes("no circle centred at A")));
  // normalize consistency has no reachable failure with the current Admin (every type translates) — assert the pass
  t("normalize: uniform translation on the correct triangle", good.notes.some((n) => n.startsWith("normalize: every element")));
  const leader = { id: "PQ", type: "arrow", head: "end", points: [[60, 40], [100, 20], [140, 70], [180, 100]] };
  const leaderAnchors = { P: [60, 40], Q: [180, 100] };
  const leaderClaims = parseClaimSet("points: P Q\nsegments: PQ\nanchors:\n P 60 40\n Q 180 100\nclaims:\n K1 arrow P -> Q | printed | curved annotation leader\n");
  const leaderCheck = (elements, claims = leaderClaims, A = leaderAnchors, defaults = tri.defaults) => checkDocument({ ...tri, defaults, elements }, claims, A);
  const rejected = (elements, claims = leaderClaims, defaults = tri.defaults) => {
    const r = leaderCheck(elements, claims, leaderAnchors, defaults);
    // every failure must be a coverage failure and the segment must be among them —
    // an invisible arrow now uncovers its OWN endpoints too, so don't count heads
    return !!r.parsed && r.fails.every((f) => f.startsWith("coverage:")) &&
      r.fails.some((f) => f.startsWith("coverage: segment PQ"));
  };
  for (const head of ["end", "both", undefined]) t(`continuous curved arrow head ${head ?? "default end"}: coverage passes`, leaderCheck([{ ...leader, head }]).fails.length === 0);
  t("reversed chain with both heads preserves declared direction", leaderCheck([{ ...leader, head: "both", points: [...leader.points].reverse() }]).fails.length === 0);
  t("reversed declaration matches reversed end-headed chain", leaderCheck([{ ...leader, points: [...leader.points].reverse() }], { ...leaderClaims, claims: [{ id: "K1", pred: "arrow", args: "Q -> P" }] }).fails.length === 0);
  const mutations = [
    ["wrong endpoint", { points: [[40, 80], ...leader.points] }], ["plain polyline", { type: "polyline" }], ["polygon", { type: "polygon" }],
    ["missing head", { head: "none" }], ["wrong direction", { points: [...leader.points].reverse() }],
    ["repeated point", { points: [leader.points[0], ...leader.points] }], ["closed chain", { points: [...leader.points, leader.points[0]] }],
    ["rounded-away edge", { points: [leader.points[0], [60.0001, 40], ...leader.points.slice(1)] }],
    ["zero width", { stroke: { width: 0 } }], ["zero stroke opacity", { stroke: { opacity: 0 } }], ["zero element opacity", { opacity: 0 }],
    ["transparent", { stroke: { color: "transparent" } }], ["none paint", { stroke: { color: "none" } }], ["rotated away", { rotation: 90 }],
  ];
  for (const [name, change] of mutations) t(`${name} helper fails coverage, not schema`, rejected([{ ...leader, ...change }]));
  t("disconnected pieces cannot cover a leader", rejected([{ ...leader, id: "part1", points: leader.points.slice(0, 2) }, { ...leader, id: "part2", points: leader.points.slice(2) }]));
  for (const defaults of [{ opacity: 0 }, { strokeWidth: 0 }, { strokeColor: "transparent" }])
    t(`invisible defaults ${JSON.stringify(defaults)} fail coverage`, rejected([leader], leaderClaims, defaults));
  t("element opacity overrides zero default", leaderCheck([{ ...leader, opacity: 1 }], leaderClaims, leaderAnchors, { opacity: 0 }).fails.length === 0);
  for (const change of [{ head: "start" }, { points: [leader.points[0], [NaN, 20], leader.points.at(-1)] }])
    t("dedicated illegal head/non-finite point schema rejection", leaderCheck([{ ...leader, ...change }]).fails.some((f) => f.startsWith("safeParse")));
  const chord = [leader.points[0], leader.points.at(-1)];
  t("straight end-headed arrow covers a directed segment", leaderCheck([{ ...leader, points: chord }]).fails.length === 0);
  t("straight chord cannot bypass wrong head direction", rejected([{ ...leader, points: [...chord].reverse() }]));
  t("straight sub-edge cannot bypass wrong true endpoints", rejected([{ ...leader, points: [[40, 30], ...chord] }]));
  t("plain straight line cannot substitute for declared arrow", rejected([{ ...leader, type: "line", points: chord }]));
  t("undeclared curved arrow cannot replace straight geometry", rejected([leader], { ...leaderClaims, claims: [] }));
  t("ordinary straight chord coverage remains valid", leaderCheck([{ ...leader, type: "line", points: chord }], { ...leaderClaims, claims: [] }).fails.length === 0);
  const leaderNumeric = { ...leaderClaims, anchors: { ...leaderAnchors, R: [60, 140] }, claims: [...leaderClaims.claims, { id: "K2", pred: "ratio", args: "len PQ / len PR = 1.342", evidence: "measured" }] };
  const numericGood = leaderCheck([leader], leaderNumeric, leaderNumeric.anchors);
  t("numeric length remains endpoint chord, not chain length", numericGood.fails.length === 0 && Math.abs(numericGood.numeric[0].drawn - len(...chord) / 100) < 1e-12);
  t("curved coverage does not bypass numeric disagreement", leaderCheck([leader], leaderNumeric, { ...leaderAnchors, R: [60, 240] }).fails.some((f) => f.startsWith("numeric K2")));
  const paints = ["#36c", "red", "rgb(30 90 180)", "hsl(220 70% 40%)", "color-mix(in srgb, red, blue)", "#36cf", "#3366cc80", "currentColor", "lab(40% 20 -40)", "none", "transparent", "#0000", "#12345600", "rgba(0, 0, 0, 0)", "white"];
  for (const color of [...paints.slice(0, 9), "white"]) t(`legal ${color} leader/default paint reaches browser verification`,
    leaderCheck([{ ...leader, stroke: { color } }]).fails.length === 0 && leaderCheck([leader], leaderClaims, leaderAnchors, { strokeColor: color }).fails.length === 0);
  const paintDoc = { ...tri, elements: paints.map((color, i) => ({ ...leader, id: `paint-${i}`, z: -i, stroke: { color } })) };
  t("all browser paint fixtures pass real schema and document checks", checkDocument(paintDoc, null, {}).fails.length === 0);
  const paintCoverage = paints.map((_, i) => ({ segment: `paint-${i}`, candidates: [[i]] }));
  const shaft = { id: "shaft", type: "line", points: chord }, chevron = { id: "chevron", type: "polyline", points: [[160, 100], chord[1], [170, 80]] };
  const assembly = [shaft, chevron];
  const assembled = leaderCheck(assembly);
  t("joined shaft and chevron form a two-element coverage candidate", assembled.fails.length === 0 && JSON.stringify(assembled.coverage[0].candidates) === "[[0,1]]");
  t("primitive arrow remains a one-element candidate", JSON.stringify(leaderCheck([leader]).coverage[0].candidates) === "[[0]]");
  t("shaft point order does not impose arrow direction", leaderCheck([{ ...shaft, points: [...chord].reverse() }, chevron]).fails.length === 0);
  t("continuous collinear polyline shaft is supported", leaderCheck([{ ...shaft, type: "polyline", points: [chord[0], [120, 70], chord[1]] }, chevron]).fails.length === 0);
  const badAssemblies = [
    ["missing head", [shaft]], ["disconnected head", [shaft, { ...chevron, points: chevron.points.map(([x, y]) => [x + 0.1, y]) }]],
    ["reversed head", [shaft, { ...chevron, points: [[200, 100], chord[1], [190, 120]] }]],
    ["one wing", [shaft, { ...chevron, points: chevron.points.slice(0, 2) }]],
    ["degenerate V", [shaft, { ...chevron, points: [chord[1], chord[1], chevron.points[2]] }]],
    ["wings on same side", [shaft, { ...chevron, points: [[160, 100], chord[1], [170, 100]] }]],
    ["collinear V", [shaft, { ...chevron, points: [[160, 90], chord[1], [140, 80]] }]],
    ["wrong tail", [{ ...shaft, points: [[50, 35], chord[1]] }, chevron]],
    ["head at tail", [shaft, { ...chevron, points: [[80, 40], chord[0], [70, 60]] }]],
    ["curved polyline shaft", [{ ...shaft, type: "polyline", points: leader.points }, chevron]],
    ["backtracking shaft", [{ ...shaft, type: "polyline", points: [chord[0], [120, 70], [100, 60], chord[1]] }, chevron]],
    ["disconnected shafts", [{ ...shaft, points: [chord[0], [100, 60]] }, { ...shaft, id: "other", points: [[120, 70], chord[1]] }, chevron]],
    ["wrong-direction arrow cannot become assembly shaft", [{ ...leader, points: [...chord].reverse() }, chevron]],
  ];
  for (const [name, elements] of badAssemblies) t(`assembly ${name} fails coverage, not schema`, rejected(elements));
  const noShaft = leaderCheck([chevron]);
  t("missing shaft fails directed coverage", !!noShaft.parsed && noShaft.fails.some((f) => f.startsWith("coverage: segment PQ")));
  for (const i of [0, 1]) for (const change of [{ opacity: 0 }, { stroke: { opacity: 0 } }, { stroke: { width: 0 } }, { stroke: { color: "transparent" } }])
    t(`assembly component ${i} ${JSON.stringify(change)} cannot be invisible`, rejected(assembly.map((el, k) => k === i ? { ...el, ...change } : el)));
  const paintOut = fs.mkdtempSync(path.join(CACHE, "leader-tests-"));
  try {
    for (const hidden of [[], [0], [1], [0, 1]]) {
      const elements = assembly.map((el, i) => ({ ...el, stroke: { color: hidden.includes(i) ? "#12345600" : "rebeccapurple" } }));
      const rep = leaderCheck(elements), r = await render({ ...tri, elements }, leaderClaims, paintOut, [320], false, rep.coverage);
      t(`Chromium assembly requires both paints; hidden components ${JSON.stringify(hidden)}`,
        // the document check itself now sees zero-alpha paint — it fails coverage before Chromium runs,
        // so no candidates reach the render and Chromium adds nothing on top
        (hidden.length
          ? rep.fails.every((f) => f.startsWith("coverage:")) && rep.fails.some((f) => f.includes("segment PQ")) && r.fails.length === 0
          : rep.fails.length === 0 && r.fails.length === 0));
    }
    for (const background of ["white", "#111"]) {
      const r = await render({ ...paintDoc, canvas: { ...tri.canvas, background } }, null, paintOut, [320], false, paintCoverage);
      for (const [i, color] of paints.entries()) {
        const visible = i < 9 || (color === "white" && background !== "white");
        t(`Chromium ${color} on ${background}: ${visible ? "visible" : "invisible"}`, ["student", "card"].every((s) => r.results[0][s]?.visibleStrokes.includes(i) === visible) &&
          r.fails.filter((f) => f.endsWith(`coverage segment paint-${i} has no candidate with visible stroke paint against the canvas`)).length === (visible ? 0 : 2));
      }
    }
  } finally { fs.rmSync(paintOut, { recursive: true, force: true }); }
  // W15 — `on X PQ` grammar (run 13 wrote `K1 on E AB`; the old `X on PQ` spelling stays accepted)
  const onCs = parseClaimSet("anchors:\n  A 60 40\n  C 240 220\n  D 150 130\n  E 150 130\nclaims:\n  K8 on D on AC | measured |\n  K9 on E AC | measured |");
  const onDrawn = { A: [60, 40], C: [240, 220], D: [150, 130], E: [150, 130] };
  const onRep = checkDocument(tri, onCs, onDrawn);
  t("`K9 on E AC` evaluates (run-13 spelling) alongside `K8 on D on AC`",
    onRep.fails.length === 0 && onRep.numeric.filter((n) => n.claim.endsWith("on AC")).length === 2);
  const offRep = checkDocument(tri, onCs, { ...onDrawn, E: [170, 130] });
  t("a drawn point off the segment fails `on X PQ` numerically", offRep.fails.some((f) => f.startsWith("numeric K9")));
  // W15 — --no-render degrades directed-arrow paint verification to WARN + exit 0 (end-to-end via the CLI)
  const nrDir = fs.mkdtempSync(path.join(CACHE, "norender-"));
  try {
    fs.writeFileSync(path.join(nrDir, "leader.json"), JSON.stringify({ ...tri, elements: [{ id: "PQ", type: "arrow", head: "end", points: chord }] }));
    fs.writeFileSync(path.join(nrDir, "leader.anchors.json"), JSON.stringify({ P: chord[0], Q: chord.at(-1) }));
    fs.writeFileSync(path.join(nrDir, "leader-claims.txt"), "segments: PQ\nanchors:\n  P 60 40\n  Q 180 100\nclaims:\n  K1 arrow P -> Q | printed |");
    let rc = 0, out = "";
    try {
      out = execFileSync(process.execPath, [fileURLToPath(import.meta.url), path.join(nrDir, "leader.json"),
        "--claims", path.join(nrDir, "leader-claims.txt"), "--no-render"], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    } catch (e) { rc = e.status ?? 1; out = String(e.stdout ?? "") + String(e.stderr ?? ""); }
    t("--no-render on a directed-arrow figure exits 0 with the paint WARN",
      rc === 0 && /WARN: --no-render skips directed-arrow paint/.test(out) && !/requires the browser check/.test(out));
  } finally { fs.rmSync(nrDir, { recursive: true, force: true }); }
  // label metrics, measured in the same real render (Chromium): bbox-to-edge < 8 px fails,
  // bbox-to-stroke < 6 px fails, a clear label passes — and `allow: label:"<text>"` is the
  // declared-departure escape through the CLI allow filter.
  const labOut = fs.mkdtempSync(path.join(CACHE, "labels-"));
  try {
    const linesOnly = tri.elements.filter((e) => ["AB", "BC", "AC"].includes(e.id));
    const labDoc = { ...tri, elements: [...linesOnly,
      { id: "edgeT", type: "text", at: [268, 120], value: "edge" },
      { id: "onT", type: "text", at: [60, 120], value: "on" },
      { id: "clearT", type: "text", at: [150, 70], value: "clear" },
    ] };
    const r = await render(labDoc, null, labOut, [320], false, []);
    t("label overflowing the canvas edge fails in the real render (student surface — normalizeVdd re-frames the card)",
      r.fails.filter((f) => f.includes('label "edge"') && f.includes("student") && f.includes("canvas edge")).length === 1);
    t("label on a stroke fails in the real render",
      r.fails.filter((f) => f.includes('label "on"') && f.includes("stroke geometry")).length === 2);
    t("clear label produces no label finding", !r.fails.some((f) => f.includes('label "clear"')));
    const clear = r.results[0].student.labels.find((l) => l.text === "clear");
    t("label metrics emitted per <text> with {text, edge_px, stroke_px, ok}",
      !!clear && clear.ok && clear.edge_px >= 8 && clear.stroke_px >= 6);
    // F3: the rule is RENDERED px at each width — a canvas far wider than the render shrinks user
    // units into px. 20 units is comfortably ≥ 8 on the canvas but ≈ 6 px at 320, so it must fail.
    const wideDoc = { ...tri, canvas: { ...tri.canvas, width: 1000 }, elements: [...linesOnly,
      { id: "farT", type: "text", at: [960, 130], value: "far" },
    ] };
    const rw = await render(wideDoc, null, labOut, [320], false, []);
    const far = rw.results[0].student.labels.find((l) => l.text === "far");
    t("label ≥8 units from edge but <8 rendered px at 320 fails (unit→px conversion)",
      rw.fails.some((f) => f.includes('label "far"') && f.includes("student") && f.includes("canvas edge")) &&
      !!far && !far.ok && far.edge_px < 8);
    const cli = fs.mkdtempSync(path.join(CACHE, "label-cli-"));
    try {
      fs.writeFileSync(path.join(cli, "lab.json"), JSON.stringify(labDoc));
      fs.writeFileSync(path.join(cli, "lab-claims.txt"), 'channel: constructed\nstem: synthetic label-clearance fixture\nlabels: "edge" "on" "clear"\nallow: "label:edge" "label:on"\n');
      const run = (argv) => { try { return { rc: 0, out: execFileSync(process.execPath, argv, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }) }; }
        catch (e) { return { rc: e.status ?? 1, out: String(e.stdout ?? "") + String(e.stderr ?? "") }; } };
      const cliArgv = (claims) => [fileURLToPath(import.meta.url), path.join(cli, "lab.json"), "--claims", path.join(cli, claims), "--widths", "320"];
      let got = run(cliArgv("lab-claims.txt"));
      t("`allow: label:<text>` downgrades declared label departures to exit 0",
        got.rc === 0 && !got.out.includes('label "edge"') && !got.out.includes('label "on"') && got.out.includes("labels:"));
      fs.writeFileSync(path.join(cli, "lab-strict.txt"), 'channel: constructed\nstem: synthetic label-clearance fixture\nlabels: "edge" "on" "clear"\n');
      got = run(cliArgv("lab-strict.txt"));
      t("undeclared edge/stroke labels fail the run",
        got.rc === 1 && got.out.includes('label "edge"') && got.out.includes('label "on"'));
    } finally { fs.rmSync(cli, { recursive: true, force: true }); }
  } finally { fs.rmSync(labOut, { recursive: true, force: true }); }
  console.log(ok ? "\nSELF-TEST PASS" : "\nSELF-TEST FAIL");
  process.exit(ok ? 0 : 1);
}

export { angleAt, offLine, parallelResidual, onSegment, parseClaimSet, evalClaims };
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
