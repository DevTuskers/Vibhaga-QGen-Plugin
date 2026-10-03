#!/usr/bin/env python3
"""tests/test_run_gates.py — offline tests for tools/run-gates.py (W9 item E).

No tool is actually run: a stub runner is injected — it records every argv, returns canned
(exit, output), and fakes `doc get` by writing the server.json the chain then diffs. Covers
stage ordering, stop-at-first-failure, the doc-compare ignore list, and exit propagation.
"""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"

_spec = importlib.util.spec_from_file_location("run_gates", TOOLS / "run-gates.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)

SID = "00000000-0000-4000-8000-0000000000aa"
ID1 = "00000000-0000-4000-8000-000000000001"
ID2 = "00000000-0000-4000-8000-000000000002"


def make_run(tmp: Path) -> Path:
    run = tmp / "run"
    (run / "specs").mkdir(parents=True)
    (run / "specs" / "figures.json").write_text(
        json.dumps([{"template": "shaded_grid", "figure_id": "Q1"},
                    {"template": "number_line", "figure_id": "Q2"}]), encoding="utf-8")
    (run / "content.yaml").write_text("id_seed: t\nquestions: []\n", encoding="utf-8")
    (run / "staged.json").write_text(json.dumps({"questions": [
        {"question_id": ID1, "question_number": 1, "stem": "one"},
        {"question_id": ID2, "question_number": 2, "stem": "two"}]}), encoding="utf-8")
    (run / "ids.json").write_text(json.dumps([ID1, ID2]), encoding="utf-8")
    (run / "ledger.json").write_text('{"sessions": {}}', encoding="utf-8")
    return run


class StubRunner:
    """Records argv; returns canned (rc, out) by predicate; doc get writes a server.json."""

    def __init__(self):
        self.calls = []
        self.canned = []          # [(predicate(argv)->bool, rc, out)]
        self.doc_get_questions = None  # what the fake server answers (None = mirror staged)

    def __call__(self, argv):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        if "doc" in argv and "get" in argv:
            out_idx = argv.index("--out") + 1
            run_dir = Path(argv[out_idx]).parent
            staged = json.loads((run_dir / "staged.json").read_text())
            qs = self.doc_get_questions if self.doc_get_questions is not None \
                else [{**q, "published": True, "published_at": "2026-01-01T00:00:00Z"}
                      for q in staged["questions"]]
            Path(argv[out_idx]).write_text(
                json.dumps({"session": {}, "questions": qs, "stats": {}}), encoding="utf-8")
            return 0, "doc get: ready · 2 question(s)"
        for pred, rc, out in self.canned:
            if pred(joined):
                return rc, out
        return 0, ""


def build_args(run, **over):
    import argparse
    base = {"run": str(run), "medium": "sinhala", "vc_out": None, "card": [],
            "grade": None, "cards_dir": None}
    base.update(over)
    return argparse.Namespace(**base)


def ship_args(run, **over):
    import argparse
    base = {"run": str(run), "sid": SID, "scope": "grade=6,subject=Mathematics,medium=sinhala",
            "session_check": False, "vc_session_out": None, "accept_signatures": 0,
            "expected": None}
    base.update(over)
    return argparse.Namespace(**base)


class BuildTest(unittest.TestCase):
    def test_stage_order_and_success_output(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.canned.append((lambda j: "visual-check" in j, 0,
                                "Q1  PASS  font ok · labels 3 · target ok · arc — · shaded ok · "
                                "aspect ok · 375×131  → /vc/Q1/\n"
                                "Q2  PASS  font ok · aspect ok · 375×96  → /vc/Q2/\n"
                                "2 figures · 2 pass · PNGs: 12 · report: /vc/report.json · "
                                "contact: /vc/contact-light-375.png 830×400\n"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run, card=["L07=7"], grade=6, cards_dir="/tmp/x"),
                                  runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            stages = [" ".join(c) for c in stub.calls]
            i_tpl = next(i for i, c in enumerate(stages) if "vdd_templates" in c)
            i_aud1 = next(i for i, c in enumerate(stages) if "audit-claim-set" in c)
            i_vdd1 = next(i for i, c in enumerate(stages) if "vdd-check" in c)
            i_staged = next(i for i, c in enumerate(stages) if "build-staged" in c)
            i_vc = next(i for i, c in enumerate(stages) if "visual-check" in c)
            i_lint = next(i for i, c in enumerate(stages) if "precritic-lint" in c)
            self.assertLess(i_tpl, i_aud1)
            self.assertLess(i_aud1, i_vdd1)
            self.assertLess(i_vdd1, i_staged)
            self.assertLess(i_staged, i_vc)
            self.assertLess(i_vc, i_lint)
            # both figures audited before either is vdd-checked? No — per figure, audit then check
            audit_calls = [c for c in stages if "audit-claim-set" in c]
            vdd_calls = [c for c in stages if "vdd-check" in c]
            self.assertEqual(len(audit_calls), 2)
            self.assertEqual(len(vdd_calls), 2)
            self.assertIn("--medium sinhala", vdd_calls[0])
            self.assertIn("--claims", vdd_calls[0])
            self.assertIn("L07=7", stages[i_lint])
            self.assertIn("--grade 6", stages[i_lint])
            o = out.getvalue()
            self.assertIn("Q1 audit ok · vdd-check ok · vc PASS 375×131", o)
            self.assertIn("Q2 audit ok · vdd-check ok · vc PASS 375×96", o)
            self.assertIn("gates: ok — 2 figures, 2 questions, contact sheet "
                          "/vc/contact-light-375.png", o)
            gates = json.loads((run / "gates.json").read_text())
            self.assertEqual(gates["templates"], 0)
            self.assertEqual(gates["visual-check"], 0)
            self.assertEqual(gates["precritic-lint"], 0)

    def test_stops_at_first_failure_and_propagates_rc(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.canned.append((lambda j: "audit-claim-set" in j, 1,
                                "K2  shaded 3 of 5 cells  FAIL\nAudit A: 91 assertions, "
                                "1 failure(s)"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 1)
            self.assertIn("stage audit:Q1: exit 1 — stopping", out.getvalue())
            self.assertIn("Audit A: 91 assertions", out.getvalue())
            # nothing downstream ran
            joined = [" ".join(c) for c in stub.calls]
            self.assertFalse(any("build-staged" in c for c in joined))
            self.assertFalse(any("visual-check" in c for c in joined))
            gates = json.loads((run / "gates.json").read_text())
            self.assertEqual(gates, {"templates": 0, "audit:Q1": 1})

    def test_precritic_skipped_without_cards(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            self.assertIn("precritic-lint: skipped — no --card", out.getvalue())
            self.assertFalse(any("precritic" in " ".join(c) for c in stub.calls))

    def test_card_without_grade_is_usage_error(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            with self.assertRaises(SystemExit) as e:
                rg.cmd_build(build_args(run, card=["L07=7"]), runner=StubRunner())
            self.assertEqual(e.exception.code, 2)

    def test_precritic_fail_stops_and_propagates(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.canned.append((lambda j: "precritic-lint" in j, 1, "  FAIL Q1.a · probe 'x'"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run, card=["L07=7"], grade=6), runner=stub)
            self.assertEqual(rc, 1)
            self.assertIn("precritic-lint", json.loads((run / "gates.json").read_text()))


class ShipTest(unittest.TestCase):
    def test_order_quotes_and_expected_default(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.canned += [
                (lambda j: "validate" in j, 0, "validate: ok — 0 error(s), 1 warning(s)"),
                (lambda j: "--dry-run" in j, 0,
                 "dry-run: signatures_at_risk = 0 · unchanged_count = 0"),
                (lambda j: " publish " in " " + j + " " and "--dry-run" not in j, 0,
                 "published 2/2\nread-back 1: staged doc confirms 2 published + flagged\n"
                 "t77: 2 question(s) · 40 comparisons · 0 mismatch(es)\n"
                 "provenance: 2 id(s) · OK\nq3: PENDING — no VIBHAGA_ADMIN_AUTH_DB_URL"),
                (lambda j: "sql-proof" in j and " q2 " in " " + j, 0, "q2: ok"),
            ]
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_ship(ship_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            stages = [" ".join(c) for c in stub.calls]
            order = [next(i for i, c in enumerate(stages) if m in c)
                     for m in ("validate", "doc put", "doc get", "--dry-run", "q2")]
            self.assertEqual(order, sorted(order))
            publishes = [c for c in stages if " publish " in f" {c} "]
            self.assertEqual(len(publishes), 2)
            self.assertIn("--accept-signatures 0", publishes[0])
            o = out.getvalue()
            for line in ("validate: ok", "dry-run: signatures_at_risk = 0", "published 2/2",
                         "read-back 1", "t77:", "provenance: 2 id(s) · OK",
                         "q3: PENDING", "q2: ok", "ship: ok"):
                self.assertIn(line, o)
            # --expected defaulted to len(ids.json)
            q2call = next(c for c in stages if "sql-proof" in c)
            self.assertIn("--expected 2", q2call)
            gates = json.loads((run / "gates.json").read_text())
            self.assertEqual(gates["publish"], 0)

    def test_doc_diff_ignores_server_mirrors_and_stops_on_real_diff(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.doc_get_questions = None         # published/published_at are stripped — clean
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_ship(ship_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            # now a real diff — the server's Q2 stem differs
            run2 = make_run(Path(td) / "r2")
            stub2 = StubRunner()
            qs = json.loads((run2 / "staged.json").read_text())["questions"]
            qs[1]["stem"] = "CHANGED"
            stub2.doc_get_questions = qs
            out2 = io.StringIO()
            with redirect_stdout(out2):
                rc = rg.cmd_ship(ship_args(run2), runner=stub2)
            self.assertEqual(rc, 1)
            self.assertIn("Q2", out2.getvalue())
            self.assertFalse(any(" publish " in f" {' '.join(c)} " for c in stub2.calls))

    def test_publish_q3_not_ok_propagates_exit_5(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.canned.append(
                (lambda j: " publish " in f" {j} " and "--dry-run" not in j, 5,
                 "published 2/2\nq3: NOT ok — sessions=1"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_ship(ship_args(run), runner=stub)
            self.assertEqual(rc, 5)
            self.assertFalse(any("sql-proof" in " ".join(c) for c in stub.calls))
            gates = json.loads((run / "gates.json").read_text())
            self.assertEqual(gates["publish"], 5)

    def test_session_check_runs_only_when_asked(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            out = io.StringIO()
            with redirect_stdout(out):
                rg.cmd_ship(ship_args(run), runner=stub)
            self.assertIn("visual-check --session: skipped", out.getvalue())
            self.assertFalse(any("--session" in c for c in map(" ".join, stub.calls)))
            stub2 = StubRunner()
            with redirect_stdout(io.StringIO()):
                rc = rg.cmd_ship(ship_args(run, session_check=True), runner=stub2)
            self.assertEqual(rc, 0)
            self.assertTrue(any("--session" in c for c in map(" ".join, stub2.calls)))


if __name__ == "__main__":
    unittest.main()
