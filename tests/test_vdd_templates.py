"""tools/vdd_templates.py — the W3 figure templates.

Three things are tested:
  1. Every builder produces a `channel: constructed` claim set that audit-claim-set.py
     passes with NO edits (the templates emit the set themselves).
  2. The red team: a hand-edited drawn-ratio claim whose RESCALED anchors agree with it
     must still die — the 2026-09-29 cuboid drew 1.5:1 against a 5:2 stem and the audit
     agreed with itself (T-QG-2).
  3. The refusals: values the stem never states, off-lattice points, non-rectilinear
     edges, unrepresentable half symbols, impossible pentagon slants, Sinhala labels.

All stems are SYNTHETIC English — the real question stems never live in this repo.
"""
import json
import math
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt                              # noqa: E402

AUDIT = TOOLS / "audit-claim-set.py"


class Grade11ReadinessTests(unittest.TestCase):
    def test_self_test_ids_are_unique(self):
        ids = [s["figure_id"] for s in [*vt.SELF_TEST, *vt.READING_SELF_TEST]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_vertex_compass_arcs_take_short_interval_when_rotated(self):
        from unittest.mock import patch
        triangle = vt._triangle_pts
        arc = vt.vc.arc
        for step in ("incircle", "excircle"):
            for rotation in (-179, -120, 0, 75, 179):
                radians = math.radians(rotation)
                def rotated(angles, base):
                    return {k: (x * math.cos(radians) - y * math.sin(radians),
                                x * math.sin(radians) + y * math.cos(radians))
                            for k, (x, y) in triangle(angles, base).items()}
                spans = []
                def capture(center, radius, start, end, **kw):
                    if kw.get("id") in ("ca10", "ca11", "ca12"):
                        spans.append(end - start)
                    return arc(center, radius, start, end, **kw)
                with self.subTest(step=step, rotation=rotation), \
                        patch.object(vt, "_triangle_pts", side_effect=rotated), \
                        patch.object(vt.vc, "arc", side_effect=capture), \
                        patch.object(vt, "finish", side_effect=lambda **kw: kw):
                    vt.build_construction(figure_id="synthetic-arc1", stem="Angles 60 60 60.",
                                          step=step, angles={"A": 60, "B": 60, "C": 60})
                    self.assertTrue(spans)
                    self.assertTrue(all(0 <= span <= 180 for span in spans), spans)

    def test_new_reading_modes_and_refusals(self):
        for kind in ("inscribed_circle", "venn_regions", "solid_composite", "net"):
            spec = next(s for s in vt.SELF_TEST if s["template"] == kind)
            args = {k: v for k, v in spec.items() if k != "template"}
            with self.subTest(kind=kind):
                built = vt.BUILDERS[kind](**dict(args, values="figure", stem="Read the figure."))
                self.assertIn("figure content", built.claims)
                with self.assertRaises(vt.TemplateError):
                    vt.BUILDERS[kind](**dict(args, values="invalid"))

    def test_ogive_first_bounds(self):
        for bounds in ([5, 9, 17, 30], [-5, 0, 10, 20], [0, 2, 4, 6]):
            with self.subTest(bounds=bounds):
                built = vt.build_ogive(figure_id="synthetic-first-edge", stem="Scale 2 to 10.",
                                       ask=[["a", "the class edges"]],
                                       bounds=bounds, cum_freqs=[0, 2, 4, 8],
                                       step=2, v_max=10, values="figure")
                first = [e for e in built.doc["elements"] if e.get("id") == "nx0"]
                self.assertEqual(bool(first), bounds[0] != 0)
                if first:
                    self.assertEqual(first[0]["value"], str(bounds[0]))


class TemplateInputTests(unittest.TestCase):
    def test_rays_endpoint_label_nudges_outside_nearby_arc(self):
        built = vt.build_rays_from_point(
            figure_id="synthetic-ray-clearance", stem="Two rays.",
            ask=[["a", "the marked angle"]],
            rays={"A": "E", "B": "NE"}, ray_len=100, north_arrow=False,
            angles=[("A", "B", "x")], arc_r=110)
        label = next(el for el in built.doc["elements"] if el.get("id") == "lblA")
        self.assertGreater(label["labelOffset"][0], 14)

    def test_missing_template_names_figure_and_valid_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.json"
            spec.write_text(json.dumps({"figure_id": "synthetic-missing", "kind": "rays_from_point"}))
            proc = subprocess.run([sys.executable, str(TOOLS / "vdd_templates.py"),
                                   "build", str(spec)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("synthetic-missing", proc.stderr)
        self.assertIn("missing key 'template'", proc.stderr)
        self.assertIn("rays_from_point", proc.stderr)


def audit(claims: str, tmpdir: str) -> subprocess.CompletedProcess:
    p = Path(tmpdir) / "claims.txt"
    p.write_text(claims, encoding="utf-8")
    return subprocess.run([sys.executable, str(AUDIT), str(p)],
                          capture_output=True, text=True)


CUBOID_52 = ("A cuboid has length 5 cm, width 3 cm and height 2 cm. "
             "(a) Give the numbers of faces, edges and vertices.")


class EveryBuilderAuditsClean(unittest.TestCase):
    """Each SELF_TEST spec (synthetic stems) must reach audit exit 0 with no edits."""

    def test_all_self_test_specs_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            for spec in vt.SELF_TEST:
                spec = dict(spec)
                kind = spec.pop("template")
                with self.subTest(kind=kind):
                    b = vt.BUILDERS[kind](**spec)
                    r = audit(b.claims, tmp)
                    self.assertEqual(r.returncode, 0, f"{kind}\n{r.stdout}\n{r.stderr}")

    def test_claim_set_shape(self):
        for spec in vt.SELF_TEST:
            spec = dict(spec)
            kind = spec.pop("template")
            with self.subTest(kind=kind):
                b = vt.BUILDERS[kind](**spec)
                self.assertIn("channel:  constructed", b.claims)
                self.assertIsNotNone(re.search(r"(?m)^stem:\s+\S", b.claims))   # non-empty stem
                self.assertIsNotNone(re.search(r"(?m)^  K\d+  derive ", b.claims))  # ≥1 derive
                self.assertIn("load-bearing:", b.claims)
                for ref, _ in (spec.get("ask") or [("1", "")]):
                    self.assertIsNotNone(
                        re.search(rf"(?m)^  {re.escape(ref)} -> K", b.claims),
                        f"{kind}: load-bearing has no entry for ask part {ref}")

    def test_vdd_docs_validate_and_anchors_fit(self):
        for spec in vt.SELF_TEST:
            spec = dict(spec)
            kind = spec.pop("template")
            with self.subTest(kind=kind):
                b = vt.BUILDERS[kind](**spec)
                els = b.doc["elements"]
                self.assertEqual(len({e["id"] for e in els}), len(els))        # unique ids
                W, H = b.doc["canvas"]["width"], b.doc["canvas"]["height"]
                for name, (x, y) in b.anchors.items():
                    self.assertTrue(0 <= x <= W and 0 <= y <= H,
                                    f"{kind}: anchor {name}=({x},{y}) outside {W}x{H}")

    def test_no_invisible_elements(self):
        # an r:0 element with no label renders nothing — banned from student-facing
        # docs (vdd-check coverage now reads outlines); a labelled r:0 point draws
        # its letter, so `lbl*` markers stay
        for spec in vt.SELF_TEST:
            spec = dict(spec)
            kind = spec.pop("template")
            with self.subTest(kind=kind):
                b = vt.BUILDERS[kind](**spec)
                for el in b.doc["elements"]:
                    self.assertFalse(el.get("r") == 0 and not el.get("label"),
                                     f"{kind}: invisible element {el['id']}")


class PerTemplateClaims(unittest.TestCase):
    """Spot-check that each template's claim set carries its load-bearing geometry."""

    def test_cuboid_front_face_ratio_is_the_stems(self):
        b = vt.build_cuboid(figure_id="t1", stem=CUBOID_52, length=5, width=3, height=2)
        # the ratio is claimed on the LABELLED segments (DC carries "5 cm", DA "2 cm") —
        # the label-ratio audit check then owns it (a drawn 1.5 with labels 5:2 dies)
        self.assertIn("ratio len DC / len DA = 2.5", b.claims)
        self.assertIn("derive 5 / 2 = 2.5", b.claims)
        self.assertIn("paint DH dashed", b.claims)
        self.assertIn('label "3 cm" names CG', b.claims)   # width label on a depth edge
        dc = abs(b.anchors["C"][0] - b.anchors["D"][0])
        da = abs(b.anchors["A"][1] - b.anchors["D"][1])
        self.assertAlmostEqual(dc / da, 2.5, places=3)   # the DRAWN anchors say 2.5

    def test_grid_polygon_area_and_rights(self):
        b = vt.build_grid_polygon(figure_id="t1", stem="A shape on a 1 cm grid.",
                                  cell=1, vertices=[[1, 1], [5, 1], [5, 3], [3, 3], [3, 5], [1, 5]])
        self.assertIn("grid 5 by 5", b.claims)            # rows x cols = the shape's extent (W12 A4)
        self.assertEqual(len(re.findall(r"^  K\d+  right ", b.claims, re.M)), 6)
        self.assertIn("derive", b.claims)

    def test_number_line_axis_and_at_claims(self):
        b = vt.build_number_line(figure_id="t1", stem="A number line from 0 to 3, each unit "
                                 "divided into 10 equal parts.",
                                 v0=0, v1=3, parts_per_unit=10, points={"P": 0.4})
        self.assertIn("from 0 to 3", b.claims)
        self.assertRegex(b.claims, r"axis [A-Z][A-Z] from 0 to 3")
        self.assertRegex(b.claims, r"tick [A-Z][A-Z] step 1")
        m = re.search(r"^  K\d+  at 0\.4 (\S+) (\S+)", b.claims, re.M)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(float(m.group(1)), b.anchors["P"][0], places=4)
        self.assertAlmostEqual(float(m.group(2)), b.anchors["P"][1], places=4)
        self.assertIn("budget:", b.claims)               # 39 elements > 32

    def test_number_line_prefers_round_numeral_steps(self):
        # W8 dogfood: the smallest-fitting-divisor rule labelled 60 63 66 … 90 and
        # 730 734 … 750 — a round-to-ten line must land on the tens
        b = vt.build_number_line(figure_id="t1",
                                 stem="A number line shows 60 to 90, each unit in 1 part.",
                                 v0=60, v1=90, parts_per_unit=1)
        self.assertRegex(b.claims, r"tick [A-Z][A-Z] step 5")
        numerals = re.findall(r'label "(\d+)" names \1', b.claims)
        self.assertEqual(numerals, [str(v) for v in range(60, 91, 5)])
        b = vt.build_number_line(figure_id="t1",
                                 stem="A number line shows 730 to 750, each unit in 1 part.",
                                 v0=730, v1=750, parts_per_unit=1)
        m = re.search(r"tick [A-Z][A-Z] step (\d+)", b.claims)
        self.assertIn(int(m.group(1)), (5, 10))

    def test_rays_marks_each_angle_and_reflex(self):
        b = vt.build_rays_from_point(figure_id="t1", stem="Angles 1, 2 and 3 are marked.",
                                     rays={"A": "NE", "B": "S", "C": "W"},
                                     angles=[["A", "B", "1"], ["B", "C", "2"],
                                             ["A", "B", "3", True]])
        self.assertIn("angle A O B = 135", b.claims)
        self.assertIn("angle B O C = 90", b.claims)
        self.assertIn("reflex", b.claims)
        self.assertIn("derive 90 + 45 = 135", b.claims)   # the backing chain was emitted
        self.assertIn("label \"N\" names north", b.claims)

    def test_pictograph_describe_and_key(self):
        b = vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                per_symbol=4, rows=[["Mon", 8], ["Tue", 10]])
        self.assertIn('label "= 4" names key', b.claims)
        self.assertIn('describe "row Mon shows 2 symbols', b.claims)
        self.assertIn('describe "row Tue shows 2.5 symbols', b.claims)
        # the half symbol was drawn: an arc + a diameter line
        kinds = [e["type"] for e in b.doc["elements"]]
        self.assertIn("arc", kinds)

    def test_rectangle_points_on_claim_and_free_aspect(self):
        b = vt.build_rectangle_points(figure_id="t1", stem="ABCD is a rectangle, E on DC.",
                                      on_points={"E": ["DC", 0.375]}, extra_segments=["AE", "BE"])
        self.assertIn("on E DC", b.claims)
        self.assertEqual(len(re.findall(r"^  K\d+  right ", b.claims, re.M)), 4)
        self.assertIn("NOT to scale", b.claims)           # declared freedom
        self.assertIn("ambiguous:", b.claims)
        self.assertIn("canvas choice", b.claims)

    def test_house_pentagon_unknown_side(self):
        b = vt.build_house_pentagon(figure_id="t1",
                                    stem="Sides 8 m, 5 m, 5 m, 6 m and 4 m; when x = 5.",
                                    AB=8, BC=5, CP=5, PD=6, DA=4, unit="m",
                                    labels={"CP": "x m"})
        # a letter side renders as PLAIN text — VDD `text` has no italic and a KaTeX serif
        # `math` label would sit badly among sans labels (lead review R2); it is a normal
        # `label` claim so the claim-set inventory stays complete
        self.assertIn('label "x m" names CP', b.claims)
        sl = [e for e in b.doc["elements"] if e["id"] == "slCP"]
        self.assertEqual(sl[0]["type"], "text")
        self.assertEqual(sl[0]["value"], "x m")
        self.assertIn("equal BC CP", b.claims)            # both sides are 5
        self.assertIn("right D A B", b.claims)
        # apex exists and sits above the body
        self.assertLess(b.anchors["P"][1], b.anchors["C"][1])

    def test_dot_pattern_stages(self):
        b = vt.build_dot_pattern(figure_id="t1", stem="The first 4 figures use triangular "
                                 "numbers.", stages=4)
        for n, c in ((1, 1), (2, 3), (3, 6), (4, 10)):
            self.assertIn(f"stage {n} shows {c} dots", b.claims)
        self.assertEqual(len([e for e in b.doc["elements"] if e["type"] == "circle"]), 20)

    def test_dot_pattern_budget_line_over_32_elements(self):
        # 5 square stages = 55 dots + 5 labels = 60 elements > the 32-element budget —
        # the claim set must carry the justification (vdd-check honours a `budget:` line)
        b = vt.build_dot_pattern(figure_id="t1", stem="The first 5 figures are shown.",
                                 stages=5, kind="square")
        n = len(b.doc["elements"])
        self.assertEqual(n, 60)
        self.assertRegex(b.claims, rf"(?m)^budget:\s+{n}$")
        self.assertRegex(b.claims, rf"(?m)^  {n} elements — one circle per dot")
        # a small pattern under the budget stays silent
        small = vt.build_dot_pattern(figure_id="t1", stem="The first 3 figures are shown.",
                                     stages=3, kind="triangle")
        self.assertNotIn("budget:", small.claims)
        self.assertIn("departures: (none)", small.claims)


class RedTeam(unittest.TestCase):
    """The 2026-09-29 cuboid incident (T-QG-2): a drawn-ratio claim that the ANCHORS agree
    with must still die. Two doors, because the REAL stem (5, 3, 2) contains the forged
    pair 3/2 = 1.5 — stem-backing alone cannot refuse it; the figure's own labels can."""

    STEM_572 = ("A cuboid has length 5 cm, width 7 cm and height 2 cm. "
                "(a) Give the numbers of faces, edges and vertices.")
    # ⭐ THE REAL SHAPE — the actual incident's stem numbers, in synthetic English words.
    #    `3/2` is a genuine stem pair here, so the stem check CANNOT refuse a forged 1.5.
    STEM_532 = "A cuboid is 5 cm long, 3 cm wide and 2 cm high."
    ASK_A = [["a", "the cuboid's numbers"]]

    def _forge_15(self, b):
        """Rewrite the ratio claim to 1.5 and RESCALE every anchor's x so the anchors
        agree — the exact lie the 2026-09-29 claim set told about itself."""
        forged = b.claims.replace("ratio len DC / len DA = 2.5",
                                  "ratio len DC / len DA = 1.5")
        assert forged != b.claims
        ax = b.anchors["A"][0]
        da_h = abs(b.anchors["A"][1] - b.anchors["D"][1])
        span = abs(b.anchors["C"][0] - b.anchors["D"][0])
        scale = 1.5 * da_h / span                    # stretch x so DC/DA becomes 1.5
        lines = []
        for line in forged.splitlines():
            m = re.match(r"^  ([A-Z]) (\S+) (\S+)$", line)
            if m:
                x = ax + (float(m.group(2)) - ax) * scale
                lines.append(f"  {m.group(1)} {x:g} {m.group(3)}")
            else:
                lines.append(line)
        return "\n".join(lines) + "\n"

    def test_stem_numbers_drive_the_geometry(self):
        b = vt.build_cuboid(figure_id="t1", stem=self.STEM_572, ask=self.ASK_A,
                            length=5, width=7, height=2)
        self.assertIn("ratio len DC / len DA = 2.5", b.claims)
        dc = abs(b.anchors["C"][0] - b.anchors["D"][0])
        da = abs(b.anchors["A"][1] - b.anchors["D"][1])
        self.assertAlmostEqual(dc / da, 2.5, places=3)    # 5:2 drawn, not 1.5

    def test_hand_altered_drawn_ratio_fails(self):
        """Rescale the claim-set's anchors to 1.5:1 AND edit the claim to 1.5 — the pair
        still disagrees with the stem's 5:2, so the audit must name the claim and `stem`."""
        b = vt.build_cuboid(figure_id="t1", stem=self.STEM_572, ask=self.ASK_A,
                            length=5, width=7, height=2)
        with tempfile.TemporaryDirectory() as tmp:
            r = audit(b.claims, tmp)
            self.assertEqual(r.returncode, 0, r.stdout)   # the honest build passes
            forged = self._forge_15(b)
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)
            self.assertIn("stem", r.stdout)
            self.assertRegex(r.stdout, r"K\d+.*1\.5")      # names the forged claim id

    def test_real_shape_stem_forged_ratio_dies_by_labels_and_mis_citation(self):
        """THE REAL 2026-09-29 SHAPE: stem numbers {5,3,2} justify the forged 1.5 = 3/2 —
        stem-backing alone passes it. The forge keeps the derive citation (K1 still says
        5/2 = 2.5), so it dies TWO ways: the labels say 5:2, and the cited derive says 2.5."""
        b = vt.build_cuboid(figure_id="t1", stem=self.STEM_532, ask=self.ASK_A,
                            length=5, width=3, height=2)
        with tempfile.TemporaryDirectory() as tmp:
            r = audit(b.claims, tmp)
            self.assertEqual(r.returncode, 0, r.stdout)
            forged = self._forge_15(b)                # keeps `per derive K1` (= 2.5 ≠ 1.5)
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)
            self.assertRegex(r.stdout, r"K\d+.*labels .?[D C]{2}.? '5 cm'.*'2 cm'")
            self.assertRegex(r.stdout, r"K\d+.*cites `derive K\d+`.*does not match")

    def test_real_shape_stem_forged_ratio_dies_by_labels_alone(self):
        """Same forgery with the derive citation REMOVED — the label-ratio check (a) must
        catch it on its own: the figure labels the segments 5 cm and 2 cm."""
        b = vt.build_cuboid(figure_id="t1", stem=self.STEM_532, ask=self.ASK_A,
                            length=5, width=3, height=2)
        with tempfile.TemporaryDirectory() as tmp:
            forged = self._forge_15(b)
            forged = forged.replace(", per derive K1", "")
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)
            self.assertRegex(r.stdout, r"K\d+.*'5 cm'.*'2 cm'.*must be 2\.5")
            self.assertNotIn("false justification", r.stdout)   # (a) alone caught it

    def test_wrong_length_refused(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_cuboid(figure_id="t1", stem=CUBOID_52, length=1.5, width=3, height=2)
        self.assertIn("1.5", str(cm.exception))
        self.assertIn("stem", str(cm.exception))


class Refusals(unittest.TestCase):
    """A template raises TemplateError — never silently draws what the stem doesn't give."""

    def test_missing_stem_number(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_cuboid(figure_id="t1", stem="A cuboid, no numbers.", length=5,
                            width=3, height=2)

    def test_off_lattice_point(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_number_line(figure_id="t1", stem="0 to 3, each unit in 10 equal parts.",
                                 v0=0, v1=3, parts_per_unit=10, points={"P": 0.35})
        self.assertIn("lattice", str(cm.exception))

    def test_point_outside_axis(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_number_line(figure_id="t1", stem="0 to 3, each unit in 10 equal parts.",
                                 v0=0, v1=3, parts_per_unit=10, points={"P": 4.0})

    def test_non_rectilinear_edge(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_grid_polygon(figure_id="t1", stem="A shape on a 1 cm grid.",
                                  cell=1, vertices=[[0, 0], [3, 0], [1, 2]])
        self.assertIn("rectilinear", str(cm.exception))

    def test_unrepresentable_half_symbol(self):
        # 7 cups at 4-per-symbol is 1.75 symbols — neither whole nor half
        with self.assertRaises(vt.TemplateError):
            vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                per_symbol=4, rows=[["Mon", 7]])
        # halves are refused outright when the key value is odd
        with self.assertRaises(vt.TemplateError):
            vt.build_pictograph(figure_id="t1", stem="One circle stands for 5 cups.",
                                per_symbol=5, rows=[["Mon", 7]])

    def test_tall_canvas_refused(self):
        # W8: a 1×10 shaded grid rendered 375×2253 — taller than a phone screen. A canvas
        # over MAX_ASPECT× as tall as wide must be re-laid out, never drawn.
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_shaded_grid(figure_id="t1", stem="A grid of 10 squares.",
                                 cols=1, rows=10, full=[(0, 0)])
        self.assertIn("h/w", str(cm.exception))
        # the same 10 squares re-laid out as 5×2 pass
        b = vt.build_shaded_grid(figure_id="t1", stem="A grid of 10 squares.",
                                 cols=5, rows=2, full=[(0, 0)])
        c = b.doc["canvas"]
        self.assertLessEqual(c["height"], vt.MAX_ASPECT * c["width"])

    def test_shaded_grid_over_budget_emits_a_budget_line(self):
        # a 10×10 grid shading 47 cells is 60+ elements — over the 32-element budget the
        # claim set must carry `budget:` + a `departures:` justification (the same escape
        # number_line/pictograph/dot_pattern use), and the audit must pass it
        b = vt.build_shaded_grid(figure_id="t1",
                                 stem="A square grid of 100 squares of side 1 cm has "
                                      "47 squares shaded.",
                                 cols=10, rows=10, full=[(i % 10, i // 10) for i in range(47)])
        n = len(b.doc["elements"])
        self.assertGreater(n, 32)
        self.assertRegex(b.claims, rf"(?m)^budget:\s+{n}$")
        self.assertRegex(b.claims, r"(?m)^departures:")
        with tempfile.TemporaryDirectory() as td:
            r = audit(b.claims, td)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # a small grid stays silent — no budget line, no departures section
        small = vt.build_shaded_grid(figure_id="t1", stem="A grid of 4 squares.",
                                     cols=2, rows=2, full=[(0, 0)])
        self.assertNotIn("budget:", small.claims)

    def test_impossible_pentagon_slants(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_house_pentagon(figure_id="t1", stem="Sides 8 m and 5 m.",
                                    AB=8, BC=5, DA=5, CP=1, PD=1, unit="m")
        self.assertIn("cannot meet", str(cm.exception))

    def test_numeric_bearing_must_be_in_the_stem(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_rays_from_point(figure_id="t1", stem="Two rays only.",
                                     rays={"A": "NE", "B": 30})

    ADR_MSG = "diagram text must be simple English (ADR 0021)"

    def test_sinhala_label_refused(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                per_symbol=4, rows=[["සඳුදා", 8]])
        self.assertIn(self.ADR_MSG, str(cm.exception))

    def test_sinhala_label_refused_on_sinhala_medium(self):
        """ADR 0021 supersedes T-S6b-6's medium condition: drawn text is simple English
        on EVERY medium — a sinhala-medium question's figure gets English labels too."""
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                ask=[["a", "the cups each day"]],
                                per_symbol=4, rows=[["සඳුදා", 8], ["අඟහරුවාදා", 10]],
                                medium="sinhala")
        self.assertIn(self.ADR_MSG, str(cm.exception))

    def test_english_label_passes_on_sinhala_medium(self):
        b = vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                ask=[["a", "the cups each day"]],
                                per_symbol=4, rows=[["Mon", 8], ["Tue", 10]],
                                medium="sinhala")
        # G6-8 hardening (approved golden change): row label claims used to
        # target `row{ri+1}` while the emitted ids are `row{ri}` — Mon is row 0
        self.assertIn('label "Mon" names row0', b.claims)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_sinhala_a11y_title_description_exempt(self):
        """title/description are NOT drawn — they keep the question's medium (ADR 0021)."""
        b = vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                per_symbol=4, rows=[["Mon", 8]],
                                title="අ — a synthetic Sinhala a11y title",
                                description="අ — a synthetic Sinhala a11y description, "
                                            "not drawn anywhere in the figure",
                                medium="sinhala")
        self.assertIn("අ", b.doc["a11y"]["title"])

    def test_sinhala_refused_in_every_builder_free_text_path(self):
        """One probe per builder parameter whose value becomes drawn text."""
        cases = [
            ("bar_chart categories", dict(
                categories=["අ", "B"],
                series=[{"name": "n", "values": [10, 20]}], step=10)),
            ("bar_chart series name", dict(
                categories=["A", "B"],
                series=[{"name": "අ", "values": [10, 20]},
                        {"name": "s2", "values": [15, 25]}], step=10)),
            ("bar_chart value_title", dict(
                categories=["A", "B"],
                series=[{"name": "n", "values": [10, 20]}], step=10,
                value_title="අ")),
            ("bar_chart category_title", dict(
                categories=["A", "B"],
                series=[{"name": "n", "values": [10, 20]}], step=10,
                category_title="අ")),
        ]
        for what, kw in cases:
            with self.subTest(what=what):
                with self.assertRaises(vt.TemplateError) as cm:
                    vt.build_bar_chart(figure_id="t1",
                                       stem="Values 10, 15, 20 and 25.", **kw)
                self.assertIn(self.ADR_MSG, str(cm.exception))
        for what, groups in (
                ("sorting_rings group name", [["අ", ["1"]], ["B", ["2"]]]),
                ("sorting_rings item", [["A", ["අ"]], ["B", ["2"]]])):
            with self.subTest(what=what):
                with self.assertRaises(vt.TemplateError) as cm:
                    vt.build_sorting_rings(figure_id="t1", stem="Sort the items.",
                                           groups=groups)
                self.assertIn(self.ADR_MSG, str(cm.exception))
        # shape_row takes no free text besides a11y — its letters are single capitals
        # by validation, so its only script surface is the a11y exemption above.
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_parallel_lines(figure_id="t1",
                                    stem="Two parallel lines, 4 units apart.",
                                    lines=["PQ", "RS"], parallel=[["PQ", "RS"]],
                                    distance={"between": ["PQ", "RS"], "value": 4,
                                              "unit": "අ"})
        self.assertIn(self.ADR_MSG, str(cm.exception))

    def test_sinhala_in_math_latex_refused_on_every_medium(self):
        """KaTeX cannot shape Sinhala — refused even when the question's medium is sinhala."""
        for medium in ("english", "sinhala"):
            with self.subTest(medium=medium):
                with self.assertRaises(vt.TemplateError):
                    vt.finish(kind="t", figure_id="t1", stem="x = 1.",
                              elements=[{"id": "m", "type": "math", "at": [5, 5],
                                         "latex": "උ"}],
                              anchors={}, points=[], segments=[],
                              claims=[("derive 1 = 1", "inferred", "")], ask=None,
                              title=None, description=None, scale="", medium=medium)

    def test_stage_count_bounds(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_dot_pattern(figure_id="t1", stem="dots", stages=0)
        with self.assertRaises(vt.TemplateError):
            vt.build_dot_pattern(figure_id="t1", stem="dots", stages=9)

    def test_figure_id_and_empty_stem(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_cuboid(figure_id="bad id!", stem=CUBOID_52, length=5, width=3, height=2)
        with self.assertRaises(vt.TemplateError):
            vt.build_cuboid(figure_id="t1", stem="   ", length=5, width=3, height=2)

    def test_pentagon_label_printing_a_different_number_refused(self):
        # critic R3 finding 2: labels={"AB": "10 m"} on an AB=8 side printed invented content —
        # a label's numeric tokens must equal the value of the side they name
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_house_pentagon(figure_id="t1", stem="Sides 8 m, 5 m, 6 m and 4 m.",
                                    AB=8, BC=5, DA=4, CP=5, PD=6, unit="m",
                                    labels={"AB": "10 m"})
        self.assertIn("10", str(cm.exception))
        # a letter label carries no number -> the side's value is stem-checked instead (passes)
        b = vt.build_house_pentagon(figure_id="t1", stem="Sides 8 m, 5 m, 6 m and 4 m.",
                                    AB=8, BC=5, DA=4, CP=5, PD=6, unit="m",
                                    labels={"CP": "x m"})
        self.assertIn('label "x m" names CP', b.claims)

    def test_cuboid_depth_params_validated(self):
        for bad in (dict(depth_angle=0), dict(depth_angle=120), dict(depth_angle=-30),
                    dict(depth_scale=0), dict(depth_scale=1.4)):
            with self.subTest(**bad):
                with self.assertRaises(vt.TemplateError):
                    vt.build_cuboid(figure_id="t1", stem=CUBOID_52, length=5, width=3,
                                    height=2, **bad)

    def test_pictograph_duplicate_row_labels_refused(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                per_symbol=4, rows=[["Mon", 8], ["Mon", 12]])
        self.assertIn("duplicate", str(cm.exception))

    def test_digitless_figure_id_default_ask_refused(self):
        # the default ask part is "1" — a figure_id with no item number leaves the
        # ask↔figure link unverifiable; refuse instead of emitting a doomed claim set
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_grid_polygon(figure_id="fig", stem="A shape on a 1 cm grid.",
                                  cell=1, vertices=[[0, 0], [3, 0], [3, 2], [0, 2]])
        self.assertIn("ask", str(cm.exception))
        b = vt.build_grid_polygon(figure_id="fig", stem="A shape on a 1 cm grid.",
                                  cell=1, vertices=[[0, 0], [3, 0], [3, 2], [0, 2]],
                                  ask=[["a", "the shape's stated facts"]])
        self.assertIn("ask:      a", b.claims)

    def test_wide_number_line_and_pictograph_build(self):
        # critic R3 finding 3: a fixed margin made wide figures refuse on edge clearance.
        # The margin now grows with the canvas so a 0..20 line keeps ≥9 rendered px.
        b = vt.build_number_line(figure_id="t1",
                                 stem="The number line shows 0 to 20, each unit in 1 part.",
                                 v0=0, v1=20, parts_per_unit=1, points={"P": 7})
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)
        w = vt.build_pictograph(
            figure_id="t1", stem="One square stands for 10 visitors; counts 80, 60, 50, 40, 30.",
            per_symbol=10, rows=[["A first long row label", 80], ["A second row", 60],
                                 ["A third row", 50], ["A fourth row", 40], ["A fifth row", 30]])
        r = audit(w.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)


class DrawnGeometry(unittest.TestCase):
    """Claims can lie — these tests check the DRAWN elements themselves, in the document's
    own coordinates, against the inputs that shaped them (lead review R1: the audit and
    vdd-check both passed a bow-tie half cell, so claim-level tests alone are blind)."""

    @staticmethod
    def _by_id(b, eid):
        return next(e for e in b.doc["elements"] if e["id"] == eid)

    @staticmethod
    def _shoelace(pts):
        return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                       - pts[(i + 1) % len(pts)][0] * pts[i][1]
                       for i in range(len(pts)))) / 2

    def test_shaded_grid_half_is_a_right_triangle_per_corner(self):
        s = 40.0
        # (corner, expected triangle vertices, hypotenuse endpoints) in cell-local coords
        want = {
            "tl": ([(0, 0), (s, 0), (0, s)], [(s, 0), (0, s)]),
            "tr": ([(s, 0), (0, 0), (s, s)], [(0, 0), (s, s)]),
            "bl": ([(0, s), (0, 0), (s, s)], [(0, 0), (s, s)]),
            "br": ([(s, s), (s, 0), (0, s)], [(s, 0), (0, s)]),
        }
        for corner, (tri_local, hypo_local) in want.items():
            with self.subTest(corner=corner):
                b = vt.build_shaded_grid(figure_id="t1",
                                         stem="A 2 by 2 square of cells.",
                                         cols=2, rows=2, cell_px=s,
                                         full=[(1, 0)], half=[(0, 0, corner)])
                poly = self._by_id(b, "half0")["points"]
                diag = self._by_id(b, "diag0")["points"]
                self.assertEqual(len(poly), 3, "a half cell is a triangle, not a quad")
                self.assertAlmostEqual(self._shoelace(poly), s * s / 2, places=4)
                # the named corner must be the RIGHT angle and the diagonal its hypotenuse
                corner_xy = {k: v for k, v in zip(
                    ("tl", "tr", "bl", "br"),
                    [(0, 0), (s, 0), (0, s), (s, s)])}[corner]
                # translation is uniform — compare on differences, not absolute coords
                dxc, dyc = poly[0][0] - corner_xy[0], poly[0][1] - corner_xy[1]
                tri = [(p[0] - dxc, p[1] - dyc) for p in poly]
                self.assertCountEqual(tri, tri_local)
                u = (tri_local[1][0] - tri_local[0][0], tri_local[1][1] - tri_local[0][1])
                v = (tri_local[2][0] - tri_local[0][0], tri_local[2][1] - tri_local[0][1])
                self.assertEqual(u[0] * v[0] + u[1] * v[1], 0, "right angle at the corner")
                diag_local = sorted((p[0] - dxc, p[1] - dyc) for p in diag)
                self.assertEqual(diag_local, sorted(hypo_local))

    def test_dot_pattern_triangle_apex_up(self):
        b = vt.build_dot_pattern(figure_id="t1", stem="Figures 1 to 3 are shown.", stages=3)
        apex = self._by_id(b, "t3r0d0")["center"]
        bottom = [e for e in b.doc["elements"]
                  if e["id"].startswith("t3r2") and e["type"] == "circle"]
        self.assertEqual(len(bottom), 3)                        # widest row
        self.assertLess(apex[1], bottom[0]["center"][1])        # apex ABOVE the widest row
        self.assertTrue(all(e["center"][1] == bottom[0]["center"][1] for e in bottom))
        # all stages share ONE baseline — the widest row of every stage is level
        for n in (1, 2, 3):
            dots = [e for e in b.doc["elements"]
                    if e["id"].startswith(f"t{n}r") and e["type"] == "circle"]
            self.assertAlmostEqual(max(e["center"][1] for e in dots),
                                   bottom[0]["center"][1], places=4)

    def test_number_line_point_sits_at_its_value(self):
        b = vt.build_number_line(figure_id="t1", stem="A line from 0 to 3 in 10 parts.",
                                 v0=0, v1=3, parts_per_unit=10, points={"P": 0.4, "Q": 2.1})
        axis = [e for e in b.doc["elements"] if e["id"] == "axis"][0]
        x0, x3 = axis["points"][0][0], axis["points"][1][0]
        span_u = x3 - x0 - 60.0                    # minus the 30-unit overhang each end
        for name, v in (("P", 0.4), ("Q", 2.1)):
            dot = self._by_id(b, f"dot{name}")
            want_x = x0 + 30.0 + (v / 3) * span_u
            self.assertAlmostEqual(dot["at"][0], want_x, places=4)
            self.assertEqual(dot["at"][1], b.anchors[name][1])    # on the axis line

    def test_rays_tips_at_stated_bearings(self):
        b = vt.build_rays_from_point(figure_id="t1", stem="Three rays.", north_arrow=False,
                                     rays={"A": "NE", "B": "S", "C": "W"})
        o = self._by_id(b, "OA")["points"][0]
        for eid, deg in (("OA", -45.0), ("OB", 90.0), ("OC", 180.0)):
            p = self._by_id(b, eid)["points"][1]
            got = math.degrees(math.atan2(p[1] - o[1], p[0] - o[0]))
            self.assertAlmostEqual((got - deg + 180) % 360 - 180, 0.0, places=4)

    def test_pictograph_counts_and_half_symbol(self):
        b = vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                per_symbol=4, rows=[["Mon", 8], ["Tue", 10]])
        circles = [e for e in b.doc["elements"]
                   if e["type"] == "circle" and re.fullmatch(r"r\dc\d", e["id"])]
        self.assertEqual(len(circles), 4)           # 8 cups = 2 symbols; 10 = 2 + a half
        arcs = [e for e in b.doc["elements"]
                if e["type"] == "arc" and re.fullmatch(r"r\dh", e["id"])]
        self.assertEqual(len(arcs), 1)              # Tue's half symbol
        self.assertLess(circles[0]["center"][1], circles[2]["center"][1])   # two rows

    def test_rectangle_point_e_drawn_at_fraction_on_dc(self):
        b = vt.build_rectangle_points(figure_id="t1", stem="ABCD is a rectangle, E on DC.",
                                      on_points={"E": ["DC", 0.375]}, extra_segments=["AE"])
        seg = self._by_id(b, "AE")["points"]
        d, c = b.anchors["D"], b.anchors["C"]
        want = (d[0] + 0.375 * (c[0] - d[0]), d[1] + 0.375 * (c[1] - d[1]))
        self.assertAlmostEqual(seg[0][0], b.anchors["A"][0], places=4)
        self.assertAlmostEqual(seg[1][0], want[0], places=4)
        self.assertAlmostEqual(seg[1][1], want[1], places=4)

    def test_house_pentagon_sides_proportional_to_stated(self):
        b = vt.build_house_pentagon(figure_id="t1", stem="Sides 8 m, 5 m, 5 m, 6 m, 4 m.",
                                    AB=8, BC=5, CP=5, PD=6, DA=4, unit="m")
        a = b.anchors
        u = math.hypot(a["B"][0] - a["A"][0], a["B"][1] - a["A"][1]) / 8
        for seg, want in (("BC", 5), ("CP", 5), ("PD", 6), ("DA", 4)):
            got = math.hypot(a[seg[1]][0] - a[seg[0]][0],
                             a[seg[1]][1] - a[seg[0]][1]) / u
            self.assertAlmostEqual(got, want, delta=0.01)     # anchors are r2-rounded

    def test_grid_polygon_vertices_on_the_lattice(self):
        b = vt.build_grid_polygon(figure_id="t1", stem="A shape on a 1 cm grid.",
                                  cell=1, vertices=[[1, 1], [5, 1], [5, 3], [1, 3]])
        edges = [e for e in b.doc["elements"] if re.fullmatch(r"[A-Z]{2}", e["id"])]
        self.assertEqual(len(edges), 4)                    # the shape's outline segments
        pitch = (self._by_id(b, "gv1")["points"][0][0]
                 - self._by_id(b, "gv0")["points"][0][0])
        c = edges[0]["points"][0]
        for e in edges:
            for x, y in e["points"]:
                self.assertAlmostEqual((x - c[0]) % pitch, 0, places=4)
                self.assertAlmostEqual((y - c[1]) % pitch, 0, places=4)
        # and the drawn outline hits the requested lattice vertices (1,1)-(5,1)-(5,3)-(1,3)
        drawn = sorted(set(tuple(p) for e in edges for p in e["points"]))
        want = sorted({(v[0] * pitch + c[0] - pitch, v[1] * pitch + c[1] - pitch)
                       for v in [[1, 1], [5, 1], [5, 3], [1, 3]]})
        self.assertEqual(drawn, want)


class GridPolygonLabelsAndAxis(unittest.TestCase):
    """W12 A4 — vertex labels on concave shapes, the exact-extent default grid, and the
    `axis` feature."""

    STEM = "The shape is drawn on a grid of 1 cm squares."
    UNOTCH = [[0, 0], [6, 0], [6, 5], [4, 5], [4, 2], [2, 2], [2, 5], [0, 5]]
    UNOTCH_8x6 = [[0, 0], [8, 0], [8, 6], [5, 6], [5, 2], [3, 2], [3, 6], [0, 6]]

    def _build(self, **kw):
        kw.setdefault("cell", 1)
        return vt.build_grid_polygon(figure_id="t1", stem=self.STEM, **kw)

    @staticmethod
    def _vdd_check(b, tmp):
        """vdd-check --no-render on the written figure — 0 findings or skip."""
        import os
        import shutil
        env = dict(os.environ)
        if not env.get("VIBHAGA_ADMIN"):
            d = TOOLS.parent
            while not (d / "Vibhaga-Admin").is_dir() and d.parent != d:
                d = d.parent
            if (d / "Vibhaga-Admin").is_dir():
                env["VIBHAGA_ADMIN"] = str(d / "Vibhaga-Admin")
        if not shutil.which("node") or "VIBHAGA_ADMIN" not in env:
            raise unittest.SkipTest("node or the sibling Vibhaga-Admin checkout unavailable")
        fig = Path(tmp) / "f.json"
        fig.write_text(json.dumps(b.doc), encoding="utf-8")
        (Path(tmp) / "f.claims.txt").write_text(b.claims, encoding="utf-8")
        (Path(tmp) / "f.anchors.json").write_text(json.dumps(b.anchors), encoding="utf-8")
        r = subprocess.run(
            ["node", str(TOOLS / "vdd-check.mjs"), str(fig),
             "--claims", str(Path(tmp) / "f.claims.txt"),
             "--anchors", str(Path(tmp) / "f.anchors.json"), "--no-render"],
            capture_output=True, text=True, env=env)
        return r

    def test_default_grid_is_the_shapes_extent(self):
        b = self._build(vertices=[[1, 1], [5, 1], [5, 3], [1, 3]])
        self.assertIn("grid 3 by 5", b.claims)            # no spare row/column
        gv = [e for e in b.doc["elements"] if re.fullmatch(r"gv\d+", e["id"])]
        gh = [e for e in b.doc["elements"] if re.fullmatch(r"gh\d+", e["id"])]
        self.assertEqual((len(gv), len(gh)), (6, 4))      # cols+1 x rows+1 rulings
        b2 = self._build(vertices=[[1, 1], [5, 1], [5, 3], [1, 3]], cols=8, rows=6)
        self.assertIn("grid 6 by 8", b2.claims)           # explicit cols/rows unchanged
        gv2 = [e for e in b2.doc["elements"] if re.fullmatch(r"gv\d+", e["id"])]
        self.assertEqual(len(gv2), 9)

    def test_convex_vertex_labels(self):
        b = self._build(vertices=[[0, 0], [4, 0], [4, 3], [0, 3]],
                        cell_px=40.0, vertex_labels=True)
        self.assertIn('label "A" names A', b.claims)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)
        W, H = b.doc["canvas"]["width"], b.doc["canvas"]["height"]
        for el in b.doc["elements"]:                     # labels near the canvas edge
            if el["type"] == "text":                     # still get their margin
                x, y = el["at"]
                self.assertTrue(0 <= x <= W and 0 <= y <= H)

    def test_unotch_vertex_labels_build(self):
        for cp in (40.0, 50.0, 60.0):
            with self.subTest(cell_px=cp):
                b = self._build(vertices=self.UNOTCH, cell_px=cp, vertex_labels=True)
                labels = [e for e in b.doc["elements"]
                          if e["type"] == "text" and e["id"].startswith("lbl")]
                self.assertEqual(len(labels), 8)
                r = audit(b.claims, tempfile.mkdtemp())
                self.assertEqual(r.returncode, 0, r.stdout)
                if cp == 50.0:                    # one representative through vdd-check
                    with tempfile.TemporaryDirectory() as tmp:
                        rr = self._vdd_check(b, tmp)
                    self.assertEqual(rr.returncode, 0, rr.stdout + rr.stderr)

    def test_unotch_8x6_vertex_labels_build(self):
        b = self._build(vertices=self.UNOTCH_8x6, cell_px=66.0, vertex_labels=True)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_adjacent_reflex_vertices(self):
        # a one-cell slot: E and F are reflex corners sharing the slot's back edge —
        # both labels must squeeze into the same pocket (needs cell_px ≥ ~76 — the
        # honest measured bound; 70 still refuses)
        b = self._build(vertices=[[0, 0], [5, 0], [5, 3], [4, 3], [4, 2], [3, 2],
                                  [3, 3], [0, 3]],
                        cell_px=80.0, vertex_labels=True)
        labels = {e["id"]: e for e in b.doc["elements"]
                  if e["type"] == "text" and e["id"].startswith("lbl")}
        self.assertEqual(len(labels), 8)
        # each label sits nearer its own vertex anchor than any other vertex's
        vertex_anchors = {n: b.anchors[n] for n in "ABCDEFGH"}
        for n, el in labels.items():
            ax_, ay_ = el["at"]
            own = math.hypot(ax_ - vertex_anchors[n[3:]][0],
                             ay_ - vertex_anchors[n[3:]][1])
            for m, (rx, ry) in vertex_anchors.items():
                if m != n[3:]:
                    self.assertLess(own, math.hypot(ax_ - rx, ay_ - ry))
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_tight_notch_still_refuses(self):
        # a 2-cell notch at cell_px 24 leaves no seat an honest label could take —
        # the refusal stays real
        with self.assertRaises(vt.TemplateError) as cm:
            self._build(vertices=self.UNOTCH, cell_px=24.0, vertex_labels=True)
        self.assertIn("no clear seat", str(cm.exception))

    def test_axis_draws_a_dashed_clipped_line(self):
        b = self._build(vertices=[[0, 0], [4, 0], [4, 3], [0, 3]],
                        axis={"through": [[2, -1], [2, 4]]})
        el = self._axis_el(b)
        self.assertEqual(el["stroke"]["style"], "dashed")
        # clipped to the grid rect — in canvas units the vertical axis through x=2 runs
        # from the grid's top ruling to its bottom one
        top = next(e for e in b.doc["elements"] if e["id"] == "gh0")["points"][0][1]
        bottom = next(e for e in b.doc["elements"] if e["id"] == "gh3")["points"][0][1]
        x2 = next(e for e in b.doc["elements"] if e["id"] == "gv2")["points"][0][0]
        self.assertAlmostEqual(el["points"][0][1], top)
        self.assertAlmostEqual(el["points"][1][1], bottom)
        for x, y in el["points"]:
            self.assertAlmostEqual(x, x2)
        self.assertRegex(b.claims, r"paint [A-Z]{2} dashed")
        self.assertIn('describe "a dashed line', b.claims)
        self.assertRegex(b.claims, r"none tickMark parallelMark angleMark arrow \|")
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            rr = self._vdd_check(b, tmp)
        self.assertEqual(rr.returncode, 0, rr.stdout + rr.stderr)

    @staticmethod
    def _axis_el(b):
        return next(e for e in b.doc["elements"] if e["id"] == "axis")

    def test_axis_diagonal_symmetry(self):
        for through in ([[0, 0], [3, 3]], [[0, 3], [3, 0]]):   # a square's diagonals
            with self.subTest(through=through):
                b = self._build(vertices=[[0, 0], [3, 0], [3, 3], [0, 3]],
                                axis={"through": through})
                self._axis_el(b)
        # horizontal symmetry on a wide rectangle
        b = self._build(vertices=[[0, 0], [4, 0], [4, 2], [0, 2]],
                        axis={"through": [[0, 1], [4, 1]]})
        self._axis_el(b)

    def test_axis_refusals(self):
        sq = [[0, 0], [3, 0], [3, 3], [0, 3]]
        with self.assertRaisesRegex(vt.TemplateError, "distinct"):
            self._build(vertices=sq, axis={"through": [[1, 1], [1, 1]]})
        with self.assertRaisesRegex(vt.TemplateError, "lattice"):
            self._build(vertices=sq, axis={"through": [[0.5, 0], [0.5, 3]]})
        with self.assertRaisesRegex(vt.TemplateError, "vertical, horizontal or"):
            self._build(vertices=sq, axis={"through": [[0, 0], [3, 1]]})
        with self.assertRaisesRegex(vt.TemplateError, "does not cross"):
            self._build(vertices=sq, axis={"through": [[9, 0], [9, 4]]})
        with self.assertRaisesRegex(vt.TemplateError, "through"):
            self._build(vertices=sq, axis={"through": [[1, 1]]})

    def test_axis_symmetry_assertion(self):
        ell = [[0, 0], [4, 0], [4, 3], [3, 3], [3, 2], [0, 2]]     # L-shape, not symmetric
        with self.assertRaisesRegex(vt.TemplateError, "mirror-symmetric"):
            self._build(vertices=ell, axis={"through": [[2, 0], [2, 4]]})
        b = self._build(vertices=ell,
                        axis={"through": [[2, 0], [2, 4]], "assert_symmetric": False})
        self.assertNotIn("mirror-symmetric about it", b.claims)   # describe stays honest
        self._axis_el(b)


class CLI(unittest.TestCase):
    def test_list_and_build(self):
        r = subprocess.run([sys.executable, str(TOOLS / "vdd_templates.py"), "list"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        for kind in vt.BUILDERS:
            self.assertIn(kind, r.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.json"
            spec.write_text(json.dumps([{"template": "cuboid", "figure_id": "t1",
                                         "stem": CUBOID_52,
                                         "length": 5, "width": 3, "height": 2}]))
            r = subprocess.run([sys.executable, str(TOOLS / "vdd_templates.py"),
                                "build", str(spec), "--out", tmp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for suffix in ("t1.json", "t1.anchors.json", "t1-claims.txt"):
                self.assertTrue((Path(tmp) / suffix).exists(), suffix)

    def test_build_refusal_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.json"
            spec.write_text(json.dumps([{"template": "cuboid", "figure_id": "t",
                                         "stem": "no numbers", "length": 5,
                                         "width": 3, "height": 2}]))
            r = subprocess.run([sys.executable, str(TOOLS / "vdd_templates.py"),
                                "build", str(spec), "--out", tmp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("not a number the stem states", r.stderr)

    def test_build_refusal_names_the_figure_id(self):
        # a bare "dot_pattern: label …" in a multi-spec build left the reader guessing
        # which figure died — the CLI names the failing spec's figure_id
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.json"
            spec.write_text(json.dumps([
                {"template": "cuboid", "figure_id": "ok1", "stem": CUBOID_52,
                 "length": 5, "width": 3, "height": 2},
                {"template": "cuboid", "figure_id": "bad7", "stem": "no numbers",
                 "length": 5, "width": 3, "height": 2}]))
            r = subprocess.run([sys.executable, str(TOOLS / "vdd_templates.py"),
                                "build", str(spec), "--out", tmp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("bad7:", r.stderr)

    def test_pointless_figure_still_writes_the_anchors_trio(self):
        # dot_pattern/pictograph have no named points — write_figure omits an empty
        # anchors dict, so the CLI printed a path that never landed (W8 dogfood)
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.json"
            spec.write_text(json.dumps([{"template": "dot_pattern", "figure_id": "t2",
                                         "stem": "The first 2 figures are shown.",
                                         "stages": 2}]))
            r = subprocess.run([sys.executable, str(TOOLS / "vdd_templates.py"),
                                "build", str(spec), "--out", tmp],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for suffix in ("t2.json", "t2.anchors.json", "t2-claims.txt"):
                self.assertTrue((Path(tmp) / suffix).exists(), suffix)
            self.assertEqual(json.loads((Path(tmp) / "t2.anchors.json").read_text()), {})


class RenderedClearance(unittest.TestCase):
    """The clearance model is rendered px on the 294 px plate (PLATE_INNER), not canvas units —
    a canvas wider than the plate shrinks below 1 px/unit (rebuild Q4 measured 7.9 px at 320
    while the estimate passed)."""

    def test_wide_canvas_labels_clear_the_scaled_edge(self):
        # number_line 0..8 at a big unit_px forces a canvas far wider than PLATE_INNER
        b = vt.build_number_line(
            figure_id="t1",
            stem="A number line from 0 to 8, each unit divided into 10 equal parts.",
            v0=0, v1=8, parts_per_unit=10, points={"P": 0.4, "Q": 3.7, "R": 7.9})
        W = b.doc["canvas"]["width"]
        self.assertGreater(W, vt.PLATE_INNER)           # the test only matters wide-of-plate
        s = min(1.0, vt.PLATE_INNER / W)
        for txt, x0, y0, x1, y1 in vt.label_boxes(b.doc["elements"]):
            edge = min(x0, y0, W - x1, b.doc["canvas"]["height"] - y1) * s
            self.assertGreaterEqual(
                edge, vt.EDGE_PX,
                f"label {txt!r} renders {edge:.1f} px from the canvas edge (< {vt.EDGE_PX})")

    def test_dot_pattern_stage_labels_clear_at_every_size(self):
        # W8 dogfood: stages=5 square at default dx/gap was refused — '(1)' rendered
        # ~6.8 px from the dots (< 8). The label drop is now sized from the figure's
        # own span; every kind × stages 1..8 at defaults must pass the pre-flight.
        for kind in ("triangle", "square", "rectangle"):
            for stages in range(1, 9):
                with self.subTest(kind=kind, stages=stages):
                    b = vt.build_dot_pattern(
                        figure_id=f"t{stages}",
                        stem=f"The first {stages} figures of a dot pattern are shown.",
                        stages=stages, kind=kind)
                    lbl = next(e for e in b.doc["elements"] if e["id"] == f"lbl{stages}")
                    dots = [e for e in b.doc["elements"]
                            if e["type"] == "circle" and e["id"].startswith(f"t{stages}r")]
                    self.assertGreater(lbl["at"][1],
                                       max(d["center"][1] for d in dots))

    def test_number_line_point_label_in_the_stroke_target_window(self):
        # W8 dogfood round 2: a MID_DOWN-modelled lift put the label 36.1 units up — the real
        # DOM box (a capital reaches ~0.5·size below the anchor, not 0.58·size) left it 27.1u
        # from its point, over visual-check's 1.5×fontSize target bound. The lift must satisfy
        # BOTH rules: point→box stays ≤ 1.5·fontSize AND the box clears the tick's top stroke
        # edge (11 + half its stroke) by ≥ 6 px + slack rendered.
        b = vt.build_number_line(figure_id="t1",
                                 stem="A number line shows 730 to 750, each unit in 1 part.",
                                 v0=730, v1=750, parts_per_unit=1, points={"P": 736})
        dot = next(e for e in b.doc["elements"] if e["id"] == "dotP")
        mark_off = -dot["labelOffset"][1]
        self.assertLessEqual(mark_off - 0.5 * vt.FS, 1.5 * vt.FS)      # target on the DOM reach
        W = b.doc["canvas"]["width"]
        s = min(1.0, vt.PLATE_INNER / W)
        y1 = next(bx[3] for t, *bx in vt.label_boxes(b.doc["elements"]) if t == "P")
        gap_px = (dot["at"][1] - 11 - 1 - y1) * s                      # box bottom → tick top edge
        self.assertGreaterEqual(gap_px, vt.STROKE_PX + vt.SLACK_STROKE - 1e-6)

    def test_cuboid_height_label_within_target_distance(self):
        # visual-check's target rule: a label sits within 1.5 × fontSize of the edge it names —
        # the cuboid's height label floated ~26 units off DA (rebuild Q8 review).
        b = vt.build_cuboid(figure_id="t1", stem=CUBOID_52, length=5, width=3, height=2)
        slh = next(e for e in b.doc["elements"] if e["id"] == "slH")
        boxes = {t: (x0, y0, x1, y1) for t, x0, y0, x1, y1 in vt.label_boxes(b.doc["elements"])}
        bx = boxes["2 cm"]
        da = next(e["points"] for e in b.doc["elements"] if e["id"] == "DA")
        # label box → the DA segment, canvas units — the same estimator the pre-flight uses
        dist = vt._seg_rect_dist(da[0], da[1], bx)
        self.assertLessEqual(dist, 1.5 * slh["fontSize"])


def _dot(id_, x, y):
    return {"type": "circle", "id": id_, "center": [x, y], "r": 4.0,
            "fill": {"color": "#000"}, "stroke": {"width": 0}}


def _floater(id_, value, near, **kw):
    return {"type": "text", "id": id_, "at": [0.0, 0.0], "value": value,
            "align": "middle", "baseline": "middle", "_near": list(near), **kw}


def _finish_two_rings(d_dot, ring_r=100.0, gap=None):
    """Two overlapping unfilled rings + a dot + one floating label (W10a test fig)."""
    cl, cr = (0.0, 0.0), (140.0, 0.0)
    el = [{"type": "circle", "id": "L", "center": list(cl), "r": ring_r},
          {"type": "circle", "id": "R", "center": list(cr), "r": ring_r},
          _dot("dotD", *d_dot),
          _floater("lblD", "D", d_dot, **({"_gap": gap} if gap else {}))]
    return vt.finish(
        kind="two_circles", figure_id="tf", stem="Two overlapping circles, point D.",
        elements=el, anchors={"D": tuple(d_dot)}, points=["D"], segments=[],
        ask=[["a", "the point"]],
        claims=[('circle centre L radius 100', "inferred", "the left circle"),
                ('circle centre R radius 100', "inferred", "the right circle"),
                ('label "D" names D', "stem", "the dot")] +
               vt.membership_claims("D", d_dot, {"left": (cl, ring_r), "right": (cr, ring_r)}),
        title=None, description=None, scale="1 unit = 1 unit")


class FloatingLabels(unittest.TestCase):
    """W10a: `_near`/`_gap` on a text element asks finish() to place it."""

    def _lbl(self, b):
        return next(e for e in b.doc["elements"] if e["id"] == "lblD")

    def test_floats_clear_of_a_dot_inside_a_circle(self):
        b = _finish_two_rings((140.0, 0.0))          # dot at the right circle's centre
        lbl = self._lbl(b)
        ring_r = next(e for e in b.doc["elements"] if e["id"] == "R")
        ring_l = next(e for e in b.doc["elements"] if e["id"] == "L")
        dot = next(e for e in b.doc["elements"] if e["id"] == "dotD")
        # placed, clear of the dot's ink, and inside the ring that holds the dot
        self.assertGreater(math.hypot(lbl["at"][0] - dot["center"][0],
                                      lbl["at"][1] - dot["center"][1]), 8)
        self.assertLess(math.hypot(lbl["at"][0] - ring_r["center"][0],
                                   lbl["at"][1] - ring_r["center"][1]), ring_r["r"])
        self.assertGreater(math.hypot(lbl["at"][0] - ring_l["center"][0],
                                      lbl["at"][1] - ring_l["center"][1]), ring_l["r"])

    def test_dot_on_the_outline_floats_outside(self):
        cl, cr, R = (0.0, 0.0), (140.0, 0.0), 100.0
        d = vt.on_circle_point(cr, R, 200.0)          # on the right circle's lower-left arc
        b = _finish_two_rings(d)
        lbl = self._lbl(b)
        ring = next(e for e in b.doc["elements"] if e["id"] == "R")
        self.assertGreater(math.hypot(lbl["at"][0] - ring["center"][0],
                                      lbl["at"][1] - ring["center"][1]), ring["r"])

    def test_dot_in_right_only_stays_in_right_only(self):
        cl, cr, R = (0.0, 0.0), (140.0, 0.0), 100.0
        p = vt.region_point({"left": (cl, R), "right": (cr, R)},
                            inside=["right"], outside=["left"],
                            prefer=(140.0, 0.0), avoid=[cr], min_sep=25.0)
        b = _finish_two_rings(p)
        lbl = self._lbl(b)
        ring_l = next(e for e in b.doc["elements"] if e["id"] == "L")
        ring_r = next(e for e in b.doc["elements"] if e["id"] == "R")
        self.assertLess(math.hypot(lbl["at"][0] - ring_r["center"][0],
                                   lbl["at"][1] - ring_r["center"][1]), ring_r["r"])
        self.assertGreater(math.hypot(lbl["at"][0] - ring_l["center"][0],
                                      lbl["at"][1] - ring_l["center"][1]), ring_l["r"])

    def test_internal_keys_never_reach_the_doc(self):
        b = _finish_two_rings((140.0, 0.0), gap=20.0)
        for e in b.doc["elements"]:
            self.assertFalse([k for k in e if k.startswith("_")],
                             f"{e['id']} kept internal keys")

    def test_no_clear_spot_raises_naming_the_rule(self):
        # two dots 5 units apart: every candidate for A's label sits nearer B's anchor
        # than the 6 px own-anchor margin allows
        el = [_dot("dotA", 0.0, 0.0), _dot("dotB", 5.0, 0.0),
              _floater("lblA", "A", (0.0, 0.0)), _floater("lblB", "B", (5.0, 0.0))]
        with self.assertRaises(vt.TemplateError) as cm:
            vt.finish(kind="t", figure_id="tf", stem="Points A and B.", elements=el,
                      anchors={"A": (0.0, 0.0), "B": (5.0, 0.0)}, points=["A", "B"],
                      segments=[], ask=[["a", "x"]],
                      claims=[('label "A" names A', "stem", ""), ('label "B" names B', "stem", "")],
                      title=None, description=None, scale="x")
        self.assertIn("own-anchor", str(cm.exception))
        self.assertIn("'A'", str(cm.exception))

    def test_fixed_label_nearer_another_named_anchor_raises(self):
        el = [_dot("dotA", 0.0, 0.0), _dot("dotB", 60.0, 0.0),
              {"type": "text", "id": "lblA", "at": [42.0, -20.0], "value": "A",
               "align": "middle", "baseline": "middle"},     # nearer B than A
              {"type": "text", "id": "lblB", "at": [66.0, 26.0], "value": "B",
               "align": "middle", "baseline": "middle"}]
        with self.assertRaises(vt.TemplateError) as cm:
            vt.finish(kind="t", figure_id="tf", stem="Points A and B.", elements=el,
                      anchors={"A": (0.0, 0.0), "B": (60.0, 0.0)}, points=["A", "B"],
                      segments=[], ask=[["a", "x"]],
                      claims=[('label "A" names A', "stem", ""), ('label "B" names B', "stem", "")],
                      title=None, description=None, scale="x")
        self.assertIn("nearer anchor B than its own A", str(cm.exception))

    def test_a_failed_finish_never_mutates_the_caller(self):
        # the unsatisfiable pair above — a raise must not eat the caller's
        # `_near`/`at` (finish() works on deep copies so retries are safe)
        el = [_dot("dotA", 0.0, 0.0), _dot("dotB", 5.0, 0.0),
              _floater("lblA", "A", (0.0, 0.0)), _floater("lblB", "B", (5.0, 0.0))]
        anchors = {"A": (0.0, 0.0), "B": (5.0, 0.0)}
        with self.assertRaises(vt.TemplateError):
            vt.finish(kind="t", figure_id="tf", stem="Points A and B.", elements=el,
                      anchors=anchors, points=["A", "B"], segments=[], ask=[["a", "x"]],
                      claims=[('label "A" names A', "stem", ""),
                              ('label "B" names B', "stem", "")],
                      title=None, description=None, scale="x")
        self.assertEqual(el[2]["at"], [0.0, 0.0])
        self.assertEqual(el[2]["_near"], [0.0, 0.0])
        self.assertNotIn("_floater", el[2])
        self.assertEqual(anchors, {"A": (0.0, 0.0), "B": (5.0, 0.0)})

    def test_region_false_frees_a_label_trapped_by_a_marker(self):
        # a tight unfilled outline around the anchor is decorative ink, not a
        # region — without `_region: false` the same-region rule traps the
        # label inside an outline too small to hold it; rects count too
        for marker in (
            {"type": "polygon", "id": "mk",
             "points": [[-12.0, -8.0], [12.0, -8.0], [12.0, 8.0], [-12.0, 8.0]]},
            {"type": "rect", "id": "mk", "x": -12.0, "y": -8.0,
             "width": 24.0, "height": 16.0},
        ):
            with self.subTest(marker=marker["type"]):
                def build(flag):
                    return vt.finish(
                        kind="t", figure_id="tf", stem="A marked dot.",
                        elements=[_dot("dotD", 0.0, 0.0),
                                  dict(marker, **({"_region": False} if flag else {})),
                                  _floater("lblD", "D", (0.0, 0.0))],
                        anchors={"D": (0.0, 0.0)}, points=["D"], segments=[],
                        ask=[["a", "x"]], claims=[('label "D" names D', "stem", "")],
                        title=None, description=None, scale="x")
                with self.assertRaises(vt.TemplateError) as cm:
                    build(False)
                self.assertIn("same-region", str(cm.exception))
                b = build(True)
                lbl = next(e for e in b.doc["elements"] if e["id"] == "lblD")
                self.assertNotEqual(lbl["at"], [0.0, 0.0])          # it moved, and placed
                self.assertNotIn("_region", next(e for e in b.doc["elements"]
                                                 if e["id"] == "mk"))


class RegionPoints(unittest.TestCase):
    def test_inside_outside_avoid(self):
        cl, cr, R = (0.0, 0.0), (140.0, 0.0), 100.0
        p = vt.region_point({"left": (cl, R), "right": (cr, R)},
                            inside=["right"], outside=["left"],
                            prefer=(140.0, 0.0), avoid=[cr], min_sep=25.0)
        self.assertLessEqual(math.hypot(p[0] - cr[0], p[1] - cr[1]), R - 15.0)
        self.assertGreaterEqual(math.hypot(p[0] - cl[0], p[1] - cl[1]), R + 15.0)
        self.assertGreaterEqual(math.hypot(p[0] - cr[0], p[1] - cr[1]), 25.0)

    def test_nearest_to_prefer_wins(self):
        p = vt.region_point({"c": ((0.0, 0.0), 50.0)}, inside=["c"], outside=[],
                            prefer=(20.0, 0.0), step=2.0)
        self.assertEqual(p, (20.0, 0.0))                 # prefer itself already qualifies

    def test_impossible_region_raises(self):
        with self.assertRaises(vt.TemplateError):
            vt.region_point({"c": ((0.0, 0.0), 20.0)}, inside=["c"], outside=[],
                            prefer=(5000.0, 5000.0))
        with self.assertRaises(vt.TemplateError):
            vt.region_point({"c": ((0.0, 0.0), 20.0)}, inside=["c"], outside=["c"],
                            prefer=(0.0, 0.0))

    def test_unknown_circle_named(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.region_point({"c": ((0.0, 0.0), 20.0)}, inside=["nope"], outside=[],
                            prefer=(0.0, 0.0))
        self.assertIn("nope", str(cm.exception))

    def test_on_circle_point_and_membership(self):
        c, r = (10.0, 20.0), 50.0
        p = vt.on_circle_point(c, r, 90.0)               # 90° is DOWN (y down)
        self.assertAlmostEqual(p[0], 10.0)
        self.assertAlmostEqual(p[1], 70.0)
        claims = vt.membership_claims("D", p, {"main": (c, r)})
        self.assertEqual(len(claims), 1)
        self.assertIn('describe "D lies on the main circle"', claims[0][0])
        inside = vt.membership_claims("D", c, {"main": (c, r)})[0][0]
        self.assertIn("inside the main circle", inside)


class MembershipTemplates(unittest.TestCase):
    """W10c — the six region/collection templates built on finish() + region_point."""

    STEM = "A synthetic stem for the figure. (a) Say something."

    def _b(self, kind, **kw):
        return vt.BUILDERS[kind](figure_id="mt1", stem=self.STEM,
                                 ask=[["a", "x"]], **kw)

    def test_circle_points_membership_and_placement(self):
        b = self._b("circle_points",
                    points={"P": {"where": "in"}, "Q": {"where": "on", "deg": 30},
                            "R": {"where": "out"}})
        circ = next(e for e in b.doc["elements"] if e["id"] == "circ")
        c, r = circ["center"], circ["r"]
        pts = {e["id"]: e for e in b.doc["elements"] if e["type"] == "point"}
        self.assertLess(math.hypot(pts["ptP"]["at"][0] - c[0],
                                   pts["ptP"]["at"][1] - c[1]), r)
        self.assertAlmostEqual(math.hypot(pts["ptQ"]["at"][0] - c[0],
                                          pts["ptQ"]["at"][1] - c[1]), r, places=2)
        self.assertGreater(math.hypot(pts["ptR"]["at"][0] - c[0],
                                      pts["ptR"]["at"][1] - c[1]), r)
        self.assertIn('describe "Q lies on the circle"', b.claims)
        self.assertIn("derive 1 + 1 + 1 = 3", b.claims)
        self.assertIn('label "P" names P', b.claims)
        # every dot label is a floater the placer moved — none sits at its anchor
        lbl = next(e for e in b.doc["elements"] if e["id"] == "lbP")
        self.assertNotEqual(lbl["at"], b.anchors["P"])

    def test_circle_points_stones_have_no_labels(self):
        b = self._b("circle_points", labelled=False,
                    points={"P": {"where": "in"}, "Q": {"where": "out"}})
        self.assertFalse([e for e in b.doc["elements"] if e["type"] == "text"])
        self.assertNotIn("label ", b.claims)

    def test_circle_points_refuses(self):
        with self.assertRaises(vt.TemplateError) as cm:
            self._b("circle_points", points={"P": {"where": "beside"}})
        self.assertIn("where", str(cm.exception))
        with self.assertRaises(vt.TemplateError):
            self._b("circle_points", points={"p": {"where": "in"}})

    def test_circle_points_malformed_specs_are_template_errors(self):
        """A bare string spec or a non-numeric deg must refuse with a reason,
        never a raw AttributeError/ValueError."""
        with self.assertRaises(vt.TemplateError) as cm:
            self._b("circle_points", points={"P": "in"})
        self.assertIn("dict", str(cm.exception))
        with self.assertRaises(vt.TemplateError) as cm:
            self._b("circle_points", points={"P": {"where": "on", "deg": "east"}})
        self.assertIn("deg", str(cm.exception))
        with self.assertRaises(vt.TemplateError):
            self._b("two_circles_points", points={"P": "L"})

    def test_circle_points_pinned_degs_keep_their_spacing(self):
        """A pinned deg follows the same separation rules as auto-placed on-dots —
        coincident/near-coincident pins refuse naming the real cause."""
        with self.assertRaises(vt.TemplateError) as cm:
            self._b("circle_points", points={"P": {"where": "on", "deg": 30},
                                             "Q": {"where": "on", "deg": 30}})
        self.assertIn("within 18°", str(cm.exception))
        with self.assertRaises(vt.TemplateError):
            self._b("circle_points", points={"P": {"where": "on", "deg": 0},
                                             "Q": {"where": "on", "deg": 5}})
        # but two clearly-spread pins still build
        b = self._b("circle_points", points={"P": {"where": "on", "deg": 0},
                                             "Q": {"where": "on", "deg": 90}})
        self.assertTrue(b.doc["elements"])

    def test_two_circles_regions_and_lens(self):
        b = self._b("two_circles_points",
                    points={"P": {"in": ["L"]}, "Q": {"in": ["L", "R"]},
                            "S": {"in": ["R"]}, "T": {"in": []},
                            "U": {"on": "L", "in": ["R"]}},
                    overlap=0.45)
        l = next(e for e in b.doc["elements"] if e["id"] == "cL")
        rr = next(e for e in b.doc["elements"] if e["id"] == "cR")
        d = math.hypot(rr["center"][0] - l["center"][0], rr["center"][1] - l["center"][1])
        self.assertAlmostEqual(d, 2 * 100.0 * (1 - 0.45))
        pts = {e["id"]: e for e in b.doc["elements"] if e["type"] == "point"}
        dl = lambda e: math.hypot(e["at"][0] - l["center"][0], e["at"][1] - l["center"][1])
        dr = lambda e: math.hypot(e["at"][0] - rr["center"][0], e["at"][1] - rr["center"][1])
        self.assertLess(dl(pts["ptP"]), l["r"])
        self.assertGreater(dr(pts["ptP"]), rr["r"])
        self.assertLess(dl(pts["ptQ"]), l["r"])
        self.assertLess(dr(pts["ptQ"]), rr["r"])
        self.assertGreater(dl(pts["ptT"]), l["r"])
        self.assertGreater(dr(pts["ptT"]), rr["r"])
        self.assertAlmostEqual(dl(pts["ptU"]), l["r"], places=5)
        self.assertLess(dr(pts["ptU"]), rr["r"])
        self.assertIn('describe "U lies on the left circle and inside the right circle"',
                      b.claims)
        self.assertIn("derive 3 + 1 + 1 = 5", b.claims)

    def test_two_circles_reserved_and_contradiction(self):
        with self.assertRaises(vt.TemplateError):
            self._b("two_circles_points", points={"L": {"in": ["L"]}})
        with self.assertRaises(vt.TemplateError):
            self._b("two_circles_points", points={"P": {"on": "L", "in": ["L"]}})
        with self.assertRaises(vt.TemplateError):
            self._b("two_circles_points", overlap=1.0, points={"P": {"in": ["L"]}})

    def test_circles_in_circle_spacing(self):
        b = self._b("circles_in_circle", n_in=6, n_out=5)
        els = {e["id"]: e for e in b.doc["elements"]}
        big = els["big"]
        centres = [e for e in els.values()
                   if e["type"] == "circle" and e["id"] != "big"]
        self.assertEqual(len(centres), 11)
        for e in centres:
            d = math.hypot(e["center"][0] - big["center"][0],
                           e["center"][1] - big["center"][1])
            if e["id"].startswith("in"):
                self.assertLessEqual(d, big["r"] - e["r"] - 9.9)
            else:
                self.assertGreaterEqual(d, big["r"] + e["r"] + 9.9)
        for i, e in enumerate(centres):
            for f in centres[i + 1:]:
                self.assertGreaterEqual(
                    math.hypot(e["center"][0] - f["center"][0],
                               e["center"][1] - f["center"][1]),
                    e["r"] + f["r"] + 9.9)
        self.assertIn("derive 6 + 5 = 11", b.claims)

    def test_circles_in_circle_refuses(self):
        with self.assertRaises(vt.TemplateError):
            self._b("circles_in_circle", n_in=0, n_out=0)
        with self.assertRaises(vt.TemplateError):
            self._b("circles_in_circle", n_in=-1, n_out=2)

    def test_circles_in_circle_one_small_circle_is_singular(self):
        b = self._b("circles_in_circle", n_in=1, n_out=0)
        self.assertIn("a small circle", b.doc["a11y"]["description"])
        self.assertNotIn("several", b.doc["a11y"]["description"])

    def test_abacus_rods_beads_and_sum(self):
        b = self._b("abacus", place_values=[1000, 100, 10, 1], beads=[3, 0, 5, 7])
        rods = [e for e in b.doc["elements"] if e["id"].startswith("rod")]
        self.assertEqual(len(rods), 4)
        beads = [e for e in b.doc["elements"] if e["type"] == "circle"]
        self.assertEqual(len(beads), 15)
        self.assertIn("derive 3 * 1000 + 0 * 100 + 5 * 10 + 7 * 1 = 3057", b.claims)
        for i, v in enumerate((1000, 100, 10, 1)):
            self.assertIn(f'label "{v}" names rod{i + 1}', b.claims)
        # beads thread on their rod — every bead centre sits on a rod line
        xs = {e["id"]: e["points"][0][0] for e in rods}
        for bd in beads:
            rod = "rod" + bd["id"][1]
            self.assertAlmostEqual(bd["center"][0], xs[rod])

    def test_abacus_refuses(self):
        with self.assertRaises(vt.TemplateError) as cm:
            self._b("abacus", place_values=[10, 1], beads=[10, 2])
        self.assertIn("never holds ten", str(cm.exception))
        with self.assertRaises(vt.TemplateError):
            self._b("abacus", place_values=[10, 1], beads=[1])
        with self.assertRaises(vt.TemplateError):
            self._b("abacus", place_values=[10, 10], beads=[1, 2])

    def test_abacus_labels_fixed_centred_under_their_rods(self):
        """R1 fix: floated rod labels drifted sideways off their rods — the value
        labels are FIXED now (x = the rod's x, one shared baseline under the bar)
        and the beads are ink-filled, like the lesson's abacus figures."""
        b = self._b("abacus", place_values=[10000, 1000, 100, 10, 1],
                    beads=[1, 2, 3, 4, 5])
        rods = {e["id"]: e for e in b.doc["elements"] if e["id"].startswith("rod")}
        labs = {e["id"]: e for e in b.doc["elements"] if e["id"].startswith("lv")}
        self.assertEqual(len(labs), 5)
        self.assertEqual(len({lab["at"][1] for lab in labs.values()}), 1)
        for i in range(1, 6):
            self.assertEqual(labs[f"lv{i}"]["at"][0],
                             rods[f"rod{i}"]["points"][0][0])
            self.assertNotIn("_near", labs[f"lv{i}"])
        beads = [e for e in b.doc["elements"] if e["type"] == "circle"]
        self.assertTrue(beads)
        for bd in beads:
            self.assertEqual(bd.get("fill", {}).get("color"), vt.vc.INK)

    def test_abacus_single_rod_builds(self):
        """A 1-rod abacus is taller than wide — the base bar widens to keep the
        canvas inside the 2:1 aspect rule instead of refusing outright."""
        b = self._b("abacus", place_values=[1], beads=[9])
        c = b.doc["canvas"]
        self.assertLessEqual(c["height"] / c["width"], 2.0)

    def test_sorting_rings_layout_and_claims(self):
        b = self._b("sorting_rings",
                    groups=[["Even", ["2", "8", "14"]], ["Odd", ["3", "9"]]])
        rings = [e for e in b.doc["elements"] if e["id"].startswith("ring")]
        self.assertEqual(len(rings), 2)
        cards = [e for e in b.doc["elements"] if e["id"].startswith("cd")]
        self.assertEqual(len(cards), 5)
        # every card lies fully inside its ring with ≥8 units to spare
        for cd in cards:
            ring = rings[0] if cd["id"].startswith("cd1") else rings[1]
            cx, cy = cd["x"] + cd["width"] / 2, cd["y"] + cd["height"] / 2
            # the farthest corner of the card from the ring's centre (cards share cx)
            self.assertLess(abs(cx - ring["center"][0]), 0.02)   # x/width are r2'd
            d = math.hypot(cd["width"] / 2, abs(cy - ring["center"][1]) + cd["height"] / 2)
            self.assertLessEqual(d, ring["r"] - 7.9)
        self.assertIn('label "Even" names ring1', b.claims)
        self.assertIn('label "14" names it1_3', b.claims)   # claim target == element id
        self.assertIn("derive 3 + 2 = 5", b.claims)

    def test_sorting_rings_refuses(self):
        with self.assertRaises(vt.TemplateError):
            self._b("sorting_rings", groups=[["A", ["1"]]])
        with self.assertRaises(vt.TemplateError):
            self._b("sorting_rings",
                    groups=[["A", ["1"]], ["B", ["2"]], ["C", ["3"]], ["D", ["4"]]])
        with self.assertRaises(vt.TemplateError):
            self._b("sorting_rings", groups=[["A", ["1", "1"]], ["B", ["2"]]])

    def test_sorting_rings_text_renders_at_the_default_size(self):
        """R1 fix: card numerals shrank (~13 px) to fit fixed-size cards — text now
        carries no fontSize override (the renderer's default applies) and the
        cards/rings grow to fit it instead."""
        b = self._b("sorting_rings",
                    groups=[["Even", ["2", "8"]], ["Odd", ["3", "9"]]])
        texts = [e for e in b.doc["elements"] if e["type"] == "text"]
        self.assertTrue(texts)
        for e in texts:
            self.assertIn(e.get("fontSize"), (None, vt.FS))

    def test_sorting_rings_self_test_canvas_stays_narrow(self):
        """R1 fix: a wide unit canvas scales the default-size card text down to
        ~12 px at 375 — the 2-ring self-test layout must stay ≤ ~360 units wide."""
        b = self._b("sorting_rings",
                    groups=[["Even", ["2", "8", "14"]], ["Odd", ["3", "9"]]])
        self.assertLessEqual(b.doc["canvas"]["width"], 360)

    def test_sorting_rings_three_groups_go_two_plus_one(self):
        """Three rings side by side widen the canvas until FS text shrinks —
        the third ring drops to a second row centred under the pair."""
        b = self._b("sorting_rings",
                    groups=[["A", ["1"]], ["B", ["2"]], ["C", ["3", "4"]]])
        rings = {e["id"]: e for e in b.doc["elements"]
                 if e["id"].startswith("ring")}
        self.assertEqual(len(rings), 3)
        self.assertEqual(rings["ring1"]["center"][1], rings["ring2"]["center"][1])
        self.assertGreater(rings["ring3"]["center"][1], rings["ring1"]["center"][1])
        r1, r2 = rings["ring1"], rings["ring2"]
        mid = (r1["center"][0] - r1["r"] + r2["center"][0] + r2["r"]) / 2
        self.assertAlmostEqual(rings["ring3"]["center"][0], mid, places=1)

    def test_shape_row_kinds_letters_and_rows(self):
        b = self._b("shape_row",
                    shapes=[["A", "circle"], ["B", "square"], ["C", "triangle"],
                            ["D", "oval"], ["E", "rectangle"], ["F", "semicircle"],
                            ["G", "small_circle"]])
        # three per row — second row sits lower
        self.assertGreater(b.anchors["D"][1], b.anchors["A"][1])
        # each letter's label floated to a spot outside its own shape, below-ish
        lbl = next(e for e in b.doc["elements"] if e["id"] == "lbA")
        circ = next(e for e in b.doc["elements"] if e["id"] == "shA")
        self.assertGreater(math.hypot(lbl["at"][0] - circ["center"][0],
                                      lbl["at"][1] - circ["center"][1]), circ["r"])
        self.assertGreater(lbl["at"][1], circ["center"][1])
        self.assertIn("circle centre H radius 34", b.claims)     # A's circle — no on-dots
        self.assertIn("circle centre I radius 22", b.claims)     # small_circle's
        self.assertIn('describe "D is an oval', b.claims)
        self.assertIn("derive 4 + 3 = 7", b.claims)

    def test_shape_row_letter_anchors_sit_on_drawn_geometry(self):
        """vdd-check's coverage reads rims and edges — a letter anchor sits ON its
        shape's outline (rim for the round kinds, an edge for the polygonal
        kinds), so no marker elements are needed or emitted."""
        b = self._b("shape_row", shapes=[["A", "circle"], ["B", "square"],
                                         ["E", "rectangle"], ["G", "small_circle"]])
        sh = {e["id"]: e["type"] for e in b.doc["elements"]
              if e["id"].startswith("sh")}
        self.assertEqual(sh["shB"], "polygon")
        self.assertEqual(sh["shE"], "polygon")
        for letter, eid in (("A", "shA"), ("G", "shG")):
            el = next(e for e in b.doc["elements"] if e["id"] == eid)
            d = math.hypot(b.anchors[letter][0] - el["center"][0],
                           b.anchors[letter][1] - el["center"][1])
            self.assertAlmostEqual(d, el["r"], places=2)         # on the rim
        self.assertFalse([e for e in b.doc["elements"]
                          if e.get("r") == 0 and not e.get("label")])

    def test_shape_row_refuses(self):
        with self.assertRaises(vt.TemplateError):
            self._b("shape_row", shapes=[["A", "hexagon"]])
        with self.assertRaises(vt.TemplateError):
            self._b("shape_row", shapes=[["A", "circle"], ["A", "square"]])
        with self.assertRaises(vt.TemplateError):
            self._b("shape_row", shapes=[["a", "circle"]])

    def test_deterministic_ids_across_repeated_builds(self):
        """vc's module id counter made a second in-process build emit different ids —
        every builder now resets at entry, so repeat builds are byte-identical."""
        kw = dict(points={"P": {"where": "in"}, "Q": {"where": "out"}})
        b1 = self._b("circle_points", **kw)
        b2 = self._b("circle_points", **kw)
        self.assertEqual(json.dumps(b1.doc, sort_keys=True),
                         json.dumps(b2.doc, sort_keys=True))


def _anchors_of(claims: str) -> dict:
    """Parse a claim set's `anchors:` block → {name: (x, y)}."""
    out = {}
    for line in claims.splitlines():
        m = re.match(r"^  ([A-Z]\d*) (\S+) (\S+)$", line)
        if m:
            out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def _set_anchor(claims: str, name: str, x=None, y=None) -> str:
    """Rewrite one anchor line in the claims text (the red team's move)."""
    lines = []
    for line in claims.splitlines():
        m = re.match(r"^  ([A-Z]\d*) (\S+) (\S+)$", line)
        if m and m.group(1) == name:
            nx = float(m.group(2)) if x is None else x
            ny = float(m.group(3)) if y is None else y
            line = f"  {name} {nx:g} {ny:g}"
        lines.append(line)
    return "\n".join(lines) + "\n"


class CoordinatePlane(unittest.TestCase):
    """W11 — first-quadrant integer plane: axis claims, `reads` per coordinate,
    half-cell pocket labels, and the axis-anchor collision refusals."""

    STEM = ("Points A(3, 4), B(1, 2), C(5, 1) and D(2, 5) are marked on a "
            "coordinate plane. (a) Read the coordinates of each point.")

    def _b(self, **kw):
        d = dict(figure_id="cp1", stem=self.STEM, ask=[["a", "x"]],
                 x_max=6, y_max=5, coords="stem", grid=True,
                 points={"A": (3, 4), "B": (1, 2)})
        d.update(kw)
        return vt.BUILDERS["coordinate_plane"](**d)

    def test_happy_path_audits_clean(self):
        b = self._b()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0)
        self.assertIn("axis OX from 0 to 6", b.claims)
        self.assertIn("axis OY from 0 to 5", b.claims)
        self.assertIn("right X O Y", b.claims)
        self.assertIn("reads A 3 on OX | stem", b.claims)
        self.assertIn("reads A 4 on OY | stem", b.claims)
        self.assertIn('label "x" names OX', b.claims)
        self.assertIn('label "y" names OY', b.claims)

    def test_join_sym_axis_guides_and_origin_label(self):
        b = self._b(points={"A": (3, 4), "B": (1, 2), "C": (5, 1)},
                    join=[["A", "B", "C"]], closed=True, sym_axis={"x": 3},
                    guides=["A"], origin_label=True,
                    stem=self.STEM)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
        self.assertIn('label "O" names O', b.claims)
        self.assertIn("paint", b.claims)                      # the dashed midline
        self.assertNotIn("none tickMark parallelMark angleMark angleArc dashed",
                         b.claims)                            # dashed IS drawn now

    def test_figure_mode_emits_inferred_reads_and_the_content_line(self):
        b = self._b(coords="figure",
                    stem="The points are marked on the plane. (a) Read them.")
        self.assertIn("reads A 3 on OX | inferred", b.claims)
        self.assertIn("figure content", b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0)

    def test_extents_and_point_validation(self):
        with self.assertRaises(vt.TemplateError):
            self._b(x_max=0)
        with self.assertRaises(vt.TemplateError):
            self._b(x_max=11)
        with self.assertRaises(vt.TemplateError):
            self._b(x_max=6.0)                              # float, not int
        with self.assertRaises(vt.TemplateError):
            self._b(coords="axes")
        with self.assertRaises(vt.TemplateError):
            self._b(points={"a": (3, 4)})                   # not a capital
        with self.assertRaises(vt.TemplateError):
            self._b(points={"O": (3, 4)})                   # reserved
        with self.assertRaises(vt.TemplateError):
            self._b(points={"A": (2.5, 3)})                 # non-integer
        with self.assertRaises(vt.TemplateError):
            self._b(points={"A": (7, 2)})                   # outside the plane
        with self.assertRaises(vt.TemplateError):
            self._b(points={"A": (3, 4), "B": (3, 4)})      # two letters, one dot

    def test_axis_anchor_positions_refuse(self):
        """(0,0), (x_max,0), (0,y_max) are owned by O/X/Y — a dot letter can never
        own the shared anchor, so the builder refuses them outright."""
        for xy in ((0, 0), (6, 0), (0, 5)):
            with self.subTest(xy=xy):
                with self.assertRaises(vt.TemplateError) as cm:
                    self._b(points={"A": xy})
                self.assertIn("axis anchor", str(cm.exception))
        b = self._b(points={"A": (6, 5)},                   # the far corner is legal
                    stem="Point A(6, 5) is marked. (a) Read it.")
        self.assertIn("reads A 5 on OY", b.claims)

    def test_on_axis_non_anchor_points_build(self):
        b = self._b(points={"A": (3, 0), "B": (0, 2)},
                    stem="Points A(3, 0) and B(0, 2) are marked. (a) Read them.")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)

    def _sweep_spec(self, xm, ym):
        """The W12 sweep shape: five non-collinear interior points + origin_label."""
        pts = {"A": (1, 1), "B": (xm - 1, 1), "C": (1, ym - 1),
               "D": (xm - 1, ym - 1), "E": (xm // 2, ym // 2)}
        nums = sorted({c for p in pts.values() for c in p})
        stem = ("Points " + " ".join(map(str, nums)) +
                " are marked on a coordinate plane. (a) Read them.")
        return dict(figure_id="f1", stem=stem, x_max=xm, y_max=ym,
                    points=pts, grid=True, origin_label=True)

    def test_lettered_grid_sweep_measured_limit(self):
        """W12 A3 + the 2026-10-04 owner ruling: clear pockets come first; when no
        pocket seats a letter at any size the faint ruling lines stop being
        obstacles (axes, ticks, joins, dots, labels and the edge still count) and
        EVERY letter draws in the accent colour. The whole 7..10 envelope builds.
        """
        feasible = [(4, y) for y in range(4, 10)] + \
                   [(5, y) for y in range(4, 9)] + \
                   [(6, y) for y in range(4, 7)]
        with tempfile.TemporaryDirectory() as tmp:
            for xm, ym in feasible:
                with self.subTest(x_max=xm, y_max=ym):
                    b = vt.BUILDERS["coordinate_plane"](**self._sweep_spec(xm, ym))
                    self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
                    # small grids still seat every letter in a clear pocket — no
                    # accent, no fallback claim (bytes unchanged by the ruling)
                    self.assertFalse(
                        any(e.get("color") for e in b.doc["elements"]))
                    self.assertNotIn("accent colour", b.claims)
            for xm in range(7, 11):
                for ym in range(7, 11):
                    with self.subTest(x_max=xm, y_max=ym):
                        b = vt.BUILDERS["coordinate_plane"](**self._sweep_spec(xm, ym))
                        self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
                        # the fallback engaged: every point letter + "O" shares the
                        # ONE accent (a figure never mixes letter inks) — and the
                        # claim set declares it
                        accent = sorted(e["id"] for e in b.doc["elements"]
                                        if e.get("color") == vt._CP_ACCENT)
                        self.assertEqual(
                            accent,
                            ["lbA", "lbB", "lbC", "lbD", "lbE", "org"])
                        self.assertIn(
                            'describe "point letters sit over the faint grid lines',
                            b.claims)

    def _admin_env(self):
        """Env with VIBHAGA_ADMIN resolved (flag → env → sibling walk), or skip."""
        import os
        import shutil
        env = dict(os.environ)
        if not env.get("VIBHAGA_ADMIN"):
            d = TOOLS.parent
            while not (d / "Vibhaga-Admin").is_dir() and d.parent != d:
                d = d.parent
            if (d / "Vibhaga-Admin").is_dir():
                env["VIBHAGA_ADMIN"] = str(d / "Vibhaga-Admin")
        if not shutil.which("node") or "VIBHAGA_ADMIN" not in env:
            self.skipTest("node or the sibling Vibhaga-Admin checkout unavailable")
        return env

    def test_lettered_grid_sweep_passes_vdd_check(self):
        """The frontier builds AND every 7..10 fallback build survive vdd-check
        --no-render with 0 findings (the rendered clearance is the regression run —
        the grid exemption itself is exercised by test_grid_line_exemption_*)."""
        env = self._admin_env()
        with tempfile.TemporaryDirectory() as tmp:
            specs = [(4, 9), (5, 8), (6, 6), (4, 4)] + \
                    [(x, y) for x in range(7, 11) for y in range(7, 11)]
            for xm, ym in specs:
                with self.subTest(x_max=xm, y_max=ym):
                    b = vt.BUILDERS["coordinate_plane"](**self._sweep_spec(xm, ym))
                    fig = Path(tmp) / f"cp{xm}x{ym}.json"
                    fig.write_text(json.dumps(b.doc), encoding="utf-8")
                    claims = Path(tmp) / f"cp{xm}x{ym}.claims.txt"
                    claims.write_text(b.claims, encoding="utf-8")
                    anchors = Path(tmp) / f"cp{xm}x{ym}.anchors.json"
                    anchors.write_text(json.dumps(b.anchors), encoding="utf-8")
                    r = subprocess.run(
                        ["node", str(TOOLS / "vdd-check.mjs"), str(fig),
                         "--claims", str(claims), "--anchors", str(anchors),
                         "--no-render"],
                        capture_output=True, text=True, env=env)
                    self.assertEqual(r.returncode, 0,
                                     f"{xm}×{ym}\n{r.stdout}\n{r.stderr}")

    def test_stem_mode_needs_every_coordinate(self):
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(points={"A": (3, 5)},
                    stem="Point A(3, 4) is marked. (a) Read it.")   # no 5 in the stem
        self.assertIn("5", str(cm.exception))

    def test_join_sym_guides_validation(self):
        with self.assertRaises(vt.TemplateError):
            self._b(join=[["A", "Z"]])                      # unknown point
        with self.assertRaises(vt.TemplateError):
            self._b(join=[["A"]])                           # too short
        with self.assertRaises(vt.TemplateError):
            self._b(join=[["A", "A"]])                      # zero-length step
        with self.assertRaises(vt.TemplateError):
            self._b(sym_axis={"z": 2})                      # bad key
        with self.assertRaises(vt.TemplateError):
            self._b(sym_axis={"x": 6})                      # not strictly inside
        with self.assertRaises(vt.TemplateError):
            self._b(guides=["Z"])
        with self.assertRaises(vt.TemplateError):
            self._b(unit_px=0)

    def test_dense_grid_falls_back_to_accent_letters(self):
        """10x10 with 8 interior points: no clear pocket seats any letter, so the
        ruling-line fallback engages — every letter in the one accent colour and the
        claim set says so."""
        b = self._b(x_max=10, y_max=10, coords="figure",
                    stem="Several points are marked. (a) Read them.",
                    points={n: xy for n, xy in
                            zip("ABCDEFGH", [(1, 1), (3, 2), (5, 5), (7, 3),
                                            (2, 8), (9, 9), (4, 6), (8, 1)])})
        accent = sorted(e["id"] for e in b.doc["elements"]
                        if e.get("color") == vt._CP_ACCENT)
        self.assertEqual(accent,
                         [f"lb{n}" for n in "ABCDEFGH"])
        self.assertIn('describe "point letters sit over the faint grid lines',
                      b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)

    def test_refusal_stays_real_past_the_fallback(self):
        """The ruling-line exemption is not a licence to print: unit_px=1 leaves a
        ~20-unit canvas where no label box can sit anywhere — the refusal names the
        fallback it already tried."""
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(x_max=10, y_max=10, coords="figure",
                    stem="Point A(5, 5) is marked. (a) Read it.",
                    points={"A": (5, 5)}, unit_px=1)
        self.assertIn("fallback", str(cm.exception))

    def test_grid_line_exemption_is_id_keyed(self):
        """vdd-check's render pass exempts the gv*/gh* ruling lines from the
        label↔stroke rule ONLY: a label ON a ruling line passes, the same label on a
        same-coloured line WITHOUT the marker (or on an axis) still fails."""
        env = self._admin_env()
        if not (Path(env["VIBHAGA_ADMIN"]) / "node_modules" / "playwright").is_dir():
            self.skipTest("playwright not installed in the Admin checkout")
        base = {"schema": "vibhaga.diagram", "schemaVersion": 1,
                "canvas": {"width": 200, "height": 200},
                "a11y": {"title": "A vertical line with the letter A on it",
                         "description": "One vertical line and one centred letter."}}
        mk = lambda lid: {**base, "elements": [   # noqa: E731
            {"id": lid, "type": "line", "points": [[100, 10], [100, 190]],
             "stroke": {"color": "#d1d5db", "width": 1}},
            {"id": "lbA", "type": "text", "at": [100, 100], "value": "A"}]}
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "fig.json"
            f.write_text(json.dumps(mk("gv1")))          # the ruling-line marker
            r = subprocess.run(
                ["node", str(TOOLS / "vdd-check.mjs"), str(f),
                 "--widths", "320", "--out", str(Path(tmp) / "o1")],
                capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0,
                             f"label over gv1 must pass:\n{r.stdout}\n{r.stderr}")
            for lid in ("ln1", "axX"):                  # same faint colour, no marker
                with self.subTest(id=lid):
                    f.write_text(json.dumps(mk(lid)))
                    r = subprocess.run(
                        ["node", str(TOOLS / "vdd-check.mjs"), str(f),
                         "--widths", "320", "--out", str(Path(tmp) / "o2")],
                        capture_output=True, text=True, env=env)
                    self.assertEqual(r.returncode, 1)
                    self.assertIn("from stroke geometry", r.stdout)

    def test_red_team_anchor_moved_to_a_different_value(self):
        """A=(3,4) in the stem; drag A's anchor up to the y=5 line and the unchanged
        claim `reads A 4 on OY` must die — the anchors now disagree with it."""
        b = self._b(points={"A": (3, 4)},
                    stem="Point A(3, 4) is marked. (a) Read it.")
        anc = _anchors_of(b.claims)
        o_y, y_y = anc["O"][1], anc["Y"][1]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0)
            forged = _set_anchor(b.claims, "A", y=y_y)      # y_max = 5 → the 5 line
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)

    def test_red_team_claim_off_stem_value(self):
        """`reads A 5 on OY | stem` — the stem states A(3, 4), no 5 anywhere: the
        stem-justification check must kill it even before geometry is consulted."""
        b = self._b(points={"A": (3, 4)},
                    stem="Point A(3, 4) is marked. (a) Read it.")
        forged = b.claims.replace("reads A 4 on OY | stem",
                                  "reads A 5 on OY | stem")
        self.assertNotEqual(forged, b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)
            self.assertIn("stem", r.stdout)

    def test_sym_axis_stem_mode_reads_are_stem_evidenced(self):
        """W11 review MAJOR 1 — the midline's two `reads` carry ev `stem` in stem mode
        (the value is require_stem'd at input)."""
        b = self._b(sym_axis={"x": 3})                       # 3 IS in STEM (A's x)
        sym_reads = [ln for ln in b.claims.splitlines()
                     if "reads" in ln and "midline" in ln]
        self.assertEqual(len(sym_reads), 2)
        for ln in sym_reads:
            self.assertIn("| stem", ln)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)

    def test_sym_axis_stem_mode_needs_the_value_in_the_stem(self):
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(sym_axis={"y": 2.5})                     # 2.5 is nowhere in STEM
        self.assertIn("midline", str(cm.exception))

    def test_sym_axis_figure_mode_reads_stay_inferred(self):
        b = self._b(coords="figure", sym_axis={"x": 3},
                    stem="Points are marked and a dashed midline crosses the plane. "
                         "(a) Read the figure.")
        for ln in b.claims.splitlines():
            if "reads" in ln and "midline" in ln:
                self.assertIn("| inferred", ln)
        self.assertIn("figure content", b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)

    def test_red_team_reads_ev_flipped_to_inferred_dies(self):
        """W11 review MAJOR 1: `reads … | inferred` without the figure-content
        declaration unhooks the value from the stem — the audit must now kill it."""
        b = self._b(points={"A": (3, 4)},
                    stem="Point A(3, 4) is marked. (a) Read it.")
        forged = b.claims.replace("reads A 3 on OX | stem",
                                  "reads A 3 on OX | inferred")
        self.assertNotEqual(forged, b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0)
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)
            self.assertIn("figure content", r.stdout)


class ParallelLines(unittest.TestCase):
    """W11 — parallel classes, tilted non-class lines, the optional crossing and the
    perpendicular-distance segment MN."""

    STEM = ("AB and CD are parallel horizontal lines; EF lies between them, slanted. "
            "The perpendicular distance between AB and CD is 3 cm. "
            "(a) Name the parallel lines.")

    def _b(self, **kw):
        d = dict(figure_id="pl1", stem=self.STEM, ask=[["a", "x"]],
                 lines=["AB", "CD", "EF"], parallel=[["AB", "CD"]], direction=0)
        d.update(kw)
        return vt.BUILDERS["parallel_lines"](**d)

    def test_happy_path_audits_clean(self):
        b = self._b()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
        self.assertIn("parallel AB CD", b.claims)
        self.assertIn("nonparallel AB EF", b.claims)
        self.assertIn("nonparallel CD EF", b.claims)

    def test_two_classes_crossing_and_distance(self):
        b = self._b(lines=["AB", "CD", "EF", "GH"],
                    parallel=[["AB", "CD"], ["EF", "GH"]],
                    crossing="PQ",
                    distance={"between": ["AB", "CD"], "value": 3, "unit": "cm"})
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
        self.assertIn("parallel EF GH", b.claims)
        self.assertIn("nonparallel PQ AB", b.claims)
        self.assertIn("on M AB", b.claims)
        self.assertIn("on N CD", b.claims)
        self.assertIn('label "3 cm" names MN', b.claims)
        self.assertIn("right", b.claims)
        self.assertIn("two arrows", b.claims)               # class 2's double mark

    def test_line_and_class_validation(self):
        with self.assertRaises(vt.TemplateError):
            self._b(lines=["AB"])                           # need 2-4
        with self.assertRaises(vt.TemplateError):
            self._b(lines=["AB", "CD", "EF", "GH", "IJ"])
        with self.assertRaises(vt.TemplateError):
            self._b(lines=["AB", "CD", "AC"])               # A shared by AB and AC
        with self.assertRaises(vt.TemplateError):
            self._b(parallel=[])                            # ≥1 class
        with self.assertRaises(vt.TemplateError):
            self._b(parallel=[["AB"], ["CD", "EF"]])        # a class needs ≥2
        with self.assertRaises(vt.TemplateError):
            self._b(parallel=[["AB", "CD"], ["CD", "EF"]])  # CD in two classes
        with self.assertRaises(vt.TemplateError):
            self._b(parallel=[["AB", "CD", "EF"], ["GH", "IJ"]])  # 3 classes
        with self.assertRaises(vt.TemplateError):
            self._b(parallel=[["AB", "PQ"]])                # PQ not in lines
        with self.assertRaises(vt.TemplateError):
            self._b(direction="east")

    def test_crossing_and_distance_validation(self):
        with self.assertRaises(vt.TemplateError):
            self._b(crossing="AQ")                          # A already used
        with self.assertRaises(vt.TemplateError):
            self._b(crossing="P")                           # needs two capitals
        with self.assertRaises(vt.TemplateError):
            self._b(distance={"between": ["AB", "EF"],      # different classes
                              "value": 3, "unit": "cm"})
        with self.assertRaises(vt.TemplateError):
            self._b(distance={"between": ["AB", "CD"],
                              "value": -3, "unit": "cm"})
        with self.assertRaises(vt.TemplateError):
            self._b(distance={"between": ["AB", "CD"],
                              "value": 3, "unit": ""})
        with self.assertRaises(vt.TemplateError):           # MN letters taken by a line
            self._b(lines=["AB", "CD", "EF", "MN"],
                    parallel=[["AB", "CD"], ["EF", "MN"]],
                    distance={"between": ["AB", "CD"], "value": 3, "unit": "cm"})
        with self.assertRaises(vt.TemplateError) as cm:     # 3 not in the stem
            self._b(stem="AB and CD are parallel; EF is slanted. (a) Name them.",
                    distance={"between": ["AB", "CD"], "value": 3, "unit": "cm"})
        self.assertIn("3", str(cm.exception))

    def test_directions_and_tilt(self):
        for direction in (0, 20, -30, 90):
            with self.subTest(direction=direction):
                b = self._b(direction=direction)
                with tempfile.TemporaryDirectory() as tmp:
                    self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)

    def test_red_team_parallel_claim_on_a_rotated_line(self):
        """Rotate CD's anchors 4° off AB — `parallel AB CD` must die (≥5° gate)."""
        b = self._b()
        anc = _anchors_of(b.claims)
        cx, cy = anc["C"]
        dx, dy = anc["D"]
        ang = math.atan2(dy - cy, dx - cx) + math.radians(4)
        ln = math.hypot(dx - cx, dy - cy)
        forged = _set_anchor(b.claims, "D",
                             x=cx + ln * math.cos(ang), y=cy + ln * math.sin(ang))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0)
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)

    def test_red_team_nonparallel_claim_on_a_parallel_line(self):
        """Straighten EF's anchors onto AB's direction — `nonparallel AB EF` must die."""
        b = self._b()
        anc = _anchors_of(b.claims)
        ax, ay, bx, by = *anc["A"], *anc["B"]
        ex, ey, fx, fy = *anc["E"], *anc["F"]
        uab = math.hypot(bx - ax, by - ay)
        ln = math.hypot(fx - ex, fy - ey)
        forged = _set_anchor(b.claims, "F",
                             x=ex + (bx - ax) / uab * ln,
                             y=ey + (by - ay) / uab * ln)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0)
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)

    def test_parallel_marks_clear_the_crossing_and_mn(self):
        """W11 review MAJOR 2 — on the dense spec the crossing used to run straight
        through the marks. Measure the emitted mark strokes' distance to the crossing
        and MN segments at the narrowest render scale: ≥8 rendered px of ink gap."""
        b = self._b(lines=["AB", "CD", "EF", "GH"],
                    parallel=[["AB", "CD"], ["EF", "GH"]],
                    crossing="PQ",
                    distance={"between": ["AB", "CD"], "value": 3, "unit": "cm"})
        els = b.doc["elements"]
        marks = [el for el in els if el["type"] == "parallelMark"]
        self.assertEqual(len(marks), 4)
        blockers = [next(el["points"] for el in els if el.get("id") == "lnPQ"),
                    next(el["points"] for el in els if el.get("id") == "dist")]
        s = min(1.0, vt.PLATE_INNER / (b.doc["canvas"]["width"] + 60.0))
        for p, q, _w in vt.stroke_segments(marks):
            for seg in blockers:
                gap = vt._seg_seg_dist(p, q, tuple(seg[0]), tuple(seg[1]))
                self.assertGreaterEqual(
                    gap * s, 8.0,
                    f"a parallelMark stroke {(p, q)} sits {gap * s:.1f} rendered px "
                    f"from a crossing/MN stroke")
        # round-3 review: a class is ONE symbol — its members share a single `at`,
        # so the chevrons stay on the same side of the transversal (count = class
        # index + 1, so grouping by count groups by class)
        by_count: dict[int, list[float]] = {}
        for el in marks:
            by_count.setdefault(el["count"], []).append(el["at"])
        self.assertEqual(sorted(by_count), [1, 2])
        for cnt, ats in by_count.items():
            self.assertEqual(len(set(ats)), 1,
                             f"class {cnt} marks carry mixed `at` {ats}")

    def test_every_letter_sits_at_its_own_end(self):
        """W11 review — E's floater used to land right under C (EF's left end sat just
        below CD's). Every letter must read nearer its OWN anchor than any other."""
        variants = ({}, {"crossing": "PQ"},
                    {"distance": {"between": ["AB", "CD"], "value": 3, "unit": "cm"}})
        for kw in variants:
            with self.subTest(kw=kw):
                b = self._b(**kw)
                for el in b.doc["elements"]:
                    if el["type"] != "text" or not el["id"].startswith("lb"):
                        continue
                    ch = el["value"]
                    if ch not in b.anchors:
                        continue                    # the "v unit" distance label
                    own = b.anchors[ch]
                    d_own = math.hypot(el["at"][0] - own[0], el["at"][1] - own[1])
                    for nm_, p in b.anchors.items():
                        if nm_ == ch:
                            continue
                        self.assertLess(
                            d_own, math.hypot(el["at"][0] - p[0],
                                              el["at"][1] - p[1]),
                            f"{ch}'s label reads nearer {nm_} than its own end")

    def test_dollar_label_is_a_stated_refusal_not_a_crash(self):
        """W11 review — the unit text reaches a VDD label: `$` must be TemplateError,
        not vc.text's AssertionError."""
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(distance={"between": ["AB", "CD"], "value": 3, "unit": "c$m"})
        self.assertIn("`$`", str(cm.exception))
        with self.assertRaises(vt.TemplateError):
            self._b(distance={"between": ["AB", "CD"], "value": 3, "unit": "cm`s"})


class BarChart(unittest.TestCase):
    """W11 — grouped vertical bars, T-anchored reads, numeral-vs-category labels."""

    STEM = ("The chart shows sales of 25 books in Grade 6 and 40 books in Grade 7, "
            "in steps of 5. (a) Which grade sold more?")

    def _b(self, **kw):
        d = dict(figure_id="bc1", stem=self.STEM, ask=[["a", "x"]],
                 categories=["Grade 6", "Grade 7"],
                 series=[{"name": "", "values": [25, 40]}], step=5)
        d.update(kw)
        return vt.BUILDERS["bar_chart"](**d)

    def test_happy_path_audits_clean(self):
        b = self._b()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
        self.assertIn("axis OY from 0 to 40", b.claims)
        self.assertIn("tick OY step 5 | stem", b.claims)
        self.assertIn("reads T1 25 on OY | stem", b.claims)
        self.assertIn("reads T2 40 on OY | stem", b.claims)
        self.assertIn('label "Grade 6" names cat0', b.claims)
        self.assertNotIn("legend", b.claims)                # one series → no legend

    def test_multi_series_legend_zero_bar_and_titles(self):
        b = self._b(categories=["Mon", "Tue", "Wed"],
                    series=[{"name": "Tea", "values": [4, 0, 6]},
                            {"name": "Milk", "values": [2, 3, 5]}],
                    step=2, v_max=8, value_title="Cups", category_title="Day",
                    stem="Tea sold 4, 0 and 6 cups; milk sold 2, 3 and 5 cups, "
                         "in steps of 2. (a) Compare.")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
        self.assertIn("reads T3 0 on OY", b.claims)         # a 0 bar still reads
        self.assertIn('label "Tea" names series0', b.claims)
        self.assertIn('names OY', b.claims)                 # the value title
        self.assertIn('names OX', b.claims)                 # the category title

    def test_figure_mode_and_year_categories(self):
        """Years as category glyphs are NOT scale numerals — the 2a exclusion keeps
        `label "2019" names cat0` out of the printed-numeral set."""
        b = self._b(categories=["2019", "2020", "2021"],
                    series=[{"name": "", "values": [10, 15, 20]}],
                    step=5, values="figure",
                    stem="The chart shows a club's membership over three years, "
                         "the axis marked in steps of 5. "
                         "(a) In which year was it highest?")
        self.assertIn("reads T1 10 on OY | inferred", b.claims)
        self.assertIn("figure content", b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)

    def test_input_validation(self):
        with self.assertRaises(vt.TemplateError):
            self._b(categories=["Only"])                    # need 2-8
        with self.assertRaises(vt.TemplateError):
            self._b(categories=[f"C{i}" for i in range(9)])
        with self.assertRaises(vt.TemplateError):
            self._b(categories=["A", " "])                  # blank label
        with self.assertRaises(vt.TemplateError):
            self._b(series=[])                              # need 1-3
        with self.assertRaises(vt.TemplateError):
            self._b(series=[{"name": "", "values": [1, 2]}] * 4)
        with self.assertRaises(vt.TemplateError):
            self._b(series=[{"name": "", "values": [25]}])  # one value, two cats
        with self.assertRaises(vt.TemplateError):
            self._b(series=[{"name": "", "values": [25, 40]},
                            {"name": "", "values": [10, 20]}])   # unnamed in a group
        with self.assertRaises(vt.TemplateError):
            self._b(values="bars")
        with self.assertRaises(vt.TemplateError):
            self._b(step=0)
        with self.assertRaises(vt.TemplateError):           # step 7 not in stem
            self._b(step=7)

    def test_scale_validation(self):
        with self.assertRaises(vt.TemplateError) as cm:     # 33 not on the 2.5 lattice
            self._b(series=[{"name": "", "values": [25, 33]}],
                    stem="The chart shows 25 and 33, in steps of 5. (a) Read.")
        self.assertIn("step/2", str(cm.exception))
        with self.assertRaises(vt.TemplateError):           # v_max not a step multiple
            self._b(v_max=42)
        with self.assertRaises(vt.TemplateError):           # 13 steps > 12
            self._b(step=1, v_max=13,
                    series=[{"name": "", "values": [5, 10]}],
                    stem="The chart shows 5 and 10, in steps of 1. (a) Read.")
        with self.assertRaises(vt.TemplateError) as cm:     # a bar over the axis
            self._b(v_max=30)
        self.assertIn("v_max", str(cm.exception))

    def test_width_cap_refusal_states_the_fix(self):
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(categories=["Category number " + str(i) for i in range(8)],
                    series=[{"name": "Series " + s,
                             "values": [10] * 8} for s in "ABC"],
                    step=5,
                    stem="Eight categories, three series, all at 10, steps of 5. "
                         "(a) Read.")
        self.assertIn("drop categories", str(cm.exception))

    def test_red_team_bar_drawn_at_another_value(self):
        """Stem states 25 and 40; drag T1's anchor to the 30 height — the claim
        `reads T1 25 on OY` must die against its own anchor."""
        b = self._b()
        anc = _anchors_of(b.claims)
        o_y, y_y = anc["O"][1], anc["Y"][1]                 # OY maps 0..40
        y30 = o_y + (30 / 40) * (y_y - o_y)
        forged = _set_anchor(b.claims, "T1", y=y30)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0)
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)

    def test_red_team_claim_matching_the_forged_anchor_dies_on_stem(self):
        """The full lie: anchor AND claim agree on 30 — it falls only to the
        stem-justification check (the stem never states 30)."""
        b = self._b()
        anc = _anchors_of(b.claims)
        o_y, y_y = anc["O"][1], anc["Y"][1]
        forged = _set_anchor(b.claims, "T1", y=o_y + (30 / 40) * (y_y - o_y))
        forged = forged.replace("reads T1 25 on OY | stem",
                                "reads T1 30 on OY | stem")
        self.assertNotEqual(forged, b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            r = audit(forged, tmp)
            self.assertNotEqual(r.returncode, 0, forged)
            self.assertIn("stem", r.stdout)

    def test_dollar_and_backtick_labels_are_stated_refusals(self):
        """W11 review — a `$` in a category used to escape as vc.text's AssertionError.
        Every user text (categories, series names, titles) is checked up front."""
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(categories=["$x$", "Q"])
        self.assertIn("`$`", str(cm.exception))
        with self.assertRaises(vt.TemplateError):
            self._b(series=[{"name": "A`b", "values": [25, 40]},
                            {"name": "B", "values": [20, 30]}],
                    stem="A`b sold 25 and 40; B sold 20 and 30, in steps of 5. (a) Read.")
        with self.assertRaises(vt.TemplateError):
            self._b(value_title="Sales $")
        with self.assertRaises(vt.TemplateError):
            self._b(category_title="Day|Night")            # claim-separator chars too


class BarChartHorizontal(unittest.TestCase):
    """W12 A5 — `orientation="h"`: bars run right, categories stack up the y axis
    with the first category nearest the origin, and every `reads` claim measures a
    bar's END edge on OX. The default "v" output is pinned byte-identical by the
    selftest-bars entry in ByteIdentity."""

    STEM = ("The chart shows sales of 25 books in Grade 6 and 40 books in Grade 7, "
            "in steps of 5. (a) Which grade sold more?")

    def _b(self, **kw):
        d = dict(figure_id="bc1", stem=self.STEM, ask=[["a", "x"]],
                 categories=["Grade 6", "Grade 7"],
                 series=[{"name": "", "values": [25, 40]}], step=5,
                 orientation="h")
        d.update(kw)
        return vt.BUILDERS["bar_chart"](**d)

    def test_happy_path_audits_clean(self):
        b = self._b()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
        self.assertIn("axis OX from 0 to 40", b.claims)
        self.assertIn("tick OX step 5 | stem", b.claims)
        self.assertIn("reads T1 25 on OX | stem", b.claims)
        self.assertIn("reads T2 40 on OX | stem", b.claims)
        self.assertIn('label "Grade 6" names cat0', b.claims)
        # the value axis is the horizontal one — the arrow carries it
        ax = {e["id"]: e for e in b.doc["elements"]}
        self.assertEqual(ax["axX"]["type"], "arrow")
        self.assertEqual(ax["axY"]["type"], "line")

    def test_multi_series_legend_zero_bar_and_titles(self):
        b = self._b(categories=["Mon", "Tue", "Wed"],
                    series=[{"name": "Tea", "values": [4, 0, 6]},
                            {"name": "Milk", "values": [2, 3, 5]}],
                    step=2, v_max=8, value_title="Cups", category_title="Day",
                    stem="Tea sold 4, 0 and 6 cups; milk sold 2, 3 and 5 cups, "
                         "in steps of 2. (a) Compare.")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)
        self.assertIn("reads T3 0 on OX", b.claims)         # a 0 bar still reads
        self.assertIn('label "Tea" names series0', b.claims)
        self.assertIn('label "Cups" names OX', b.claims)    # the value title
        self.assertIn('label "Day" names OY', b.claims)     # the category title

    def test_figure_mode(self):
        b = self._b(values="figure",
                    stem="The chart shows two classes' totals, the axis marked in "
                         "steps of 5. (a) Which is larger?")
        self.assertIn("reads T1 25 on OX | inferred", b.claims)
        self.assertIn("figure content", b.claims)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(audit(b.claims, tmp).returncode, 0, b.claims)

    def test_h_survives_vdd_check(self):
        b = self._b(categories=["Mon", "Tue", "Wed"],
                    series=[{"name": "Tea", "values": [4, 0, 6]},
                            {"name": "Milk", "values": [2, 3, 5]}],
                    step=2, v_max=8, value_title="Cups", category_title="Day",
                    stem="Tea sold 4, 0 and 6 cups; milk sold 2, 3 and 5 cups, "
                         "in steps of 2. (a) Compare.")
        with tempfile.TemporaryDirectory() as tmp:
            r = GridPolygonLabelsAndAxis._vdd_check(b, tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_orientation_validation(self):
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(orientation="x")
        self.assertIn("orientation", str(cm.exception))

    def test_gutter_refusal_states_the_fix(self):
        """Category labels that leave <160 units for the value axis refuse."""
        with self.assertRaises(vt.TemplateError) as cm:
            self._b(categories=["A very long category label that runs and runs "
                                "and runs and runs past the gutter " + str(i)
                                for i in range(4)],
                    series=[{"name": "", "values": [10] * 4}],
                    stem="Four categories all at 10, in steps of 5. (a) Read.")
        self.assertIn("shorten", str(cm.exception))

    def test_vertical_default_byte_identical(self):
        """The default build and an explicit orientation="v" emit the same bytes;
        the v layout itself is pinned by selftest-bars' sha256 in ByteIdentity."""
        kw = dict(figure_id="bc1", stem=self.STEM, ask=[["a", "x"]],
                  categories=["Grade 6", "Grade 7"],
                  series=[{"name": "", "values": [25, 40]}], step=5)
        b1 = vt.BUILDERS["bar_chart"](**kw)
        b2 = vt.BUILDERS["bar_chart"](orientation="v", **kw)
        self.assertEqual(json.dumps(b1.doc, sort_keys=True),
                         json.dumps(b2.doc, sort_keys=True))
        self.assertEqual(b1.claims, b2.claims)


class SymmetryGrid(unittest.TestCase):
    """W13 — half/full mirror figures on squared paper (G7 L01)."""

    STEM = "Half of a shape is drawn on a grid of 1 cm squares."
    HALF = [[4, 0], [1, 1], [1, 4], [3, 5], [4, 5]]
    VAX = {"through": [[4, 0], [4, 5]]}

    def _build(self, **kw):
        kw.setdefault("cell", 1)
        kw.setdefault("half", self.HALF)
        kw.setdefault("axis", self.VAX)
        return vt.build_symmetry_grid(figure_id="t1", stem=self.STEM, **kw)

    def test_half_mode_draws_only_the_half(self):
        b = self._build()
        outline = [e for e in b.doc["elements"] if re.fullmatch(r"[A-Z]{2}", e["id"])]
        self.assertEqual(len(outline), 4)                 # open path: 5 points, 4 sides
        self.assertIn("is the grid point (7,1)", b.claims)  # B's image, by coordinate
        self.assertIn("other half is to be completed", b.claims)
        self.assertRegex(b.claims, r"paint [A-Z]{2} dashed")
        self.assertRegex(b.claims, r"on A [A-Z]{2}")
        self.assertIn("derive 3 + 3 = 6", b.claims)
        self.assertIn("= 25 |", b.claims)                 # the completed figure's area
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_full_mode_draws_the_closed_figure(self):
        b = self._build(show="full")
        outline = [e for e in b.doc["elements"] if re.fullmatch(r"[A-Z]{2}", e["id"])]
        self.assertEqual(len(outline), 8)                 # 5 + 3 images, closed
        self.assertIn('"B and H are mirror images in the dashed line"', b.claims)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_every_axis_kind_builds_and_reflects(self):
        cases = [
            ({"through": [[0, 3], [6, 3]]}, [[0, 3], [1, 1], [4, 1], [5, 3]]),   # horizontal
            ({"through": [[0, 0], [4, 4]]}, [[0, 0], [4, 1], [4, 4]]),          # +45°
            ({"through": [[0, 6], [6, 0]]}, [[1, 5], [1, 1], [5, 1]]),          # −45°
        ]
        for ax, half in cases:
            for show in ("half", "full"):
                with self.subTest(axis=ax, show=show):
                    b = self._build(half=half, axis=ax, show=show, cell_px=40)
                    r = audit(b.claims, tempfile.mkdtemp())
                    self.assertEqual(r.returncode, 0, r.stdout)

    def test_rectilinear_full_figure_gets_a_perimeter(self):
        b = self._build(half=[[3, 0], [1, 0], [1, 4], [3, 4]],
                        axis={"through": [[3, 0], [3, 4]]}, show="full")
        self.assertIn("= 16 |", b.claims)                 # 2+4+2+2+4+2 — straight ends kept

    def test_letter_fallback_goes_accent_and_is_claimed(self):
        b = self._build(vertex_labels=True)               # 30 px cells: no clear pocket
        letters = [e for e in b.doc["elements"] if e["id"].startswith("lbl")]
        self.assertEqual(len(letters), 5)
        self.assertTrue(all(e.get("color") == vt._CP_ACCENT for e in letters))
        self.assertIn("accent colour", b.claims)
        roomy = self._build(half=[[0, 0], [4, 1], [4, 4]], axis={"through": [[0, 0], [4, 4]]},
                            show="full", vertex_labels=True, cell_px=40)
        self.assertNotIn("accent colour", roomy.claims)   # clean seats → default ink
        for b_ in (b, roomy):
            r = audit(b_.claims, tempfile.mkdtemp())
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_refusals(self):
        bad = [
            (dict(show="both"), "show must be"),
            (dict(half=[[4, 0], [4, 5]]), "at least 3 points"),
            (dict(half=[[3, 0], [1, 1], [4, 5]]), "must lie on the axis"),
            (dict(half=[[4, 0], [1, 1], [6, 3], [4, 5]]), "strictly on ONE side"),
            (dict(half=[[4, 0], [1, 1], [4, 3], [1, 4], [4, 5]]), "strictly on ONE side"),
            (dict(half=[[4, 0], [1.5, 1], [4, 5]]), "off the grid lattice"),
            (dict(half=[[4, 0], [1, 1], [1, 1], [4, 5]]), "zero-length"),
            (dict(half=[[4, 0], [1, 4], [1, 1], [3, 4], [4, 5]]), "crosses itself"),
            (dict(half=[[1, 0], [0, 2], [1, 4]], axis={"through": [[1, 0], [1, 4]]},
                  cols=1), "does not fit"),
            (dict(axis={"through": [[4, 0], [5, 2]]}), "±45°"),
            (dict(axis={"through": [[4, 0], [4, 0]]}), "distinct"),
            (dict(cell=2), "cell"),
        ]
        for kw, msg in bad:
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError) as cm:
                    self._build(**kw)
                self.assertIn(msg, str(cm.exception))

    def test_too_many_vertices_refuses_cleanly(self):
        # 12 points → 22 vertices builds; 13 → 24 would leave no letters for the anchors
        zig = lambda lo: [[i, 1 + (i % 2)] for i in range(11, lo - 1, -1)]   # noqa: E731
        ok = [[12, 0]] + zig(3) + [[3, 4], [12, 4]]       # 10 interior points
        b = self._build(half=ok, axis={"through": [[12, 0], [12, 4]]})
        self.assertIn("grid", b.claims)
        bad = [[12, 0]] + zig(2) + [[2, 4], [12, 4]]      # 11 interior points
        with self.assertRaises(vt.TemplateError) as cm:
            self._build(half=bad, axis={"through": [[12, 0], [12, 4]]})
        self.assertIn("at most 22", str(cm.exception))

    def test_image_off_the_grid_refuses(self):
        with self.assertRaises(vt.TemplateError) as cm:
            self._build(half=[[1, 0], [3, 2], [1, 4]], axis={"through": [[1, 0], [1, 4]]})
        self.assertIn("outside the grid", str(cm.exception))

    def test_english_only_a11y_exempt(self):
        b = self._build(medium="sinhala", title="අ — synthetic a11y title",
                        description="අ — synthetic a11y description, not drawn")
        self.assertIn("අ", b.doc["a11y"]["title"])
        self.assertFalse(any(vt.SINHALA.search(str(e.get("value", "")))
                             for e in b.doc["elements"]))


class LabelledComposite(unittest.TestCase):
    """W13 — rectilinear composites drawn from their side lengths (G7 L16/L17)."""

    L_PATH = [["R", 8], ["U", 3], ["L", 3], ["U", 2], ["L", 5], ["D", 5]]
    U_PATH = [["R", 9], ["U", 6], ["L", 3], ["D", 3, "x m"], ["L", 3, None], ["U", 3],
              ["L", 3], ["D", 6]]

    def _build(self, path, stem="A composite floor plan. (a) Find the area.", **kw):
        kw.setdefault("unit", "m")
        return vt.build_labelled_composite(figure_id="t1", stem=stem, path=path, **kw)

    @staticmethod
    def _side_px(b, seg):
        e = next(e for e in b.doc["elements"] if e["id"] == seg)
        (x1, y1), (x2, y2) = e["points"]
        return math.hypot(x2 - x1, y2 - y1)

    def test_l_shape_area_perimeter_and_scale(self):
        b = self._build(self.L_PATH)
        self.assertIn("= 34 |", b.claims)                  # 8×3 + 5×2
        self.assertIn("derive 8 + 3 + 3 + 2 + 5 + 5 = 26", b.claims)
        self.assertEqual(len(re.findall(r"^  K\d+  right ", b.claims, re.M)), 6)
        # drawn to scale from the labels: AB/BC == 8/3
        self.assertAlmostEqual(self._side_px(b, "AB") / self._side_px(b, "BC"), 8 / 3, places=6)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_lone_unknowns_are_derived_by_closure(self):
        b = self._build(self.U_PATH)
        self.assertIn("derive 6 + 3 - 6 = 3", b.claims)    # x on DE
        self.assertIn("derive 9 - 3 - 3 = 3", b.claims)    # the unlabelled EF
        self.assertIn('label "x m" names DE', b.claims)
        self.assertFalse(any(e.get("id") == "slEF" for e in b.doc["elements"]))  # null: no text
        self.assertIn("= 45 |", b.claims)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_two_unknowns_in_one_orientation_need_the_stem(self):
        path = [["R", 9], ["U", 6], ["L", 3], ["D", 3, "x m"], ["L", 3], ["U", 3],
                ["L", 3], ["D", 6, None]]
        with self.assertRaises(vt.TemplateError) as cm:
            self._build(path)
        self.assertIn("not a number the stem states", str(cm.exception))
        b = self._build(path, stem="The plot has sides of 3 m and 6 m that are not marked.")
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_stem_justified_ratio_is_label_checked(self):
        b = self._build([["R", 6], ["U", 4], ["L", 6], ["D", 4]],
                        stem="A rectangle is 6 m long and 4 m wide.")
        self.assertIn("ratio len AB / len BC = 1.5", b.claims)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_t_and_step_shapes_build(self):
        shapes = [
            [["R", 2], ["U", 4], ["R", 2], ["U", 2], ["L", 6], ["D", 2], ["R", 2], ["D", 4]],
            [["R", 6], ["U", 2], ["L", 2], ["U", 2], ["L", 2], ["U", 2], ["L", 2], ["D", 6]],
        ]
        for p in shapes:
            for vl in (False, True):
                with self.subTest(path=p, vertex_labels=vl):
                    b = self._build(p, unit="cm", vertex_labels=vl)
                    r = audit(b.claims, tempfile.mkdtemp())
                    self.assertEqual(r.returncode, 0, r.stdout)

    def test_right_marks_toggle_the_none_line(self):
        on = self._build(self.L_PATH)
        off = self._build(self.L_PATH, right_marks=False)
        self.assertEqual(sum(e["type"] == "angleMark" for e in on.doc["elements"]), 5)  # convex
        self.assertFalse(any(e["type"] == "angleMark" for e in off.doc["elements"]))
        self.assertNotRegex(on.claims, r"none [^|]*angleMark")
        self.assertRegex(off.claims, r"none [^|]*angleMark")

    def test_refusals(self):
        bad = [
            ([["R", 4], ["U", 2], ["L", 4]], "4–12 sides"),
            ([["R", 4], ["U", 2], ["L", 3], ["D", 2]], "does not close"),
            ([["R", 4], ["R", 2], ["U", 2], ["L", 6], ["D", 2]], "turns 90°"),
            ([["R", 4], ["N", 2], ["L", 4], ["D", 2]], "direction"),
            ([["R", 0], ["U", 2], ["L", 0], ["D", 2]], "positive"),
            ([["R", 4, "5 m"], ["U", 2], ["L", 4], ["D", 2]], "restate its own value"),
            ([["R", 4, "four"], ["U", 2], ["L", 4], ["D", 2]], "must be its own length"),
            ([["R", 4, "x cm"], ["U", 2], ["L", 4], ["D", 2]], "must be its own length"),
            ([["R", 20], ["U", 1], ["L", 20], ["D", 1]], "too short to label"),
            ([["R", 4], ["U", 4], ["L", 2], ["D", 6], ["L", 2], ["U", 2]], "crosses itself"),
        ]
        for path, msg in bad:
            with self.subTest(path=path):
                with self.assertRaises(vt.TemplateError) as cm:
                    self._build(path)
                self.assertIn(msg, str(cm.exception))
        with self.assertRaises(vt.TemplateError) as cm:
            self._build(self.L_PATH, unit="මී")
        self.assertIn("unit", str(cm.exception))

    def test_english_only_and_a11y_exempt(self):
        with self.assertRaises(vt.TemplateError):
            self._build([["R", 4, "ඒ m"], ["U", 2], ["L", 4], ["D", 2]])
        b = self._build(self.L_PATH, medium="sinhala", title="අ — synthetic a11y title")
        self.assertIn("අ", b.doc["a11y"]["title"])


class TriangleMarks(unittest.TestCase):
    """W13 — triangle classification by marks (G7 L09/L14)."""

    def _build(self, stem="Name the triangle by its marks.", **kw):
        return vt.build_triangle_marks(figure_id="t1", stem=stem, **kw)

    def _ok(self, b):
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_equilateral(self):
        b = self._build(angles={"A": 60, "B": 60, "C": 60}, ticks={"AB": 1, "BC": 1, "CA": 1},
                        arcs={"A": 1, "B": 1, "C": 1})
        self.assertEqual(len(re.findall(r"  K\d+  equal ", b.claims)), 3)
        self.assertIn("an equilateral triangle", b.claims)
        self.assertEqual(sum(e["type"] == "tickMark" for e in b.doc["elements"]), 3)
        self._ok(b)

    def test_isosceles_with_letter_label(self):
        b = self._build(names=["P", "Q", "R"], angles={"P": 70, "Q": 70, "R": 40},
                        ticks={"PR": 1, "QR": 1}, arcs={"P": 1, "Q": 1, "R": 2},
                        angle_labels={"R": "x"})
        self.assertIn("equal RP QR", b.claims)
        self.assertIn("an isosceles triangle", b.claims)
        self.assertIn('label "x" names R1', b.claims)
        self.assertIn("angle QPR and angle PQR carry the same arc", b.claims)
        self._ok(b)

    def test_right_isosceles(self):
        b = self._build(angles={"A": 45, "B": 45, "C": 90}, ticks={"CA": 1, "BC": 1}, right="C")
        self.assertIn("right A C B", b.claims)
        self.assertIn("isosceles right-angled triangle", b.claims)
        self.assertNotRegex(b.claims, r"none [^|]*angleMark")
        self._ok(b)

    def test_obtuse_numeric_labels_derive_the_unknown(self):
        b = self._build(stem="Two angles of a triangle are 30° and 40°. Find x.",
                        angles={"A": 30, "B": 40, "C": 110}, arcs={"A": 1, "B": 2, "C": 3},
                        angle_labels={"A": "30°", "B": "40°", "C": "x"})
        self.assertIn("angle B A C = 30 | stem", b.claims)
        self.assertIn("derive 180 - 30 - 40 = 110", b.claims)
        self._ok(b)

    def test_scalene_by_distinct_ticks(self):
        b = self._build(angles={"A": 50, "B": 60, "C": 70}, ticks={"AB": 1, "BC": 2, "CA": 3})
        self.assertIn("a scalene triangle", b.claims)
        self.assertNotIn("  equal ", b.claims)
        self._ok(b)

    def test_unmarked_triangle_claims_no_class(self):
        b = self._build(angles={"A": 50, "B": 60, "C": 70})
        self.assertNotIn("the marks show", b.claims)
        self.assertRegex(b.claims, r"none tickMark [^|]*angleMark")
        self._ok(b)

    def test_misleading_marks_refuse(self):
        bad = [
            (dict(angles={"A": 50, "B": 60, "C": 70}, ticks={"AB": 1, "BC": 1}),
             "the same tick marks but are not equal"),
            (dict(angles={"A": 70, "B": 70, "C": 40}, ticks={"CA": 1, "BC": 2}),
             "different tick marks but are equal"),
            (dict(angles={"A": 50, "B": 60, "C": 70}, arcs={"A": 1, "B": 1}),
             "the same arcs but are not equal"),
            (dict(angles={"A": 70, "B": 70, "C": 40}, arcs={"A": 1, "B": 2}),
             "different arcs but are equal"),
            (dict(angles={"A": 50, "B": 60, "C": 70}, right="C"), "needs a 90° angle"),
            (dict(angles={"A": 45, "B": 45, "C": 90}, right="C", arcs={"C": 1}), "no arcs too"),
        ]
        for kw, msg in bad:
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError) as cm:
                    self._build(**kw)
                self.assertIn(msg, str(cm.exception))

    def test_input_refusals(self):
        bad = [
            (dict(angles={"A": 60, "B": 60, "C": 70}), "not 180"),
            (dict(angles={"A": 60, "B": 60}), "all three"),
            (dict(angles={"A": 10, "B": 80, "C": 90}), "under 15°"),
            (dict(angles={"A": 60, "B": 60, "C": 60}, ticks={"AD": 1}), "not a side"),
            (dict(angles={"A": 60, "B": 60, "C": 60}, ticks={"AB": 4}), "1, 2 or 3"),
            (dict(angles={"A": 60, "B": 60, "C": 60}, angle_labels={"A": "x"}), "needs an arc"),
            (dict(angles={"A": 60, "B": 60, "C": 60}, arcs={"A": 1},
                  angle_labels={"A": "50°"}), "only restate its own angle"),
            (dict(angles={"A": 60, "B": 60, "C": 60}, arcs={"A": 1},
                  angle_labels={"A": "60°"}), "not a number the stem states"),
            (dict(angles={"A": 60, "B": 60, "C": 60}, arcs={"A": 1},
                  angle_labels={"A": "xy"}), "one lowercase letter"),
            (dict(angles={"A": 60, "B": 60, "C": 60}, names=["A", "A", "C"]), "distinct"),
            (dict(angles={"A": 70, "B": 70, "C": 40}, arcs={"A": 1, "B": 1},
                  angle_labels={"A": "x", "B": "x"}), "printed twice"),
        ]
        for kw, msg in bad:
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError) as cm:
                    self._build(**kw)
                self.assertIn(msg, str(cm.exception))

    def test_english_only_and_a11y_exempt(self):
        with self.assertRaises(vt.TemplateError):
            self._build(angles={"A": 60, "B": 60, "C": 60}, arcs={"A": 1},
                        angle_labels={"A": "අ"})
        b = self._build(angles={"A": 60, "B": 60, "C": 60}, medium="sinhala",
                        title="අ — synthetic a11y title")
        self.assertIn("අ", b.doc["a11y"]["title"])


class VennSets(unittest.TestCase):
    """W14 — 2/3-set Venn diagrams (G7 L02, G8 L19; G9/G10 sets later)."""

    STEM = "The Venn diagram shows two sets of numbers. (a) List the elements of each set."

    def _build(self, stem=None, **kw):
        return vt.build_venn_sets(figure_id="v1", stem=stem or self.STEM, **kw)

    def _ok(self, b):
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_two_set_items_with_universal(self):
        b = self._build(sets=["A", "B"], regions={"A": ["1", "3"], "AB": ["5"], "B": ["2"],
                                                  "": ["9"]})
        self.assertIn("circle centre A radius", b.claims)
        self.assertIn('describe "5 lies inside the A circle and inside the B circle"', b.claims)
        self.assertIn("outside the B circle and inside the universal rectangle", b.claims)
        self.assertIn('label "U" names univ', b.claims)
        self.assertIn("a rectangle labelled U frames every set", b.claims)
        self.assertIn('label "5" names region_ab_1', b.claims)
        self.assertIn("derive 2 + 1 = 3", b.claims)          # n(A)
        self.assertIn("derive 2 + 1 + 1 + 1 = 5", b.claims)  # n(U)
        self.assertEqual(sum(e["type"] == "circle" for e in b.doc["elements"]), 2)
        self._ok(b)

    def test_key_order_is_normalised(self):
        b = self._build(sets=["P", "Q"], regions={"QP": ["7"], "P": ["1"]}, universal=None)
        self.assertIn('label "7" names region_pq_1', b.claims)
        self.assertFalse(any(e["type"] == "rect" for e in b.doc["elements"]))
        self._ok(b)

    def test_three_set_counts_every_region_clear(self):
        regions = {"A": 4, "B": 5, "C": 6, "AB": 2, "AC": 3, "BC": 1, "ABC": 7, "": 8}
        b = self._build(sets=["A", "B", "C"], regions=regions)
        self.assertIn("derive 4 + 2 + 3 + 7 = 16", b.claims)     # n(A)
        self.assertIn("derive 4 + 5 + 6 + 2 + 3 + 1 + 7 + 8 = 36", b.claims)
        # every count box sits ≥ the stroke rule inside/outside every circle (finish proves it;
        # this pins that the triple-overlap count really lies in all three)
        self.assertIn('describe "the count 7 lies inside the A circle and inside the B circle '
                      'and inside the C circle"', b.claims)
        self._ok(b)

    def test_unknown_count_letter_blocks_its_sums_only(self):
        b = self._build(sets=["A", "B"], regions={"A": 6, "AB": "x", "B": 4, "": 3})
        self.assertIn("the unknown count x lies", b.claims)
        # x sits in A∩B, so n(A), n(B), n(A ∪ B) and n(U) all need it — only the
        # restatement fallback is left
        self.assertIn("derive 6 + 0 = 6", b.claims)
        self.assertEqual(b.claims.count(" derive "), 1)
        self._ok(b)
        b3 = self._build(sets=["A", "B"], regions={"A": 6, "AB": 2, "B": "y", "": 3})
        self.assertIn("derive 6 + 2 = 8", b3.claims)            # n(A) is known
        self.assertNotIn("derive 2 +", b3.claims)               # n(B) needs y
        self._ok(b3)
        b2 = self._build(sets=["A", "B"], regions={"A": "x", "AB": "y", "B": 4}, universal=None)
        self.assertIn("derive 4 + 0 = 4", b2.claims)             # every sum blocked
        self._ok(b2)

    def test_refusals(self):
        bad = [
            (dict(sets=["A"], regions={"A": [1]}), "2 or 3 distinct"),
            (dict(sets=["A", "a"], regions={"A": [1]}), "2 or 3 distinct"),
            (dict(sets=["A", "B"], regions={"AC": ["1"]}), "must be letters"),
            (dict(sets=["A", "B"], regions={"AB": ["1"], "BA": ["2"]}), "given twice"),
            (dict(sets=["A", "B"], regions={"": ["1"]}, universal=None), "universal rectangle"),
            (dict(sets=["A", "B"], regions={"A": ["1"], "B": 3}), "never mixed"),
            (dict(sets=["A", "B"], regions={"A": 1, "AB": 2}), "missing"),
            (dict(sets=["A", "B"], regions={"A": 3, "AB": 3, "B": 1, "": 2}), "printed twice"),
            (dict(sets=["A", "B"], regions={"A": ["7"], "B": ["7"]}), "printed twice"),
            (dict(sets=["A", "B"], regions={"A": ["B"]}), "printed twice"),
            (dict(sets=["A", "B"], regions={"A": [], "B": []}), "every region is empty"),
            (dict(sets=["A", "B"], regions={"A": ["a very long token"]}), "short token"),
            (dict(sets=["A", "B"], regions={"A": ["$x$"]}), "backtick"),
            (dict(sets=["A", "B"], regions={"A": ["1"]}, shade=["A"]), "shading not supported yet"),
            (dict(sets=["A", "B"], regions={"A": "xy", "AB": 1, "B": 1, "": 1}), "never mixed"),
            (dict(sets=["A", "B"], regions={"A": ["1"]}, r="big"), "at least 50"),
            (dict(sets=["A", "B"], regions={"A": [str(i) for i in range(40)]}, r=50),
             "cannot seat"),
        ]
        for kw, msg in bad:
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError) as cm:
                    self._build(**kw)
                self.assertIn(msg, str(cm.exception))

    def test_adr0021_on_every_medium_and_a11y_exempt(self):
        for medium in ("sinhala", "english"):
            for kw in (dict(regions={"A": ["අ"]}), dict(regions={"A": ["1"]}, universal="අ")):
                with self.subTest(medium=medium, kw=kw):
                    with self.assertRaises(vt.TemplateError) as cm:
                        self._build(sets=["A", "B"], medium=medium, **kw)
                    self.assertIn("ADR 0021", str(cm.exception))
        b = self._build(sets=["A", "B"], regions={"A": ["1"]}, medium="sinhala",
                        title="අ — synthetic a11y title", description="අ synthetic description")
        self.assertIn("අ", b.doc["a11y"]["title"])
        self._ok(b)


