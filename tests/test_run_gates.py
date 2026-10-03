#!/usr/bin/env python3
"""tests/test_run_gates.py — offline tests for tools/run-gates.py (W9 item E).

No tool is actually run: a stub runner is injected — it records every argv, returns canned
(exit, output), and fakes `doc get` by writing the server.json the chain then diffs. Covers
stage ordering, stop-at-first-failure, the doc-compare ignore list, and exit propagation.
"""
import importlib.util
import io
import json
import os
import shutil
import subprocess
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
        {"question_id": ID1, "question_number": 1, "stem": "one",
         "question_text": "one stem"},
        {"question_id": ID2, "question_number": 2, "stem": "two",
         "question_text": "two stem"}]}), encoding="utf-8")
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
        if any(a.endswith("vdd_templates.py") for a in argv) and "build" in argv:
            # emit <id>.json + <id>-claims.txt per spec, the way vdd_templates build does —
            # the audit stage requires the files to exist
            specs = json.loads(Path(argv[argv.index("build") + 1]).read_text())
            out_dir = Path(argv[argv.index("--out") + 1])
            out_dir.mkdir(exist_ok=True)
            for s in rg.pl.figure_specs(specs):
                fid = s.get("figure_id") if isinstance(s, dict) else None
                if fid:
                    (out_dir / f"{fid}.json").write_text("{}", encoding="utf-8")
                    (out_dir / f"{fid}-claims.txt").write_text("claims:\n", encoding="utf-8")
            return 0, ""
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

    def test_dict_keyed_specs_gate_every_figure(self):
        # a {figure_id: spec} map yields its values — the shared normalisation, so stage 2
        # audits/vdd-checks each figure instead of silently gating zero
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "specs" / "figures.json").write_text(json.dumps(
                {"Q1": {"template": "shaded_grid", "figure_id": "Q1"},
                 "Q2": {"template": "number_line", "figure_id": "Q2"}}), encoding="utf-8")
            stub = StubRunner()
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            gates = json.loads((run / "gates.json").read_text())
            for k in ("audit:Q1", "audit:Q2", "vdd-check:Q1", "vdd-check:Q2"):
                self.assertIn(k, gates)
            self.assertIn("2 figures", out.getvalue())

    def test_nonempty_specs_with_no_figure_ids_dies_before_stage_1(self):
        # a non-empty file that yields zero figure ids must not report "gates: ok — 0 figures"
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "specs" / "figures.json").write_text(
                json.dumps([{"template": "shaded_grid"}]), encoding="utf-8")  # no figure_id
            stub = StubRunner()
            with self.assertRaises(SystemExit) as e:
                rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(e.exception.code, 2)
            self.assertEqual(stub.calls, [])

    def test_hand_drawn_figures_are_audited_too(self):
        # specs ∪ content.yaml figures: a hand-drawn figure is gated exactly like a
        # template-built one (audit + vdd-check on its own files)
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "figures").mkdir(exist_ok=True)
            (run / "figures" / "Q7.json").write_text("{}", encoding="utf-8")
            (run / "figures" / "Q7-claims.txt").write_text("claims:\n", encoding="utf-8")
            (run / "content.yaml").write_text(
                "id_seed: t\nfigures: {H7: figures/Q7.json}\nquestions: []\n",
                encoding="utf-8")
            stub = StubRunner()
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            audits = [" ".join(c) for c in stub.calls if "audit-claim-set" in " ".join(c)]
            vdds = [" ".join(c) for c in stub.calls if "vdd-check" in " ".join(c)]
            self.assertTrue(any("Q7-claims.txt" in c for c in audits), audits)
            self.assertTrue(any("Q7.json" in c for c in vdds), vdds)
            gates = json.loads((run / "gates.json").read_text())
            self.assertEqual(gates["audit:Q7"], 0)
            self.assertEqual(gates["vdd-check:Q7"], 0)
            self.assertIn("Q7 audit ok · vdd-check ok", out.getvalue())
            self.assertIn("3 figures", out.getvalue())

    def test_hand_figure_missing_claims_fails_the_stage(self):
        # a content.yaml figure with no <id>-claims.txt must fail loudly, not pass unaudited
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "figures").mkdir(exist_ok=True)
            (run / "figures" / "Q7.json").write_text("{}", encoding="utf-8")
            (run / "content.yaml").write_text(
                "id_seed: t\nfigures: {H7: figures/Q7.json}\nquestions: []\n",
                encoding="utf-8")
            stub = StubRunner()
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 1)
            self.assertIn("Q7-claims.txt", out.getvalue())
            self.assertEqual(json.loads((run / "gates.json").read_text())["audit:Q7"], 1)
            # the audit subprocess was never even invoked for Q7
            self.assertFalse(any("audit-claim-set" in " ".join(c) and "Q7" in " ".join(c)
                                 for c in stub.calls))

    def test_all_hand_drawn_run_skips_the_template_stage(self):
        # specs/figures.json absent → every figure hand-drawn; stage 1 skips with a log line
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "specs" / "figures.json").unlink()
            (run / "figures").mkdir(exist_ok=True)
            (run / "figures" / "Q7.json").write_text("{}", encoding="utf-8")
            (run / "figures" / "Q7-claims.txt").write_text("claims:\n", encoding="utf-8")
            (run / "content.yaml").write_text(
                "id_seed: t\nfigures: {H7: figures/Q7.json}\nquestions: []\n",
                encoding="utf-8")
            stub = StubRunner()
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            self.assertIn("templates: skipped — no specs/figures.json", out.getvalue())
            self.assertFalse(any("vdd_templates" in " ".join(c) for c in stub.calls))
            self.assertTrue(any("Q7-claims.txt" in " ".join(c) for c in stub.calls))

    def test_figure_file_stem_must_match_its_staged_id(self):
        # visual-check resolves <id>-claims.txt by the STAGED id (Q3, Q3.a) — a file named
        # anything else audits under its basename but then assesses claims-less in both modes.
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "specs" / "figures.json").write_text("[]", encoding="utf-8")
            (run / "figures").mkdir(exist_ok=True)
            (run / "figures" / "pic.json").write_text("{}", encoding="utf-8")
            (run / "figures" / "pic-claims.txt").write_text("claims:\n", encoding="utf-8")
            (run / "content.yaml").write_text(
                "id_seed: t\nfigures: {F1: figures/pic.json}\nquestions:\n"
                "  - {n: 3, stem: s, lessons: [L1], figure: F1, approach: a, final: f}\n",
                encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=StubRunner())
            self.assertEqual(rc, 1)
            self.assertIn("figure F1 file pic.json is used at Q3 — name it Q3.json "
                          "so visual-check finds its claim set", out.getvalue())
            self.assertEqual(json.loads((run / "gates.json").read_text())["audit:pic"], 1)
            # naming the file after its staged id clears the check — same run, renamed
            (run / "figures" / "pic.json").rename(run / "figures" / "Q3.json")
            (run / "figures" / "pic-claims.txt").rename(run / "figures" / "Q3-claims.txt")
            (run / "content.yaml").write_text(
                "id_seed: t\nfigures: {F1: figures/Q3.json}\nquestions:\n"
                "  - {n: 3, stem: s, lessons: [L1], figure: F1, approach: a, final: f}\n",
                encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                rc = rg.cmd_build(build_args(run), runner=StubRunner())
            self.assertEqual(rc, 0)

    def test_figure_file_stem_must_match_its_staged_id_parts(self):
        # same check at part depth: a part's figure is staged as Q<n>.<label[.label…]>
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "specs" / "figures.json").write_text("[]", encoding="utf-8")
            (run / "figures").mkdir(exist_ok=True)
            (run / "figures" / "pic.json").write_text("{}", encoding="utf-8")
            (run / "figures" / "pic-claims.txt").write_text("claims:\n", encoding="utf-8")
            (run / "content.yaml").write_text(
                "id_seed: t\nfigures: {F2: figures/pic.json}\nquestions:\n"
                "  - {n: 3, stem: s, lessons: [L1], parts:\n"
                "     [{label: a, text: t, figure: F2, approach: x, final: y}]}\n",
                encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=StubRunner())
            self.assertEqual(rc, 1)
            self.assertIn("used at Q3.a — name it Q3.a.json", out.getvalue())

    def test_figures_map_dict_value_dies_like_build_staged(self):
        # build-staged accepts only {key: path-string} — stage 2 must refuse the dict shape
        # too, not carry a usage error later into the chain
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            (run / "content.yaml").write_text(
                "id_seed: t\nfigures: {H7: {file: figures/Q7.json}}\nquestions: []\n",
                encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                rg.cmd_build(build_args(run), runner=StubRunner())
            self.assertEqual(cm.exception.code, 2)

    def test_markdown_gate_blocks_stop_the_build(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.canned.append((lambda j: "markdown-gate" in j, 1,
                                "Q2 · question_text\n"
                                "   [block] M2-displayMathInline — line 3\n"
                                "1 fields · 1 BLOCKED\n"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 1)
            self.assertIn("[block] M2-displayMathInline", out.getvalue())
            self.assertFalse(any("visual-check" in " ".join(c) for c in stub.calls))
            gates = json.loads((run / "gates.json").read_text())
            self.assertEqual(gates["markdown-gate"], 1)

    def test_markdown_gate_stage_order_and_fields_file(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.canned.append((lambda j: "markdown-gate" in j, 0, "2 fields · 0 BLOCKED\n"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_build(build_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            joined = [" ".join(c) for c in stub.calls]
            i_staged = next(i for i, c in enumerate(joined) if "build-staged" in c)
            i_mg = next(i for i, c in enumerate(joined) if "markdown-gate" in c)
            i_vc = next(i for i, c in enumerate(joined) if "visual-check" in c)
            self.assertLess(i_staged, i_mg)
            self.assertLess(i_mg, i_vc)
            fields = json.loads((run / "fields.json").read_text())
            self.assertEqual([(f["id"], f["field"]) for f in fields],
                             [("Q1", "question_text"), ("Q2", "question_text")])
            self.assertIn("markdown-gate: 2 fields · 0 BLOCKED", out.getvalue())
            self.assertEqual(json.loads((run / "gates.json").read_text())["markdown-gate"], 0)

    def test_staged_fields_matches_fields_py_field_set(self):
        # the same set run-gate.sh's fields_py produces: stems (+_sinhala), answers[] AND the
        # singular sub_answer, part texts, sq/sa at depth 1, sq2/sa2 below
        staged = {"questions": [{
            "question_id": ID1, "question_number": 1,
            "question_text": "stem", "question_text_sinhala": "si",
            "answers": [{"answer_id": "a1", "approach": "app", "final_answer_latex": "fin"}],
            "sub_questions": [{
                "sub_question_id": "s1", "label": "a",
                "text": "part", "text_sinhala": "parsi",
                "sub_answer": {"sub_answer_id": "s2",
                               "approach": "pa", "final_answer_latex": "pf"},
                "sub_questions": [{
                    "sub_question_id": "s3", "label": "i", "text": "deep",
                    "sub_answer": {"sub_answer_id": "s4",
                                   "approach": "da", "final_answer_latex": "df"}}]}]}]}
        got = [(f["id"], f["field"]) for f in rg.staged_fields(staged)]
        self.assertEqual(got, [
            ("Q1", "question_text"), ("Q1", "question_text_sinhala"),
            ("Q1", "a:a1:approach"), ("Q1", "a:a1:final"),
            ("Q1/a", "sq:s1:text"), ("Q1/a", "sq:s1:text_sinhala"),
            ("Q1/a", "sa:s2:approach"), ("Q1/a", "sa:s2:final"),
            ("Q1/a/i", "sq2:s3:text"),
            ("Q1/a/i", "sa2:s4:approach"), ("Q1/a/i", "sa2:s4:final")])

    def test_markdown_gate_real_binary(self):
        # one real invocation: a single-line $$…$$ stem blocks, a clean field passes.
        # markdown-gate bundles the renderer from the sibling checkouts — resolve them the way
        # the sibling convention does (env, then walking up from the plugin dir so a worktree
        # under a sibling dir finds the umbrella checkouts too).
        env = dict(os.environ)
        for var, name in (("VIBHAGA_WEB", "Vibhaga-Web"), ("VIBHAGA_ADMIN", "Vibhaga-Admin")):
            if env.get(var):
                continue
            d = TOOLS.parent
            while not (d / name).is_dir() and d.parent != d:
                d = d.parent
            if (d / name).is_dir():
                env[var] = str(d / name)
        if not shutil.which("node") or "VIBHAGA_WEB" not in env or "VIBHAGA_ADMIN" not in env:
            self.skipTest("node or the sibling checkouts (Vibhaga-Web/Vibhaga-Admin) unavailable")
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "fields.json"
            f.write_text(json.dumps([{"id": "Q1", "field": "question_text",
                                      "text": "Consider these. $$x \\times 2$$ find it."}]),
                         encoding="utf-8")
            r = subprocess.run(["node", str(TOOLS / "markdown-gate.mjs"), "--fields", str(f)],
                               capture_output=True, text=True, env=env)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("BLOCKED", r.stdout + r.stderr)
            f.write_text(json.dumps([{"id": "Q1", "field": "question_text",
                                      "text": "Consider $x \\times 2$ — find it."}]),
                         encoding="utf-8")
            r = subprocess.run(["node", str(TOOLS / "markdown-gate.mjs"), "--fields", str(f)],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("0 BLOCKED", r.stdout + r.stderr)

    def test_card_without_grade_is_usage_error(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            with self.assertRaises(SystemExit) as e:
                rg.cmd_build(build_args(run, card=["L07=7"]), runner=stub)
            self.assertEqual(e.exception.code, 2)
            self.assertEqual(stub.calls, [])          # refused before any stage ran

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

    def test_doc_diff_matches_by_id_reorder_and_server_extra_warns(self):
        # doc put merges INTO the server array — order is meaningless and kept_unlisted rows
        # stay; a reordered server doc + one extra question must be a WARN, not a failure
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            staged_qs = json.loads((run / "staged.json").read_text())["questions"]
            extra = {"question_id": "00000000-0000-4000-8000-000000000099",
                     "question_number": 9, "stem": "server only"}
            stub.doc_get_questions = [extra] + list(reversed(staged_qs))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_ship(ship_args(run), runner=stub)
            self.assertEqual(rc, 0, out.getvalue())
            self.assertIn("WARN server holds Q9", out.getvalue())
            self.assertIn("kept_unlisted", out.getvalue())

    def test_doc_diff_missing_on_server_fails_before_publish(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            stub = StubRunner()
            stub.doc_get_questions = [
                {"question_id": ID1, "question_number": 1, "stem": "one"}]
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_ship(ship_args(run), runner=stub)
            self.assertEqual(rc, 1)
            self.assertIn("missing on the server", out.getvalue())
            self.assertFalse(any(" publish " in f" {' '.join(c)} " for c in stub.calls))

    def test_doc_diff_fails_cleanly_on_malformed_entries(self):
        # a non-dict staged entry or a server row without question_id → FAIL lines + exit 1,
        # never a traceback
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td))
            staged = json.loads((run / "staged.json").read_text())
            staged["questions"].append("not-a-dict")
            (run / "staged.json").write_text(json.dumps(staged), encoding="utf-8")
            stub = StubRunner()
            stub.doc_get_questions = [dict(q) for q in staged["questions"][:2]] + [{"no_id": 1}]
            out = io.StringIO()
            with redirect_stdout(out):
                rc = rg.cmd_ship(ship_args(run), runner=stub)
            self.assertEqual(rc, 1)
            self.assertIn("not a question object", out.getvalue())
            self.assertFalse(any(" publish " in f" {' '.join(c)} " for c in stub.calls))

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
            sess = next(" ".join(c) for c in stub2.calls if "--session" in c)
            # no <run>/figures dir → the pre-change bare argv; an absent dir makes
            # visual-check die, and a figure-less run has no claim sets to pair anyway
            self.assertNotIn("--claims-dir", sess)
            self.assertNotIn("--staged", sess)
            # with figures/ present, the local staged.json IS the server doc (doc get just
            # proved it) and the claim sets go to the live preview — allow:/departures apply
            (run / "figures").mkdir()
            stub3 = StubRunner()
            with redirect_stdout(io.StringIO()):
                rc = rg.cmd_ship(ship_args(run, session_check=True), runner=stub3)
            self.assertEqual(rc, 0)
            sess = next(" ".join(c) for c in stub3.calls if "--session" in c)
            self.assertIn(f"--staged {run / 'staged.json'}", sess)
            self.assertIn(f"--claims-dir {run / 'figures'}", sess)


if __name__ == "__main__":
    unittest.main()
