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
        self.assertEqual(
            (self.out / "hashes.txt").read_text(encoding="utf-8").splitlines(),
            [f"# critic-read hashes v1 sid={BID}",
             f"Q1 {hashlib.sha256(line.encode('utf-8')).hexdigest()}"])
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


class HashesMode(EndToEnd):
    """`hashes <sid>` (W9-H1) — the hashes.txt computation alone, through the same Q4b read."""

    def test_hashes_prints_and_writes(self):
        self.write_canned(q4b=FIXTURE.read_text(encoding="utf-8"))
        rc, out, err = self.run_main("hashes", BID)
        self.assertEqual(rc, 0, err)
        want = [f"# critic-read hashes v1 sid={BID}",
                f"Q1 {hashlib.sha256(FIXTURE.read_text().splitlines()[0].encode()).hexdigest()}"]
        self.assertEqual(out.strip().splitlines(), want)
        # --out writes the same lines — a valid --previous file by provenance
        rc, out, _ = self.run_main("hashes", BID, "--out", str(self.out / "h.txt"))
        self.assertEqual(rc, 0)
        self.assertEqual((self.out / "h.txt").read_text().strip().splitlines(), want)

    def test_hashes_non_uuid_and_empty_batch(self):
        rc, _, err = self.run_main("hashes", "not-a-uuid")
        self.assertEqual(rc, 2)
        self.assertIn("not a uuid", err)
        self.write_canned(q4b="")
        rc, _, err = self.run_main("hashes", BID)
        self.assertEqual(rc, 1)
        self.assertIn("no questions", err)


class PreviousMode(EndToEnd):
    """`--previous` (W9-H2) — changed-only fields/figures + carried.txt + the printed line."""

    def prev_dir(self, entries, sid=BID):
        d = self.out / "prev"
        d.mkdir(parents=True)
        (d / "hashes.txt").write_text(
            f"# critic-read hashes v1 sid={sid}\n"
            + "".join(f"{q} {h}\n" for q, h in entries), encoding="utf-8")
        return d

    def fixture_hash(self):
        return hashlib.sha256(FIXTURE.read_text().splitlines()[0].encode()).hexdigest()

    def test_unchanged_question_is_carried(self):
        self.write_canned(
            q4a=json.dumps({"batch_id": BID}) + "\n",
            q4b=FIXTURE.read_text(encoding="utf-8"), q4c="")
        prev = self.prev_dir([("Q1", self.fixture_hash()), ("Q9", "0" * 64)])
        rc, out, _ = self.run_main(BID, "--out", str(self.out), "--previous", str(prev))
        self.assertEqual(rc, 0)
        self.assertIn("changed: [] · carried: ['Q1'] · gone: ['Q9']", out)
        self.assertEqual(json.loads((self.out / "fields.json").read_text()), [])
        self.assertEqual((self.out / "figures.txt").read_text(), "")
        self.assertEqual((self.out / "carried.txt").read_text().strip(),
                         f"Q1 {self.fixture_hash()}")

    def test_changed_question_gets_fields(self):
        self.write_canned(
            q4a=json.dumps({"batch_id": BID}) + "\n",
            q4b=FIXTURE.read_text(encoding="utf-8"), q4c="")
        prev = self.prev_dir([("Q1", "f" * 64)])
        rc, out, _ = self.run_main(BID, "--out", str(self.out), "--previous", str(prev))
        self.assertEqual(rc, 0)
        self.assertIn("changed: ['Q1'] · carried: []", out)
        self.assertEqual(len(json.loads((self.out / "fields.json").read_text())), 15)
        self.assertIn("Q1\t-", (self.out / "figures.txt").read_text())

    def test_previous_accepts_a_hashes_file_and_bad_lines_die(self):
        self.write_canned(
            q4a=json.dumps({"batch_id": BID}) + "\n",
            q4b=FIXTURE.read_text(encoding="utf-8"), q4c="")
        f = Path(self.tmp.name) / "old.txt"
        f.write_text(f"# critic-read hashes v1 sid={BID}\nnot a hashes line\n",
                     encoding="utf-8")
        rc, _, err = self.run_main(BID, "--out", str(self.out), "--previous", str(f))
        self.assertEqual(rc, 2)
        self.assertIn("bad line", err)

    def test_previous_refuses_a_file_with_no_header(self):
        # a bare `Q<n> <sha256>` file — even one whose hash matches the current batch — must not
        # mark a question carried: only critic-read's own output (header line) counts
        self.write_canned(
            q4a=json.dumps({"batch_id": BID}) + "\n",
            q4b=FIXTURE.read_text(encoding="utf-8"), q4c="")
        f = Path(self.tmp.name) / "forged.txt"
        f.write_text(f"Q1 {self.fixture_hash()}\n", encoding="utf-8")
        rc, _, err = self.run_main(BID, "--out", str(self.out), "--previous", str(f))
        self.assertEqual(rc, 2)
        self.assertIn("not a critic-read hashes file", err)

    def test_previous_refuses_a_different_sessions_hashes(self):
        self.write_canned(
            q4a=json.dumps({"batch_id": BID}) + "\n",
            q4b=FIXTURE.read_text(encoding="utf-8"), q4c="")
        prev = self.prev_dir([("Q1", self.fixture_hash())],
                             sid="00000000-0000-4000-8000-0000000000aa")
        rc, _, err = self.run_main(BID, "--out", str(self.out), "--previous", str(prev))
        self.assertEqual(rc, 2)
        self.assertIn("≠ this batch", err)