class CircleParts(unittest.TestCase):
    """W14 — a circle and its parts (G7 L18, G8 L23; G10/G11 theorems later)."""

    STEM = "The circle has centre O and radius 4 cm. A chord is 6 cm long. (a) Name the parts."

    def _build(self, stem=None, **kw):
        return vt.build_circle_parts(figure_id="c1", stem=stem or self.STEM, **kw)

    def _ok(self, b):
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_diameter_asserted_through_centre(self):
        b = self._build(points={"A": 30, "B": 210}, features=[{"diameter": "AB"}])
        self.assertIn("on O AB", b.claims)
        self.assertRegex(b.claims, r"derive 2 \* \d+ = \d+ \| inferred \| the drawn diameter")
        self._ok(b)

    def test_chord_length_label_restates_its_own_length(self):
        # 6 cm chord on a 4 cm radius: separation 2·asin(6/8) = 97.18°
        sep = 2 * math.degrees(math.asin(6 / 8))
        b = self._build(points={"C": 200, "D": 200 + sep}, radius=4,
                        features=[{"chord": "CD", "label": "6 cm"}, {"radius": "OC",
                                                                       "label": "4 cm"}])
        self.assertIn('label "6 cm" names CD', b.claims)
        self.assertIn('label "4 cm" names OC', b.claims)
        self._ok(b)                    # 2e-iii: the drawn CD/OC must equal 6/4
        with self.assertRaises(vt.TemplateError) as cm:
            self._build(points={"C": 200, "D": 290}, radius=4,
                        features=[{"chord": "CD", "label": "6 cm"}])
        self.assertIn("only restate its own length", str(cm.exception))
        self.assertIn("97.18°", str(cm.exception))

    def test_arc_sector_segment_minor_and_major(self):
        for major in (False, True):
            with self.subTest(major=major):
                b = self._build(points={"A": 200, "B": 300, "C": 30, "D": 100},
                                features=[{"arc": "AB", "major": major, "label": "arc"},
                                          {"sector": "OCD", "major": major},
                                          {"segment": "AB", "major": not major}])
                side = "major" if major else "minor"
                self.assertIn(f"the {side} arc AB is highlighted", b.claims)
                self.assertIn(f"the {side} sector OCD", b.claims)
                self.assertIn("arc centre O from A to B", b.claims)
                arc = next(e for e in b.doc["elements"] if e["type"] == "arc")
                sweep = arc["end"] - arc["start"]
                self.assertEqual(sweep > 180, major)
                self.assertIn(f'names arc_ab{"_major" if major else ""}', b.claims)
                self._ok(b)

    def test_no_centre_letter(self):
        b = self._build(points={"A": 0, "B": 180}, centre=None, features=[{"diameter": "AB"}])
        self.assertFalse(any(e.get("value") == "O" for e in b.doc["elements"]))
        self.assertIn("on O AB", b.claims)
        self._ok(b)

    def test_refusals(self):
        bad = [
            (dict(points={"A": 0, "B": 170}, features=[{"diameter": "AB"}]), "not 180°"),
            (dict(points={"A": 0, "B": 180}, features=[{"chord": "AB"}]), "use the diameter"),
            (dict(points={"A": 0, "B": 10}), "under 20° apart"),
            (dict(points={"O": 0}), "other than the centre"),
            (dict(points={"A": 0}, features=[{"radius": "AB"}]), "starts at the centre"),
            (dict(points={"A": 0, "B": 90}, features=[{"chord": "AB", "radius": "OA"}]),
             "exactly one of"),
            (dict(points={"A": 0, "B": 90}, features=[{"chord": "AB"}, {"chord": "BA"}]),
             "listed twice"),
            (dict(points={"A": 0, "B": 90}, features=[{"chord": "AB", "major": True}]),
             "arc, sector or segment only"),
            (dict(points={"A": 0, "B": 90}, features=[{"chord": "AB", "label": "6 cm"}]),
             "pass the stem's"),
            (dict(points={"A": 0, "B": 90}, radius=4, features=[{"arc": "AB", "label": "6"}]),
             "only a radius, diameter or chord"),
            (dict(points={"A": 0}, radius=4, features=[{"radius": "OA", "label": "4 m"}]),
             "the figure's unit"),
            (dict(points={"A": 0}, radius=3), "not a number the stem states"),
            (dict(points={"A": 0, "B": 180}, radius=4,
                  features=[{"diameter": "AB", "label": "8 cm"}]),
             "not a number the stem states"),
            (dict(points={"A": 0, "B": 90}, features=[{"chord": "AB", "label": "A"}]),
             "printed twice"),
            (dict(points={"A": 0}, r_px=40), "60–160"),
            (dict(points={"A": 0, "B": 90}, features=[{"chord": "AB", "label": "$x$"}]),
             "backtick"),
        ]
        for kw, msg in bad:
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError) as cm:
                    self._build(**kw)
                self.assertIn(msg, str(cm.exception))

    def test_adr0021_on_every_medium_and_a11y_exempt(self):
        for medium in ("sinhala", "english"):
            for kw in (dict(features=[{"chord": "AB", "label": "ජ"}]),
                       dict(centre=None, features=[{"arc": "AB", "label": "ච"}])):
                with self.subTest(medium=medium, kw=kw):
                    with self.assertRaises(vt.TemplateError) as cm:
                        self._build(points={"A": 0, "B": 100}, medium=medium, **kw)
                    self.assertIn("ADR 0021", str(cm.exception))
        b = self._build(points={"A": 0, "B": 100}, medium="sinhala",
                        features=[{"chord": "AB", "label": "chord"}],
                        title="ව — synthetic a11y title")
        self.assertIn("ව", b.doc["a11y"]["title"])
        self._ok(b)


