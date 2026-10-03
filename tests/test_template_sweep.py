"""tests/test_template_sweep.py — W9 item F: a parameter sweep over the nine figure templates.

The point is coverage, not the golden path: each builder is run across a parameter grid with
synthetic stems that state the numbers it needs, and the sweep asserts:

  · every case either builds or raises TemplateError with a STATED reason — any other exception
    is a bug, and so is a refusal whose reason is the template's own label pre-flight
    ("~N rendered px from …") on a case that isn't deliberately extreme;
  · every built claim set passes audit-claim-set.py IN-PROCESS (fails == 0);
  · a built figure with >32 elements carries a `budget:` claim-set line;
  · a built canvas is never taller than MAX_ASPECT × its width;
  · number_line: when a nice step (1·2·5 decades + 25s) divides the span and fits, the emitted
    `tick … step k` numeral step is nice.

Runtime is kept under ~30 s by auditing in-process and by keeping each grid modest.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt                              # noqa: E402

_spec = importlib.util.spec_from_file_location("audit_claim_set", TOOLS / "audit-claim-set.py")
acs = importlib.util.module_from_spec(_spec)           # noqa: E402  (hyphenated — imported, not copied)
_spec.loader.exec_module(acs)

SELF_FLIGHT = re.compile(r"rendered px (from|apart)")   # finish()'s label pre-flight refusal
STEP_RE = re.compile(r"tick\s+[A-Z]+\s+step\s+(\d+)")
DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Hol"]


def C(builder, extreme=False, **kw):
    return {"kind": builder, "kw": kw, "extreme": extreme}


def case_grid() -> list[dict]:
    cases = []
    # number_line — a few bases, spans 1..60, ppu 1..10, 0–4 lattice points
    for v0 in (0, 60, 730):
        for span in (1, 3, 5, 20, 60):
            v1 = v0 + span
            for ppu in (1, 2, 4, 5, 10):
                stem = (f"The number line shows {v0} to {v1}. Each unit is divided into "
                        f"{ppu} equal parts.")
                base = dict(stem=stem, v0=v0, v1=v1, parts_per_unit=ppu)
                ex = span * ppu > 100            # hundreds of minor ticks is a deliberate extreme
                cases.append(C("number_line", extreme=ex, **base))
                cases.append(C("number_line", extreme=ex,
                               **{**base, "points": {"P": v0 + (span * ppu // 2) / ppu}}))
                ks = sorted({min(span * ppu, i * max(1, span * ppu // 4)) for i in range(4)})
                pts = {n: v0 + k / ppu for n, k in zip("PQRS", ks)}
                cases.append(C("number_line", extreme=ex, **{**base, "points": pts}))
    # shaded_grid — every cols×rows in 1..10, one shading pattern; a second pattern on a subset
    for c in range(1, 11):
        for r in range(1, 11):
            cases.append(C("shaded_grid", stem=f"A grid of {c * r} squares of side 1 cm.",
                           cols=c, rows=r, full=[(0, 0)]))
    for c in (2, 3, 5):
        for r in (2, 3, 5):
            cases.append(C("shaded_grid", stem=f"A grid of {c * r} squares of side 1 cm.",
                           cols=c, rows=r, full=[(0, 0), (c - 1, r - 1)],
                           half=[(c - 1, 0, "tl")]))
    # dot_pattern — the three kinds × stages 1..8
    for kind in ("triangle", "square", "rectangle"):
        for s in range(1, 9):
            cases.append(C("dot_pattern",
                           stem=f"The first {s} figures of a dot pattern are shown; their dot "
                                f"counts are {kind} numbers.",
                           kind=kind, stages=s))
    # pictograph — 1..8 rows, whole and half counts
    for n_rows in range(1, 9):
        for per in (2, 4):
            stem = f"One full circle stands for {per} cups."
            whole = [[DAY_LABELS[i], per * (i + 1)] for i in range(n_rows)]
            cases.append(C("pictograph", stem=stem, per_symbol=per, rows=whole))
            half = [[DAY_LABELS[i], per * i + per // 2] for i in range(n_rows)]
            cases.append(C("pictograph", stem=stem, per_symbol=per, rows=half))
    # halves under an ODD key are unrepresentable — a stated refusal, not a bug
    cases.append(C("pictograph", stem="One full circle stands for 5 cups.",
                   per_symbol=5, rows=[["Mon", 5], ["Tue", 8]]))
    # grid_polygon — a few rectilinear shapes × cell × vertex labels
    shapes = [
        [[0, 0], [3, 0], [3, 2], [0, 2]],
        [[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4]],
        [[0, 0], [5, 0], [5, 2], [3, 2], [3, 4], [2, 4], [2, 2], [0, 2]],
        [[0, 0], [6, 0], [6, 1], [3, 1], [3, 3], [0, 3]],
    ]
    for verts in shapes:
        for cell in (1, 2):
            for vl in (False, True):
                cases.append(C("grid_polygon",
                               stem=f"A closed shape on a grid, each square of side {cell} cm.",
                               cell=cell, vertices=verts, vertex_labels=vl))
    # vertex labels seat on exterior bisectors — they only build when every corner's wedge
    # runs OUT of the grid, which needs the polygon spanning the full grid (cols/rows given)
    cases.append(C("grid_polygon",
                   stem="A closed shape on a grid, each square of side 1 cm.",
                   cell=1, vertices=[[0, 0], [3, 0], [3, 2], [0, 2]], cols=3, rows=2,
                   vertex_labels=True))
    # rays_from_point — compass sets, a numeric-bearing set, angle labels, no north arrow
    cases.append(C("rays_from_point", stem="Rays OA, OB and OC.",
                   rays={"A": "NE", "B": "S", "C": "W"}))
    cases.append(C("rays_from_point", stem="Rays OA, OB, OC and OD.",
                   rays={"A": "N", "B": "E", "C": "S", "D": "W"}))
    cases.append(C("rays_from_point", stem="Five rays from O.",
                   rays={"A": "NE", "B": "SE", "C": "SW", "D": "NW", "E": "E"}))
    cases.append(C("rays_from_point", stem="Bearings 30 and 120 are marked; angle 1 is marked.",
                   rays={"A": 30, "B": 120}, angles=[["A", "B", "1"]]))
    cases.append(C("rays_from_point", stem="Rays OA and OB with angle 1.",
                   rays={"A": "NE", "B": "W"}, angles=[["A", "B", "1"]], north_arrow=False))
    # rectangle_points — lengths, aspect-only, on-points and extra segments
    cases.append(C("rectangle_points", stem="A rectangle 8 cm by 4 cm.",
                   length=8, width=4, on_points={"E": ("DC", 0.5)}, extra_segments=["AE", "BE"]))
    cases.append(C("rectangle_points", stem="A rectangle 6 cm by 3 cm.",
                   length=6, width=3))
    cases.append(C("rectangle_points", stem="A rectangle with a marked point.",
                   aspect=(16, 9), on_points={"E": ("DC", 0.25), "F": ("BC", 0.5)},
                   extra_segments=["AE", "AF"]))
    cases.append(C("rectangle_points", stem="A square with a marked point.", aspect=(1, 1)))
    # house_pentagon — labelled-x and all-numeric variants, plus an impossible geometry refusal
    cases.append(C("house_pentagon",
                   stem="A garden's sides are 8 m, 5 m, 5 m, 6 m and 4 m; one slanting side is "
                        "marked x m. When x = 5, find the perimeter.",
                   AB=8, BC=5, CP=5, PD=6, DA=4, unit="m", labels={"CP": "x m"}))
    cases.append(C("house_pentagon",
                   stem="A garden's five sides are shown.",
                   AB=8, BC=5, CP=5, PD=6, DA=4, unit="m"))
    cases.append(C("house_pentagon",
                   stem="Sides 10 m, 6 m, 6 m, 8 m, 4 m; one slant is x m. When x = 6.",
                   AB=10, BC=6, CP=6, PD=8, DA=4, unit="m", labels={"CP": "x m"}))
    cases.append(C("house_pentagon", stem="Sides 8 m and 5 m.",
                   AB=8, BC=5, DA=5, CP=1, PD=1, unit="m"))   # cannot meet — a stated refusal
    # cuboid — a few triples incl. a cube and a bar
    for L, Wd, H in ((5, 3, 2), (8, 4, 3), (6, 6, 6), (10, 2, 2), (4, 4, 9)):
        cases.append(C("cuboid",
                       stem=f"A cuboid has length {L} cm, width {Wd} cm and height {H} cm.",
                       length=L, width=Wd, height=H))
    return cases


class Sweep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = []              # {kind, kw, extreme, status, detail, built}
        for c in case_grid():
            try:
                b = vt.BUILDERS[c["kind"]](figure_id="sw1", **c["kw"])
            except vt.TemplateError as e:
                cls.results.append({**c, "status": "refused", "detail": str(e), "built": None})
            except Exception as e:
                cls.results.append({**c, "status": "crashed",
                                    "detail": f"{type(e).__name__}: {e}", "built": None})
            else:
                cls.results.append({**c, "status": "built", "detail": "", "built": b})

    def show(self, r):
        args = " ".join(f"{k}={v!r}" for k, v in r["kw"].items() if k != "stem")
        return f"{r['kind']}({args})"

    def test_no_case_crashes_with_a_non_template_error(self):
        for r in self.results:
            with self.subTest(case=self.show(r)):
                self.assertEqual(r["status"] != "crashed", True,
                                 f"{r['kind']} crashed: {r['detail']}")

    def test_every_refusal_states_a_reason(self):
        for r in self.results:
            if r["status"] != "refused":
                continue
            with self.subTest(case=self.show(r)):
                self.assertTrue(r["detail"].strip(), "TemplateError with an empty message")

    def test_no_self_flight_refusal_on_a_moderate_case(self):
        """A template places its own labels clear by construction — a clearance refusal
        ("~N rendered px from …") on a case that isn't deliberately extreme is a template bug."""
        for r in self.results:
            if r["status"] == "refused" and SELF_FLIGHT.search(r["detail"]):
                with self.subTest(case=self.show(r)):
                    self.assertTrue(r["extreme"],
                                    f"{r['kind']} failed its own label pre-flight: {r['detail']}")

    def test_built_cases_audit_clean(self):
        for r in self.results:
            if r["status"] != "built":
                continue
            with self.subTest(case=self.show(r)):
                cs = acs.parse(r["built"].claims)
                _out, fails, _stats = acs.audit(cs)
                self.assertEqual(fails, 0, "claim set must audit clean; first lines: "
                                 + " | ".join(l for l in _out if "FAIL" in l)[:300])

    def test_over_32_elements_carries_a_budget_line(self):
        for r in self.results:
            if r["status"] != "built":
                continue
            n = len(r["built"].doc["elements"])
            with self.subTest(case=self.show(r)):
                if n > 32:
                    self.assertRegex(r["built"].claims, r"(?m)^budget:",
                                     f"{n} elements but no budget: line")

    def test_built_canvases_are_never_tall(self):
        for r in self.results:
            if r["status"] != "built":
                continue
            c = r["built"].doc["canvas"]
            with self.subTest(case=self.show(r)):
                self.assertLessEqual(c["height"], vt.MAX_ASPECT * c["width"],
                                     f"canvas {c['width']}×{c['height']} past the aspect bound")

    def test_number_line_numeral_step_is_nice_when_one_fits(self):
        for r in self.results:
            if r["status"] != "built" or r["kind"] != "number_line":
                continue
            kw, span = r["kw"], r["kw"]["v1"] - r["kw"]["v0"]
            n_units = int(round(span))
            unit_px = min(90.0, 340.0 / span)
            est_span = span * unit_px + 2 * 30.0 + 12          # overhang=30.0 default
            num_gap = vt._clearance_units(4.0, est_span)
            wlab = max(vt._label_width(f"{v:g}", 16)
                       for v in (kw["v0"], kw["v1"], kw["v0"] + 1))
            fits = lambda k: n_units % k == 0 and k * unit_px >= wlab + num_gap   # noqa: E731
            m = STEP_RE.search(r["built"].claims)
            self.assertIsNotNone(m, f"no `tick … step` claim: {self.show(r)}")
            step = int(m.group(1))
            with self.subTest(case=self.show(r)):
                if any(fits(k) for k in vt._NICE_STEPS):
                    self.assertIn(step, vt._NICE_STEPS,
                                  f"step {step} is not nice though a nice divisor fits "
                                  f"(span {n_units})")


if __name__ == "__main__":
    unittest.main()
