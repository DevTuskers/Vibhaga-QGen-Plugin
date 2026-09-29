#!/usr/bin/env node
/**
 * S8 §6 check #10's MEASURING half — renders every inline `$…$` run through the REAL shared renderer
 * (`Vibhaga-Admin/src/lib/markdown/ContentMarkdown` + KaTeX, byte-identical with Web's) in Chromium and
 * reports the rendered width of each `.katex` span, so a borderline estimate from
 * `check-inline-math-width.py` becomes a number instead of a judgement.
 *
 *     cd <the Vibhaga umbrella root>
 *     node Vibhaga-Docs/.devin/skills/_maths-onboarding/measure-inline-math-width.mjs --fields fields.json [--min 250] [--box 301]
 *     node Vibhaga-Docs/.devin/skills/_maths-onboarding/measure-inline-math-width.mjs --runs '["\\sum fx = 1216", "44,\\ 47"]'
 *
 * `--fields` is the markdown gate's `[{id, field, text}]` shape (the same file `check-inline-math-width.py
 * --fields` reads). Every inline run in every field is rendered ALONE (so nothing wraps around it) at the
 * student body size (18 px) and measured with `getBoundingClientRect()`.
 *
 * THE BOX AND THE FONT SIZE DEPEND ON THE FIELD — read off Vibhaga-Web's own classes (2026-09-05):
 *   share page / study view: `main px-4` → 343 px at a 375 px viewport; `article p-5` + 1 px border → 301 px
 *   stem                `text-lg`  18 px   box 301          (`q/[id]/page.tsx:132`, `StudyView.tsx:91`)
 *   sub-part text       base       16 px   box 265 = 301 − 24 px label chip − 12 px gap   (`SubParts.tsx:79-87`)
 *   depth-2 part text   base       16 px   box 229 (another chip + gap)
 *   whole-question answer `text-sm` 14 px  box 301          (`AnswerBlock.tsx:77`, `RevealAnswer.tsx:136` px-5)
 *   sub-answer          `text-sm`  14 px   box 239 = 265 − the disclosure panel's `p-3` + 1 px border each side (`SubParts.tsx:134`)
 *   depth-2 sub-answer  `text-sm`  14 px   box 203
 * A field id of the form `question_text*` / `sq:*` / `sq2:*` / `a:*` / `sa:*` / `sa2:*` (the shape the
 * live-fields SQL emits — `2` marks depth 2) picks the row; anything else gets the stem's 18 px / 301.
 * `--box N` overrides every box; `--font N` every size.
 * A run at or over its box is CLIP, one within 25 px under it is TIGHT. Exit 1 on any CLIP.
 *
 * ⚠️ Font stack: the page loads no webfont, so Chromium falls back to a system sans for text inside
 * `\text{}`; KaTeX's own maths fonts are what the width mostly depends on and those are loaded from
 * Admin's node_modules. Treat a TIGHT result as a clip if the run holds a long `\text{}`.
 */
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const UMBRELLA = path.resolve(process.env.VIBHAGA_ROOT ?? path.join(HERE, "..", ".."));
const ADMIN = path.resolve(process.env.VIBHAGA_ADMIN ?? path.join(UMBRELLA, "Vibhaga-Admin"));
const args = process.argv.slice(2);
const opt = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
const die = (m) => { console.error(`measure-inline-math-width: ${m}`); process.exit(2); };
const ESBUILD = path.join(ADMIN, "node_modules/.bin/esbuild");
if (!fs.existsSync(ESBUILD)) die(`no esbuild at ${ESBUILD}`);