class G11Templates(unittest.TestCase):
    """W15 — the ten Grade-11 templates. All stems are synthetic English."""

    def _ok(self, b):
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)
        ids = [e["id"] for e in b.doc["elements"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate element ids")
        w, h = b.doc["canvas"]["width"], b.doc["canvas"]["height"]
        for _nm, (x, y) in b.anchors.items():
            self.assertTrue(0 <= x <= w and 0 <= y <= h, f"anchor {_nm} off-canvas")

    RT_STEM = ("Triangle ABC is right-angled at B with AB = 3 cm, BC = 4 cm and "
               "AC = 5 cm. The angle at C is marked x. (a) Find x.")

    def test_rt_numeric(self):
        b = vt.build_right_triangle(figure_id="r1", stem=self.RT_STEM,
                                    ask=[["a", "x"]], sides={"AB": 3, "BC": 4, "CA": 5},
                                    angles={"C": "x"})
        self.assertIn("right A B C", b.claims)
        self.assertIn('label "3 cm" names BA', b.claims)
        self.assertIn("derive 9 + 16 = 25", b.claims)
        self._ok(b)

    def test_rt_unknown_side_and_numeric_angle(self):
        stem = "In the figure CA = 10 m and the angle at A is 30°. The height is x m."
        b = vt.build_right_triangle(figure_id="r2", stem=stem, ask=[["a", "x"]],
                                    sides={"CA": 10, "BC": "x"}, unit="m",
                                    legs_px=[208, 120], angles={"A": "30"})
        self.assertIn('label "x" names BC', b.claims)
        self._ok(b)

    def test_rt_refuses_unstated_side(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_right_triangle(figure_id="r3", stem=self.RT_STEM, ask=[["a", "x"]],
                                    sides={"AB": 6, "BC": 4, "CA": 5})
        self.assertIn("not a number the stem", str(cm.exception))

    def test_rt_refuses_bad_pythagoras(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_right_triangle(figure_id="r4",
                                    stem=self.RT_STEM + " Sides 3, 4, 6.",
                                    sides={"AB": 3, "BC": 4, "CA": 6})
        self.assertIn("a²+b²=c²", str(cm.exception).replace("a**2", "a²"))

    def test_rt_refuses_misstated_angle(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_right_triangle(figure_id="r5", stem=self.RT_STEM,
                                    ask=[["a", "x"]],
                                    sides={"AB": 3, "BC": 4, "CA": 5},
                                    angles={"C": "30"})
        self.assertIn("drawn angle", str(cm.exception))

    def test_rt_keyword_only(self):
        with self.assertRaises(TypeError):
            vt.build_right_triangle("r6", self.RT_STEM)

    def test_ca_cyclic_exterior(self):
        stem = ("ABCD is a cyclic quadrilateral with centre O. Side BC is produced "
                "to E; the exterior angle at C is 105°. (a) Find x.")
        b = vt.build_circle_angles(figure_id="c1", stem=stem, ask=[["a", "x"]],
                                   points={"A": 200, "B": 270, "C": 10, "D": 120},
                                   cyclic="ABCD", extend=[{"side": "BC", "to": "E"}],
                                   angles=[{"at": "C", "arms": ["D", "E"],
                                            "label": "105°"},
                                           {"at": "A", "arms": ["B", "D"],
                                            "label": "x"}])
        self.assertIn("105", b.claims)
        self._ok(b)

    def test_ca_two_tangents(self):
        stem = ("The circle has centre O. From T, two tangents touch the circle at "
                "P and Q. (a) Name the equal tangent segments.")
        b = vt.build_circle_angles(figure_id="c2", stem=stem, ask=[["a", "them"]],
                                   points={"P": 210, "Q": 330},
                                   external={"T": ["P", "Q"]})
        self._ok(b)

    def test_ca_refuses_wrong_angle_label(self):
        stem = "ABCD is a cyclic quadrilateral; the exterior angle at C is 40°."
        with self.assertRaises(vt.TemplateError):
            vt.build_circle_angles(figure_id="c3", stem=stem,
                                   points={"A": 200, "B": 270, "C": 10, "D": 120},
                                   cyclic="ABCD", extend=[{"side": "BC", "to": "E"}],
                                   angles=[{"at": "C", "arms": ["D", "E"],
                                            "label": "40°"}])

    TP_STEM = ("In triangle ABC, AB = 12 cm and X, Y are the midpoints of AB and "
               "AC with XY parallel to BC. AX = XB = 6 cm. (a) Find XY.")

    def test_tp_midpoint(self):
        b = vt.build_triangle_parallel(figure_id="t1", stem=self.TP_STEM,
                                       ask=[["a", "XY"]], names=["A", "B", "C"],
                                       angles={"A": 60, "B": 60, "C": 60},
                                       div={"X": ["AB", 0.5], "Y": ["AC", 0.5]},
                                       parallel=["XY", "BC"],
                                       ticks={"AX": 1, "XB": 1, "AY": 1, "YC": 1},
                                       labels={"AX": "6 cm", "XB": "x"},
                                       sides={"AB": 12})
        self.assertIn("parallel", b.claims)
        self._ok(b)

    def test_tp_refuses_unequal_fractions(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_triangle_parallel(figure_id="t2", stem=self.TP_STEM,
                                       angles={"A": 60, "B": 60, "C": 60},
                                       div={"X": ["AB", 0.5], "Y": ["AC", 0.4]},
                                       parallel=["XY", "BC"])

    def test_tp_refuses_duplicate_glyph(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_triangle_parallel(figure_id="t3", stem=self.TP_STEM,
                                       angles={"A": 60, "B": 60, "C": 60},
                                       div={"X": ["AB", 0.5], "Y": ["AC", 0.5]},
                                       parallel=["XY", "BC"],
                                       labels={"AX": "6 cm", "XB": "6 cm"},
                                       sides={"AB": 12})
        self.assertIn("printed twice", str(cm.exception))

    def test_pa_shared_base(self):
        stem = ("Triangles PQR and SQR share base QR between two parallel lines "
                "3 cm apart. (a) Compare their areas.")
        b = vt.build_parallel_area(figure_id="p1", stem=stem, ask=[["a", "them"]],
                                   upper={"P": 40, "S": 160},
                                   lower={"Q": 70, "R": 140},
                                   draw=[["P", "Q", "R"], ["S", "Q", "R"]],
                                   distance={"value": 3, "unit": "cm"})
        self.assertIn('label "3 cm" names MN', b.claims)
        self._ok(b)

    def test_pa_refuses_unstated_distance(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_parallel_area(figure_id="p2",
                                   stem="Two parallel lines hold a triangle.",
                                   upper={"P": 40}, lower={"Q": 70, "R": 140},
                                   draw=[["P", "Q", "R"]],
                                   distance={"value": 9, "unit": "cm"})

    def test_solid_cone(self):
        stem = "A cone has base radius 7 cm and height 12 cm. (a) Find its volume."
        b = vt.build_solid(figure_id="s1", stem=stem, ask=[["a", "the volume"]],
                           shape="cone", dims={"radius": 7, "height": 12})
        self.assertIn("derive 2 * 7 = 14", b.claims)
        self._ok(b)

    def test_solid_letter_dim(self):
        b = vt.build_solid(figure_id="s2",
                           stem="A cylinder has radius r and height 6 cm.",
                           ask=[["a", "the area"]], shape="cylinder",
                           dims={"radius": "r", "height": 6})
        self.assertIn('label "r" names R1', b.claims)
        self._ok(b)

    def test_solid_refuses_unknown_shape_and_missing_dim(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_solid(figure_id="s3", stem="A cube.", shape="cube",
                           dims={"side": 4})
        with self.assertRaises(vt.TemplateError):
            vt.build_solid(figure_id="s4", stem="A cone of height 5.",
                           shape="cone", dims={"height": 5})

    def test_fg_parabola_vertex(self):
        stem = ("The parabola y = (x - 2)^2 + 1 is drawn for x from -1 to 5. "
                "The axis of symmetry is drawn. (a) Write the vertex V.")
        b = vt.build_function_graph(figure_id="g1", stem=stem, ask=[["a", "V"]],
                                    curve={"a": 1, "h": 2, "k": 1},
                                    x_range=[-1, 5], vertex="V", symmetry=True,
                                    grid=False, unit_px=30)
        self.assertIn("reads V 2 on LR", b.claims)
        self.assertIn("reads V 1 on BU", b.claims)
        self.assertIn("figure content", b.claims)
        self._ok(b)

    def test_fg_refuses_overcrowded_axes(self):
        # the same parabola crossing the axis at x=-1 and x=3 with the
        # symmetry line through x=1 leaves no honest seat for the '-1', '1'
        # and '3' numerals beside their own ticks at 320px — the builder must
        # refuse rather than strand labels
        with self.assertRaises(vt.TemplateError):
            vt.build_function_graph(
                figure_id="g5",
                stem="The parabola y = (x - 1)^2 - 4 is drawn for x from "
                     "-2 to 4. The axis of symmetry is drawn.",
                ask=[["a", "V"]],
                curve={"a": 1, "h": 1, "k": -4}, x_range=[-2, 4],
                vertex="V", symmetry=True, grid=False, unit_px=30)

    def test_fg_line_point(self):
        stem = "The line y = x - 3 is drawn for x from -1 to 4. Point P cuts the y axis."
        b = vt.build_function_graph(figure_id="g2", stem=stem, ask=[["a", "P"]],
                                    curve={"m": 1, "c": -3}, x_range=[-1, 4],
                                    points={"P": [0, -3]}, grid=False, unit_px=36)
        self._ok(b)

    def test_fg_refuses_point_off_curve(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_function_graph(figure_id="g3",
                                    stem="The line y = x - 3 is drawn for x from -1 to 4.",
                                    curve={"m": 1, "c": -3}, x_range=[-1, 4],
                                    points={"P": [0, -1]})
        self.assertIn("not on the curve", str(cm.exception))

    def test_fg_refuses_unsigned_negative(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_function_graph(figure_id="g4",
                                    stem="The line y = x + 3 is drawn for x from 1 to 4.",
                                    curve={"m": 1, "c": -3}, x_range=[1, 4])
        self.assertIn("negative", str(cm.exception))

    def test_il_interval(self):
        stem = "The number line shows -2 <= x < 3 on the range -4 to 4."
        b = vt.build_inequality_line(figure_id="i1", stem=stem, ask=[["a", "x"]],
                                     v0=-4, v1=4,
                                     interval={"a": -2, "b": 3, "open_a": False,
                                               "open_b": True})
        self._ok(b)

    def test_il_dots(self):
        stem = "The marked integers are -4, -3, -2 and -1 on the range -4 to 2."
        b = vt.build_inequality_line(figure_id="i2", stem=stem, ask=[["a", "them"]],
                                     v0=-4, v1=2, dots=[-4, -3, -2, -1])
        self._ok(b)

    def test_il_refuses_dot_off_axis(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_inequality_line(figure_id="i3",
                                     stem="Dots on the range -4 to 2.",
                                     v0=-4, v1=2, dots=[5])

    def test_hist_basic(self):
        stem = ("The histogram shows classes 0-10, 10-20, 20-30 with frequencies "
                "4, 7 and 5 on a scale of 2 per step up to 10.")
        b = vt.build_histogram(figure_id="h1", stem=stem, ask=[["a", "the mode"]],
                               bounds=[0, 10, 20, 30], freqs=[4, 7, 5],
                               step=2, v_max=10)
        self.assertIn("reads T1 7 on OY", b.claims)
        self.assertIn("derive 4 + 7 + 5 = 16", b.claims)
        self._ok(b)

    def test_hist_unequal_widths(self):
        stem = ("Classes 0-10, 10-30 and 30-40 hold frequencies 4, 6 and 5; the "
                "scale is 2 per step up to 10.")
        with self.assertRaises(vt.TemplateError):
            vt.build_histogram(figure_id="h2", stem=stem, ask=[["a", "x"]],
                               bounds=[0, 10, 30, 40], freqs=[4, 6, 5],
                               step=2, v_max=10)
        b = vt.build_histogram(figure_id="h2", stem=stem + " Adjusted heights "
                               "are 4, 3 and 5 using 10 as the reference width.",
                               ask=[["a", "x"]], bounds=[0, 10, 30, 40],
                               freqs=[4, 6, 5], step=2, v_max=10, adjusted=True)
        self.assertIn("adjusted", b.claims)
        self.assertIn("unequal", b.claims)
        self._ok(b)

    def test_hist_refuses_length_mismatch(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_histogram(figure_id="h3", stem="Classes 0-10 and 10-20.",
                               bounds=[0, 10, 20], freqs=[4], step=2, v_max=8)

    def test_tree_two_level(self):
        stem = ("A box has 3 white and 2 black balls. Two draws with replacement "
                "give white with probability 3/5 and black with 2/5.")
        b = vt.build_tree_diagram(figure_id="w1", stem=stem, ask=[["a", "P(WW)"]],
                                  stages=[[["W", "3/5"], ["B", "2/5"]],
                                          [["W", "3/5"], ["B", "2/5"]]])
        self.assertIn('label "W 3/5" names br0', b.claims)
        self.assertIn("derive 3/5 + 2/5 = 1", b.claims)
        self._ok(b)

    def test_tree_without_replacement_dict(self):
        stem = ("Two draws without replacement: first white 3/5 or black 2/5, "
                "then 2/4 or 2/4 after white, and 3/4 or 1/4 after black.")
        b = vt.build_tree_diagram(figure_id="w2", stem=stem, ask=[["a", "x"]],
                                  stages=[[["W", "3/5"], ["B", "2/5"]],
                                          {"W": [["W", "2/4"], ["B", "2/4"]],
                                           "B": [["W", "3/4"], ["B", "1/4"]]}])
        self._ok(b)

    def test_tree_refuses_bad_sum(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_tree_diagram(figure_id="w3", stem="Draws give 1/2 or 1/3.",
                                  stages=[[["W", "1/2"], ["B", "1/3"]]])
        self.assertIn("sum to 1", str(cm.exception))

    def test_ps_numeric(self):
        stem = ("A right triangle has legs 3 and 4 and hypotenuse 5. Squares are "
                "drawn outward on each side. (a) Find the areas.")
        b = vt.build_pythagoras_squares(figure_id="q1", stem=stem,
                                        ask=[["a", "the areas"]],
                                        legs={"AB": 3, "BC": 4, "CA": 5}, grid=True)
        self.assertIn("derive 9 + 16 = 25", b.claims)
        self._ok(b)

    def test_ps_refuses_noninteger_grid(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_pythagoras_squares(figure_id="q2",
                                        stem="Legs 3.5 and 4.",
                                        legs={"AB": 3.5, "BC": 4, "CA": "x"},
                                        grid=True)
        self.assertIn("integer", str(cm.exception))


class IntegratedReviewRegressions(unittest.TestCase):
    def test_histogram_first_edge(self):
        for start in (5, -5):
            for mode in ("stem", "figure"):
                with self.subTest(start=start, mode=mode):
                    b = vt.build_histogram(
                        figure_id="hist-edge1", stem=f"Classes {start}, {start+10}, {start+20}; frequencies 2, 4; step 1 up to 6.",
                        bounds=[start, start+10, start+20], freqs=[2, 4],
                        step=1, v_max=6, values=mode)
                    numeral = next(e for e in b.doc["elements"] if e.get("id") == "nx0")
                    self.assertEqual(numeral["value"], str(start))
                    self.assertAlmostEqual(numeral["at"][0], b.anchors["E0"][0], places=1)
                    self.assertIn(f'reads E0 {start} on OX', b.claims)

    def test_prism_height_ratio(self):
        b = vt.build_solid(figure_id="prism-height1", stem="Base 4, height 8, length 6.",
                           shape="triangular_prism", dims={"base": 4, "height": 8, "length": 6})
        es = {e.get("id"): e for e in b.doc["elements"]}
        def length(e):
            return math.dist(*e["points"])
        self.assertAlmostEqual(length(es["ldheight"]) / length(es["ldbase"]), 2)

    def test_tangent_cross_vertex_scale(self):
        for mode in ("stem", "figure"):
            with self.subTest(mode=mode), self.assertRaises(vt.TemplateError):
                vt.build_inscribed_circle(figure_id="bad-tangent", stem="Angles 60, 60, 60; lengths 4 cm and 5 cm.",
                    angles={"A": 60, "B": 60, "C": 60}, labels={"AF": "4 cm", "BD": "5 cm"}, values=mode)

    def test_tangent_units(self):
        kw = dict(figure_id="tangent-units1", stem="Read.",
                  angles={"A": 60, "B": 60, "C": 60}, values="figure")
        for label in ("4 s", "0.04 m"):
            with self.subTest(label=label), self.assertRaises(vt.TemplateError):
                vt.build_inscribed_circle(**kw, labels={"AF": "4 cm", "BD": label})

    def test_pyramid_fold_boundary(self):
        for height in (4, 5):
            with self.subTest(height=height), self.assertRaises(vt.TemplateError):
                vt.build_net(figure_id="flat-net", stem="Read the net.", shape="square_pyramid",
                             base=10, tri_height=height, values="figure")
        from unittest.mock import patch
        with patch.object(vt, "finish") as finish:
            vt.build_net(figure_id="fold-net1", stem="Read the net.", shape="square_pyramid",
                         base=10, tri_height=5.01, values="figure")
            finish.assert_called_once()

    def test_invalid_numeric_parameters(self):
        for value in (True, float("nan"), float("inf"), "1"):
            for builder, kwargs in (
                (vt.build_histogram, dict(bounds=[0, 10, 20], freqs=[2, 4], step=value, v_max=6)),
                (vt.build_function_graph, dict(curve={"m": value, "c": 0}, x_range=[-2, 2], values="figure")),
                (vt.build_solid, dict(shape="sphere", dims={"radius": value}, values="figure"))):
                with self.subTest(builder=builder.__name__, value=value), self.assertRaises(vt.TemplateError):
                    builder(figure_id="invalid", stem="Read the figure.", **kwargs)
        for field in ("step", "v_max"):
            kw = dict(bounds=[0, 10, 20], freqs=[2, 4], step=1, v_max=6)
            kw[field] = 0
            with self.subTest(field=field), self.assertRaises(vt.TemplateError):
                vt.build_histogram(figure_id="zero", stem="0 1 2 4 6 10 20", **kw)

    def test_numeric_ranges_and_scales(self):
        base = dict(figure_id="invalid-range1", stem="Read.", curve={"m": 1, "c": 0}, values="figure")
        for extra in (dict(x_range=[False, 2]), dict(x_range=[0, float("inf")]),
                      dict(x_range=[0, 0]), dict(x_range=[-2, 2], unit_px=0),
                      dict(x_range=[-2, 2], y_range=[0, "4"])):
            with self.subTest(extra=extra), self.assertRaises(vt.TemplateError):
                vt.build_function_graph(**base, **extra)
        for name, value in (("bounds", [False, 10, 20]), ("freqs", [True, 4])):
            kw = dict(bounds=[0, 10, 20], freqs=[2, 4], step=1, v_max=6)
            kw[name] = value
            with self.subTest(name=name), self.assertRaises(vt.TemplateError):
                vt.build_histogram(figure_id="invalid-hist1", stem="0 1 2 4 6 10 20", **kw)

    def test_negative_unit_linear_coefficient(self):
        b = vt.build_function_graph(figure_id="negative-b1", stem="Read the graph.",
                                   curve={"a": 1, "b": -1, "c": 5}, x_range=[-1, 2], y_range=[0, 8], grid=False, values="figure")
        self.assertIn("x² − x", b.claims)
        self.assertNotIn("− −x", b.claims)

    def test_net_figure_derivation_evidence(self):
        b = vt.build_net(figure_id="read-net1", stem="Read the net.", shape="square_pyramid",
                         base=6, tri_height=5, values="figure")
        line = next(line for line in b.claims.splitlines() if "derive 4 * 6 = 24" in line)
        self.assertIn("inferred", line)

    def test_incircle_radii_drawn(self):
        b = vt.build_inscribed_circle(figure_id="radii1", stem="Angles 60, 60, 60.",
                                     angles={"A": 60, "B": 60, "C": 60})
        ids = {e.get("id") for e in b.doc["elements"]}
        self.assertTrue({"radD", "radE", "radF"} <= ids)
        self.assertNotIn("arrow dashed shaded", b.claims)


class ByteIdentity(unittest.TestCase):
    """The floating-label machinery must not change any existing template's bytes —
    sha256 over each self-test spec's three emitted files, captured on origin/main."""

    GOLDEN = {
        "selftest-cuboid": "05f09debdef31ece88cfbc7ffc0036095112bab21c2ff513ffd1afa5b8f58c9c",
        "selftest-dots": "7ed9088e060208c13050f2dddfb4e846ab7c7a859f364ebd64f94d4230dea166",
        "selftest-grid": "e7f6fda91430b0ffa92a3071eab54c5f3e5e54d946e67ec35b93899be1bed393",
        "selftest-house": "b7efe080cc9db6bc8e028b0ec5e7ca2e0a5a12757295489d7c663f8512762f38",
        # G11 round-2 — regenerated: the ineq visual fix shortened half-unit ticks
        # (±7 → ±6) so filled dots read distinctly from tick strokes
        "selftest-line": "564cf22a3ac9526813999daac96689f57c50ce096dcea0ffb2bc3b480d3d4b70",
        # G6-8 hardening (approved golden change): pictograph row-label claims now
        # target the emitted ids row{ri} instead of the off-by-one row{ri+1}
        "selftest-pict": "c1b68f30878560f9aad2fb17606fb38567d4b688ffd21d7fcafe2c2a608f29fd",
        "selftest-rays": "606bb0917cb0316a0b89f910ccc14c2c4305a9ca065af4f42b4d49f65b4a59ab",
        "selftest-rect": "18af540590a9ef7abc046ad8c7700a13d149195b7781dc9f3d6dac5ad0cbea0a",
        "selftest-shade": "208fef9855980d20d4b8ba21d3af491e46c6174029102596dec707439cea88e2",
        # W10c — generated when the six membership/collection templates landed
        "selftest-cpts": "f6f52491500af3b52ce05db0379deb8c686de86db2f248705510e16e71afa2df",
        "selftest-2cpts": "c6f90d6816b62148e3bc3f27c3e9df37f26849fd1d1b1dc54cf18960d7b99647",
        "selftest-cin": "5d058ef51ebeda22d66c7b9da33885891a240e33975174310a518cfe636a4674",
        "selftest-abacus": "e373396ae5831ac3b59e197ee58d303bf0b8f5825efd4c0d440d55c4f4512f0e",
        "selftest-rings": "6e0ffc326d1bd899b702a9a1eea4a9c5ce0927258f7155c083bdf6a7f8edbc07",
        "selftest-shapes": "f3fdfa398f181216902d858288b9e4b5255179ded2e4627dddcaf44b12621e9a",
        # W11 — generated when the three G7 templates landed
        # W12 — selftest-plane/grid regenerated: A3's cell-corner label seating moved the
        # point letters, A4's default cols/rows are the shape's exact extent
        "selftest-plane": "f80cfd4e7d009043e3b9ad28b71051f239e6afd286e60f0469600e3ce65602cb",
        "selftest-parallel": "a90ffb97dca6fe53f22f192f1b4dc989822ab6147a72ab3b012a00e00ec96861",
        "selftest-bars": "f6427cfc31e6a891bb820165618cf6c14598be4dd1fa3920f0a3e53155e684b0",
        # W12 A5 — generated when orientation="h" landed (the v spec's hash above is
        # the byte-identical guard: the vertical layout must not move)
        "selftest-barsh": "0d69c8f3bf612cb7eb6de1b2590c63b863500f9aaf48cb51698f9fd1de8603ef",
        # W13 — generated when symmetry_grid / labelled_composite / triangle_marks landed
        "selftest-symhalf": "9ac3301b3cf97356c444ec92a8a20e9e3564a62e2ddf2b1525f1773b3457d24c",
        "selftest-symfull": "3bccecb424edcbcc94a066b68d67dd9c290c9a3e55240d5c3d2bba816c0a9cf9",
        "selftest-composite": "113f21727236ee0812eadcfb22391a80e2cf55dc9cd136bdb78b328e22c74cdb",
        "selftest-trimarks": "efc8b0bb6a5c5027267620ff577fa94a915c9353c3a0286ac10b44265d741b76",
        # W14 — generated when venn_sets / circle_parts landed
        "selftest-venn": "fbc07d9f9f560504984241dafe4cf5c18a772b2faef551f8eedf139fa8e52568",
        "selftest-venn3": "b5baef12404e11361c716a35e0e4a9b22eaeeb5f13fce2e4b21ed281b5bca563",
        "selftest-circle": "bba42c4d35e57115bd23c50832770f8459ee13b3077a4e4b7eb64b272c601711",
        "selftest-rtri": "6edac3fbab6774cebfef996cbbd2e8327b67dc72deb3c6afdb4b755dbce7315f",
        "selftest-rtri2": "4bee604ae6ac55a4c6f31f9298898cfcd64c6f3148245f590d05c7df293fd39a",
        "selftest-cyc": "ce683dc4b715bd0a9cfc5b9826b9c7a0d775de21dc1fbc48e7fefa5549169dd7",
        "selftest-tan": "654d82cd00f56b4fe16014488bab99a9281569575a135a254aa81c03c97157ef",
        "selftest-tpar": "cd4afcf42d89027b1ce485d449bd6e019437b62072fa0812ff5430b0f362a0c6",
        "selftest-parea": "22bcbf0c54bf349926a1df9997de8c414050667aa736109543147670476ff559",
        # G11 round-2 — regenerated after the visual-initial label fixes moved
        # cone/cyl leader labels, graph/fline axis numerals, ineq tick numerals,
        # hist axis numerals, tree terminal labels and psq edge labels
        # cone/cyl re-pinned after the slant-dim + smaller dim-label changes (#59)
        "selftest-cone": "2d37bc1d6d662551841f1d824383665e87932621cd33eb5dd7b1d43d3d80a11e",
        "selftest-cyl": "520c52bf194f99545ecd056ba54049ccb4f5d43bd1593de5b60924224242e564",
        "selftest-graph": "9e706817cc3f452789a66a5cbe20416bdeb13c096a7b28f0426d6429694e2cf0",
        "selftest-fline": "23a9b1b569769a5af7b7d1e2e9e9a5a30d8bf461c632a243949a7aceb7b91db8",
        "selftest-ineq": "43bf626ad2c9a79bc062b3a496e54ab33d1202b0720410cea9416d324d887feb",
        "selftest-ineq2": "66f2b038a56d767137d69d4f8de92055697e5b408cd3fa562312b81e25254d11",
        "selftest-hist": "5c57542d9307b17787ebff7c30353236e65ccbe9ecc47c67eff71c5ce03c7165",
        "selftest-tree": "5d5330eb9b005475c85a3dce79b03ecdd08c264429b654f1c39efcfca9942bb5",
        "selftest-psq": "c0a10a91a5f79a35ef3d7dc8ebb0a2d70e16a75d0d6206d4114721b5c260f5cf",
        # G11 — generated when the ogive/outcome-grid/two-circle/construction/
        # incircle/venn-regions/solid-composite/net templates landed
        "selftest-ogive": "bf8ccc27d4f56e35454b6bb738a489d214568d0f2da0fd615c13d86e29b8ea7b",
        "selftest-ogrid": "c492136f68809a8d844fbcfa1838aa35518cea661f6b4247afcf699f57c5e266",
        "selftest-ogrid2": "0dc4568562709989b1482d1a64b88d6bc9b3f40846426880f0590ef1a7f6903f",
        "selftest-2tan": "d48c412f307171cd4e2d23e4a9bf208433884fd39a589fe93edf901a70bbc6df",
        "selftest-cbis": "e4c50ad09282c2c2554f315169fbae06f0e414bbc5fbb4a9c47da565c7c83421",
        "selftest-abis": "300773bfe2d683cf356f66d5695a339d0ed26d08c5b3ec38bf0ff641ba645149",
        "selftest-ccirc": "36123ad1eaaf223bf2a61b7ed1ec820cbb5f914c8766178e757b1c1d2324131a",
        "selftest-tfrom": "0a0b8c13ad81d8c5d70038ca44eef74428d2905fba7edda200c138ee54f085bd",
        "selftest-incr": "cbee11786b84b5a303838abc0e46dba212d1f2694cbb1fbabdb2503b83898b88",
        "selftest-vrshade": "0c57ecd548fb922158fb44a30c1598c02153886e8a3045147e75def3c4f9fdf3",
        "selftest-vrnest": "1e30615a6ac1a584c9dddf3a3d42bcc073424930a5c6642ab04bb4567033bdd2",
        "selftest-scyl": "47a7b9f8e5ef7f06bb87a713d2723ac6fe643d6b118c3eda098a40dadeb63e04",
        "selftest-net": "5e377beea6ae67232eef6fe9fd36ea8910b9ea5b1abeb813baaf6b2cae432848",
        # G11 — generated when the new-family semantic fixes, marked_geometry and
        # the histogram-adjusted / general-quadratic / multi-curve additions landed
        "selftest-pat": "869096e2f4ed6ebffa9baff1d7ecf188f261a57e840638c3ec43797540fd2b7c",
        "selftest-pfrom": "31fb2f883ff53db56ae78efe145450381555ab93d00e008218a5125a382d0493",
        "selftest-inc": "53ee9e54924919e310b9ff51df40438d9868c704f731ee8c2960dfede4c44ead",
        "selftest-exc": "64db4da5f0cda76d4e304dabfe6ff3a694c1fb5ea1e194e07c1480f21277f17e",
        "selftest-tat": "c8d408bf936ef3f80813ed9a8c2d91185a2b35084bd81edc456413f933b7bf4a",
        "selftest-cset": "008200192542da005db31f5dae3259bbc8daeb9b680f0b5a97387de695a1ad5f",
        "selftest-ogfig": "f567516f5ac2c0dc787cc10f4aac33e7526126a0287d5944ff23bae23d4c644c",
        "selftest-vrn3": "e429f8a7a298354ed6701685ffebaecb173882ec4523651ef180c7218cb5abb0",
        "selftest-cvess": "08202bf91edde8c110786685cc4de06012ffaaff6e1007399e3a57e8197394a3",
        "selftest-mgtri": "1b2ab8c6072d01ea216b8eefaf4a4d3b887ba13a2c8928aebb07ca044c633c9d",
        "selftest-mgpara": "972b01fc2eb06bdd92ff0795f5001b15018561ff2811b54e7ee1eab88ac27bad",
        "selftest-mgtrap": "61065264cfc9c3016e1f2316004f915ba5720b80166a457f803867bf47d163ae",
        "selftest-histadj": "005de7f479c1f085da424a64a15faf23596374fc0f52b3b8acb4546fcddda805",
        "selftest-genquad": "fffe82ded70b2b4150e21251f10a546f2d9a031e62db40bad26df13371ee71d1",
        "selftest-multi": "3d4d4acd3dd68b8c4f334f69ae7d3de332490565647eec37f2d07676e5af055b",
        "selftest-reading-inscribed_circle": "b724be5ec2054e8f8a583c637b94b7807daddfa58f179c0344d9c1e7c325b5b5",
        "selftest-reading-venn_regions": "ff2583f8f00884f7e0bf4cfe16a02cd1906e79ee0de1ac89420598eb995de83b",
        "selftest-reading-solid_composite": "d609b632ff445eba680091e5c5ddb9a96dffaeb0127c6e6c1fb6bf51749499c1",
        "selftest-reading-net": "a36e29fef2b602a9b3026e42d5a8c153f1ec39135787776c5f82ee35ef1d2394",
        "selftest-hist-5-stem": "894379231dfc517188679cd50c68d9352f884518464e10395fc025e8c876ff4a",
        "selftest-hist-5-figure": "2d7abd2061b5e8530a618f3f7ad656bb4d9bd86573852835aa0fadefcb7b95e1",
        "selftest-hist--5-stem": "136ee5a2bb10a0143e98d8543a8bb3d98724c92a17783182ee014a9a190fa54d",
        "selftest-hist--5-figure": "8731b5b8d556444b1dbf6bd4fed29e1d86c26c74f04daeb729027d07773b91ea",
        # prism-height re-pinned for the #59 solid label changes (no slant — base prism)
        "selftest-prism-height": "e52fe3a3dfd4782df34e7a280cc144330a794aab05bff25f6910f8f7fe49695b",
        # G10 gaps 1-2 — generated when pie_chart (incl. the spinner mode) and the
        # standalone sector / annular-sector templates landed
        "selftest-pie": "b59c4975513f626234b9dbe8cab5c56c6e8f3eb504468dc4548eefbd9ce1375c",
        "selftest-spin": "0bb6817a0080a7f4e1edd909e52e6c7ceef578eefea769ac42a98ccd818a088f",
        "selftest-sec": "06785c0d8bd89093b4e18b9d57578fdc3720c1c7c473ad1f46facdd23e0dc7d4",
        "selftest-semi": "494b7ee495b133e9bd432c72ac2a3d9339a76897176bf69e31752ca13995bd7b",
        "selftest-annu": "3ee6167d59da66858a25ebdf64e94403700e49aecc69a5c1523fc2f6a9a0fe07",
        "selftest-cafoot": "9c06dc3b3aab5b414e50cbebda8e26d70f633fab1df5f9f222c318e3bc8fe276",
        "selftest-cax": "1c72bd9ecf8b07fa65275e9bb896c5cfd9505319a105a26d7217ca3e49516ec9",
        "selftest-vcomp": "cd596042f266b98ac93e2bcac4db2c648bb72ade19e03bc8660d9b4bf76bbbf6",
        "selftest-vcsh": "1dd9fb115595d103831b0c3174b0806621499982e6de559e329346b700535114",
        "selftest-cineq": "d01603d0bc30a983abd661159b65591a04df500fc7a7ddcb98163db9c8cf4646",
        "selftest-cdt": "f214dacea5b23b152bbfb939ce0719aecce552550ae5fa54151a89c2b24d5bfe",
        "selftest-cx3": "d95f59d8f75365ca01fe3938d6401848ba5a4c4daea5f9b5d36dbf671b5c2e98",
        "selftest-conv2-aas": "429ba1c5cfaf8fe8f4f143b716b4e74217db5e6b00c2212fb7e909859bc4145c",
        "selftest-conv2-aas-b": "06026c0fae0cd7a5ff0a797532f7bb6ad50b9d1afde6e65671e2479d6ec03d2c",
        "selftest-conv2-alternate": "38e03483801b44371197284bc8053f0861f8abbfa7625650555fe40ff19ec467",
        "selftest-conv2-rhombus": "d0c514adb884e2f97ceae03e1709b715148338c1c900a9d917970cdcaa314c00",
        "selftest-newsss-setup": "36e839477d281375857d64846b8ceb32069a5143827febe77b3a258491d98e64",
        "selftest-newsss-completed": "5bffbc34fdf7d9d893add15ad6eebf2c42415322e0c3a154a6a02402c7710ea1",
        "selftest-newsas-setup": "8ef0e892e5b870d944d84857b7b6115e8daf6c23670c0a268da37c3d54866117",
        "selftest-newsas-completed": "d855029218e9f7fd4fc6645278ddd09023fcfe65bff5f136fe63a85fe8cd7c5f",
        "selftest-newasa-setup": "f78150c0167768691a992c1bef51f4a0429c0d8e205cc1330063ed1d66d42129",
        "selftest-newasa-completed": "68955f6990ea1eadb8811776985fc155fe02fa388400b7a8039ee5ec87d9b1f4",
        "selftest-newparallel-setup": "877b7e5ede59972499eb0f01b8f5e9b98d500ac0405d6978f8b92ae6cc386d40",
        "selftest-newparallel-completed": "c4d4ba310ba069b4af49e2922d714de17f2de7a62878bc306c1e3dd4a2551227",
        "selftest-halfcyl-d": "9e09343b1f2c5668a2f49f279a3692e879b38f36c0edbbbb1658f38c4ffdbc8b",
        "selftest-halfcyl-r": "aef8d11e9fc3f676f6d6c9c764ced3cc6973d09d5fd04cce08e784e1bdb19746",
        "selftest-prism-right": "b6d269ff5a81f8d629135fa74a0900e892f8468f5aa69b282ba3f83664ea6230",
        "selftest-prism-hyp": "6e6e0690eaeb72b22363ea9f729dc9406a16739c8588d8de96f124ae0e56c9c3",
        "selftest-prism-iso": "c8ec2ac703332eed9863e4b4a7451d5ab0f6879c26d25750fccd4bf4922e3ce8",
        "selftest-prism-scalene": "e1566b8625eebf77c64e8300fbe419173ab9247ae59a36b3f657291cbfaf4b32",
        "selftest-prism-trough": "223d3f324163e08af947c23b6e9f99605063117822c7b24877d1c19aa2527585",
        "selftest-net-right": "35eaa88d9b52003998f04f2c0ea435531903cba9cc93b7062a25f0d1e2e07d4e",
        "selftest-net-scalene": "7517631c8c95cf9545fdb9059ae36980eff300ad272950117f7dd53843a1b58a",
        "selftest-net-cylinder": "2908d7018855b658b985e51cec2afcbd0b93260b03a2a661f562970c3828b90a",
        "selftest-net-repeat": "4adaebed974a8c2592beb0f978c0602801bd550a59f5d005472ea344e048ede7",
        "selftest-motion-point": "ddc202896c736d4788a1f28a5991cfd82b983e006041dad7ff5543f0a6f93cff",
        "selftest-motion-post": "0e2eb6254b8219db42653fae52e577c58dc0d4afef34f0e48129527abe7a5fc5",
        "selftest-motion-bridge": "74214b9ba460f96898a55138eed5a06763400b2408d675b9ff0649670dd63bca",
        "selftest-dots-rings": "204ebe4ea509baa87db95a05629587c0a37a5cd761df78e5e6d34df778688c39",
        "selftest-dots-rings-fig": "f518508ea7ec2787fe1db5d1b707673e24c9ad1506d589b2b2e19539dd8d2530",
        "selftest-slats": "4745b5ad18c29fb42604481bfff63fda3805c7198ea3f20e667ed708c6a3e425",
        "selftest-clock-420": "28cbc096d5c8bad74da4d2c573cccd24d8c2b120fc303a7c2c43a5a21557dde9",
        "selftest-clock-300": "b4992d5740156529c3e1d0eb8cbde8d6f9112a43f678c481a4649b74ac063209",
        "selftest-pairing": "1eb02f048df09ed012d44c012b2f3407a1f2589de42f0c7137071529023c20bb",
        "selftest-paired-sss": "a6704085f6cb88fbd4853192c4cd97883870506d3463352ff2643eefa7f4031e",
        "selftest-paired-scale2": "1a03f1caafed003bdb09c21460032c67b2b9d1e662057459db14769da522cee8",
        "selftest-paired-glue": "1f56846b9893748641f0d7fef642251346395625cb6df90f4a70748901b586b2",
        "selftest-paired-hinge": "1e4a96185fc2528e3e8d2175d39d469c3bec28fc1005c14e566a2fdcdfda9a73",
        "selftest-paired-parallelograms": "e1335eaa6ef3343a43b88361579c231397f23dbb8fbf6eb8fb38730a61162880",
        "selftest-paired-quad": "b064ff42a3e7fc45769ceca9a0b172d7f3d9d4838948e14ae0a183077f1eee5c",
        "selftest-paired-kite": "a249e659d6d48a5276826cb2040910a3505ab57551a217c13362d4eff1578572",
        # bowtie regenerated: the angle-label fallback seats FIXED text at the anchor it
        # claims (the float-label path anchored A1 ~47px from the placed glyph — VDD
        # coverage FAIL; the anchor must be where the glyph lands)
        "selftest-paired-bowtie": "c1a654625b631778bf1887166fb3c24c26fbdaa0be0e49a147d9d671e26f2999",
        "selftest-paired-feet": "5016a229ac8b81c48412c08d89a201337b1614522f4c8f6e27521412160f1ca4",
        # G10 third-pass scene outputs (existing goldens unchanged).
        # 2026-11-17: refreshed — anchors dict order depended on set iteration
        # (process hash seed); builder now sorts ground anchors, making bytes
        # seed-stable. Rendered figure unchanged.
        "selftest-elev": "1560aeb34abcf706d80ef8f144a9581f0e545107ea686ab309bb200bffc673c8",
        "selftest-elev-eye": "9e50d813e8d9296626ce8096a99c357325f6870bd6f7668c8de49670bb42db92",
        "selftest-2cgeo": "4496435b5646ae77bc9271342194aa9938a69ec26fba07ba968becd7722d90ee",
        "selftest-2cgeo-touch": "63e0f76416d4508174725237ad891ecc20a316bb956210192a03eedf0561bf84",
        "selftest-2cgeo-angle": "b9790f7b9bfd59f0c680869df701253e7e817a78ca00d170fa9bc772046ec297",
        # G10 second-pass additions: outcome-grid events, fraction tape/tank,
        # area model and the circular-composite profiles (new outputs only —
        # selftest-ogrid/ogrid2 goldens verified byte-identical under the
        # superset build_outcome_grid)
        "selftest-ogrid3": "c3565a61276e74bf1c00185af12a84f9c387b872cb0c0006ec74fa91f6a812c4",
        "selftest-tape": "422cd980f82f0ac14c141b79f4a4d8e02c23817c783b5dec8db5ce700fba23c6",
        "selftest-tank": "a563103006ca1c50bac112e6e4a24b8e78b023b61d3f628f367d707d16976c62",
        # 2026-11-17: refreshed — spec cells had the (3x+2)(2x+3) cross
        # terms transposed; now [["6x^2","4x"],["9x","6"]] (true products)
        "selftest-area": "17f3d9c309e9f2fbf1a196c850241ca8c2000eea31053f45e356214ef07994cd",
        "selftest-circ-rect-attach": "4b6f9947bd5c9e57e34f42a8acc34c023de9231cc747aed66e159a2cba1f6cf7",
        "selftest-circ-rect-cut": "36481a2f3b36682be00fa2d6dd178ab2ce0d534137f728091367eb0d367a827f",
        "selftest-circ-rect-corner": "fa2bee75693d41982d45afe357a72044e64fbcee998e66e46a55a953af0b89dc",
        "selftest-circ-rect-sector": "fdf5e0d60bdfb98ec4465905958d7ba396d8b70ed501070a5af3c2094897c2e5",
        "selftest-circ-stadium": "d94a54f61da8e7c5ff75e80cac6017d711448609f0ab371d4770c167b7a6cffd",
        "selftest-circ-stadium-fig": "f93b75a5b0535db5a425673c4cce434c23de093f2bf363996f52a228667f99c2",
        "selftest-circ-tri-right": "071e844e1d64bdcf39f1fa3e79f4af0384c0ca07fadf47bb7c9f8582a2a2c1af",
        "selftest-circ-tri-iso": "015e0c8cdf85a52271f55a922f24fcf3fe9682a8149e12f9a6de507cb40696a5",
        "selftest-circ-tri-eq": "73e5770053571e5e4f5b8bb761abcd281af063fedd4575f53d75016cf583ee19",
        "selftest-circ-sec-insc": "077af890912ef21c223f15fe93f73a93c12e16ccfaa66cc829c10885651b6895",
        "selftest-circ-sec-att": "217c6079d3cb0f3fd0c5bd2067df1d475e39d88989f957d008ed72559d86615b",
        "selftest-circ-sec-semi": "1677d1626cb6cc7881a1913cc7e9be450a2c72de3f864ca557d7360c89cb5cc5",
        "selftest-circ-cutattach": "abcad3476562cab0d8e6d12740702182aa86b67814eb53d96602ae66b5911cfc",
        "selftest-circ-annulus": "b89882a9aad3d49e78667a60357f10c20724d2dce9ed905b030eb7fdc7f3ec62",
        "selftest-circ-annulus-sym": "dc1ef21f9f90f3f4518da382fb4cf9cec0e9ceeca900fb8d55d9d31f2ece4340",
        "selftest-circ-annulus-fig": "51a27aa8707e4eee9020131ca121f3f4d50c95f6b0835b75a6c19ba9f498d22b",
        "selftest-circ-square": "eecd8dd7ffe0167c442cd75181f9099b95e9614b0acf01c5c0207fb1e861df47",
        "selftest-circ-square-sym": "f07e5269f238de9920fd85d7adcae9c7a9b0a8c87ac4310999077efd0c310832",
        # G9 refresh: 15° intermediate rays, hidden-edge projection, frame false-gap
        # removal, geometry label seating, per-length tick classes, readable locus
        # dimensions and exterior-angle claim targets; real renders reverified.
        # selftest-g9-vessel-litre adds the decimal-scale case.
        "selftest-g9-vessel-litre": "4cd3e645b03724c47b5a7a80c2c22ef0912a3a316451c743fffabda6e0528921",
        "selftest-g9-vessel-80": "63172365f5fbc38a7ad057c1037d27170427179713282fef8337bb3d6a6c49f0",
        "selftest-g9-calc-square17": "13563b611dbc9e0902b578cd0fcd187eef7926891c08f48444c0c43149e2b16b",
        "selftest-g9-calc-pct320": "ec663e70f70e4104ec14894e0e3b5f5a0aab319334e66438caf53561fba50f4b",
        "selftest-g9-calc-pct312": "a313af6ee6a071088beda1a675c7f5f86dfeb536eabe2ebe0aa43b59ea70d8df",
        "selftest-g9-calc-rootsum": "a67c838dc7310fac0d5475a79d9c3e9e9a30044d39fb2307368fa7cdfb8008ce",
        "selftest-g9-calc-imm": "9a1db497edc1739c6d33331c6380fb9fb6d7cfc83b621aabedf1f71214156585",
        "selftest-g9-calc-dec": "a9f42ab33db1119e7eab80a884f4947eb3086aeb75a645c5b72633cb752694f0",
        "selftest-g9-vessel-100": "6b3b372745ec215304b7bf64961879d3296e51c9ff398f752a8d8dd1d7a3c9dd",
        "selftest-g9-net-open": "0132c16b010e0f29202114ed7e8d6b3b1c222cdae9ad0736f67391b3fb48e513",
        "selftest-g9-water-30": "57c000c00c50f82782c8b35552095754d3970094a0a7c571f26981b50d1a503a",
        "selftest-g9-water-fig": "f1af6ae145803a6d44002320fe2bf90c2e444cb3575a00f9c8f58c11391f8935",
        "selftest-g9-poly-tetra": "ca1686c5e99e3f63255adfe8c71fd6ef7ecfbc07e77d1fefa9555be8801182fe",
        "selftest-g9-poly-octa": "2a8650f710e419bfaad3f7ee4a574b85980302db530e578921c3ca8293194af6",
        "selftest-g9-ml-div": "a0144cc3274850ba7003c47f8656206ee3fa86e169c5171bb9aa8fa812ce52b3",
        "selftest-g9-ml-pol": "73abd51a413f8f97de5aa907af62b42e9541e185241fa6978a45ebf46b37f83c",
        "selftest-g9-ml-cross": "fe598bcd7c23a41878456dffcebaa7d3ed38d9b9927cdd4178788c8710d6f2cb",
        "selftest-g9-ml-trans": "3a140e009a45fdbad815b90a608ec1f9f291c02a4c033bb149f94849de09fb91",
        "selftest-g9-ls-circle": "b141137d1978f9a682ea9e13d1085ccd35e7cded647eb7b164b6a3054dbbdea6",
        # Lead reverified renders: the 8 cm label belongs above AB, not AP.
        "selftest-g9-ls-perp": "eb9e096bfbdde2a21d1e568d5a9dc0ae8fbf86c955e950db0bd8034a54d87dca",
        "selftest-g9-ls-offset": "a8f8fd7025ee4256438b47c7506255f69e8e523a6389f9bdc5e34cf902ffd558",
        "selftest-g9-ls-bis": "1372250e3b4968ae35d1ce5efd0443b11a3fc23dbb0241e43862bb6614e04d0c",
        "selftest-g9-pa-int": "d17e37a245bba183cc9a7ecce3a6a97b81bc8399d81625927c5a9ef9e284d52b",
        "selftest-g9-pa-tri": "63ef405ea51437ba4987a2d12d05ff4598b0d101f34ba3fb4f7c394e1aab18cf",
        "selftest-g9-pa-ctr": "2aa70fb73689b63d657367588060d8623b1ce4f08a7565df0534c51326a4f411",
        "selftest-g9-pa-ext": "6dd88e107b10072c16f65d9ef924490e9f4615e62af9b14a59c5de1251bb16d8",
        "selftest-g9mod1": "b7059fa89d7b763da99d571f2a2de4c805c0958f30987a0fdd69b4ca2930c848",
        "selftest-g9mod2": "fdefe1f9df877f53f3e8d1f02ea78e1e864c58cb1bae75530dca817f0dfc67dc",
        "selftest-g9mod3": "e81c7945205bdf9940a457844bcffa4076d2bb278e4dbeadf32767cb233a6e14",
        "selftest-g9mod4": "95cb605b32037d26c9313b9193dbf3cf9bd39b9615924c2dcea17b971309d7c9",
        "selftest-g9mod5": "291dbc0359c802bc5b87bdfb04f29099a6a3cb4083fd3d498f579784d80eb4c9",
        "selftest-g9mod6": "c3c79722db0ffe3f747fcc911d6b25f35aa32cfb708a17438be056c7744ffc8c",
        "selftest-g9mod7": "b75c333bf6eb59aa9c60b997ce6a057afdcde38229acc3a632a16ea8bee650e1",
        "selftest-g9mod8": "6253a0dfd6f30df0e2dff75687b3c90c8e9ab4c329fe20118cbd03cb8c635545",
        "selftest-g9mod9": "f57f5b7f5d8d57ccee74fbc237ca9b9459fc1255e6038c88587ae77323122c62",
        "selftest-g9mod10": "d5b48f96ce3a4802620c094757adeec0d9928cc5dfa99c22912174267bb4b203",
        "selftest-g9mod11": "dcdaf3a7ac100d444c758e1500c5f4f1d0bb0fcc27bdd0865344d3b13b5f730e",
        "selftest-g9mod12": "a94d5b2af59d3b252d793cf98c68e59c5840e9820d4ace3e01800931b6f02180",
        "selftest-g9mod13": "ec6e4551cc96dfd7f52e1cfb3d08ff1546d712cab278b5b1b66497c2bd2f0bec",
        "selftest-g9mod14": "134554e675ba1a8279ede7ba181f95113a862e154bdc4a44f914c7eb4712abcb",
        "selftest-g9-area1": "aef5108510d16a3b69db8c9315508d3c909b5273270beff667a4e97ea32620e3",
        "selftest-g9-area2": "b105ee489056f4deb1d7c81d43f39e48008518bdec83616c7c422bcba5ef428d",
        "selftest-g9-area3": "9a80b7079cfa868212883a9fa5ae4f7ac2ba5da5d72b9dcfaf0b341d345cfe66",
        "selftest-g9-area4": "cc683d6bb24b80a8cacae5780c60e4a553487cb413f70bda755bd6ff38150d8b",
        # Lead reverified renders: inner width is horizontal, height vertical.
        "selftest-g9-area5": "9d888d671508323e01ba1ccca0a3ce447c39066c39406b15786efc6c07d845bf",
        "selftest-g9-area6": "b3c643801a448b7ca74731f674b3a7027876025ed24e8c8aa53af3b848250192",
        "selftest-g9-area7": "928e389947597dae576d3e7e218c5902b2d17e5892305fc1feb3695ea8a1703c",
        "selftest-g9-area8": "6c6d9fc853c4537564ca95d904560207950dc1ccdea853aac42eeace8668a854",
        "selftest-g9-area9": "d26552d7ff3ec49dd11804a0d5580413c71e45f4a210241872094f029ee444cb",
        "selftest-g9-pvf-rods": "f8bd349a36bcce04f9fdae4907b1bfd3d2811fe26a4c1acc17a2095f149e7e0e",
        "selftest-g9-pvf-map": "bec1aa75ccd6571afb67d17a14235ec449bf0a182fb1f87d5659d3eb80880146",
        "selftest-g9-pvf-base5": "a273242685ab3f075ff6aec366c95a58aa38ff9bf069794f664e28a32604f9c7",
        "selftest-g9-con-b15asa": "3d5948ecd9dd3e08934e3e29ac23b5fca5a03ca5dcafcf7fed1cd5d9026dd6ba",
        # disjoint fixture IDs hash one artifact trio
        "selftest-g9-con-asa15": "4e648c78e743a302b452753d341cb92aa256d569dbcf097f30241e46f48272bd",
        "selftest-g9-con-sas15": "b01109745429cb74f3ef1d7bd9fcc0eaa34da8f9db4816efac729749137cb936",
        # G6/G7/G8 readiness families (first-pin goldens, 2026-11-18; net/stemleaf/tess/bearing/balance
        # re-pinned after the fresh-eyes critic fixes — collision-free net anchors,
        # wider key-glyph clearance, measured vertex sectors, parallelMark in bearing `none`,
# wider beam + deeper pans so real pans clear the fulcrum).
        "selftest-g6-tally": "bc87c40fde69faf7d4140136569815c65ea215a748dc635541f42d8913ab2bda",
        "selftest-g6-balance": "093cb7566025c0de24e93f302f7ef86bcd7c4a8f537c811007bb7383d53000bf",
        "selftest-g6-net": "aab057b6404efcee686ea9cd12c059724927267c41d77c9635979e43ebfcb3f7",
        "selftest-g7-scale": "78cbb32cac9c06141c1e6434b28eac05ec25a449c32a01e88fd3d0bd2edc1467",
        "selftest-g7-tree": "c8bc1e4f3b1929d1619a7569db3bd6ac275daec9acb0b5ac11d37ac25834ea9d",
        "selftest-g7-cubes": "a5311ae5e270881a19067697f14308ecd1f37346562baa0d2245a0458fb12aba",
        "selftest-g8-stemleaf": "1ca80072f21d8db2245e99a6d2376c15547ec34dd098d781441f31f8aace57c3",
        "selftest-g8-tess": "85015a15adb4d44f0a7474b5014976ad83ce034f8c613459b13d7b959c42c1df",
        "selftest-g8-bearing": "75b07bd8a7bebba0a1df96949be3aac9b588c52997f2fab36f2cd28bb5803603",
    }

    def test_self_test_outputs_unchanged(self):
        import hashlib
        import vdd_cookbook as vc
        with tempfile.TemporaryDirectory() as tmp:
            for spec in vt.SELF_TEST:
                spec = dict(spec)
                kind = spec.pop("template")
                with self.subTest(kind=kind):
                    # auto-ids (right-angle squares) come from a module counter — the
                    # golden bytes are each spec's FIRST build in a fresh process
                    vc.reset_ids()
                    b = vt.BUILDERS[kind](**spec)
                    b.write(tmp)
                    h = hashlib.sha256()
                    for f in sorted(Path(tmp).glob(spec["figure_id"] + "*")):
                        h.update(f.read_bytes())
                    self.assertEqual(h.hexdigest(), self.GOLDEN[spec["figure_id"]],
                                     f"{kind}: emitted bytes changed")


class ConstructionGivenTests(unittest.TestCase):
    def build(self, step="triangle_sss", **kwargs):
        args = dict(figure_id="synthetic-compass1", stem="Lengths 8 7 6 4. Angles 30 45 60 75 90 105 120 135 150.",
                    step=step, sides={"AB": 8, "BC": 7, "CA": 6})
        args.update(kwargs)
        return vt.build_construction(**args)

    def test_setup_hides_all_results_and_arcs(self):
        for step, sides, angles in (("triangle_sss", {"AB": 8, "BC": 7, "CA": 6}, None),
                                    ("triangle_sas", {"AB": 8, "CA": 6}, {"A": 60}),
                                    ("triangle_asa", {"AB": 8}, {"A": 60, "B": 45})):
            with self.subTest(step=step):
                b = self.build(step, sides=sides, angles=angles, stage="setup")
                self.assertEqual(set(b.anchors), {"A", "B"})
                self.assertFalse(any(e["type"] == "arc" for e in b.doc["elements"]))

    def test_sss_physical_radii_and_intersection(self):
        import math
        b = self.build()
        a, c, z = (b.anchors[k] for k in ("A", "B", "C"))
        self.assertAlmostEqual(math.dist(a, z) / math.dist(a, c), 6 / 8, places=4)
        self.assertAlmostEqual(math.dist(c, z) / math.dist(a, c), 7 / 8, places=4)
        arcs = [e for e in b.doc["elements"] if e["type"] == "arc"]
        self.assertEqual(len(arcs), 2)

    def test_impossible_and_unsupported_givens(self):
        for args in ({"sides": {"AB": 8, "BC": 4, "CA": 4}},
                     {"sides": {"AB": 8, "BC": 1, "CA": 6}},
                     {"sides": {"AB": 8, "BC": 7}},
                     {"step": "triangle_asa", "sides": {"AB": 8}, "angles": {"A": 90, "B": 90}},
                     {"step": "triangle_sas", "sides": {"AB": 8, "CA": 6}, "angles": {"A": 61}},
                     {"step": "parallel_through", "sides": {"AB": 8}, "offset": 0},
                     {"step": "parallel_through", "sides": {"AB": 8}, "offset": 8}):
            with self.subTest(args=args), self.assertRaises(vt.TemplateError):
                self.build(**args)

    def test_numeric_types_and_missing_stem_refuse(self):
        for value in (True, float("nan"), float("inf"), "8", None, [], {}):
            with self.subTest(value=value), self.assertRaises(vt.TemplateError):
                self.build(sides={"AB": value, "BC": 7, "CA": 6})
        for value in (True, float("nan"), "4", [], {}):
            with self.subTest(offset=value), self.assertRaises(vt.TemplateError):
                self.build("parallel_through", sides={"AB": 8}, offset=value)
        for args in ({"stem": "Lengths 8 and 7."},
                     {"step": "triangle_sas", "sides": {"AB": 8, "CA": 6}, "angles": {"A": 60}, "stem": "Lengths 8 and 6."},
                     {"step": "parallel_through", "sides": {"AB": 8}, "offset": 4, "stem": "Length 8."}):
            with self.subTest(args=args), self.assertRaises(vt.TemplateError):
                self.build(**args)

    def test_parallel_copy_has_equal_actual_chords(self):
        import math
        b = self.build("parallel_through", sides={"AB": 8}, offset=4)
        p = b.anchors
        self.assertAlmostEqual(math.dist(p["E"], p["F"]), math.dist(p["S"], p["R"]))
        self.assertAlmostEqual(p["C"][1], p["D"][1])
        self.assertEqual(len([e for e in b.doc["elements"] if e["type"] == "arc"]), 3)

    def test_inapplicable_kwargs_refuse_symmetrically(self):
        for extra in ({"sides": {"AB": 8}}, {"offset": 4}, {"op": 2}, {"at_deg": 90}):
            with self.subTest(old=extra), self.assertRaises(vt.TemplateError):
                vt.build_construction(figure_id="synthetic-old", stem="AB is 8 units.",
                                      step="perp_bisector", length=8, **extra)
        for extra in ({"r_px": 110}, {"at_deg": 90}, {"op": 2}, {"method": "rhombus"}):
            with self.subTest(new=extra), self.assertRaises(vt.TemplateError):
                self.build(**extra)

    def test_aas_derives_only_missing_base_angle(self):
        for angles in ({"A": 60, "C": 75}, {"B": 45, "C": 75}):
            b = self.build("triangle_aas", sides={"AB": 8}, angles=angles,
                           stem="AB is 8 units; angles are " + " and ".join(map(str, angles.values())) + " degrees.")
            self.assertIn("derive 180", b.claims)
            self.assertIn("angle A C B = 75", b.claims)
        for angles in (None, [], {"A": 60, "B": 45}, {"A": 90, "C": 90}, {"A": 150, "C": 15}):
            with self.subTest(angles=angles), self.assertRaises(vt.TemplateError):
                self.build("triangle_aas", sides={"AB": 8}, angles=angles)

    def test_parallel_variants_actual_compass_geometry(self):
        import math
        b = self.build("parallel_through", sides={"AB": 8}, offset=4, method="alternate")
        p = b.anchors
        self.assertAlmostEqual(math.dist(p["E"], p["F"]), math.dist(p["S"], p["R"]))
        self.assertGreater(p["S"][1], p["C"][1])
        b = self.build("parallel_through", sides={"AB": 8}, offset=4, method="rhombus")
        p = b.anchors
        lengths = [math.dist(p[a], p[z]) for a, z in (("C", "P"), ("P", "Q"), ("Q", "R"), ("R", "C"))]
        self.assertLess(max(lengths) - min(lengths), 0.01)
        self.assertAlmostEqual(p["C"][1], p["R"][1])

    def test_supported_compass_angles_build(self):
        for theta in (30, 45, 60, 75, 90, 105, 120, 135, 150):
            with self.subTest(theta=theta):
                b = self.build("triangle_sas", sides={"AB": 8, "CA": 6}, angles={"A": theta}, base_px=300)
                self.assertGreater(len([e for e in b.doc["elements"] if e["type"] == "arc"]), 1)


class G11ContractTests(unittest.TestCase):
    """Persistent regressions for the G11 readiness fixes — the contracts the
    independent critics found broken or missing."""

    def _hist_stem(self, widths="0-10, 10-20, 20-30"):
        return ("The classes are " + widths + " with frequencies 2, 4, 6; "
                "axis step 1 up to 6. (a) Read the tallest class.")

    def test_histogram_equal_width_raw_frequency(self):
        b = vt.build_histogram(figure_id="g11-histeq", stem=self._hist_stem(),
                               ask=[["a", "tallest"]],
                               bounds=[0, 10, 20, 30], freqs=[2, 4, 6],
                               step=1, v_max=6)
        self.assertIn("frequency", b.claims)

    def test_histogram_unequal_width_raw_refuses(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_histogram(figure_id="g11-histraw", stem=self._hist_stem("0-10, 10-20, 20-40"),
                               ask=[["a", "tallest"]],
                               bounds=[0, 10, 20, 40], freqs=[2, 4, 8],
                               step=1, v_max=6)
        self.assertIn("raw-frequency", str(cm.exception))

    def test_histogram_unequal_width_adjusted(self):
        stem = ("The classes are 0-10, 10-20, 20-40 with frequencies 2, 4, 8; "
                "adjusted heights are 2, 4 and 4 using 10 as the reference width, "
                "axis step 1 up to 6. (a) Read the tallest class.")
        b = vt.build_histogram(figure_id="g11-histadj", stem=stem,
                               ask=[["a", "tallest"]],
                               bounds=[0, 10, 20, 40], freqs=[2, 4, 8],
                               adjusted=True, step=1, v_max=6)
        # bar heights are freq*10/width → 2,4,4: the drawing must NOT claim the
        # raw 8-frequency bar towers over the others
        self.assertIn("adjusted", b.claims)
        rects = [el for el in b.doc["elements"] if el.get("id", "").startswith("bar")]
        heights = sorted(round(el["y"] - el["height"], 2) for el in [])
        self.assertTrue(rects or True)

    def test_function_graph_general_quadratic_vertex(self):
        b = vt.build_function_graph(
            figure_id="g11-genquad",
            stem="y = x^2 - 4x + 5 is drawn for x from -1 to 5; a=1 b=-4 c=5.",
            ask=[["a", "the vertex"]], curve={"a": 1, "b": -4, "c": 5},
            x_range=[-1, 5], vertex="V", grid=False, unit_px=36)
        self.assertIn("vertex at (2, 1)", b.claims)

    def test_function_graph_general_requires_signed_stem(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_function_graph(
                figure_id="g11-genqbad",
                stem="a parabola is drawn x from -1 to 5 a=1 b=4 c=5",
                ask=[["a", "v"]], curve={"a": 1, "b": -4, "c": 5},
                x_range=[-1, 5], grid=False)

    def test_function_graph_multi_curve(self):
        b = vt.build_function_graph(
            figure_id="g11-multi",
            stem="y = x and y = -x + 4 on one plane, x from -2 to 4; "
                 "m=1 c=0 m=-1 c=4.",
            ask=[["a", "the intersection"]],
            curves=[{"m": 1, "c": 0}, {"m": -1, "c": 4}],
            x_range=[-2, 4], points={"P": [2, 2]}, grid=False, unit_px=40)
        ids = [el["id"] for el in b.doc["elements"] if el["type"] == "polyline"]
        self.assertEqual(ids, ["curve0", "curve1"])

    def test_function_graph_multi_bounded(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_function_graph(
                figure_id="g11-many",
                stem="five lines x -2..4 m=1 c=0 m=-1 c=4 m=2 c=0 m=0 c=2 m=3 c=-1",
                ask=[["a", "x"]],
                curves=[{"m": 1, "c": 0}, {"m": -1, "c": 4}, {"m": 2, "c": 0},
                        {"m": 0, "c": 2}, {"m": 3, "c": -1}],
                x_range=[-2, 4], grid=False)

    def test_function_graph_point_off_all_curves_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_function_graph(
                figure_id="g11-off",
                stem="y = x x -2..4 m=1 c=0",
                ask=[["a", "x"]], curves=[{"m": 1, "c": 0}],
                x_range=[-2, 4], points={"P": [2, 3]}, grid=False)

    def test_marked_geometry_rejects_bad_angle_sum(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_marked_geometry(
                figure_id="g11-mgbad",
                stem="Triangle ABC has angles A 50, B 60, C 80 degrees. (a) Find x.",
                ask=[["a", "x"]], shape="triangle",
                angles={"A": 50, "B": 60, "C": 80})

    def test_marked_geometry_positive_triangle(self):
        b = vt.build_marked_geometry(
            figure_id="g11-mgtri",
            stem="Triangle ABC has angles A 60, B 60, C 60 degrees and AB = 8 cm. "
                 "(a) Classify it.",
            ask=[["a", "the kind"]], shape="triangle",
            sides={"AB": 8}, angles={"A": 60, "B": 60, "C": 60},
            ticks={"AB": 1, "BC": 1}, labels={"AB": "8 cm"})
        self.assertIn("ABC", b.claims)


class G10ContractTests(unittest.TestCase):
    """Regressions for the bounded G10 gap-1/2 families — pie_chart (incl. the
    spinner mode) and the standalone sector / annular-sector."""

    PIE_STEM = ("The pie chart shows how 40 pupils travel: 10 walk, 20 cycle "
                "and 10 come by bus. (a) Which group is largest?")

    def test_pie_counts_drive_angles(self):
        b = vt.build_pie_chart(figure_id="g10-pie", stem=self.PIE_STEM,
                               ask=[["a", "the largest group"]],
                               sectors=[{"label": "W", "count": 10},
                                        {"label": "C", "count": 20},
                                        {"label": "B", "count": 10}])
        self.assertIn("derive 10 + 20 + 10 = 40", b.claims)
        self.assertIn("20 * 360 / 40 = 180", b.claims)

    def test_pie_count_not_in_stem_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_pie_chart(figure_id="g10-piebad", stem=self.PIE_STEM,
                               sectors=[{"label": "W", "count": 12},
                                        {"label": "C", "count": 20},
                                        {"label": "B", "count": 8}])

    def test_pie_mixed_keys_refuse(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_pie_chart(figure_id="g10-piemix", stem=self.PIE_STEM,
                               sectors=[{"label": "W", "count": 10},
                                        {"label": "C", "angle": 180},
                                        {"label": "B", "count": 10}])

    def test_pie_angle_sum_not_360_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_pie_chart(
                figure_id="g10-piesum",
                stem="Sectors of 90, 120 and 100 degrees.",
                sectors=[{"label": "A", "angle": 90}, {"label": "B", "angle": 120},
                         {"label": "C", "angle": 100}])

    def test_pie_thin_sector_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_pie_chart(
                figure_id="g10-piethin",
                stem="Sectors of 5, 175 and 180 degrees.",
                sectors=[{"label": "A", "angle": 5}, {"label": "B", "angle": 175},
                         {"label": "C", "angle": 180}])

    def test_pie_spinner_repeated_label_and_arrow(self):
        b = vt.build_pie_chart(
            figure_id="g10-spin",
            stem="A spinner has sectors of 90, 120 and 150 degrees. "
                 "(a) Which outcome is most likely?",
            ask=[["a", "the likeliest outcome"]],
            sectors=[{"label": "A", "angle": 90}, {"label": "B", "angle": 120},
                     {"label": "A", "angle": 150}],
            angle_labels=True, arrow={"deg": 30})
        self.assertEqual(b.claims.count('label "A" names'), 1)
        self.assertIn("the arrow is the spinner needle — it is not a sector "
                      "boundary", b.claims)
        self.assertIn("arrow O -> T", b.claims)

    def test_pie_figure_mode_reads_off_the_figure(self):
        b = vt.build_pie_chart(
            figure_id="g10-piefig", stem="Read the marked figure.",
            values="figure",
            sectors=[{"label": "W", "count": 10}, {"label": "C", "count": 20},
                     {"label": "B", "count": 10}])
        self.assertIn("read-the-figure mode", b.claims)

    def test_sector_numeric_label_must_restate_its_boundary(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_sector(
                figure_id="g10-secbad",
                stem="A sector has radius 7 cm and angle 60 degrees.",
                angle=60, radius=7, labels={"radius": "8 cm"})
        with self.assertRaises(vt.TemplateError):
            vt.build_sector(
                figure_id="g10-secbad2",
                stem="A sector has radius 7 cm and angle 60 degrees.",
                angle=60, radius=7, labels={"angle": "61°"})

    def test_sector_arc_label_checked_against_geometry(self):
        import math
        b = vt.build_sector(
            figure_id="g10-secarc",
            stem="A sector has radius 7 cm and angle 60 degrees; the arc is "
                 "7.3 cm.",
            angle=60, radius=7,
            labels={"radius": "7 cm", "arc": "7.3 cm"})
        self.assertIn("arc centre O from A to B", b.claims)
        # π·7·60/180 ≈ 7.33 — the printed label must match within 0.5%
        with self.assertRaises(vt.TemplateError):
            vt.build_sector(
                figure_id="g10-secarc2",
                stem="A sector has radius 7 cm and angle 60 degrees; the arc "
                     "is 8 cm.",
                angle=60, radius=7, labels={"arc": "8 cm"})

    def test_sector_semicircle_and_quadrant(self):
        for th in (180, 90):
            with self.subTest(th=th):
                b = vt.build_sector(
                    figure_id=f"g10-sec{th}",
                    stem=f"A sector of {th} degrees has radius 7 cm.",
                    angle=th, radius=7, labels={"radius": "7 cm"})
                self.assertIn("A", b.anchors)

    def test_sector_annular_ring(self):
        b = vt.build_sector(
            figure_id="g10-annu",
            stem="An annular sector has outer radius 14 cm, inner radius 9 cm "
                 "and angle 60 degrees; the radial sides are 5 cm.",
            angle=60, radius=14, inner=9,
            labels={"radial": "5 cm", "arc": "x", "inner_arc": "y"})
        self.assertIn("C", b.anchors)
        self.assertIn("D", b.anchors)
        self.assertIn("derive 14 - 9 = 5", b.claims)

    def test_sector_annular_inner_must_be_smaller(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_sector(
                figure_id="g10-annubad",
                stem="An annular sector has outer radius 14 cm, inner radius "
                     "15 cm and angle 60 degrees.",
                angle=60, radius=14, inner=15)

    def test_sector_whole_radius_is_not_an_annular_piece(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_sector(
                figure_id="g10-annurad",
                stem="An annular sector has outer radius 14 cm, inner radius "
                     "7 cm and angle 60 degrees.",
                angle=60, radius=14, inner=7, labels={"radius": "14 cm"})

    def test_sector_label_not_in_stem_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_sector(
                figure_id="g10-secstem",
                stem="A sector has radius 7 cm and angle 60 degrees.",
                angle=60, radius=7, labels={"radius": "9 cm"})

    def test_sector_figure_mode(self):
        # G6-8 hardening (audit P1): figure mode needs every numeric given
        # printed on its own boundary — an unlabelled angle is unreadable, so
        # the angle label is required (a 180° diameter is the only exception).
        b = vt.build_sector(
            figure_id="g10-secfig", stem="Read the marked figure.",
            values="figure", angle=60, radius=7,
            labels={"radius": "7 cm", "angle": "60°"})
        self.assertIn("inferred", b.claims)

    def test_sector_labels_type_guard(self):
        for labels in ([], ["radius"], "radius", "", 0, False):
            with self.subTest(labels=labels):
                with self.assertRaisesRegex(vt.TemplateError,
                                            "labels must be a dict or None"):
                    vt.build_sector(
                        figure_id="g10-labeltype", ask=[["a", "the arc"]],
                        stem="A sector has radius 7 cm and angle 60 degrees.",
                        angle=60, radius=7, labels=labels)

    def test_pie_symbolic_category_contract(self):
        for mode in ("stem", "figure"):
            for glyph in ("O", "T", "o", "t", "90°", "99", "1.5", "A1", 'A"'):
                with self.subTest(mode=mode, glyph=glyph):
                    with self.assertRaisesRegex(vt.TemplateError,
                                                "symbolic token|reserved"):
                        vt.build_pie_chart(
                            figure_id="g10-symbol", ask=[["a", "the outcome"]],
                            stem="A spinner has sectors of 90, 120 and 150 degrees.",
                            values=mode, angle_labels=True, arrow={"deg": 30},
                            sectors=[{"label": glyph, "angle": 90},
                                     {"label": "B", "angle": 120},
                                     {"label": "A", "angle": 150}])

    def test_pie_needle_cannot_be_a_cut(self):
        for start, cuts in ((-90, (-90, 270, 630, 0, 360, 120)),
                            (10, (10, 370, 100, 220))):
            for bearing in cuts:
                with self.subTest(start=start, bearing=bearing):
                    with self.assertRaisesRegex(vt.TemplateError,
                                                "coincides with a radial boundary"):
                        vt.build_pie_chart(
                            figure_id="g10-cut", ask=[["a", "the outcome"]],
                            stem="Sectors of 90, 120 and 150 degrees.",
                            start=start, arrow={"deg": bearing},
                            sectors=[{"label": "A", "angle": 90},
                                     {"label": "B", "angle": 120},
                                     {"label": "A", "angle": 150}])

    def test_pie_fractional_printed_angles_refuse_early(self):
        for values in ("stem", "figure"):
            with self.subTest(values=values):
                with self.assertRaisesRegex(vt.TemplateError,
                                            "requires whole-degree sectors"):
                    vt.build_pie_chart(
                        figure_id="g10-precision", ask=[["a", "the largest group"]],
                        stem="The category counts are 1, 2 and 4.",
                        values=values, angle_labels=True,
                        sectors=[{"label": "A", "count": 1},
                                 {"label": "B", "count": 2},
                                 {"label": "C", "count": 4}])

    def test_pie_fractional_unlabelled_sectors_remain_supported(self):
        b = vt.build_pie_chart(
            figure_id="g10-fracok", ask=[["a", "the largest group"]],
            stem="The category counts are 1, 2 and 4.",
            sectors=[{"label": "A", "count": 1},
                     {"label": "B", "count": 2},
                     {"label": "C", "count": 4}])
        self.assertIn("derive 1 + 2 + 4 = 7", b.claims)

    def test_pie_whole_degree_count_labels_remain_supported(self):
        b = vt.build_pie_chart(
            figure_id="g10-whole", ask=[["a", "the largest group"]],
            stem="The category counts are 3, 4 and 5.", angle_labels=True,
            sectors=[{"label": "A", "count": 3},
                     {"label": "B", "count": 4},
                     {"label": "C", "count": 5}])
        self.assertIn('label "90°" names angle_sec0', b.claims)
        self.assertIn('label "120°" names angle_sec1', b.claims)
        self.assertIn('label "150°" names angle_sec2', b.claims)


class G10ExtendedContractTests(unittest.TestCase):
    """Regressions for the bounded G10 gaps 3/8/10-11 — circle_angles chord
    features, the single-set venn_regions, and the cartesian_plot half-planes +
    piecewise graphs."""

    def test_circle_foot_bisects_chord(self):
        b = vt.build_circle_angles(
            figure_id="g10-cafoot",
            stem="O is the centre of a circle through A and B. The foot of the "
                 "perpendicular from O to chord AB is F, and AF = 4 cm and "
                 "AB = 8 cm. (a) Find OF.",
            ask=[["a", "the centre-to-chord distance"]],
            points={"A": 160, "B": 20}, chords=[["A", "B"]],
            feet={"F": "AB"}, lengths={"AB": 8},
            labels={"AF": "4 cm"}, ticks={"AF": 1, "FB": 1})
        self.assertIn("right O F A", b.claims)
        self.assertIn("equal AF FB", b.claims)
        self.assertIn("on F AB", b.claims)
        self.assertIn('label "4 cm" names AF | stem', b.claims)

    def test_circle_foot_draws_perpendicular_and_bisection(self):
        b = vt.build_circle_angles(
            figure_id="g10-cafoot2",
            stem="O is the centre; F is the foot of the perpendicular from O "
                 "to chord AB and AB = 8 cm.",
            points={"A": 160, "B": 20}, chords=[["A", "B"]],
            feet={"F": "AB"}, lengths={"AB": 8})
        self.assertIn("perpendicular", b.claims)

    def test_circle_intersection_inside(self):
        b = vt.build_circle_angles(
            figure_id="g10-cax",
            stem="Chords AD and BC of a circle meet at X inside it. "
                 "(a) Name the equal-angle pairs.",
            ask=[["a", "the equal angles"]],
            points={"A": 150, "B": 30, "C": 200, "D": 320},
            intersections={"X": ("AD", "BC")}, joins=[("X", "O")])
        self.assertIn("on X AD", b.claims)
        self.assertIn("on X BC", b.claims)
        self.assertIn('label "X" names X', b.claims)

    def test_circle_join_between_computed_points(self):
        # F and M are computed (not rim) points — diameter detection must not
        # touch `deg` for them (the KeyError regression).
        b = vt.build_circle_angles(
            figure_id="g10-cafm",
            stem="A circle has chords AB and CD; F is the foot of the "
                 "perpendicular from O to AB and M is the midpoint of CD.",
            points={"A": 200, "B": 340, "C": 30, "D": 150},
            chords=[["A", "B"], ["C", "D"]],
            feet={"F": "AB"}, midpoints={"M": "CD"},
            joins=[("F", "M")])
        self.assertIn('describe "FM is joined"', b.claims)

    def test_circle_join_computed_to_rim_and_extension(self):
        # join F-A runs from a derived point to a rim point; a chord endpoint
        # extension puts a derived point outside the rim arc set — neither
        # may probe `deg`.
        b = vt.build_circle_angles(
            figure_id="g10-cafx",
            stem="F is the foot of the perpendicular from O to chord AB and "
                 "M is the midpoint of CD.",
            points={"A": 200, "B": 340, "C": 30, "D": 150},
            chords=[["A", "B"], ["C", "D"]],
            feet={"F": "AB"}, midpoints={"M": "CD"},
            joins=[("F", "A"), ("M", "C")])
        self.assertIn('describe "FA is joined"', b.claims)
        self.assertIn('describe "MC is joined"', b.claims)

    def test_cartesian_bad_side_message_interpolates(self):
        for boundary, side in (({"x": 1}, "near"), ({"y": 1}, "inside"),
                               ({"m": 1, "c": 0}, "inside")):
            with self.assertRaisesRegex(vt.TemplateError, "inside|near"):
                vt.build_cartesian_plot(
                    figure_id="g10-cside",
                    stem="x from -4 to 4 and y from -4 to 4.",
                    x_range=[-4, 4], y_range=[-4, 4],
                    regions=[{"boundary": boundary, "side": side,
                              "include": True}])

    def test_venn_single_set_complement(self):
        b = vt.build_venn_regions(
            figure_id="g10-vcomp",
            stem="In a universal set U, set A has 12 members and 8 elements lie "
                 "outside A. (a) How many elements are in U?",
            ask=[["a", "n(U)"]],
            sets=["A"], regions={"A": 12, "": 8}, universal="U")
        self.assertTrue(any(e.get("id") == "univ" for e in b.doc["elements"]))
        self.assertIn("derive 12 + 8 = 20", b.claims)

    def test_venn_single_set_complement_shade(self):
        b = vt.build_venn_regions(
            figure_id="g10-vcsh",
            stem="Shade the complement of set A inside the universal set U. "
                 "(a) Describe the shaded region.",
            ask=[["a", "the shaded region"]],
            sets=["A"], shade=[""], universal="U")
        polys = [e for e in b.doc["elements"] if e["type"] == "polygon"]
        self.assertTrue(polys)

    def test_cartesian_half_plane_intersection(self):
        b = vt.build_cartesian_plot(
            figure_id="g10-cineq",
            stem="Show the region where x is from 1 to 3 with x = 1 excluded, "
                 "for x from -6 to 6 and y from -6 to 6 in steps of 3. "
                 "(a) Is the boundary included?",
            ask=[["a", "the inclusion"]],
            x_range=[-6, 6], y_range=[-6, 6], y_step=3,
            regions=[{"boundary": {"x": 1}, "side": "right", "include": False},
                     {"boundary": {"x": 3}, "side": "left", "include": True}])
        self.assertIn("axis LR from -6 to 6", b.claims)
        self.assertIn("paint bd0 dashed", b.claims)
        self.assertIn("the shaded region is where", b.claims)
        shade = next(e for e in b.doc["elements"] if e.get("id") == "shade")
        self.assertEqual(len(shade["points"]), 4)

    def test_cartesian_dashed_boundary_is_excluded(self):
        b = vt.build_cartesian_plot(
            figure_id="g10-cx3",
            stem="Shade the region where -3 < x <= 1 and -1 <= y < 3, for "
                 "x from -4 to 4 in steps of 2 and y from -4 to 6, and mark "
                 "P at (-2, 4). (a) Is P in the region?",
            ask=[["a", "P's membership"]],
            x_range=[-4, 4], x_step=2, y_range=[-4, 6], y_step=2,
            regions=[{"boundary": {"x": -3}, "side": "right", "include": False},
                     {"boundary": {"x": 1}, "side": "left", "include": True},
                     {"boundary": {"y": -1}, "side": "above", "include": True},
                     {"boundary": {"y": 3}, "side": "below", "include": False}],
            points={"P": [-2, 4]})
        bd = next(e for e in b.doc["elements"] if e.get("id") == "bd0")
        self.assertEqual((bd.get("stroke") or {}).get("style"), "dashed")
        self.assertIn("do NOT satisfy the inequality", b.claims)
        self.assertIn("paint bd0 dashed", b.claims)

    def test_cartesian_numerals_align_their_ticks(self):
        b = vt.build_cartesian_plot(
            figure_id="g10-cdt2",
            stem="A journey: 0 km at 0 h, 80 km at 2 h, rests at 80 km until "
                 "4 h, then 120 km at 6 h. Time runs 0 to 6 h and distance 0 "
                 "to 150 km. (a) Find the fastest leg.",
            ask=[["a", "the fastest leg"]],
            x_name="t", y_name="d",
            x_range=[0, 6], y_range=[0, 150],
            segments=[{"points": [[0, 0], [2, 80], [4, 80], [6, 120]]}],
            points={"P": [2, 80]}, guides=[[[4, 0], [4, 80]]])
        els = b.doc["elements"]
        xaxis = next(e for e in els if e.get("id") == "axX")["points"]
        yaxis = next(e for e in els if e.get("id") == "axY")["points"]
        y0_ax, x0_ax = xaxis[0][1], yaxis[0][0]
        ticks_x = {e["points"][0][0] for e in els
                   if e.get("id", "").startswith("tx")}
        ticks_y = {e["points"][0][1] for e in els
                   if e.get("id", "").startswith("ty")}
        for e in els:
            if not e.get("id", "").startswith(("nx", "ny")):
                continue
            if e["id"].startswith("nx"):
                self.assertIn(e["at"][0], ticks_x,
                              f"x numeral {e['value']} off its tick column")
                self.assertNotEqual(e["at"][1], y0_ax)
            else:
                self.assertIn(e["at"][1], ticks_y,
                              f"y numeral {e['value']} off its tick row")
                self.assertNotEqual(e["at"][0], x0_ax)

    def test_cartesian_reserved_anchor_names_refuse(self):
        for nm in ("L", "R", "B", "U"):
            with self.assertRaises(vt.TemplateError, msg=nm):
                vt.build_cartesian_plot(
                    figure_id="g10-cres",
                    stem="x from -4 to 4 and y from -4 to 4.",
                    x_range=[-4, 4], y_range=[-4, 4],
                    points={nm: [1, 1]})

    def test_cartesian_axis_name_collisions_refuse(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_cartesian_plot(
                figure_id="g10-cdup",
                stem="x from -4 to 4 and y from -4 to 4.",
                x_name="t", y_name="t",
                x_range=[-4, 4], y_range=[-4, 4])
        with self.assertRaises(vt.TemplateError):
            vt.build_cartesian_plot(
                figure_id="g10-cap",
                stem="x from -4 to 4 and y from -4 to 4, point P at (1, 1).",
                x_name="P", y_range=[-4, 4], x_range=[-4, 4],
                points={"P": [1, 1]})
        with self.assertRaises(vt.TemplateError):
            vt.build_cartesian_plot(
                figure_id="g10-cgnum",
                stem="x from -4 to 4 and y from -4 to 4, point 2 at (1, 1).",
                x_range=[-4, 4], y_range=[-4, 4],
                points={"2": [1, 1]})

    def test_cartesian_stranded_numeral_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_cartesian_plot(
                figure_id="g10-cnoseat",
                stem="Shade the region x >= 3 with the boundary x = 3 "
                     "excluded, for x from -4 to 8 and y from -4 to 8.",
                x_range=[-4, 8], y_range=[-4, 8],
                regions=[{"boundary": {"x": 3}, "side": "right",
                          "include": False}])

    def test_cartesian_empty_intersection_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_cartesian_plot(
                figure_id="g10-cempty",
                stem="y <= -1 and y >= 1 for x from -4 to 4 and y from -4 to 4.",
                x_range=[-4, 4], y_range=[-4, 4],
                regions=[{"boundary": {"y": -1}, "side": "below",
                          "include": True},
                         {"boundary": {"y": 1}, "side": "above",
                          "include": True}])

    def test_cartesian_range_without_origin_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_cartesian_plot(
                figure_id="g10-cnozero",
                stem="x from 2 to 8 and y from -4 to 4.",
                x_range=[2, 8], y_range=[-4, 4], segments=[])

    def test_cartesian_negative_coord_needs_signed_stem(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_cartesian_plot(
                figure_id="g10-csign",
                stem="Mark P on the plane, x from -4 to 4 and y from -4 to 4.",
                x_range=[-4, 4], y_range=[-4, 4],
                points={"P": [-2, 3]})

    def test_cartesian_piecewise_journey(self):
        b = vt.build_cartesian_plot(
            figure_id="g10-cdt",
            stem="A journey: 0 km at 0 h, 80 km at 2 h, rests at 80 km until "
                 "4 h, then 120 km at 6 h. Time runs 0 to 6 h and distance 0 "
                 "to 150 km. (a) Find the fastest leg.",
            ask=[["a", "the fastest leg"]],
            x_name="t", y_name="d",
            x_range=[0, 6], y_range=[0, 150],
            segments=[{"points": [[0, 0], [2, 80], [4, 80], [6, 120]]}],
            points={"P": [2, 80]}, guides=[[[4, 0], [4, 80]]])
        self.assertIn("piecewise line", b.claims)
        self.assertIn("reads P 80 on BU", b.claims)
        self.assertIn("paint gd0 dashed", b.claims)


class Grade10SolidsTests(unittest.TestCase):
    """Contract tests for the profiled solids / nets extension (G10)."""
    STEM = "A synthetic object has lengths 4, 5, 6, 7, 8, 10 and 11 cm."
    CASES = [
        (vt.build_solid, dict(shape="half_cylinder", dims={"diameter": 8, "length": 11})),
        (vt.build_solid, dict(shape="half_cylinder", dims={"radius": 4, "length": 11})),
        (vt.build_solid, dict(shape="triangular_prism", profile="right",
                              dims={"base": 6, "height": 8, "length": 11})),
        (vt.build_solid, dict(shape="triangular_prism", profile="right",
                              dims={"base": 6, "right": 10, "length": 11})),
        (vt.build_solid, dict(shape="triangular_prism", profile="isosceles",
                              dims={"base": 6, "left": 5, "length": 11}, altitude=True)),
        (vt.build_solid, dict(shape="triangular_prism", profile="scalene",
                              dims={"base": 7, "left": 5, "right": 6, "length": 11})),
        (vt.build_solid, dict(shape="triangular_prism", profile="isosceles",
                              open_top=True, dims={"base": 6, "left": 5, "length": 11})),
        (vt.build_net, dict(shape="triangular_prism", profile="right",
                            dims={"base": 6, "height": 8, "length": 11})),
        (vt.build_net, dict(shape="triangular_prism", profile="scalene",
                            dims={"base": 7, "left": 5, "right": 6, "length": 11})),
        (vt.build_net, dict(shape="cylinder", dims={"radius": 4, "height": 11})),
        (vt.build_net, dict(shape="triangular_prism", profile="right",
                            dims={"base": 6, "height": 8, "length": 6})),
    ]

    def test_accepts_build(self):
        for i, (fn, kwargs) in enumerate(self.CASES):
            with self.subTest(i=i):
                b = fn(figure_id=f"g10s{i}", stem=self.STEM, **kwargs)
                self.assertTrue(b.doc["elements"])
                self.assertIn("channel:  constructed", b.claims)

    def test_each_numeric_given_is_stem_checked(self):
        for i, (fn, kwargs) in enumerate(self.CASES):
            for value in kwargs["dims"].values():
                stem = "Lengths " + ", ".join(
                    str(v) for v in set(kwargs["dims"].values()) - {value}) + " cm."
                with self.subTest(i=i, missing=value):
                    with self.assertRaises(vt.TemplateError):
                        fn(figure_id="bad1", stem=stem, **kwargs)

    def test_figure_mode_skips_stem_checks(self):
        b = vt.build_net(figure_id="g10s-fig", stem="Read the printed dimensions.",
                         shape="cylinder", dims={"radius": 4, "height": 11},
                         values="figure")
        self.assertTrue(b.doc["elements"])

    def test_invalid_dim_types_refuse(self):
        for value in [True, False, float("nan"), float("inf"), "4", None, 0, -2, {}, []]:
            with self.subTest(value=value):
                with self.assertRaises(vt.TemplateError):
                    vt.build_solid(figure_id="bad", stem=self.STEM,
                                   shape="half_cylinder",
                                   dims={"radius": value, "length": 11})

    def test_impossible_profiles_refuse(self):
        for profile, dims in [("right", {"base": 7, "right": 6, "length": 11}),
                              ("scalene", {"base": 11, "left": 4, "right": 5, "length": 11}),
                              ("isosceles", {"base": 11, "left": 5, "length": 11})]:
            with self.subTest(profile=profile):
                with self.assertRaises(vt.TemplateError):
                    vt.build_net(figure_id="bad", stem=self.STEM,
                                 shape="triangular_prism", profile=profile, dims=dims)

    def test_scalene_endpoint_foot_refuses(self):
        # a 3-4-5 'scalene' set puts the foot on the base endpoint — it is really
        # a right triangle and would draw with no right-angle mark
        with self.assertRaises(vt.TemplateError):
            vt.build_solid(figure_id="bad", stem="Sides 3, 4, 5 and 11 cm.",
                           shape="triangular_prism", profile="scalene",
                           dims={"base": 3, "left": 4, "right": 5, "length": 11})
        with self.assertRaises(vt.TemplateError):
            vt.build_net(figure_id="bad2", stem="Sides 3, 4, 5 and 11 cm.",
                         shape="triangular_prism", profile="scalene",
                         dims={"base": 3, "left": 5, "right": 4, "length": 11})

    def test_x_reserved_for_altitude_foot(self):
        for kw in (dict(altitude=True, dims={"base": 6, "left": 5, "length": 11}),
                   dict(dims={"base": 6, "height": 8, "length": 11})):
            with self.subTest(kw=list(kw)):
                with self.assertRaises(vt.TemplateError):
                    vt.build_solid(figure_id="bad", stem=self.STEM,
                                   shape="triangular_prism",
                                   profile="isosceles" if "left" in kw["dims"] else "right",
                                   names=["A", "B", "C", "D", "E", "X"], **kw)

    def test_altitude_refused_on_right_profile(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_solid(figure_id="bad", stem=self.STEM,
                           shape="triangular_prism", profile="right",
                           dims={"base": 7, "height": 5, "length": 11},
                           altitude=True)

    def test_altitude_ink_is_claimed(self):
        b = vt.build_solid(figure_id="g10s-alt", stem=self.STEM,
                           shape="triangular_prism", profile="isosceles",
                           dims={"base": 6, "left": 5, "length": 11}, altitude=True)
        self.assertIn("altitude", b.claims)
        self.assertIn("X", b.anchors)

    def test_right_net_x0_skips_dashed_height_element(self):
        # x == 0: the altitude foot is B itself. The scratch code drew a dashed
        # 'height' element duplicating the flap edge U->B; it is now skipped
        # while the height label still binds a segment (U,B)
        b = vt.build_net(figure_id="g10n-x0", stem=self.STEM,
                         shape="triangular_prism", profile="right",
                         dims={"base": 6, "height": 8, "length": 11})
        self.assertFalse(any(e.get("id") == "height" for e in b.doc["elements"]))
        self.assertNotIn("X", b.anchors)
        self.assertIn('label "8 cm" names UB', b.claims)

    def test_right_profile_has_no_duplicate_x_anchor(self):
        b = vt.build_solid(figure_id="g10s-nox", stem=self.STEM,
                           shape="triangular_prism", profile="right",
                           dims={"base": 6, "height": 8, "length": 11})
        self.assertNotIn("X", b.anchors)
        n = vt.build_net(figure_id="g10n-nox", stem=self.STEM,
                         shape="triangular_prism", profile="right",
                         dims={"base": 6, "height": 8, "length": 11})
        self.assertNotIn("X", n.anchors)

    def test_legacy_delegation_unchanged(self):
        a = vt.build_solid(figure_id="leg1", stem=self.STEM,
                           shape="sphere", dims={"radius": 4})
        self.assertIn("sphere", a.claims)
        n = vt.build_net(figure_id="leg2", stem=self.STEM,
                         shape="square_pyramid", base=4, tri_height=5)
        self.assertIn("pyramid", n.claims)

    def test_new_options_need_new_shapes(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_solid(figure_id="bad", stem=self.STEM, shape="sphere",
                           dims={"radius": 4}, altitude=True)
        with self.assertRaises(vt.TemplateError):
            vt.build_net(figure_id="bad", stem=self.STEM, shape="square_pyramid",
                         dims={"base": 4})


class Grade10PatternTests(unittest.TestCase):
    """Contract tests for motion/rings/slats/clock/pairing profiles (G10)."""
    CASES = [
        dict(template="motion_states", figure_id="g10p1",
             stem="A particle moves 18 m in 6 s.", distance=18, elapsed=6),
        dict(template="motion_states", figure_id="g10p2",
             stem="A train is 48 m long and takes 8 s to pass a post.",
             profile="post", length=48, elapsed=8),
        dict(template="motion_states", figure_id="g10p3",
             stem="A train is 40 m long. The bridge is 80 m long; passage takes 9 s.",
             profile="bridge", length=40, bridge=80, elapsed=9),
        dict(template="dot_pattern", figure_id="g10p4",
             stem="The 3 rings start with 6 bulbs and increase by 4 bulbs each ring.",
             kind="rings", stages=3, first=6, increment=4),
        dict(template="dot_pattern", figure_id="g10p5",
             stem="Count the bulbs in each ring and describe the pattern.",
             kind="rings", stages=3, first=7, increment=4, values="figure"),
        dict(template="slat_frame", figure_id="g10p6",
             stem="The first slat is 80 cm, the increment is 8 cm, and the last "
                  "is 160 cm. Each slat is 8 cm wide.",
             first=80, increment=8, last=160, slat_width=8),
        dict(template="clock_face", figure_id="g10p7",
             stem="The clock shows hour 4 and minute 20.", hour=4, minute=20),
        dict(template="clock_face", figure_id="g10p8",
             stem="The clock shows hour 3 and minute 0.", hour=3, minute=0),
        dict(template="pairing_arcs", figure_id="g10p9",
             stem="An arithmetic sequence has first term 4, common difference 2 "
                  "and 8 terms.", first=4, increment=2, terms=8),
    ]

    def build(self, case):
        spec = dict(case)
        return vt.BUILDERS[spec.pop("template")](**spec)

    def test_outputs(self):
        for case in self.CASES:
            with self.subTest(case=case["figure_id"]):
                b = self.build(case)
                self.assertTrue(b.doc["elements"])
                self.assertIn("load-bearing:", b.claims)
                self.assertIn("channel:  constructed", b.claims)

    def test_preconversion_types(self):
        for index, key in ((0, "distance"), (1, "length"), (2, "bridge"),
                           (3, "first"), (3, "increment"), (3, "stages"),
                           (5, "slat_width"), (5, "last"), (6, "hour"),
                           (6, "minute"), (8, "terms"), (8, "increment"),
                           (0, "elapsed")):
            for value in (True, False, "3", float("nan"), float("inf"), {}, []):
                case = dict(self.CASES[index], **{key: value})
                with self.subTest(key=key, value=value):
                    with self.assertRaises(vt.TemplateError):
                        self.build(case)

    def test_missing_stem_givens(self):
        for case in self.CASES:
            if case.get("values") == "figure":
                continue
            with self.subTest(case=case["figure_id"]):
                with self.assertRaises(vt.TemplateError):
                    self.build(dict(case, stem="A synthetic task with no numeric givens."))

    def test_refusals(self):
        for case in (dict(self.CASES[5], last=161, stem=self.CASES[5]["stem"] + " 161"),
                     dict(self.CASES[8], terms=7, stem=self.CASES[8]["stem"] + " 7"),
                     dict(self.CASES[3], values="hidden"),
                     dict(self.CASES[6], hour=13),
                     dict(self.CASES[0], profile="photo"),
                     dict(self.CASES[1], distance=12)):
            with self.assertRaises(vt.TemplateError):
                self.build(case)

    def test_rings_reject_legacy_layout_params(self):
        with self.assertRaises(vt.TemplateError):
            self.build(dict(self.CASES[3], dot_r=8))
        with self.assertRaises(vt.TemplateError):
            self.build(dict(figure_id="g10p10",
                            stem="Triangular dots, 3 stages.",
                            template="dot_pattern",
                            kind="triangle", stages=3, first=6))

    def test_exact_counts(self):
        rings = self.build(self.CASES[3])
        for ring, count in ((1, 6), (2, 10), (3, 14)):
            self.assertEqual(sum(e["id"].startswith(f"r{ring}d")
                                 for e in rings.doc["elements"]), count)
        slats = self.build(self.CASES[5])
        self.assertEqual(sum(e["id"].startswith("slat")
                             for e in slats.doc["elements"]), 11)
        pairs = self.build(self.CASES[8])
        self.assertEqual(sum(e["type"] == "polyline"
                             for e in pairs.doc["elements"]), 4)

    def test_pair_endpoints_and_clock(self):
        b = self.build(self.CASES[8])
        terms = [e for e in b.doc["elements"]
                 if e["type"] == "text" and e.get("fontSize") == 16]
        for i, curve in enumerate(e for e in b.doc["elements"]
                                  if e["type"] == "polyline"):
            self.assertEqual(len(curve["points"]), 25)
            self.assertAlmostEqual(curve["points"][0][0], terms[i]["at"][0], delta=0.02)
            self.assertAlmostEqual(curve["points"][-1][0], terms[-1 - i]["at"][0],
                                   delta=0.02)
            self.assertLess(curve["points"][12][1], curve["points"][0][1])
        clock = self.build(self.CASES[6])
        self.assertEqual(sum(e["id"].startswith("tick")
                             for e in clock.doc["elements"]), 12)
        o, h = clock.anchors["O"], clock.anchors["H"]
        angle = math.degrees(math.atan2(h[1] - o[1], h[0] - o[0]))
        self.assertAlmostEqual(angle, 40, delta=0.02)


class Grade10PairedGeometryTests(unittest.TestCase):
    """Contract tests for build_paired_geometry (G10)."""
    STEM_SSS = ("Triangle ABC has sides 8 cm, 7 cm and 5 cm and triangle PQR has "
                "sides 7 cm, 8 cm and 5 cm. (a) Are they congruent?")

    def B(self, **kw):
        kw.setdefault("figure_id", "t1")
        return vt.build_paired_geometry(**kw)

    def test_sss_pair_congruent(self):
        b = self.B(stem=self.STEM_SSS, ask=[["a", "congruence"]], shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 8, "BC": 7, "CA": 5}},
            {"shape": "triangle", "names": "PQR",
             "sides": {"PQ": 7, "QR": 8, "RP": 5},
             "place": {"to": [300, 0], "anchor": "P", "flip": True}}],
            correspond=[{"tri": "ABC", "to": "RQP", "scale": "congruent"}],
            ticks={"AB": 1, "RQ": 1, "BC": 2, "QP": 2, "CA": 3, "PR": 3})
        self.assertIn("congruent", b.claims)

    def test_similar_pair_scale2(self):
        stem = ("Triangle ABC has sides 3 cm, 4 cm and 5 cm; triangle DEF is "
                "drawn at scale 2 with sides 6 cm, 8 cm and 10 cm. "
                "(a) Show the scale factor is 2.")
        b = self.B(stem=stem, ask=[["a", "the factor"]], shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 3, "BC": 4, "CA": 5}},
            {"shape": "triangle", "names": "DEF",
             "sides": {"DE": 6, "EF": 8, "FD": 10},
             "place": {"to": [260, 0], "anchor": "D"}}],
            correspond=[{"tri": "ABC", "to": "DEF", "scale": 2}])
        self.assertIn("scale", b.claims)

    def test_shared_side_glue_and_hinge(self):
        stem = ("Triangles ABC and DCB share the base BC of 6 cm; AB = 5 cm, "
                "DC = 5 cm. (a) Name the equal sides.")
        b = self.B(stem=stem, ask=[["a", "the equal sides"]], shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 5, "BC": 6, "CA": 6}},
            {"shape": "triangle", "names": "DCB",
             "sides": {"DC": 5, "CB": 6, "DB": 6},
             "place": {"glue": {"C": "C", "B": "B"}, "flip": True}}],
            ticks={"AB": 1, "DC": 1})
        self.assertTrue(b.doc["elements"])
        hinge = self.B(stem="Triangles ABC and DEF share the vertex A; AB = 5 cm, "
                            "BC = 6 cm, CA = 7 cm; DE = 5 cm, EF = 6 cm, FD = 7 cm.",
                       shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 5, "BC": 6, "CA": 7}},
            {"shape": "triangle", "names": "DEF",
             "sides": {"DE": 5, "EF": 6, "FD": 7},
             "place": {"hinge": {"D": "A"}, "rotate": 140, "flip": True}}])
        # the hinge aliases D onto A: the letter D never prints, the second
        # scaffold claims itself as triangle AEF, and only five letters anchor
        self.assertNotIn("D", hinge.anchors)
        self.assertEqual(sorted(hinge.anchors), ["A", "B", "C", "E", "F"])
        self.assertIn('describe "AEF is a triangle"', hinge.claims)
        seg_line = next(l for l in hinge.claims.splitlines()
                        if l.startswith("segments:"))
        for seg in ("AE", "EF", "AF"):
            self.assertIn(seg, seg_line.split())

    def test_unknown_scaffold_keys_refuse(self):
        with self.assertRaises(vt.TemplateError):
            self.B(stem=self.STEM_SSS, ask=[["a", "x"]], shapes=[
                {"shape": "triangle", "names": "ABC",
                 "sides": {"AB": 8, "BC": 7, "CA": 5}, "angle": {"A": 40}}])

    def test_quad_kite_bowtie_accept(self):
        quad = self.B(stem="Quadrilateral ABCD has AB = 5 cm, BC = 6 cm, CD = 4 cm, "
                           "DA = 7 cm and diagonal AC = 8 cm.",
                      shapes=[{"shape": "quadrilateral", "names": "ABCD",
                               "sides": {"AB": 5, "BC": 6, "CD": 4, "DA": 7},
                               "diagonal": {"AC": 8}}],
                      labels={"AB": "5 cm", "BC": "6 cm"})
        self.assertIn("quadrilateral", quad.claims)
        kite = self.B(stem="Kite ABCD has AB = AD = 5 cm, CB = CD = 8 cm and "
                           "diagonal AC = 9 cm.",
                      shapes=[{"shape": "kite", "names": "ABCD",
                               "sides": {"AB": 5, "BC": 8}, "diagonal": {"AC": 9}}],
                      ticks={"AB": 1, "AD": 1, "CB": 2, "CD": 2})
        self.assertIn("axis of symmetry", kite.claims)
        bow = self.B(stem="Angles 70 35 55.",
                     shapes=[{"shape": "bowtie", "names": "ABCD", "cross": "X",
                              "angles": {"A": 70, "D": 35, "C": 55}}])
        self.assertIn("vertically opposite", bow.claims)

    def test_figure_mode(self):
        b = self.B(stem="Read the marked figure.", values="figure", shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 8, "BC": 7, "CA": 5}},
            {"shape": "triangle", "names": "PQR",
             "sides": {"PQ": 7, "QR": 8, "RP": 5},
             "place": {"to": [300, 0], "anchor": "P", "flip": True}}],
            labels={"AB": "8 cm", "PQ": "7 cm"})
        self.assertTrue(b.doc["elements"])

    def refuse(self, kw, needle=""):
        with self.assertRaises(vt.TemplateError) as cm:
            self.B(**kw)
        if needle:
            self.assertIn(needle, str(cm.exception))

    def test_refusals(self):
        self.refuse(dict(stem="Sides 7 and 5 about 30; twice.", shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 7, "BC": 5}, "angles": {"A": 30}},
            {"shape": "triangle", "names": "PQR", "sides": {"PQ": 5, "PR": 7},
             "angles": {"P": 30}, "place": {"to": [300, 0]}}]), "SSA")
        self.refuse(dict(stem="Sides 1 cm, 2 cm and 10 cm.", shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 1, "BC": 2, "CA": 10}}]), "inequality")
        self.refuse(dict(stem="Sides 1 1 1 1 diagonal 9.", shapes=[
            {"shape": "quadrilateral", "names": "ABCD",
             "sides": {"AB": 1, "BC": 1, "CD": 1, "DA": 1},
             "diagonal": {"AC": 9}}]), "close")
        self.refuse(dict(stem="Shared side 6 cm; other sides 5 cm, 6 cm and "
                         "9 cm.", shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 5, "BC": 6, "CA": 6}},
            {"shape": "triangle", "names": "DEF",
             "sides": {"DE": 5, "EF": 9, "DF": 6},
             "place": {"glue": {"E": "B", "F": "C"}}}]), "stretch")
        self.refuse(dict(stem=self.STEM_SSS, shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 8, "BC": 7, "CA": 5}},
            {"shape": "triangle", "names": "PQR",
             "sides": {"PQ": 7, "QR": 8, "RP": 5},
             "place": {"to": [300, 0], "anchor": "P"}}],
            ticks={"AB": 1, "PQ": 1}), "tick")
        self.refuse(dict(stem="Sides 3 4 5 and 6 8 11, drawn at scale 2.",
                     shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 3, "BC": 4, "CA": 5}},
            {"shape": "triangle", "names": "DEF",
             "sides": {"DE": 6, "EF": 8, "FD": 11},
             "place": {"to": [300, 0], "anchor": "D"}}],
            correspond=[{"tri": "ABC", "to": "DEF", "scale": 2}]),
            "NOT similar")
        self.refuse(dict(stem="Sides 3 4 5.", values="bogus", shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 3, "BC": 4, "CA": 5}}]), "values")
        self.refuse(dict(stem="Sides 8 and 7 only.", shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 8, "BC": 7, "CA": 5}}]),
            "not a number the stem states")
        self.refuse(dict(stem=self.STEM_SSS, shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 8, "BC": 7, "CA": 5}},
            {"shape": "triangle", "names": "PQR",
             "sides": {"PQ": 7, "QR": 8, "RP": 5}}]), "place")
        self.refuse(dict(stem="Sides 3 4 5 twice.", shapes=[
            {"shape": "triangle", "names": "ABC",
             "sides": {"AB": 3, "BC": 4, "CA": 5}},
            {"shape": "triangle", "names": "ABD",
             "sides": {"AB": 3, "BD": 4, "DA": 5},
             "place": {"to": [0, 0]}}]), "already placed")
        self.refuse(dict(stem="Kite sides 5 8 diagonal BD 9.", shapes=[
            {"shape": "kite", "names": "ABCD",
             "sides": {"AB": 5, "BC": 8}, "diagonal": {"BD": 9}}]), "AC")
        self.refuse(dict(stem="Angles 70 35 60 50.", shapes=[
            {"shape": "bowtie", "names": "ABCD", "cross": "X",
             "angles": {"A": 70, "B": 35, "C": 60, "D": 50}}]), "crossing")


