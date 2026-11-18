"""G6-8 readiness hardening — refusals and regressions for the audit's findings.

Every builder now rejects bools, strings, non-finite and oversized numerics with
a TemplateError BEFORE conversion or arithmetic (the G9 `_num` pattern, via the
shared `_validate_numeric_inputs` wrapper), `finish` validates the common
metadata/ask block once for all builders, and the histogram/ogive half-step
lattice checks run on exact Decimal arithmetic so valid decimal data is no
longer falsely refused.

Two output changes are explicitly approved (see builder-audit.md):
  * pictograph row-label claims target the emitted ids `row{ri}` (was the
    off-by-one `row{ri+1}`);
  * marked_geometry floating angle-label anchors bind the seated glyph's own
    `at` (was the pre-float seed that finish() then relocated).

All stems and figure_ids here are synthetic — never corpus text.
"""

import math
import unittest

import tools.vdd_templates as vt


ASK = [["a", "the unknown"]]


class P1RawCrashes(unittest.TestCase):
    """Audit P1: inputs that raised NameError/TypeError or silently coerced."""

    def test_grid_polygon_off_lattice_is_template_error(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_grid_polygon(figure_id="probe1",
                                  stem="A shape on a grid of 1 cm squares.",
                                  ask=ASK, cell=1,
                                  vertices=[[0, 0], [3.5, 0], [0, 2]])
        self.assertIn("grid_polygon", str(cm.exception))

    def test_rectangle_points_needs_both_dimensions(self):
        for kw in (dict(length=8), dict(width=5)):
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError):
                    vt.build_rectangle_points(
                        figure_id="probe1",
                        stem="A rectangle is 8 cm by 5 cm.", ask=ASK, **kw)

    def test_abacus_nonfinite_place_value(self):
        for v in (math.nan, math.inf, -math.inf, 10 ** 400):
            with self.subTest(v=v):
                with self.assertRaises(vt.TemplateError):
                    vt.build_abacus(figure_id="probe1",
                                    stem="One rod stands for 1.",
                                    ask=ASK, place_values=[v], beads=[1])

    def test_triangle_marks_bool_counts_refuse(self):
        base = dict(figure_id="probe1", stem="In triangle ABC, AB = AC.",
                    ask=ASK, angles={"A": 50, "B": 60, "C": 70})
        for kw in (dict(ticks={"AB": True}), dict(ticks={"AB": False}),
                   dict(arcs={"A": True}), dict(arcs={"A": False})):
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError):
                    vt.build_triangle_marks(**{**base, **kw})

    def test_dot_pattern_bool_stages_refuse_all_kinds(self):
        for kind_ in ("triangle", "square", "rectangle"):
            for stages in (True, False):
                with self.subTest(kind=kind_, stages=stages):
                    with self.assertRaises(vt.TemplateError):
                        vt.build_dot_pattern(figure_id="probe1",
                                             stem="A pattern of dots.",
                                             ask=ASK, kind=kind_,
                                             stages=stages)

    def test_inequality_line_open_flags_must_be_bool(self):
        for bad in (dict(open_a=1), dict(open_b="yes"), dict(open_a=None)):
            iv = {"a": -2, "b": 3, **bad}
            with self.subTest(bad=bad):
                with self.assertRaises(vt.TemplateError):
                    vt.build_inequality_line(
                        figure_id="probe1", stem="x is between -2 and 3.",
                        ask=ASK, v0=-4, v1=4, interval=iv)


class FinishMetadataValidation(unittest.TestCase):
    """`finish` now validates the shared metadata once, for every builder."""

    def _build(self, **kw):
        base = dict(figure_id="probe1", stem="A rectangle is 8 cm by 5 cm.",
                    ask=ASK, length=8, width=5)
        return vt.build_rectangle_points(**{**base, **kw})

    def test_bad_stem_figure_id_title_description(self):
        # NB: empty-string title/description are swallowed by the builders'
        # `title or <default>` fallbacks before finish() sees them — that is
        # pre-existing behaviour; only typed/whitespace junk reaches the gate
        for kw in (dict(stem=""), dict(stem=4), dict(figure_id=""),
                   dict(title=7), dict(description=b"x")):
            with self.subTest(kw=kw):
                with self.assertRaises(vt.TemplateError):
                    self._build(**kw)

    def test_medium_must_be_supported(self):
        for m in ("klingon", "", None, 3):
            with self.subTest(m=m):
                with self.assertRaises(vt.TemplateError):
                    self._build(medium=m)
        for m in ("english", "sinhala", "tamil"):
            self._build(medium=m)   # the supported set builds

    def test_ask_must_be_nonempty_well_formed(self):
        for ask in ([], (), "a", [["a"]], [["a", "x", "extra"]],
                    [[1, "text"]], [["a", ""]], [["a", "line\nbreak"]],
                    [["a", "one"], ["a", "two"]]):          # duplicate ref
            with self.subTest(ask=ask):
                with self.assertRaises(vt.TemplateError):
                    self._build(ask=ask)


