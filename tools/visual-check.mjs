#!/usr/bin/env node
/**
 * visual-check.mjs — batch-render VDD figures through the REAL Admin `/diagtest` host page
 * (real globals.css, real next/font Inter + Noto Sans Sinhala, real `html[data-theme]` theming)
 * and measure every label against the geometry in RENDERED pixels.
 *
 *     node tools/visual-check.mjs <inputs…> [--out DIR] [--widths 320,375,768] [--themes light,dark]
 *                                          [--base-url URL] [--claims-dir DIR] [--headed]
 *                                          [--admin PATH]
 *     node tools/visual-check.mjs --session <playground-session-id> [--out DIR] [--base-url URL]
 *                                          [--staged FILE] [--claims-dir DIR] [--admin PATH]
 *                                          (always headed — signs in, then out; PNGs land in
 *                                          <out>/session/ and the run's verdict/exit/screenshot
 *                                          list in <out>/report.json — W12 A7)
 *     node tools/visual-check.mjs --self-test
 *
 * `--admin PATH` is the Vibhaga-Admin CHECKOUT (`--admin` flag > `VIBHAGA_ADMIN` env >
 * `<plugin>/../Vibhaga-Admin`) — the same convention as vdd-check.mjs. ⚠️ It is NOT the session
 * flag the plan once called `--admin <session>`: playground sessions are selected with `--session`.
 *
 * Inputs (any mix, positional):
 *   · a staged doc JSON (the tools/build-staged.py shape — tests/fixtures/staged-golden.json):
 *     every non-null `diagram_dsl` at question / sub-question (both depths) / answer / sub-answer
 *     level becomes a figure, id `Q<n>`, `Q<n>.<label>`, `Q<n>.<label>.<label2>`, `Q<n>.ans<k>`,
 *     `Q<n>.<label>.ans<k>`;
 *   · a single VDD `.json` (schema `vibhaga.diagram`), id = basename;
 *   · a directory → every VDD `.json` in it (`*.anchors.json` and non-VDD JSON skipped).
 * A figure's claim set (optional): sibling `<base>.claims.txt` or `<base>-claims.txt`, else
 * `<claims-dir>/<id>.claims.txt` or `<claims-dir>/<id>-claims.txt` via `--claims-dir` (the second
 * name is what vdd_templates.py emits: figure id `Q3` → `Q3-claims.txt`). In `--session` mode
 * `--staged FILE` reads the run's staged doc from disk (run-gates ship has already proven
 * `doc get` == staged.json, so the local file IS the server doc — nothing is scraped from the
 * page) and pairs each rendered figure with the doc's figures in document order per question;
 * `--claims-dir` then resolves each pair's claim set so `allow:`/departures apply exactly as in
 * mode 1. `--claims-dir` without `--staged` is a usage error — claims need the staged ids.
 *
 * Server: `--base-url` is used as-is (must answer `GET /diagtest` 200); otherwise
 * `node_modules/.bin/next dev -p <free port>` is spawned in the Admin checkout and waited on for up
 * to 180 s (first compile is slow). `/diagtest` DOES need the NEXT_PUBLIC_* env vars —
 * `src/lib/env.ts` throws at module load (QuestionCard → lib/api/onboarding → lib/api/fetch → env),
 * so a checkout with no `.env.local` fails fast with a clear message. The spawned server is killed
 * on exit (SIGINT/SIGTERM too).
 *
 * Rendering: one page load per theme (`addInitScript` writes `localStorage['vibhaga_admin_theme']`
 * before ThemeScript runs, plus `colorScheme` emulation; `documentElement.dataset.theme` is
 * asserted), then an esbuild bundle of the real `@/components/diagram/DiagramRenderer` is injected
 * (bundled exactly like vdd-check.mjs: Admin's esbuild, `--alias:@=<admin>/src`, cache keyed by
 * source mtimes + this file's hash). `window.__vc.render(doc, widths)` overlays a container on the
 * page and renders `<figure data-vc-figure>` plates — the StudentPreview `PreviewFigure` classes
 * minus `max-w-md`, so 768 really is 768 px. One render per figure; measurement runs on the LIGHT
 * pass (dark asserts an <svg> drew and the aria-label is present, and screenshots).
 *
 * PNG: element screenshot of each `figure[data-vc-figure]` → `<out>/<id>/<theme>-<w>.png`
 * (default out `os.tmpdir()/visual-check-out`), plus `<out>/report.json` (a W4 deliverable — the
 * label rows carry the measured label↔edge / label↔stroke distances per width).
 *
 * Per figure ONE stdout line + a summary. Exit 1 on any FAIL, 2 on usage/env errors, 0 otherwise.
 */
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFileSync, spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import { assess } from "./visual-metrics.mjs";
import { pushFigure, claimsForWarn, pairRenderedFigures, groupStagedFigures, sqlProofQ3Argv } from "./session-db.mjs";
import { contactSheetHtml } from "./contact-sheet.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN = path.resolve(HERE, "..");
const args = process.argv.slice(2);
const VALUE_OPTS = new Set(["--out", "--widths", "--themes", "--base-url", "--claims-dir", "--admin", "--session", "--staged"]);
const positional = [];
for (let i = 0; i < args.length; i++) {
  if (VALUE_OPTS.has(args[i])) { i++; continue; }
  if (!args[i].startsWith("--")) positional.push(args[i]);
}
const flag = (name) => args.includes(name);
const die = (msg) => { console.error(`visual-check: ${msg}`); process.exit(2); };
const opt = (name, dflt) => {
  const i = args.indexOf(name);
  if (i < 0) return dflt;
  const v = args[i + 1];
  if (v === undefined || v.startsWith("--")) die(`${name} needs a value (got ${v ?? "end of argv"})`);
  return v;
};

const ADMIN = path.resolve(opt("--admin") ?? process.env.VIBHAGA_ADMIN ?? path.join(PLUGIN, "..", "Vibhaga-Admin"));
if (!fs.existsSync(path.join(ADMIN, "package.json"))) die(`no Vibhaga-Admin at ${ADMIN} (pass --admin PATH or set VIBHAGA_ADMIN)`);
const ESBUILD = path.join(ADMIN, "node_modules/.bin/esbuild");
if (!fs.existsSync(ESBUILD)) die(`no esbuild at ${ESBUILD} — run \`npm ci\` in Vibhaga-Admin`);
const NEXT = path.join(ADMIN, "node_modules/.bin/next");
if (!fs.existsSync(NEXT)) die(`no next binary at ${NEXT} — run \`npm ci\` in Vibhaga-Admin`);
const PLAYWRIGHT = path.join(ADMIN, "node_modules/playwright/index.mjs");
if (!fs.existsSync(PLAYWRIGHT)) die(`no playwright at ${PLAYWRIGHT} — run \`npm ci\` in Vibhaga-Admin`);

// ── esbuild bundles — same cache discipline as vdd-check.mjs: Admin's own esbuild, a node_modules
// symlink so bare imports (react-dom/client, @vibhaga/shared, @/*) resolve through the checkout,
// and a cache key of source mtimes + this file's hash. ────────────────────────────────────────────
const CACHE = path.join(os.tmpdir(), "vibhaga-vdd-check");
fs.mkdirSync(CACHE, { recursive: true });
const NM = path.join(CACHE, "node_modules");
// rmSync unconditionally: a DANGLING symlink (a VIBHAGA_ADMIN path removed since the last run)
// reads as "missing" to existsSync, so the re-create would EEXIST.
try { if (fs.lstatSync(NM).isSymbolicLink()) fs.unlinkSync(NM); else fs.rmSync(NM, { recursive: true, force: true }); } catch (e) { if (e.code !== "ENOENT") throw e; }
fs.symlinkSync(path.join(ADMIN, "node_modules"), NM, "dir");
const SRC = path.join(ADMIN, "src/components/diagram");
const SHARED_SCHEMA = path.join(ADMIN, "node_modules/@vibhaga/shared/dist/vdd-schema");
if (!fs.existsSync(SHARED_SCHEMA)) die(`no @vibhaga/shared under ${ADMIN}/node_modules — run \`npm ci\` in an Admin checkout that carries the package`);
function stamp() {
  // Every local file the renderer touches: the source itself, its @/lib imports (cn,
  // markdown/config → KATEX_OPTIONS), the shared-schema dist, and the katex version (a bump
  // changes the overlay DOM without any source mtime moving).
  const katexVer = JSON.parse(
    fs.readFileSync(path.join(ADMIN, "node_modules/katex/package.json"), "utf8"),
  ).version;
  return [
    ...["DiagramRenderer.tsx"].map((f) => path.join(SRC, f)),
    ...["cn.ts"].map((f) => path.join(ADMIN, "src/lib", f)),
    ...["config.ts"].map((f) => path.join(ADMIN, "src/lib/markdown", f)),
    ...["index.js", "parse.js", "types.js", "colors.js"].map((f) => path.join(SHARED_SCHEMA, f)),
  ].map((f) => fs.statSync(f).mtimeMs.toFixed(0)).join("-") + `-${katexVer}`;
}
const SELF_HASH = crypto.createHash("sha1").update(fs.readFileSync(fileURLToPath(import.meta.url))).digest("hex").slice(0, 8);