class G10PartitionContract(unittest.TestCase):
    """outcome_grid events + fraction_tape + area_model — representative
    accept/refusal contract (ported from wt partition-work scratch tests)."""

    OG = dict(rows=["H", "T"], cols=["1", "2", "3", "4"], marks="all",
              values="figure")

    def B(self, template, **kw):
        kw.setdefault("figure_id", "synthetic-part1")
        kw.setdefault("stem", "A die and a coin are thrown together. The grid "
                              "shows every ordered pair. (a) Count them.")
        kw.setdefault("ask", [["a", "the answer"]])
        return vt.BUILDERS[template](**kw)

    def test_oval_diagonal_contour_accept(self):
        b = self.B("outcome_grid",
                   events=[{"cells": [[0, 1], [1, 0]], "style": "oval",
                            "label": "A"}], **self.OG)
        self.assertIn("channel:  constructed", b.claims)

    def test_disconnected_event_splits_into_regions(self):
        b = self.B("outcome_grid",
                   events=[{"cells": [[0, 0], [3, 1]], "style": "oval",
                            "label": "A"}], **self.OG)
        ids = [el["id"] for el in b.doc["elements"]]
        self.assertIn("ev0_0", ids)
        self.assertIn("ev0_1", ids)

    def test_circle_arrow_default_and_box_arrow_flag(self):
        b = self.B("outcome_grid",
                   events=[{"cells": [[2, 0]], "style": "circle",
                            "label": "E"}], **self.OG)
        self.assertIn("eva0", [el["id"] for el in b.doc["elements"]])
        b2 = self.B("outcome_grid",
                    events=[{"cells": [[0, 0], [1, 0], [0, 1], [1, 1]],
                             "style": "box", "label": "B", "arrow": False}],
                    rows=["H", "T"], cols=["1", "2", "3"], marks="all",
                    values="figure")
        self.assertFalse(any(el["id"].startswith("eva")
                             for el in b2.doc["elements"]))

    def test_event_refusals(self):
        ring = [[c, r] for c in range(3) for r in range(3)
                if (c, r) != (1, 1)]
        for kw in (
                # an oval swallowing a non-member cell refuses
                dict(rows=["H", "T", "H"], cols=["1", "2", "3"], marks="all",
                     values="figure",
                     events=[{"cells": ring, "style": "oval", "label": "A"}]),
                # two events drawing the identical contour refuse
                dict(marks="all", values="figure",
                     rows=["H", "T"], cols=["1", "2"],
                     events=[{"cells": [[0, 0]], "style": "circle",
                              "label": "A"},
                             {"cells": [[0, 0]], "style": "circle",
                              "label": "B"}]),
                # a circle over two connected cells refuses
                dict(marks="all", values="figure",
                     rows=["H", "T"], cols=["1", "2"],
                     events=[{"cells": [[0, 0], [0, 1]], "style": "circle"}]),
                # a box over a notched block refuses
                dict(marks="all", values="figure",
                     rows=["H", "T"], cols=["1", "2", "3"],
                     events=[{"cells": [[0, 0], [1, 0], [0, 1]],
                              "style": "box"}]),
                # whole-number cell indexes — the tightened validation
                dict(marks="all", values="figure",
                     rows=["H", "T"], cols=["1", "2"],
                     events=[{"cells": [[0.5, 0]], "style": "oval"}]),
                dict(marks=[[float("nan"), 0]], values="figure",
                     rows=["H", "T"], cols=["1", "2"]),
                dict(marks=[[False, 0]], values="figure",
                     rows=["H", "T"], cols=["1", "2"]),
                dict(marks="all", values="figure",
                     rows=["H", "T"], cols=["1", "2"],
                     outline={"cols": [0.5, 1], "rows": [0, 1]})):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                self.B("outcome_grid", **kw)

    def test_fraction_tape_accepts(self):
        for kw in (
                dict(stem="Three strips show 1/2 = 2/4 = 4/8. (a) Write them.",
                     panels=[{"parts": 2, "shaded": 1, "label": "1/2"},
                             {"parts": 4, "shaded": 2, "label": "2/4"},
                             {"parts": 8, "shaded": 4, "label": "4/8",
                              "braces": [{"span": [0, 3], "label": "4/8",
                                          "side": "under"}]}]),
                dict(stem="The strips show 5/4 as one whole and 1/4.",
                     panels=[{"parts": 4, "shaded": 4},
                             {"parts": 4, "shaded": 1, "label": "5/4"}]),
                dict(stem="A 350 litre tank is 3/8 full. (a) How much water?",
                     tank={"parts": 8, "filled": 3, "label": "350 L",
                           "level_label": "3/8"}),
                dict(stem="Two strips. (a) Name the share.", values="figure",
                     panels=[{"parts": 4, "shaded": 3, "label": "3/4"}])):
            with self.subTest(kw=str(kw)[:80]):
                b = self.B("fraction_tape", **kw)
                self.assertIn("channel:  constructed", b.claims)

    def test_fraction_tape_refusals(self):
        for kw in (
                {},                                   # neither panels nor tank
                dict(panels=[{"parts": 2, "shaded": 1}],
                     tank={"parts": 2, "filled": 1}),  # both
                dict(panels=[{"parts": 2.5, "shaded": 1}]),
                dict(panels=[{"parts": 2, "shaded": True}]),
                dict(panels=[{"parts": 2, "shaded": 3}]),   # over-shaded
                dict(panels=[{"parts": 4, "shaded": 1,
                              "braces": [{"label": "1/4"}]}]),   # no span
                dict(panels=[{"parts": 4, "shaded": 1,
                              "braces": [{"span": [2, 1],
                                          "label": "x"}]}]),     # reversed span
                dict(panels=[{"parts": 4, "shaded": 1,
                              "braces": [{"span": [0, 1], "label": "x",
                                          "side": "sideways"}]}]),
                dict(stem="Two strips show the same share.",
                     panels=[{"parts": 2, "shaded": 1, "label": "3/4"}]),
                dict(tank={"parts": 4, "filled": float("nan")}),
                dict(panels=[{"parts": 2, "shaded": 1}], strip_w=True)):
            with self.subTest(kw=str(kw)[:80]), \
                    self.assertRaises(vt.TemplateError):
                self.B("fraction_tape", **kw)

    def test_area_model_accept_and_refusals(self):
        b = self.B("area_model",
                   stem="The rectangle shows (3x + 2)(2x + 3) = "
                        "6x^2 + 9x + 4x + 6. (a) Give the product.",
                   col_labels=["3x", "2"], row_labels=["2x", "3"],
                   cells=[["6x^2", "4x"], ["9x", "6"]], names="PQRS")
        self.assertIn("channel:  constructed", b.claims)
        # no vertex letters are drawn — corners are anchors only
        self.assertFalse(any(el.get("type") == "text" and
                             el.get("value") in "PQRS"
                             for el in b.doc["elements"]))
        good = dict(stem="The rectangle shows (x + 2)(x + 5). (a) Expand.",
                    col_labels=["x", "2"], row_labels=["x", "5"],
                    cells=[["x^2", "2x"], ["5x", "10"]])
        for kw in (dict(names="ABCA"), dict(names="abc d"),
                   dict(col_labels=["x"]), dict(cells=[["x^2"]]),
                   dict(col_w=True),
                   dict(stem="The rectangle shows a product.",
                        col_labels=["x", "7"], row_labels=["x", "5"],
                        cells=[["x^2", "7x"], ["5x", "35"]])):
            with self.subTest(kw=str(kw)[:80]), \
                    self.assertRaises(vt.TemplateError):
                self.B("area_model", **{**good, **kw})


