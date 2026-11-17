"""G9 readiness — pattern/fraction/outcome models (tools/vdd_g9_models.py).

Bounded builders for the inventory's B6/B7/B8 residuals: the L03 diamond
matchstick chain (4k + (k-1) sticks) and common-difference jump arcs, the
L04 equal-sector fraction discs (incl. the two-panel improper figure), and
the L24 resting polygon spinners + flat canonical die faces. All stems are
SYNTHETIC English — no source text leaves the corpus.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g9_models as gm

STEM_STICKS = "A matchstick pattern of diamonds is shown for stages 1 to 4. How many sticks does each stage need?"
STEM_SEQ = "The sequence 3, 7, 11, 15, 19 has a common difference of +4. Write the next term."
STEM_DISC = "A circle is divided into 5 equal sectors and 3 are shaded. Write the shaded fraction."
STEM_DISC2 = "Two equal circles are each divided into 8 equal sectors; 8 of the first and 3 of the second are shaded, showing 11/8."
STEM_SPIN = "A hexagonal spinner has 6 equal regions with printed outcomes 1, 2, 3, 4, 5, 6. List the sample space."
STEM_DIE = "A fair die has 6 faces. List the possible outcomes."


def els(b, t):
    return [e for e in b.doc["elements"] if e["type"] == t]


def audit(built):
    with tempfile.TemporaryDirectory() as tmp:
        paths = built.write(tmp)
        r = subprocess.run([sys.executable, str(TOOLS / "audit-claim-set.py"),
                            str(paths["claims"])], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


class MatchstickTests(unittest.TestCase):
    def spec(self, **kw):
        s = dict(figure_id="g9m1", stem=STEM_STICKS, stages=4)
        s.update(kw)
        return gm.build_matchstick_pattern(**s)

    def test_diamond_chain_counts(self):
        b = self.spec()

        counts = {k: 5 * k - 1 for k in (1, 2, 3, 4)}
        lines = els(b, "line")
        self.assertEqual(len(lines), sum(counts.values()))
        for k, m in counts.items():
            self.assertIn(f"stage {k} shows {m} sticks", b.claims)
            self.assertIn(f"derive 4 * {k} + ( {k} - 1 ) = {m}", b.claims)

        conn = [e for e in lines if e["id"].endswith("j")]
        self.assertEqual(len(conn), sum(k - 1 for k in counts))

    def test_stage_numerals_and_audit(self):
        b = self.spec()
        nums = sorted(e["value"] for e in els(b, "text"))
        self.assertEqual(nums, ["1", "2", "3", "4"])
        audit(b)

    def test_modes_and_refusals(self):
        audit(self.spec(stages=1))
        audit(self.spec(stem="Count the sticks on each of the 4 stages.",
                        values="figure"))
        self.assertIn("figure content", self.spec(
            stem="Count the sticks.", values="figure").claims)
        for kw in (dict(stages=0), dict(stages=5), dict(stages=2.5),
                   dict(stages=True), dict(stages="4"), dict(stages=float("nan")),
                   dict(kind="square_chain"), dict(values="maybe"),
                   dict(half_w=4), dict(stem="A pattern with no number.")):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                self.spec(**kw)


class SequenceJumpTests(unittest.TestCase):
    def spec(self, **kw):
        s = dict(figure_id="g9m2", stem=STEM_SEQ, first=3, difference=4, terms=5)
        s.update(kw)
        return gm.build_sequence_jumps(**s)

    def test_terms_arcs_labels(self):
        b = self.spec()
        self.assertEqual([e["value"] for e in els(b, "text")],
                         ["3", "7", "11", "15", "19", "+4", "+4", "+4", "+4"])

        self.assertEqual(len(els(b, "polyline")), 4)
        self.assertEqual(len(els(b, "arc")), 0)
        self.assertIn("derive 7 - 3 = 4", b.claims)
        self.assertIn("derive 19 - 15 = 4", b.claims)
        audit(b)

    def test_negative_difference(self):
        b = gm.build_sequence_jumps(
            figure_id="g9m2n", first=17, difference=-5, terms=4,
            stem="The sequence 17, 12, 7, 2 decreases by -5 each step.")
        self.assertIn("derive 12 - 17 = -5", b.claims)
        self.assertIn('label "-5" names jump1', b.claims)
        audit(b)

    def test_figure_mode_and_refusals(self):
        b = self.spec(stem="Write the next term of the pattern.", values="figure")
        self.assertIn("figure content", b.claims)
        audit(b)
        for kw in (dict(difference=0), dict(terms=1), dict(terms=8),
                   dict(first=1.5), dict(difference=2.5), dict(first=True),
                   dict(difference="4"), dict(terms=float("inf")),
                   dict(stem="The sequence 3, 7, 11, 15, 20 adds 4."),
                   dict(stem="The sequence 3, 7, 11, 15, 19 adds 5."),
                   dict(values="other")):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                self.spec(**kw)

        with self.assertRaises(vt.TemplateError):
            self.spec(stem="A pattern starts at 3 and adds 4 each step.")


class FractionDiscTests(unittest.TestCase):
    def spec(self, **kw):
        s = dict(figure_id="g9m3", stem=STEM_DISC, panels=[(5, 3)])
        s.update(kw)
        return gm.build_fraction_disc(**s)

    def test_equal_sectors_and_shading(self):
        b = self.spec()
        self.assertEqual(len(els(b, "circle")), 1)
        cuts = [e for e in els(b, "line")]
        self.assertEqual(len(cuts), 5)
        shade = [e for e in els(b, "polygon") if e["id"].startswith("sh")]
        self.assertEqual(len(shade), 3)
        self.assertIn("shaded 3 of 5 sectors on panel1", b.claims)
        self.assertIn("derive 5 - 3 = 2", b.claims)
        audit(b)

    def test_two_panel_improper(self):
        b = self.spec(stem=STEM_DISC2, panels=[(8, 8), (8, 3)])
        self.assertEqual(len(els(b, "circle")), 2)
        self.assertEqual(len([e for e in els(b, "polygon") if e["id"].startswith("sh")]), 11)
        self.assertIn("derive 8 + 3 = 11", b.claims)
        audit(b)

    def test_modes_and_refusals(self):
        audit(self.spec(stem="What fraction is shaded?", panels=[(6, 2)],
                        values="figure"))
        for kw in (dict(panels=[]), dict(panels=[(5, 3)] * 4),
                   dict(panels=[(1, 0)]), dict(panels=[(13, 3)]),
                   dict(panels=[(5, 6)]), dict(panels=[(5, -1)]),
                   dict(panels=[(5, 2.5)]), dict(panels=[(True, 1)]),
                   dict(panels=[("5", 3)]), dict(panels=[(5, 3), 9]),
                   dict(radius=10), dict(radius=float("nan")),
                   dict(values="nope"),
                   dict(stem="A circle has 6 equal sectors and 3 are shaded."),
                   dict(panels=[(5, 3), (8, 3)], stem=STEM_DISC)):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                self.spec(**kw)


class SpinnerTests(unittest.TestCase):
    def spec(self, **kw):
        s = dict(figure_id="g9m4", stem=STEM_SPIN, n=6,
                 outcomes=[4, 5, 6, 1, 2, 3])
        s.update(kw)
        return gm.build_polygon_spinner(**s)

    def test_sectors_spokes_pointer(self):
        b = self.spec()
        self.assertEqual(len(els(b, "polygon")), 1)
        self.assertEqual(len(els(b, "polygon")[0]["points"]), 6)
        self.assertEqual(len(els(b, "line")), 6)
        self.assertEqual(len(els(b, "arrow")), 1)
        self.assertEqual(len(els(b, "text")), 6)
        self.assertIn("derive 360 / 6 = 60", b.claims)
        audit(b)

    def test_symbolic_outcomes_and_sizes(self):
        for n in (5, 8):
            with self.subTest(n=n):
                b = gm.build_polygon_spinner(
                    figure_id=f"g9m4s{n}", n=n,
                    outcomes=list("ABCDEFGH")[:n],
                    stem=f"A {n}-sided spinner has {n} equal sectors.",
                    values="figure")
                self.assertIn(f"derive 360 / {n} = {360 // n}", b.claims)
                audit(b)

        b = self.spec(outcomes=[2, 1, 3, 2, 4, 5],
                      stem="A 6-sector spinner shows 1, 2, 3, 4, 5 and 2.")
        self.assertEqual(b.claims.count('label "2" names'), 1)
        audit(b)

    def test_refusals(self):
        for kw in (dict(n=4), dict(n=9), dict(n=6.0 if False else 5.5),
                   dict(n="6"), dict(n=True), dict(n=float("inf")),
                   dict(outcomes=[1, 2, 3]),
                   dict(outcomes=[1, 2, 3, 4, 5, "six sides"]),
                   dict(outcomes=[1, 2, 3, 4, 5, None]),
                   dict(radius=200), dict(values="bad"),
                   dict(stem="A spinner has 5 sectors."),
                   dict(stem="A 6-sector spinner shows 1 to 6.")):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                self.spec(**kw)


class DieFaceTests(unittest.TestCase):
    def spec(self, **kw):
        s = dict(figure_id="g9m5", stem=STEM_DIE, faces=[1, 2, 3, 4, 5, 6])
        s.update(kw)
        return gm.build_die_faces(**s)

    def test_flat_canonical_pips(self):
        b = self.spec()
        self.assertEqual(len(els(b, "rect")), 6)
        self.assertEqual(len(els(b, "circle")), 21)
        self.assertIn("derive 1 + 2 + 3 + 4 + 5 + 6 = 21", b.claims)
        self.assertIn("figure content", b.claims)
        audit(b)

    def test_layout_rows_and_subset(self):
        b = self.spec(faces=[2, 5, 6], stem="A die shows 3 faces.")
        self.assertEqual(len(els(b, "rect")), 3)
        self.assertEqual(len(els(b, "circle")), 13)
        audit(b)

        b2 = self.spec(stem="The die has 6 faces.", values="stem")
        audit(b2)
        with self.assertRaises(vt.TemplateError):
            self.spec(stem="A die.", values="stem")

    def test_refusals(self):
        for kw in (dict(faces=[]), dict(faces=[1] * 7), dict(faces=[0]),
                   dict(faces=[7]), dict(faces=[2.5]), dict(faces=[True]),
                   dict(faces=["3"]), dict(faces=[float("nan")]),
                   dict(side=5), dict(values="x")):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                self.spec(**kw)


class NoAnswerLeakTests(unittest.TestCase):
    def test_descriptions_hold_no_answers(self):
        b = gm.build_fraction_disc(figure_id="g9m6",
                                   stem="What fraction of the circle is shaded?",
                                   panels=[(5, 3)], values="figure")
        desc = b.doc["a11y"]["description"]
        self.assertNotIn("3/5", desc)
        audit(b)


class StrictContractTests(unittest.TestCase):
    def test_sequence_signs_in_both_directions(self):
        for first, difference, stem in (
            (3, 4, "The sequence -3, -7, -11 changes by -4."),
            (-3, -4, "The sequence 3, 7, 11 changes by +4."),
            (3, 4, "The sequence 3, 7, 11 changes by -4."),
        ):
            with self.subTest(stem=stem), self.assertRaises(vt.TemplateError):
                gm.build_sequence_jumps(figure_id="probe1", first=first,
                                        difference=difference, terms=3, stem=stem)
        audit(gm.build_sequence_jumps(figure_id="probe1", first=3, difference=4,
              terms=3, stem="The sequence +3, +7, +11 changes by +4."))

    def test_spinner_signed_numbers(self):
        for glyph, stem in (("-1", "A spinner with 5 sectors."),
                            ("-1", "A spinner with 5 sectors showing +1."),
                            ("+1", "A spinner with 5 sectors showing -1.")):
            with self.subTest(glyph=glyph, stem=stem), self.assertRaises(vt.TemplateError):
                gm.build_polygon_spinner(figure_id="probe1", stem=stem, n=5,
                                         outcomes=[glyph] * 5, radius=130)
        for glyph in ("-1", "+1"):
            b = gm.build_polygon_spinner(figure_id="probe1", n=5,
                stem=f"A spinner with 5 sectors showing {glyph}.",
                outcomes=[glyph] * 5, radius=130)
            audit(b)

    def test_entry_errors_are_template_errors(self):
        for name in ("matchstick_pattern", "sequence_jumps", "fraction_disc",
                     "polygon_spinner", "die_faces"):
            builder = getattr(gm, "build_" + name)
            for kw in ({}, {"figure_id": "p1", "stem": "x", "bogus": 1}):
                with self.subTest(name=name, kw=kw), self.assertRaises(vt.TemplateError):
                    builder(**kw)
            with self.assertRaises(vt.TemplateError):
                builder("positional")

    def test_malformed_options(self):
        for kwargs in ({"arrows": "false"}, {"show_value": "false"},
                       {"values": False}, {"medium": True}, {"title": False},
                       {"description": []}, {"ask": "a"}, {"ask": [["a"]]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(vt.TemplateError):
                gm.build_matchstick_pattern(figure_id="probe1", stem="Stage 1.",
                                             stages=1, **kwargs)

    def test_huge_numbers_and_panel_schema(self):
        bad = 10**1000
        calls = (
            (gm.build_matchstick_pattern, dict(stages=bad)),
            (gm.build_matchstick_pattern, dict(stages=1, half_w=bad)),
            (gm.build_sequence_jumps, dict(first=bad, difference=1, terms=3)),
            (gm.build_fraction_disc, dict(panels=[(bad, 1)])),
            (gm.build_polygon_spinner, dict(n=bad, outcomes=[])),
            (gm.build_polygon_spinner, dict(n=5, outcomes=[bad] * 5)),
            (gm.build_die_faces, dict(faces=[bad])),
        )
        for builder, kwargs in calls:
            with self.subTest(builder=builder.__name__), self.assertRaises(vt.TemplateError):
                builder(figure_id="probe1", stem="Read the figure.", **kwargs)
        for panel in ({"sectors": 5, "shaded": 3, "extra": 99},
                      {"sectors": 5}, {"sectors": 5, "shaded": "false"}):
            with self.subTest(panel=panel), self.assertRaises(vt.TemplateError):
                gm.build_fraction_disc(figure_id="probe1", stem="Read figure.",
                                       panels=[panel], values="figure")


if __name__ == "__main__":
    unittest.main()
