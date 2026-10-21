import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "si-style.py"
SPEC = importlib.util.spec_from_file_location("si_style_test", TOOL)
si_style = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(si_style)


class SinhalaStyleTests(unittest.TestCase):
    def test_mechanical_warnings(self):
        text = ("වන අතර වන අතර කරනු ලැබේ "
                + " ".join(["සිංහල"] * 26)
                + " English cm A AB ABCD කරුණාකර")
        findings = si_style.field_warnings(text)
        self.assertTrue(any("වන අතර" in item for item in findings))
        self.assertIn("passive construction", findings)
        self.assertTrue(any("sentence has" in item for item in findings))
        self.assertIn("Latin word 'English'", findings)
        self.assertIn("Latin word 'ABCD'", findings)
        self.assertNotIn("Latin word 'cm'", findings)
        self.assertNotIn("Latin word 'A'", findings)
        self.assertNotIn("Latin word 'AB'", findings)
        self.assertIn("contains කරුණාකර", findings)

    def test_point_labels_and_set_notation_are_not_latin_words(self):
        self.assertEqual(si_style.field_warnings("POT, n(A)"), [])

    def test_long_sentence_limit_is_thirty_words(self):
        thirty = " ".join(["සිංහල"] * 30)
        thirty_one = " ".join(["සිංහල"] * 31)
        self.assertFalse(any("sentence has" in item
                             for item in si_style.field_warnings(thirty)))
        self.assertIn("sentence has 31 words (max 30)",
                      si_style.field_warnings(thirty_one))

    def test_markup_is_stripped_before_scanning(self):
        self.assertEqual(si_style.field_warnings(
            "$$English XYZ කරුණාකර$$ `Latin` $cm$ A."),
            ["Latin word 'Latin'"])

    def test_main_names_question_and_part_and_never_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / "content.yaml").write_text(
                "questions:\n"
                "  - n: 4\n"
                "    stem_si: 'කරුණාකර පවුල් 3ක්'\n"
                "    parts:\n"
                "      - label: b\n"
                "        text_si: 'English'\n", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = si_style.main([str(run)])
        self.assertEqual(rc, 0)
        self.assertIn("si-style: 1 warn(s) · Q4.stem_si", output.getvalue())
        self.assertIn("si-style: 1 warn(s) · Q4.b.text_si", output.getvalue())


if __name__ == "__main__":
    unittest.main()
