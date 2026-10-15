"""tests/test_check_layout.py — readable-layout gate tests with synthetic text only."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "check-layout.py"
SPEC = importlib.util.spec_from_file_location("check_layout", TOOL)
check_layout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_layout)


class CheckLayoutTest(unittest.TestCase):
    def run_fields(self, fields):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fields.json"
            path.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(TOOL), "--fields", str(path)],
                capture_output=True, text=True, encoding="utf-8",
            )

    def field(self, field, text, item_id="Q1"):
        return {"id": item_id, "field": field, "text": text}

    def test_sinhala_answer_fields_parse_and_gate(self):
        """0024: the *_sinhala answer fields are the same kinds in the other language — a Sinhala
        approach with two steps on ONE line FAILs exactly like the English one does."""
        self.assertEqual(check_layout.field_kind("a:one:approach_sinhala"), "APPROACH")
        self.assertEqual(check_layout.field_kind("a:one:final_sinhala"), "FINAL")
        self.assertEqual(check_layout.field_kind("sa:x:approach_sinhala"), "APPROACH")
        self.assertEqual(check_layout.field_kind("sa:x:final_sinhala"), "FINAL")
        result = self.run_fields([
            self.field("a:one:approach_sinhala",
                       "පළමු පියවර. දෙවන පියවර. තුන්වන පියවර."),
        ])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL Q1 a:one:approach_sinhala", result.stdout)

    def test_three_sentence_approach_fails(self):
        result = self.run_fields([
            self.field("a:one:approach", "First step. Second step. Third step.")
        ])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL Q1 a:one:approach ¶1: 3 sentences", result.stdout)

    def test_blank_lines_split_approach_steps(self):
        result = self.run_fields([
            self.field("a:one:approach", "First step.\n\nSecond step.\n\nThird step.")
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_200_character_approach_fails(self):
        result = self.run_fields([self.field("a:one:approach", "a" * 199 + ".")])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("200 chars > 180", result.stdout)

    def test_two_sentence_approach_warns_without_failing(self):
        result = self.run_fields([
            self.field("a:one:approach", "First step. Second step.")
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARN Q1 a:one:approach ¶1: 2 sentences", result.stdout)
        self.assertIn("0 fail(s) · 1 warn(s)", result.stdout)

    def test_table_lists_and_display_math_are_excluded_from_length(self):
        long = "x" * 300
        text = (
            "Short setup.\n"
            f"| {long} | {long} |\n"
            "|---|---|\n"
            f"- {long}\n"
            f"2. {long}\n"
            "$$\n"
            f"{long}\n"
            f"\n{long}\n"
            "$$\n"
            f"$${long}$$\n"
            "Done."
        )
        result = self.run_fields([self.field("a:one:approach", text)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_inline_decimal_math_and_parenthetical_period_count_correctly(self):
        result = self.run_fields([
            self.field("a:one:approach", "The values $40.53$ and $3.5$ are exact."),
            self.field("a:two:approach", "එය හරි යයි.) තවත් දෙයක්."),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARN Q1 a:two:approach ¶1: 2 sentences", result.stdout)
        self.assertIn("0 fail(s) · 1 warn(s)", result.stdout)

    def test_sinhala_sentence_pair_warns(self):
        result = self.run_fields([
            self.field("question_text", "මෙය එකකි. මෙය දෙකද?")
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARN Q1 question_text ¶1: 2 sentences", result.stdout)

    def test_sinhala_dotted_abbreviation_is_not_a_sentence_end(self):
        result = self.run_fields([
            self.field("question_text", "සමන් ප.ව. 4.30 ට පාසලෙන් පිටත් වෙයි.")
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_english_dotted_abbreviation_is_not_a_sentence_end(self):
        result = self.run_fields([
            self.field("a:one:approach", "Leave at 7 a.m. and walk home.")
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_abbreviation_does_not_hide_real_sentence_ends(self):
        result = self.run_fields([
            self.field(
                "a:one:approach",
                "සමන් පෙ.ව. 7 ට පිටත් වෙයි. ඔහු පැයක් ඇවිදියි. "
                "ඉන්පසු ඔහු නවතියි.",
            )
        ])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("3 sentences", result.stdout)

    def test_abbreviation_at_paragraph_end_counts_once(self):
        result = self.run_fields([
            self.field("a:one:approach", "ඔහු එන්නේ ප.ව.")
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_currency_marker_periods_are_not_sentence_ends(self):
        result = self.run_fields([
            self.field("question_text", "පොතක මිල රු. 250 කි."),
            self.field("a:one:approach", "It costs Rs. 120 in total."),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_currency_marker_does_not_hide_real_sentence_ends(self):
        result = self.run_fields([
            self.field(
                "a:one:approach",
                "ඔහු රු. 50 ක් දුන්නේ ය. ඔහු ගියේ ය. ඇය ආවා ය.",
            )
        ])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("3 sentences", result.stdout)

    def test_spaced_sinhala_time_abbreviations_are_not_sentence_ends(self):
        result = self.run_fields([
            self.field("question_text", "සමන් පෙ. ව. 7.30 ට පිටත් වෙයි."),
            self.field("a:one:approach", "ඔහු එන්නේ ප. ව."),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_lone_sinhala_time_tokens_are_not_abbreviations(self):
        result = self.run_fields([
            self.field("a:one:approach", "ප. අද."),
            self.field("a:two:approach", "ව. අද."),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("2 sentences"), 2, result.stdout)

    def test_dot_runs_for_fill_in_blanks_are_not_sentence_ends(self):
        result = self.run_fields([
            self.field("sq:one:text", "පාද ගණන ............ වේ.")
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_roman_numeral_list_lines_are_excluded(self):
        result = self.run_fields([
            self.field(
                "question_text",
                "හිස් තැන් පුරවන්න:\n\n"
                "i. පළමුවැන්න ........ වේ.\n"
                "ii. දෙවැන්න ........ වේ.\n"
                "iii. තෙවැන්න ........ වේ.",
            ),
            self.field(
                "question_text",
                "(i) පළමුවැන්න ........ වේ. (ii) දෙවැන්න ........ වේ.",
            ),
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 fail(s) · 0 warn(s)", result.stdout)

    def test_roman_numeral_list_marker_regex(self):
        for marker in (
            "i. ", "ii. ", "iii. ", "iv. ", "v. ", "vi. ",
            "viii. ", "ix. ", "x. ", "(i) ", "II. ",
        ):
            with self.subTest(marker=marker):
                self.assertIsNotNone(check_layout.LIST_ITEM.match(marker))
        for marker in ("il. ", "xi. "):
            with self.subTest(marker=marker):
                self.assertIsNone(check_layout.LIST_ITEM.match(marker))

    def test_roman_list_marker_in_middle_does_not_hide_sentence_end(self):
        result = self.run_fields([
            self.field("a:one:approach", "Find x. Then add 2. Then stop.")
        ])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("3 sentences", result.stdout)

    def test_stem_length_warn_and_fail_thresholds(self):
        warning = self.run_fields([self.field("question_text", "a" * 199 + ".")])
        self.assertEqual(warning.returncode, 0, warning.stdout + warning.stderr)
        self.assertIn("WARN Q1 question_text ¶1: 200 chars > 180", warning.stdout)
        self.assertIn("0 fail(s) · 1 warn(s)", warning.stdout)

        failure = self.run_fields([self.field("question_text", "a" * 249 + ".")])
        self.assertEqual(failure.returncode, 1, failure.stdout + failure.stderr)
        self.assertIn("250 chars > 240", failure.stdout)

    def test_field_kind_parsing(self):
        self.assertEqual(check_layout.field_kind("sq2:part:text"), "PART")
        self.assertEqual(check_layout.field_kind("sa2:answer:approach"), "APPROACH")
        self.assertEqual(check_layout.field_kind("question_text_sinhala"), "STEM")

    def test_staged_json_positional_input(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "staged.json"
            path.write_text(json.dumps({
                "questions": [{"question_number": 1, "question_text": "A short stem."}]
            }), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(TOOL), str(path)],
                capture_output=True, text=True, encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("check-layout: 0 fail(s) · 0 warn(s) · 1 fields", result.stdout)


if __name__ == "__main__":
    unittest.main()
