"""tests/test_template_sweep.py — W9 item F: a parameter sweep over the figure templates.

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
    # circle_points — in/on/out mixes, stones (unlabelled), a non-capital-name refusal
    cases.append(C("circle_points", stem="A circle with points P, Q and R.",
                   points={"P": {"where": "in"}, "Q": {"where": "on"},
                           "R": {"where": "out"}}))
    cases.append(C("circle_points", stem="A circle with points P, Q, R and S.",
                   points={"P": {"where": "in"}, "Q": {"where": "in"},
                           "R": {"where": "on", "deg": 120},
                           "S": {"where": "on", "deg": 250}}))
    cases.append(C("circle_points", stem="Stones are scattered around a circle.",
                   points={"P": {"where": "out"}, "Q": {"where": "out"},
                           "R": {"where": "in"}}, labelled=False))
    cases.append(C("circle_points", stem="A circle with a dot.",
                   points={"p1": {"where": "in"}}))   # lower-case name — a stated refusal
    # two_circles_points — lens/L-only/R-only/outside/on-outline mixes, refusals
    cases.append(C("two_circles_points", stem="Two overlapping circles with points.",
                   points={"P": {"in": ["L"]}, "Q": {"in": ["L", "R"]},
                           "S": {"in": ["R"]}, "T": {"in": []}}))
    cases.append(C("two_circles_points", stem="Two overlapping circles with points.",
                   points={"P": {"on": "L", "in": ["R"]}, "Q": {"on": "R", "in": []}}))
    cases.append(C("two_circles_points", stem="Two overlapping circles.",
                   overlap=0.7, points={"P": {"in": ["L", "R"]}, "Q": {"in": ["L"]}}))
    cases.append(C("two_circles_points", stem="Two overlapping circles.",
                   points={"P": {"on": "L", "in": ["L"]}}))   # on AND in — a stated refusal
    cases.append(C("two_circles_points", stem="Two circles.",
                   overlap=1.0, points={"P": {"in": ["L"]}}))  # overlap out of (0,1)
    # circles_in_circle — several counts; a zero-total refusal; an overcrowd refusal
    for n_in, n_out in ((5, 4), (8, 0), (0, 6), (3, 9)):
        cases.append(C("circles_in_circle", stem="A big circle with small rings.",
                       n_in=n_in, n_out=n_out))
    cases.append(C("circles_in_circle", stem="A big circle.", n_in=0, n_out=0))
    cases.append(C("circles_in_circle", stem="A big circle with small rings.",
                   n_in=40, n_out=0, extreme=True))   # cannot all fit — stated refusal OK
    # abacus — a few rod sets incl. max beads; a >9-bead refusal; mismatched lengths
    cases.append(C("abacus", stem="The abacus shows a number.",
                   place_values=[1000, 100, 10, 1], beads=[3, 0, 5, 7]))
    cases.append(C("abacus", stem="The abacus shows a number.",
                   place_values=[100, 10, 1], beads=[9, 9, 9]))
    cases.append(C("abacus", stem="The abacus shows a number.",
                   place_values=[10, 1], beads=[0, 0]))
    cases.append(C("abacus", stem="The abacus shows a number.",
                   place_values=[100, 10, 1], beads=[10, 0, 0]))   # 10 beads — refusal
    cases.append(C("abacus", stem="The abacus shows a number.",
                   place_values=[100, 10, 1], beads=[1, 2]))       # length mismatch
    # sorting_rings — 2 and 3 groups; refusals for 1 group, 4 groups, a duplicate item
    cases.append(C("sorting_rings", stem="Sort the cards.",
                   groups=[["Even", ["2", "8", "14"]], ["Odd", ["3", "9"]]]))
    cases.append(C("sorting_rings", stem="Sort the cards.",
                   groups=[["Round", ["ball", "wheel"]],
                           ["Flat", ["mat"]],
                           ["Long", ["pole", "stick", "rail"]]]))
    cases.append(C("sorting_rings", stem="Sort the cards.",
                   groups=[["Only", ["a", "b"]]]))                      # 1 group — refusal
    cases.append(C("sorting_rings", stem="Sort the cards.",
                   groups=[["A", ["1"]], ["B", ["2"]], ["C", ["3"]], ["D", ["4"]]]))
    cases.append(C("sorting_rings", stem="Sort the cards.",
                   groups=[["Even", ["2", "2"]], ["Odd", ["3"]]]))      # dup glyph — refusal
    # shape_row — all seven kinds in one 2-row build; refusals for bad kind/dup letter
    cases.append(C("shape_row", stem="Name each shape.",
                   shapes=[["A", "circle"], ["B", "square"], ["C", "triangle"],
                           ["D", "oval"], ["E", "rectangle"], ["F", "semicircle"],
                           ["G", "small_circle"]]))
    cases.append(C("shape_row", stem="Name each shape.",
                   shapes=[["A", "triangle"], ["B", "circle"], ["C", "square"]]))
    cases.append(C("shape_row", stem="Name each shape.",
                   shapes=[["A", "hexagon"], ["B", "circle"]]))          # bad kind — refusal
    cases.append(C("shape_row", stem="Name each shape.",
                   shapes=[["A", "circle"], ["A", "square"]]))           # dup letter — refusal

    # ── W11: the three G7 templates ──────────────────────────────────────────────
    # coordinate_plane — extents {1,3,5,8,10}² × point sets × join/sym/guides/grid/coords.
    # The letter pockets are half-cells beside each dot; a fine grid on a large plane can
    # leave none of them clear — that refusal is legitimate only past the demonstrated
    # 6x5 region (small cells, many ruling lines), so those cases are flagged extreme.
    def plane_stem(pts):
        if not pts:
            return "A coordinate plane. (a) Describe it."
        return ("Points " + ", ".join(f"{n}({x}, {y})" for n, (x, y) in pts.items()) +
                " are marked on a coordinate plane. (a) Read their coordinates.")
    for xm in (1, 3, 5, 8, 10):
        for ym in (1, 3, 5, 8, 10):
            inside = [(x, y) for x in range(xm + 1) for y in range(ym + 1)
                      if (x, y) not in ((0, 0), (xm, 0), (0, ym))]
            # `inside` already holds the legal on-axis sits (x,0)/(0,y) plus the far
            # corner (xm,ym) — the three excluded cells are the axis anchors
            pool = inside
            p1 = {"A": (xm, ym)}                       # the far corner is always legal
            p4 = dict(zip("ABCD", pool[::max(1, len(pool) // 4)][:4]))
            p8 = dict(zip("ABCDEFGH", pool[::max(1, len(pool) // 8)][:8]))
            tight = min(52.0, 430.0 / xm, 300.0 / ym) < 45
            cases.append(C("coordinate_plane", stem=plane_stem({}), points={},
                           x_max=xm, y_max=ym, grid=True, coords="figure"))
            cases.append(C("coordinate_plane", stem=plane_stem(p1), points=p1,
                           x_max=xm, y_max=ym, grid=False, coords="stem",
                           origin_label=True))
            ex = tight and bool(p4)
            kw4 = dict(points=p4, x_max=xm, y_max=ym, grid=True, coords="stem",
                       sym_axis={"x": xm / 2} if (xm + ym) % 2 == 0 else {"y": ym / 2})
            if len(p4) >= 2:
                kw4["join"] = [list(p4)[:3]]
            cases.append(C("coordinate_plane", stem=plane_stem(p4), extreme=ex, **kw4))
            ex8 = tight and bool(p8)
            kw8 = dict(points=p8, x_max=xm, y_max=ym, grid=False, coords="figure")
            if p8:
                kw8["guides"] = [next(iter(p8))]
            cases.append(C("coordinate_plane",
                           stem="Several points are marked. (a) Read them.",
                           extreme=ex8, **kw8))
    for xy in ((0, 0), (5, 0), (0, 5)):                # the shared axis anchors refuse
        cases.append(C("coordinate_plane", stem=plane_stem({}), x_max=5, y_max=5,
                       points={"A": xy}, coords="figure"))

    # parallel_lines — 2/3/4 lines × class layouts × direction × crossing × distance.
    # dir=20 + crossing + distance packs an endpoint letter against the crossing and the
    # MN segment at the smallest stack gap — the two densest cells legitimately refuse.
    pl_stem = ("Some of the lines are parallel; the perpendicular distance between the "
               "parallel lines is 3 cm. (a) Name the parallel lines.")
    for lines, par in (
            (["AB", "CD"], [["AB", "CD"]]),
            (["AB", "CD", "EF"], [["AB", "CD"]]),
            (["AB", "CD", "EF"], [["AB", "CD", "EF"]]),
            (["AB", "CD", "EF", "GH"], [["AB", "CD"]]),
            (["AB", "CD", "EF", "GH"], [["AB", "CD"], ["EF", "GH"]])):
        for d in (0, 20, -30, 90):
            for cross in (None, "PQ"):
                for dist in (None, {"between": ["AB", "CD"], "value": 3, "unit": "cm"}):
                    cases.append(C("parallel_lines", stem=pl_stem, lines=lines,
                                   parallel=par, direction=d, crossing=cross,
                                   distance=dist,
                                   extreme=bool(d == 20 and cross and dist)))

    # bar_chart — categories 2..8 x 1..3 series x steps {1,2,5,10,1000} x values modes;
    # a 0-value bar and year categories; then the stated refusals.
    for i, nc in enumerate(range(2, 9)):
        n_ser = 1 + i % 3
        step = (1, 2, 5, 10, 1000)[i % 5]
        vals = [[step * ((k * (j + 1)) % 7 + 1) for k in range(nc)]   # ≤ 7·step → ≤7 axis steps
                for j in range(n_ser)]
        if i % 4 == 0:
            vals[0][1] = 0                              # a 0 bar still reads
        mode = "stem" if i % 2 == 0 else "figure"
        cats = [f"Grp {k + 1}" for k in range(nc)]
        if i == 5:
            cats = [str(2015 + k) for k in range(nc)]     # years are not scale numerals
        series = [{"name": f"S{j + 1}" if n_ser > 1 else "", "values": v}
                  for j, v in enumerate(vals)]
        nums = [step] + [v for vs in vals for v in vs]
        stem = ("The chart shows " + ", ".join(f"{v:g}" for v in sorted(set(nums))) +
                ", the axis in steps of " + f"{step:g}. (a) Read the bars.")
        cases.append(C("bar_chart", stem=stem, categories=cats, series=series,
                       step=step, values=mode))
    cases.append(C("bar_chart", stem="x", categories=[f"C{i}" for i in range(9)],
                   series=[{"name": "", "values": [1] * 9}], step=1))        # 9 cats
    cases.append(C("bar_chart", stem="x",
                   categories=["A", "B"],
                   series=[{"name": f"S{j}", "values": [1, 2]} for j in range(4)],
                   step=1))                                                  # 4 series
    cases.append(C("bar_chart", stem="The chart shows 7, in steps of 4. (a) Read.",
                   categories=["A", "B"],
                   series=[{"name": "", "values": [7, 4]}], step=4))         # 7 not on the lattice
    cases.append(C("bar_chart", stem="The chart shows 12, in steps of 2. (a) Read.",
                   categories=["A", "B"],
                   series=[{"name": "", "values": [12, 4]}], step=2, v_max=10))  # over v_max
    cases.append(C("bar_chart", stem="The chart shows 5, in steps of 1. (a) Read.",
                   categories=["A", "B"],
                   series=[{"name": "", "values": [5, 3]}], step=1, v_max=13))   # 13 steps
    # W11 review — a `$`/backtick/`|` in any user label must be a stated refusal,
    # never vc.text's AssertionError
    cases.append(C("bar_chart", stem="The chart shows 5, in steps of 1. (a) Read.",
                   categories=["$x$", "B"],
                   series=[{"name": "", "values": [5, 3]}], step=1))
    cases.append(C("parallel_lines", stem=pl_stem, lines=["AB", "CD"],
                   parallel=[["AB", "CD"]],
                   distance={"between": ["AB", "CD"], "value": 3, "unit": "c$m"}))
    # symmetry_grid (W13) — 4 axis kinds × 2 shapes × half/full × labels × cell sizes
    sg_stem = "Half of a shape is drawn on a grid of 1 cm squares. (a) Complete it."
    sg = [
        ({"through": [[4, 0], [4, 5]]}, [[4, 0], [1, 1], [1, 4], [3, 5], [4, 5]]),
        ({"through": [[3, 0], [3, 4]]}, [[3, 0], [1, 0], [1, 4], [3, 4]]),
        ({"through": [[0, 3], [6, 3]]}, [[0, 3], [1, 1], [4, 1], [5, 3]]),
        ({"through": [[0, 2], [5, 2]]}, [[1, 2], [1, 0], [4, 0], [4, 2]]),
        ({"through": [[0, 0], [4, 4]]}, [[0, 0], [4, 1], [4, 4]]),
        ({"through": [[0, 0], [5, 5]]}, [[1, 1], [3, 0], [5, 2], [4, 4]]),
        ({"through": [[0, 6], [6, 0]]}, [[1, 5], [1, 1], [5, 1]]),
        ({"through": [[0, 5], [5, 0]]}, [[0, 5], [0, 2], [2, 0], [5, 0]]),
    ]
    for ax, half in sg:
        for show in ("half", "full"):
            for vl in (False, True):
                for cp in (30.0, 45.0):
                    cases.append(C("symmetry_grid", stem=sg_stem, cell=1, half=half,
                                   axis=ax, show=show, vertex_labels=vl, cell_px=cp))
    # labelled_composite (W13) — L/T/U/step/plus outlines × unknown variants × letters
    lc_stem = "A composite floor plan with sides 3 m and 6 m. (a) Find the area."
    lc = [
        [["R", 8], ["U", 3], ["L", 3], ["U", 2], ["L", 5], ["D", 5]],
        [["R", 2], ["U", 4], ["R", 2], ["U", 2], ["L", 6], ["D", 2], ["R", 2], ["D", 4]],
        [["R", 9], ["U", 6], ["L", 3], ["D", 3], ["L", 3], ["U", 3], ["L", 3], ["D", 6]],
        [["R", 6], ["U", 2], ["L", 2], ["U", 2], ["L", 2], ["U", 2], ["L", 2], ["D", 6]],
        [["R", 2], ["U", 2], ["R", 2], ["U", 2], ["L", 2], ["U", 2], ["L", 2], ["D", 2],
         ["L", 2], ["D", 2], ["R", 2], ["D", 2]],
        [["R", 12], ["U", 5], ["L", 4], ["U", 3], ["L", 8], ["D", 8]],
    ]
    for p in lc:
        for variant in ("all", "x", "null", "both"):
            q = [list(s) for s in p]
            if variant in ("x", "both"):
                q[1] = q[1][:2] + ["x m"]
            if variant in ("null", "both"):
                q[2] = q[2][:2] + [None]
            for vl in (False, True):
                cases.append(C("labelled_composite", stem=lc_stem, path=q, unit="m",
                               vertex_labels=vl))
    # triangle_marks (W13) — triangle classes × mark sets × labels
    tm_stem = "Two angles are 30°, 40°, 45°, 50°, 60° or 70°. Find x."
    tri = [
        ({"A": 60, "B": 60, "C": 60}, {"AB": 1, "BC": 1, "CA": 1}, {"A": 1, "B": 1, "C": 1}, None),
        ({"A": 70, "B": 70, "C": 40}, {"CA": 1, "BC": 1}, {"A": 1, "B": 1, "C": 2}, None),
        ({"A": 40, "B": 40, "C": 100}, {"CA": 2, "BC": 2}, {"A": 1, "B": 1, "C": 2}, None),
        ({"A": 45, "B": 45, "C": 90}, {"CA": 1, "BC": 1}, {"A": 1, "B": 1}, "C"),
        ({"A": 30, "B": 60, "C": 90}, {}, {"A": 1, "B": 2}, "C"),
        ({"A": 90, "B": 50, "C": 40}, {}, {"B": 1, "C": 2}, "A"),
        ({"A": 50, "B": 60, "C": 70}, {"AB": 1, "BC": 2, "CA": 3}, {"A": 1, "B": 2, "C": 3}, None),
        ({"A": 30, "B": 40, "C": 110}, {}, {"A": 1, "B": 2, "C": 3}, None),
    ]
    for angles_, ticks_, arcs_, right_ in tri:
        for lab in ("none", "letter", "numeric"):
            labels = {}
            arced = list(arcs_)
            if lab == "letter" and arced:
                labels = {arced[-1]: "x"}
            if lab == "numeric" and len(arced) >= 2:
                labels = {}
                for v in arced[:-1]:          # an equal angle's size prints once
                    if f"{angles_[v]:g}°" not in labels.values():
                        labels[v] = f"{angles_[v]:g}°"
                labels[arced[-1]] = "x"
            cases.append(C("triangle_marks", stem=tm_stem, angles=angles_, ticks=ticks_,
                           arcs=arcs_, right=right_, angle_labels=labels))
    # venn_sets (W14) — 2/3 sets × items/counts × universal on/off
    vs_stem = "The Venn diagram shows the sets. (a) List the elements of each set."
    for n_ in (2, 3):
        sets_ = ["A", "B", "C"][:n_]
        keys = ["A", "AB", "B"] if n_ == 2 else ["A", "B", "C", "AB", "AC", "BC", "ABC"]
        for uni in ("U", None):
            ks = keys + ([""] if uni else [])
            counts = {k: i + 2 for i, k in enumerate(ks)}
            cases.append(C("venn_sets", stem=vs_stem, sets=sets_, regions=counts, universal=uni))
            cases.append(C("venn_sets", stem=vs_stem, sets=sets_, universal=uni,
                           regions={**counts, keys[1]: "x"}))
            for per in (1, 2, 3):
                items, c_ = {}, 0
                for k in ks:
                    items[k] = [str(10 + c_ + j) for j in range(per)]
                    c_ += per
                cases.append(C("venn_sets", stem=vs_stem, sets=sets_, regions=items,
                               universal=uni))
            cases.append(C("venn_sets", stem=vs_stem, sets=sets_, universal=uni,
                           regions={"A": ["red", "blue"], keys[1]: ["green"]}))
            cases.append(C("venn_sets", stem=vs_stem, sets=sets_, universal=uni,
                           regions={keys[-1]: ["Ravi", "Nimal"], "B": ["Kamal"]}))
    # circle_parts (W14) — feature combinations × point angles × labels
    cp_stem = "The circle has centre O, radius 4 cm and diameter 8 cm. Name its parts."
    rot = (0, 37, 90, 145)
    combos = [
        ({"A": 0, "B": 180}, [{"diameter": "AB"}]),
        ({"A": 0, "B": 180}, [{"diameter": "AB", "label": "diameter"}]),
        ({"A": 0, "B": 180}, [{"diameter": "AB", "label": "8 cm"}]),
        ({"A": 30}, [{"radius": "OA", "label": "4 cm"}]),
        ({"A": 30}, [{"radius": "OA", "label": "radius"}]),
        ({"C": 200, "D": 300}, [{"chord": "CD", "label": "chord"}]),
        ({"C": 200, "D": 300}, [{"chord": "CD"}, {"segment": "CD"}]),
        ({"C": 200, "D": 300}, [{"chord": "CD"}, {"segment": "CD", "major": True}]),
        ({"C": 200, "D": 300}, [{"arc": "CD", "label": "arc"}]),
        ({"C": 200, "D": 300}, [{"arc": "CD", "major": True, "label": "arc"}]),
        ({"A": 10, "B": 80}, [{"sector": "OAB", "label": "sector"}]),
        ({"A": 10, "B": 80}, [{"sector": "OAB", "major": True}]),
        ({"A": 180, "B": 0, "C": 60, "D": 120, "E": 270},
         [{"radius": "OE", "label": "4 cm"}, {"diameter": "AB"},
          {"chord": "CD", "label": "chord"}, {"segment": "CD"}]),
        ({"A": 180, "B": 0, "E": 270, "F": 45},
         [{"diameter": "AB", "label": "diameter"}, {"radius": "OE", "label": "radius"},
          {"arc": "BF", "label": "arc"}]),
    ]
    for pts, feats in combos:
        for d0 in rot:
            p2 = {k: (v + d0) % 360 for k, v in pts.items()}
            for centre_ in ("O", None):
                cases.append(C("circle_parts", stem=cp_stem, points=p2, features=feats,
                               centre=centre_, radius=4))
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
