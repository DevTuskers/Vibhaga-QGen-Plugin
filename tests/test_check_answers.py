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
    check: "divmod(925, 40) == (23, 5) and 20 < 23 <= 20 + 3 and (3, 1)[0] == 3 and not 0"
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

    def test_sequence_repetition_refused_before_it_allocates(self):
        # [1]*10**9 is legal syntax but an ~8 GB bomb — refused by the length cap,
        # never materialised (a MemoryError would escape the per-leaf catch)
        for expr in ("[1] * 10**9 == [1]", "(1,) * 10**18 == (1,)", "sorted([1]*2000) == [1]"):
            with self.subTest(expr=expr), tempfile.TemporaryDirectory() as td:
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
                self.assertIn("exceed", r.stdout, expr)

    def test_sequence_at_the_cap_still_evaluates(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "1000"
    check: "sum([1] * 1000) == 1000"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bigint_bomb_refused_by_the_value_cap(self):
        # each ** exponent is ≤ MAX_POW, but the intermediate 2**1000 blows the
        # |value| cap — the chain never reaches its second exponentiation
        for expr in ("(2 ** 1000) ** 1000 > 0", "10 ** 20 == 1",
                     "10**14 * 10**14 == 10**28"):
            with self.subTest(expr=expr), tempfile.TemporaryDirectory() as td:
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

    def test_deep_nesting_refused_not_crashed(self):
        # 3000 nested unary minuses — refused by the node cap or the parser, never a crash
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "1"
    check: "%s1 == 1"
""" % ("-" * 3000))
            r = run_tool(run)
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL Q1", r.stdout)

    def test_check_without_a_comparison_fails(self):
        for expr in ("True", "sum([1, 2, 3])", "abs(-5) * 2"):
            with self.subTest(expr=expr), tempfile.TemporaryDirectory() as td:
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
                self.assertIn("no comparison", r.stdout, expr)

    def test_same_literal_comparison_is_a_tautology(self):
        # every side a literal — same value or not — computes nothing
        for expr in ("1 == 1", "2.5 <= 2.5", "1 < 2", "(1, 2) == (1, 2)",
                     "[1] == [1]", "-5 < 0", "40 * 23 == 920 or 7 == 7"):
            with self.subTest(expr=expr), tempfile.TemporaryDirectory() as td:
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
                self.assertIn("constant-only", r.stdout, expr)

    def test_one_computed_side_is_enough(self):
        # -20 is a bare negative literal, but the BinOp side makes it a real check
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "-20"
    check: "5 * -4 == -20"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

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

    # ---- W12: `check: "none — <reason>"`, len(), tuple comparisons ----------
    def test_check_none_em_dash_counts_as_unchecked(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "name the shape"
    final: "a triangle"
    check: "none — a naming answer computes nothing"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("0 checked · 0 false · 0 warn · 0 without check · "
                          "1 unchecked (check: none)", r.stdout)
            self.assertNotIn("WARN Q1", r.stdout)

    def test_check_none_ascii_dash(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "acute"
    check: "none - an angle classification is not a computation"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 unchecked (check: none)", r.stdout)

    def test_check_none_short_reason_refused(self):
        # a reason <10 chars after a valid dash is refused naming the reason rule;
        # `none` with a dash and NO reason at all dies at the parser instead
        for expr in ("none — short", "none - x", "none — too brief"):
            with self.subTest(expr=expr), tempfile.TemporaryDirectory() as td:
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
                self.assertIn("reason", r.stdout, expr)
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "1"
    check: "none —"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL Q1", r.stdout)

    def test_len_and_tuple_compare_in_whitelist(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "4"
    check: "len(sorted([4, 1, 2])) == 3 and divmod(925, 40) == (23, 5) and divmod(925, 40) < (24, 0)"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 checked", r.stdout)

    def test_tuple_of_constants_vs_constants_still_constant_only(self):
        # whitelisting tuple comparisons does NOT reopen the tautology hole
        with tempfile.TemporaryDirectory() as td:
            run = write_run(Path(td), """\
  - n: 1
    lessons: [L01]
    stem: "x"
    approach: "…"
    final: "1"
    check: "(1, 2) == (1, 2) or len([1, 1]) == 2"
""")
            r = run_tool(run)
            self.assertEqual(r.returncode, 1)
            self.assertIn("constant-only", r.stdout)

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