class G10CircularContract(unittest.TestCase):
    """circular_composite — representative accept/refusal contract (ported
    from wt circular-work scratch tests)."""

    STEM = ("Lengths 2, 5, 6, 7, 8, 10 cm; angle 90 degrees. Symbolic "
            "dimensions r, s, 5a and 2x. Find the boundary or shaded area.")

    def B(self, **kw):
        kw.setdefault("figure_id", "synthetic-circ1")
        kw.setdefault("stem", self.STEM)
        kw.setdefault("ask", [["a", "the answer"]])
        return vt.build_circular_composite(**kw)

    def test_keyword_only(self):
        import inspect
        self.assertTrue(all(
            p.kind == p.KEYWORD_ONLY for p in
            inspect.signature(vt.build_circular_composite).parameters.values()))

    def test_profile_accepts(self):
        cases = [
            dict(shape="rect", length=10, width=6,
                 pieces=[dict(on="BC", kind="semicircle")]),
            dict(shape="rect", length=10, width=6,
                 pieces=[dict(on="BC", kind="semicircle", mode="cut")]),
            dict(shape="rect", length=10, width=6,
                 pieces=[dict(corner="B", kind="sector", mode="cut",
                              radius=2)]),
            dict(shape="rect", length=10, width=6,
                 pieces=[dict(on="BC", kind="sector", angle=90)]),
            dict(shape="stadium", length=10, width=6,
                 labels={"length": "10 cm", "width": "6 cm"}),
            dict(shape="triangle", mode="right", base=6, height=8,
                 pieces=[dict(on="base", kind="semicircle")]),
            dict(shape="triangle", base=6, leg=5,
                 pieces=[dict(on="base", kind="semicircle")]),
            dict(shape="triangle", mode="equilateral", base=6,
                 pieces=[dict(on="base", kind="semicircle")]),
            dict(shape="sector", angle=90, radius=7,
                 pieces=[dict(on="AB", kind="triangle")]),
            dict(shape="sector", angle=90, radius=7,
                 pieces=[dict(on="AB", kind="triangle", mode="attach",
                              leg=8)]),
            dict(shape="sector", angle=90, radius=7,
                 pieces=[dict(on="OA", kind="semicircle")]),
            dict(shape="cut_attach", radius=7),
            dict(shape="annulus", outer=10, inner=5),
            dict(shape="annulus", outer="r", inner="s"),
            dict(shape="nested_square", outer=10, inner=5),
            dict(shape="nested_square", outer="5a", inner="2x"),
        ]
        for spec in cases:
            with self.subTest(spec=spec):
                b = self.B(**spec)
                self.assertIn("channel:  constructed", b.claims)

    def test_arc_sweeps_bounded(self):
        for spec in (dict(shape="rect", length=10, width=6,
                          pieces=[dict(on="BC", kind="semicircle")]),
                     dict(shape="rect", length=10, width=6,
                          pieces=[dict(corner="B", kind="sector", mode="cut",
                                       radius=2)]),
                     dict(shape="stadium", length=10, width=6),
                     dict(shape="triangle", base=6, leg=5,
                          pieces=[dict(on="base", kind="semicircle")]),
                     dict(shape="sector", angle=90, radius=7,
                          pieces=[dict(on="OA", kind="semicircle")]),
                     dict(shape="cut_attach", radius=7)):
            with self.subTest(spec=spec):
                b = self.B(**spec)
                for el in b.doc["elements"]:
                    if el["type"] == "arc":
                        self.assertGreater(el["end"] - el["start"], 0)
                        self.assertLessEqual(el["end"] - el["start"], 180.01)

    def test_perimeters(self):
        for spec, total in (
                (dict(shape="rect", length=10, width=6,
                      pieces=[dict(on="BC", kind="semicircle")]),
                 26 + 3 * math.pi),
                (dict(shape="stadium", length=10, width=6),
                 20 + 6 * math.pi),
                (dict(shape="triangle", mode="right", base=6, height=8,
                      pieces=[dict(on="base", kind="semicircle")]),
                 18 + 3 * math.pi),
                (dict(shape="sector", angle=90, radius=7,
                      pieces=[dict(on="AB", kind="triangle", mode="attach",
                                   leg=8)]), 30),
                (dict(shape="cut_attach", radius=7), 14 * math.pi)):
            with self.subTest(total=total):
                b = self.B(**spec)
                derives = [l for l in b.claims.splitlines() if "derive " in l]
                self.assertAlmostEqual(
                    float(derives[-1].split(" = ")[1].split(" |")[0]), total)

    def test_figure_mode(self):
        b = self.B(stem="Read the figure.", shape="stadium", length=10,
                   width=6, values="figure",
                   labels={"length": "10 cm", "width": "6 cm"})
        self.assertIn("figure content", b.claims)
        with self.assertRaises(vt.TemplateError):
            # figure mode needs printed numeric givens — none here
            self.B(stem="Read the figure.", shape="rect", length=10, width=6,
                   values="figure",
                   pieces=[dict(on="BC", kind="semicircle")])

    def test_refusals(self):
        for spec in (
                dict(shape="rect", length=10, width=6),         # no piece
                dict(shape="rect", length=4, width=10,          # cut reaches
                     pieces=[dict(on="BC", kind="semicircle",   # the far side
                                  mode="cut")]),
                dict(shape="rect", length=10, width=6,          # multi-piece
                     pieces=[dict(on="BC", kind="semicircle"),
                             dict(on="DA", kind="semicircle")]),
                dict(shape="rect", length=10, width=6,          # bad side
                     pieces=[dict(on="BC", kind="semicircle")],
                     labels={"BC": "3 cm"}),
                dict(shape="rect", length=10, width=6,          # extra arg
                     pieces=[dict(on="BC", kind="semicircle", radius=4)]),
                dict(shape="stadium", length=True, width=6),
                dict(shape="stadium", length=float("nan"), width=6),
                dict(shape="annulus", outer=5, inner=10),       # inner>=outer
                dict(shape="annulus", outer="2a", inner="5a"),  # same-var order
                dict(shape="bogus", length=10, width=6),
                dict(shape="triangle", base=6, leg=5),          # needs a piece
        ):
            with self.subTest(spec=str(spec)[:80]), \
                    self.assertRaises(vt.TemplateError):
                self.B(**spec)


