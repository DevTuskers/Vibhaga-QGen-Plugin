import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

import yaml

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
    def test_grade_nine_like_terms_use_textbook_words(self):
        template = """questions:
  - n: 1
    stem: "Collect like terms."
    stem_si: "{} පද එකතු කරන්න."
"""
        rc, out = run_tool(template.format("සමජාතීය"), "--grade", "9")
        self.assertEqual(rc, 1)
        self.assertIn("banned term", out)
        self.assertEqual(run_tool(template.format("සජාතීය"), "--grade", "9")[0], 0)

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
        # "angle of elevation" has no G8 entry; neither the compound nor
        # the "angle" inside it is checked — the lexeme, not grade-activity,
        # decides suppression (un-taught terms are scope-card territory)
        doc = """\
questions:
  - n: 1
    stem: "Mark the angle of elevation at B."
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
            ("නිව් උතුරට", "නැව නිව් උතුරට යාත්‍රා කරයි."),
            ("නිව් නැගෙනහිරින්", "A පිහිටියේ B ට නිව් නැගෙනහිරින් ය."),
            ("දෙකොළය", "නිරීක්ෂකයා දෙකොළය මත සිටී."),
            ("භූමිකාරයා", "භූමිකාරයා තණකොළ කපයි."),
            ("කෑලිය", "ඉඩමෙන් එක් කෑලියක් විකුණන ලදී."),
            ("භූමි කෑලි", "භූමි කෑලි කිහිපයකට වෙන් කර ඇත."),
            ("ජ්‍යා රේඛාව", "වෘත්තයේ ජ්‍යා රේඛාව අඳින්න."),
            ("සලකුණක් පවසයි", "සලකුණක් පවසයි කෝණය 60 බව."),
            ("සලකුණක් ප්‍රකාශ කරයි", "සලකුණක් ප්‍රකාශ කරයි මෙම දිග 5 cm බව."),
            ("ප්‍රතිලෝම කරන්න", "භාගය ප්‍රතිලෝම කරන්න."),
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

    def test_g11_circle_and_bearing_terms_enforced(self):
        good_g11 = """\
questions:
  - n: 1
    stem: "A chord subtends an angle of $60°$ at the centre."
    stem_si: "ජ්‍යායක් මඟින් කේන්ද්‍රයේ $60°$ ක කෝණයක් ආපාතනය කරයි."
  - n: 2
    stem: "State the alternate segment theorem."
    stem_si: "ඒකාන්තර වෘත්ත ඛණ්ඩයේ කෝණ ආශ්‍රිත ප්‍රමේයය ප්‍රකාශ කරන්න."
  - n: 3
    stem: "The bearing of B from A is $220°$."
    stem_si: "A සිට B හි දිගංශය $220°$ කි."
  - n: 4
    stem: "State the midpoint theorem."
    stem_si: "මධ්‍ය ලක්ෂ්‍ය ප්‍රමේයය ප්‍රකාශ කරන්න."
"""
        rc, out = run_tool(good_g11, "--grade", "11")
        self.assertEqual(rc, 0, out)

        # Chord mistranslated as chord line fails
        bad_chord = """\
questions:
  - n: 1
    stem: "Draw a chord in the circle."
    stem_si: "වෘත්තයේ ජ්‍යා රේඛාව අඳින්න."
"""
        rc, out = run_tool(bad_chord, "--grade", "11")
        self.assertEqual(rc, 1)
        self.assertIn("ජ්‍යා රේඛාව".replace("\u200d", ""), out.replace("\u200d", ""))

        # Bearing at G11 using banned දිශාංකය fails
        bad_bearing = """\
questions:
  - n: 1
    stem: "The bearing of P is $045°$."
    stem_si: "P හි දිශාංකය $045°$ වේ."
"""
        rc, out = run_tool(bad_bearing, "--grade", "11")
        self.assertEqual(rc, 1)
        self.assertIn("දිශාංකය", out)

        # Subtends mistranslated without standard math terms fails
        bad_subtends = """\
questions:
  - n: 1
    stem: "The arc subtends an angle of $40°$."
    stem_si: "චාපය මඟින් $40°$ ක කෝණයක් සාදයි."
"""
        rc, out = run_tool(bad_subtends, "--grade", "11")
        self.assertEqual(rc, 1)
        self.assertIn("subtends", out)

    def test_g10_chords_scale_and_banned_mt_terms_enforced(self):
        good_g10 = """\
