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
        self.assertIn('label "Mon" names row1', b.claims)
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


class ByteIdentity(unittest.TestCase):
    """The floating-label machinery must not change any existing template's bytes —
    sha256 over each self-test spec's three emitted files, captured on origin/main."""

    GOLDEN = {
        "selftest-cuboid": "05f09debdef31ece88cfbc7ffc0036095112bab21c2ff513ffd1afa5b8f58c9c",
        "selftest-dots": "7ed9088e060208c13050f2dddfb4e846ab7c7a859f364ebd64f94d4230dea166",
        "selftest-grid": "e7f6fda91430b0ffa92a3071eab54c5f3e5e54d946e67ec35b93899be1bed393",
        "selftest-house": "b7efe080cc9db6bc8e028b0ec5e7ca2e0a5a12757295489d7c663f8512762f38",
        "selftest-line": "aaabd2c6e476e4cb67c22dcb3c1f506aba59e7e2fc29764635bd886a52279851",
        "selftest-pict": "c39c157a1f4fcbedcad1e30515b71184db67d234930e96ec51d7c515245ccdd3",
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


if __name__ == "__main__":
    unittest.main()