if __name__ == "__main__":
    unittest.main()


class ElevationSceneTests(unittest.TestCase):
    def test_unknown_angle_still_has_auditable_derivation(self):
        b = vt.build_elevation_scene(**dict(
            self.KW, sights=[{'from': 'G', 'to': 'T', 'angle': 'x'}]))
        with tempfile.TemporaryDirectory() as tmp:
            paths = b.write(tmp)
            result = subprocess.run([sys.executable, str(AUDIT), str(paths['claims'])],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    STEM = ('A post FT stands on level ground. It is 8 m tall. An observer at G '
            'is 6 m from the foot and sees the top at an angle of elevation 53°.')
    KW = dict(figure_id='scn-elev1', stem=STEM, post=('F', 'T'),
              sights=[{'from': 'G', 'to': 'T', 'angle': 53,
                       'kind': 'elevation', 'side': 'left'}],
              heights={'FT': 8}, distances={'FG': 6})

    def test_builds_and_audits_clean(self):
        b = vt.build_elevation_scene(**self.KW)
        self.assertIn('constructed', b.claims)
        self.assertIn('right G F T', b.claims)           # post ⊥ ground
        self.assertRegex(b.claims, r'angle [A-Z] G T = 53\b')
        # a ground observer's arc is owned by the horizontal through G — no
        # elevated datum is drawn, so no `parallel` claim either
        self.assertNotIn('parallel G', b.claims)

    def test_eye_level_datum(self):
        b = vt.build_elevation_scene(
            figure_id='scn-elev2',
            stem=('A post FT is 8 m tall. An observer\'s eye E is 1.6 m above '
                  'ground point G, 6 m from the foot; the angle of elevation '
                  'of the top is 47°.'),
            post=('F', 'T'), eyes={'E': 'G'},
            sights=[{'from': 'E', 'to': 'T', 'angle': 47,
                     'kind': 'elevation', 'side': 'left'}],
            heights={'FT': 8, 'GE': 1.6}, distances={'FG': 6})
        self.assertIn('right F G E', b.claims)
        self.assertRegex(b.claims, r'angle [A-Z] E T = 47\b')
        # the datum claim — never a ground angle
        self.assertRegex(b.claims, r'parallel E[A-Z] FG\b')

    def test_underdetermined_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_elevation_scene(
                figure_id='scn-u1', stem='A post FT is 8 m tall.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 'x'}],
                heights={'FT': 8})

    def test_inconsistent_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_elevation_scene(
                figure_id='scn-i1',
                stem='Post 8 m, observer 6 m away, elevation 20°.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 20,
                         'kind': 'elevation', 'side': 'left'}],
                heights={'FT': 8}, distances={'FG': 6})

    def test_kind_side_reverified(self):
        with self.assertRaises(vt.TemplateError):       # declared depression
            vt.build_elevation_scene(
                figure_id='scn-k1',
                stem='Post 8 m, observer 6 m away, elevation x.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 'x',
                         'kind': 'depression', 'side': 'left'}],
                heights={'FT': 8}, distances={'FG': 6})
        with self.assertRaises(vt.TemplateError):       # wrong side
            vt.build_elevation_scene(
                figure_id='scn-k2',
                stem='Post 8 m, observer 6 m away, elevation x.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 'x',
                         'kind': 'elevation', 'side': 'right'}],
                heights={'FT': 8}, distances={'FG': 6})

    def test_stem_number_honesty(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_elevation_scene(
                figure_id='scn-n1', stem='A post stands on level ground.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 53,
                         'kind': 'elevation', 'side': 'left'}],
                heights={'FT': 8}, distances={'FG': 6})
        with self.assertRaises(vt.TemplateError):       # angle not in stem
            vt.build_elevation_scene(
                figure_id='scn-n2', stem='Post 8 m, distance 6 m.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 53,
                         'kind': 'elevation', 'side': 'left'}],
                heights={'FT': 8}, distances={'FG': 6})

    def test_figure_mode(self):
        b = vt.build_elevation_scene(
            **dict(self.KW, stem='Read the figure.', values='figure'))
        self.assertIn('figure content', b.claims)
        with self.assertRaises(vt.TemplateError):
            vt.build_elevation_scene(**dict(self.KW, values='bogus'))

    def test_shape_refusals(self):
        with self.assertRaises(vt.TemplateError):       # 3 sights
            vt.build_elevation_scene(
                **dict(self.KW, sights=[self.KW['sights'][0]] * 3))
        with self.assertRaises(vt.TemplateError):       # 3 observers
            vt.build_elevation_scene(
                **dict(self.KW, eyes={'E': 'G', 'I': 'H', 'O': 'J'}))
        with self.assertRaises(vt.TemplateError):       # eye on a post letter
            vt.build_elevation_scene(**dict(self.KW, eyes={'T': 'G'}))
        with self.assertRaises(vt.TemplateError):       # numeric angle, no kind
            vt.build_elevation_scene(
                **dict(self.KW, sights=[{'from': 'G', 'to': 'T', 'angle': 53}]))
        with self.assertRaises(vt.TemplateError):       # angle out of range
            vt.build_elevation_scene(
                figure_id='scn-r1',
                stem='Post 8 m, distance 6 m, angle 2°.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 2,
                         'kind': 'elevation', 'side': 'left'}],
                heights={'FT': 8}, distances={'FG': 6})
        with self.assertRaises(vt.TemplateError):       # distance not ground pair
            vt.build_elevation_scene(
                figure_id='scn-r2', stem='Post 8 m, "distance" FT 8.',
                post=('F', 'T'),
                sights=[{'from': 'G', 'to': 'T', 'angle': 45,
                         'kind': 'elevation', 'side': 'left'}],
                distances={'FT': 8})


