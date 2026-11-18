"""G9 readiness — tools/vdd_g9_geometry.py (marked_lines / locus_scene /
polygon_angles for L08, L13, L15, L16 and L25).

All stems are SYNTHETIC English — no corpus text is reproduced.  The audits
run the real `audit-claim-set.py` over each emitted claim set; the refusal
tables exercise the mathematical guards (bool/string/non-finite numerics,
geometry the ink cannot honestly carry, and stem-mode givens the stem never
states).
"""
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g9_geometry as gg

STEM_LINE = "Angles on a straight line add to 180; the two parts are 110 and 70."
STEM_DIV = "AB is 8 cm; M is its midpoint and each half is 4 cm."
STEM_CIRCLE = "A locus of points 5 cm from O."
STEM_PERP = "The segment AB is 8 cm."
STEM_OFFSET = "Points stay 2 cm from the line AB."
STEM_POLY = "A regular polygon has 5 sides."


def els(b, t):
    return [e for e in b.doc["elements"] if e["type"] == t]


def audit(built):
    """Run the real claim-set audit on the emitted trio."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = built.write(tmp)
        result = subprocess.run(
            [sys.executable, str(TOOLS / "audit-claim-set.py"), str(paths["claims"])],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr


class MarkedLinesTests(unittest.TestCase):
    def test_point_on_line_computes_and_claims(self):
        b = gg.build_marked_lines(
            figure_id="g9ml1", stem=STEM_LINE, profile="point_on_line",
            rays={"A": 180, "B": 0, "C": -70},
            marks=[{"arms": ("A", "C"), "label": 110},
                   {"arms": ("C", "B"), "label": 70}])
        audit(b)
        self.assertIn("collinear A O B", b.claims)
        self.assertIn("angle A O C = 110", b.claims)
        self.assertIn("derive 110 + 70 = 180", b.claims)

        self.assertEqual(len(els(b, "angleMark")), 2)

    def test_rays_and_cross_profiles(self):
        b = gg.build_marked_lines(
            figure_id="g9ml2", stem="Two arcs mark angles at the point.",
            profile="rays", vertex="B",
            rays={"A": -120, "D": -60, "C": 0},
            marks=[{"arms": ("A", "D"), "arcs": 1},
                   {"arms": ("D", "C"), "arcs": 2}])
        audit(b)
        self.assertIn('describe "an arc marks angle ABD"', b.claims)
        b2 = gg.build_marked_lines(figure_id="g9ml3", stem="The lines cross.",
                                   profile="cross", vertex="T",
                                   lines={"AB": 30, "CD": -50})
        audit(b2)
        self.assertIn("nonparallel AB CD", b2.claims)
        self.assertIn("collinear A T B", b2.claims)

    def test_transversal_computed_crossings(self):
        b = gg.build_marked_lines(
            figure_id="g9ml4", stem="The two lines are parallel.",
            profile="transversal", lines={"AB": 0, "CD": 0},
            transversal={"PQ": 70}, crossings=("E", "F"))
        audit(b)
        self.assertIn("parallel AB CD", b.claims)
        self.assertIn("collinear P E F", b.claims)
        e_, f_ = b.anchors["E"], b.anchors["F"]

        dx, dy = f_[0] - e_[0], f_[1] - e_[1]
        self.assertAlmostEqual(math.degrees(math.atan2(dy, dx)) % 360, 70.0, places=2)

    def test_divided_ticks_validated_and_labels(self):
        b = gg.build_marked_lines(
            figure_id="g9ml5", stem=STEM_DIV, profile="divided",
            segment=("A", "B"), rays={"A": 0}, divisions={"M": 0.5},
            equal=[["AM", "MB"]], length=8, unit="cm",
            labels={"AM": "4 cm", "MB": "4 cm"})
        audit(b)
        self.assertIn("equal AM MB", b.claims)
        self.assertIn("on M AB", b.claims)
        self.assertIn('label "4 cm" names AM', b.claims)

    def test_marked_lines_refusals(self):
        spec = dict(figure_id="g9mlb", stem=STEM_LINE, profile="point_on_line",
                    rays={"A": 180, "B": 0, "C": -70},
                    marks=[{"arms": ("A", "C"), "label": 110}])
        for kw in ({"rays": {"A": 180, "C": -70}},
                   {"marks": [{"arms": ("A", "C"), "label": 105}]},
                   {"marks": [{"arms": ("A", "B"), "label": 50}]},
                   {"rays": {"A": 0, "B": 1}},
                   {"values": "maybe"}, {"vertex": "o"},
                   {"marks": [{"arms": ("A", "Z")}]},
                   {"marks": [{"arms": ("A", "C"), "arcs": 4}]}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gg.build_marked_lines(**{**spec, **kw})

        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(figure_id="g9mlb", stem="x", profile="rays",
                                  rays={"A": 0, "B": 180})

        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(figure_id="g9mlb", stem="x", profile="transversal",
                                  lines={"AB": 0, "CD": 10}, transversal={"PQ": 70})

        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(figure_id="g9mlb", stem="x", profile="divided",
                                  segment=("A", "B"), rays={"A": 0},
                                  divisions={"M": 0.4}, equal=[["AM", "MB"]])
        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(figure_id="g9mlb", stem=STEM_DIV, profile="divided",
                                  segment=("A", "B"), rays={"A": 0},
                                  divisions={"M": 0.5}, equal=[["AB", "MB"]])
        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(figure_id="g9mlb", stem=STEM_DIV, profile="divided",
                                  segment=("A", "B"), rays={"A": 0}, divisions={"M": 0.5},
                                  length=8, labels={"AM": "5 cm"})

    def test_numeric_guards(self):
        spec = dict(figure_id="g9mlb", stem="x", profile="rays",
                    rays={"A": 0, "D": 90})
        for bad in (True, "60", float("nan"), float("inf"), None):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                gg.build_marked_lines(**{**spec, "rays": {"A": bad, "D": 90}})
            with self.subTest(dl=bad), self.assertRaises(vt.TemplateError):
                gg.build_marked_lines(**{**spec, "draw_length": bad})
            with self.subTest(div=bad), self.assertRaises(vt.TemplateError):
                gg.build_marked_lines(figure_id="g9mlb", stem="x", profile="divided",
                                      segment=("A", "B"), rays={"A": 0},
                                      divisions={"M": bad})


class LocusSceneTests(unittest.TestCase):
    def test_circle_locus_equal_radii(self):
        b = gg.build_locus_scene(figure_id="g9lc1", stem=STEM_CIRCLE, kind="circle",
                                 radius=5, unit="cm",
                                 samples={"P": -30, "Q": 150})
        audit(b)
        self.assertIn("circle centre O through P Q", b.claims)
        self.assertIn("equal OP OQ", b.claims)
        d = math.dist(b.anchors["O"], b.anchors["P"])
        self.assertAlmostEqual(d, math.dist(b.anchors["O"], b.anchors["Q"]), places=6)

    def test_perp_bisector_midpoint_and_equidistance(self):
        b = gg.build_locus_scene(figure_id="g9lp2", stem=STEM_PERP,
                                 kind="perp_bisector", length=8, unit="cm",
                                 samples={"P": 0.6, "Q": -0.5})
        audit(b)
        self.assertIn("equal AM MB", b.claims)
        self.assertIn("right A M U", b.claims)
        self.assertIn("equal AP PB", b.claims)
        self.assertIn("on P UW", b.claims)
        m = b.anchors["M"]
        self.assertAlmostEqual(math.dist(m, b.anchors["A"]),
                               math.dist(m, b.anchors["B"]), places=6)

    def test_parallel_offset_feet_and_distances(self):
        b = gg.build_locus_scene(figure_id="g9lo3", stem=STEM_OFFSET,
                                 kind="parallel_offset", distance=2, unit="cm",
                                 samples={"P": (1, 0.5), "Q": (-1, 0.4)})
        audit(b)
        self.assertIn("parallel AB UV", b.claims)
        self.assertIn("parallel UV ST", b.claims)
        self.assertIn("parallel AB ST", b.claims)

        f1, f2 = b.anchors["F"], b.anchors["G"]
        for p, f in (("P", f1), ("Q", f2)):
            self.assertAlmostEqual(math.dist(b.anchors[p], f), 2 * 25.0, places=3)

    def test_angle_bisector_equal_feet(self):
        b = gg.build_locus_scene(figure_id="g9lb4", stem="The bisector locus.",
                                 kind="angle_bisector",
                                 arms={"A": -80, "B": -20},
                                 samples={"P": 0.5})
        audit(b)
        self.assertIn("inside P angle A V B", b.claims)
        self.assertIn("equal PF PG", b.claims)
        self.assertIn("derive 60 / 2 = 30", b.claims)

        b2 = gg.build_locus_scene(figure_id="g9lb5", stem="Each half is 30.",
                                  kind="angle_bisector",
                                  arms={"A": -80, "B": -20},
                                  samples={"P": 0.5})
        audit(b2)
        self.assertIn("angle A V W = 30", b2.claims)

    def test_locus_refusals(self):
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9lb", stem="x", kind="ellipse")
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9lb", stem="no number", kind="circle",
                                 radius=5, samples={"P": 0, "Q": 90})
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9lb", stem=STEM_CIRCLE, kind="circle",
                                 radius=5, samples={"P": 0})
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9lb", stem=STEM_PERP,
                                 kind="perp_bisector", samples={"P": 0.0})
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9lb", stem=STEM_OFFSET,
                                 kind="parallel_offset", distance=2,
                                 samples={"P": (0, 0.5)})
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9lb", stem="x", kind="angle_bisector",
                                 arms={"A": 0, "B": 8}, samples={"P": 0.5})
        for bad in (True, "5", float("nan"), float("inf"), -3):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                gg.build_locus_scene(figure_id="g9lb", stem=STEM_CIRCLE,
                                     kind="circle", radius=bad,
                                     samples={"P": 0, "Q": 90})

    def test_values_figure_mode(self):
        b = gg.build_locus_scene(figure_id="g9lf", stem="Read the figure.",
                                 kind="circle", radius=5, values="figure",
                                 samples={"P": -30, "Q": 150})
        audit(b)
        self.assertIn("figure content", b.claims)
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9lf", stem="Read the figure.",
                                 kind="circle", radius=5, values="stem",
                                 samples={"P": -30, "Q": 150})


class PolygonAnglesTests(unittest.TestCase):
    def test_interior_derives_and_measures(self):
        b = gg.build_polygon_angles(figure_id="g9pa1", stem=STEM_POLY, n=5,
                                  show="interior")
        audit(b)
        self.assertIn("derive 5 - 2 = 3", b.claims)
        self.assertIn("derive 3 * 180 = 540", b.claims)
        self.assertIn("derive 540 / 5 = 108", b.claims)
        self.assertIn("angle E A B = 108", b.claims)
        self.assertEqual(len(els(b, "tickMark")), 5)
        self.assertEqual(len(els(b, "angleMark")), 5)

    def test_triangulation_fan(self):
        b = gg.build_polygon_angles(figure_id="g9pa2", stem=STEM_POLY, n=5,
                                    show="triangulation")
        audit(b)
        fans = [e for e in els(b, "line") if e["id"].startswith("fan")]
        self.assertEqual(len(fans), 2)
        self.assertIn("derive 5 - 3 = 2", b.claims)
        self.assertIn("derive 3 * 180 = 540", b.claims)

    def test_centre_spokes(self):
        b = gg.build_polygon_angles(figure_id="g9pa3", stem=STEM_POLY, n=5,
                                    show="centre")
        audit(b)
        self.assertIn("circle centre O through A B C", b.claims)
        self.assertIn("derive 360 / 5 = 72", b.claims)

    def test_exterior_extensions(self):
        b = gg.build_polygon_angles(figure_id="g9pa4",
                                    stem="A regular 5-gon; exterior 72.", n=5,
                                    show="exterior",
                                    exterior_labels={"A": 72})
        audit(b)
        self.assertIn("derive 360 / 5 = 72", b.claims)
        self.assertIn("derive 5 * 72 = 360", b.claims)
        ext = [e for e in els(b, "line") if e["id"].startswith("e")]
        self.assertEqual(len(ext), 5)

    def test_polygon_refusals(self):
        spec = dict(figure_id="g9pb", stem=STEM_POLY, n=5, show="interior")
        for kw in ({"n": 2.5}, {"n": 2}, {"n": 9}, {"show": "mixed"},
                   {"names": "ABCDE"[:4]}, {"names": "ABCDA"},
                   {"labels": {"Z": "x"}},
                   {"labels": {"A": 100}},
                   {"fan": "Z"}, {"values": "maybe"},
                   {"exterior_labels": {"A": 72}},
                   {"n": True}, {"n": "5"}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gg.build_polygon_angles(**{**spec, **kw})
        with self.assertRaises(vt.TemplateError):
            gg.build_polygon_angles(figure_id="g9pb", stem="a polygon", n=5)
        with self.assertRaises(vt.TemplateError):
            gg.build_polygon_angles(figure_id="g9pb", stem="5 sides and 70.",
                                    n=5, show="exterior",
                                    exterior_labels={"A": 70})


class CriticRegressionTests(unittest.TestCase):
    """wt/g9-readiness/critic-geometry.md findings — global tick classes,
    strict numeric glyph parsing, reflex-wrap wedges, exact TemplateError on
    malformed input, drawn figure-mode measures, honest exterior claims."""

    @staticmethod
    def _tick_count(b, x, y):
        want = frozenset({tuple(round(c, 2) for c in b.anchors[x]),
                          tuple(round(c, 2) for c in b.anchors[y])})
        for e in els(b, "tickMark"):
            if frozenset(map(tuple, e["on"])) == want:
                return e["count"]
        return None

    def test_tick_classes_follow_length(self):

        b = gg.build_locus_scene(figure_id="g9cr1", stem=STEM_PERP,
                                 kind="perp_bisector", length=8,
                                 samples={"P": 0.6})
        am, mb = self._tick_count(b, "A", "M"), self._tick_count(b, "M", "B")
        ap, pb = self._tick_count(b, "A", "P"), self._tick_count(b, "P", "B")
        self.assertEqual(am, mb)
        self.assertEqual(ap, pb)
        self.assertNotEqual(am, ap)

        b2 = gg.build_locus_scene(figure_id="g9cr2", stem="Bisector.",
                                  kind="angle_bisector",
                                  arms={"A": 0, "B": 60},
                                  samples={"P": 0.4, "Q": 0.8})
        pf, pg = self._tick_count(b2, "P", "F"), self._tick_count(b2, "P", "G")
        qh, qk = self._tick_count(b2, "Q", "H"), self._tick_count(b2, "Q", "I")
        self.assertEqual(pf, pg)
        self.assertEqual(qh, qk)
        self.assertNotEqual(pf, qh)

    def test_polygon_numeric_label_gate(self):
        spec = dict(figure_id="g9cr3", stem=STEM_POLY, n=5, show="interior")
        for bad in (-108, float("nan"), float("inf"), 1e100, "-108", "1e100",
                    "+108", "10a", "108!!", True, None):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                gg.build_polygon_angles(**{**spec, "labels": {"A": bad}})
            with self.subTest(bad=bad, show="exterior"), \
                    self.assertRaises(vt.TemplateError):
                gg.build_polygon_angles(figure_id="g9cr3", stem="5 and 72.",
                                        n=5, show="exterior",
                                        exterior_labels={"A": bad})

        b = gg.build_polygon_angles(**{**spec, "stem": "5 sides; interior 108.",
                                      "labels": {"A": "108°"}})
        self.assertIn("108", " ".join(e.get("label", "") or e.get("value", "")
                                      for e in els(b, "angleMark") + els(b, "text")))

    def test_divided_label_gate(self):
        spec = dict(figure_id="g9cr4", stem=STEM_DIV, profile="divided",
                    segment="AB", rays={"A": 0}, divisions={"M": 0.5},
                    length=8, unit="cm")
        for bad in ("-99 cm", "+4 cm", "4.0.1 cm", "4 yd", "abc def", 4 + 0j,
                    ["4 cm"], float("nan")):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                gg.build_marked_lines(**{**spec, "labels": {"AM": bad}})
        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(**{**spec, "labels": ["4 cm"]})

    def test_reflex_wedge_refused(self):

        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(figure_id="g9cr5", stem="The marked angle.",
                                  profile="rays", rays={"A": 0, "B": 60, "C": 120},
                                  marks=[{"arms": ["C", "A"]}])

        b = gg.build_marked_lines(figure_id="g9cr5", stem="The marked angle.",
                                  profile="rays", rays={"A": 0, "B": 60, "C": 120},
                                  marks=[{"arms": ["B", "C"]}])
        self.assertIn("angleMark", [e["type"] for e in els(b, "angleMark")])

    def test_malformed_inputs_raise_template_error(self):
        with self.assertRaises(vt.TemplateError):
            gg.build_polygon_angles(figure_id="g9cr6", stem="5", n=10 ** 400)
        with self.assertRaises(vt.TemplateError):
            gg.build_marked_lines(figure_id="g9cr6", stem="x",
                                  profile="transversal",
                                  lines={"AB": 0, "CD": 0},
                                  transversal={"PQ": 70},
                                  marks=[{"at": [], "arms": ["A", "P"]}])
        with self.assertRaises(vt.TemplateError):
            gg.build_locus_scene(figure_id="g9cr6", stem="2",
                                 kind="parallel_offset", distance=2,
                                 samples={"P": (True, 0.5)})
        for bad in (True, "0.5", None):
            with self.subTest(t=bad), self.assertRaises(vt.TemplateError):
                gg.build_locus_scene(figure_id="g9cr6", stem="2",
                                     kind="parallel_offset", distance=2,
                                     samples={"P": (1, bad)})

    def test_figure_mode_draws_the_measure(self):

        b = gg.build_locus_scene(figure_id="g9cr7", stem="Read the figure.",
                                 kind="circle", radius=5, unit="cm",
                                 values="figure",
                                 samples={"P": -30, "Q": 150})
        texts = [e["value"] for e in els(b, "text")]
        self.assertTrue(any("5" in t for t in texts),
                        f"no drawn radius measure in {texts}")
        self.assertIn('label "5 cm" names OP', b.claims)
        b2 = gg.build_locus_scene(figure_id="g9cr7", stem="Read it.",
                                  kind="parallel_offset", distance=2, unit="cm",
                                  values="figure",
                                  samples={"P": (1, 0.5)})
        texts2 = [e["value"] for e in els(b2, "text")]
        self.assertTrue(any("2" in t for t in texts2),
                        f"no drawn distance measure in {texts2}")
        b3 = gg.build_locus_scene(figure_id="g9cr7", stem="Read it.",
                                  kind="perp_bisector", length=8, unit="cm",
                                  values="figure", samples={"P": 0.6})
        self.assertTrue(any("8" in e["value"] for e in els(b3, "text")))

    def test_exterior_glyph_names_exterior(self):
        b = gg.build_polygon_angles(figure_id="g9cr8",
                                    stem="5 sides; exterior 72.", n=5,
                                    show="exterior", exterior_labels={"A": 72})
        audit(b)
        self.assertNotIn('label "72°" names EAB', b.claims)
        self.assertIn('label "72°" names EA', b.claims)
        self.assertIn("exterior angle at A", b.claims)


if __name__ == "__main__":
    unittest.main()
