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
