#!/usr/bin/env python3
"""Offline unit-notation checks over synthetic Sinhala fields."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "tools" / "unit-notation.py"


def write_content(run: Path, body: str) -> Path:
    run.mkdir(parents=True, exist_ok=True)
    path = run / "content.yaml"
    path.write_text(body, encoding="utf-8")
    return path


class UnitNotationTest(unittest.TestCase):
    def run_tool(self, path: Path):
        return subprocess.run([sys.executable, str(TOOL), str(path)],
                              capture_output=True, text=True, check=False)

    def test_rejects_numbered_words_abbreviations_and_transliterations(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            path = write_content(run, """\
questions:
  - n: 1
    stem_si: "$4$ සෙන්ටිමීටර"
    parts:
      - label: a
        text_si: "12 සෙ.මී."
        parts:
          - label: i
            approach_si: "5 කි.ග්‍රෑ."
  - n: 2
    stem_si: "$3.5$ ක්ම්, ක්මී"
""")
            result = self.run_tool(run)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL Q1 stem_si: $4$ සෙන්ටිමීටර", result.stdout)
        self.assertIn("FAIL Q1.a text_si: 12 සෙ.මී.", result.stdout)
        self.assertIn("FAIL Q1.a.i approach_si: 5 කි.ග්‍රෑ.", result.stdout)
        self.assertIn("FAIL Q2 stem_si: ක්ම්", result.stdout)
        self.assertIn("FAIL Q2 stem_si: ක්මී", result.stdout)
        self.assertIn("unit-notation: 5 fail(s)", result.stdout)

    def test_accepts_english_symbols_and_unit_words_in_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_content(run, """\
questions:
  - n: 3
    stem_si: "$4$ cm"
    final_si: "සෙන්ටිමීටර්වලින් දක්වන්න."
    approach_si: "මීටර් කීයක් ද?"
    parts:
      - label: a
        text_si: "$4\\\\ \\\\text{cm}$"
        final_si: "$250$ g"
      - label: b
        approach_si: "ග්‍රෑම්, මිලිග්‍රෑම්වලට හරවන්න."
""")
            result = self.run_tool(run)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unit-notation: 0 fail(s)", result.stdout)

    def test_rejects_unit_words_before_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_content(run, """\
questions:
  - n: 4
    stem_si: "දිග සෙන්ටිමීටර් $4$කි."
  - n: 5
    stem_si: "ඝන සෙන්ටිමීටර් $192$ක්"
  - n: 6
    stem_si: "වර්ග මීටර් 8"
""")
            result = self.run_tool(run)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL Q4 stem_si:", result.stdout)
        self.assertIn("FAIL Q5 stem_si: ඝන සෙන්ටිමීටර් $192$", result.stdout)
        self.assertIn("FAIL Q6 stem_si: වර්ග මීටර් 8", result.stdout)
        self.assertIn("not සෙන්ටිමීටර් $4$", result.stdout)
        self.assertIn("unit-notation: 3 fail(s)", result.stdout)

    def test_math_segments_do_not_pair_across_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_content(run, """\
questions:
  - n: 7
    stem_si: "$a$ හා $b$ සෙන්ටිමීටර් ..."
""")
            result = self.run_tool(run)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL Q7 stem_si: $b$ සෙන්ටිමීටර්", result.stdout)
        self.assertNotIn("$ හා $", result.stdout)
        self.assertIn("unit-notation: 1 fail(s)", result.stdout)

    def test_accepts_a_content_yaml_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_content(Path(tmp) / "run", "questions: []\n")
            result = self.run_tool(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