// Node-side bundle: the REAL strict parser, for the invalid-doc FAIL ("would show 'Diagram coming
// soon'") and to hand the renderer the same parsed document the review surface renders.
const NODE_BUNDLE = path.join(CACHE, `vc-lib-${stamp()}-${SELF_HASH}.mjs`);
if (!fs.existsSync(NODE_BUNDLE)) {
  const entry = path.join(CACHE, "vc-lib-entry.ts");
  fs.writeFileSync(entry, `export { parseVddDocument } from "@vibhaga/shared/vdd-schema";\n`);
  execFileSync(ESBUILD, [entry, "--bundle", "--format=esm", "--platform=node", `--outfile=${NODE_BUNDLE}`,
    `--alias:@=${path.join(ADMIN, "src")}`, "--log-level=error"]);
}
const lib = await import(pathToFileURL(NODE_BUNDLE).href);

// Browser bundle: exposes window.__vc = { render(doc, widths), clear(), measure(scope) }.
// ⚠️ `math` elements are NOT in the <svg>: DiagramRenderer overlays KaTeX HTML in an absolutely
// positioned div inside the [role="img"] container (DD4 — "never <foreignObject>", DiagramRenderer.tsx
// header + renderMathOverlay), so measure() collects the top-level .katex span of each overlay and
// converts its client rect to canvas units through svg.getScreenCTM().inverse().
const RENDER_BUNDLE = path.join(CACHE, `vc-render-${stamp()}-${SELF_HASH}.js`);
if (!fs.existsSync(RENDER_BUNDLE)) {
  const entry = path.join(CACHE, "vc-render-entry.tsx");
  fs.writeFileSync(entry, `import { createRoot } from "react-dom/client";
import { createElement as h } from "react";
import { DiagramRenderer } from "@/components/diagram/DiagramRenderer";
import { parseVddDocument } from "@vibhaga/shared/vdd-schema";

const g = window as any;
let mount: HTMLDivElement | null = null;
let root: any = null;

// The overlay that owns the rendered figures: absolute top-left over the page, z-index max, the
// page's own computed body background, 16px padding; every other body child is display:none'd once.
function ensureHost(): HTMLDivElement {
  if (mount) return mount;
  const bg = getComputedStyle(document.body).backgroundColor;
  for (const c of Array.from(document.body.children)) (c as HTMLElement).style.display = "none";
  const host = document.createElement("div");
  host.id = "__vc_host";
  host.style.cssText = "position:absolute;top:0;left:0;z-index:2147483647;background:" + bg + ";padding:16px;min-height:100vh;";
  document.body.appendChild(host);
  mount = document.createElement("div");
  host.appendChild(mount);
  root = createRoot(mount);
  return mount;
}

const PRIM_SEL = "line,polyline,polygon,path,circle,rect,ellipse";
function paintOn(v: string): boolean { return !!v && v !== "none" && v !== "transparent" && v !== "rgba(0, 0, 0, 0)"; }

/** Measure every [role=img] figure under scope — one entry each (per-width hosts in batch mode). */
function measure(scope: ParentNode) {
  const hosts = [...scope.querySelectorAll('[role="img"]')] as HTMLElement[];
  return hosts.map((host, index) => {
    const svg = host.querySelector("svg");
    if (!svg) return { index, svg: false, ariaLabel: host.getAttribute("aria-label") ?? null, labels: [] };
    const vb = (svg as SVGSVGElement).viewBox?.baseVal;
    const srect = svg.getBoundingClientRect();
    const pxPerUnit = vb && vb.width ? srect.width / vb.width : null;
    const ctm = (svg as SVGSVGElement).getScreenCTM();
    const inv = ctm ? ctm.inverse() : null;
    const boxOf = (el: Element): [number, number, number, number] | null => {
      if (!inv) return null;
      const r = el.getBoundingClientRect();
      if (!(r.width > 0 || r.height > 0)) return null;
      const cs = [[r.left, r.top], [r.right, r.top], [r.right, r.bottom], [r.left, r.bottom]]
        .map(([x, y]) => new DOMPoint(x, y).matrixTransform(inv));
      const xs = cs.map((p) => p.x), ys = cs.map((p) => p.y);
      const x0 = Math.min(...xs), y0 = Math.min(...ys);
      return [x0, y0, Math.max(...xs) - x0, Math.max(...ys) - y0];
    };
    const prims = ([...svg.querySelectorAll(PRIM_SEL)] as SVGGeometryElement[])
      .filter((e) => !e.closest("defs") && !e.closest("marker"))
      .map((el) => {
        const s = getComputedStyle(el);
        const shown = s.visibility === "visible" && s.display !== "none" && parseFloat(s.opacity || "1") > 0;
        const pts: { x: number; y: number }[] = [];
        try {
          const L = el.getTotalLength();
          if (Number.isFinite(L) && L > 0) {
            const n = Math.max(8, Math.min(64, Math.ceil(L / 4)));
            for (let i = 0; i <= n; i++) pts.push(el.getPointAtLength((L * i) / n));
          }
        } catch (_) { /* not a geometry element on this engine */ }
        return {
          el, pts,
          stroked: shown && paintOn(s.stroke) && parseFloat(s.strokeWidth) > 0 && parseFloat(s.strokeOpacity || "1") > 0,
          filled: shown && paintOn(s.fill) && parseFloat(s.fillOpacity || "1") > 0,
          halfStroke: (parseFloat(s.strokeWidth) || 0) / 2,
        };
      })
      .filter((p) => p.stroked || p.filled);
    // The templates' faint ruling lines (gv*/gh* line ids — the structural marker, never
    // colour or width) are exempt from the label-to-stroke distance only (owner ruling
    // 2026-10-04: a letter may sit over them); they still count for geom_u, whose
    // proximity is exactly what keeps a fallback letter attached. Same positional
    // g-to-element mapping vdd-check's render pass uses — a count mismatch exempts nothing.
    const docEls = ((g.__vcDoc?.elements ?? []) as any[]).map((el: any, i: number) => ({ el, index: i }));
    if (docEls.some(({ el }: any) => typeof el.z === "number"))
      docEls.sort((a: any, b: any) => (a.el.z ?? 0) - (b.el.z ?? 0) || a.index - b.index);
    const shapeEls = docEls.filter(({ el }: any) => el.type !== "math");
    const gEls = [...svg.children].filter((e) => e.tagName.toLowerCase() === "g");
    const gridPrims = new Set<Element>();
    if (gEls.length === shapeEls.length)
      shapeEls.forEach(({ el }: any, i: number) => {
        if (el.type === "line" && /^g[vh][0-9]+$/.test(String(el.id ?? "")))
          for (const n of gEls[i].querySelectorAll(PRIM_SEL)) gridPrims.add(n);
      });
    const labelEls = [
      ...([...svg.querySelectorAll("text")] as SVGTextElement[])
        .filter((t) => !t.closest("defs") && !t.closest("marker"))
        .map((e) => ({ e: e as Element, kind: "text" })),
      ...([...host.querySelectorAll(".katex")] as HTMLElement[])
        .filter((e) => !(e.parentElement && e.parentElement.closest(".katex")))
        .map((e) => ({ e: e as Element, kind: "math" })),
    ];
    // Math overlay font sizes: DiagramRenderer sets fontSize = (fontSizeU / W) · 100 cqw AND
    // katex.css puts font-size: 1.21em on .katex — so the computed px is
    // fontSizeU·pxPerUnit·1.21, not canvas units. Recover units from the parsed doc's math
    // element (matched by trimmed latex, then by POSITION — the overlay centres on the at point, so
    // nearest at disambiguates two math elements carrying the same latex; a residual collision
    // only misreports if they also differ in fontSize — nearest wins, noted here);
    // fontSizeOf semantics mirrored: el.fontSize ?? defaults.fontSize ?? 18.
    const mathEls = ((g.__vcDoc?.elements ?? []) as any[])
      .filter((el) => el.type === "math")
      .map((el) => ({ latex: String(el.latex).trim(), at: el.at,
        fs: el.fontSize ?? g.__vcDoc?.defaults?.fontSize ?? 18 }));
    const labels = labelEls.map(({ e, kind }, i) => {
      const bbox = boxOf(e);
      const cs = getComputedStyle(e);
      const html = kind === "math" ? e.querySelector(".katex-html") : null;
      const text = (html ? html.textContent : e.textContent || "").trim();
      const latex = kind === "math" ? e.querySelector("annotation")?.textContent?.trim() ?? undefined : undefined;
      const ownG = e.closest("g");
      let edge_u = null, stroke_u = null, geom_u = null;
      if (bbox && vb) {
        edge_u = Math.min(
          bbox[0] - vb.x, bbox[1] - vb.y,
          vb.x + vb.width - (bbox[0] + bbox[2]), vb.y + vb.height - (bbox[1] + bbox[3]));
        const centre: [number, number] = [bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2];
        const corners = [centre, [bbox[0], bbox[1]], [bbox[0] + bbox[2], bbox[1]],
          [bbox[0], bbox[1] + bbox[3]], [bbox[0] + bbox[2], bbox[1] + bbox[3]]] as [number, number][];
        let stroke = Infinity, geom = Infinity;
        for (const p of prims) {
          if (ownG && ownG.contains(p.el as Element)) continue; // the label's own element never counts
          let d = Infinity;
          for (const pt of p.pts) {
            const dx = Math.max(bbox[0] - pt.x, 0, pt.x - (bbox[0] + bbox[2]));
            const dy = Math.max(bbox[1] - pt.y, 0, pt.y - (bbox[1] + bbox[3]));
            const dd = Math.hypot(dx, dy);
            if (dd < d) d = dd;
          }
          if (Number.isFinite(d)) {
            if (p.stroked && !gridPrims.has(p.el as Element)) stroke = Math.min(stroke, d - p.halfStroke);
            geom = Math.min(geom, d);
          }
          if (p.filled) {
            // isPointInFill's input space is engine-dependent (element-local vs viewport units);
            // try both — a false "inside" only zeroes a distance the paint really neighbours.
            const m = p.el.getCTM() ? p.el.getCTM()!.inverse() : null;
            for (const [x, y] of corners) {
              const dp = new DOMPoint(x, y);
              let inFill = false;
              try { inFill = p.el.isPointInFill(dp); } catch (_) {}
              if (!inFill && m) { try { inFill = p.el.isPointInFill(dp.matrixTransform(m)); } catch (_) {} }
              if (inFill) { geom = 0; break; }
            }
          }
        }
        stroke_u = stroke === Infinity ? null : stroke;
        geom_u = geom === Infinity ? null : geom;
      }
      return { i, text, latex, kind, bbox,
        fontFamily: cs.fontFamily,
        // For svg <text> cs.fontSize IS in user units (geometry properties report unscaled — the
        // viewBox→px scale lives on the CTM). For math overlays it is CSS px =
        // units·pxPerUnit·1.21 (.katex's em), so prefer the doc's fontSizeU and fall back to
        // px ÷ (pxPerUnit·1.21) — guarded so a null/0 scale yields null, never Infinity/NaN.
        fontSizeU: (() => {
          if (kind !== "math") return parseFloat(cs.fontSize) || null;
          const cands = mathEls.filter((m) => m.latex === (latex ?? ""));
          let el = cands[0];
          if (cands.length > 1 && bbox) {
            const c = [bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2];
            el = cands.reduce((a, b) => (!a.at ? b : !b.at ? a
              : Math.hypot(c[0] - a.at[0], c[1] - a.at[1]) <= Math.hypot(c[0] - b.at[0], c[1] - b.at[1]) ? a : b));
          }
          if (el) return el.fs;
          const u = parseFloat(cs.fontSize) / ((pxPerUnit || 0) * 1.21);
          return Number.isFinite(u) ? u : null;
        })(),
        edge_u, stroke_u, geom_u };
    });
    return { index, svg: true,
      viewBox: vb ? [vb.x, vb.y, vb.width, vb.height] : null,
      pxPerUnit, ariaLabel: host.getAttribute("aria-label") ?? null, labels };
  });
}

g.__vc = {
  render(doc: unknown, widths: number[]) {
    const r = parseVddDocument(doc);
    if (!r.ok) return { ok: false, errors: r.errors };
    g.__vcDoc = r.value; // measure() reads per-element fontSize for math labels
    ensureHost();
    root.render(h("div", { "data-vc-row": "" }, widths.map((w: number) =>
      h("div", { key: w, "data-vc-width": w, style: { width: w + "px" } },
        // The StudentPreview PreviewFigure plate minus max-w-md — 768 really is 768 px.
        h("figure", { "data-vc-figure": "",
          className: "overflow-hidden rounded-[var(--radius-lg)] border border-border bg-white p-3" },
          h(DiagramRenderer, { dsl: r.value }))))));
    return { ok: true };
  },
  clear() { root?.render(h("div", null)); },
  measure,
  /** Every [data-vc-width] host of the current render → one measurement each (batch mode). */
  measureAll() {
    return [...document.querySelectorAll("[data-vc-width]")].map((wdiv) => ({
      width: Number((wdiv as HTMLElement).getAttribute("data-vc-width")),
      ...(measure(wdiv as HTMLElement)[0] ?? { svg: false, labels: [] }),
    }));
  },
};
`);
  execFileSync(ESBUILD, [entry, "--bundle", "--format=iife", "--jsx=automatic", `--outfile=${RENDER_BUNDLE}`,
    `--alias:@=${path.join(ADMIN, "src")}`, "--loader:.css=empty", "--define:process.env.NODE_ENV=\"production\"",
    "--resolve-extensions=.tsx,.ts,.js", "--log-level=error"]);
}
const RENDER_SOURCE = fs.readFileSync(RENDER_BUNDLE, "utf8");

