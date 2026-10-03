#!/usr/bin/env python3
"""tests/test_check_answers.py — offline tests for tools/check-answers.py (W10 answers-as-code).

Synthetic content.yaml files only — the evaluator is the unit under test: the whitelist,
the True verdict, and the `final`-number coverage warn.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "tools" / "check-answers.py"

BASE = """\
id_seed: "synthetic"
lessons:
  L01: 00000000-0000-4000-8000-000000000001
questions:
  - n: 1
    lessons: [L01]
    stem: "Multiply."
    parts:
      - label: a
        text: "Compute."
        approach: "…"
        final: "$920$"
        check: "40 * 23 == 920"
        level: M
"""


def write_run(tmp: Path, questions: str) -> Path:
    run = tmp / "run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "content.yaml").write_text(BASE.split("questions:")[0] + "questions:\n" + questions,
                                      encoding="utf-8")
    return run


def run_tool(path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), str(path)],
                          capture_output=True, text=True)


class CheckAnswersTest(unittest.TestCase):
    def test_true_check_passes(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), BASE.split("questions:\n", 1)[1])
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 checked · 0 false · 0 warn · 0 without check", r.stdout)

    def test_false_check_fails(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "919"
    check: "40 * 23 == 919"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL Q1: check evaluates to False", r.stdout)

    def test_eval_error_fails(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "1"
    check: "1 / 0 == 1"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 1)
            self.assertIn("eval error", r.stdout)

    def test_forbidden_call_and_attribute_refused(self):
        for expr in ("open('/tmp/x') == 1", "__import__('os') is not None",
                     "(1).__class__ == int", "ceil.__name__ == 'ceil'"):
            with tempfile.TemporaryDirectory() as td:
                run = write_run(Path(td), f"""\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "1"
    check: {expr!r}
""")
                r = run_tool(run)
                self.assertEqual(r.returncode, 1, expr)
                self.assertIn("refused", r.stdout, expr)

    def test_chained_compare_tuple_call_and_subscript_pass(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "23"
    check: "divmod(925, 40) == (23, 5) and 20 < 23 <= 23 and (3, 1)[0] == 3 and not 0"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_huge_pow_refused_not_hung(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "1"
    check: "10 ** (10 ** 8) > 0"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 1)
            self.assertIn("exponent", r.stdout)

    def test_final_number_not_covered_warns(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "$7$"
    check: "40 * 23 == 920"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("WARN Q1: final number 7 not covered by check", r.stdout)

    def test_final_number_covered_by_a_subexpression(self):
        # 920 is no literal in the check — it is the VALUE of the Call node round(920.4)
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "$920$"
    check: "round(920.4) > 900"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("not covered", r.stdout)

    def test_no_check_warns_and_counts(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "name it"
    final: "a triangle"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("WARN Q1: no check", r.stdout)
            self.assertIn("0 checked · 0 false · 0 warn · 1 without check", r.stdout)

    def test_nested_leaf_names_and_level_are_ignored_fields(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 2
    lessons: [L01]
    stem: "x"
    parts:
      - label: a
        text: "outer"
        parts:
          - label: i
            text: "inner"
            approach: "…"
            final: "5"
            check: "10 // 2 == 5"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 checked", r.stdout)


if __name__ == "__main__":
    unittest.main()
