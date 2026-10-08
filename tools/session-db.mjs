// Offline-testable helpers for `visual-check.mjs` — separated so the unit tests can import them
// without touching the Admin checkout, esbuild, or a browser: claimsFor/pushFigure/claimsForWarn
// carry the claim-set lookup and its dedup + missing-claims decisions (modes 1 AND --session), and
// pairRenderedFigures is --session's rendered↔staged pairing (a mis-pair assesses a figure against
// another figure's claims). The post-logout Q3 proof lives in tools/sql-proof.py — --session
// shells to it, there is no JS copy of it here.
import fs from "node:fs";
import path from "node:path";

/**
 * Find a figure's claim set, in order: `<fileBase>.claims.txt`, `<fileBase>-claims.txt` beside a
 * VDD input, then under `--claims-dir` as `<id>.claims.txt` OR `<id>-claims.txt` — the second name
 * is what `tools/vdd_templates.py` emits for a figure id (`Q3` → `Q3-claims.txt`). → {path, text}
 * or null.
 */
export function claimsFor(id, fileBase, claimsDir) {
  const cands = [];
  if (fileBase) cands.push(`${fileBase}.claims.txt`, `${fileBase}-claims.txt`);
  if (claimsDir) cands.push(path.join(claimsDir, `${id}.claims.txt`), path.join(claimsDir, `${id}-claims.txt`));
  for (const f of cands) if (fs.existsSync(f)) return { path: f, text: fs.readFileSync(f, "utf8") };
  return null;
}

/**
 * The `push` behind visual-check's collectFigures: a repeated id lands as `<id>~<k>` (a dup is
 * never silently overwritten), but claims always resolve by the BASE id — `Q3~2.claims.txt` is
 * never a real filename; the duplicate shares `Q3`'s claim set. `baseId` rides on the figure so
 * the --claims-dir warning names what was actually looked up.
 */
export function pushFigure(figures, seen, id, doc, source, fileBase, claimsDir) {
  const k = (seen.get(id) ?? 0) + 1;
  seen.set(id, k);
  figures.push({
    id: k === 1 ? id : `${id}~${k}`, baseId: id, doc, source,
    claims: claimsFor(id, fileBase, claimsDir),
  });
}

/**
 * The --claims-dir warning: claim sets are optional in general, but a claims-dir run implies every
 * figure should have one — a figure that resolved none gets a loud line (and the summary counts
 * them). → the WARN string, or null.
 */
export function claimsForWarn(baseId, claimsDir, resolved) {
  if (!claimsDir || resolved) return null;
  return `WARN no claim set for ${baseId} (looked for ${baseId}.claims.txt / ${baseId}-claims.txt in ${claimsDir})`;
}

/**
 * --session's per-question pairing: the k-th svg-bearing `[role="img"]` host in the student
 * preview IS the k-th figure collectFromStaged emitted for that question — StudentPreview's
 * document order (question figure, then parts in label order, then the whole-question answers)
 * is the walk's order. ⚠️ pair on POSITION among the svg entries, never m.index — measure()'s
 * index counts every role=img host, svg-less plates included, so one unparseable figure ahead
 * of a real one would shift every pairing behind it. `stagedFigs` null → figures assess
 * claims-less exactly as before. → [{measured, fig}] with fig null when the staged doc has
 * fewer figures than the preview renders.
 */
export function pairRenderedFigures(measured, stagedFigs) {
  return (measured ?? []).filter((m) => m?.svg)
    .map((m, k) => ({ measured: m, fig: stagedFigs?.[k] ?? null }));
}

/**
 * Group collectFromStaged's figures by question number for --session pairing, in the walk's
 * document order. ⚠️ A figure with `renders === false` (the caller marks it when the doc fails
 * parseVddDocument or parses to zero elements — StudentPreview draws a `<p>` note, NO svg host)
 * takes no pairing slot and lands in `skipped` instead; counted, it would shift every figure
 * behind it in that question onto the wrong claim set. → {byQ: Map<q, fig[]>, skipped: [{q,id,why}]}
 */
export function groupStagedFigures(figs) {
  const byQ = new Map();
  const skipped = [];
  for (const f of figs) {
    const id = f.baseId ?? f.id;
    const m = id.match(/^Q(\d+)/);
    if (!m) continue;
    const q = +m[1];
    if (f.renders === false) { skipped.push({ q, id, why: f.why ?? "does not parse" }); continue; }
    if (!byQ.has(q)) byQ.set(q, []);
    byQ.get(q).push(f);
  }
  return { byQ, skipped };
}

/**
 * The argv for --session's post-logout Q3 proof. `authEnv` is the env FILE the URL was read
 * from — sql-proof.py resolves VIBHAGA_ADMIN_AUTH_DB_URL via env → VIBHAGA_ADMIN_ENV → the
 * admin checkout's own .env.local path, which is NOT necessarily the file visual-check's
 * resolver found it in (a non-sibling --admin/VIBHAGA_ADMIN checkout), so the file goes along
 * as `--auth-env` and one resolution feeds both. null when the URL came from the process env
 * or when nothing resolved — sql-proof falls back to the content-DB chain (DATABASE_URL env →
 * Vibhaga-DB/.env) on the merged project. actorId on argv matches the ship-chain behaviour;
 * the URL itself never goes on argv.
 */
export function sqlProofQ3Argv(pluginDir, actorId, authEnv = null) {
  const argv = [path.join(pluginDir, "tools", "sql-proof.py"), "q3", "--actor", actorId];
  if (authEnv) argv.push("--auth-env", authEnv);
  return argv;
}
