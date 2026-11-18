"""G9 readiness — L02 Number Base Two place-value frame (tools/vdd_g9_binary.py).

The lesson's abacus rods are headed by POWER forms (2^3 … 2^0) and its
digit-to-place figures map each digit onto its power header — neither is the
plain abacus's `8 4 2 1` numerals. All stems are SYNTHETIC English.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g9_binary as gb

STEM_13 = "A display shows the number 13 in base 2. Write it in binary."
STEM_FIG = "What number does the frame show?"


def els(b, t):
    return [e for e in b.doc["elements"] if e["type"] == t]


class G9BinaryFrameTests(unittest.TestCase):
    def test_rods_power_headers_and_beads(self):
        b = gb.build_place_value_frame(figure_id="g9b1", stem=STEM_13,
                                       style="rods", base=2, digits=[1, 1, 0, 1])
        heads = [e["value"] for e in
                 sorted((e for e in els(b, "text") if e["id"].startswith("hv")),
                        key=lambda e: int(e["id"][2:]))]
        self.assertEqual(heads, ["2³", "2²", "2¹", "2⁰"])
        self.assertEqual(len(els(b, "circle")), 3)
        self.assertEqual(len(els(b, "math")), 0)
        self.assertIn("derive 1 * 8 + 1 * 4 + 0 * 2 + 1 * 1 = 13", b.claims)
        self.assertIn('label "8" names col1', b.claims)
        self.assertIn('label "2³" names hv1', b.claims)

    def test_digit_mapping_arrows(self):
        b = gb.build_place_value_frame(figure_id="g9b2", stem=STEM_13,
                                       style="digits", base=2,
                                       digits=[1, 1, 0, 1], show_value=False)
        self.assertEqual(len(els(b, "arrow")), 4)
        self.assertEqual(len(els(b, "text")), 8)
        self.assertNotIn(" arrow", next(
            l for l in b.claims.splitlines() if "none " in l))

    def test_reusable_across_bases(self):
        b = gb.build_place_value_frame(
            figure_id="g9b3",
            stem="The number 20 in base 5 uses the digits 4 and 0.",
            style="digits", base=5, digits=[4, 0])
        self.assertIn("derive 4 * 5 + 0 * 1 = 20", b.claims)
        self.assertEqual([e["value"] for e in
                          sorted((e for e in els(b, "text")
                                  if e["id"].startswith("hv")),
                                 key=lambda e: int(e["id"][2:]))],
                         ["5¹ = 5", "5⁰ = 1"])

    def test_figure_mode_read_off(self):
        b = gb.build_place_value_frame(figure_id="g9b4", stem=STEM_FIG,
                                       style="rods", base=2, digits=[1, 0, 1],
                                       values="figure")
        self.assertIn("figure content", b.claims)
        with self.assertRaises(vt.TemplateError):
            gb.build_place_value_frame(figure_id="g9b5", stem=STEM_FIG,
                                       style="rods", base=2, digits=[1, 0, 1],
                                       values="stem")

    def test_numeric_validator_first(self):
        for bad in (True, "2", float("nan"), float("inf")):
            with self.subTest(base=bad), self.assertRaises(vt.TemplateError):
                gb.build_place_value_frame(figure_id="g9bb", stem=STEM_13,
                                           base=bad, digits=[1, 0, 1])
            with self.subTest(digit=bad), self.assertRaises(vt.TemplateError):
                gb.build_place_value_frame(figure_id="g9bb", stem=STEM_13,
                                           base=2, digits=[1, bad, 1])

    def test_domain_refusals(self):
        for kw in (dict(base=1), dict(base=11), dict(base=2.5),
                   dict(digits=[]), dict(digits=[1] * 9),
                   dict(digits=[1, 2, 0]),
                   dict(digits=[0, 1]),
                   dict(values="maybe"),
                   dict(style="column"),
                   dict(style="rods", arrows=True),
                   dict(bead_r=99)):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                spec = dict(figure_id="g9bb", stem=STEM_13, base=2,
                            digits=[1, 0, 1])
                spec.update(kw)
                gb.build_place_value_frame(**spec)

    def test_critic_typed_options_and_malformed_specs(self):
        valid = dict(figure_id="probe1", stem="Read figure.", base=2,
                     digits=[1], values="figure")
        for key in ("arrows", "show_value"):
            for bad in ("false", "true", 0, 1, [], {}):
                with self.subTest(key=key, bad=bad), self.assertRaises(vt.TemplateError):
                    gb.build_place_value_frame(**dict(valid, **{key: bad}))
        for spec in ({}, dict(figure_id="p1", stem="x", bogus=1),
                     dict(valid, bogus=1), dict(valid, stem=None)):
            with self.subTest(spec=spec), self.assertRaises(vt.TemplateError):
                gb.build_place_value_frame(**spec)
        with self.assertRaises(vt.TemplateError):
            gb.build_place_value_frame(valid)

    def test_critic_typed_a11y_and_ask(self):
        valid = dict(figure_id="probe1", stem="Read figure.", base=2,
                     digits=[1], values="figure")
        for key in ("title", "description", "medium"):
            for bad in (3, True, [], {}):
                with self.subTest(key=key, bad=bad), \
                        self.assertRaises(vt.TemplateError):
                    gb.build_place_value_frame(**dict(valid, **{key: bad}))
        for medium in ("french", "si", ""):
            with self.subTest(medium=medium), self.assertRaises(vt.TemplateError):
                gb.build_place_value_frame(**dict(valid, medium=medium))
        for ask in ("a", 3, [], ["a"], [("a", 1)], [("a",)], [["a", "b", "c"]]):
            with self.subTest(ask=ask), self.assertRaises(vt.TemplateError):
                gb.build_place_value_frame(**dict(valid, ask=ask))

        b = gb.build_place_value_frame(**dict(valid, ask=[["a", "the number"]]))
        self.assertIn("the number", b.claims)

    def test_critic_huge_integer_refused_before_float(self):
        valid = dict(figure_id="probe1", stem="Read figure.", base=2,
                     digits=[1], values="figure")
        for huge in (10**1000, -(10**1000)):
            for key, value in (("base", huge), ("digits", [huge]), ("bead_r", huge)):
                with self.subTest(key=key), self.assertRaises(vt.TemplateError):
                    gb.build_place_value_frame(**dict(valid, **{key: value}))

    def test_stem_discipline(self):

        with self.assertRaises(vt.TemplateError):
            gb.build_place_value_frame(
                figure_id="g9bb",
                stem="A display shows the number 12 in base 2.",
                base=2, digits=[1, 1, 0, 1])


if __name__ == "__main__":
    unittest.main()
