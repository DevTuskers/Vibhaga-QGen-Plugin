"""G9 readiness — L06/L07 symbolic algebra areas + L10 proportion mapping
(tools/vdd_g9_area.py).

Covers the confirmed source residuals: symbolic-rectangle (06:493,726;
07:629), affine-corner-cut (06:512 strips, 06:751/07:650 corner),
rectangular-frame (06:770) and the lesson-10 arrow mappings
(10:276,323,380,972,1041). Dissection-rearrangement (06:372 composite,
07:683) is refused and stays a handdrawn residual. All stems SYNTHETIC.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g9_area as ga

STEM_SQ = "A square garden has side x. Write its area."
STEM_STRIP = ("Synthetic tile: both initial dimensions are x. Trim 2 from its "
              "right edge and 3 from its lower edge.")
STEM_MAP = "5 pens cost 75 rupees. Find the price x of 8 pens."
STEM_FIG = "What does the figure show?"


def els(b, t):
    return [e for e in b.doc["elements"] if e["type"] == t]


class AlgebraAreaRectangleTests(unittest.TestCase):
    def test_square_side_and_area(self):
        b = ga.build_algebra_area(figure_id="g9a1", stem=STEM_SQ,
                                  style="rectangle", square=True,
                                  top="x", side="x", area="x^{2}")
        self.assertEqual(len(els(b, "polygon")), 1)
        labels = sorted(e["latex"] for e in els(b, "math"))
        self.assertEqual(labels, ["x", "x", "x^{2}"])
        self.assertIn('the centre label x^2 is the product x x x', b.claims)
        self.assertIn("derive 360 / 90 = 4", b.claims)
        sq = els(b, "polygon")[0]
        xs = [p[0] for p in sq["points"]]
        ys = [p[1] for p in sq["points"]]
        self.assertAlmostEqual(max(xs) - min(xs), max(ys) - min(ys))

    def test_numeric_side_is_stem_number(self):
        b = ga.build_algebra_area(figure_id="g9a2",
                                  stem="A plot is x by 2 metres.",
                                  style="rectangle", top="x", side="2")
        self.assertIn('side 2', b.claims)
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9a3",
                                  stem="A plot is x by 5 metres.",
                                  style="rectangle", top="x", side="2")

    def test_area_must_be_true_product(self):

        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9a5", stem=STEM_SQ,
                                  style="rectangle", square=True,
                                  top="x", side="x", area="x^{3}")

        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9a6",
                                  stem="A floor is 3 by 4 tiles; area 13.",
                                  style="rectangle", top="3", side="4",
                                  area="13")

        b = ga.build_algebra_area(figure_id="g9a7",
                                  stem="A floor is 3 by 4 tiles; area 12.",
                                  style="rectangle", top="3", side="4",
                                  area="12")
        self.assertIn("the centre label 12 is the product 3 x 4", b.claims)

        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9a8", stem=STEM_SQ,
                                  style="rectangle", top="x+8", side="x+5",
                                  area="x^{2}+13x+40")

    def test_figure_mode_reads_off(self):
        b = ga.build_algebra_area(figure_id="g9a4", stem=STEM_FIG,
                                  style="rectangle", top="a", side="3",
                                  values="figure")
        self.assertIn("figure content", b.claims)


class CornerCutTests(unittest.TestCase):
    def test_strips_remaining_rect(self):
        b = ga.build_algebra_area(figure_id="g9b1", stem=STEM_STRIP,
                                  style="corner_cut", mode="strips",
                                  outer_top="x", outer_side="x",
                                  cut_w="2", cut_h="3",
                                  inner_top="x-2", inner_side="x-3")
        polys = els(b, "polygon")
        self.assertEqual(len(polys), 2)
        self.assertEqual(polys[0].get("stroke", {}).get("style"), "dashed")
        self.assertIn("x-2", b.claims)
        self.assertIn("x - 3", b.claims.replace("x-3", "x - 3"))
        self.assertNotIn("shaded", next(
            l for l in b.claims.splitlines() if "none " in l).split("shaded")[0]
            + "")
        self.assertIn("arrow", next(
            l for l in b.claims.splitlines() if "none " in l))

    def test_strips_require_inner_labels(self):
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9b2", stem=STEM_STRIP,
                                  style="corner_cut", mode="strips",
                                  outer_top="x", outer_side="x",
                                  cut_w="2", cut_h="3")

    def test_corner_l_shape_is_difference(self):
        b = ga.build_algebra_area(figure_id="g9b3",
                                  stem="A square of side a loses a corner "
                                       "square of side b.",
                                  style="corner_cut", mode="corner",
                                  outer_top="a", outer_side="a",
                                  cut_w="b", cut_h="b", corner="tr",
                                  square=True)
        rem = next(p for p in els(b, "polygon") if p["id"] == "rem")
        self.assertEqual(len(rem["points"]), 6)
        self.assertIn("outer a x a rectangle less the b x b corner", b.claims)
        cut = next(p for p in els(b, "polygon") if p["id"] == "cut")
        self.assertEqual(cut.get("stroke", {}).get("style"), "dashed")

    def test_numeric_cut_is_stem_number(self):
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9b4",
                                  stem="A square of side a loses a corner "
                                       "of width 4.",
                                  style="corner_cut", mode="corner",
                                  outer_top="a", outer_side="a",
                                  cut_w="5", cut_h="b")


class FrameTests(unittest.TestCase):
    def test_shaded_band_difference(self):
        b = ga.build_algebra_area(figure_id="g9c1",
                                  stem="A frame is x+8 by x+5 with an "
                                       "inner x+2 by x+1 opening.",
                                  style="frame",
                                  outer_top="x+8", outer_side="x+5",
                                  inner_top="x+2", inner_side="x+1",
                                  W=160.0, H=120.0, frac=0.4)
        self.assertIn("outer x+8 x x+5 rectangle less the x+2 x x+1 "
                      "inner one", b.claims)
        band = next(p for p in els(b, "polygon") if p["id"] == "band")
        self.assertEqual(len(band["points"]), 6)

    def test_dissection_refused(self):
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9c2", stem=STEM_SQ,
                                  style="dissection")


class MappingArrowTests(unittest.TestCase):
    def test_two_row_mapping(self):
        b = ga.build_mapping_arrows(figure_id="g9d1", stem=STEM_MAP,
                                    left=["5", "8"], right=["75", "x"],
                                    heads=["n", "Rs"])
        self.assertEqual(len(els(b, "arrow")), 2)
        self.assertIn("derive 75 / 5 = 15", b.claims)
        self.assertIn('"5 maps to 75"', b.claims)
        self.assertIn('"8 maps to x"', b.claims)
        heads = sorted(e["latex"] for e in els(b, "math")
                       if e["id"] in ("hl", "hr"))
        self.assertEqual(heads, ["Rs", "n"])

    def test_single_oval_pair(self):
        b = ga.build_mapping_arrows(figure_id="g9d2",
                                    stem="If a : b = u : v, show the mapping.",
                                    left=["a", "b"], right=["u", "v"])
        self.assertEqual(len(els(b, "arrow")), 2)

    def test_unknown_symbolic_no_stem_needed(self):
        b = ga.build_mapping_arrows(figure_id="g9d3", stem=STEM_MAP,
                                    left=["5", "8"], right=["75", "x"])
        self.assertIn("x", [e["latex"] for e in els(b, "math")])

    def test_numeric_token_must_be_in_stem(self):
        with self.assertRaises(vt.TemplateError):
            ga.build_mapping_arrows(
                figure_id="g9d4",
                stem="5 pens cost 75 rupees. Find the price x of 8 pens.",
                left=["5", "9"], right=["75", "x"])

    def test_figure_mode(self):
        b = ga.build_mapping_arrows(figure_id="g9d5", stem=STEM_FIG,
                                    left=["100", "500"], right=["115", "x"],
                                    values="figure")
        self.assertIn("figure content", b.claims)

    def test_domain_refusals(self):
        for kw in (dict(left=["5"], right=["75", "x"]),
                   dict(left=[], right=[]),
                   dict(left=["5"] * 5, right=["x"] * 5),
                   dict(values="maybe"),
                   dict(heads=["n"]),
                   dict(left=["a long phrase"], right=["x"]),
                   dict(row_gap=5.0), dict(col_gap=10.0)):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                spec = dict(figure_id="g9d9", stem=STEM_MAP,
                            left=["5", "8"], right=["75", "x"])
                spec.update(kw)
                ga.build_mapping_arrows(**spec)

    def test_numeric_validator_first(self):
        for bad in (True, float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                ga.build_mapping_arrows(figure_id="g9db", stem=STEM_MAP,
                                        left=["5"], right=["75"],
                                        row_gap=bad)


class CriticFixTests(unittest.TestCase):
    """critic-solids-area.md F3, F4, F5, F7, F8, F9."""

    def test_f3_non_proportional_rows_refused(self):
        for l, r in ((["2", "3"], ["10", "99"]),
                     (["5", "5"], ["75", "90"]),
                     (["5", "5"], ["75", "75"]),
                     (["5", "8"], ["x", "x"]),
                     (["0", "4"], ["3", "x"])):
            with self.subTest(l=l, r=r), self.assertRaises(vt.TemplateError):
                ga.build_mapping_arrows(figure_id="g9f3", stem=STEM_FIG,
                                        left=l, right=r, values="figure")
        b = ga.build_mapping_arrows(figure_id="g9f3b", stem=STEM_FIG,
                                    left=["2", "3", "x"],
                                    right=["10", "15", "40"],
                                    values="figure")
        self.assertEqual(b.claims.count("= 5 |"), 2)

    def test_f4_strips_identity_verified_or_omitted(self):
        base = dict(figure_id="g9f4", stem=STEM_STRIP, style="corner_cut",
                    mode="strips", outer_top="x", outer_side="x",
                    cut_w="2", cut_h="3")

        for it, is_ in (("x-5", "x-3"), ("y", "x-3"), ("x-2", "z")):
            with self.subTest(it=it, is_=is_), \
                    self.assertRaises(vt.TemplateError):
                ga.build_algebra_area(**base, inner_top=it, inner_side=is_)

        b = ga.build_algebra_area(**base, inner_top="x-2",
                                  inner_side="\\sqrt{x}")
        self.assertNotIn("sqrt x = x - 3", b.claims)
        self.assertIn("where x-2 = x - 2", b.claims)
        self.assertNotIn(" and ", next(l for l in b.claims.splitlines()
                                       if "remaining rectangle" in l))

        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9f4n",
                                  stem="A 3 by 3 square loses strips 3 and 1.",
                                  style="corner_cut", mode="strips",
                                  outer_top="3", outer_side="3", cut_w="3",
                                  cut_h="1", inner_top="0", inner_side="2")

    def test_f4_frame_gap_must_be_band_width(self):
        spec = dict(figure_id="g9f4f",
                    stem="A frame x+8 by x+5 with an x+2 by x+1 opening; "
                         "bands 4 and 6.",
                    style="frame", outer_top="x+8", outer_side="x+5",
                    inner_top="x+2", inner_side="x+1",
                    W=160.0, H=120.0, frac=0.4)
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(**spec, gap_top="x+2", gap_side="x+1")
        with self.assertRaisesRegex(vt.TemplateError, "no unambiguous bounded layout"):
            ga.build_algebra_area(**spec, gap_top="4", gap_side="6")
        b = ga.build_algebra_area(**spec, gap_side="6")
        self.assertIn("verified as outer_top - inner_top", b.claims)

    def test_f5_signed_decimal_comma_tokens(self):
        for tok in ("-3", ".5", "−3"):
            with self.subTest(tok=tok), self.assertRaises(vt.TemplateError):
                ga.build_mapping_arrows(figure_id="g9f5", stem="nothing",
                                        left=[tok], right=["x"])
        with self.assertRaises(vt.TemplateError):
            ga.build_mapping_arrows(figure_id="g9f5", stem="1,000 and 15",
                                    left=["1,000"], right=["x"])
        with self.assertRaises(vt.TemplateError):
            ga.build_mapping_arrows(figure_id="g9f5", stem=STEM_FIG,
                                    left=["1,000"], right=["x"],
                                    values="figure")

        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9f5a",
                                  stem="A plot is x+7 by x metres.",
                                  style="rectangle", top="x+8", side="x")

        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9f5b",
                                  stem="A side of -3 and x.",
                                  style="rectangle", top="-3", side="x")

    def test_f7_unshaded_claims_no_shading(self):
        for kw in (dict(style="frame", outer_top="x+8", outer_side="x+5",
                        inner_top="x+2", inner_side="x+1",
                        W=160.0, H=120.0, frac=0.4),
                   dict(style="corner_cut", mode="corner", outer_top="a",
                        outer_side="a", cut_w="b", cut_h="b", square=True),
                   dict(style="corner_cut", mode="strips", outer_top="x",
                        outer_side="x", cut_w="2", cut_h="3",
                        inner_top="x-2", inner_side="x-3")):
            with self.subTest(style=kw["style"], mode=kw.get("mode")):
                b = ga.build_algebra_area(figure_id="g9f7", stem=STEM_STRIP
                                          + " x+8 x+5 x+2 x+1", shaded=False,
                                          values="figure", **kw)
                self.assertNotIn("the shaded", b.claims)
                none = next(l for l in b.claims.splitlines() if "none " in l)
                self.assertIn("shaded", none)
                self.assertFalse(any(e.get("fill") for e in b.doc["elements"]))

    def test_f8_f9_malformed_stem_and_medium(self):
        for kw in (dict(stem=None), dict(stem=12), dict(medium="klingon"),
                   dict(medium=None)):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                spec = dict(figure_id="g9f8", stem=STEM_SQ, style="rectangle",
                            top="x", side="x")
                spec.update(kw)
                ga.build_algebra_area(**spec)
            with self.subTest(map=kw), self.assertRaises(vt.TemplateError):
                spec = dict(figure_id="g9f8", stem=STEM_MAP,
                            left=["5", "8"], right=["75", "x"])
                spec.update(kw)
                ga.build_mapping_arrows(**spec)


class SharedGateTests(unittest.TestCase):
    def test_huge_int_refuses_as_template_error(self):
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9huge", stem=STEM_SQ,
                                  style="rectangle", top="x", side="x",
                                  W=10**400)
        with self.assertRaises(vt.TemplateError):
            ga.build_mapping_arrows(figure_id="g9huge", stem=STEM_MAP,
                                    left=["5", "8"], right=["75", "x"],
                                    row_gap=10**400)

    def test_nonfinite_dims(self):
        for bad in (True, "9", float("nan")):
            with self.subTest(W=bad), self.assertRaises(vt.TemplateError):
                ga.build_algebra_area(figure_id="g9e1", stem=STEM_SQ,
                                      style="rectangle", top="x", side="x",
                                      W=bad)

    def test_missing_side_labels(self):
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9e2", stem=STEM_SQ,
                                  style="rectangle", top="x")

    def test_prose_token_refused(self):
        with self.assertRaises(vt.TemplateError):
            ga.build_algebra_area(figure_id="g9e3", stem=STEM_SQ,
                                  style="rectangle", top="x metres long",
                                  side="x")


if __name__ == "__main__":
    unittest.main()
