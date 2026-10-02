#!/usr/bin/env python3
"""tools/critic-read.py — offline tests. No DB, no network:

  · block slicing + the read-only assertion run against the REAL queries.sql;
  · doctored blocks (a non-SELECT, a write token inside a SELECT) are refused with exit 2;
  · fields/hashes/figures are derived from a synthetic q4b fixture line
    (tests/fixtures/critic-read-q4b.jsonl — uuids in the 00000000-…-0NNN family);
  · pg_env_from_url splits a synthetic URL (percent-encoded user/password, ?sslmode=);
  · end-to-end: a fake `psql` executable on PATH echoes canned output per Q4 marker it sees on
    stdin (and asserts the `set default_transaction_read_only=on;` prefix), so the real argv/env
    plumbing is exercised — the URL must never appear on argv.
"""
import contextlib
import hashlib
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
FIXTURE = HERE / "fixtures" / "critic-read-q4b.jsonl"

SPEC = importlib.util.spec_from_file_location("critic_read", TOOLS / "critic-read.py")
cr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cr)

BID = "00000000-0000-4000-8000-0000000000f0"

# Canned-output psql: records its argv, asserts the read-only preamble on stdin, prints the file
# named by the first `-- Q4x` marker in the SQL (absent file → 0 rows).
FAKE_PSQL = """#!/usr/bin/env python3
import os, sys
data = sys.stdin.read()
with open(os.environ["FAKE_PSQL_ARGV"], "a") as f:
    f.write("\\t".join(sys.argv) + "\\n")
assert data.startswith("set default_transaction_read_only=on;"), "read-only prefix missing"
for marker in ("Q4a", "Q4b", "Q4c"):
    if f"-- {marker}" in data:
        if os.environ.get("FAKE_PSQL_FAIL") == marker.lower():
            sys.stderr.write(f"psql: {marker} synthetic failure\\n")
            sys.exit(3)
        p = os.path.join(os.environ["FAKE_PSQL_DIR"], marker.lower() + ".out")
        if os.path.exists(p):
            sys.stdout.write(open(p).read())
        sys.exit(0)
sys.stderr.write("no Q4 marker in stdin\\n")
sys.exit(1)
"""


class SliceTests(unittest.TestCase):
    def setUp(self):
        self.sql = QUERIES.read_text(encoding="utf-8")

    def test_real_q4_blocks_slice_cleanly(self):
        for marker in ("Q4a", "Q4b", "Q4c"):
            raw = cr.slice_block(self.sql, marker)
            self.assertTrue(raw.startswith(f"-- {marker}"), marker)
            stmt = cr.assert_single_select(raw, marker)
            self.assertTrue(stmt.lstrip().upper().startswith("SELECT"), marker)
            self.assertTrue(stmt.rstrip().endswith(";"), marker)
            self.assertIn("batch_id", stmt, marker)

    def test_missing_block_refused(self):
        with self.assertRaises(SystemExit) as e:
            cr.slice_block(self.sql, "Q9z")
        self.assertEqual(e.exception.code, 2)

    def test_non_select_block_refused(self):
        with self.assertRaises(SystemExit) as e:
            cr.assert_single_select("-- Q4b\nDELETE FROM questions;", "Q4b")
        self.assertEqual(e.exception.code, 2)

    def test_write_token_inside_select_refused(self):
        with self.assertRaises(SystemExit) as e:
            cr.assert_single_select("-- Q4b\nSELECT 1 WHERE 'x' = 'DROP TABLE q';", "Q4b")
        self.assertEqual(e.exception.code, 2)

    def test_widened_tokens_refused(self):
        for tok in ("CREATE", "GRANT", "COPY", "MERGE", "INTO", "EXPLAIN", "DO", "CALL", "REVOKE"):
            with self.subTest(tok=tok), self.assertRaises(SystemExit) as e:
                cr.assert_single_select(f"-- Q4b\nSELECT 1 WHERE 'x' = '{tok} TABLE q';", "Q4b")
            self.assertEqual(e.exception.code, 2)


