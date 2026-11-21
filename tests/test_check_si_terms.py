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

    def test_bearing_format_entry_accepted(self):
        doc = """\
questions:
  - n: 1
    stem: "The bearing of P from O is given by the figure. Write it."
    stem_si: "රූපයෙන් O සිට P හි දිශාව දැක්වේ. O සිට P උ 50° නැ දිශාවෙන් පිහිටා ඇත."
"""
        rc, out = run_tool(doc, "--grade", "8")
        self.assertEqual(rc, 0, out)

    def test_bearing_format_missing_flagged(self):
        doc = """\
questions:
  - n: 1
    stem: "Write the bearing of P from O."
    stem_si: "O සිට P හි පිහිටීම ලියන්න."
"""
        rc, out = run_tool(doc, "--grade", "8")
        self.assertEqual(rc, 1)
        self.assertIn("bearing", out)

    def test_longer_term_match_suppresses_shorter(self):
        # "square root" must not demand the shape term වර්ගය/සමචතුරස්‍රය too
        doc = """\
questions:
  - n: 1
    stem: "Find the square root of $144$."
    stem_si: "$144$ හි වර්ගමූලය සොයන්න."
"""
        rc, out = run_tool(doc, "--grade", "8")
        self.assertEqual(rc, 0, out)

    def test_untaught_compound_still_suppresses_inner_word(self):
        # "right angle" has no G8 entry; at grade 8 neither the compound nor
        # the "angle" inside it is checked — the lexeme, not grade-activity,
        # decides suppression (un-taught terms are scope-card territory)
        doc = """\
questions:
  - n: 1
    stem: "Mark the right angle at B."
    stem_si: "B දී ලකුණු කරන්න."
"""
        rc, out = run_tool(doc, "--grade", "8")
        self.assertEqual(rc, 0, out)

    def test_compound_suppresses_inner_word_other_grade(self):
        # "north-east" is G6-only; at G8 it suppresses "north", so the correct
        # compound rendering ඊසාන (which contains no උතුර) passes
        doc = """\
questions:
  - n: 1
    stem: "Draw a line in the north-east direction."
    stem_si: "ඊසාන දිශාවට රේඛාවක් අඳින්න."
"""
        rc, out = run_tool(doc, "--grade", "8")
        self.assertEqual(rc, 0, out)

    def test_truncated_east_bearing_flagged(self):
        doc = """\
questions:
  - n: 1
    stem: "Write the bearing of P from O."
    stem_si: "O සිට P උ 50° න දිශාවෙන් පිහිටා ඇත."
"""
        rc, out = run_tool(doc, "--grade", "8")
        self.assertEqual(rc, 1, out)

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

    def test_g11_solid_geometry_terms_enforced(self):
        # Cone mistranslated as 'කෝනය' (angle) must fail at Grade 11
        bad_cone = """\
questions:
  - n: 1
    stem: "A cone has base radius 7 cm and height 12 cm."
    stem_si: "කෝනයක ආධාරක අරය 7 cm සහ උස 12 cm වේ."
"""
        rc, out = run_tool(bad_cone, "--grade", "11")
        self.assertEqual(rc, 1)
        self.assertIn("English term 'cone' present but the Sinhala does not use the dictionary rendering", out)
        self.assertIn("කේතුව", out)

        # Cone correctly translated as 'කේතුව' passes
        good_cone = """\
questions:
  - n: 1
    stem: "A cone has base radius 7 cm and slant height 12 cm."
    stem_si: "කේතුවක ආධාරක අරය 7 cm සහ ඇල උස 12 cm වේ."
"""
        rc, out = run_tool(good_cone, "--grade", "11")
        self.assertEqual(rc, 0, out)

        # Slant height mistranslated as perpendicular height 'ලම්බ උස' fails
        bad_slant = """\
questions:
  - n: 1
    stem: "A solid cone has a slant height of 10 cm."
    stem_si: "ඝන කේතුවක ලම්බ උස 10 cm වේ."
"""
        rc, out = run_tool(bad_slant, "--grade", "11")
        self.assertEqual(rc, 1)
        self.assertIn("English term 'slant height' present but the Sinhala does not use the dictionary rendering 'ඇල උස'", out)

        # Banned 'ප්‍රතිලෝම ප්‍රමේයය' is caught
        bad_converse = """\
questions:
  - n: 1
    stem_si: "මධ්‍ය ලක්ෂ්‍ය ප්‍රමේයයේ ප්‍රතිලෝම ප්‍රමේයය ප්‍රකාශ කරන්න."
"""
        rc, out = run_tool(bad_converse, "--grade", "11")
        self.assertEqual(rc, 1)
        self.assertIn("ප්රතිලෝම ප්රමේයය", out.replace("\u200d", ""))

    def test_new_banned_mt_artifacts_flagged(self):
        banned_samples = [
            ("තිඹිරි ඉරි", "තිඹිරි ඉරි වලින් අඳින්න."),
            ("තීන්සිලි", "තීන්සිලි 12ක් භාවිතා කර ඇත."),
            ("පරෙක", "වහලයේ පරෙක දිග ගණනය කරන්න."),
            ("පාත්තුම්", "පාත්තුම් ගල් අල්ලා ඇත."),
            ("කැබලය", "කැබලය මගින් සම්බන්ධ කර ඇත."),
            ("කෝණ සමභාජක", "කෝණ සමභාජකය අඳින්න."),
            ("කෝණ සමභාජනය", "කෝණ සමභාජනය කරන්න."),
            ("බහුස්‍රය", "සවිධි බහුස්‍රයක කෝණ සොයන්න."),
            ("ලෙඛනය", "ලෝහ ලෙඛනයක් භාවිතා කරන්න."),
            ("සමභාජක", "රේඛා සමභාජකය අඳින්න."),
            ("සමභාජනය", "රේඛාව සමභාජනය කරන්න."),
        ]
        for term, sample in banned_samples:
            doc = f"""\
questions:
  - n: 1
    stem_si: "{sample}"
"""
            rc, out = run_tool(doc, "--grade", "9")
            self.assertEqual(rc, 1, f"Failed to flag banned term: {term}")
            self.assertIn(term.replace("\u200d", ""), out.replace("\u200d", ""))

    def test_g9_geometry_and_polygon_terms_enforced(self):
        # Good doc using standard curriculum terms passes at Grade 9
        good_g9 = """\
questions:
  - n: 1
    stem: "Calculate the arc length subtending a central angle of $60°$ in a circle of radius $7$ cm."
    stem_si: "අරය $7$ cm වූ වෘත්තයක $60°$ ක කේන්ද්‍රික කෝණයක් ආපාතනය කරන චාප දිග ගණනය කරන්න."
  - n: 2
    stem: "Each interior angle of a regular polygon is $120°$. Find the sum of interior angles."
    stem_si: "සවිධි බහු අස්‍රයක එක් අභ්‍යන්තර කෝණයක් $120°$ කි. අභ්‍යන්තර කෝණවල ඓක්‍යය සොයන්න."
  - n: 3
    stem: "The figure shows a rectangle where each corner is a right angle."
    stem_si: "රූපයේ දැක්වෙන්නේ එක් එක් මුල්ල ඍජු කෝණයක් වන ඍජුකෝණාස්‍රයකි."
"""
        rc, out = run_tool(good_g9, "--grade", "9")
        self.assertEqual(rc, 0, out)

        # Missing standard terms at Grade 9 are caught
        bad_central = """\
questions:
  - n: 1
    stem: "Find the central angle of the sector."
    stem_si: "කේන්ද්‍රික ඛණ්ඩයේ මැද කෝණය සොයන්න."
"""
        rc, out = run_tool(bad_central, "--grade", "9")
        self.assertEqual(rc, 1)
        self.assertIn("central angle", out)

        bad_polygon = """\
questions:
  - n: 1
    stem: "A regular polygon has 8 sides."
    stem_si: "සමාන පැති ඇති රූපයක පැති 8ක් ඇත."
"""
        rc, out = run_tool(bad_polygon, "--grade", "9")
        self.assertEqual(rc, 1)
        self.assertIn("regular polygon", out)

        bad_sum = """\
questions:
  - n: 1
    stem: "Find the sum of interior angles."
    stem_si: "ඇතුළත කෝණ එකතු කරන්න."
"""
        rc, out = run_tool(bad_sum, "--grade", "9")
        self.assertEqual(rc, 1)
        self.assertIn("sum of interior angles", out)


if __name__ == "__main__":
    unittest.main()