const INLINE = /(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/gs;
let runs = [];
if (opt("--runs")) runs = JSON.parse(opt("--runs")).map((t, i) => ({ id: `run${i}`, field: "-", latex: t }));
else if (opt("--fields")) {
  for (const f of JSON.parse(fs.readFileSync(opt("--fields"), "utf8"))) {
    const text = String(f.text ?? "");
    // skip display math blocks
    const noDisplay = text.replace(/\$\$[\s\S]*?\$\$/g, " ");
    for (const m of noDisplay.matchAll(INLINE)) runs.push({ id: f.id, field: f.field, latex: m[1] });
  }
} else die("pass --fields fields.json or --runs '[…]'");
const MIN = Number(opt("--min", 200));
const ROWS = { stem: [18, 301], part: [16, 265], part2: [16, 229], answer: [14, 301], subanswer: [14, 239], subanswer2: [14, 203] };
const rowOf = (field) => field?.startsWith("sq2:") ? ROWS.part2 : field?.startsWith("sq:") ? ROWS.part : field?.startsWith("sa2:") ? ROWS.subanswer2 : field?.startsWith("sa:") ? ROWS.subanswer : field?.startsWith("a:") ? ROWS.answer : ROWS.stem;
for (const r of runs) { const [fs, box] = rowOf(r.field); r.font = Number(opt("--font", fs)); r.box = Number(opt("--box", box)); }

const CACHE = path.join(os.tmpdir(), "vibhaga-vdd-check"); fs.mkdirSync(CACHE, { recursive: true });
const NM = path.join(CACHE, "node_modules"); if (!fs.existsSync(NM)) fs.symlinkSync(path.join(ADMIN, "node_modules"), NM, "dir");
const stamp = fs.statSync(path.join(ADMIN, "src/lib/markdown/ContentMarkdown.tsx")).mtimeMs.toFixed(0);
const ENTRY_SRC = `import { createRoot } from "react-dom/client";
import { ContentMarkdown } from "@/lib/markdown/ContentMarkdown";
const runs = (window as any).__RUNS__ as {i:number, latex:string, font:number}[];
const host = document.getElementById("host")!;
for (const r of runs) {
  const d = document.createElement("div"); d.className = "row"; d.dataset.i = String(r.i); d.style.fontSize = r.font + "px"; host.appendChild(d);
  createRoot(d).render(<ContentMarkdown text={"$" + r.latex + "$"} variant="block" tableLabel="Table" />);
}
(window as any).__READY__ = true;
`;
const BUNDLE = path.join(CACHE, `md-${stamp}-${crypto.createHash("sha1").update(ENTRY_SRC).digest("hex").slice(0, 8)}.js`);
if (!fs.existsSync(BUNDLE)) {
  const entry = path.join(CACHE, "md-entry.tsx");
  fs.writeFileSync(entry, ENTRY_SRC);
  execFileSync(ESBUILD, [entry, "--bundle", "--format=iife", "--jsx=automatic", `--outfile=${BUNDLE}`, `--alias:@=${path.join(ADMIN, "src")}`,
    "--loader:.css=empty", "--define:process.env.NODE_ENV=\"production\"", "--resolve-extensions=.tsx,.ts,.js", "--log-level=error"]);
}
const katexCss = fs.readFileSync(path.join(ADMIN, "node_modules/katex/dist/katex.min.css"));
const fontsDir = path.join(ADMIN, "node_modules/katex/dist/fonts");
const html = `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/katex.min.css">
<style>body{margin:0;font:18px/1.6 Inter,system-ui,-apple-system,"Noto Sans Sinhala",sans-serif;color:#1f2937}.row{width:2000px;white-space:nowrap;margin:2px 0}.katex{white-space:nowrap}</style></head>
<body><div id="host"></div><script>window.__RUNS__=${JSON.stringify(runs.map((r, i) => ({ i, latex: r.latex, font: r.font })))};</script><script src="/bundle.js"></script></body></html>`;
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split("?")[0]);
  if (u === "/") { res.setHeader("content-type", "text/html"); return res.end(html); }
  if (u === "/katex.min.css") { res.setHeader("content-type", "text/css"); return res.end(katexCss); }
  if (u === "/bundle.js") { res.setHeader("content-type", "text/javascript"); return res.end(fs.readFileSync(BUNDLE)); }
  if (u.startsWith("/fonts/")) { const p = path.join(fontsDir, path.basename(u)); if (fs.existsSync(p)) return res.end(fs.readFileSync(p)); }
  res.statusCode = 404; res.end();
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const { chromium } = await import(pathToFileURL(path.join(ADMIN, "node_modules/playwright/index.mjs")).href);
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 375, height: 800 } });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  // createRoot().render is asynchronous: wait until every row has painted its .katex (or given up), then let the fonts settle.
  await page.waitForFunction(() => window.__READY__ && [...document.querySelectorAll(".row")].every((d) => d.querySelector(".katex, .katex-error") || d.textContent.length) && document.fonts.status === "loaded", null, { timeout: 60000 });
  await page.waitForTimeout(500);
  const widths = await page.evaluate(() => [...document.querySelectorAll(".row")].map((d) => {
    const k = d.querySelector(".katex"); return k ? Math.round(k.getBoundingClientRect().width * 10) / 10 : null;
  }));
  // ⚠️ Count CLIP over EVERY run, BEFORE `--min` filters what is printed. Until 2026-09-06 the count ran inside the
  // filtered loop, so `--min 9999` printed "0 CLIP" on any input — a gate that could not fail (TRAPS T13/T114).
  const all = runs.map((r, i) => ({ ...r, width: widths[i] }));
  const clips = all.filter((r) => r.width !== null && r.width >= r.box).length;
  const rows = all.filter((r) => r.width === null || r.width >= MIN || r.width >= r.box).sort((a, b) => ((b.width ?? 0) - b.box) - ((a.width ?? 0) - a.box));
  for (const r of rows) {
    const tag = r.width === null ? "NORENDER" : r.width >= r.box ? "CLIP    " : r.width >= r.box - 25 ? "TIGHT   " : "fits    ";
    console.log(`${tag} ${String(r.width ?? "-").padStart(6)} px of ${r.box} @${r.font}px  ${r.id}  [${r.field.length > 40 ? r.field.slice(0, 12) + "…" + r.field.slice(-9) : r.field}]  $${r.latex.length > 80 ? r.latex.slice(0, 77) + "…" : r.latex}$`);
  }
  console.log(`measure-inline-math-width: ${runs.length} run(s) rendered · ${clips} CLIP (at or over the field's box, counted over ALL runs) · showing ≥ ${MIN} px (CLIP rows always shown)`);
  process.exitCode = clips ? 1 : 0;
} finally { await browser.close(); server.close(); }
