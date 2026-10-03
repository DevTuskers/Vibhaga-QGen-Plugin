#!/usr/bin/env python3
"""tools/sql-proof.py — offline tests. No DB, no network:

  · the REAL queries.sql slices to exactly one guarded statement for Q2 (opens WITH) and Q3;
  · a fake `psql` shell script on PATH records its argv and prints a canned header + row —
    the URL must never reach argv (PG* env only) and stdin must carry the read-only prefix;
  · ok=t → exit 0; ok=f → exit 1 naming the failing counts; psql non-zero → exit 1;
  · non-uuid id / --expected 0 → exit 2; q3 with no URL source anywhere → exit 2.

All ids are synthetic (00000000-0000-4000-8000-0000000000NN); the URLs are *.invalid.test.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
QUERIES = HERE.parent / "queries.sql"

SPEC = importlib.util.spec_from_file_location("sql_proof", TOOLS / "sql-proof.py")
sp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sp)

SID = "00000000-0000-4000-8000-0000000000e1"
ACTOR = "00000000-0000-4000-8000-0000000000e2"

Q2_COLS = ["session_exists", "questions", "not_flagged", "not_published", "papered",
           "scope_mismatch", "parts", "answers", "signed_answers", "sub_answers",
           "signed_sub_answers", "unanswered_leaves", "ok"]
Q3_COLS = ["actor_exists", "sessions", "active_refresh_tokens", "wrong_project", "ok"]

# Canned-output psql: records argv (one per line), asserts the read-only prefix on stdin, prints
# $FAKE_PSQL_OUT, or exits $FAKE_PSQL_EXIT with a stderr line when set.
FAKE_PSQL = """#!/bin/sh
printf '%s\\n' "$@" > "$FAKE_PSQL_ARGV"
data=$(cat)
case "$data" in
  "set default_transaction_read_only=on;"*) ;;
  *) echo "read-only prefix missing" >&2; exit 9;;
esac
case "$data" in
  *"-- Q2"*|*"-- Q3"*) ;;
  *) echo "no Q marker in stdin" >&2; exit 8;;
esac
if [ -n "$FAKE_PSQL_EXIT" ]; then
  if [ -n "$FAKE_PSQL_ERR" ]; then printf '%s' "$FAKE_PSQL_ERR" >&2; else echo "psql: synthetic failure" >&2; fi
  exit "$FAKE_PSQL_EXIT"
