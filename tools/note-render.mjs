#!/usr/bin/env node
/**
 * note-render.mjs — render a lesson note's English and Sinhala bodies in the REAL Admin
 * `/lesson-notes` preview and measure them at a desktop column AND a 375 px content column.
 *
 *     node tools/note-render.mjs --work DIR --lesson <uuid> --grade N [--subject Mathematics]
 *          [--stored] [--base http://localhost:3000] [--cdp http://localhost:29229]
 *          [--admin PATH] [--out DIR]
 *
 * Default (draft) mode pastes WORK/en.md, si.md and diagrams.json into the editor WITHOUT saving:
 * every non-GET `/api/admin/**` request is aborted, so the run cannot write. `--stored` renders
 * what the API returns and also requires the "Draft · Version N" status line.
 *
 * Needs a running Admin dev server at --base (`npm run dev -- --hostname localhost` in
 * Vibhaga-Admin with the Access pair in its environment). Admin resolution: --admin >
 * VIBHAGA_ADMIN env > <plugin>/../Vibhaga-Admin; sign-in reads VIBHAGA_ADMIN_EMAIL/PASSWORD from
 * VIBHAGA_ADMIN_ENV or Admin's .env.local (never printed). Playwright comes from Admin's
 * node_modules; --cdp attaches to an existing Chrome instead of launching Chromium.
 *
 * Expected counts come from the source files: maths spans, `$$` displays, `<table`s, `## `
 * headings and diagrams. FAIL (exit 1) on any KaTeX error, count mismatch, exposed `$`, element
 * overflowing horizontally at either width, or (stored) a non-draft status. Screenshots go to
 * OUT (default WORK/shots): <mode>-<lang>.png and <mode>-<lang>-375.png. JSON metrics on stdout.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const PLUGIN = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function expectedCounts(md, diagrams) {
  const display = (md.match(/^\$\$[ \t]*$/gm) || []).length / 2;
  const noDisplay = md.replace(/^\$\$[ \t]*\n[\s\S]*?^\$\$[ \t]*$/gm, "");
  const inline = (noDisplay.match(/\$[^$\n]+\$/g) || []).length;
  return {
    math: inline + display, display,
    tables: (md.match(/<table\b/gi) || []).length,
    h2: (md.match(/^## /gm) || []).length,
    figures: diagrams.length,
  };
}

export function failures(m, exp, { stored = false } = {}) {
  if (typeof m !== "object" || !m) return ["note preview article not found"];
  const bad = [];
  if (m.errors) bad.push(`${m.errors} KaTeX error(s)`);
  for (const k of ["math", "display", "tables", "h2", "figures"])
    if (m[k] !== exp[k]) bad.push(`${k} ${m[k]} ≠ expected ${exp[k]}`);
  if (m.rawDollar) bad.push(`${m.rawDollar} exposed $`);
  if (m.overflow.length) bad.push(`overflow: ${m.overflow.join(" | ")}`);
  if (m.overflow375.length) bad.push(`overflow at 375 px: ${m.overflow375.join(" | ")}`);
  if (stored && !/^Draft\b/.test(m.status || "")) bad.push(`status ${JSON.stringify(m.status)} is not Draft`);
  return bad;
}

function args(argv) {
  const a = { subject: "Mathematics", base: "http://localhost:3000", stored: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === "--stored") a.stored = true;
    else if (k.startsWith("--") && i + 1 < argv.length) a[k.slice(2)] = argv[++i];
    else throw new Error(`unknown argument ${k}`);
  }
  if (!a.work || !a.grade || !UUID.test(a.lesson || "")) throw new Error("need --work DIR --lesson <uuid> --grade N");
  return a;
}

function readEnv(file) {
  return Object.fromEntries(fs.readFileSync(file, "utf8").split("\n")
    .map((l) => l.match(/^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$/)).filter(Boolean)
    .map((m) => [m[1], m[2].replace(/^["']|["']$/g, "")]));
}

function measure() {
  const note = document.querySelector('article[lang="en"], article[lang="si"]');
  if (!note) return null;
  const count = (s) => [...note.querySelectorAll(s)].filter((x) => !x.closest("figure")).length;
  const over = () => [...note.querySelectorAll("*")]
    .filter((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX !== "visible")
    .map((e) => `${e.scrollWidth}/${e.clientWidth} ${e.innerText.slice(0, 40).replace(/\s+/g, " ")}`);
  return {
    language: note.lang, math: count(".katex"), display: count(".katex-display"),
    errors: note.querySelectorAll(".katex-error").length, tables: count("table"),
    figures: note.querySelectorAll("figure").length, h2: count("h2"), callouts: count("blockquote"),
    width: Math.round(note.getBoundingClientRect().width), overflow: over(),
    rawDollar: (note.innerText.match(/\$/g) || []).length,
    status: document.body.innerText.match(/(Draft|Verified)[^\n]{0,30}Version[^\n]{0,10}/)?.[0] ?? null,
  };
}

async function main() {
  const a = args(process.argv.slice(2));
  const admin = path.resolve(a.admin || process.env.VIBHAGA_ADMIN || path.join(PLUGIN, "..", "Vibhaga-Admin"));
  const env = readEnv(process.env.VIBHAGA_ADMIN_ENV || path.join(admin, ".env.local"));
  const work = path.resolve(a.work), out = path.resolve(a.out || path.join(work, "shots"));
  fs.mkdirSync(out, { recursive: true });
  const diagrams = JSON.parse(fs.readFileSync(path.join(work, "diagrams.json"), "utf8"));
  const { chromium } = await import(pathToFileURL(path.join(admin, "node_modules", "playwright", "index.mjs")).href);
  const browser = a.cdp ? await chromium.connectOverCDP(a.cdp) : await chromium.launch();
  const ctx = a.cdp ? browser.contexts()[0] : await browser.newContext();
  const page = await ctx.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/api/admin/**", (r) => (["GET", "HEAD", "OPTIONS"].includes(r.request().method()) ? r.continue() : r.abort()));
  const open = async () => { await page.goto(`${a.base}/lesson-notes`); await page.waitForLoadState("networkidle"); };
  await open();
  if (page.url().includes("/login")) {
    await page.fill('input[type="email"]', env.VIBHAGA_ADMIN_EMAIL);
    await page.fill('input[type="password"]', env.VIBHAGA_ADMIN_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL((u) => !u.toString().includes("/login"), { timeout: 30000 });
    await open();
  }
  const sel = page.locator("select");
  await sel.nth(0).selectOption(String(a.grade));
  await sel.nth(1).selectOption(a.subject);
  await sel.nth(2).selectOption(a.lesson);
  await page.waitForTimeout(2500);
  const mode = a.stored ? "stored" : "preview";
  const results = {}, bad = [];
  for (const [tab, file, lang] of [["English", "en.md", "en"], ["Sinhala", "si.md", "si"]]) {
    const md = fs.readFileSync(path.join(work, file), "utf8");
    await page.getByRole("tab", { name: tab }).click();
    if (!a.stored) {
      const expand = page.getByRole("button", { name: "Expand editor" });
      if (await expand.count()) await expand.first().click();
      await page.locator(`textarea[lang="${lang}"]`).fill(md);
      const d = page.locator("textarea").nth(1), want = JSON.stringify(diagrams, null, 2);
      if (JSON.stringify(JSON.parse((await d.inputValue()) || "null")) !== JSON.stringify(diagrams)) await d.fill(want);
    }
    await page.waitForTimeout(1500);
    const m = await page.evaluate(measure);
    const art = page.locator("article[lang]").first();
    if (m) {
      await art.screenshot({ path: path.join(out, `${mode}-${lang}.png`) });
      await page.evaluate(() => { const n = document.querySelector("article[lang]"); n.style.width = n.style.maxWidth = "375px"; });
      await page.waitForTimeout(500);
      m.overflow375 = (await page.evaluate(measure)).overflow;
      await art.screenshot({ path: path.join(out, `${mode}-${lang}-375.png`) });
      await page.evaluate(() => { const n = document.querySelector("article[lang]"); n.style.width = n.style.maxWidth = ""; });
    }
    results[lang] = m;
    for (const f of failures(m, expectedCounts(md, diagrams), { stored: a.stored })) bad.push(`${lang}: ${f}`);
  }
  await page.close();
  if (!a.cdp) await browser.close();
  console.log(JSON.stringify(results, null, 1));
  for (const b of bad) console.log(`note-render: FAIL ${b}`);
  console.log(bad.length ? "note-render: NOT ok" : `note-render: ok (${mode}; screenshots in ${out})`);
  process.exit(bad.length ? 1 : 0);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main().catch((e) => { console.error(`note-render: ${e.message}`); process.exit(2); });
}
