#!/usr/bin/env node
/**
 * S9's GENERATIVE MARKDOWN GATE — the blocking markup check for one authored batch.
 *
 *     cd <the Vibhaga umbrella root>
 *     node Vibhaga-Docs/.devin/skills/_maths-onboarding/markdown-gate.mjs --self-test
 *     node Vibhaga-Docs/.devin/skills/_maths-onboarding/markdown-gate.mjs --fields authored.json
 *
 * The two app repos are found four levels up from this file. Override either when they are not
 * beside `Vibhaga-Docs` — a worktree, a sandbox — and RELATIVE IS FINE, resolved against the cwd:
 *
 *     VIBHAGA_WEB=Vibhaga-Web VIBHAGA_ADMIN=Vibhaga-Admin node …/markdown-gate.mjs --self-test
 *     VIBHAGA_ROOT=/tmp/some-sandbox node …/markdown-gate.mjs --self-test
 *
 * ⚠️ WHY THIS IS NOT A PATTERN LIST. `technical/content-text-syntax.md` records that the hazard
 * list was found to be an undercount FOUR ROUNDS RUNNING (5 → 12 → 19 → 24, then Phase 0's own
 * critiques added 20 more). A hand-maintained list of shapes is therefore guaranteed to be short by
 * the time anyone reads it. The core here is GENERATIVE: it asks the author's own source to survive
 * a round trip through the renderer's own parser, so a construct nobody has thought of is caught by
 * the same rule as one that is documented.
 *
 * ⚠️ AND IT IS NOT THE CHARACTER DIFF. The obvious generative rule — compare non-whitespace
 * character counts of source against render — was built and measured to reject EVERY legitimate
 * table, bullet list and numbered list, because `|---|---|` and `- ` are deletions by definition.
 * Do not re-derive it. See the same document's § "generative".
 *
 * THREE LAYERS, all three load-bearing.
 *
 * ⚠️⚠️ **THE PER-LAYER NUMBERS ARE NOT WRITTEN DOWN ANYWHERE. RUN `--ablate`.** They have been
 * transcribed twice and been wrong twice — the second time in the very commit that added `--ablate`
 * and claimed they were computed, which missed the two cells that commit's OWN other change (`n2a`)
 * had moved. A figure that has rotted twice inside one phase does not belong in prose; the only
 * durable statement is the one that survives every re-measurement:
 *
 *     dropping ANY ONE layer loses vectors that no other layer catches.
 *
 * `--ablate` prints the current contribution of each of the seven combinations, blocking and
 * surfaced, from the live vector table.
 *
 * SEVERITY. `block` refuses the publish; `advice` is recorded and does NOT fail the paper — the
 * same two-tier shape `checkDiagram()` already has in this gate (S9 §4.2).
 */
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// ── Locating the app repos ─────────────────────────────────────────────────────────────────────
// This file lives at <umbrella>/Vibhaga-QGen-Plugin/tools/, so the umbrella root is one level up —
// the directory holding this plugin checkout. Both are overridable, because a checkout does not
// always sit beside its siblings.
// ⚠️ `fileURLToPath`, NEVER `new URL(...).pathname` — the latter is PERCENT-ENCODED, so one space
// or one non-ASCII character in the checkout path yields `/My%20Repo/...`, which exists nowhere.
// ⚠️ `path.resolve` EVERY override: `createRequire` below throws `ERR_INVALID_ARG_VALUE` on a
// relative path, and `fs.existsSync` does not, so `VIBHAGA_WEB=Vibhaga-Web` sailed past this file's
// own `die()` and crashed with a bare stack trace instead. A gate that cannot run must say so in its
// own words (§0.5). ⚠️ The override form was also not written down anywhere — it is in the usage
// block above now, because a form nobody documented is a form nobody tested.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const UMBRELLA = path.resolve(process.env.VIBHAGA_ROOT ?? path.resolve(HERE, ".."));
const WEB = path.resolve(process.env.VIBHAGA_WEB ?? path.join(UMBRELLA, "Vibhaga-Web"));
const ADMIN = path.resolve(process.env.VIBHAGA_ADMIN ?? path.join(UMBRELLA, "Vibhaga-Admin"));

function die(msg) {
  // S9 §0.5: a gate that cannot run its check FAILS the paper. It never passes quietly.
  console.error(`\nGATE CANNOT RUN — this is a FAIL, not a skip.\n  ${msg}\n`);
  process.exit(2);
}

if (!fs.existsSync(path.join(WEB, "package.json"))) die(`no Vibhaga-Web at ${WEB} (set VIBHAGA_WEB)`);
if (!fs.existsSync(path.join(ADMIN, "package.json"))) die(`no Vibhaga-Admin at ${ADMIN} (set VIBHAGA_ADMIN)`);

// ── ⚠️ THE CROSS-REPO CHECK — the only one that exists anywhere (TRAPS T56) ────────────────────
// `lockstep.test.tsx` hashes the four shared files against a constant committed IN THE SAME REPO, so
// it catches "edited one and forgot the constant" inside one checkout and is blind to a one-sided
// landing. This process is the one place in the programme that holds BOTH checkouts at once, so it is
// the only place the comparison can live. A divergence makes the gate's own answer unsound — L1 reads
// WEB's copy while L2 reads ADMIN's `markdownHazards.ts`, so it would be describing one renderer and
// one author-warning from different releases — hence a FAIL, not a warning.
//
// ⚠️ WHAT IS AND IS NOT INVISIBLE TO THE SUITES, MEASURED — because the first version of this comment
// got it wrong. Gutting Admin's `vectors.ts` to 36 bytes turns **6 tests RED** in Admin's own suite —
// `lockstep`'s `length === 163`, `MathText`'s projection, three in `markdownHazards.vectors`, and the
// checksum assertion itself; 5 if the digest is recomputed with it — so that mutation was never the
// argument. The one that IS invisible is a **comment-only divergence**:
// append one comment line to Admin's copy, recompute Admin's own digest, and both suites stay green
// (1523/1523 and 801/801) while `diff` reports the files DIVERGED. That is the case this check exists
// for, and it is exactly the shape of the edit this phase itself landed.
//
// ⚠️ The corpus fixture is in the list even though it is not checksummed: Admin's
// `markdownHazards.corpus.test.ts` calls it "copied byte-for-byte … `diff` is the drift check", the
// gate reads it from WEB only, and markdown Phase 6 half-landed exactly this file before a critique
// caught it. A declared byte-identical file with no tripwire is precisely what this check is for.
const SHARED_MARKDOWN_FILES = [
  "config.ts",
  "vectors.ts",
  "ContentMarkdown.tsx",
  "lockstep.test.tsx",
  "__fixtures__/live-corpus.json",
];
{
  const diverged = [];
  for (const name of SHARED_MARKDOWN_FILES) {
    const w = path.join(WEB, "src/lib/markdown", name);
    const a = path.join(ADMIN, "src/lib/markdown", name);
    if (!fs.existsSync(w) || !fs.existsSync(a)) die(`shared file missing: ${!fs.existsSync(w) ? w : a}`);
    if (!fs.readFileSync(w).equals(fs.readFileSync(a))) diverged.push(name);
  }
  if (diverged.length) {
    die(
      `Vibhaga-Web and Vibhaga-Admin DISAGREE on ${diverged.length} of the ${SHARED_MARKDOWN_FILES.length} ` +
        `byte-identical shared renderer files:\n    ${diverged.join("\n    ")}\n` +
        `  These must be byte-identical (TRAPS T56). This is a HALF-LANDED cross-repo change: one repo\n` +
        `  has the edit and the other does not, and each repo's own checksum test stays GREEN because it\n` +
        `  only ever compares that repo to its own committed constant. An author's preview and a\n` +
        `  student's page can now render the same content differently.\n` +
        `  Fix: land the identical edit in both repos and recompute SHARED_CONTRACT_SHA256 in both.\n` +
        `  Check: diff -u ${path.join(WEB, "src/lib/markdown")}/<file> ${path.join(ADMIN, "src/lib/markdown")}/<file>`,
    );
  }
}

