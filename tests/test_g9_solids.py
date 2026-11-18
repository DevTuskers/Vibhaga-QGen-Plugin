"""G9 solids — open_cuboid_net (L09 activity), cuboid_water (L09 tank) and
regular_polyhedron (L17 tetrahedron/octahedron). All stems are SYNTHETIC."""
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g9_solids as solids


class SolidsTests(unittest.TestCase):
    def net(self, **kwargs):
        spec = dict(figure_id="synthetic-9-net", length=5, width=2, height=1,
                    stem="The net folds into an open cuboid 5 cm long, 2 cm wide and 1 cm high.")
        spec.update(kwargs)
        return solids.build_open_cuboid_net(**spec)

    def water(self, **kwargs):
        spec = dict(figure_id="synthetic-9-tank", length=30, width=10, height=12, depth=7,
                    stem="A tank is 30 cm long, 10 cm wide and 12 cm high. "
                         "Water fills it to a depth of 7 cm.")
        spec.update(kwargs)
        return solids.build_cuboid_water(**spec)

    def poly(self, **kwargs):
        spec = dict(figure_id="synthetic-9-poly", shape="tetrahedron", edge=4,
                    stem="A regular tetrahedron has edge length 4 cm.")
        spec.update(kwargs)
        return solids.build_regular_polyhedron(**spec)

    def audit(self, built):
        with tempfile.TemporaryDirectory() as tmp:
            paths = built.write(tmp)
            result = subprocess.run([sys.executable, str(TOOLS / "audit-claim-set.py"),
                                     str(paths["claims"])],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_audit_stem_and_figure_modes(self):
        self.audit(self.net())
        self.audit(self.net(values="figure", stem="The figure shows a net."))
        self.audit(self.water())
        self.audit(self.water(values="figure", stem="The figure shows a tank."))
        self.audit(self.poly())
        self.audit(self.poly(values="figure", stem="The figure shows a solid."))
        self.audit(self.poly(shape="octahedron"))
        self.audit(self.poly(shape="octahedron", edge=None, stem="Identify the solid."))
        self.audit(self.poly(edge=None, stem="Name the regular solid."))

    def test_audit_extremes(self):
        for dims in ((4, 4, 4), (12, 3, 9), (9, 1.5, 1.5)):
            with self.subTest(dims=dims):
                self.audit(self.net(length=dims[0], width=dims[1], height=dims[2],
                                    stem=f"An open cuboid {dims[0]:g} cm by {dims[1]:g} cm "
                                         f"by {dims[2]:g} cm."))
        for depth in (1, 2.4, 5.5, 11.9):
            with self.subTest(depth=depth):
                self.audit(self.water(depth=depth,
                                      stem=f"Synthetic reservoir: length 30 cm; width 10 cm; height 12 cm. Liquid is "
                                           f"{depth:g} cm deep."))

    def test_bad_numbers_before_conversion(self):
        for builder, key, bads in (
                (self.net, "length", (True, "5", None, float("nan"), float("inf"), -1, 0, 10**400)),
                (self.net, "height", (True, "5", None, float("nan"), float("inf"), -1, 0, 10**400)),
                (self.water, "depth", (True, "5", None, float("nan"), float("inf"), -1, 0, 10**400)),
                (self.water, "width", (True, "5", None, float("nan"), float("inf"), -1, 0, 10**400)),

                (self.poly, "edge", (True, "5", float("nan"), float("inf"), -1, 0, 10**400))):
            for bad in bads:
                with self.subTest(key=key, bad=repr(bad)[:20]), self.assertRaises(vt.TemplateError):
                    builder(**{key: bad})
        for bad in (True, "x", float("nan"), 95, 0):
            with self.assertRaises(vt.TemplateError):
                self.water(depth_angle=bad)
        for bad in (True, "x", 0, 1.4):
            with self.assertRaises(vt.TemplateError):
                self.water(depth_scale=bad)

    def test_stem_discipline_and_shape_bounds(self):
        for kwargs in (dict(stem="No numbers here."),
                       dict(height=3),
                       dict(values="other"),
                       dict(height=0.3),
                       ):
            with self.assertRaises(vt.TemplateError):
                self.net(**kwargs)
        for kwargs in (dict(depth=12), dict(depth=20), dict(depth=0.4),
                       dict(stem="Synthetic reservoir: length 30 cm; width 10 cm; height 12 cm."),
                       dict(values="other")):
            with self.assertRaises(vt.TemplateError):
                self.water(**kwargs)
        for shape in ("cube", "square_pyramid", "icosahedron", "dodecahedron", 5):
            with self.assertRaises(vt.TemplateError):
                self.poly(shape=shape)
        with self.assertRaises(vt.TemplateError):
            self.poly(stem="It has an edge, but the stem never says how long.")

    def test_net_is_a_true_unfolded_net(self):
        with patch.object(vt, "finish", side_effect=lambda **kw: kw):
            out = self.net()
        A, B, C, D = (out["anchors"][k] for k in "ABCD")
        self.assertAlmostEqual(abs(B[0] - A[0]), abs(D[1] - A[1]) * 2.5, places=6)
        E = out["anchors"]["E"]
        unit = abs(B[0] - A[0]) / 5
        self.assertAlmostEqual(abs(A[1] - E[1]), 1 * unit, places=6)
        folds = [e for e in out["elements"] if e["id"].startswith("fold")]
        self.assertEqual(len(folds), 4)
        self.assertTrue(all(e["stroke"]["style"] == "dashed" for e in folds))

        self.assertEqual(len(out["elements"]) - len(folds)
                         - sum(1 for e in out["elements"] if e["type"] == "text"), 12)

    def test_water_surface_is_computed(self):
        with patch.object(vt, "finish", side_effect=lambda **kw: kw):
            out = self.water()
        P, C, B = out["anchors"]["P"], out["anchors"]["C"], out["anchors"]["B"]

        drawn = abs(C[1] - out["anchors"]["Q"][1]) / abs(C[1] - B[1])
        self.assertAlmostEqual(drawn, 7 / 12, places=6)

        self.assertAlmostEqual(P[1], out["anchors"]["Q"][1], places=6)
        water = [e for e in out["elements"] if e["id"].startswith("water")]
        self.assertEqual(len(water), 3)
        self.assertTrue(any("ratio len CQ / len CB = 0.58" in c[0] for c in out["claims"]))
        self.assertTrue(any("ambiguous" not in c for c in out))
        self.assertTrue(out["contested"])

    def test_polyhedron_projection_and_hidden_edges(self):
        with patch.object(vt, "finish", side_effect=lambda **kw: kw):
            tet = self.poly()
            octa = self.poly(shape="octahedron", edge=None, stem="Identify it.")

        dashed = lambda o: [e["id"] for e in o["elements"] if e.get("stroke", {}).get("style") == "dashed"]
        self.assertEqual(dashed(tet), ["BC"])
        self.assertEqual(sorted(dashed(octa)), ["BS", "RS", "SP", "TS"])
        self.assertEqual(len(octa["elements"]), 12)
        self.assertFalse(any(e["type"] == "text" for e in octa["elements"]))

        A, D, B, C = (tet["anchors"][n] for n in "ADBC")
        self.assertTrue(all(A[1] < tet["anchors"][n][1] for n in "BCD"))
        self.assertGreater(D[1], (B[1] + C[1]) / 2)
        with self.assertRaises(vt.TemplateError):
            self.poly(shape="cube")

    def test_water_contested_only_when_width_label_printed(self):

        with patch.object(vt, "finish", side_effect=lambda **kw: kw):
            cube = self.water(length=10, width=10, height=10, depth=4,
                              stem="A 10 cm by 10 cm by 10 cm tank, water 4 cm deep.")
        self.assertFalse(cube["contested"])
        self.assertFalse(any(e.get("stroke", {}).get("color") for e in cube["elements"]
                             if e["id"] in ("CG",)))
        glyphs = [c[0] for c in cube["claims"] if c[0].startswith('label "')]
        self.assertEqual(glyphs, ['label "10 cm" names DC', 'label "4 cm" names DP'])

        with patch.object(vt, "finish", side_effect=lambda **kw: kw):
            out = self.water()
        kid, why = out["contested"][0]
        i = int(kid[1:])
        self.assertTrue(out["claims"][i - 1][0].startswith('label "10 cm" names CG'))
        self.assertIn("CG", why)

    def test_malformed_kwargs_refuse_as_template_error(self):

        for builder in (self.net, self.water, self.poly):
            with self.subTest(builder=builder.__name__), self.assertRaises(vt.TemplateError):
                builder(stem=None)
            with self.subTest(medium="klingon"), self.assertRaises(vt.TemplateError):
                builder(medium="klingon")
        for good in ("english", "sinhala", " English "):
            with self.subTest(medium=good):
                self.net(medium=good)

        for bad in ("nope", 5, [["a"]], [[1, "x"]], [[("a", 2)]]):
            with self.subTest(ask=repr(bad)[:20]), self.assertRaises(vt.TemplateError):
                self.net(ask=bad)
        for name in ("title", "description"):
            for bad in (5, [], {}):
                with self.subTest(name=name, bad=repr(bad)[:10]), self.assertRaises(vt.TemplateError):
                    self.water(**{name: bad})


if __name__ == "__main__":
    unittest.main()
