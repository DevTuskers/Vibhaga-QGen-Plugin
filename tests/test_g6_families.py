"""G6 readiness — tools/vdd_g6_families.py (tally_chart / balance_scale /
cube_net for inventory-g6 confirmed gaps 3, 4 and 5).

All stems are SYNTHETIC English — no corpus text is reproduced.  The audits
run the real `audit-claim-set.py` over each emitted claim set; the refusal
tables exercise the mathematical guards (bool/string/non-finite numerics,
impossible states, and stem-mode givens the stem never states).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g6_families as gf

STEM_TALLY = "A tally table shows 12 cars and 8 bikes."
STEM_BAL = "A pan holds 5 kg and 2 kg against 7 kg."
STEM_BAL_UNK = "A pan holds 5 kg and a bag A against 7 kg."
STEM_CUBE = "A cube has edge 5 cm."
STEM_CUBOID = "A box is 4 cm by 3 cm by 2 cm."
STEM_TETRA = "A tetrahedron has edge 6 cm."


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


class TallyChartTests(unittest.TestCase):
    def test_happy_path_groups_of_five(self):
        b = gf.build_tally_chart(figure_id="g6tc1", stem=STEM_TALLY,
                                 rows=[("Cars", 12), ("Bikes", 8)])
        audit(b)
        self.assertIn('label "Cars" names cat0', b.claims)
        self.assertIn('describe "the Cars row tallies 12 — 2 groups of five '
                      'and 2 single strokes"', b.claims)
        self.assertIn("derive 12 + 8 = 20", b.claims)
        # 12 → 2 gates (4 uprights + a diagonal) + 2 singles: 2*5+2 strokes
        row0 = [e for e in els(b, "line") if e["id"].startswith("tal0")
                or e["id"].startswith("x0")]
        self.assertEqual(len(row0), 12)

    def test_figure_mode_is_honest(self):
        b = gf.build_tally_chart(figure_id="g6tc2", stem="Count the strokes.",
                                 rows=[("Dogs", 7)], values="figure")
        audit(b)
        self.assertIn("figure content", b.claims)
        with self.assertRaises(vt.TemplateError):
            gf.build_tally_chart(figure_id="g6tc2", stem="Count the strokes.",
                                 rows=[("Dogs", 7)], values="stem")

    def test_tally_refusals(self):
        spec = dict(figure_id="g6tcb", stem=STEM_TALLY,
                    rows=[("Cars", 12), ("Bikes", 8)])
        for kw in ({"rows": []},
                   {"rows": [("Cars", 12)] * 7},
                   {"rows": [("Cars", 12), ("Cars", 3)]},
                   {"rows": [("two words!", 4)]},
                   {"rows": [("Cars", 2.5)]},
                   {"rows": [("Cars", 31)]},
                   {"rows": [("Cars", True)]},
                   {"rows": [("Cars", "12")]},
                   {"rows": [("Cars", float("nan"))]},
                   {"rows": [("Cars", 10 ** 400)]},
                   {"values": "maybe"}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gf.build_tally_chart(**{**spec, **kw})
        with self.assertRaises(vt.TemplateError):       # unstated stem given
            gf.build_tally_chart(figure_id="g6tcb", stem="A tally table.",
                                 rows=[("Cars", 12)])


class BalanceScaleTests(unittest.TestCase):
    def test_level_equal_totals(self):
        b = gf.build_balance_scale(figure_id="g6bs1", stem=STEM_BAL,
                                   left=[5, 2], right=[7], state="level")
        audit(b)
        self.assertIn('label "5 kg" names itl0', b.claims)
        self.assertIn('describe "the beam is level — the pans balance"',
                      b.claims)
        self.assertIn("derive 5 + 2 = 7", b.claims)
        self.assertIn("derive 7 = 7", b.claims)

    def test_tilted_and_unknown(self):
        b = gf.build_balance_scale(figure_id="g6bs2", stem=STEM_BAL_UNK,
                                   left=[5, "A"], right=[7],
                                   state="right_down")
        audit(b)
        self.assertIn('label "A" names itl1', b.claims)
        self.assertIn("right pan hangs lower", b.claims)
        self.assertIn("named objects or unknowns", b.claims)
        b2 = gf.build_balance_scale(figure_id="g6bs3", stem="What mass balances?",
                                    left=["?"], right=[7], state="level",
                                    values="figure")
        audit(b2)
        self.assertIn('label "?" names itl0', b2.claims)

    def test_numeric_contradictions_refuse(self):
        unbal = "The left pan holds 5 kg and 2 kg; the right holds 8 kg."
        with self.assertRaisesRegex(vt.TemplateError, "level beam|balance"):
            gf.build_balance_scale(figure_id="g6bsb", stem=unbal,
                                   left=[5, 2], right=[8], state="level")
        with self.assertRaisesRegex(vt.TemplateError, "lighter side"):
            gf.build_balance_scale(figure_id="g6bsb", stem=unbal,
                                   left=[5, 2], right=[8], state="left_down")
        with self.assertRaisesRegex(vt.TemplateError, "lighter side"):
            gf.build_balance_scale(figure_id="g6bsb", stem="Each pan holds 7 kg.",
                                   left=[7], right=[7], state="right_down")

    def test_wide_pan_would_cross_the_fulcrum(self):
        # a rim this wide reaches the fulcrum's reach on the inner side —
        # the builder must refuse rather than draw a yoke through it
        with self.assertRaisesRegex(vt.TemplateError, "fulcrum"):
            gf.build_balance_scale(figure_id="g6bsb", stem=STEM_BAL,
                                   left=["12 kg", "?", "12 kg"],
                                   right=["12 kg", "?", "12 kg"],
                                   state="level", unit="kg", values="figure")

    def test_balance_refusals(self):
        spec = dict(figure_id="g6bsb", stem=STEM_BAL,
                    left=[5, 2], right=[7], state="level")
        for kw in ({"state": "flat"},
                   {"left": []}, {"right": [1, 2, 3, 4, 5]},
                   {"left": [True]}, {"left": [-5]}, {"left": ["5 g"]},
                   {"left": [float("nan")]}, {"left": ["abc def"]},
                   {"tilt_deg": 4}, {"tilt_deg": 30}, {"tilt_deg": "12"},
                   {"unit": "kilogram!"}, {"values": "maybe"}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gf.build_balance_scale(**{**spec, **kw})
        with self.assertRaises(vt.TemplateError):       # unstated mass
            gf.build_balance_scale(figure_id="g6bsb", stem="A balance.",
                                   left=[5], right=[5], state="level")


class CubeNetTests(unittest.TestCase):
    def test_cube_cross(self):
        b = gf.build_cube_net(figure_id="g6cn1", stem=STEM_CUBE, shape="cube",
                              dims={"edge": 5}, unit="cm",
                              labels=["A", "B", "C", "D", "E", "F"],
                              scale_px=44)
        audit(b)
        self.assertRegex(b.claims, r"right [A-Z] [A-Z] [A-Z] \| measured \| a corner")
        self.assertIn("derive 4 + 2 = 6", b.claims)
        self.assertIn('label "A" names region_face0', b.claims)
        self.assertIn('label "5 cm" names', b.claims)
        dashed = [e for e in els(b, "line")
                  if e.get("stroke", {}).get("style") == "dashed"]
        self.assertEqual(len(dashed), 5)                # 5 shared fold edges

    def test_cuboid_strip(self):
        b = gf.build_cube_net(figure_id="g6cn2", stem=STEM_CUBOID,
                              shape="cuboid",
                              dims={"length": 4, "width": 3, "height": 2},
                              unit="cm", scale_px=44)
        audit(b)
        self.assertRegex(b.claims, r"right [A-Z] [A-Z] [A-Z] \| measured \| a corner")
        self.assertIn('label "4 cm" names', b.claims)
        # dimension glyphs draw as label-only `point` elements anchored just
        # off their measured edge — never floating text far from the ink
        dims = [e for e in els(b, "point") if e.get("label")]
        self.assertEqual(len(dims), 3)
        dashed = [e for e in els(b, "line")
                  if e.get("stroke", {}).get("style") == "dashed"]
        self.assertEqual(len(dashed), 5)

    def test_tetrahedron_strip(self):
        b = gf.build_cube_net(figure_id="g6cn3", stem=STEM_TETRA,
                              shape="tetrahedron", dims={"edge": 6},
                              unit="cm", scale_px=40)
        audit(b)
        self.assertRegex(b.claims, r"equal [A-Z][A-Z] [A-Z][A-Z] \| measured \| equilateral")
        self.assertIn("derive 1 + 1 + 1 + 1 = 4", b.claims)
        dashed = [e for e in els(b, "line")
                  if e.get("stroke", {}).get("style") == "dashed"]
        self.assertEqual(len(dashed), 3)

    def test_figure_mode_dims(self):
        b = gf.build_cube_net(figure_id="g6cn4", stem="Read the net.",
                              shape="cube", dims={"edge": 5},
                              values="figure", scale_px=44)
        audit(b)
        self.assertIn("figure content", b.claims)

    def test_net_refusals(self):
        spec = dict(figure_id="g6cnb", stem=STEM_CUBE, shape="cube",
                    dims={"edge": 5}, scale_px=44)
        for kw in ({"shape": "pyramid"},
                   {"dims": {"edge": 5, "extra": 2}},
                   {"dims": {"edge": -5}},
                   {"dims": {"edge": True}},
                   {"dims": {"edge": "5"}},
                   {"dims": {"edge": float("nan")}},
                   {"dims": {"edge": 10 ** 400}},
                   {"dims": None},
                   {"labels": ["A", "B", "C", "D", "E"]},
                   {"labels": ["A", "B", "C", "D", "E", "A"]},
                   {"labels": ["A", "b", "C", "D", "E", "F"]},
                   {"labels": {"A": 1}},
                   {"scale_px": 5}, {"scale_px": "30"},
                   {"values": "maybe"}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gf.build_cube_net(**{**spec, **kw})
        with self.assertRaises(vt.TemplateError):       # thin faces refuse
            gf.build_cube_net(figure_id="g6cnb", stem=STEM_CUBOID,
                              shape="cuboid",
                              dims={"length": 4, "width": 3, "height": 0.5},
                              scale_px=40)
        with self.assertRaises(vt.TemplateError):       # cuboid needs 3 dims
            gf.build_cube_net(figure_id="g6cnb", stem=STEM_CUBOID,
                              shape="cuboid", dims={"edge": 4})
        with self.assertRaises(vt.TemplateError):       # unstated stem given
            gf.build_cube_net(figure_id="g6cnb", stem="A cube.", shape="cube",
                              dims={"edge": 5})


if __name__ == "__main__":
    unittest.main()
