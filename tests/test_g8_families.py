"""G8 readiness — tools/vdd_g8_families.py (stem_leaf / tessellation /
bearing_map for L27, L30 and L24).

All stems are SYNTHETIC English — no corpus text is reproduced.  The audits
run the real `audit-claim-set.py` over each emitted claim set; the refusal
tables exercise the numeric gates (bool/string/non-finite/oversized), the
geometric guards (patches that cannot draw honestly, rays that cannot fix),
and the stem-mode givens the stem never states.
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
import vdd_g8_families as gf

STEM_SL = "The data are 23, 25, 31, 31, 37, 42, 45, 45 and 47."
STEM_TS = "A pattern uses square tiles in 3 rows and 4 columns."
STEM_TT = "Equilateral triangles tile a 3 by 3 patch; each corner is 60."
STEM_BM = "From A the bearing of T is 050; from B it is 310."


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


class StemLeafTests(unittest.TestCase):
    def test_ordered_plot_sorts_and_claims(self):
        b = gf.build_stem_leaf(figure_id="g8sl1", stem=STEM_SL,
                               data=[37, 25, 45, 31, 23, 42, 45, 47, 31])
        audit(b)
        self.assertIn('describe "stem 2: leaves 3 5"', b.claims)
        self.assertIn('describe "stem 4: leaves 2 5 5 7"', b.claims)
        self.assertIn("derive 2 + 3 + 4 = 9", b.claims)
        self.assertIn("derive 47 - 23 = 24", b.claims)
        self.assertIn('label "means 23" names keyline', b.claims)
        texts = [e["value"] for e in els(b, "text")]
        self.assertEqual(texts.count("5"), 3)          # every leaf is printed
        # every row sits between two horizontal rules — a leaf digit is
        # always ~25 canvas units from a stroke it belongs to
        rule_ys = [e["points"][0][1] for e in els(b, "line")
                   if e["id"].startswith("hrule")]
        self.assertEqual(len(rule_ys), 4)              # 3 rows → 4 row rules
        for leaf in (e for e in els(b, "text") if e["id"].startswith("l")):
            self.assertEqual(min(abs(leaf["at"][1] - ry)
                                 for ry in rule_ys), 25.0)

    def test_unordered_and_key(self):
        b = gf.build_stem_leaf(figure_id="g8sl2", stem=STEM_SL,
                               data=[37, 25, 45, 31, 23, 42, 45, 47, 31],
                               ordered=False, key=(4, 5))
        audit(b)
        self.assertIn('describe "the leaves are shown in data order '
                      '(unsorted)"', b.claims)
        self.assertIn('describe "the key reads stem 4 with leaf 5 as 45"',
                      b.claims)

    def test_figure_mode(self):
        b = gf.build_stem_leaf(figure_id="g8sl3", stem="Read the plot.",
                               data=[12, 15, 21, 26], values="figure")
        audit(b)
        self.assertIn("figure content", b.claims)
        with self.assertRaises(vt.TemplateError):
            gf.build_stem_leaf(figure_id="g8sl3", stem="Read the plot.",
                               data=[12, 15, 21, 26], values="stem")

    def test_stem_leaf_refusals(self):
        spec = dict(figure_id="g8slb", stem=STEM_SL,
                    data=[23, 25, 31, 31, 37, 42, 45, 45, 47])
        for kw in ({"data": [1, 2]},
                   {"data": list(range(10, 30))},            # > 8 rows
                   {"data": [10 + i for i in range(10)]},    # > 8 leaves/row
                   {"data": [12, 15, 21.5, 26]},             # non-integer
                   {"data": [12, -3, 21]},                   # negative
                   {"data": [12, 15, 1000]},                 # ≥ 1000
                   {"ordered": False},                       # sorted data lies
                   {"key": (3,)}, {"key": (3, 12)},
                   {"values": "maybe"}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gf.build_stem_leaf(**{**spec, **kw})

    def test_numeric_guards(self):
        for bad in (True, "31", float("nan"), float("inf"), 10 ** 400):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                gf.build_stem_leaf(figure_id="g8slb", stem=STEM_SL,
                                   data=[23, bad, 45])
        for bad in (True, "7", float("nan")):
            with self.subTest(kb=bad), self.assertRaises(vt.TemplateError):
                gf.build_stem_leaf(figure_id="g8slb", stem=STEM_SL,
                                   data=[23, 31, 45], key=(4, bad))

    def test_key_must_restate_a_drawn_row(self):
        with self.assertRaisesRegex(vt.TemplateError, "restate"):
            gf.build_stem_leaf(figure_id="g8slb", stem=STEM_SL,
                               data=[23, 25, 31, 45], key=(9, 9))

    def test_two_digit_key_stem_seats(self):
        b = gf.build_stem_leaf(figure_id="g8sl4",
                               stem="The data are 100, 110 and 120.",
                               data=[100, 110, 120], key=(10, 0))
        audit(b)
        self.assertIn('describe "the key reads stem 10 with leaf 0 as 100"',
                      b.claims)


class TessellationTests(unittest.TestCase):
    def test_square_vertex_rights_and_shade(self):
        b = gf.build_tessellation(figure_id="g8ts1", stem=STEM_TS,
                                  tile="square", rows=3, cols=4, cell=50,
                                  shade=[0, 6], vertex="V")
        audit(b)
        self.assertIn('describe "a 3 by 4 patch of square tiles"', b.claims)
        self.assertIn("derive 3 * 4 = 12", b.claims)
        self.assertIn("shaded 2 of 12 cells", b.claims)
        self.assertIn("paint cell6 shaded", b.claims)
        self.assertIn("right A V B", b.claims)
        self.assertIn("derive 4 * 90 = 360", b.claims)
        self.assertIn("equal VA VB", b.claims)
        self.assertIn('describe "4 square corners meet at V"', b.claims)
        # each vertex letter seats in the tile pocket nearest its vertex —
        # within the target rule's reach of its own dot
        for e in els(b, "text"):
            if e["id"].startswith("t") and len(e["value"]) == 1:
                ax, ay = b.anchors[e["value"]]
                self.assertLessEqual(
                    math.hypot(e["at"][0] - ax, e["at"][1] - ay), 30.0,
                    f"letter {e['value']} drifts from its vertex")

    def test_triangle_vertex_angles(self):
        b = gf.build_tessellation(figure_id="g8ts2", stem=STEM_TT,
                                  tile="triangle", rows=3, cols=3, cell=70,
                                  vertex="V")
        audit(b)
        self.assertIn("derive 2 * 9 = 18", b.claims)
        self.assertIn("angle A V B = 60", b.claims)
        self.assertIn("derive 6 * 60 = 360", b.claims)
        self.assertIn('describe "6 equilateral triangle corners meet at V"',
                      b.claims)

    def test_edge_vertex_claims_real_sectors(self):
        # a vertex on a patch edge is not fully surrounded — the claims must
        # measure the real sectors, never assume 360/k
        b = gf.build_tessellation(figure_id="g8ts4",
                                  stem="A strip uses square tiles in 1 row and "
                                       "4 columns.",
                                  tile="square", rows=1, cols=4, cell=50,
                                  vertex="V")
        audit(b)
        self.assertNotIn("= 360", b.claims)          # no fake vertex-sum derive
        self.assertNotIn("corners of the tile (", b.claims)
        self.assertIn("collinear", b.claims)         # the straight seam is real

    def test_hexagon_plain_patch(self):
        b = gf.build_tessellation(figure_id="g8ts3",
                                  stem="The honeycomb uses 2 rows and 3 columns.",
                                  tile="hexagon", rows=2, cols=3)
        audit(b)
        self.assertIn("derive 2 * 3 = 6", b.claims)
        self.assertIn("none tickMark parallelMark angleMark angleArc arrow "
                      "dashed shaded", b.claims)

    def test_tessellation_refusals(self):
        spec = dict(figure_id="g8tsb", stem=STEM_TS, tile="square",
                    rows=3, cols=4)
        for kw in ({"tile": "pentagon"}, {"tile": "rhombus"},
                   {"rows": 0}, {"rows": 7}, {"cols": 2.5},
                   {"rows": True}, {"rows": "3"},
                   {"rows": 6, "cols": 7},
                   {"shade": [12]}, {"shade": [-1]}, {"shade": [0, 0]},
                   {"shade": "3"},
                   {"vertex": "v"}, {"vertex": "V", "cell": 40},
                   {"values": "maybe"},
                   {"cell": True}, {"cell": float("nan")}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gf.build_tessellation(**{**spec, **kw})
        with self.assertRaises(vt.TemplateError):   # triangle vertex needs 3×3
            gf.build_tessellation(figure_id="g8tsb", stem=STEM_TT,
                                  tile="triangle", rows=2, cols=4, cell=70,
                                  vertex="V")
        with self.assertRaises(vt.TemplateError):   # unstated givens
            gf.build_tessellation(figure_id="g8tsb", stem="A grid of tiles.",
                                  tile="square", rows=3, cols=4)


class BearingMapTests(unittest.TestCase):
    def test_computed_fix_and_claims(self):
        b = gf.build_bearing_map(figure_id="g8bm1", stem=STEM_BM,
                                 centres={"A": (0, 0), "B": (6, 0)},
                                 bearings={"A": 50, "B": 310})
        audit(b)
        self.assertIn("angle C A T = 50", b.claims)
        self.assertIn("parallel AC BD", b.claims)
        self.assertIn("derive 310 - 50 = 260", b.claims)
        self.assertIn("derive 360 - 260 = 100", b.claims)
        self.assertIn("angle A T B = 100", b.claims)
        self.assertIn('describe "the reflex bearing at B is 310°', b.claims)
        # the fix really is the ray intersection
        T, A, B = b.anchors["T"], b.anchors["A"], b.anchors["B"]
        d_at = math.degrees(math.atan2(T[1] - A[1], T[0] - A[0])) % 360
        d_bt = math.degrees(math.atan2(T[1] - B[1], T[0] - B[0])) % 360
        self.assertAlmostEqual(d_at, (50 - 90) % 360, places=3)
        self.assertAlmostEqual(d_bt, (310 - 90) % 360, places=3)
        # each bearing numeral seats by its own angle mark (arc r=30 at the
        # vertex) — near enough that the target rule reads it as that arc's
        marks = {e["id"]: e for e in els(b, "angleMark")}
        for lt, mid in (("A", "ang1"), ("B", "ang2")):
            gl = next(e for e in els(b, "text") if e["id"] == f"gl{lt}")
            vx, vy = marks[mid]["vertex"]
            r_gl = math.hypot(gl["at"][0] - vx, gl["at"][1] - vy)
            self.assertGreaterEqual(r_gl, 40.0)        # outside the arc
            self.assertLessEqual(r_gl, 90.0)           # beside it, not adrift

    def test_bearing_map_refusals(self):
        spec = dict(figure_id="g8bmb", stem=STEM_BM,
                    centres={"A": (0, 0), "B": (6, 0)},
                    bearings={"A": 50, "B": 310})
        for kw in ({"bearings": {"A": 90, "B": 270}},    # parallel rays
                   {"bearings": {"A": 270, "B": 90}},    # diverging rays
                   {"bearings": {"A": 310}},             # missing a centre
                   {"bearings": {"A": 50, "B": 360}},    # 360 is not a bearing
                   {"bearings": {"A": -5, "B": 310}},
                   {"centres": {"A": (0, 0)}},           # one centre
                   {"centres": {"A": (0, 0), "B": (0.1, 0)}},  # coincident
                   {"centres": {"A": (0, 0), "a": (6, 0)}},
                   {"target": "A"},                       # letter collision
                   {"unit_px": True}, {"unit_px": "45"}):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                gf.build_bearing_map(**{**spec, **kw})

    def test_numeric_guards_and_stem(self):
        for bad in (True, "50", float("nan"), float("inf"), 10 ** 400):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                gf.build_bearing_map(figure_id="g8bmb", stem=STEM_BM,
                                     centres={"A": (0, 0), "B": (6, 0)},
                                     bearings={"A": bad, "B": 310})
            with self.subTest(cb=bad), self.assertRaises(vt.TemplateError):
                gf.build_bearing_map(figure_id="g8bmb", stem=STEM_BM,
                                     centres={"A": (bad, 0), "B": (6, 0)},
                                     bearings={"A": 50, "B": 310})
        with self.assertRaises(vt.TemplateError):   # bearing not in the stem
            gf.build_bearing_map(figure_id="g8bmb",
                                 stem="From A the bearing of T is 050.",
                                 centres={"A": (0, 0), "B": (6, 0)},
                                 bearings={"A": 50, "B": 310})


if __name__ == "__main__":
    unittest.main()