const req = createRequire(path.join(WEB, "package.json"));
const load = async (pkg) => {
  let resolved;
  try {
    resolved = req.resolve(pkg);
  } catch {
    // ⚠️ `remark-stringify` is NOT a declared dependency of either app. It is present only as a
    // direct dependency of `remark-gfm`, which both DO declare. That is reliable today and could
    // stop being true at a remark-gfm major — so the gate says so rather than silently degrading.
    die(`cannot resolve '${pkg}' from ${WEB}. Run \`npm ci\` there.` +
      (pkg === "remark-stringify" ? "\n  NOTE: remark-stringify is undeclared; it arrives via remark-gfm." : ""));
  }
  return import(pathToFileURL(resolved).href);
};

const { unified } = await load("unified");
const remarkParse = (await load("remark-parse")).default;
const remarkGfm = (await load("remark-gfm")).default;
const remarkMath = (await load("remark-math")).default;
const remarkBreaks = (await load("remark-breaks")).default;
const remarkStringify = (await load("remark-stringify")).default;

// ── Layer 2 — Admin's own author-warning triggers, bundled from source ─────────────────────────
// S9 §4: wire in the gates that already exist; do not rebuild them. A second copy of 29 construct
// triggers would drift from the one the author actually sees, which is the whole point of reuse.
async function loadHazards() {
  const esbuild = path.join(ADMIN, "node_modules/.bin/esbuild");
  const fallback = path.join(WEB, "node_modules/.bin/esbuild");
  const bin = fs.existsSync(esbuild) ? esbuild : fs.existsSync(fallback) ? fallback : null;
  if (!bin) die(`no esbuild in either repo's node_modules. Run \`npm ci\` in ${ADMIN}.`);
  const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "vib-gate-")), "hazards.mjs");
  const src = path.join(ADMIN, "src/lib/markdownHazards.ts");
  if (!fs.existsSync(src)) die(`no ${src} — is Vibhaga-Admin on a ref that has markdown Phase 1?`);
  try {
    execFileSync(bin, [src, "--bundle", "--format=esm", "--platform=node", `--outfile=${out}`, "--log-level=warning"], {
      stdio: ["ignore", "inherit", "inherit"],
    });
  } catch (e) {
    die(`could not bundle ${src}: ${e.message}`);
  }
  return import(pathToFileURL(out).href);
}
const { findMarkdownHazards } = await loadHazards();

// ── The pipeline, and the round trip ───────────────────────────────────────────────────────────
const STRINGIFY_OPTIONS = { bullet: "-", emphasis: "*", strong: "*", rule: "-" };
const serialiser = unified()
  .use(remarkParse).use(remarkGfm).use(remarkMath).use(remarkBreaks)
  .use(remarkStringify, STRINGIFY_OPTIONS);
const parser = unified().use(remarkParse).use(remarkGfm).use(remarkMath).use(remarkBreaks);
const parse = (s) => parser.runSync(parser.parse(s));

/** N1 — collapse table-cell padding and delimiter-row width. */
const n1 = (s) => s.split("\n").map((line) => {
  if (!line.includes("|")) return line;
  const cells = line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|");
  // ⚠️ NOT `/^\s*\|?[\s:|-]+\|?\s*$/`. `\s*`, `\|?` and `[\s:|-]+` all overlap, so a FAILING
  // pipe-bearing line of whitespace backtracks quadratically: measured 15 ms at 4 000 characters,
  // 219 ms at 16 000, 1 958 ms at 50 000 — and it runs on BOTH sides of every round trip. Every
  // alternative branch is a subset of `[\s:|-]`, so this accepts exactly the same language;
  // verified over 300 000 random strings from `[ \t:|-x0]`, zero disagreements.
  const isDelim = /^[\s:|-]+$/.test(line) && line.includes("-");
  return "|" + cells.map((c) => (isDelim ? c.trim().replace(/-+/g, "-") : c.trim())).join("|") + "|";
}).join("\n");
/**
 * N2 — strip escapes the serialiser ADDS.
 * ⚠️ `|` IS IN THE CLASS, and the contract's own list omits it. `remark-stringify` drops an author's
 * `\|` in PROSE (a lone pipe outside a table needs no escape), so the source kept the backslash, the
 * output did not, and `key: 2 \| 3 means 23` was BLOCKED — a legitimate escape, rendering exactly as
 * authored, and the one this suite's sibling skills tell authors to write. Invisible to the binding
 * test because no pinned legitimate construct and none of the 300 live strings contains a `\|`.
 */
