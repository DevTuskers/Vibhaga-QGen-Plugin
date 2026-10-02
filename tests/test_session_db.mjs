import test from "node:test";
import assert from "node:assert/strict";
import { q3Block, pgEnvFromUrl } from "../tools/session-db.mjs";

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