class PgEnvTests(unittest.TestCase):
    def test_full_url(self):
        env = cr.pg_env_from_url("postgres://u%40x:p%40ss%3Aw@db.example.test:6543/fakedb?sslmode=prefer")
        self.assertEqual(env["PGHOST"], "db.example.test")
        self.assertEqual(env["PGPORT"], "6543")
        self.assertEqual(env["PGUSER"], "u@x")
        self.assertEqual(env["PGPASSWORD"], "p@ss:w")
        self.assertEqual(env["PGDATABASE"], "fakedb")
        self.assertEqual(env["PGSSLMODE"], "prefer")

    def test_defaults(self):
        env = cr.pg_env_from_url("postgres://u@db.example.test/db")
        self.assertEqual(env["PGPORT"], "5432")
        self.assertEqual(env["PGPASSWORD"], "")
        self.assertEqual(env["PGSSLMODE"], "require")

    def test_not_a_postgres_url(self):
        with self.assertRaises(SystemExit) as e:
            cr.pg_env_from_url("not-a-url")
        self.assertEqual(e.exception.code, 2)

    def test_db_env_file_beats_env_var(self):
        """Precedence: explicit --db-env > ambient DATABASE_URL env > load_db_url fallback — and the
        SOURCE (never the value) is announced on stderr."""
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("DATABASE_URL=postgres://file.invalid/y\n")
            envfile = f.name
        try:
            with patch.dict(os.environ, {"DATABASE_URL": "postgres://env.invalid/x"}):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(cr.resolve_db_url(envfile), "postgres://file.invalid/y")
                self.assertIn(f"DB URL from --db-env {envfile}", err.getvalue())

                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(cr.resolve_db_url(None), "postgres://env.invalid/x")
                self.assertIn("DB URL from DATABASE_URL env", err.getvalue())
                self.assertNotIn("postgres://", err.getvalue())  # source named, never the URL
        finally:
            os.unlink(envfile)


class ArtefactTests(unittest.TestCase):
    def setUp(self):
        self.line = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
        self.q = json.loads(self.line)

    def test_fields_ids_and_order(self):
        fields, _, nparts = cr.question_artefacts(self.q)
        self.assertEqual(nparts, 3)
        self.assertEqual([(f["id"], f["field"]) for f in fields], [
            ("Q1.stem", "question_text"),
            ("Q1.stem_sinhala", "question_text_sinhala"),
            ("Q1.ans1.approach", "approach"),
            ("Q1.ans1.final", "final_answer_latex"),
            ("Q1.ans2.final", "final_answer_latex"),   # ans2 approach is null → omitted
            ("Q1.a.text", "text"),
            ("Q1.a.text_sinhala", "text_sinhala"),
            ("Q1.a.approach", "approach"),             # single sub_answer → unnumbered
            ("Q1.a.final", "final_answer_latex"),
            ("Q1.a.i.text", "text"),                   # nested label path, depth-first
            ("Q1.b.text_sinhala", "text_sinhala"),     # b text is null → omitted
            ("Q1.b.ans1.approach", "approach"),        # two sub_answers → ans<k> numbered
            ("Q1.b.ans1.final", "final_answer_latex"),
            ("Q1.b.ans2.approach", "approach"),
            ("Q1.b.ans2.final", "final_answer_latex"),
        ])

    def test_figures_visual_check_ids_with_uuid(self):
        """`<id>\t<answer_or_sub_answer_id or ->` — the uuid column maps ans<k> to a row even when
        q4b's created_at ordering disagrees with the staged order visual-check numbered by."""
        _, figs, _ = cr.question_artefacts(self.q)
        self.assertEqual(figs, [
            "Q1\t-",                                                  # question diagram — no answer row
            "Q1.ans2\t00000000-0000-4000-8000-000000000102",
            "Q1.a\t-",                                                # part diagram — no answer row
            "Q1.b.ans2\t00000000-0000-4000-8000-000000000203",
        ])

    def test_orphan_part_lands_under_orphan_id(self):
        """A part whose parent_sub_question_id is missing from the set must not vanish — it is
        emitted as `Q<n>.ORPHAN<k>` (fields + figures + count) with a stderr WARNING."""
        q = json.loads(self.line)
        q["parts"].append({"sub_question_id": "00000000-0000-4000-8000-000000000077",
                           "label": "z", "text": "orphan text", "text_sinhala": None,
                           "sort_order": 9,
                           "parent_sub_question_id": "00000000-0000-4000-8000-0000000000ee",
                           "diagram_dsl": {"template": "t_orphan"},
                           "sub_answers": [{"sub_answer_id": "00000000-0000-4000-8000-000000000204",
                                            "approach": "orphan app", "final_answer_latex": "$z$",
                                            "diagram_dsl": None}]})
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            fields, figs, nparts = cr.question_artefacts(q)
        self.assertEqual(nparts, 4)
        self.assertIn("critic-read: WARNING Q1: 1 orphan part(s)", err.getvalue())
        ids = [f["id"] for f in fields]
        for wanted in ("Q1.ORPHAN1.text", "Q1.ORPHAN1.approach", "Q1.ORPHAN1.final"):
            self.assertIn(wanted, ids)
        self.assertIn("Q1.ORPHAN1\t-", figs)