questions:
  - n: 1
    stem: "The perpendicular from the centre bisects the chord."
    stem_si: "කේන්ද්‍රයේ සිට ජ්‍යාවට අඳින ලද ලම්බයෙන් ජ්‍යාව සමච්ඡේදනය වේ."
  - n: 2
    stem: "Chords equidistant from the centre are equal in length."
    stem_si: "කේන්ද්‍රයේ සිට සමදුරින් පිහිටි ජ්‍යා දිගින් සමාන වේ."
  - n: 3
    stem: "A rope of length $16$ cm is tied across."
    stem_si: "$16$ cm දිගැති කඹයක් හරහා බැඳ ඇත."
  - n: 4
    stem: "Construct a scale drawing of the field."
    stem_si: "ක්ෂේත්‍රයේ පරිමාණ රූපයක් නිර්මාණය කරන්න."
  - n: 5
    stem: "The angle in a semicircle is a right angle."
    stem_si: "අර්ධ වෘත්තයේ කෝණය සෘජුකෝණයකි."
  - n: 6
    stem: "The chord subtends a central angle."
    stem_si: "ජ්‍යාය කේන්ද්‍රික කෝණයක් ආපාතනය කරන බව දැක්වේ."
"""
        rc, out = run_tool(good_g10, "--grade", "10")
        self.assertEqual(rc, 0, out)

        # Banned සමහාරක fails
        bad_samaharaka = """\
questions:
  - n: 1
    stem: "The line bisects the chord."
    stem_si: "රේඛාවෙන් ජ්‍යාව සමහාරක කරයි."
"""
        rc, out = run_tool(bad_samaharaka, "--grade", "10")
        self.assertEqual(rc, 1)
        self.assertIn("සමහාරක", out)

        # Banned රජි fails
        bad_raji = """\
questions:
  - n: 1
    stem: "A rope is attached to the pole."
    stem_si: "කණුවට රජියක් සවි කර ඇත."
"""
        rc, out = run_tool(bad_raji, "--grade", "10")
        self.assertEqual(rc, 1)
        self.assertIn("රජි", out)

        # Banned ungrammatical participles ඇඳන / ඇඳූ fail
        bad_drawn1 = """\
questions:
  - n: 1
    stem_si: "කේන්ද්‍රයෙන් ඇඳන ලම්බකය."
"""
        rc, out = run_tool(bad_drawn1, "--grade", "10")
        self.assertEqual(rc, 1)
        self.assertIn("ඇඳන", out)

        bad_drawn2 = """\
questions:
  - n: 1
    stem_si: "කේන්ද්‍රයෙන් ඇඳූ ලම්බකය."
"""
        rc, out = run_tool(bad_drawn2, "--grade", "10")
        self.assertEqual(rc, 1)
        self.assertIn("ඇඳූ", out)

        # Banned පරිමාණ සටහන fails
        bad_scale = """\
questions:
  - n: 1
    stem: "Draw a scale drawing."
    stem_si: "පරිමාණ සටහනක් අඳින්න."
"""
        rc, out = run_tool(bad_scale, "--grade", "10")
        self.assertEqual(rc, 1)
        self.assertIn("පරිමාණ සටහන", out)

        # Banned මනියි fails
        bad_maniyi = """\
questions:
  - n: 1
    stem_si: "AB පාදය 5 cm මනියි."
"""
        rc, out = run_tool(bad_maniyi, "--grade", "10")
        self.assertEqual(rc, 1)
        self.assertIn("මනියි", out)

    def test_g8_non_frontier_translation_and_banned_mt_terms_enforced(self):
        # Banned translation calques from non-frontier models must be caught
        banned_non_frontier = [
            ("කුරුසු ලක්ෂ්‍යය", "කවකටු චාප වල කුරුසු ලක්ෂ්‍යය P ලෙස නම් කරන්න."),
            ("කුරුසු වේ", "චාප දෙක A හිදී කුරුසු වේ."),
            ("රුස්සාවි රෝදය", "ළමුන් රුස්සාවි රෝදයක නැඟී ගමන් කරයි."),
            ("බඳිනු නැත", "පළමු සහ දෙවන පියවර එකිනෙකාට බඳිනු නැත."),
            ("සම්පාත", "ත්‍රිකෝණ දෙක සම්පාත බව පෙන්වන්න."),
        ]
        for term, sample in banned_non_frontier:
            doc = f"""\