const n2 = (s) => s.replace(/\\([=\-+*_#>.~[\]`$])/g, "$1");
/**
 * N2a — the pipe escape, unstripped BEFORE N1 for the same reason N3 runs before it. N1 rebuilds any
 * pipe-bearing line from its `|`-split cells, so by the time N2 could act the backslash is already
 * inside a cell and the two sides have split differently. Run here, both sides split identically.
 */
const n2a = (s) => s.replace(/\\\|/g, "|");
/** N3 — strip an ADDED end-of-line backslash (remark-breaks round-trips a soft break that way). */
const n3 = (s) => s.replace(/\\$/gm, "");
/** N4 — collapse leading, trailing and repeated whitespace. */
const n4 = (s) => s.replace(/[ \t]+/g, " ").replace(/^[ \t]+/gm, "").replace(/[ \t]+$/gm, "").trim();

/**
 * ⚠️ N3 RUNS BEFORE N1, AND THE ORDER IS LOAD-BEARING. The contract numbers the normalisations and
 * does not order them. N1 wraps every pipe-bearing line in edge pipes; if the serialiser's
 * end-of-line `\` is still present when it does, the backslash ends up INSIDE the last cell
 * (`…\|`) where N3's `\$` anchor can no longer see it.
 * ⚠️ THE JUSTIFICATION MOVED. Measured 2026-08-22, pre-N2a, N1-first made two live strings unstable.
 * Re-measured 2026-08-24 with this pipeline it costs 0 of 300 — N2a strips the pipe escape first, and
 * `61180663` is a real table since Phase 6. What keeps the rule is the legitimate set: N1-first blocks
 * `L12` (`key: 2 \| 3 means 23`), the escape the sibling skills tell authors to write.
 */
/**
 * N5 — drop a blank line the SERIALISER inserts immediately before a table row.
 * ⚠️ Narrow on purpose. `remark-stringify` always puts a blank line between a paragraph and a
 * following table, so `Complete this:` + the table on the next line — which the vector table's own
 * note calls legitimate (*"a table needs NO blank line before it — it interrupts a paragraph
 * cleanly"*) — read as unstable, i.e. a false positive on THE canonical shape for this product.
 * Measured alternatives: collapsing ALL newline runs also fixes it and costs 5 of the ⚠️ vectors
 * the round trip catches (⚠️ **this said "5 of the 46" — a per-layer number this file's own header
 * forbids writing down, and 46 is the PRE-`n2a` value; `--ablate` reports L1 = 40. Third instance of
 * that slip, in the comment beside the normalisation that moved it**) —
 * vectors the round trip catches; this form costs **0**. It cannot mask "a table then a sentence"
 * (the sentence does not start with `|`) or two tables merged by `mergeUp` (no blank line at all).
 */
const n5 = (s) => s.replace(/\n{2,}(?=\|)/g, "\n");

const normalise = (s) => n5(n4(n2(n1(n2a(n3(s))))));

function roundTripStable(input) {
  let out;
  try {
    out = String(serialiser.processSync(input));
  } catch {
    return false; // a source the renderer's own parser cannot serialise is itself a finding
  }
  return normalise(input) === normalise(out);
}

// ── The gate ───────────────────────────────────────────────────────────────────────────────────
/**
 * `bulletList` is DOWNGRADED to `advice`, and it is the only trigger that is. Of the 29
 * `MarkdownHazardId`s it is the only one that fires on the acceptance test's own legitimate set (a
 * plain bullet list), so it cannot block. ⚠️ **Measured cost of the downgrade: ZERO ⚠️ vectors go
 * dark** — it fires on 11 vector rows, 8 of them ⚠️, and all 8 are blocked by another layer
 * anyway (`- $\rule{20em}{1em}$` ×3 by `L3-rule` and by `M1`). An earlier revision of this comment
 * said "exactly ONE", which does not reproduce.
 * ⚠️ It must still be REPORTED, not silenced: it is the only signal a field whose FIRST line is
 * `- 5 = -2` has, and that shape loses the minus sign with nothing else firing at all.
 */
const ADVISORY_TRIGGERS = new Set(["bulletList"]);

const walk = (node, fn) => { fn(node); for (const c of node.children ?? []) walk(c, fn); };

/**
 * ⚠️ `layers` exists so the per-layer contribution is COMPUTED, never transcribed. The numbers in
 * this file's header were hand-copied once and were wrong within a day of the severities changing —
 * three of the seven, plus the sentence derived from them. `--ablate` prints them.
 */
export function gateFindings(rawSrc, layers = { L1: true, L2: true, L3: true }) {
  /**
   * ⚠️ NORMALISE LINE ENDINGS FIRST, BEFORE ANY LAYER. `micromark` treats CRLF and LF alike, so the
   * RENDER is byte-identical — but nothing here stripped the `\r`, and N4 collapses `[ \t]` only, so
   * the carriage return survived into the comparison. Measured: **43 of the 45** multi-line live
   * strings and 4 of the 9 legitimate constructs were blocked as CRLF while clean as LF, with a
   * message no author could act on. Tables happened to survive because N1 rebuilds pipe-bearing
   * lines from `line.trim()` — an accident, not a decision. The realistic producer of a `--fields`
   * batch is a paste out of a PDF or Word, so this is the common case, not the exotic one.
   */
  // ⚠️ REFUSE a non-string rather than coerce one. `String(123)` gates the characters "123" and
  // reports clean, so a batch producer bug reads as clean content. The guard was added to `--fields`
  // first and left off the EXPORTED function, which is the one a consumer calls.
  if (typeof rawSrc !== "string") throw new TypeError(`gateFindings expects a string, got ${rawSrc === null ? "null" : typeof rawSrc}`);
  const src = rawSrc.replace(/\r\n?/g, "\n");
  const out = [];
  const block = (code, detail) => out.push({ code, detail, severity: "block" });
  const advise = (code, detail) => out.push({ code, detail, severity: "advice" });

  // ── L1 · the generative core ──
  // ⚠️ Carry the DIVERGENCE, not just the verdict. This is the most frequent blocking finding
  // (68 of the vector hits), and "does not survive parse→serialise" is the least actionable string
  // an author could be handed — the data is right here.
  if (layers.L1 && !roundTripStable(src)) {
    let a = "", b = "";
    try { a = normalise(src); b = normalise(String(serialiser.processSync(src))); } catch { /* reported below */ }
    let i = 0; while (i < a.length && i < b.length && a[i] === b[i]) i++;
    block("M1-round-trip-unstable", a || b
      ? `diverges at offset ${i}: you wrote ${JSON.stringify(a.slice(Math.max(0, i - 20), i + 30))}, markdown makes ${JSON.stringify(b.slice(Math.max(0, i - 20), i + 30))}`
      : "the renderer's own parser cannot serialise this source");
  }

  // ── L2 · the triggers the author already sees ──
  let tree = null;
  try {
    tree = parse(src);
    if (layers.L2) for (const h of findMarkdownHazards(src, tree)) {
      // ⚠️ `else advise` — NOT silence. Without it, a trigger in the set produced no finding of any
      // severity, and `- 5 = -2` ALONE (the spec's headline hazard, first line of a field) was
      // completely unflagged: a list round-trips stably, so L1 is silent too, and the two-line form
      // is only caught because of the line above it. A bare leading `- ` in a sub-answer is exactly
      // how a subtraction step or a vertical sum continues.
      if (ADVISORY_TRIGGERS.has(h.id)) advise(`M2-${h.id}`, `line ${h.line}`);
      else block(`M2-${h.id}`, `line ${h.line}`);
    }
  } catch (e) {
    block("M2-unparseable", e.message);
  }

  // ── L3 · what neither layer above can see ──
  /**
   * ⚠️ THE TWO PARITY CHECKS ARE `advice`, NOT `block`, AND THE REASON IS A CONTRADICTION INSIDE
   * `vectors.ts` THAT NO PARITY RULE CAN RESOLVE. `oops $unterminated` is marked ⚠️; `Rs. $500
   * profit` is declared *"legitimate and must survive"* — and they are the SAME shape: one
   * unescaped, unpaired delimiter in prose. Neither loses anything at render (both are literal
   * text); what an odd delimiter costs is the OG/`<title>` sweep in `plainText()`. Blocking would
   * refuse `Rs. $500 profit`, `US $50 ක් රුපියල් වලට හරවන්න.` and every currency-conversion
   * question in an O/L paper. ⚠️ **The same false positive is latent in §3.1's `G4` as specified**,
   * which this restates — recorded there too.
   * The shapes that genuinely DO lose content keep blocking: an empty `` `` `` wrapper below, the
   * blank-line-in-a-wrapper leak (`M2-codeSpanBlankLine`) and prose swallowed into maths
   * (`L3-math-swallowed-prose`).
   */
  if (!layers.L3) return out;
  const ticks = (src.match(/`/g) ?? []).length;
  if (ticks % 2 === 1) advise("L3-backtick-odd", `${ticks} backticks — the survivor is literal text, and plainText() sweeps it`);
  if (/(^|[^`])``([^`]|$)/.test(src)) block("L3-backtick-empty", "an empty `` wrapper reaches the student as two characters");

  // The `[^` gate (0010 PD-13). `0011` removed footnotes at the mdast level and RESTORES the source
  // text, so nothing is lost — this stays as the nudge the contract says to keep it as.
  if (src.includes("[^")) advise("L3-footnote-marker", "`[^` — footnotes are stripped and the source restored, never rendered");

  // S9's own G4, restated here so the markdown gate is self-contained (TRAPS T14/T30).
  const dollars = (src.match(/(?<!\\)\$/g) ?? []).length;
  if (dollars % 2 === 1) advise("L3-dollar-odd", `${dollars} unescaped $ — legitimate as currency, but plainText() sweeps it from the OG title`);

  // ⚠️ An ODD run of backslashes, not just a lone one: `\\\` at end of line is a literal `\` plus a
  // hard break, and the third character is still deleted. `(^|[^\\])\\$` missed every run above 1.
  if (/(?<!\\)(?:\\\\)*\\$/m.test(src)) block("L3-backslash-eol", "a line ends in an odd run of `\\` — the last one is a hard break and is deleted");

  if (tree) {
    /**
     * ⚠️ EVERY WALKED FINDING CARRIES ITS LINE — and that is not cosmetic, it is what makes the dedupe
     * below per-OCCURRENCE. Most L3 details are constant strings, so deduping on `code + detail` alone
     * collapsed eight task-list items, or six distinct links, into ONE un-locatable finding: strictly
     * worse than the six it replaced. Every `M2-*` has carried a line since Phase 1; no `L3-*` did.
     */
    const at = (n) => (n?.position ? ` (line ${n.position.start.line})` : "");
    walk(tree, (n) => {
      // ⚠️ Read raw HTML off the mdast `html` NODE, never by regexing the source: a tag inside a
      // code span (`` `<script>alert(1)</script>` ``) is literal by design and the vector table
      // marks that row ✅ SAFE. A source regex flags it and is wrong.
      if (n.type === "html") block("L3-raw-html", `${JSON.stringify(String(n.value).slice(0, 30))} is escaped to literal text, never rendered${at(n)}`);

      if (n.type === "image") block("L3-image-alt-deleted", `![${n.alt ?? ""}](…) — an image is VOID, so its alt text is DELETED${at(n)}`);

      // ⚠️ SAME CLASS AS THE IMAGE, AND BOTH WERE MISSING. `input` is a denied element and
      // `unwrapDisallowed` cannot unwrap a VOID one, so a GFM task list loses the checkbox AND the
      // author's own `[ ]`/`[x]` characters: `- [ ] step one` renders as `step one`. The only
      // trigger that fired was `bulletList`, which this gate downgrades — so it was silent.
      if (n.type === "listItem" && n.checked !== null && n.checked !== undefined)
        block("L3-task-list-checkbox", `\`[${n.checked ? "x" : " "}]\` — \`input\` is denied and VOID, so the checkbox and its brackets are both deleted${at(n)}`);

      // ⚠️ `a` is denied, so the label survives and the URL is thrown away, silently. A bare
      // https:// autolink IS caught by L1 (the serialiser escapes it); only `[text](url)` was mute.
      if (n.type === "link" || n.type === "linkReference")
        block("L3-link-url-deleted", `a link's URL is deleted and only its text survives (\`a\` is a denied element)${at(n)}`);

      // ⚠️ A number at line start eaten as a list marker. The narrow shape is a SINGLE-item ordered
      // list whose start is not 1 (`1988. In that year…`). A MULTI-item list starting at 0 or 3 is
      // a deliberate list, and the vector table marks `0. item one / 1. item two` ✅ SAFE. The
      // genuine renumbering hazard (`1.` then `3.`) is a different shape and L1 + `M2-
      // orderedListRenumbered` both catch it.
      if (n.type === "list" && n.ordered && n.start != null && n.start !== 1 && (n.children?.length ?? 0) === 1)
        block("L3-ordered-list-start", `a lone \`${n.start}.\` at line start became a list marker and the number is gone from the text${at(n)}`);

      if (n.type === "table") {
        // ⚠️ A HEADER-ONLY TABLE IS ALMOST NEVER ONE. Two lines a maths author writes without meaning a
        // table — absolute value, set-builder, a determinant — become a GFM table whose pipes are then
        // DELETED: `|x| = 5` over `|---|---|` parses to a 2-cell header row and renders as `x  = 5`.
        // The round trip is stable (both sides are the same table) and no other check fires.
        if ((n.children?.length ?? 0) === 1)
          block("L3-table-no-body-rows", "a table with a header row and no body — if you meant `|x|` as absolute value, write `$\\vert x \\vert$`");
        const header = n.children?.[0];
        for (const cell of header?.children ?? []) {
          if ((cell.children ?? []).length === 0) block("L3-table-blank-header", `a blank HEADER cell collapses its whole column (a blank BODY cell is the fill-in affordance and is fine)${at(n)}`);
        }
        const cols = header?.children?.length ?? 0;
        const rows = n.children?.length ?? 0;
        // OD-15, two-tier: 8 columns is far outside a 320 px phone, so advise long before blocking.
        if (cols > 8) block("L3-table-columns-over-cap", `${cols} columns — the cap is 8`);
        else {
          // ⚠️ The spec's threshold is SCRIPT-DEPENDENT — "above 2 columns for Sinhala (4 for
          // English)". Advising at >2 unconditionally fired on a 3-column English table the spec
          // explicitly sanctions, with a message that contradicted its own firing.
          // ⚠️ THE TABLE'S OWN SOURCE, not the whole field: an ASCII table inside a Sinhala stem is the
          // most common shape in a bilingual product, and sniffing the field called it Sinhala.
          const sinhala = /[\u0D80-\u0DFF]/.test(src.slice(n.position.start.offset, n.position.end.offset));
          const limit = sinhala ? 2 : 4;
          if (cols > limit)
            advise("L3-table-columns-advisory", `${cols} columns in ${sinhala ? "Sinhala" : "English"} — advise ≤${limit} (a 2-column Sinhala table is already 305 px against a 210 px box at 320 px)`);
        }
        if (rows > 30) block("L3-table-rows-over-cap", `${rows} rows — the cap is 30`);

        // ⚠️ ADVICE, NOT A BLOCK, and the reason is measured rather than chosen. A table written
        // WITHOUT edge pipes is textually IDENTICAL to prose that has accidentally become one; the
        // live migrated row `e59fc94b` (`0011` PD-4) is exactly this shape, so blocking here would
        // fail the live corpus. S4/S8 therefore require edge pipes at authoring time — that is what
        // makes the deliberate case distinguishable from the accident.
        const lines = src.split("\n").slice(n.position.start.line - 1, n.position.end.line);
        if (lines.some((l) => l.includes("|") && !/^\s*\|/.test(l)))
          advise("L3-table-no-edge-pipes", `a table row without edge pipes — indistinguishable from prose that became a table; write \`| a | b |\`${at(n)}`);
      }

      if (n.type === "list" && (n.children?.length ?? 0) > 50)
        block("L3-list-items-over-cap", `${n.children.length} items — the cap is 50${at(n)}`);

      // Two stray `$` in prose become ONE math span and the word spaces vanish (`Rs. $500 and $600
      // profit` → `Rs. 500and600 profit`). ⚠️ The value must CONTAIN WHITESPACE: `$AB$` is a line
      // segment and occurs live (`07c81644`), `$500 and $` is swallowed prose.
      if ((n.type === "inlineMath" || n.type === "math") && !n.value.includes("\\") && /\s/.test(n.value)
        && /(?:^|\s)[A-Za-z]{2,}(?:\s|$)/.test(n.value))
        block("L3-math-swallowed-prose", `$…$ contains the prose word(s) ${JSON.stringify(n.value.slice(0, 40))} — two stray $ have paired around prose${at(n)}`);

      /**
       * ⚠️ INTRAWORD EMPHASIS. Admin's `emphasisAsterisk` fires only when a `*` sits next to a
       * DIGIT, and the round trip is stable because the serialiser re-emits `*…*` — so `3*4*5 = 60`
       * is caught and `a*b*c = 60` is not. Measured silent before this check: `area = l*b*h` →
       * `area = lbh`, `p*q*r ට සමාන වේ` → `pqr ට සමාන වේ`, `සම*චතුරස්*රය` → `සමචතුරස්රය`.
       * Multiplication between LETTERS is at least as common as between digits in a worked answer,
       * and the vector table has no Sinhala emphasis row at all — the undercount is still running.
       * Generative and language-blind: emphasis whose delimiters are both INTRAWORD (the source
       * characters just outside the node are neither whitespace nor punctuation) is not authored
       * emphasis, whatever script it is in.
       */
      if ((n.type === "emphasis" || n.type === "strong") && n.position) {
        // ⚠️ BY CODE POINT. `src[i]` is one UTF-16 code unit, so any astral neighbour (𝛁 U+1D6C1, an
        // emoji) was classified by its lone SURROGATE — category `Cs`, i.e. always "wordish" — and
        // `𝛁*y*𝛁` blocked while its BMP twin `∇*y*∇` did not.
        const before = [...src.slice(0, n.position.start.offset)].pop();
        const after = [...src.slice(n.position.end.offset)][0];
        const wordish = (c) => c !== undefined && !/[\s\p{P}\p{S}]/u.test(c);
        if (wordish(before) && wordish(after))
          block("L3-intraword-emphasis", `\`${src.slice(n.position.start.offset, n.position.end.offset).slice(0, 24)}\` is intraword — the markers are deleted and the words run together${at(n)}`);
      }

      if ((n.type === "inlineMath" || n.type === "math") && /\\rule\s*\{/.test(n.value))
        block("L3-rule", `\`\\rule\` draws a box only KaTeX's \`maxSize\` clamps — for a blank, use an empty table cell${at(n)}`);
    });

    let blocks = 0, maxDepth = 0;
    const BLOCK_NODES = new Set(["paragraph", "heading", "list", "listItem", "table", "blockquote", "code", "math", "thematicBreak"]);
    (function depth(n, d) {
      if (BLOCK_NODES.has(n.type)) blocks++;
      // ⚠️ BLOCK nesting — a list in a list in a list — NOT element depth, under which a plain
      // table's `<th>` is already depth 3 and the cap would reject every table (OD-15).
      const nd = ["list", "blockquote", "table"].includes(n.type) ? d + 1 : d;
      maxDepth = Math.max(maxDepth, nd);
      for (const c of n.children ?? []) depth(c, nd);
    })(tree, 0);
    if (blocks > 200) block("L3-block-nodes-over-cap", `${blocks} block nodes — the cap is 200`);
    if (maxDepth > 3) block("L3-nesting-over-cap", `block nesting depth ${maxDepth} — the cap is 3`);
  }

  /**
   * ⚠️ DEDUPE, and give every finding a line. `L3-raw-html` fired once per `html` node — three
   * findings for `<object data=x></object><embed src=y>` — and no `L3-*` finding carried a line
   * number although every walked node has `n.position`. A findings list an operator cannot scan at
   * 03:00 is the thing §2 says a verdict must not be.
   */
  const seen = new Set();
  return out.filter((f) => {
    const k = `${f.code}\u0000${f.detail}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

/**
 * ⚠️ BOTH OF THESE TAKE EXACTLY ONE ARGUMENT, AND THAT IS A CORRECTNESS PROPERTY, NOT A STYLE.
 * `gateBlocks` briefly took `(s, layers)` so `--ablate` could reuse it. `Array#filter` passes
 * `(element, index, array)`, so `NASTY_BATCH.filter(gateBlocks)` put the INDEX in `layers`;
 * `(0).L1` is `undefined`, all three layers switched off, and **every input came back clean** —
 * a total, silent bypass of the exported API, in the one call shape `TRAPS.md` T74 prescribes.
 * Ablation uses `gateFindings(src, layers)` directly instead.
 */
export const gateBlocks = (s) => gateFindings(s).some((f) => f.severity === "block");
export const gateFlags = (s) => gateFindings(s).length > 0;

// ── The binding acceptance test ────────────────────────────────────────────────────────────────
/**
 * The NAMED legitimate set, from `technical/content-text-syntax.md` § "generative": a real table,
 * bullet and numbered lists, bold/italic, inline and display maths, a blank-cell table — plus the
 * §12.1 Sinhala sample and prose alone, which the same document's method paragraph names.
 */
const LEGIT = [
  ["L1-table", "| Shape | Order |\n|---|---|\n| square | 4 |\n| triangle | 3 |"],
  ["L2-bullet-list", "- first\n- second\n- third"],
  ["L3-numbered-list", "1. first\n2. second\n3. third"],
  ["L4-bold-italic", "This is **bold** and this is *italic*."],
  ["L5-inline-maths", "Find the value of $x$ when $x + 2 = 5$."],
  ["L6-display-maths", "Solve:\n\n$$\n\\frac{3}{4} + \\frac{1}{2}\n$$"],
  ["L7-blank-cell-table", "| Shape | Order |\n|---|---|\n| square |  |\n| triangle |  |"],
  ["L8-sinhala-table", "පහත වගුව සම්පූර්ණ කරන්න.\n\n| තල රූපය | භ්‍රමක සමමිති ගනය |\n|---|---|\n| සමචතුරස්‍රය |  |\n| සමාන්තරාස්‍රය |  |\n| රොම්බසය |  |\n"],
  ["L9-prose", "The angles of a triangle sum to 180 degrees."],
  // ⚠️ L10/L11 are the shape N5 exists for, and the vector table's own note calls it legitimate:
  // "a table needs NO blank line before it — it interrupts a paragraph cleanly". It is also THE
  // canonical stem for this product ("Complete the table below:"), in both languages.
  ["L10-prose-then-table", "Complete this:\n| A | B |\n|---|---|\n| 1 | 2 |"],
  ["L11-sinhala-prose-then-table", "පහත වගුව සම්පූර්ණ කරන්න.\n| තල රූපය | ගනය |\n|---|---|\n| සමචතුරස්‍රය |  |"],
  // ⚠️ L12–L16 ARE THE ESCAPES THE SIBLING SKILLS TELL AUTHORS TO WRITE. They were missing, and the
  // gate blocked one of them (`\|` in prose) while reporting "0 false positives" — the named set
  // could not see it, which is the same vacuous-evidence failure the contract warns about, from the
  // other side. A gate that refuses its own recommended escape teaches an author the escape is wrong.
  ["L12-escaped-pipe-in-prose", "key: 2 \\| 3 means 23"],
  ["L13-escaped-pipe-in-cell", "| a \\| b | c |\n|---|---|\n| 1 | 2 |"],
  ["L14-vert-in-a-cell", "| $5 \\vert 8$ | 58 |\n|---|---|\n| a | b |"],
  ["L15-escaped-list-markers", "1\\) Find x\n2\\) Find y"],
  ["L16-escaped-gt-and-math-gt", "\\>5 is bigger, and so is $>5$"],
];

/**
 * The TWO ⚠️ rows the gate deliberately does not flag. EVERY ONE is a row whose own `note` records
 * that the input shown loses nothing — each is the SAFE half of a hazard pair. Flagging a working
 * escape is not a stricter gate; it teaches an author that the escape does not work.
 * ⚠️ **There were FOUR, and TWO were `vectors.ts` LABELLING DEFECTS — both now fixed at the source.**
 * `3. Rs. 500 / 4. Rs. 600` was marked ⚠️ while `0. item one / 1. item two` — the same `ol[start=N]`,
 * two items, consecutive, numbers re-derived to the values authored — was marked ✅. One shape cannot
 * be both, and "flag every ⚠️ vector" cannot be a binding test while two identical shapes disagree
 * about being one. Re-marked ✅ in BOTH repos (checksum `d1ed223b…`), so it needs no exemption here.
 * ⚠️ The damaging half of the mechanism is a NON-consecutive run, which has always been its own ⚠️ row
 * (`1. Find x / 3. Find y`) and says the damage out loud: "part 3 is shown to the student as 2".
 * ⚠️⚠️ **AND THIS COMMENT ONCE SAID "each is the SAFE half of a hazard pair", IMPLYING NONE REMAINED.
 * A critique found the second one immediately:** `1\. not a list` — the ESCAPED, WORKING form — was
 * marked ⚠️ carrying the UNESCAPED form's reason, while `\- 5 = -2` two rows above calls the identical
 * shape "✅ ESCAPE". ⇒ **the class is "a marker describing the MECHANISM instead of THIS input", and
 * one instance is never evidence there are no others.** Also re-marked ✅, so its exemption is gone
 * too: allow-list **4 → 3 → 2**.
 * ⚠️ **And "loses nothing" is scoped to the RENDER, not to every surface.** The `line one  ⏎ line two`
 * entry loses nothing when rendered, but `plainText()` — the `<title>`/`og:title` of the public
 * `/q/{id}` page — maps a hard break to `""` and joins a paragraph's children with `""`, returning
 * `"line oneline two"`: **two words fused**. Measured: 2 of the 300 live strings carry a hard break
 * and 1 fuses, none of them a question stem. Still exempted, because the author's intent reaches the
 * reader on the surface the row projects — recorded because "nothing" was doing more work than the
 * measurement supports.
 */
const EXPECTED_UNFLAGGED = new Map([
  ["line one  \nline two", "the row's own note: `remark-breaks` already breaks every newline, and 0 of the 8 live trailing-whitespace strings render differently"],
  ["Answer:\n    $x = 5$ ලෙස", "the row's own note: without a blank line above, THE MATHS STILL RENDERS — this is the safe half of the indent pair"],
]);

/**
 * ⚠️ ⚠️ THE FIVE ⚠️ ROWS THAT ARE SURFACED BUT DO NOT BLOCK. Pinned by NAME, because an earlier
 * revision of this test measured coverage with `gateFlags` (any severity) and false positives with
 * `gateBlocks` (blocking only) — so **downgrading every `block` to `advice` produced a byte-identical
 * green run** while the gate blocked nothing at all and `--fields` published everything.
 */
const EXPECTED_ADVICE_ONLY = new Map([
  ["a $x$$ b", "L3-dollar-odd — odd `$`, literal at render; the cost is the plainText() sweep"],
  ["`a`b`", "L3-backtick-odd — same shape, same reason"],
  ["oops $unterminated", "L3-dollar-odd — and `Rs. $500 profit` is the SAME shape and declared legitimate"],
  ["A | B\n---|---\n1 | 2", "L3-table-no-edge-pipes — textually identical to the live migrated row e59fc94b"],
  ["a[^1]\n\n[^1]: outer text\n\n    [^2]: nested text", "L3-footnote-marker — `0011` restores the source text, so nothing is lost"],
]);

/** OD-15's caps, each with the just-under case, so a cap cannot be deleted or widened unnoticed. */
const CAP_FIXTURES = [
  ["9 columns", "|" + Array.from({ length: 9 }, (_, i) => `c${i}`).join("|") + "|\n|" + Array(9).fill("---").join("|") + "|\n|" + Array(9).fill("x").join("|") + "|", true],
  ["8 columns", "|" + Array.from({ length: 8 }, (_, i) => `c${i}`).join("|") + "|\n|" + Array(8).fill("---").join("|") + "|\n|" + Array(8).fill("x").join("|") + "|", false],
  ["31 rows", "| a | b |\n|---|---|\n" + Array(31).fill("| x | y |").join("\n"), true],
  ["30 rows", "| a | b |\n|---|---|\n" + Array(29).fill("| x | y |").join("\n"), false],
  ["51 items", Array.from({ length: 51 }, (_, i) => `- item ${i}`).join("\n"), true],
  ["50 items", Array.from({ length: 50 }, (_, i) => `- item ${i}`).join("\n"), false],
  ["nesting 4", "- a\n  - b\n    - c\n      - d", true],
  ["nesting 3", "- a\n  - b\n    - c", false],
  ["201 blocks", Array.from({ length: 201 }, (_, i) => `para ${i}`).join("\n\n"), true],
];

/** A batch the gate must REFUSE — the end-to-end assertion that `block` still means something. */
const NASTY_BATCH = [
  "x = 3\n- 5 = -2", "Answer:\n________", "1) Find x\n2) Find y",
  "See ![figure](fig.png) here", "```\n$x = 5$\n```", "area = l*b*h", "- [ ] step one",
  "See [the syllabus](https://nie.lk) here",   // `a` is denied: the URL is deleted
  "a\\\\\\\nb",                                    // an ODD run of 3 backslashes at end of line
];

async function loadVectors() {
  const vecSrc = path.join(WEB, "src/lib/markdown/vectors.ts");
  if (!fs.existsSync(vecSrc)) die(`no ${vecSrc}`);
  const esbuild = fs.existsSync(path.join(WEB, "node_modules/.bin/esbuild"))
    ? path.join(WEB, "node_modules/.bin/esbuild") : path.join(ADMIN, "node_modules/.bin/esbuild");
  const vecOut = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "vib-vec-")), "vectors.mjs");
  execFileSync(esbuild, [vecSrc, "--format=esm", `--outfile=${vecOut}`, "--log-level=error"]);
  return import(pathToFileURL(vecOut).href);
}

async function selfTest() {
  const corpusSrc = path.join(WEB, "src/lib/markdown/__fixtures__/live-corpus.json");
  const { MARKDOWN_VECTORS } = await loadVectors();
  const corpus = JSON.parse(fs.readFileSync(corpusSrc, "utf8"));

  const hazards = MARKDOWN_VECTORS.filter((v) => v.note.includes("⚠️"));
  const safeRows = MARKDOWN_VECTORS.filter((v) => v.note.includes("✅"));
  // ⚠️ THE FOURTH DENOMINATOR. 163 − 75 − 20 = 68 rows carry NEITHER marker and were counted
  // nowhere, so 19 blocked rows were invisible to this test — two of them legitimate content.
  const neither = MARKDOWN_VECTORS.filter((v) => !v.note.includes("⚠️") && !v.note.includes("✅"));

  const missed = hazards.filter((v) => !gateFlags(v.input));
  const adviceOnly = hazards.filter((v) => !gateBlocks(v.input) && gateFlags(v.input));
  const blockedHaz = hazards.filter((v) => gateBlocks(v.input));
  const legitFp = LEGIT.filter(([, t]) => gateBlocks(t));
  const liveFp = corpus.filter((c) => gateBlocks(c.text));
  const safeFp = safeRows.filter((v) => gateBlocks(v.input));
  const neitherBlocked = neither.filter((v) => gateBlocks(v.input));

  console.log(`
════════ S9 MARKDOWN GATE · THE BINDING ACCEPTANCE TEST ════════
  vectors ${MARKDOWN_VECTORS.length} · ⚠️ ${hazards.length} · ✅ ${safeRows.length} · neither ${neither.length} · live corpus ${corpus.length}

  ⚠️  surfaced                ${hazards.length - missed.length} / ${hazards.length}   = ${blockedHaz.length} BLOCKING + ${adviceOnly.length} advice
  ✅  legitimate set          ${legitFp.length} blocked / ${LEGIT.length}
  📚  live corpus             ${liveFp.length} blocked / ${corpus.length}
  ✅  ✅-marked vector rows    ${safeFp.length} blocked / ${safeRows.length}
  ··  neither-marked rows     ${neitherBlocked.length} blocked / ${neither.length}   (policy + security rows: an author's marker really is deleted)`);

  let ok = true;
  const fail = (m) => { ok = false; console.log(`\n  FAIL — ${m}`); };

  if (legitFp.length) fail(`legitimate markdown blocked: ${legitFp.map(([i]) => i).join(", ")}`);
  if (liveFp.length) fail(`live corpus blocked: ${liveFp.map((c) => c.id).join(", ")}`);
  if (safeFp.length) fail(`✅-marked rows blocked: ${safeFp.map((v) => JSON.stringify(v.input.slice(0, 30))).join(", ")}`);

  // ⚠️ Coverage is asserted on the BLOCKING set, with the advice-only rows named one by one.
  for (const v of adviceOnly) if (!EXPECTED_ADVICE_ONLY.has(v.input))
    fail(`⚠️ row newly DOWNGRADED to advice — it no longer refuses a publish:\n     ${JSON.stringify(v.input.slice(0, 60))}`);
  for (const k of EXPECTED_ADVICE_ONLY.keys()) if (!adviceOnly.some((v) => v.input === k))
    fail(`an EXPECTED_ADVICE_ONLY row is no longer advice-only — delete it from the list:\n     ${JSON.stringify(k.slice(0, 60))}`);

  const unexpected = missed.filter((v) => !EXPECTED_UNFLAGGED.has(v.input));
  const goneStale = [...EXPECTED_UNFLAGGED.keys()].filter((k) => !missed.some((m) => m.input === k));
  for (const v of unexpected) fail(`⚠️ vector newly unflagged — the gate has REGRESSED:\n     ${JSON.stringify(v.input.slice(0, 60))}\n       ${v.note.replace(/\s+/g, " ").slice(0, 110)}`);
  // The allow-list must SHRINK, never silently hold a row the gate now catches.
  for (const k of goneStale) fail(`allow-listed row is now flagged; delete it from EXPECTED_UNFLAGGED:\n     ${JSON.stringify(k.slice(0, 60))}`);

  // ⚠️ (1) A DOWNGRADED TRIGGER MUST STILL BE REPORTED. Silencing `bulletList` instead of advising
  // left every count identical, and `- 5 = -2` as a field's FIRST line — the spec's headline
  // hazard — went completely dark: a list round-trips stably, so nothing else fires at all.
  if (!gateFindings("- 5 = -2").length)
    fail("`- 5 = -2` as a whole field produces NO finding of any severity — a downgraded trigger is being silenced, not advised");

  // ⚠️ (2) The legitimate half of the binding test is REQUIRED, and emptying it made this file green.
  if (LEGIT.length < 9) fail(`the legitimate set has ${LEGIT.length} constructs; the contract names 9 as the minimum`);

  // ⚠️ (3) The allow-list must be EXACT, not a superset. Neutering `EXPECTED_UNFLAGGED.has` to a
  // constant `true` left this test green; comparing the sizes is what makes that impossible.
  if (missed.length !== EXPECTED_UNFLAGGED.size)
    fail(`${missed.length} unflagged ⚠️ rows against ${EXPECTED_UNFLAGGED.size} allow-listed — the two must match exactly`);

  // ── OD-15's caps, over and under ──
  for (const [name, text, shouldBlock] of CAP_FIXTURES) {
    const got = gateBlocks(text);
    if (got !== shouldBlock) fail(`cap fixture "${name}": expected ${shouldBlock ? "BLOCK" : "pass"}, got ${got ? "BLOCK" : "pass"}`);
  }

  // ── `block` must still refuse a batch end to end ──
  const nastyBlocked = NASTY_BATCH.filter((t) => gateBlocks(t)).length;
  if (nastyBlocked !== NASTY_BATCH.length)
    fail(`only ${nastyBlocked}/${NASTY_BATCH.length} of the known-corrupt batch is BLOCKED — 'block' has stopped meaning anything`);

  // ── CRLF must be indistinguishable from LF: the render is, so the gate must be ──
  const crlfDrift = [...corpus.map((c) => c.text), ...LEGIT.map(([, t]) => t)]
    .filter((t) => t.includes("\n") && gateBlocks(t) !== gateBlocks(t.replace(/\n/g, "\r\n")));
  if (crlfDrift.length) fail(`${crlfDrift.length} string(s) are judged differently as CRLF than as LF`);

  console.log(`\n  ── the ${adviceOnly.length} ⚠️ rows surfaced as ADVICE (recorded, do not fail a paper) ──`);
  for (const v of adviceOnly) console.log(`   · ${JSON.stringify(v.input.slice(0, 40)).padEnd(42)} ${EXPECTED_ADVICE_ONLY.get(v.input) ?? "?"}`);
  console.log(`\n  ── the ${missed.length} ⚠️ rows deliberately NOT flagged, each with its reason ──`);
  for (const v of missed) console.log(`   · ${JSON.stringify(v.input.slice(0, 40)).padEnd(42)} ${EXPECTED_UNFLAGGED.get(v.input) ?? "?"}`);
  /**
   * ⚠️ (7) N1's delimiter test is the one defect a behavioural assertion CANNOT see: the quadratic
   * form and the linear one accept exactly the same language, so every count above is identical
   * either way. Only cost separates them — and an absolute millisecond budget measures the machine
   * that ran it, so this asserts the SCALING RATIO instead. Quadratic backtracking is ~16× per 4×
   * of input (measured 15 ms → 219 ms → 1 958 ms at 4 k / 16 k / 50 k); linear is ~4×. Best-of-3
   * per size, and a threshold of 8 leaves a wide margin so this cannot red at random (T70).
   */
  const timeNormalise = (n) => {
    const probe = "|" + " ".repeat(n) + "x";
    let best = Infinity;
    for (let i = 0; i < 3; i++) { const t = process.hrtime.bigint(); normalise(probe); best = Math.min(best, Number(process.hrtime.bigint() - t) / 1e6); }
    return best;
  };
  const small = Math.max(timeNormalise(4000), 0.05);
  const ratio = timeNormalise(16000) / small;
  if (ratio > 8) fail(`N1 scales ${ratio.toFixed(1)}× for 4× the input (linear is ~4×, quadratic ~16×) — the delimiter regex is backtracking`);

  console.log(`\n  N1 scaling ${ratio.toFixed(1)}× per 4× input (linear)`);
  console.log(`  caps ${CAP_FIXTURES.length}/${CAP_FIXTURES.length} · known-corrupt batch ${nastyBlocked}/${NASTY_BATCH.length} blocked · CRLF drift ${crlfDrift.length}`);
  console.log(`\n  ${ok ? "PASS" : "FAIL"} — the gate is ${ok ? "usable" : "NOT usable"} on a real batch.\n`);
  return ok ? 0 : 1;
}

async function ablate() {
  const { MARKDOWN_VECTORS } = await loadVectors();
  const hz = MARKDOWN_VECTORS.filter((v) => v.note.includes("⚠️"));
  const combos = [["L1", 1, 0, 0], ["L2", 0, 1, 0], ["L3", 0, 0, 1], ["L1+L2", 1, 1, 0],
    ["L1+L3", 1, 0, 1], ["L2+L3", 0, 1, 1], ["all three", 1, 1, 1]];
  console.log(`\n  layer contribution over the ${hz.length} ⚠️ vector rows\n`);
  console.log(`  ${"combination".padEnd(12)} blocking  surfaced`);
  const res = {};
  for (const [name, a, b, c] of combos) {
    const L = { L1: !!a, L2: !!b, L3: !!c };
    const blocking = hz.filter((v) => gateFindings(v.input, L).some((f) => f.severity === "block")).length;
    const surfaced = hz.filter((v) => gateFindings(v.input, L).length > 0).length;
    res[name] = blocking;
    console.log(`  ${name.padEnd(12)} ${String(blocking).padStart(8)}  ${String(surfaced).padStart(8)}`);
  }
  const all = res["all three"];
  console.log(`\n  cost of dropping one layer: L1 ${all - res["L2+L3"]} · L2 ${all - res["L1+L3"]} · L3 ${all - res["L1+L2"]}\n`);
  return 0;
}

// ── CLI ────────────────────────────────────────────────────────────────────────────────────────
/**
 * ⚠️ THE GUARD IS THE POINT. Without it, this block is top-level module code: any consumer that
 * does `import { gateBlocks } from "…/markdown-gate.mjs"` falls through to the usage branch and is
 * KILLED BY `process.exit(0)` — a batch script would report success having gated nothing. That is
 * the precise failure `die()` exists to prevent, arriving through the front door.
 */
// ⚠️ REALPATH BOTH SIDES. On macOS `/tmp` is a symlink to `/private/tmp`, so `import.meta.url` is
// `file:///private/tmp/…` while `process.argv[1]` is `/tmp/…`. Comparing them raw made the CLI
// silently do NOTHING — exit 0, no output, no gate — which is the same class of quiet pass the
// guard exists to prevent.
const realpath = (f) => { try { return fs.realpathSync(f); } catch { return f; } };
const SELF = fileURLToPath(import.meta.url);
const RUN_AS_CLI = process.argv[1] ? realpath(SELF) === realpath(process.argv[1]) : false;
// ⚠️ AND THE GUARD MUST FAIL LOUDLY WHEN IT MIS-IDENTIFIES ITSELF. The first version compared
// `new URL(import.meta.url).pathname` (percent-encoded) with `process.argv[1]` (not), so any checkout
// path containing a space or a non-ASCII character took the `--imported` branch: **no gate, no output,
// exit 0** — a `--self-test` that never ran, reported to `$?` as a pass. Fixing the encoding is not
// enough on its own; a guard whose failure mode is silence needs its own alarm.
if (!RUN_AS_CLI && process.argv[1] && path.basename(process.argv[1]) === path.basename(SELF)) {
  console.error(`\nGATE CANNOT RUN — the CLI guard did not recognise its own invocation.\n  argv[1]: ${process.argv[1]}\n  self:    ${SELF}\n`);
  process.exit(2);
}
const argv = RUN_AS_CLI ? process.argv.slice(2) : ["--imported"];
if (argv.includes("--imported")) {
  // imported as a library: export and do nothing else
} else if (argv.includes("--ablate")) {
  process.exit(await ablate());
} else if (argv.includes("--self-test")) {
  process.exit(await selfTest());
} else if (argv.includes("--fields")) {
  const file = argv[argv.indexOf("--fields") + 1];
  if (!file) die("--fields needs a path to a JSON array of { id, field, text }");
  let fields;
  try {
    fields = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    die(`could not read ${file}: ${e.message}`);
  }
  if (!Array.isArray(fields)) die(`${file} must be a JSON ARRAY of { id, field, text }`);
  let blocked = 0;
  let crashed = 0;
  for (const f of fields) {
    if (typeof f?.text !== "string") {
      // ⚠️ Name it rather than coercing it quietly. A non-string `text` is a defect in whatever
      // produced the batch, and `String(123)` would gate the characters "123" and report clean.
      crashed++;
      console.log(`\n${f?.id ?? "?"} · ${f?.field ?? "?"}\n   [GATE-CRASHED] \`text\` is ${typeof f?.text}, not a string — fix the batch producer`);
      continue;
    }
    let findings;
    try {
      // ⚠️ `String(...)` and a per-field catch. A non-string `text` used to throw
      // `src.match is not a function`, abort the batch mid-way and exit 1 — THE SAME CODE AS
      // "blocked" — so a run that died after 3 of 40 fields was indistinguishable from one that
      // gated all 40. A gate that cannot check a field says so, per §0.5.
      findings = gateFindings(String(f?.text ?? ""));
    } catch (e) {
      crashed++;
      console.log(`\n${f?.id ?? "?"} · ${f?.field ?? "?"}\n   [GATE-CRASHED] ${e.message}`);
      continue;
    }
    if (!findings.length) continue;
    if (findings.some((x) => x.severity === "block")) blocked++;
    console.log(`\n${f?.id ?? "?"} · ${f?.field ?? "?"}`);
    for (const x of findings) console.log(`   [${x.severity}] ${x.code} — ${x.detail}`);
  }
  console.log(`\n${fields.length} fields · ${blocked} BLOCKED${crashed ? ` · ${crashed} COULD NOT BE CHECKED` : ""}\n`);
  // 0 clean · 1 content is blocked · 3 the gate itself failed on a field (never a quiet pass).
  process.exit(crashed ? 3 : blocked ? 1 : 0);
} else {
  console.log(`usage:
  markdown-gate.mjs --self-test              run the binding acceptance test
  markdown-gate.mjs --fields <file.json>     gate a batch: [{ id, field, text }, …]
  markdown-gate.mjs --ablate                 per-layer contribution, computed not transcribed

⚠️ S9 §0.1: run --self-test in the SAME SESSION, before gating anything. A gate that has never
   been observed to fail has not been tested.`);
  process.exit(0);
}
