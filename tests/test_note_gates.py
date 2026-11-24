#!/usr/bin/env python3
"""tools/note-gates.py — offline tests over synthetic note bodies (no corpus, no Admin, no network).
The terminology subprocess is stubbed; its own tests live in test_check_si_terms.py."""
import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent.parent / "tools"
SPEC = importlib.util.spec_from_file_location("note_gates", TOOLS / "note-gates.py")
ng = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ng)

EN = "## Rule\n\nFor $x > 0$, $\\lg 10x = 1 + \\lg x$.\n\n$$\n\\lg 100 = 2\n$$\n\nDone.\n"
SI = "## නීතිය\n\n$x > 0$ සඳහා $\\lg 10x = 1 + \\lg x$ වේ.\n\n$$\n\\lg 100 = 2\n$$\n\nඅවසන්.\n"


def ok_proc(*_a, **_k):
    return subprocess.CompletedProcess([], 0, "check-si-terms: OK", "")


class NoteGates(unittest.TestCase):
    def run_gate(self, en=EN, si=SI, diagrams="[]", proc=ok_proc):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d)
            (w / "en.md").write_text(en, encoding="utf-8")
            (w / "si.md").write_text(si, encoding="utf-8")
            (w / "diagrams.json").write_text(diagrams, encoding="utf-8")
            out = io.StringIO()
            with patch.object(ng.subprocess, "run", side_effect=proc) as run, contextlib.redirect_stdout(out):
                code = ng.main([str(w), "--grade", "11"])
            terms = json.loads((w / "terms.json").read_text(encoding="utf-8")) if (w / "terms.json").exists() else None
        return code, out.getvalue(), run, terms

    def test_pass_writes_terms_and_calls_checker(self):
        code, out, run, terms = self.run_gate()
        self.assertEqual(code, 0, out)
        self.assertIn("3 identical maths spans, 1 display", out)
        self.assertTrue(out.rstrip().endswith("note-gates: ok"))
        self.assertEqual(terms, {"note": EN, "note_si": SI})
        argv = run.call_args_list[0].args[0]
        self.assertIn("--grade", argv)
        self.assertEqual(argv[argv.index("--grade") + 1], "11")

    def test_terms_failure_fails(self):
        code, out, *_ = self.run_gate(proc=lambda *a, **k: subprocess.CompletedProcess([], 1, "FAIL x", ""))
        self.assertEqual(code, 1)
        self.assertIn("FAIL Sinhala terminology", out)

    def test_hard_failures(self):
        cases = {
            "order": (EN, SI.replace("$x > 0$ සඳහා $\\lg 10x = 1 + \\lg x$", "$\\lg 10x = 1 + \\lg x$ සඳහා $x > 0$"),
                      "maths span 1 differs"),
            "count": (EN, SI.replace("$x > 0$ සඳහා ", ""), "maths span 1 differs"),
            "sinhala-in-text": (EN, SI.replace("$x > 0$", "$x \\text{ ධන }$"), "Sinhala inside maths"),
            "unclosed": (EN.replace("$x > 0$", "$x > 0"), SI, "bad maths span"),
            "tight-display": (EN.replace(".\n\n$$", ".\n$$"), SI.replace("වේ.\n\n$$", "වේ.\n$$"), "blank line"),
            "blank": ("  \n", SI, "blank body"),
            "nul": (EN + "\0", SI, "NUL"),
            "huge": (EN + "a" * 50_001, SI, "API ceiling"),
        }
        for name, (en, si, want) in cases.items():
            with self.subTest(name):
                code, out, run, _ = self.run_gate(en, si)
                self.assertEqual(code, 1, out)
                self.assertIn(want, out)
                run.assert_not_called()

    def test_diagrams(self):
        ref = "\n::diagram[1]\n"
        for name, (diagrams, want) in {
            "missing-ref": ("[{}]", "::diagram[1] has no document"),
            "not-array": ("{}", "JSON array"),
            "too-many": (json.dumps([{}] * 21), "at most 20"),
            "bad-json": ("[", "diagrams.json"),
        }.items():
            with self.subTest(name):
                code, out, *_ = self.run_gate(EN + ref, SI + ref, diagrams)
                self.assertEqual(code, 1, out)
                self.assertIn(want, out)

    def test_vdd_failure_fails(self):
        calls = iter([ok_proc(), subprocess.CompletedProcess([], 1, "", "invalid VDD at index 0")])
        ref = "\n::diagram[0]\n"
        code, out, run, _ = self.run_gate(EN + ref, SI + ref, "[{}]", proc=lambda *a, **k: next(calls))
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL VDD", out)
        self.assertEqual(run.call_count, 2)

    def test_warnings_do_not_fail(self):
        wide = "$$\n\\begin{aligned}\n" + " + ".join(["\\overline{3}.8753"] * 6) + "\n\\end{aligned}\n$$\n"
        en = EN + "\n| a | b |\n\n" + wide
        si = SI + "\n| a | b |\n\n" + wide
        code, out, *_ = self.run_gate(en, si)
        self.assertEqual(code, 0, out)
        self.assertIn("pipe-table row", out)
        self.assertIn("may scroll at 375 px", out)
        short = EN + "\n$$\n\\begin{aligned}\nx &= 1 \\\\\ny &= 2\n\\end{aligned}\n$$\n"
        code, out, *_ = self.run_gate(short, SI + short[len(EN):])
        self.assertEqual(code, 0, out)
        self.assertNotIn("WARN", out)


if __name__ == "__main__":
    unittest.main()
