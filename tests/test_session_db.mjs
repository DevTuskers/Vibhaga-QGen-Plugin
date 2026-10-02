import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { q3Block, pgEnvFromUrl, claimsFor, pushFigure, claimsForWarn } from "../tools/session-db.mjs";

// Synthetic SQL + a synthetic URL only — never a real host, user, or query text.

const SQL = `-- Q1 …
SELECT 1;
-- Q2 …
SELECT 2;
-- Q3 — revocation check
SELECT count(*) FROM audit_log WHERE actor_id = :'actor_id';
-- Q4 …
SELECT 4;
`;

test("q3Block slices Q3's SELECT to its terminating semicolon — not to EOF", () => {
  const block = q3Block(SQL);
  assert.match(block, /^SELECT count\(\*\)/);
  assert.match(block, /;$/);
  assert.ok(!block.includes("SELECT 4"), "trailing queries must not bleed into the block");
});

test("q3Block throws clearly when the Q3 marker or SELECT is missing", () => {
  assert.throws(() => q3Block("SELECT 1;"), /no Q3 block/);
  assert.throws(() => q3Block("-- Q3 — nothing here"), /no SELECT/);
});

test("pgEnvFromUrl splits a postgres URL into PG* vars — nothing on argv", () => {
  const env = pgEnvFromUrl("postgresql://svc_user:p%40ss@db.example.test:6543/authdb");
  assert.deepEqual(env, {
    PGHOST: "db.example.test",
    PGPORT: "6543",
    PGUSER: "svc_user",
    PGPASSWORD: "p@ss",
    PGDATABASE: "authdb",
    PGSSLMODE: "require",
  });
});

test("pgEnvFromUrl: defaults and explicit sslmode", () => {
  assert.equal(pgEnvFromUrl("postgres://u:p@h.test/db").PGPORT, "5432");
  assert.equal(pgEnvFromUrl("postgres://u:p@h.test/db?sslmode=disable").PGSSLMODE, "disable");
  assert.throws(() => pgEnvFromUrl("not-a-url"));
  assert.throws(() => pgEnvFromUrl("postgres://h.test/db"), /needs host \+ user/);
});

test("pgEnvFromUrl: percent-decoded user/password/database, IPv6 brackets stripped", () => {
  const env = pgEnvFromUrl("postgresql://svc%20user:x@[2001:db8::1]/auth%20db");
  assert.equal(env.PGUSER, "svc user");
  assert.equal(env.PGHOST, "2001:db8::1");
  assert.equal(env.PGDATABASE, "auth db");
});

test("claimsFor: --claims-dir resolves <id>-claims.txt (the vdd_templates name) too", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vc-claims-"));
  // Only the dash name exists — a staged doc's figure id Q3 must still find it.
  fs.writeFileSync(path.join(dir, "Q3-claims.txt"), "claims:\n  K1 none x | stem |\n");
  const hit = claimsFor("Q3", null, dir);
  assert.equal(hit.path, path.join(dir, "Q3-claims.txt"));
  assert.match(hit.text, /K1 none x/);
  // <id>.claims.txt still wins when both exist beside it.
  fs.writeFileSync(path.join(dir, "Q3.claims.txt"), "claims:\n  K9 none y | stem |\n");
  assert.equal(claimsFor("Q3", null, dir).path, path.join(dir, "Q3.claims.txt"));
  // A dotted part id works the same way; a missing figure resolves to null.
  fs.writeFileSync(path.join(dir, "Q3.b-claims.txt"), "x");
  assert.equal(claimsFor("Q3.b", null, dir).path, path.join(dir, "Q3.b-claims.txt"));
  assert.equal(claimsFor("Q9", null, dir), null);
  // Beside a VDD input file the sibling names are unchanged.
  const base = path.join(dir, "fig");
  fs.writeFileSync(`${base}-claims.txt`, "x");
  assert.equal(claimsFor("fig", base, dir).path, `${base}-claims.txt`);
});

test("pushFigure: a duplicate id lands as <id>~k but claims resolve by the BASE id", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vc-dup-"));
  fs.writeFileSync(path.join(dir, "Q3-claims.txt"), "claims:\n  K1 none x | stem |\n");
  const figures = [], seen = new Map();
  pushFigure(figures, seen, "Q3", {}, "t", null, dir);
  pushFigure(figures, seen, "Q3", {}, "t", null, dir);
  assert.equal(figures[0].id, "Q3");
  assert.equal(figures[1].id, "Q3~2");       // the dup keeps its display suffix
  assert.equal(figures[1].baseId, "Q3");
  // …but `Q3~2.claims.txt` is never a real filename — the dup shares Q3's claim set.
  assert.equal(figures[0].claims.path, path.join(dir, "Q3-claims.txt"));
  assert.equal(figures[1].claims.path, path.join(dir, "Q3-claims.txt"));
});

test("claimsForWarn: warns only under --claims-dir and only when nothing resolved", () => {
  const dir = "/tmp/vc-claims-dir";
  assert.equal(claimsForWarn("Q3", dir, null),
    `WARN no claim set for Q3 (looked for Q3.claims.txt / Q3-claims.txt in ${dir})`);
  assert.equal(claimsForWarn("Q3", dir, { path: "p", text: "t" }), null); // resolved → silent
  assert.equal(claimsForWarn("Q3", null, null), null);                    // no --claims-dir → silent
});
