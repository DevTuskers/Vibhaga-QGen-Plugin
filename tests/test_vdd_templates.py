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


def audit(claims: str, tmpdir: str) -> subprocess.CompletedProcess:
    p = Path(tmpdir) / "claims.txt"
    p.write_text(claims, encoding="utf-8")
    return subprocess.run([sys.executable, str(AUDIT), str(p)],
                          capture_output=True, text=True)


CUBOID_52 = ("A cuboid has length 5 cm, width 3 cm and height 2 cm. "
             "(a) Give the numbers of faces, edges and vertices.")


class EveryBuilderAuditsClean(unittest.TestCase):
    """Each SELF_TEST spec (synthetic stems) must reach audit exit 0 with no edits."""

    def test_all_nine_self_test_specs_audit(self):
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
        self.assertIn("grid 6 by 6", b.claims)            # rows x cols over the corner anchors
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

    def test_sinhala_label_refused(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                per_symbol=4, rows=[["සඳුදා", 8]])
        self.assertIn("Sinhala", str(cm.exception))

    def test_sinhala_label_allowed_on_sinhala_medium(self):
        """vdd-check rule 3 is medium-conditional: a sinhala-medium question's figure may —
        should — carry Sinhala labels (T-S6b-6). The build must pass it through."""
        b = vt.build_pictograph(figure_id="t1", stem="One circle stands for 4 cups.",
                                ask=[["a", "the cups each day"]],
                                per_symbol=4, rows=[["සඳුදා", 8], ["අඟහරුවාදා", 10]],
                                medium="sinhala")
        self.assertIn('label "සඳුදා" names row1', b.claims)
        r = audit(b.claims, tempfile.mkdtemp())
        self.assertEqual(r.returncode, 0, r.stdout)

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


if __name__ == "__main__":
    unittest.main()