// ── Env file (never printed, and never READ by mode 1) — /diagtest needs the NEXT_PUBLIC_* vars:
// src/lib/env.ts throws at module load (QuestionCard → lib/api/onboarding → lib/api/fetch → env),
// so a checkout with no env file serves a 500. `next dev` loads `.env.local` itself; all mode 1
// needs is to know ONE exists (`VIBHAGA_ADMIN_ENV` path wins over the default) so a missing env is
// a clear usage error instead of a 180 s timeout. Only --session ever parses the file — for the
// admin credentials, which are read at runtime and never printed or placed on a command line.
function adminEnvFile() {
  const override = process.env.VIBHAGA_ADMIN_ENV;
  if (override && fs.existsSync(override)) return override;
  const local = path.join(ADMIN, ".env.local");
  return fs.existsSync(local) ? local : null;
}
function parseEnvFile(file) {
  const out = {};
  for (const raw of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = raw.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!m) continue;
    let v = m[2].trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
    out[m[1]] = v;
  }
  return out;
}

// ── Dev server ───────────────────────────────────────────────────────────────────────────────────
async function freePort() {
  return new Promise((ok, no) => {
    const s = http.createServer();
    s.once("error", no);
    s.listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => ok(p)); });
  });
}
async function probe(url) {
  try { const r = await fetch(url, { signal: AbortSignal.timeout(4000) }); return r.status; }
  catch { return 0; }
}
let lastBaseUrl = null;
/** → { baseUrl, proc|null }. Kills a spawned server on exit/SIGINT/SIGTERM. */
async function ensureServer() {
  const base = opt("--base-url");
  if (base) {
    const status = await probe(`${base.replace(/\/$/, "")}/diagtest`);
    if (status !== 200) die(`--base-url ${base} does not answer GET /diagtest 200 (got ${status || "no response"})`);
    lastBaseUrl = base.replace(/\/$/, "");
    return { baseUrl: lastBaseUrl, proc: null };
  }
  // /diagtest needs the NEXT_PUBLIC_* vars — src/lib/env.ts throws at module load
  // (QuestionCard → lib/api/onboarding → lib/api/fetch → env), so the page 500s without them.
  // Existence check only — this mode never reads the env file; `next dev` loads it itself.
  const envFile = adminEnvFile();
  if (!envFile)
    die(`next dev cannot serve /diagtest — ${ADMIN} has no env file and VIBHAGA_ADMIN_ENV (${process.env.VIBHAGA_ADMIN_ENV ?? "unset"}) does not exist. /diagtest's module graph throws without NEXT_PUBLIC_API_BASE_URL/NEXT_PUBLIC_SUPABASE_URL/NEXT_PUBLIC_SUPABASE_ANON_KEY (src/lib/env.ts).`);
  const port = await freePort();
  const proc = spawn(NEXT, ["dev", "-p", String(port)], { cwd: ADMIN, env: { ...process.env }, stdio: ["ignore", "pipe", "pipe"] });
  let tail = [];
  const hear = (d) => { tail.push(...String(d).split("\n")); tail = tail.slice(-25); };
  proc.stdout.on("data", hear);
  proc.stderr.on("data", hear);
  let exited = null;
  proc.on("exit", (code) => { exited = code; });
  const stop = () => { try { proc.kill("SIGTERM"); } catch {} };
  process.once("exit", stop);
  for (const sig of ["SIGINT", "SIGTERM"]) process.once(sig, () => { stop(); process.exit(sig === "SIGINT" ? 130 : 143); });
  const deadline = Date.now() + 180_000;
  const url = `http://localhost:${port}`;
  for (;;) {
    if (exited !== null) die(`next dev exited ${exited} before /diagtest answered.\n${tail.join("\n")}`);
    if (Date.now() > deadline) { stop(); die(`/diagtest did not answer 200 within 180s on ${url}. If the page 500s, ${envFile} is missing a NEXT_PUBLIC_* var — src/lib/env.ts throws at module load.\n${tail.join("\n")}`); }
    if (await probe(`${url}/diagtest`) === 200) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  lastBaseUrl = url;
  return { baseUrl: url, proc };
}

// ── Inputs ───────────────────────────────────────────────────────────────────────────────────────
const isVdd = (o) => o && typeof o === "object" && o.schema === "vibhaga.diagram";
const isStaged = (o) => o && typeof o === "object" && Array.isArray(o.questions);

// The staged-doc walk is shared: mode 1 reads the doc from a positional input, --session from
// --staged — either way each diagram_dsl becomes a figure whose claim set resolves by the
// staged id (`Q<n>`, `Q<n>.<label>`, `Q<n>.ans<k>`) under --claims-dir.
function collectFromStaged(figures, seen, staged, source, claimsDir) {
  const push = (id, doc, _src, fileBase = null) =>
    pushFigure(figures, seen, id, doc, source, fileBase, claimsDir);
  const walkSubs = (list, prefix) => {
    for (const s of list ?? []) {
      if (!s || typeof s !== "object") continue;
      const id = `${prefix}.${s.label ?? "?"}`;
      if (s.diagram_dsl) push(id, s.diagram_dsl);
      // sub-answers: canonical `answers: []`, plus the legacy singular `sub_answer` folded first
      // (the same order Admin's normalizeStagedQuestions uses).
      const answers = [...(s.sub_answer ? [s.sub_answer] : []), ...(Array.isArray(s.answers) ? s.answers : [])];
      answers.forEach((a, k) => { if (a?.diagram_dsl) push(`${id}.ans${k + 1}`, a.diagram_dsl); });
      walkSubs(s.sub_questions, id);
    }
  };
  walkStagedDoc(staged, source, push, walkSubs);
}

function collectFigures(inputs, claimsDir) {
  const figures = [];
  const seen = new Map();
  // pushFigure (session-db.mjs) dedups `id` to `id~k` but resolves claims by the BASE id —
  // a duplicate shares the first figure's claim file.
  const push = (id, doc, source, fileBase) => pushFigure(figures, seen, id, doc, source, fileBase, claimsDir);
  for (const input of inputs) {
    const st = fs.statSync(input, { throwIfNoEntry: false });
    if (!st) die(`no such input: ${input}`);
    if (st.isDirectory()) {
      for (const f of fs.readdirSync(input).sort()) {
        if (!f.endsWith(".json") || f.endsWith(".anchors.json")) continue;
        const full = path.join(input, f);
        let doc;
        try { doc = JSON.parse(fs.readFileSync(full, "utf8")); } catch { continue; }
        if (isVdd(doc)) push(path.basename(f, ".json"), doc, full, full.slice(0, -5));
      }
      continue;
    }
    let doc;
    try { doc = JSON.parse(fs.readFileSync(input, "utf8")); }
    catch (e) { die(`${input}: not JSON — ${e.message}`); }
    if (isVdd(doc)) push(path.basename(input, ".json"), doc, input, input.slice(0, -5));
    else if (isStaged(doc)) collectFromStaged(figures, seen, doc, input, claimsDir);
    else die(`${input}: neither a VDD document (schema:"vibhaga.diagram") nor a staged doc (questions[])`);
  }
  return figures;
}
// ⚠️ the walk order IS the pairing order for --session: it must emit each question's figures in
// the order StudentPreview renders them — question figure, then parts (each part: its figure,
// its sub-answers' figures, then nested sub-questions), then the whole-question answers LAST.
// Answers-before-parts here would mis-pair every part figure behind them.
function walkStagedDoc(staged, source, push, walkSubs) {
  (staged.questions ?? []).forEach((q, i) => {
    if (!q || typeof q !== "object") return;
    const id = `Q${q.question_number ?? i + 1}`;
    if (q.diagram_dsl) push(id, q.diagram_dsl, source, null);
    walkSubs(q.sub_questions, id, source);
    (Array.isArray(q.answers) ? q.answers : []).forEach((a, k) => {
      if (a?.diagram_dsl) push(`${id}.ans${k + 1}`, a.diagram_dsl, source, null);
    });
  });
}

// ── The batch run ────────────────────────────────────────────────────────────────────────────────
async function runBatch(figures, { out, widths, themes, headed }) {
  const server = await ensureServer();
  const { chromium } = await import(pathToFileURL(PLAYWRIGHT).href);
  const browser = await chromium.launch({ headless: !headed });
  const measureTheme = themes.includes("light") ? "light" : themes[0];
  try {
    for (const theme of themes) {
      const ctx = await browser.newContext({
        viewport: { width: Math.max(...widths) + 64, height: 1600 },
        colorScheme: theme,
      });
      await ctx.addInitScript((t) => { try { localStorage.setItem("vibhaga_admin_theme", t); } catch (_) {} }, theme);
      const page = await ctx.newPage();
      await page.goto(`${server.baseUrl}/diagtest`, { waitUntil: "domcontentloaded", timeout: 120_000 });
      await page.waitForFunction((t) => document.documentElement.dataset.theme === t, theme, { timeout: 30_000 });
      await page.evaluate(() => document.fonts.ready.then(() => true));
      await page.addScriptTag({ content: RENDER_SOURCE });
      await page.waitForFunction(() => typeof window.__vc === "object", null, { timeout: 15_000 });
      for (const fig of figures) {
        if (fig.invalid) continue;
        const r = await page.evaluate(([doc, ws]) => window.__vc.render(doc, ws), [fig.parsed, widths]);
        if (!r?.ok) {
          fig.invalid = r?.errors ?? "render() failed";
          fig.findings.push({ rule: "parse", severity: "fail", message: `in-page parseVddDocument failed — a student would see 'Diagram coming soon'` });
          continue;
        }
        await page.waitForSelector("figure[data-vc-figure] svg", { timeout: 15_000 });
        await page.evaluate(() => document.fonts.ready.then(() => true));
        const measured = await page.evaluate(() => window.__vc.measureAll());
        if (theme === measureTheme) {
          fig.measured = measured;
          for (const m of measured) {
            if (!m.svg) fig.findings.push({ rule: "render", severity: "fail", message: `no <svg> drew at ${m.width}px — 'Diagram coming soon' territory` });
            else if (!m.ariaLabel) fig.findings.push({ rule: "render", severity: "fail", message: `no aria-label on the figure at ${m.width}px` });
          }
        } else {
          // Non-light passes only assert the figure drew (svg + accessible name) — label metrics
          // are the light pass's job.
          for (const m of measured) {
            if (!m.svg || !m.ariaLabel)
              fig.findings.push({ rule: "render", severity: "fail", message: `${theme} pass: ${!m.svg ? "no <svg> drew" : "no aria-label"} at ${m.width}px` });
          }
        }
        for (const w of widths) {
          const shot = path.join(fig.outDir, `${theme}-${w}.png`);
          fs.mkdirSync(fig.outDir, { recursive: true });
          await page.locator(`[data-vc-width="${w}"] figure[data-vc-figure]`).screenshot({ path: shot });
          fig.pngs.push(shot);
        }
      }
      await ctx.close();
    }
    // The contact sheets (W9-C): every figure's <theme>-375.png at native size, 2 per row with its
    // id captioned above, on white — one PNG per theme the lead can read instead of N. Composed in a
    // bare page off the already-open browser; the PNGs are inlined as data URIs because a setContent
    // page may not load file:// subresources. Skipped silently when no <theme>-375 shot exists
    // (a --widths/--themes that excludes them, or every figure invalid before render).
    const sheets = [];
    for (const theme of themes) {
      const items = [];
      for (const fig of figures) {
        const png = (fig.pngs ?? []).find((p) => new RegExp(`${theme}-375\\.png$`).test(p));
        if (png && fs.existsSync(png)) items.push({ id: fig.id, data: fs.readFileSync(png).toString("base64") });
      }
      if (!items.length) continue;
      const sheetPath = path.join(out, `contact-${theme}-375.png`);
      // Start tiny: body.scrollWidth floors at the viewport, so a small initial viewport lets the
      // 2-tile grid overflow and reveals its real width — the fullPage shot then has no 1280×720
      // floor of whitespace under a small batch.
      const page = await browser.newPage({ viewport: { width: 100, height: 100 } });
      await page.setContent(contactSheetHtml(items));
      await page.waitForFunction(() => [...document.images].every((i) => i.complete));
      const w = await page.evaluate(() => document.body.scrollWidth);
      await page.setViewportSize({ width: w, height: 100 });
      await page.screenshot({ path: sheetPath, fullPage: true });
      await page.close();
      const b = fs.readFileSync(sheetPath);
      sheets.push({ path: sheetPath, dims: b.length > 24 ? `${b.readUInt32BE(16)}×${b.readUInt32BE(20)}` : "?" });
    }
    if (sheets.length) figures.sheets = sheets;
  } finally {
    await browser.close();
    if (server.proc) { server.proc.kill("SIGTERM"); }
  }
  // verdicts — the pure module decides
  for (const fig of figures) {
    const res = assess({
      doc: fig.parsed ?? fig.doc,
      claims: fig.claims?.text ?? null,
      widths: fig.measured ?? [],
    });
    res.findings.unshift(...fig.findings);
    if (res.findings.some((f) => f.severity === "fail")) res.verdict = "FAIL";
    fig.result = res;
  }
  return figures;
}

function figureLine(fig, pad) {
  const a = fig.result;
  const failsOf = (rule) => a.findings.filter((f) => f.rule === rule && f.severity === "fail");
  const parts = [];
  const fontF = failsOf("font");
  parts.push(a.font && (a.font.math || a.font.text) ? (fontF.length ? `font: ${fontF[0].message.replace(/^font /, "")}` : "font ok") : "font —");
  const uniq = a.labels.filter((l) => l.width === a.labels[0]?.width).length || new Set(a.labels.map((l) => `${l.i}:${l.text}`)).size;
  const minE = a.labels.reduce((m, l) => Math.min(m, l.edge_px ?? Infinity), Infinity);
  const minS = a.labels.reduce((m, l) => Math.min(m, l.stroke_px ?? Infinity), Infinity);
  parts.push(`labels ${uniq} (min edge ${minE === Infinity ? "—" : minE + "px"}, min stroke ${minS === Infinity ? "—" : minS + "px"})`);
  parts.push(`target ${failsOf("target").length ? `${failsOf("target").length} fail` : "ok"}`);
  parts.push(`arc ${a.arcs ? (failsOf("arc").length ? `${failsOf("arc").length} fail` : "ok") : "—"}`);
  const shadedF = failsOf("shaded");
  parts.push(`shaded ${a.shaded ? (shadedF.length ? `measured ${a.shaded.measured} ≠ claimed ${a.shaded.claimed}` : "ok") : "—"}`);
  parts.push(`aspect ${a.aspect ? (failsOf("aspect").length ? "FAIL" : "ok") : "—"}`);
  // the light-375 PNG's pixel dimensions — a tall plate is exactly what the aspect rule guards
  let dims = "—";
  const png375 = fig.pngs?.find((p) => /light-375\.png$/.test(p));
  if (png375 && fs.existsSync(png375)) {
    const b = fs.readFileSync(png375);
    if (b.length > 24) dims = `${b.readUInt32BE(16)}×${b.readUInt32BE(20)}`;
  }
  parts.push(dims);
  const other = failsOf("parse").concat(failsOf("render")).map((f) => f.message).join("; ");
  return `${fig.id.padEnd(pad)}  ${fig.result.verdict.padEnd(4)}  ${parts.join(" · ")}${other ? ` · ${other}` : ""}  → ${fig.outDir}/`;
}

async function batchMode() {
  if (!positional.length && !flag("--self-test")) die(`usage: visual-check.mjs <inputs…> [--out DIR] [--widths 320,375,768] [--themes light,dark] [--base-url URL] [--claims-dir DIR] [--headed] [--admin PATH]\n       visual-check.mjs --session <id> [--staged FILE] [--claims-dir DIR]   (⚠️ --session, not --admin — --admin PATH is the Admin CHECKOUT)\n       visual-check.mjs --self-test`);
  const out = path.resolve(opt("--out", path.join(os.tmpdir(), "visual-check-out")));
  const widths = opt("--widths", "320,375,768").split(",").map(Number);
  if (!widths.length || widths.some((w) => !(w > 0))) die(`bad --widths: ${opt("--widths")}`);
  const themes = opt("--themes", "light,dark").split(",").map((t) => t.trim());
  if (!themes.length || themes.some((t) => !["light", "dark"].includes(t))) die(`bad --themes: ${opt("--themes")} (light,dark)`);
  const claimsDir = opt("--claims-dir") ? path.resolve(opt("--claims-dir")) : null;
  if (claimsDir && !fs.existsSync(claimsDir)) die(`--claims-dir ${claimsDir} does not exist`);
  const figures = collectFigures(positional, claimsDir);
  if (!figures.length) die("no VDD figures found in the given inputs");
  let noClaims = 0; // --claims-dir only: a resolved-everywhere failure is loud, never fatal
  for (const fig of figures) {
    const w = claimsForWarn(fig.baseId ?? fig.id, claimsDir, fig.claims);
    if (w) { console.log(w); noClaims++; }
  }
  for (const fig of figures) {
    fig.outDir = path.join(out, fig.id);
    fig.pngs = [];
    fig.findings = [];
    const r = lib.parseVddDocument(fig.doc);
    if (!r.ok) {
      fig.invalid = r.errors;
      fig.parsed = null;
      fig.findings.push({ rule: "parse", severity: "fail", message: `document fails parseVddDocument: ${JSON.stringify(r.errors?.slice?.(0, 3) ?? r.errors).slice(0, 200)} — a student would see 'Diagram coming soon'` });
    } else fig.parsed = r.value;
  }
  await runBatch(figures, { out, widths, themes, headed: flag("--headed") });
  const pad = Math.max(...figures.map((f) => f.id.length));
  let pass = 0;
  let pngs = 0;
  for (const fig of figures) {
    if (fig.result.verdict === "PASS") pass++;
    pngs += fig.pngs.length;
    console.log(figureLine(fig, pad));
  }
  console.log(`${figures.length} figures · ${pass} pass · ${figures.length - pass} fail${claimsDir ? ` · ${noClaims} without claims` : ""} · PNGs: ${pngs} · report: ${path.join(out, "report.json")}${(figures.sheets ?? []).map((s) => ` · contact: ${s.path} ${s.dims}`).join("")}`);
  fs.mkdirSync(out, { recursive: true });
  const report = {
    tool: "visual-check",
    widths,
    themes,
    base_url: lastBaseUrl ?? null,
    figures: figures.map((f) => ({
      id: f.id,
      source: f.source,
      verdict: f.result.verdict,
      findings: f.result.findings,
      labels: f.result.labels.map(({ i, text, kind, width, edge_px, stroke_px, target_u, ok }) =>
        ({ i, text, kind, width, edge_px, stroke_px, target_u, ok })),
      shaded: f.result.shaded,
      font: f.result.font,
      arcs: f.result.arcs,
      aspect: f.result.aspect,
      pngs: f.pngs,
    })),
  };
  fs.writeFileSync(path.join(out, "report.json"), JSON.stringify(report, null, 1));
  process.exit(figures.length - pass ? 1 : 0);
}

// ── Mode 2: --session <id> — headed Chromium against the real workspace, then sign out + prove. ──
function loadCredentials() {
  // The ONLY place the env file is parsed — --session's sign-in needs the admin credentials.
  const file = adminEnvFile();
  const vars = file ? parseEnvFile(file) : {};
  const email = vars.VIBHAGA_ADMIN_EMAIL, password = vars.VIBHAGA_ADMIN_PASSWORD;
  if (!email || !password)
    die(`--session needs VIBHAGA_ADMIN_EMAIL/VIBHAGA_ADMIN_PASSWORD in ${file ?? path.join(ADMIN, ".env.local")} (or VIBHAGA_ADMIN_ENV) — credentials are read at runtime and never printed`);
  return { email, password };
}
/** Actor's user.id from the Supabase session — cookie chunks joined, base64- decoded.
 *  Reads ONLY user.id; never a token value, never logged. */
async function extractActorId(page) {
  return page.evaluate(() => {
    const decode = (raw) => {
      try {
        let v = raw;
        try { v = decodeURIComponent(v); } catch (_) {}
        if (v.startsWith("base64-")) v = atob(v.slice(7));
        const j = JSON.parse(v);
        return j?.user?.id ?? null;
      } catch (_) { return null; }
    };
    const groups = {};
    for (const part of document.cookie.split("; ")) {
      const eq = part.indexOf("=");
      if (eq < 0) continue;
      const m = part.slice(0, eq).trim().match(/^(sb-.+-auth-token)(?:\.(\d+))?$/);
      if (m) (groups[m[1]] ??= {})[m[2] === undefined ? 0 : +m[2]] = part.slice(eq + 1);
    }
    for (const g of Object.values(groups)) {
      const joined = Object.keys(g).map(Number).sort((a, b) => a - b).map((i) => g[i]).join("");
      const id = decode(joined);
      if (id) return id;
    }
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i) ?? "";
      if (!/auth-token/.test(k)) continue;
      const id = decode(localStorage.getItem(k) ?? "");
      if (id) return id;
    }
    return null;
  });
}

