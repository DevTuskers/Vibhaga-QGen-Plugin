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
    parts:
      - label: a
        text_si: "$4\\\\ \\\\text{cm}$"
        final_si: "$250$ g"
    approach_si: "ග්‍රෑම්, මිලිග්‍රෑම්වලට හරවන්න."
""")
            result = self.run_tool(run)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unit-notation: 0 fail(s)", result.stdout)

    def test_accepts_a_content_yaml_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_content(Path(tmp) / "run", "questions: []\n")
            result = self.run_tool(path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