questions:
  - n: 1
    stem_si: "{sample}"
"""
            rc, out = run_tool(doc, "--grade", "8")
            self.assertEqual(rc, 1, f"Failed to flag banned term: {term}")
            self.assertIn(term.replace("\u200d", ""), out.replace("\u200d", ""))

        # Grade 8 curriculum math terms enforced:
        # Good doc passes with all standard Grade 8 terms and inflections
        good_g8 = """\
questions:
  - n: 1
    stem: "Construct a triangle with side lengths $5$ cm and $6$ cm. The two triangles are congruent."
    stem_si: "පාදවල දිග $5$ cm සහ $6$ cm වන ත්‍රිකෝණයක් නිර්මාණය කරන්න. ත්‍රිකෝණ දෙක අංගසම වේ."
  - n: 2
    stem: "Find the central angle of a sector in a wheel having 12 spokes."
    stem_si: "ගරාදි 12ක් සහිත රෝදයක කේන්ද්‍රික ඛණ්ඩයක කේන්ද්‍රික කෝණය සොයන්න."
  - n: 3
    stem: "Mark the crossing point of the two arcs as point P."
    stem_si: "චාප දෙකෙහි ඡේදන ලක්ෂ්‍යය P ලක්ෂ්‍යය ලෙස ලකුණු කරන්න."
  - n: 4
    stem: "Calculate the straight-line distance between the two points."
    stem_si: "ලක්ෂ්‍ය දෙක අතර සරල රේඛීය දුර ගණනය කරන්න."
"""
        rc, out = run_tool(good_g8, "--grade", "8")
        self.assertEqual(rc, 0, out)

        # Missing 'congruent' dictionary rendering (අංගසම) is caught
        bad_congruent = """\
questions:
  - n: 1
    stem: "The two triangles are congruent."
    stem_si: "ත්‍රිකෝණ දෙක එක හා සමාන වේ."
"""
        good_congruent = bad_congruent.replace("එක හා සමාන වේ", "අංගසම වේ")
        rc, out = run_tool(good_congruent, "--grade", "10")
        self.assertEqual(rc, 0, out)
        rc, out = run_tool(bad_congruent, "--grade", "10")
        self.assertEqual(rc, 1)
        self.assertIn("congruent", out)

        # The wheel caption supplies the Grade 7 plural ගරාදි.
        good_spoke = """\
questions:
  - n: 1
    stem: "The wheel has 8 spokes."
    stem_si: "රෝදයේ ගරාදි 8ක් ඇත."
"""
        rc, out = run_tool(good_spoke, "--grade", "7")
        self.assertEqual(rc, 0, out)

        # Missing 'spoke' dictionary rendering (ගරාදි) is caught
        bad_spoke = """\
questions:
  - n: 1
    stem: "The wheel has 8 spokes."
    stem_si: "රෝදයේ කූරු 8ක් ඇත."
"""
        rc, out = run_tool(bad_spoke, "--grade", "7")
        self.assertEqual(rc, 1)
        self.assertIn("spoke", out)

        # Missing 'crossing point' dictionary rendering (ඡේදන ලක්ෂ්‍යය) is caught
        bad_crossing = """\
questions:
  - n: 1
    stem: "Label the crossing point."
    stem_si: "හමුවන තැන ලකුණු කරන්න."