fi
printf '%s\\n' "$FAKE_PSQL_OUT"
"""


def out_line(cols, vals):
    return "\t".join(cols) + "\n" + "\t".join(str(v) for v in vals)


class SliceTests(unittest.TestCase):
    def setUp(self):
        self.sql = QUERIES.read_text(encoding="utf-8")

    def test_real_q2_block_is_one_guarded_with_statement(self):
        raw = sp.slice_proof(self.sql, "Q2")
        self.assertTrue(raw.lstrip().startswith("-- Q2"), "slice starts at the Q2 marker")
        stmt = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("--")).strip()
        self.assertTrue(stmt.upper().startswith("WITH"), stmt[:80])
        self.assertTrue(stmt.endswith(";"))
        self.assertNotIn(";", stmt[:-1], "the slice must hold exactly one statement")
        self.assertIn(":'batch_id'", stmt)
        self.assertIn(":expected", stmt)

    def test_real_q3_block_is_one_guarded_select(self):
        raw = sp.slice_proof(self.sql, "Q3")
        stmt = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("--")).strip()
        self.assertTrue(stmt.upper().startswith("SELECT"), stmt[:80])
        self.assertTrue(stmt.endswith(";"))
        self.assertNotIn(";", stmt[:-1])
        self.assertIn(":'actor_id'", stmt)

    def test_write_token_and_multi_statement_refused(self):
        with self.assertRaises(SystemExit) as e:
            sp.slice_proof("-- Q2\nWITH x AS (SELECT 1) DELETE FROM q;", "Q2")
        self.assertEqual(e.exception.code, 2)
        with self.assertRaises(SystemExit) as e:
            sp.slice_proof("-- Q3\nSELECT 1; SELECT 2;", "Q3")
        self.assertEqual(e.exception.code, 2)

    def test_neither_with_nor_select_refused(self):
        with self.assertRaises(SystemExit) as e:
            sp.slice_proof("-- Q3\nVALUES (1);", "Q3")
        self.assertEqual(e.exception.code, 2)


class FailingTests(unittest.TestCase):
    def test_q2_failing_names_each_broken_invariant(self):
        counts = {"session_exists": 1, "questions": 4, "not_flagged": 0, "not_published": 4,
                  "papered": 0, "scope_mismatch": 0, "signed_answers": 0, "signed_sub_answers": 0,
                  "unanswered_leaves": 0}
        self.assertEqual(sp.failing_q2(counts, 4), ["not_published=4"])
        counts["questions"] = 3
        self.assertIn("questions=3 (expected 4)", sp.failing_q2(counts, 4))

    def test_q3_failing(self):
        counts = {"actor_exists": 1, "sessions": 2, "active_refresh_tokens": 0,
                  "wrong_project": False}
        self.assertEqual(sp.failing_q3(counts), ["sessions=2"])
        counts["wrong_project"] = True
        self.assertEqual(sp.failing_q3(counts), ["sessions=2", "wrong_project=t"])


class EndToEnd(unittest.TestCase):
    """A fake `psql` executable on PATH; synthetic URLs arrive via env vars only."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.bindir = root / "bin"
        self.bindir.mkdir()
        psql = self.bindir / "psql"
        psql.write_text(FAKE_PSQL, encoding="utf-8")
        psql.chmod(0o755)
        self.argv_log = root / "argv.log"
        self.env = {
            "PATH": f"{self.bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_PSQL_ARGV": str(self.argv_log),
            "VIBHAGA_ADMIN_ENV": "/nonexistent/offline-test-only",
            "DATABASE_URL": "postgres://proof:s3cret%40pw@db.invalid.test:6543/fakedb",
            "VIBHAGA_ADMIN_AUTH_DB_URL": "postgres://proof:s3cret%40pw@auth.invalid.test:6543/authdb",
            # empty defaults: the stub treats "" as unset and ambient leakage can't reach a test
            "FAKE_PSQL_OUT": "",
            "FAKE_PSQL_EXIT": "",
            "FAKE_PSQL_ERR": "",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args, drop=(), extra=None):
        env = {**self.env, **(extra or {})}
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, env), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            for k in drop:
                os.environ.pop(k, None)
            try:
                rc = sp.main(list(args))
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    # ---- q2 -----------------------------------------------------------------
    def test_q2_ok_t_exits_0(self):
        vals = [1, 4, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, "t"]
        rc, out, err = self.run_main("q2", SID, "--expected", "4",
                                     extra={"FAKE_PSQL_OUT": out_line(Q2_COLS, vals)})
        self.assertEqual(rc, 0, err)
        self.assertIn("not_published=0", out)
        self.assertIn("ok=t", out)
        self.assertIn("q2: ok", out)
        self.assertIn("DB URL from DATABASE_URL env", err)
        self.assertNotIn("s3cret", err + out)

    def test_q2_ok_f_exits_1_naming_the_failing_counts(self):
        vals = [1, 4, 0, 4, 0, 0, 0, 4, 0, 0, 0, 0, "f"]
        rc, out, _ = self.run_main("q2", SID, "--expected", "4",
                                   extra={"FAKE_PSQL_OUT": out_line(Q2_COLS, vals)})
        self.assertEqual(rc, 1)
        self.assertIn("q2: NOT ok — not_published=4", out)

    def test_q2_psql_failure_exits_1(self):
        rc, _, err = self.run_main("q2", SID, "--expected", "4",
                                   extra={"FAKE_PSQL_EXIT": "3"})
        self.assertEqual(rc, 1)
        self.assertIn("psql failed on q2", err)
        self.assertIn("synthetic failure", err)

    def test_psql_failure_shows_the_error_line_and_the_tail(self):
        # the owner once saw only `^` — the caret under psql's position marker. The ERROR/FATAL
        # line plus up to the last 3 stderr lines must print.
        canned = ("psql: error: connection to server failed\n"
                  'FATAL:  password authentication failed for user "proof"\n'
                  "LINE 1: SELECT bogus\n"
                  "       ^\n")
        rc, _, err = self.run_main("q3", "--actor", ACTOR,
                                   extra={"FAKE_PSQL_EXIT": "2", "FAKE_PSQL_ERR": canned})
        self.assertEqual(rc, 1)
        self.assertIn('FATAL:  password authentication failed for user "<user>"', err)
        self.assertIn("LINE 1: SELECT bogus", err)
        self.assertIn("^", err)
        self.assertNotIn("s3cret", err)
        self.assertNotIn('"proof"', err)

    def test_psql_failure_redacts_host_ip_and_user(self):
        # a connection failure echoes the server host + resolved IP — they must be blanked
        canned = ('psql: error: connection to server at "db.abc123.supabase.example.test" '
                  '(203.0.113.7), port 6543 failed: Connection refused\n'
                  'psql: error: could not translate host name "auth.invalid.test" to address\n'
                  'FATAL:  password authentication failed for user "proof"\n')
        rc, _, err = self.run_main("q3", "--actor", ACTOR,
                                   extra={"FAKE_PSQL_EXIT": "2", "FAKE_PSQL_ERR": canned})
        self.assertEqual(rc, 1)
        self.assertNotIn("db.abc123.supabase.example.test", err)
        self.assertNotIn("auth.invalid.test", err)   # the URL's own host is redacted too
        self.assertNotIn("203.0.113.7", err)
        self.assertNotIn('"proof"', err)
        self.assertIn("<host>", err)
        self.assertIn("<ip>", err)
        self.assertIn('user "<user>"', err)
        self.assertIn("Connection refused", err)     # the error wording survives

    def test_psql_missing_qgen_function_adds_the_setup_hint(self):
        # on the content project (or before the one-time setup) qgen.q3 is absent
        canned = ('ERROR:  function qgen.q3(uuid) does not exist\n'
                  "LINE 1: ...FROM qgen.q3('00000000-0000-4000-8000-0000000000f0'::uuid) f\n"
                  "                 ^\n"
                  "HINT:  No function matches the given name and argument types.\n")
        rc, _, err = self.run_main("q3", "--actor", ACTOR,
                                   extra={"FAKE_PSQL_EXIT": "3", "FAKE_PSQL_ERR": canned})
        self.assertEqual(rc, 1)
        self.assertIn("qgen.q3 missing", err)
        self.assertIn("step 11", err)

    def test_psql_permission_denied_adds_the_grant_hint(self):
        canned = ("ERROR:  permission denied for function q3\n"
                  "LINE 1: ...qgen.q3(...\n"
                  "                 ^\n")
        rc, _, err = self.run_main("q3", "--actor", ACTOR,
                                   extra={"FAKE_PSQL_EXIT": "3", "FAKE_PSQL_ERR": canned})
        self.assertEqual(rc, 1)
        self.assertIn("USAGE on schema qgen and EXECUTE on qgen.q3", err)
        self.assertIn("step 11", err)

    def test_q2_argv_never_carries_the_url(self):
        vals = [1, 4, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, "t"]
        rc, _, _ = self.run_main("q2", SID, "--expected", "4",
                                 extra={"FAKE_PSQL_OUT": out_line(Q2_COLS, vals)})
        self.assertEqual(rc, 0)
        argv = self.argv_log.read_text()
        self.assertIn(f"batch_id={SID}", argv)
        self.assertIn("expected=4", argv)
        self.assertIn("ON_ERROR_STOP=1", argv)
        self.assertIn("-f\n-\n", argv)
        self.assertNotIn("postgres://", argv)
        self.assertNotIn("s3cret", argv)
        self.assertNotIn("db.invalid.test", argv)

    def test_q2_non_uuid_and_bad_expected_exit_2(self):
        rc, _, err = self.run_main("q2", "not-a-uuid", "--expected", "4")
        self.assertEqual(rc, 2)
        self.assertIn("not a uuid", err)
        rc, _, err = self.run_main("q2", SID, "--expected", "0")
        self.assertEqual(rc, 2)
        self.assertIn("positive", err)

    def test_q2_out_writes_counts_json(self):
        vals = [1, 4, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, "t"]
        out_path = Path(self.tmp.name) / "proof.json"
        rc, _, _ = self.run_main("q2", SID, "--expected", "4", "--out", str(out_path),
                                 extra={"FAKE_PSQL_OUT": out_line(Q2_COLS, vals)})
        self.assertEqual(rc, 0)
        payload = json.loads(out_path.read_text())
        self.assertEqual(payload["query"], "Q2")
        self.assertEqual(payload["session_id"], SID)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["counts"]["questions"], 4)
        self.assertNotIn("ok", payload["counts"])

    # ---- q3 -----------------------------------------------------------------
    def test_q3_ok_t_exits_0(self):
        vals = [1, 0, 0, "f", "t"]
        rc, out, err = self.run_main("q3", "--actor", ACTOR,
                                     extra={"FAKE_PSQL_OUT": out_line(Q3_COLS, vals)})
        self.assertEqual(rc, 0, err)
        self.assertIn("q3: ok", out)
        self.assertIn("auth DB URL from VIBHAGA_ADMIN_AUTH_DB_URL env", err)
        self.assertNotIn("s3cret", err + out)
        argv = self.argv_log.read_text()
        self.assertIn(f"actor_id={ACTOR}", argv)
        self.assertNotIn("postgres://", argv)
        self.assertNotIn("auth.invalid.test", argv)

    def test_q3_ok_f_exits_1_naming_sessions(self):
        vals = [1, 2, 1, "f", "f"]
        rc, out, _ = self.run_main("q3", "--actor", ACTOR,
                                   extra={"FAKE_PSQL_OUT": out_line(Q3_COLS, vals)})
        self.assertEqual(rc, 1)
        self.assertIn("q3: NOT ok", out)
        self.assertIn("sessions=2", out)
        self.assertIn("active_refresh_tokens=1", out)

    def test_q3_no_url_source_exits_2(self):
        rc, _, err = self.run_main("q3", "--actor", ACTOR,
                                   drop=("VIBHAGA_ADMIN_AUTH_DB_URL",))
        self.assertEqual(rc, 2)
        self.assertIn("VIBHAGA_ADMIN_AUTH_DB_URL", err)
        self.assertNotIn("postgres://", err)

    def test_q3_auth_env_file_beats_env_var(self):
        envfile = Path(self.tmp.name) / "auth.env"
        envfile.write_text("VIBHAGA_ADMIN_AUTH_DB_URL=postgres://proof:x@file.invalid.test/db\n")
        vals = [1, 0, 0, "f", "t"]
        rc, _, err = self.run_main("q3", "--actor", ACTOR, "--auth-env", str(envfile),
                                   extra={"FAKE_PSQL_OUT": out_line(Q3_COLS, vals)})
        self.assertEqual(rc, 0, err)
        self.assertIn(f"auth DB URL from --auth-env {envfile}", err)

    def test_q3_bad_actor_exits_2(self):
        rc, _, err = self.run_main("q3", "--actor", "nope")
        self.assertEqual(rc, 2)
        self.assertIn("not a uuid", err)


if __name__ == "__main__":
    unittest.main()
