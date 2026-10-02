// Offline-testable helpers for `visual-check.mjs` — separated so the unit tests can import them
// without touching the Admin checkout, esbuild, or a browser: q3Block/pgEnvFromUrl feed
// `--session`'s revocation proof; claimsFor/pushFigure/claimsForWarn carry the claim-set lookup
// and its dedup + missing-claims decisions. No secrets: the URL is only ever parsed into PG*
// environment variables for the psql child process, never placed on its command line (argv leaks
// into `ps`) and never printed.
import fs from "node:fs";
import path from "node:path";

/**
 * Slice the Q3 block out of queries.sql's text: from the "Q3 —" marker's first SELECT to its
 * terminating `;` — NOT to EOF (the file has more queries after it).
 */
export function q3Block(sqlText) {
  const at = sqlText.indexOf("Q3 —");
  if (at < 0) throw new Error("queries.sql has no Q3 block");
  const sel = sqlText.indexOf("SELECT", at);
  const end = sel < 0 ? -1 : sqlText.indexOf(";", sel);
  if (sel < 0 || end < 0) throw new Error("queries.sql Q3 block has no SELECT…;");
  return sqlText.slice(sel, end + 1);
}

/**
 * Parse a postgres URL into libpq environment variables. psql reads PGHOST/PGPORT/PGUSER/
 * PGPASSWORD/PGDATABASE from the environment — that keeps the password OFF argv and out of logs.
 * PGSSLMODE defaults to require unless the URL says otherwise (`?sslmode=disable` honoured).
 */
export function pgEnvFromUrl(raw) {
  const u = new URL(raw); // throws TypeError on a malformed URL — caller surfaces it
  if (!u.hostname || !u.username) throw new Error("VIBHAGA_ADMIN_AUTH_DB_URL is not a postgres URL (needs host + user)");
  const env = {
    PGHOST: u.hostname.replace(/^\[|\]$/g, ""), // WHATWG keeps IPv6 brackets; PGHOST wants bare
    PGPORT: u.port || "5432",
    PGUSER: decodeURIComponent(u.username),
    PGPASSWORD: decodeURIComponent(u.password),
    PGDATABASE: decodeURIComponent(u.pathname.replace(/^\//, "")) || "postgres",
    PGSSLMODE: u.searchParams.get("sslmode") ?? "require",
  };
  return env;
}

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