class EarlyNumericGates(unittest.TestCase):
    """Bool/string/non-finite/oversized numerics refuse before arithmetic."""

    def test_scalar_gates(self):
        stem = "A synthetic figure with lengths 8 and 5."
        cases = [
            (vt.build_rays_from_point,
             dict(rays={"A": "NE"}, ray_len="long")),
            (vt.build_rays_from_point,
             dict(rays={"A": "NE"}, ray_len=math.nan)),
            (vt.build_number_line,
             dict(v0=10 ** 400, v1=10, parts_per_unit=2)),
            (vt.build_number_line,
             dict(v0="low", v1=10, parts_per_unit=2)),
            (vt.build_house_pentagon,
             dict(AB=math.inf, BC=4, DA=4, CP=4, PD=4)),
            (vt.build_cuboid, dict(length=True, width=3, height=4)),
            (vt.build_coordinate_plane, dict(x_max="5", y_max=5)),
            (vt.build_parallel_lines,
             dict(lines=["AB", "CD"],
                  distance={"between": ["AB", "CD"], "value": "far",
                            "unit": "cm"})),
            (vt.build_bar_chart,
             dict(categories=["Jan", "Feb"],
                  series=[{"name": "", "values": [4, 6]}],
                  step=True, v_max=10)),
            (vt.build_symmetry_grid,
             dict(cell=1, half=[[0, 0], [1, 1]],
                  axis={"through": [[0, 0], [0, 4]]}, cols=math.nan)),
        ]
        for fn, kw in cases:
            with self.subTest(builder=fn.__name__, kw=kw):
                with self.assertRaises(vt.TemplateError):
                    fn(figure_id="probe1", stem=stem, ask=ASK, **kw)

    def test_paired_geometry_oversized_int_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_paired_geometry(
                figure_id="probe1",
                stem="Triangle ABC has sides 8 cm, 7 cm and 5 cm.", ask=ASK,
                shapes=[{"shape": "triangle", "names": "ABC",
                         "sides": {"AB": 8, "BC": 7, "CA": 5}}],
                base_px=10 ** 400)


