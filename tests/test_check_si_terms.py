import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "check-si-terms.py"
SPEC = importlib.util.spec_from_file_location("check_si_terms_test", TOOL)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "content.yaml"


def run_tool(doc_text: str, *extra):
    with tempfile.TemporaryDirectory() as td:
        doc = Path(td) / "content.yaml"
        doc.write_text(doc_text, encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = mod.main([str(doc), *extra])
        return rc, out.getvalue()


GOOD = """\
questions:
  - n: 1
    stem: "Use a compass to draw a circle of radius $5$ cm. Draw a chord and the central angle of a sector."
    stem_si: "කවකටුව භාවිතයෙන් අරය $5$ cm ක වෘත්තයක් අඳින්න. කේන්ද්‍රික ඛණ්ඩයක ජ්‍යායයක් සහ කේන්ද්‍රික කෝණය අඳින්න."
    approach: "The chord subtends the central angle."
    approach_si: "ජ්‍යායය කේන්ද්‍රික කෝණයට අදාල වේ."
    final: "Done."
    final_si: "සම්පූර්ණයි."
"""


class CheckSiTermsTests(unittest.TestCase):
    def test_known_bad_strings_all_flagged(self):
        bad = """\
questions:
  - n: 1
    stem: "Use a compass to draw the circle. Mark the central angle."
    stem_si: "කාරණදාර භාවිතයෙන් වෘත්තය අඳින්න. කේන්ද්‍රීය කෝණය සලකුණු කරන්න."
  - n: 2
    stem: "Classify each event as certain, likely or unlikely."
    stem_si: "එක් එක් සිදුවීම නිශ්චිත, බොහෝ දුරට සිදු වන නැතහොත් අසම්භාව්‍ය ලෙස වර්ග කරන්න."
  - n: 3
    stem: "Draw a bearing from O to P."
    stem_si: "O සිට P දක්වා දිශාංකයක් අඳින්න."
  - n: 4
    stem: "Complete the pictograph."
    stem_si: "සංකේත ප්‍රස්තාරය සම්පූර්ණ කරන්න."
"""
        rc, out = run_tool(bad, "--grade", "8")
        self.assertEqual(rc, 1)
        self.assertIn("කාරණදාර", out)
        self.assertIn("කේන්ද්රීය කෝණය", out.replace("‍", ""))
        self.assertIn("සංකේත ප්රස්තාරය", out.replace("‍", ""))
        self.assertIn("දිශාංකය", out)
        self.assertIn("නිශ්චිත", out)
        self.assertIn("බොහෝ දුරට", out)
        self.assertIn("අසම්භාව්", out)

    def test_dictionary_renderings_pass(self):
        rc, out = run_tool(GOOD, "--grade", "8")
        self.assertEqual(rc, 0, out)
        self.assertIn("OK", out)

    def test_shared_fixture_is_clean(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = mod.main([str(FIXTURE)])
        self.assertEqual(rc, 0, out.getvalue())

    def test_wrong_grade_variant_flagged(self):
        # G7 spells the event class ස්ථීරවම සිදුවන සිද්ධිය; a G8 doc must use
        # ස්ථිරවම සිදු වන සිදුවීම — the G7 spelling must not pass at grade 8.
        doc = """\
questions:
  - n: 1
    stem: "Classify the event: a certain event, an impossible event, a random event."
    stem_si: "සිදුවීම වර්ග කරන්න: ස්ථීරවම සිදුවන සිද්ධියක්, ස්ථීරවම සිදුනොවන සිද්ධියක්, අහඹු සිදුවීමක්."
"""
        rc8, out8 = run_tool(doc, "--grade", "8")
        rc7, _ = run_tool(doc, "--grade", "7")
        self.assertEqual(rc8, 1)
        self.assertEqual(rc7, 0, "G7 spelling must pass at grade 7")

    def test_banned_checked_even_without_english_pair(self):
        doc = """\
questions:
  - n: 1
    stem_si: "කාරණදාර ගෙන වෘත්තයක් අඳින්න."
"""
        rc, out = run_tool(doc)
        self.assertEqual(rc, 1)
        self.assertIn("කාරණදාර", out)

    def test_near_miss_spelling_flagged(self):
        doc = """\
questions:
  - n: 1
    stem: "The central angle of a sector is $60°$."
    stem_si: "කේන්ද්‍රික ඛණ්ඩයක කේන්ද්‍රීයා කෝණය $60°$ කි."
"""
        rc, out = run_tool(doc, "--grade", "8")
        self.assertEqual(rc, 1)
        self.assertIn("central angle", out)

    def test_term_present_tolerates_inflection(self):
        self.assertTrue(mod.term_present("කවකටුව", "කවකටුවෙන් අඳින්න"))
        self.assertTrue(mod.term_present("සරල රේඛාව", "සරල රේඛාවේ ලක්ෂ්‍ය"))
        self.assertFalse(mod.term_present("කවකටුව", "කෝදුවෙන් අඳින්න"))

    def test_iter_pairs_finds_si_and_sinhala_suffixes(self):
        doc = {"q": [{"n": 1, "stem": "en", "stem_si": "si1",
                      "question_text": "en2", "question_text_sinhala": "si2"}]}
        pairs = list(mod.iter_pairs(doc))
        ids = {p[0] for p in pairs}
        self.assertIn("Q1.stem_si", ids)
        self.assertIn("Q1.question_text_sinhala", ids)


if __name__ == "__main__":
    unittest.main()