class EndToEnd(unittest.TestCase):
    """A fake `psql` binary on PATH; DATABASE_URL is a synthetic URL. The fake prints the canned
    file for whichever Q4 marker it finds on stdin — missing file means 0 rows."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.bindir = root / "bin"
        self.bindir.mkdir()
        psql = self.bindir / "psql"
        psql.write_text(FAKE_PSQL, encoding="utf-8")
        psql.chmod(0o755)
        self.canned = root / "canned"
        self.canned.mkdir()
        self.argv_log = root / "argv.log"
        self.out = root / "out"
        self.env = {
            "PATH": f"{self.bindir}{os.pathsep}{os.environ.get('PATH', '')}",
            "DATABASE_URL": "postgres://critic:s3cret%40pw@db.invalid.test:6543/fakedb",
            "FAKE_PSQL_DIR": str(self.canned),
            "FAKE_PSQL_ARGV": str(self.argv_log),
            "VIBHAGA_ADMIN_ENV": "/nonexistent/offline-test-only",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, self.env), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = cr.main(list(args))
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def write_canned(self, q4a=None, q4b=None, q4c=None):
        for marker, text in (("q4a", q4a), ("q4b", q4b), ("q4c", q4c)):
            if text is not None:
                (self.canned / f"{marker}.out").write_text(text, encoding="utf-8")

    def test_non_uuid_batch_id_exits_2(self):
        rc, _, err = self.run_main("not-a-uuid", "--out", str(self.out))
        self.assertEqual(rc, 2)
        self.assertIn("not a uuid", err)

    def test_session_not_found_exits_1(self):
        self.write_canned(q4a="", q4b="ignored\n", q4c="")
        rc, _, err = self.run_main(BID, "--out", str(self.out))
        self.assertEqual(rc, 1)
        self.assertIn("session not found", err)
        self.assertFalse((self.out / "q4a.json").exists())

    def test_zero_questions_exits_1(self):
        self.write_canned(q4a=json.dumps({"batch_id": BID}) + "\n", q4b="", q4c="")
        rc, _, err = self.run_main(BID, "--out", str(self.out))
        self.assertEqual(rc, 1)
        self.assertIn("no questions", err)
        self.assertTrue((self.out / "q4a.json").exists())
        self.assertFalse((self.out / "q4b.jsonl").exists())

    def test_psql_nonzero_exits_1_naming_the_block(self):
        self.write_canned(q4a=json.dumps({"batch_id": BID}) + "\n")
        self.env["FAKE_PSQL_FAIL"] = "q4b"
        rc, _, err = self.run_main(BID, "--out", str(self.out))
        self.assertEqual(rc, 1)
        self.assertIn("psql failed on q4b", err)
        self.assertIn("synthetic failure", err)

    def test_happy_path_artefacts_and_argv_hygiene(self):
        self.write_canned(
            q4a=json.dumps({"batch_id": BID, "name": "synthetic session"}) + "\n",
            q4b=FIXTURE.read_text(encoding="utf-8"),
            q4c=json.dumps({"question_id": "00000000-0000-4000-8000-000000000099",
                            "question_number": 7, "source_paper_id": None,
                            "source_batch_id": "00000000-0000-4000-8000-000000000098",
                            "stem_excerpt": "other row"}) + "\n")
        rc, out, err = self.run_main(BID, "--out", str(self.out))
        self.assertEqual(rc, 0, err)
        self.assertIn("critic-read: DB URL from DATABASE_URL env", err)
        self.assertNotIn("s3cret", err)
        self.assertIn(f"critic-read: 1 question(s) · 3 part(s) · 4 figure(s) · "
                      f"1 other row(s) on the same lessons → {self.out}", out)

        session = json.loads((self.out / "q4a.json").read_text(encoding="utf-8"))
        self.assertEqual(session["batch_id"], BID)
        self.assertEqual((self.out / "q4b.jsonl").read_text(encoding="utf-8").splitlines()[0],
                         FIXTURE.read_text(encoding="utf-8").splitlines()[0])
        q4c_lines = (self.out / "q4c.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(q4c_lines), 1)
        self.assertEqual(json.loads(q4c_lines[0])["question_number"], 7)
        self.assertEqual(len(json.loads((self.out / "fields.json").read_text(encoding="utf-8"))), 15)
        line = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual((self.out / "hashes.txt").read_text(encoding="utf-8").strip(),
                         f"Q1 {hashlib.sha256(line.encode('utf-8')).hexdigest()}")
        self.assertEqual((self.out / "figures.txt").read_text(encoding="utf-8").splitlines(),
                         ["Q1\t-", "Q1.ans2\t00000000-0000-4000-8000-000000000102",
                          "Q1.a\t-", "Q1.b.ans2\t00000000-0000-4000-8000-000000000203"])

        # the URL and its password must never reach psql's argv — PG* env only
        argv_text = self.argv_log.read_text(encoding="utf-8")
        self.assertIn(f"batch_id={BID}", argv_text)
        self.assertIn("ON_ERROR_STOP=1", argv_text)
        self.assertIn("\t-w\t", argv_text)  # never prompt for a password
        self.assertNotIn("postgres://", argv_text)
        self.assertNotIn("s3cret", argv_text)
        self.assertNotIn("db.invalid.test", argv_text)


if __name__ == "__main__":
    unittest.main()
