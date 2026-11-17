"""G9 readiness — the taught 15-degree compass chain in build_construction.

L13 (Loci and Constructions) teaches 15 degrees explicitly (the 45-degree
method-II chain bisects 30 to 15, and the exercises ask for 15 and 75), so the
triangle steps accept it through a genuine double bisection; 165 degrees never
appears in the lesson and stays refused. All stems are SYNTHETIC English.
"""
import json
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt


def arcs_of(b):
    return [e for e in b.doc["elements"] if e["type"] == "arc"]


class G9Construction15Tests(unittest.TestCase):
    def test_sas_15_builds_with_double_bisection_work(self):
        b = vt.build_construction(
            figure_id="g9c15sas", step="triangle_sas", base_px=300,
            stem="AB is 8 units and CA is 12 units; the angle at A is 15 degrees.",
            sides={"AB": 8, "CA": 12}, angles={"A": 15})
        a, c = b.anchors["A"], b.anchors["C"]
        drawn = math.degrees(math.atan2(c[1] - a[1], c[0] - a[0]))
        self.assertAlmostEqual(abs(drawn), 15.0, places=2)

        base = vt.build_construction(
            figure_id="g9c30sas", step="triangle_sas", base_px=300,
            stem="AB is 8 units and CA is 12 units; the angle at A is 30 degrees.",
            sides={"AB": 8, "CA": 12}, angles={"A": 30})
        self.assertGreater(len(arcs_of(b)), len(arcs_of(base)))

    def test_asa_15_at_either_vertex(self):
        for angles, vertex in (({"A": 15, "B": 105}, "A"), ({"A": 105, "B": 15}, "B")):
            with self.subTest(vertex=vertex):
                b = vt.build_construction(
                    figure_id=f"g9c15asa{vertex}", step="triangle_asa", base_px=300,
                    stem="AB is 8 units; the angles are 15 and 105 degrees.",
                    sides={"AB": 8}, angles=angles)
                o = b.anchors[vertex]
                other = b.anchors["B" if vertex == "A" else "A"]
                c = b.anchors["C"]
                u = (other[0] - o[0], other[1] - o[1])
                v = (c[0] - o[0], c[1] - o[1])
                drawn = abs(math.degrees(math.atan2(
                    u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
                self.assertAlmostEqual(drawn, 15.0, places=2)

    def test_aas_derives_15_or_takes_it_given(self):
        b = vt.build_construction(
            figure_id="g9c15aas", step="triangle_aas", base_px=300,
            stem="AB is 8 units; the angles are 15 and 60 degrees.",
            sides={"AB": 8}, angles={"A": 15, "C": 60})
        self.assertIn("derive 180 - 15 - 60 = 105", b.claims)
        self.assertGreater(len(arcs_of(b)), 1)

    def test_15_stem_backed_claim_and_refusals(self):
        b = vt.build_construction(
            figure_id="g9c15sas", step="triangle_sas", base_px=300,
            stem="AB is 8 units and CA is 12 units; the angle at A is 15 degrees.",
            sides={"AB": 8, "CA": 12}, angles={"A": 15})
        self.assertIn("15-degree ray", b.claims)
        for angles in ({"A": 165}, {"A": 50}, {"A": 7.5}):
            with self.subTest(angles=angles), self.assertRaises(vt.TemplateError):
                vt.build_construction(
                    figure_id="g9cbad", step="triangle_sas", base_px=300,
                    stem="AB is 8 units and CA is 12 units; angle 50 degrees.",
                    sides={"AB": 8, "CA": 12}, angles=angles)

    def test_intermediate_rays_and_unique_15_arcs(self):
        for step, angles, sides, vertex, names in (
                ("triangle_sas", {"A": 15}, {"AB": 8, "CA": 12}, "A", ("D", "E")),
                ("triangle_asa", {"A": 15, "B": 60}, {"AB": 8}, "A", ("D", "E")),
                ("triangle_asa", {"A": 60, "B": 15}, {"AB": 8}, "B", ("F", "G")),
                ("triangle_aas", {"B": 60, "C": 105}, {"AB": 8}, "A", ("D", "E"))):
            with self.subTest(step=step, angles=angles):
                b = vt.build_construction(
                    figure_id="g9c15rays", step=step, base_px=300,
                    stem="Lengths 8 and 12 units; angles 15, 60 and 105 degrees.",
                    sides=sides, angles=angles)
                arcs = arcs_of(b)
                keys = [json.dumps({k: v for k, v in e.items() if k != "id"}, sort_keys=True)
                        for e in arcs]
                self.assertEqual(len(keys), len(set(keys)))
                if step == "triangle_sas":
                    self.assertEqual(len(arcs), 9)
                for theta, name in zip((60, 30), names):
                    ray = next(e for e in b.doc["elements"] if e.get("id") == f"work{vertex}{theta}")
                    self.assertEqual(ray["stroke"]["style"], "dashed")
                    o, tip = b.anchors[vertex], b.anchors[name]
                    d = math.degrees(math.atan2(tip[1] - o[1], tip[0] - o[0]))
                    self.assertAlmostEqual(d, -theta if vertex == "A" else 180 + theta - 360, delta=0.02)
                    self.assertIn(vertex + name, b.claims)
                    self.assertAlmostEqual(math.dist(o, tip), 42 if theta == 60 else 42 * math.sqrt(3), delta=0.02)

    def test_setup_has_no_intermediate_rays(self):
        b = vt.build_construction(
            figure_id="g9c15setup", step="triangle_sas", base_px=300, stage="setup",
            stem="AB is 8 units and CA is 12 units; angle A is 15 degrees.",
            sides={"AB": 8, "CA": 12}, angles={"A": 15})
        self.assertEqual(set(b.anchors), {"A", "B"})
        self.assertFalse(arcs_of(b))
        self.assertNotIn("15-degree ray", b.claims)

    def test_apex_15_does_not_claim_constructed_15_ray(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_construction(
                figure_id="g9capex15", step="triangle_aas", base_px=400,
                stem="AB is 8 units; angles B and C are 75 and 15 degrees.",
                sides={"AB": 8}, angles={"B": 75, "C": 15})
        from unittest.mock import patch
        with patch.object(vt.vc, "triangle_from_angles", return_value=(150, -200)), \
                patch.object(vt, "finish") as finish:
            vt.build_construction(
                figure_id="g9capex15", step="triangle_aas", base_px=400,
                stem="AB is 8 units; angles B and C are 75 and 15 degrees.",
                sides={"AB": 8}, angles={"B": 75, "C": 15})
        self.assertFalse(any("15-degree ray" in c[0] for c in finish.call_args.kwargs["claims"]))

    def test_numeric_guards_apply_to_15_paths(self):
        stem = "AB is 8 units and CA is 12 units; the angle at A is 15 degrees."
        for value in (True, float("nan"), float("inf"), "15"):
            with self.subTest(value=value), self.assertRaises(vt.TemplateError):
                vt.build_construction(
                    figure_id="g9cbad", step="triangle_sas", base_px=300,
                    stem=stem, sides={"AB": 8, "CA": 12}, angles={"A": value})
        with self.assertRaises(vt.TemplateError):
            vt.build_construction(
                figure_id="g9cbad", step="triangle_sas", base_px=300,
                stem="AB is 8 units and CA is 12 units; the angle at A is 30 degrees.",
                sides={"AB": 8, "CA": 12}, angles={"A": 15})


if __name__ == "__main__":
    unittest.main()