MINI_CARD = """\
schema_version: 1
grade: 6
subject: Mathematics
medium: si
lesson_number: {nn}
title_en: {title}
title_si: {title} (si)
syllabus_refs: ["1.1"]
term: 1
periods: 2
source: {{file: "lessons/{slug}.md", sha256: "0000000000000000000000000000000000000000000000000000000000000001"}}
generated:
  sections:
    - {{number: "1.1", title: "First section of {title}"}}
  vocabulary: ["{title}-term"]
  worked_examples: []
  exercises: []
  activities: []
  figure_kinds: []
  figures: 0
  tables: 0
  summary: []
curated:
  status: drafted
  not_taught: []
  prerequisites: []
  difficulty_hooks: []
"""


class BriefTests(unittest.TestCase):
    """The critic pack: brief.txt = scope-cards brief for exactly the session's lessons —
    Q4a's session_lessons mapped to NN-*.yaml cards (sort_order ÷ 10), grade from the
    session row. No DB, no psql — write_brief is the unit under test."""

    def _corpus(self, tmp: Path, cards: dict) -> Path:
        d = tmp / "corpus" / "maths" / "grade-06" / "scope-cards"
        d.mkdir(parents=True)
        for nn, title in cards.items():
            (d / f"{nn:02d}-{title}.yaml").write_text(
                MINI_CARD.format(nn=nn, title=title, slug=f"{nn:02d}-{title}"),
                encoding="utf-8")
        return tmp / "corpus"

    def _session(self, *lessons) -> dict:
        return {"grade": 6, "session_lessons": [
            {"lesson_id": f"00000000-0000-4000-8000-0000000000{n:02x}",
             "sort_order": n * 10, "name": name} for n, name in lessons]}

    def test_brief_maps_each_session_lesson_to_its_card(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "rows"
            out.mkdir()
            corpus = self._corpus(Path(td), {1: "Alpha", 2: "Beta"})
            session = self._session((1, "Alpha"), (2, "Beta"), (3, "Gamma"))
            p = cr.write_brief(out, session, corpus)
            text = p.read_text(encoding="utf-8")
            self.assertIn("== 01-Alpha.yaml — Alpha", text)
            self.assertIn("Alpha-term", text)          # the real brief body made it in
            self.assertIn("== 02-Beta.yaml — Beta", text)
            self.assertIn("== lesson 03 (Gamma) — no scope card found", text)

    def test_title_mismatch_warns_and_no_corpus_says_so(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "rows"
            out.mkdir()
            corpus = self._corpus(Path(td), {1: "Alpha"})
            session = self._session((1, "Not-Alpha"))
            p = cr.write_brief(out, session, corpus)
            self.assertIn("title_en 'Alpha' ≠ lesson name 'Not-Alpha'",
                          p.read_text(encoding="utf-8"))
            p2 = cr.write_brief(out, session, None)
            self.assertIn("grade/corpus unresolved", p2.read_text(encoding="utf-8"))

    def test_lesson_with_no_sort_order_is_named_not_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "rows"
            out.mkdir()
            corpus = self._corpus(Path(td), {1: "Alpha"})
            session = self._session((1, "Alpha"))
            session["session_lessons"].append({"lesson_id": "x", "name": "Mystery"})
            text = cr.write_brief(out, session, corpus).read_text(encoding="utf-8")
            self.assertIn("== lesson ? (Mystery) — no scope card found", text)


class CorpusResolution(EndToEnd):
    """W12 A6 — a chunked round-2 critic wrote 'no scope cards found' briefs: without
    --corpus or VIBHAGA_CORPUS the fallback pointed INSIDE the plugin checkout
    (<plugin>/Vibhaga-Maths-Corpus — one directory short of the real sibling). Every
    chunk critic must resolve the corpus the same way the lead does."""

    def test_fallback_is_the_sibling_checkout(self):
        with patch.dict(os.environ, {}, clear=True):       # VIBHAGA_CORPUS absent
            p = cr.corpus_candidate(None)
        self.assertEqual(p, TOOLS.parent.parent / "Vibhaga-Maths-Corpus")

    def test_env_then_flag_order(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"VIBHAGA_CORPUS": td}):
                self.assertEqual(cr.corpus_candidate(None), Path(td))
                self.assertEqual(cr.corpus_candidate("/flag/wins"),
                                 Path("/flag/wins"))

    def test_brief_uses_env_corpus_end_to_end(self):
        """The regression itself: VIBHAGA_CORPUS reaches write_brief through main() —
        brief.txt holds the real card brief, never 'no scope card found'."""
        with tempfile.TemporaryDirectory() as td:
            cards_dir = Path(td) / "corpus" / "maths" / "grade-06" / "scope-cards"
            cards_dir.mkdir(parents=True)
            (cards_dir / "01-Alpha.yaml").write_text(
                MINI_CARD.format(nn=1, title="Alpha", slug="01-Alpha"),
                encoding="utf-8")
            self.write_canned(
                q4a=json.dumps({"batch_id": BID, "grade": 6, "session_lessons": [
                    {"lesson_id": "00000000-0000-4000-8000-000000000001",
                     "sort_order": 10, "name": "Alpha"}]}) + "\n",
                q4b=FIXTURE.read_text(encoding="utf-8"), q4c="")
            self.env["VIBHAGA_CORPUS"] = str(Path(td) / "corpus")
            rc, _out, err = self.run_main(BID, "--out", str(self.out))
            self.assertEqual(rc, 0, err)
            text = (self.out / "brief.txt").read_text(encoding="utf-8")
            self.assertIn("== 01-Alpha.yaml — Alpha", text)
            self.assertNotIn("no scope card found", text)
            self.assertIn(f"critic-read: corpus {Path(td) / 'corpus'}", err)

    def test_flag_beats_env_end_to_end(self):
        """--corpus wins over VIBHAGA_CORPUS — the flag corpus's card is the one
        briefed (a chunk spawn must be able to override the ambient env)."""
        with tempfile.TemporaryDirectory() as td:
            for sub, title in (("env-corpus", "EnvCard"), ("flag-corpus", "FlagCard")):
                d = Path(td) / sub / "maths" / "grade-06" / "scope-cards"
                d.mkdir(parents=True)
                (d / f"01-{title}.yaml").write_text(
                    MINI_CARD.format(nn=1, title=title, slug=f"01-{title}"),
                    encoding="utf-8")
            self.write_canned(
                q4a=json.dumps({"batch_id": BID, "grade": 6, "session_lessons": [
                    {"lesson_id": "00000000-0000-4000-8000-000000000001",
                     "sort_order": 10, "name": "FlagCard"}]}) + "\n",
                q4b=FIXTURE.read_text(encoding="utf-8"), q4c="")
            self.env["VIBHAGA_CORPUS"] = str(Path(td) / "env-corpus")
            rc, _out, err = self.run_main(BID, "--out", str(self.out),
                                          "--corpus", str(Path(td) / "flag-corpus"))
            self.assertEqual(rc, 0, err)
            text = (self.out / "brief.txt").read_text(encoding="utf-8")
            self.assertIn("01-FlagCard.yaml — FlagCard", text)
            self.assertNotIn("EnvCard", text)


if __name__ == "__main__":
    unittest.main()