"""
        rc, out = run_tool(bad_crossing, "--grade", "8")
        self.assertEqual(rc, 1)
        self.assertIn("crossing point", out)

    def test_attested_right_angle_spacing_variants(self):
        for grade in (9, 10, 11):
            for si in ("ඍජුකෝණය", "ඍජු කෝණය"):
                with self.subTest(grade=grade, si=si):
                    doc = f'questions:\n  - n: 1\n    stem: "A right angle."\n    stem_si: "{si}"\n'
                    rc, out = run_tool(doc, "--grade", str(grade))
                    self.assertEqual(rc, 0, out)

    def test_resolved_review_terms_enforced(self):
        cases = [
            ("heptagon", 7, "සප්තාස්‍රය"),
            ("octagon", 7, "අෂ්ටාස්‍රය"),
            ("decagon", 7, "දසාස්‍රය"),
            ("compasses", 7, "කවකටුව"),
            ("compasses", 8, "කවකටුව"),
            ("pair of compasses", 7, "කවකටුව"),
            ("pair of compasses", 8, "කවකටුව"),
            ("set square", 7, "විහිත චතුරස්‍රය"),
            ("standard form", 9, "විද්‍යාත්මක අංකනය"),
            ("y-intercept", 9, "අන්තඃඛණ්ඩය"),
            ("y-intercept", 10, "අන්තඃඛණ්ඩය"),
            ("tree diagram", 10, "රුක් සටහන"),
            ("tree diagram", 10, "රුක්සටහන්"),
            ("outcome table", 10, "කොටු දැල"),
            ("quadrant (of a pie chart)", 10, "හතරෙන් පංගුවේ කේන්ද්‍රික ඛණ්ඩය"),
        ]
        for term, grade, si in cases:
            with self.subTest(term=term, grade=grade, si=si):
                doc = f'questions:\n  - n: 1\n    stem: "{term}"\n    stem_si: "{si}"\n'
                rc, out = run_tool(doc, "--grade", str(grade))
                self.assertEqual(rc, 0, out)
                rc, out = run_tool(doc.replace(si, "කෝණය"), "--grade", str(grade))
                self.assertEqual(rc, 1, out)
                self.assertIn(term, out)

    def test_lookup_aliases_copy_cited_target_grades(self):
        terms = yaml.safe_load(mod.DICT_PATH.read_text(encoding="utf-8"))["terms"]
        required = {
            "rectangular prism": "cuboid", "rectangular box": "cuboid",
            "center": "centre", "radii": "radius", "vertices": "vertex",
            "triangles": "triangle", "angles": "angle", "circles": "circle",
            "chords": "chord", "sectors": "sector", "fractions": "fraction",
            "edges": "edge", "solid faces": "face",
            "x axis": "x-axis", "average": "mean", "slope": "gradient",
            "percent": "percentage", "compound interest": "compound interest (වැල්)",
            "pie graph": "pie chart", "trapezoid": "trapezium",
            "LCM": "least common multiple", "HCF": "highest common factor",
            "GCD": "highest common factor", "angle bisectors": "angle bisector",
            "perpendicular bisectors": "perpendicular bisector",
        }
        # ambiguous bare words ("prime factorisation", "sets aside") stay unaliased
        for ambiguous in ("prime", "sets"):
            self.assertNotIn(ambiguous, terms)
        for alias, target in required.items():
            with self.subTest(alias=alias):
                self.assertEqual(terms[alias]["note"], "alias of " + target)
        for alias, entry in terms.items():
            note = entry.get("note", "")
            if not note.startswith("alias of "):
                continue
            target = terms[note[len("alias of "):]]["grades"]
            if alias in {"three-figure bearing", "three-figure bearings",
                         "three figure bearing", "three figure bearings"}:
                target = {g: e for g, e in target.items() if g in (10, 11)}
            with self.subTest(alias=alias):
                self.assertEqual(entry["grades"], target)
                self.assertTrue(all(e["sources"] for e in entry["grades"].values()))
        self.assertEqual(set(terms["three-figure bearing"]["grades"]), {10, 11})
        for ambiguous in ("bisector", "bisectors", "bases", "faces", "modes", "means", "axes", "scales"):
            self.assertNotIn(ambiguous, terms)

    def test_coverage_and_aliases_enforce_correct_renderings(self):
        cases = {
            6: [("elapsed time", "ගත වූ කාලය"), ("divisibility", "භාජ්‍යතාව"),
                ("triangles", "ත්‍රිකෝණය"), ("angles", "කෝණ")],
            7: [("rectangular boxes", "ඝනකාභය"), ("vertices", "ශීර්ෂය"),
                ("LCM", "කුඩා ම පොදු ගුණාකාරය"), ("GCD", "මහා පොදු සාධකය"),
                ("Euler relation", "ඔයිලර් සම්බන්ධතාව"), ("drawing scales", "පරිමාණය")],
            8: [("circles", "වෘත්තය"), ("x axis", "x අක්ෂය"),
                ("average", "මධ්‍යන්‍යය"), ("statistical modes", "මාතය")],
            9: [("radii", "අරය"), ("slope", "අනුක්‍රමණය"),
                ("angle bisectors", "කෝණ සමච්ඡේදකය"),
                ("simultaneous equations", "සමගාමී සමීකරණ")],
            10: [("arithmetic progression", "සමාන්තර ශ්‍රේඪි"),
                 ("three-figure bearings", "දිගංශය"), ("pie graph", "වට ප්‍රස්තාරය")],
            11: [("dependent event", "පරායත්ත සිද්ධි"), ("quartile", "චතුර්ථක"),
                 ("compound interest", "වැල් පොලී"), ("plane figures", "තල රූපය")],
        }
        for grade, rows in cases.items():
            questions = [{"n": i, "stem": en, "stem_si": si}
                         for i, (en, si) in enumerate(rows, 1)]
            with self.subTest(grade=grade, rendering="correct"):
                rc, out = run_tool(yaml.safe_dump({"grade": grade, "questions": questions}, allow_unicode=True))
                self.assertEqual(rc, 0, out)
            for rendering in ("", "වෘත්තය" if grade == 6 else "කෝණය"):
                wrong = [dict(q, stem_si=rendering) for q in questions]
                with self.subTest(grade=grade, rendering=rendering):
                    rc, out = run_tool(yaml.safe_dump({"grade": grade, "questions": wrong}, allow_unicode=True))
                    self.assertEqual(rc, 1, out)
                    for en, _ in rows:
                        self.assertIn(en, out)

    def test_new_alias_compounds_suppress_only_contained_hits(self):
        cases = [
            (7, "rectangular prisms", "ඝනකාභය", 0, None),
            (7, "rectangular prisms and prisms", "ඝනකාභය", 1, "'prisms'"),
            (7, "rectangular prisms", "ප්‍රිස්මය", 1, "'rectangular prisms'"),
            (7, "rectangular prisms and prisms", "ඝනකාභය ප්‍රිස්මය", 0, None),
            (10, "average speed", "මධ්‍යක වේගය", 0, None),
            (10, "average speed and average", "මධ්‍යක වේගය", 1, "'average'"),
        ]
        for grade, en, si, expected, finding in cases:
            with self.subTest(grade=grade, en=en, si=si):
                doc = yaml.safe_dump({"grade": grade, "questions": [{"n": 1, "stem": en, "stem_si": si}]}, allow_unicode=True)
                rc, out = run_tool(doc)
                self.assertEqual(rc, expected, out)
                if finding:
                    self.assertIn(finding, out)

    def test_empty_set_and_context_adjudications(self):
        terms = yaml.safe_load(mod.DICT_PATH.read_text(encoding="utf-8"))["terms"]
        self.assertNotIn("non-empty set", terms)
        self.assertEqual(terms["null set"]["grades"], terms["empty set"]["grades"])
        self.assertEqual(terms["company shares"]["grades"], terms["company share"]["grades"])
        self.assertIsNone(mod.en_pattern("empty set").search("non-empty set"))
        self.assertIsNone(mod.en_pattern("empty set").search("NON-EMPTY SET"))
        self.assertIsNotNone(mod.en_pattern("non-terminating decimal").search("non-terminating decimal"))
        cases = [
            (8, "empty set", "අභිශූන්‍ය කුලකය", 0),
            (8, "null set", "අභිශූන්‍ය කුලකය", 0),
            (8, "empty set", "කුලකය", 1),
            (8, "null set", "කුලකය", 1),
            (8, "non-empty set", "කුලකය", 0),
            (11, "company share", "සමාගමේ කොටස්", 0),
            (11, "company shares", "සමාගමේ කොටස්", 0),
            (11, "company share", "කොටස්", 1),
            (11, "bar notation (logarithms)", "වියුති", 0),
            (7, "digital root", "ඉලක්කම් දර්ශකය", 0),
            (6, "number period", "සංඛ්‍යා කලාපයක්", 0),
            (10, "height", "උස", 0),
        ]
        for grade, en, si, expected in cases:
            with self.subTest(grade=grade, en=en, si=si):
                doc = yaml.safe_dump({"grade": grade, "questions": [{"n": 1, "stem": en, "stem_si": si}]}, allow_unicode=True)
                rc, out = run_tool(doc)
                self.assertEqual(rc, expected, out)



if __name__ == "__main__":
    unittest.main()