class DecimalLattice(unittest.TestCase):
    """Histogram/ogive half-step checks and _arange run on exact Decimals."""

    # step 0.4 → half-step 0.2: `0.6 % 0.2` = 0.1999… on binary floats, so the
    # old remainder check refused this VALID data; Decimal(str(…)) accepts it.
    # Such a dense axis can't seat its own numerals (clearance), so the proof
    # that the data is now ACCEPTED is that any refusal is a clearance/label
    # refusal — never the lattice message "multiple of step/2". A step ≥ ~0.5
    # also builds end-to-end.
    def test_histogram_decimal_half_steps_pass_the_lattice(self):
        # the audit's own false-refusal case: valid half-step decimals
        try:
            vt.build_histogram(figure_id="probe1",
                               stem="A histogram on an axis with step 0.4 up to 1.2.",
                               ask=ASK, bounds=[0, 10, 20], freqs=[0.6, 0.2],
                               step=0.4, v_max=1.2, values="figure")
        except vt.TemplateError as e:
            self.assertNotIn("multiple of step/2", str(e))
        b = vt.build_histogram(figure_id="probe1",
                               stem="A histogram on an axis with step 0.6 up to 2.4.",
                               ask=ASK, bounds=[0, 10, 20], freqs=[0.9, 1.5],
                               step=0.6, v_max=2.4, values="figure")
        self.assertIn("probe1", b.claims)

    def test_histogram_non_half_step_still_refuses(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_histogram(figure_id="probe1",
                               stem="A histogram on an axis with step 0.4 up to 1.2.",
                               ask=ASK, bounds=[0, 10, 20], freqs=[0.5, 0.4],
                               step=0.4, v_max=1.2, values="figure")
        self.assertIn("multiple of step/2", str(cm.exception))

    def test_ogive_decimal_half_steps_pass_the_lattice(self):
        try:
            vt.build_ogive(figure_id="probe1",
                           stem="A cumulative-frequency curve, step 0.4 up to 1.2.",
                           ask=ASK, bounds=[0, 10, 20, 30],
                           cum_freqs=[0, 0.2, 0.6, 1.2],
                           step=0.4, v_max=1.2, values="figure")
        except vt.TemplateError as e:
            self.assertNotIn("multiple of step/2", str(e))
        b = vt.build_ogive(figure_id="probe1",
                           stem="A cumulative-frequency curve, step 0.6 up to 2.4.",
                           ask=ASK, bounds=[0, 10, 20, 30],
                           cum_freqs=[0, 0.3, 0.9, 1.5],
                           step=0.6, v_max=2.4, values="figure")
        self.assertIn("probe1", b.claims)

    def test_ogive_non_half_step_still_refuses(self):
        with self.assertRaises(vt.TemplateError) as cm:
            vt.build_ogive(figure_id="probe1",
                           stem="A cumulative-frequency curve, step 0.4 up to 1.2.",
                           ask=ASK, bounds=[0, 10, 20, 30],
                           cum_freqs=[0, 0.3, 0.6, 1.2],
                           step=0.4, v_max=1.2, values="figure")
        self.assertIn("multiple of step/2", str(cm.exception))


class ApprovedGoldenChanges(unittest.TestCase):
    """The two explicit exceptions to byte-identical output."""

    def test_pictograph_row_claims_target_emitted_ids(self):
        # emitted row ids are row0, row1, … — claims used to say row{ri+1}
        b = vt.build_pictograph(figure_id="probe1",
                                stem="One circle stands for 4 cups.",
                                ask=[["a", "the cups each day"]],
                                per_symbol=4, rows=[["Mon", 8], ["Tue", 10]])
        self.assertIn('label "Mon" names row0', b.claims)
        self.assertIn('label "Tue" names row1', b.claims)
        self.assertNotIn("names row2", b.claims)

    def test_marked_geometry_floated_angle_anchor_is_the_glyph(self):
        # audit probe: selftest-mgtri without `labels`, base_px=120 — the angle
        # label floats out of the wedge; the claim anchor must be the seat the
        # glyph lands on, not the pre-float seed
        b = vt.build_marked_geometry(
            figure_id="probe1",
            stem="In triangle ABC, AB = 12 cm. M is the midpoint of AB and D is "
                 "the foot of the perpendicular from C to AB. The angle at A "
                 "is marked x. AM = MB = 6 cm. (a) Find x.",
            ask=[["a", "the angle x"]],
            shape="triangle",
            angles={"A": 55, "B": 65, "C": 60}, sides={"AB": 12},
            medians={"M": ["C", "AB"]}, altitudes={"D": ["C", "AB"]},
            ticks={"AM": 1, "MB": 1}, arcs={"A": 1, "B": 2, "C": 3},
            angle_labels={"A": "x"}, base_px=120)
        glyph = next(e for e in b.doc["elements"] if e.get("id") == "alA")
        self.assertIn('label "x" names A1', b.claims)
        ax, ay = b.anchors["A1"]
        self.assertAlmostEqual(ax, glyph["at"][0], places=6)
        self.assertAlmostEqual(ay, glyph["at"][1], places=6)


class CriticRoundOne(unittest.TestCase):
    """Findings from the fresh-eyes hardening critic (2026-11-18)."""

    def test_sector_figure_mode_needs_printed_givens(self):
        # audit P1: an unlabelled figure-mode sector has no readable numeric ink
        for kw in (dict(labels=None), dict(labels={"arc": "l"})):
            with self.subTest(kw=kw), self.assertRaises(vt.TemplateError):
                vt.build_sector(figure_id="probe1", stem="Read the figure.",
                                ask=[["a", "the arc length"]],
                                angle=90, radius=7, values="figure", **kw)
        # every numeric given labelled on its own boundary builds
        b = vt.build_sector(figure_id="probe1", stem="Read the figure.",
                            ask=[["a", "the arc length"]],
                            angle=90, radius=7, values="figure",
                            labels={"radius": "7 cm", "angle": "90°"})
        self.assertTrue(b.claims)
        # a 180° sector needs no angle label — the diameter reads itself
        b = vt.build_sector(figure_id="probe1", stem="Read the figure.",
                            ask=[["a", "the perimeter"]],
                            angle=180, radius=7, values="figure",
                            labels={"radius": "7 cm"})
        self.assertTrue(b.claims)

    def test_rays_bool_bearing_refuses(self):
        with self.assertRaises(vt.TemplateError):
            vt.build_rays_from_point(figure_id="probe1",
                                     stem="Bearings 90 and 1.",
                                     ask=[["a", "the angle"]],
                                     rays={"A": True, "B": 90})
        b = vt.build_rays_from_point(figure_id="probe1",
                                     stem="Bearings 90 and 1.",
                                     ask=[["a", "the angle"]],
                                     rays={"A": 1, "B": 90})
        self.assertTrue(b.claims)

    def test_non_string_stem_refuses(self):
        for bad in (4, None, [], {}):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                vt.build_pictograph(figure_id="probe1", stem=bad,
                                    ask=[["a", "the cups"]],
                                    per_symbol=4, rows=[["Mon", 8]])

    def test_ogive_guide_name_namespace(self):
        args = dict(figure_id="probe1",
                    stem="Edges 0, 10, 20, 30; cumulative 0, 6, 14, 20; scale 2 to 24.",
                    ask=[["a", "the median"]],
                    bounds=[0, 10, 20, 30], cum_freqs=[0, 6, 14, 20],
                    step=2, v_max=24)
        for nm in ("E", "V", "O", "X"):
            with self.subTest(nm=nm), self.assertRaises(vt.TemplateError):
                vt.build_ogive(**args, guide={"y": 10, "name": nm})
        b = vt.build_ogive(**args, guide={"y": 10, "name": "M"})
        self.assertTrue(b.claims)


if __name__ == "__main__":
    unittest.main()