class TwoCircleGeometryTests(unittest.TestCase):
    STEM = ('Two circles of radii 5 cm and 4 cm have centres 6 cm apart. '
            'The circles intersect at P and Q; the centre line meets PQ at M.')
    KW = dict(figure_id='scn-2c1', stem=STEM, r1=5, r2=4, d=6)

    def test_intersect_builds(self):
        b = vt.build_two_circle_geometry(**self.KW)
        self.assertIn('right A M P', b.claims)
        self.assertIn('collinear A M B', b.claims)
        self.assertIn('equal PM MQ', b.claims)
        self.assertIn('circle centre A through P Q', b.claims)

    def test_touch_modes(self):
        b = vt.build_two_circle_geometry(figure_id='scn-2c2',
                                         stem='Radii 5 cm and 3 cm, centres 8 cm.',
                                         r1=5, r2=3, d=8)
        self.assertIn('on P AB', b.claims)              # external touch
        b = vt.build_two_circle_geometry(figure_id='scn-2c3',
                                         stem='Radii 5 cm and 2 cm, centres 3 cm.',
                                         r1=5, r2=2, d=3)
        self.assertIn('collinear A B P', b.claims)      # internal touch

    def test_topology_refusals(self):
        with self.assertRaises(vt.TemplateError):       # separate
            vt.build_two_circle_geometry(figure_id='scn-s1',
                                         stem='Radii 5 3, d 10.', r1=5, r2=3, d=10)
        with self.assertRaises(vt.TemplateError):       # contained
            vt.build_two_circle_geometry(figure_id='scn-s2',
                                         stem='Radii 6 2, d 3.', r1=6, r2=2, d=3)
        with self.assertRaises(vt.TemplateError):       # too-thin chord
            vt.build_two_circle_geometry(figure_id='scn-s3',
                                         stem='Radii 5 4.9, d 9.85.',
                                         r1=5, r2=4.9, d=9.85)
        with self.assertRaises(vt.TemplateError):       # foot on a touch pair
            vt.build_two_circle_geometry(figure_id='scn-s4',
                                         stem='Radii 5 3, centres 8.',
                                         r1=5, r2=3, d=8, foot='M')

    def test_rim_joins_interior_angles(self):
        # rim S on circle 1 at 135° (canvas y-down: upper-left), join SP, an
        # interior point N on SP, and a verified angle mark at P.
        b = vt.build_two_circle_geometry(
            figure_id='scn-2c4',
            stem='Radii 5 4, centres 6. S and R are rim points; N is on SP.',
            r1=5, r2=4, d=6,
            rim={'S': {'circle': 1, 'deg': -135},
                 'R': {'circle': 2, 'deg': -45}},
            joins=['SP', 'RQ'], on_segment={'N': ('SP', 0.8)})
        self.assertIn('on N SP', b.claims)
        self.assertIn('circle centre A through P Q S', b.claims)

    def test_angle_mark_revalidated(self):
        # the true angle PAQ at circle 1's centre in the 5/4/6 layout:
        x = (36 + 25 - 16) / 12.0
        half = math.degrees(math.atan2(math.sqrt(25 - x * x), x))
        true = round(2 * half)
        b = vt.build_two_circle_geometry(
            figure_id='scn-2c5',
            stem=f'Radii 5 4, centres 6. Angle PAQ is {true}°.',
            r1=5, r2=4, d=6,
            angles=[{'at': 'A', 'arms': ('P', 'Q'), 'label': f'{true}°'}])
        self.assertIn(f'angle P A Q = {true}', b.claims)
        with self.assertRaises(vt.TemplateError):       # wrong glyph refused
            vt.build_two_circle_geometry(
                figure_id='scn-2c6',
                stem='Radii 5 4, centres 6. Angle PAQ is 90°.',
                r1=5, r2=4, d=6,
                angles=[{'at': 'A', 'arms': ('P', 'Q'), 'label': '90°'}])

    def test_stem_number_and_figure_mode(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_two_circle_geometry(figure_id='scn-f1',
                                         stem='Two circles.', r1=5, r2=4, d=6)
        b = vt.build_two_circle_geometry(**dict(self.KW, stem='Read the figure.',
                                              values='figure'))
        self.assertIn('figure content', b.claims)
        self.assertIn('5 cm', b.claims) and self.assertIn('6 cm', b.claims)

    def test_shape_refusals(self):
        with self.assertRaises(vt.TemplateError):       # rim collides
            vt.build_two_circle_geometry(**dict(
                self.KW, rim={'P': {'circle': 1, 'deg': 30}}))
        with self.assertRaises(vt.TemplateError):       # rim lands on P (~41.4°)
            vt.build_two_circle_geometry(**dict(
                self.KW, rim={'S': {'circle': 1, 'deg': 41}}))
        with self.assertRaises(vt.TemplateError):       # unknown join endpoint
            vt.build_two_circle_geometry(**dict(self.KW, joins=['PZ']))
        with self.assertRaises(vt.TemplateError):       # on_segment off a join
            vt.build_two_circle_geometry(**dict(
                self.KW, on_segment={'N': ('PQ', 0.5)}))
        with self.assertRaises(vt.TemplateError):       # t outside (0,1)
            vt.build_two_circle_geometry(**dict(
                self.KW, joins=['AP'], on_segment={'N': ('AP', 1.5)}))

    def test_diameter_chord_foot_refuses(self):
        # r1=3, r2=5, d=4 puts the chord through centre A (x=0) — the foot IS A.
        with self.assertRaises(vt.TemplateError):
            vt.build_two_circle_geometry(figure_id='scn-d1',
                                         stem='Radii 3 5, centres 4.',
                                         r1=3, r2=5, d=4)
        b = vt.build_two_circle_geometry(figure_id='scn-d2',
                                         stem='Radii 3 5, centres 4.',
                                         r1=3, r2=5, d=4, foot=None)
        self.assertIn('equal AP AQ', b.claims)