async function sessionMode() {
  const sessionId = opt("--session");
  const out = path.resolve(opt("--out", path.join(os.tmpdir(), "visual-check-out")));
  const stagedFile = opt("--staged") ? path.resolve(opt("--staged")) : null;
  const claimsDir = opt("--claims-dir") ? path.resolve(opt("--claims-dir")) : null;
  if (claimsDir && !stagedFile)
    die("--claims-dir needs --staged FILE — the staged doc supplies each rendered figure's id; claims resolve against it (run-gates ship passes --staged <run>/staged.json --claims-dir <run>/figures)");
  if (stagedFile && !fs.existsSync(stagedFile)) die(`--staged ${stagedFile} does not exist`);
  if (claimsDir && !fs.existsSync(claimsDir)) die(`--claims-dir ${claimsDir} does not exist`);
  // --staged: the run's staged doc read from disk — ship's doc-get step has already proven it
  // IS the server doc, so nothing is fetched from the page. Each diagram_dsl becomes a figure
  // keyed by staged id; the rendered↔staged pairing is positional per question (see
  // pairRenderedFigures), so this map is built once, up front, and a bad file dies before the
  // browser ever opens.
  const figsByQ = new Map();               // question number → staged figures, doc order
  if (stagedFile) {
    let staged;
    try { staged = JSON.parse(fs.readFileSync(stagedFile, "utf8")); }
    catch (e) { die(`--staged ${stagedFile}: not JSON — ${e.message}`); }
    if (!isStaged(staged)) die(`--staged ${stagedFile}: not a staged doc (no questions[])`);
    const figs = [];
    collectFromStaged(figs, new Map(), staged, stagedFile, claimsDir);
    for (const f of figs) {
      const r = lib.parseVddDocument(f.doc);
      f.parsed = r.ok ? r.value : f.doc;
      // StudentPreview renders an unparseable or element-less diagram as a <p> note — NO
      // [role="img"] host, no svg — so it must not take a pairing slot, or one broken figure
      // shifts every figure behind it onto the wrong claim set (a false PASS).
      if (!r.ok) { f.renders = false; f.why = "does not parse"; }
      else if (!(r.value.elements ?? []).length) { f.renders = false; f.why = "has no elements"; }
      const w = claimsForWarn(f.baseId ?? f.id, claimsDir, f.claims);
      if (w) console.log(w);
    }
    const { byQ, skipped } = groupStagedFigures(figs);
    for (const s of skipped)
      console.log(`  WARN Q${s.q}: staged figure ${s.id} ${s.why} — not rendered, not paired`);
    for (const [k, v] of byQ) figsByQ.set(k, v);
  }
  const outDir = path.join(out, "session");
  fs.mkdirSync(outDir, { recursive: true });
  const creds = loadCredentials();
  const server = await ensureServer();
  lastBaseUrl = server.baseUrl;
  const { chromium } = await import(pathToFileURL(PLAYWRIGHT).href);
  const browser = await chromium.launch({ headless: false }); // always headed
  let exitCode = 0;
  // hoisted to function scope so the outer catch/finally can still write report.json
  // when the run dies before the question loop (A7 — ship had no artefact to summarise)
  const shots = [];                       // {question, theme, verdict, findings, png}
  let actorId = null;
  let anyFail = false;
  let fatal = null;
  let proofFail = false;
  try {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
    const page = await ctx.newPage();
    await page.goto(`${server.baseUrl}/login`, { waitUntil: "domcontentloaded", timeout: 120_000 });
    // SignInForm's inputs are CONTROLLED (`useState("")`) — a fill that lands before hydration is
    // clobbered to "" on hydrate and the submit sends empty credentials ("Incorrect email or
    // password."). Wait for networkidle, then probe hydration directly: a hydrated input carries
    // React's __reactProps*/__reactFiber* expando; a server-rendered one does not. Fill with real
    // keystrokes (pressSequentially), which React always tracks, then assert the DOM value held.
    await page.waitForLoadState("networkidle", { timeout: 30_000 }).catch(() => {});
    const emailIn = page.getByLabel("Email");
    const pwdIn = page.getByLabel("Password");
    const hydrated = await emailIn.evaluate((el) =>
      Object.keys(el).some((k) => k.startsWith("__reactProps") || k.startsWith("__reactFiber")),
    ).catch(() => null);
    console.log(`sign-in form hydrated: ${hydrated === null ? "?" : hydrated ? "yes" : "no"}`);
    const fillField = async (locator, value) => {
      await locator.click();
      await locator.pressSequentially(value, { delay: 8 });
      if ((await locator.inputValue()) === "") {       // React state ate the DOM value — retry once
        await locator.fill(value);
      }
      return (await locator.inputValue()) !== "";
    };
    const emailOk = await fillField(emailIn, creds.email);
    const pwdOk = await fillField(pwdIn, creds.password);
    const fieldsFilled = emailOk && pwdOk;
    console.log(`sign-in fields at submit: ${fieldsFilled ? "both non-empty" : "EMPTY — hydration clobbered the fill"}`);
    // Diagnostics without values: watch the Supabase token call so a hung request is told apart
    // from a credential rejection (its STATUS only — never a body or token), and catch a
    // client-side throw in the submit handler (unhandled rejection → pageerror).
    let authStatus = "no /auth/v1/token request seen";
    let pageError = "";
    page.on("response", (res) => {
      if (/auth\/v1\/token/.test(res.url())) authStatus = `token request → HTTP ${res.status()}`;
    });
    page.on("requestfailed", (req) => {
      if (/supabase|auth/.test(req.url())) authStatus = `request failed: ${req.url().replace(/\?.*$/, "")} (${req.failure()?.errorText})`;
    });
    page.on("pageerror", (e) => { pageError = `pageerror: ${e.message}`; });
    await page.getByRole("button", { name: "Sign in" }).click();
    const alert = page.getByRole("alert").filter({ hasText: "Incorrect email or password." });
    const outcome = await Promise.race([
      page.waitForURL((u) => !u.pathname.endsWith("/login"), { timeout: 60_000 }).then(() => "in"),
      alert.waitFor({ state: "visible", timeout: 60_000 }).then(() => "bad"),
    ]).catch(() => "timeout");
    if (outcome !== "in")
      throw new Error(`sign-in failed (fields at submit: ${fieldsFilled ? "non-empty" : "EMPTY"}; ${authStatus}${pageError ? "; " + pageError : ""}): ` +
        `${(await alert.first().textContent().catch(() => null))?.trim() ?? "no redirect"}`);
    // ── signed in ── everything below runs under a finally that ALWAYS signs out; the actor id
    // is captured FIRST so a mid-loop failure still leaves a usable revocation proof.
    try {
      actorId = await extractActorId(page);
      if (!actorId) throw new Error("could not extract the actor's user id from the Supabase session (cookie/localStorage)");
      await page.goto(`${server.baseUrl}/generate/${sessionId}`, { waitUntil: "domcontentloaded", timeout: 60_000 });
    for (const theme of ["light", "dark"]) {
      await page.emulateMedia({ colorScheme: theme });
      await page.evaluate((t) => { try { localStorage.setItem("vibhaga_admin_theme", t); } catch (_) {} }, theme);
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForFunction((t) => document.documentElement.dataset.theme === t, theme, { timeout: 30_000 });
      await page.addScriptTag({ content: RENDER_SOURCE });
      await page.waitForFunction(() => typeof window.__vc === "object", null, { timeout: 15_000 });
      // The staged doc loads via TanStack Query — wait for the first card's preview trigger.
      await page.getByRole("button", { name: /Preview as a student — question \d+/ })
        .first().waitFor({ timeout: 60_000 });
      const names = await page.getByRole("button", { name: /Preview as a student — question \d+/ })
        .evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
      for (const name of names) {
        const n = Number(name.match(/question (\d+)/)[1]);
        // exact: true — "question 1" substring-matches "question 10" otherwise
        await page.getByRole("button", { name, exact: true }).click();
        const region = page.getByRole("region", { name: `Preview — question ${n}, as a student reads it` });
        await region.waitFor({ timeout: 15_000 });
        const port = region.locator("[data-student-scrollport]");
        await page.evaluate(() => document.fonts.ready.then(() => true));
        await port.locator('[role="img"] svg').first().waitFor({ timeout: 10_000 }).catch(() => {});
        // ── unclip ── the scrollport is height-clamped and scrollable, and an element shot only
        // captures the VISIBLE box (the earlier PNGs were cut below the side labels with a black
        // band beyond the viewport). Remove every clamp from the scrollport up to the region, and
        // grow the viewport to fit (the preview region re-renders on each open, so no restore of
        // styles is needed; the viewport is put back below).
        await port.evaluate((el) => {
          // scrollport → up to AND INCLUDING the preview region (role=region). NOT past it —
          // ancestors above the overlay persist after the region unmounts and would break the
          // next question's layout/click (observed: "element is outside of the viewport").
          for (let node = el; node; node = node.parentElement) {
            node.style.setProperty("max-height", "none", "important");
            node.style.setProperty("height", "auto", "important");
            node.style.setProperty("overflow", "visible", "important");
            if (node.getAttribute("role") === "region") break;
          }
        });
        const needH = await region.evaluate((el) => Math.ceil(el.getBoundingClientRect().bottom + 24));
        const vp = page.viewportSize() ?? { width: 1440, height: 900 };
        if (needH > vp.height) {
          await page.setViewportSize({ width: 1440, height: Math.min(6000, needH) });
          await page.evaluate(() => document.fonts.ready.then(() => true)); // layout settles
        }
        const png = path.join(outDir, `${theme}-Q${n}.png`);
        await port.screenshot({ path: png });
        // ── clip assert ── nothing may remain scrollable inside the shot, and every figure svg
        // must lie inside the port's box. A clipped shot is a FAIL, not a best-effort PNG.
        const clip = await port.evaluate((el) => {
          const pr = el.getBoundingClientRect();
          const rects = [...el.querySelectorAll("svg")].map((s) => s.getBoundingClientRect());
          return {
            noScroll: el.scrollHeight <= el.clientHeight + 1,
            svgsInside: rects.every((r) => r.top >= pr.top - 1 && r.bottom <= pr.bottom + 1
              && r.left >= pr.left - 1 && r.right <= pr.right + 1),
            nSvg: rects.length,
          };
        });
        const clipped = !(clip.noScroll && clip.svgsInside);
        const measured = await port.evaluate((el) => window.__vc.measure(el));
        // --staged: pair each rendered figure with the staged doc's figure by position among
        // the svg-bearing hosts (m.index counts svg-less plates too — see pairRenderedFigures);
        // the same claims then drive assess() exactly as in mode 1.
        const qFigs = stagedFile ? (figsByQ.get(n) ?? []) : null;
        const pairs = pairRenderedFigures(measured, qFigs);
        if (qFigs && qFigs.length !== pairs.length)
          console.log(`  WARN Q${n}: ${qFigs.length} staged figure(s) but ${pairs.length} rendered — claims resolved by position`);
        const results = pairs.map(({ measured: m, fig }) =>
          assess({ doc: fig?.parsed ?? null, claims: fig?.claims?.text ?? null,
                   widths: [{ width: 375, pxPerUnit: m.pxPerUnit, labels: m.labels }] }));
        const fails = results.flatMap((r) => r.findings.filter((f) => f.severity === "fail"));
        if (fails.length || clipped) anyFail = true;
        const verdict = clipped ? "CLIPPED FAIL" : fails.length ? "FAIL" : "PASS";
        shots.push({ question: n, theme, verdict, figures: results.length,
                     findings: fails.map((f) => f.message), png });
        console.log(`Q${n}  ${verdict}  ${theme} · figures ${results.length} · findings ${fails.length}${fails.length ? " — " + fails.map((f) => f.message).join("; ") : ""}  → ${png}`);
        if (needH > vp.height) await page.setViewportSize(vp); // put the viewport back
        await region.getByRole("button", { name: "Close preview" }).click().catch(() => {});
        const detached = await region.waitFor({ state: "detached", timeout: 5_000 })
          .then(() => true).catch(() => false);
        if (!detached) {
          // The region didn't unmount — its unclamped inline styles could leak into the next
          // question's shot. Reload the page (same theme) instead of trusting the close.
          await page.reload({ waitUntil: "domcontentloaded" });
          await page.waitForFunction((t) => document.documentElement.dataset.theme === t, theme, { timeout: 30_000 });
          await page.addScriptTag({ content: RENDER_SOURCE });
          await page.waitForFunction(() => typeof window.__vc === "object", null, { timeout: 15_000 });
          await page.getByRole("button", { name: /Preview as a student — question \d+/ })
            .first().waitFor({ timeout: 60_000 });
        }
      }
    }
  } catch (e) {
    fatal = e;
    console.error(`visual-check: --session aborted — ${e?.message ?? e} — still signing out`);
  } finally {
    // Sign out MUST happen once signed in — the Q3 revocation proof is meaningless on a live
    // session. Button first; if that fails, expire the sb-* auth cookies + storage in-page and
    // say so LOUDLY (a skipped sign-out must never pass silently).
    try {
      await page.getByRole("button", { name: "Sign out" }).first().click();
      await page.waitForURL(/\/login/, { timeout: 15_000 });
    } catch (_) {
      try {
        await page.evaluate(() => {
          for (const c of document.cookie.split(";")) {
            const n = c.split("=")[0].trim();
            if (n.startsWith("sb-"))
              document.cookie = `${n}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
          }
          for (let i = localStorage.length - 1; i >= 0; i--) {
            const k = localStorage.key(i) ?? "";
            if (/auth|sb-/.test(k)) localStorage.removeItem(k);
          }
        });
      } catch (_) { /* page may be gone — the loud line below still reports it */ }
      console.error("visual-check: ⚠️ SIGN-OUT FAILED — the admin session may still be live; verify revocation with queries.sql Q3 on the Admin Auth project");
    }
    // The revocation proof runs whether or not the loop failed — never select token values.
    // Same resolution playground-publish's post-logout Q3 uses (sql-proof's find_auth_url):
    // VIBHAGA_ADMIN_AUTH_DB_URL env, then that key's line in the admin env file. When it
    // resolves, sql-proof.py runs the proof itself (its own resolver + psql runner, output
    // echoed verbatim); when it doesn't, one PENDING hint stands instead. The URL is never
    // printed and never placed on argv.
    if (actorId) {
      const envFile = adminEnvFile();
      const fromEnv = !!process.env.VIBHAGA_ADMIN_AUTH_DB_URL;
      const authUrl = process.env.VIBHAGA_ADMIN_AUTH_DB_URL
        ?? (envFile ? parseEnvFile(envFile).VIBHAGA_ADMIN_AUTH_DB_URL : null);
      if (authUrl) {
        // authEnv when the URL came from the FILE: sql-proof's own resolver would not find
        // this file when --admin/VIBHAGA_ADMIN points at a non-sibling checkout — one
        // resolution feeds both (see sqlProofQ3Argv).
        const r = spawnSync(process.env.PYTHON ?? "python3",
          sqlProofQ3Argv(PLUGIN, actorId, fromEnv ? null : envFile),
          { encoding: "utf8" });
        const text = `${r.stdout ?? ""}${r.stderr ?? ""}`.trim();
        if (text) console.log(text.split("\n").map((l) => `  ${l}`).join("\n"));
        if (r.error || r.status !== 0) {
          console.log(`  q3: NOT ok — the proof did not pass (sql-proof exit ${r.status ?? r.error?.message})`);
          proofFail = true;
        }
      } else {
        console.log(`revocation: PENDING — run queries.sql Q3 on the Admin Auth project with actor_id=${actorId}`);
      }
    } else {
      console.log("revocation: UNKNOWN — no actor id was captured before the failure");
    }
  }
  } catch (e) {
    // a sign-in-time failure lands here — before the inner finally existed. Record it so
    // report.json still says what happened instead of the stage leaving nothing behind.
    fatal = fatal ?? e;
    console.error(`visual-check: --session failed — ${e?.message ?? e}`);
  } finally {
    await browser.close();
    if (server.proc) server.proc.kill("SIGTERM");
  }
  exitCode = fatal ? 1 : (anyFail || proofFail) ? 1 : 0;
  // report.json — the stage's artefact: ship quotes the verdict lines and this summary is
  // the proof the run happened (screenshots alone used to be the only trace)
  const report = {
    tool: "visual-check",
    mode: "session",
    session: sessionId,
    base_url: lastBaseUrl ?? null,
    verdict: fatal ? "ERROR" : (anyFail || proofFail) ? "FAIL" : "PASS",
    exit: exitCode,
    error: fatal ? String(fatal?.message ?? fatal) : null,
    screenshots: shots,
  };
  fs.writeFileSync(path.join(out, "report.json"), JSON.stringify(report, null, 1));
  console.log(`${shots.length} screenshot(s) · verdict ${report.verdict} · exit ${exitCode} · report: ${path.join(out, "report.json")}`);
  return exitCode;
}

// ── --self-test: two synthetic figures through the real /diagtest pipeline ───────────────────────
async function selfTest() {
  // The self-test needs a servable /diagtest — a checkout with no env file is a SKIP, not a
  // failure (existence check only; nothing here reads the env file). With --base-url the server
  // is already up — no env needed.
  const envFile = adminEnvFile();
  if (!opt("--base-url") && !envFile) {
    console.log(`SELF-TEST SKIP — ${ADMIN} has no env file (VIBHAGA_ADMIN_ENV / .env.local) for /diagtest`);
    process.exit(0);
  }
  // A clean right-triangle: point labels offset clear of every stroke and edge. Capital labels are
  // deliberately NOT arc-rule numerals (the regex excludes capitals — they are point names).
  const clean = {
    schema: "vibhaga.diagram", schemaVersion: 1, canvas: { width: 300, height: 260 },
    defaults: { strokeWidth: 2, fontSize: 18 },
    a11y: { title: "Synthetic right triangle for visual-check", description: "A synthetic right-angled triangle, vertices labelled, the right angle marked with a square. Fixture only." },
    elements: [
      { id: "AB", type: "line", points: [[60, 40], [60, 220]] },
      { id: "BC", type: "line", points: [[60, 220], [240, 220]] },
      { id: "AC", type: "line", points: [[60, 40], [240, 220]] },
      { id: "rB", type: "angleMark", vertex: [60, 220], from: [60, 40], to: [240, 220], r: 16, variant: "right" },
      { id: "pA", type: "point", at: [60, 40], r: 0, label: "A", labelOffset: [-28, -6] },
      { id: "pB", type: "point", at: [60, 220], r: 0, label: "B", labelOffset: [-28, -2] },
      { id: "pC", type: "point", at: [240, 220], r: 0, label: "C", labelOffset: [16, 4] },
    ],
  };
  // Known defects: a KaTeX math label next to <text> point labels (font mix) and a text label
  // pushed off the right edge of the canvas (edge).
  const bad = {
    ...clean,
    a11y: { title: "Synthetic broken figure for visual-check", description: "A synthetic triangle with a deliberately mixed font label set and a label clipped by the canvas edge. Fixture only." },
    elements: [
      ...clean.elements,
      { id: "mx", type: "math", at: [150, 120], latex: "x^2" },
      { id: "edgeT", type: "text", at: [292, 60], value: "clip" },
    ],
  };
  // The ruling-line exemption (owner ruling 2026-10-04): a letter ON a gv*/gh* line passes
  // label↔stroke; the same letter on an identical line without the marker id still fails.
  const rulingOf = (lineId, a11yTitle) => ({
    schema: "vibhaga.diagram", schemaVersion: 1, canvas: { width: 200, height: 200 },
    a11y: { title: a11yTitle, description: "One faint vertical line and the letter A centred on it. Fixture only." },
    elements: [
      { id: lineId, type: "line", points: [[100, 10], [100, 190]], stroke: { color: "#d1d5db", width: 1 } },
      { id: "lbA", type: "text", at: [100, 100], value: "A" },
    ],
  });
  const ruling = rulingOf("gv1", "Synthetic ruling line with a letter on it");
  const notRuling = rulingOf("ln1", "Synthetic faint line (no marker id) with a letter on it");
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "visual-check-selftest-"));
  const figures = [
    { id: "clean", doc: clean, source: "self-test", claims: null, outDir: path.join(outDir, "clean"), pngs: [], findings: [] },
    { id: "defective", doc: bad, source: "self-test", claims: null, outDir: path.join(outDir, "bad"), pngs: [], findings: [] },
    { id: "ruling", doc: ruling, source: "self-test", claims: null, outDir: path.join(outDir, "ruling"), pngs: [], findings: [] },
    { id: "notRuling", doc: notRuling, source: "self-test", claims: null, outDir: path.join(outDir, "notRuling"), pngs: [], findings: [] },
  ];
  for (const fig of figures) {
    const r = lib.parseVddDocument(fig.doc);
    if (r.ok) fig.parsed = r.value;
    else { fig.invalid = r.errors; fig.findings.push({ rule: "parse", severity: "fail", message: "self-test doc failed parse" }); }
  }
  await runBatch(figures, { out: outDir, widths: [320, 375], themes: ["light", "dark"], headed: flag("--headed") });
  const byId = Object.fromEntries(figures.map((f) => [f.id, f]));
  let ok = true;
  const t = (name, cond, extra = "") => { console.log(`${cond ? "PASS" : "FAIL"}  ${name}${extra ? " — " + extra : ""}`); if (!cond) ok = false; };
  t("clean figure: PASS", byId.clean.result.verdict === "PASS",
    byId.clean.result.findings.map((f) => f.message).join("; ") || "no findings");
  t("defective figure: FAIL", byId.defective.result.verdict === "FAIL");
  const badRules = new Set(byId.defective.result.findings.filter((f) => f.severity === "fail").map((f) => f.rule));
  t("defective fires font", badRules.has("font"), byId.defective.result.font && `math ×${byId.defective.result.font.math} + text ×${byId.defective.result.font.text}`);
  t("defective fires edge", badRules.has("edge"));
  // cqw overlay font: computed px = fontSizeU·pxPerUnit — measure() must hand back CANVAS units
  // (doc fontSize 18) at every width, not px that drift with the scale (320 vs 375 differ ~1.2×).
  const mathRows = byId.defective.result.labels.filter((r) => r.kind === "math");
  t("math label fontSizeU is canvas units at every width",
    mathRows.length === 2 && mathRows.every((r) => Math.abs(r.fontSizeU - 18) < 1),
    mathRows.map((r) => `${r.width}px→${r.fontSizeU}u`).join(", ") || "no math rows");
  t("clean figure drew on both themes", byId.clean.pngs.length === 4);
  t("letter over a gv* ruling line: PASS (exempt)",
    byId.ruling.result.verdict === "PASS",
    byId.ruling.result.findings.map((f) => f.message).join("; ") || "no findings");
  t("same letter over an unmarked faint line: FAIL stroke",
    byId.notRuling.result.verdict === "FAIL" &&
    byId.notRuling.result.findings.some((f) => f.rule === "stroke" && f.severity === "fail"),
    byId.notRuling.result.findings.map((f) => f.message).join("; "));
  console.log(ok ? "\nSELF-TEST PASS" : "\nSELF-TEST FAIL");
  process.exit(ok ? 0 : 1);
}

async function main() {
  if (flag("--self-test")) return selfTest();
  if (opt("--session") !== undefined) process.exit(await sessionMode());
  return batchMode();
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  main().catch((e) => die(e?.message ?? String(e)));
