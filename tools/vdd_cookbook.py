#!/usr/bin/env python3
"""S6b's COOKBOOK — tested generators for the primitive combinations a maths figure keeps needing.

    from vdd_cookbook import *            # in a small draw script beside the claim set
    A, B, C = (60, 40), (60, 220), (240, 220)
    els  = polygon_sides({"A": A, "B": B, "C": C}, "ABC")            # the three sides as lines
    els += right_angle_mask(B, A, C, size=16)                        # opaque white square (T-S6b-3)
    els += angle_label(A, B, C, r=28, label="58°")                   # arc + label on the bisector
    els += vertex_labels({"A": A, "B": B, "C": C}, {"A": (-16, -4), "B": (-16, 12), "C": (10, 12)})
    write_figure("q7.json", doc(300, 260, els, title="…", description="…"), anchors={"A": A, "B": B, "C": C})

then  node …/vdd-check.mjs q7.json --claims q7-claims.txt      (the anchors sidecar is picked up automatically)

Every recipe returns a LIST of VDD elements (array order = paint order — masks go after the strokes
they hide). Points are (x, y) tuples in canvas units, y down, degrees clockwise from +x (the VDD
convention). Nothing here validates: run vdd-check.mjs on the output, every time (S6b §4).

Why these shapes, and not others (each is a measured lesson, see S6b §3.2 and TRAPS):
  • a FILLED curved region is a ≤ 2°-sampled `polygon` (stroke 0) under an `arc` rim — `arc` cannot
    fill and `path` was second-class on the reviewer's card (T-S6b-9)
  • a RIGHT-ANGLE MARK that a ray crosses is an opaque white `polygon` square after the lines — the
    `angleMark variant:"right"` is `fill:"none"` and shows the ray through it (T-S6b-3)
  • a NUMBER LINE has no primitive: axis (line/arrow) + one short `line` per tick + one `text` per
    numeral; open/closed endpoints are `circle`s whose FILL carries the meaning (T104)
  • a GRID is r×c `rect`s; shading is a `fill` on exactly the shaded cells
  • vertex labels are `point` elements with `r: 0` (label, no dot) so the label stays bound to its point
  • `angleMark` labels (both variants) render correctly since 2026-08-28 — measured 2026-09-05 in the
    harness — so `angle_label` uses the mark's own `label`; `text` is no longer needed for that (T98 fixed)

`python3 vdd_cookbook.py --demo <dir>` writes one figure per recipe (+ anchors) for vdd-check's
render; `--self-test` asserts the geometry of each recipe (a sampled semicircle's vertices all lie on
the circle, a number line's ticks land on the lattice, a mask's corner is at the vertex…).
"""
from __future__ import annotations
import json, math, os, sys
from typing import Iterable, Sequence

XY = tuple[float, float]
INK = "#1f2937"
SHADE = "#e5e7eb"      # the live convention for a shaded region (S6b §3.2)
WHITE = "#ffffff"

_ids: dict[str, int] = {}
def _id(prefix: str) -> str:
    _ids[prefix] = _ids.get(prefix, 0) + 1
    return f"{prefix}{_ids[prefix]}"
def reset_ids() -> None:
    _ids.clear()

def r2(v: float) -> float:
    return round(v + 0.0, 2)
def P(p: Sequence[float]) -> list[float]:
    return [r2(p[0]), r2(p[1])]
def polar(c: XY, r: float, deg: float) -> XY:
    a = math.radians(deg)
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
def angle_of(p: XY, origin: XY) -> float:
    return math.degrees(math.atan2(p[1] - origin[1], p[0] - origin[0]))
def dist(a: XY, b: XY) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])
def lerp(a: XY, b: XY, t: float) -> XY:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
def unit(a: XY, b: XY) -> XY:
    d = dist(a, b)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
def normal(a: XY, b: XY) -> XY:
    ux, uy = unit(a, b)
    return (-uy, ux)          # left-hand normal (screen coordinates: rotates the direction 90° anticlockwise on screen)

# ── document ──────────────────────────────────────────────────────────────────────────────────────
def doc(width: float, height: float, elements: list[dict], *, title: str, description: str, font_size: float = 18, stroke_width: float = 2) -> dict:
    return {
        "schema": "vibhaga.diagram", "schemaVersion": 1,
        "canvas": {"width": width, "height": height, "background": "transparent"},
        "defaults": {"strokeColor": INK, "strokeWidth": stroke_width, "fontSize": font_size},
        "a11y": {"title": title, "description": description},
        "elements": elements,
    }

def write_figure(path: str, document: dict, anchors: dict[str, XY] | None = None) -> None:
    with open(path, "w") as f:
        json.dump(document, f, indent=1, ensure_ascii=False)
    if anchors:
        with open(path[:-5] + ".anchors.json" if path.endswith(".json") else path + ".anchors.json", "w") as f:
            json.dump({k: P(v) for k, v in anchors.items()}, f)

# ── primitives ────────────────────────────────────────────────────────────────────────────────────
def line(a: XY, b: XY, *, dashed: bool = False, width: float | None = None, id: str | None = None) -> dict:
    el = {"id": id or _id("l"), "type": "line", "points": [P(a), P(b)]}
    st = {}
    if dashed: st["style"] = "dashed"
    if width is not None: st["width"] = width
    if st: el["stroke"] = st
    return el

def polyline(pts: Sequence[XY], *, id: str | None = None, dashed: bool = False) -> dict:
    el = {"id": id or _id("pl"), "type": "polyline", "points": [P(p) for p in pts]}
    if dashed: el["stroke"] = {"style": "dashed"}
    return el

def polygon(pts: Sequence[XY], *, fill: str | None = None, stroke_width: float | None = None, id: str | None = None) -> dict:
    el = {"id": id or _id("pg"), "type": "polygon", "points": [P(p) for p in pts]}
    if fill: el["fill"] = {"color": fill}
    if stroke_width is not None: el["stroke"] = {"width": stroke_width}
    return el

def circle(c: XY, r: float, *, fill: str | None = None, id: str | None = None, width: float | None = None) -> dict:
    el = {"id": id or _id("c"), "type": "circle", "center": P(c), "r": r2(r)}
    if fill: el["fill"] = {"color": fill}
    if width is not None: el["stroke"] = {"width": width}
    return el

def arc(c: XY, r: float, start: float, end: float, *, id: str | None = None, dashed: bool = False) -> dict:
    el = {"id": id or _id("a"), "type": "arc", "center": P(c), "r": r2(r), "start": r2(start), "end": r2(end)}
    if dashed: el["stroke"] = {"style": "dashed"}
    return el

def text(at: XY, value: str, *, align: str = "middle", baseline: str = "middle", size: float | None = None, id: str | None = None) -> dict:
    assert "$" not in value and "`" not in value, "no $ or backtick in a VDD label (S6b §0.6)"
    el = {"id": id or _id("t"), "type": "text", "at": P(at), "value": value, "align": align, "baseline": baseline}
    if size: el["fontSize"] = size
    return el

def math_label(at: XY, latex: str, *, align: str = "middle", baseline: str = "middle", id: str | None = None) -> dict:
    return {"id": id or _id("m"), "type": "math", "at": P(at), "latex": latex, "align": align, "baseline": baseline}

def dot(at: XY, r: float = 3, *, label: str | None = None, offset: XY = (8, -8), id: str | None = None) -> dict:
    el = {"id": id or _id("d"), "type": "point", "at": P(at), "r": r}
    if label: el.update({"label": label, "labelOffset": P(offset)})
    return el

def arrow(a: XY, b: XY, *, head: str = "end", width: float | None = None, id: str | None = None) -> dict:
    el = {"id": id or _id("ar"), "type": "arrow", "points": [P(a), P(b)], "head": head}
    if width is not None: el["stroke"] = {"width": width}
    return el

# ── recipes ───────────────────────────────────────────────────────────────────────────────────────
def vertex_labels(pts: dict[str, XY], offsets: dict[str, XY] | None = None, default: XY = (8, -8)) -> list[dict]:
    """One label-only `point` (r 0) per named vertex — the label stays bound to the point (S6b §3.2)."""
    offsets = offsets or {}
    return [{"id": f"lbl{k}", "type": "point", "at": P(v), "r": 0, "label": k, "labelOffset": P(offsets.get(k, default))} for k, v in pts.items()]

def polygon_sides(pts: dict[str, XY], order: str, *, closed: bool = True, dashed: Iterable[str] = ()) -> list[dict]:
    """The sides of a named polygon as separate `line`s (one per printed stroke, so S6b §5.2 can count them).
    `order` is the vertex sequence, e.g. "ABC"; a side named in `dashed` (e.g. "AC") is drawn dashed."""
    dashed = {"".join(sorted(s)) for s in dashed}
    names = list(order) + ([order[0]] if closed else [])
    out = []
    for a, b in zip(names, names[1:]):
        out.append(line(pts[a], pts[b], dashed="".join(sorted(a + b)) in dashed, id=f"{a}{b}"))
    return out

def right_angle_mask(vertex: XY, toward_a: XY, toward_b: XY, size: float = 14) -> list[dict]:
    """An OPAQUE right-angle square at `vertex` (white fill, default stroke) — put it AFTER the lines it
    must mask (T-S6b-3: `angleMark variant:"right"` is transparent and a ray inside shows through)."""
    ua, ub = unit(vertex, toward_a), unit(vertex, toward_b)
    p1 = (vertex[0] + ua[0] * size, vertex[1] + ua[1] * size)
    p3 = (vertex[0] + ub[0] * size, vertex[1] + ub[1] * size)
    p2 = (p1[0] + ub[0] * size, p1[1] + ub[1] * size)
    return [polygon([vertex, p1, p2, p3], fill=WHITE, id=_id("rt"))]

def right_angle_mark(vertex: XY, toward_a: XY, toward_b: XY, r: float = 14) -> list[dict]:
    """The transparent `angleMark variant:"right"` — fine when NO ray crosses the marked angle."""
    return [{"id": _id("rt"), "type": "angleMark", "vertex": P(vertex), "from": P(toward_a), "to": P(toward_b), "r": r, "variant": "right"}]

def angle_label(vertex: XY, toward_a: XY, toward_b: XY, *, r: float = 26, label: str | None = None, arcs: int = 1, reflex: bool = False) -> list[dict]:
    """An angle arc at `vertex` between the rays to a and b, with its label on the drawn arc's bisector.
    The renderer places the label (bisectorDeg, label-aware distance) — verified 2026-09-05, T98 fixed."""
    el = {"id": _id("ang"), "type": "angleMark", "vertex": P(vertex), "from": P(toward_a), "to": P(toward_b), "r": r}
    if label: el["label"] = label
    if arcs > 1: el["arcs"] = arcs
    if reflex: el["reflex"] = True
    return [el]

def tick_marks(a: XY, b: XY, count: int = 1, *, at: float = 0.5, size: float = 8) -> list[dict]:
    return [{"id": _id("tk"), "type": "tickMark", "on": [P(a), P(b)], "count": count, "at": at, "size": size}]

def parallel_marks(a: XY, b: XY, count: int = 1, *, at: float = 0.5, size: float = 8) -> list[dict]:
    """The arrowhead-style parallel mark on segment a→b (direction matters: the chevron points a→b)."""
    return [{"id": _id("pm"), "type": "parallelMark", "on": [P(a), P(b)], "count": count, "at": at, "size": size}]

def sampled_arc(c: XY, r: float, start: float, end: float, step: float = 2.0) -> list[XY]:
    """Points along the arc from `start` to `end` degrees (clockwise-positive on screen), every ≤ `step`°.
    Chord error at 2° is r·(1−cos 1°) ≈ 0.00015 r — invisible under a 2 px rim."""
    if end < start: end += 360
    n = max(1, math.ceil((end - start) / step))
    return [polar(c, r, start + (end - start) * i / n) for i in range(n + 1)]

def filled_sector(c: XY, r: float, start: float, end: float, *, fill: str = SHADE, rim: bool = True, radii: bool = True) -> list[dict]:
    """A filled sector: polygon (centre + sampled arc, stroke 0) under an `arc` rim + the two radii.
    A SEMICIRCLE is filled_sector(c, r, 90, 270) — the diameter is then radii=True's two collinear lines;
    pass radii=False and draw the diameter yourself as one `line` if the claim set has it as one stroke."""
    pts = [c] + sampled_arc(c, r, start, end)
    out = [polygon(pts, fill=fill, stroke_width=0, id=_id("sec"))]
    if rim: out.append(arc(c, r, start, end, id=_id("rim")))
    if radii:
        out.append(line(c, polar(c, r, start), id=_id("rad")))
        out.append(line(c, polar(c, r, end), id=_id("rad")))
    return out

def filled_segment(c: XY, r: float, start: float, end: float, *, fill: str = SHADE, chord: bool = True, rim: bool = True) -> list[dict]:
    """The region between an arc and its chord (a circular segment), shaded."""
    pts = sampled_arc(c, r, start, end)
    out = [polygon(pts, fill=fill, stroke_width=0, id=_id("seg"))]
    if rim: out.append(arc(c, r, start, end, id=_id("rim")))
    if chord: out.append(line(pts[0], pts[-1], id=_id("chord")))
    return out

def filled_polygon(pts: Sequence[XY], *, fill: str = SHADE, outline: bool = True) -> list[dict]:
    """A shaded straight-edged region: the fill (stroke 0) and, optionally, its outline as one polygon."""
    out = [polygon(pts, fill=fill, stroke_width=0, id=_id("sh"))]
    if outline: out.append(polygon(pts, id=_id("out")))
    return out

def grid(origin: XY, cols: int, rows: int, cell: float | XY, *, shaded: Iterable[tuple[int, int]] = (), fill: str = SHADE) -> list[dict]:
    """r×c `rect`s (no grid primitive exists); `shaded` lists (col, row) cells (0-based) that get the fill."""
    cw, ch = (cell, cell) if isinstance(cell, (int, float)) else cell
    shaded = set(shaded)
    out = []
    for r in range(rows):
        for c in range(cols):
            el = {"id": f"cell{c}{r}", "type": "rect", "x": r2(origin[0] + c * cw), "y": r2(origin[1] + r * ch), "width": r2(cw), "height": r2(ch)}
            if (c, r) in shaded: el["fill"] = {"color": fill}
            out.append(el)
    return out

def number_line(x0: float, x1: float, y: float, v0: float, v1: float, *, step: float = 1, tick: float = 6, label_every: int = 1,
                arrows: bool = True, overhang: float = 14, closed: Iterable[float] = (), open: Iterable[float] = (), dot_r: float = 5,
                heavy: tuple[float, float] | None = None, heavy_width: float = 4, label_dy: float = 18, fmt=lambda v: f"{v:g}") -> tuple[list[dict], dict[float, XY]]:
    """A numbered scale from value v0 (at x0) to v1 (at x1) on the horizontal y. Returns (elements, {value: (x,y)}).
    `closed`/`open` values get a filled / hollow circle; `heavy` = (a, b) draws the marked interval heavier.
    An unbounded heavy end is `heavy=(a, math.inf)` — it runs to the axis's drawn end (S6a §3.2 `interval`)."""
    span = (x1 - x0) / (v1 - v0)
    at = lambda v: (x0 + (v - v0) * span, y)
    out = []
    a, b = (x0 - overhang, y), (x1 + overhang, y)
    out.append(arrow(a, b, head="both", id="axis") if arrows else line(a, b, id="axis"))
    positions: dict[float, XY] = {}
    n = int(round((v1 - v0) / step))
    for i in range(n + 1):
        v = v0 + i * step
        x, _ = at(v)
        positions[v] = (x, y)
        out.append(line((x, y - tick), (x, y + tick), id=f"tick{i}", width=1.5))
        if i % label_every == 0:
            out.append(text((x, y + label_dy), fmt(v), id=f"num{i}"))
    if heavy:
        ha, hb = heavy
        pa = at(ha) if math.isfinite(ha) else a
        pb = at(hb) if math.isfinite(hb) else b
        if not math.isfinite(hb) or not math.isfinite(ha):
            out.append(arrow(pa, pb, head=("both" if not (math.isfinite(ha) or math.isfinite(hb)) else "end"), width=heavy_width, id="heavy"))
        else:
            out.append(line(pa, pb, width=heavy_width, id="heavy"))
    for v in closed:
        out.append(circle(at(v), dot_r, fill=INK, id=f"closed{fmt(v)}"))
    for v in open:
        out.append(circle(at(v), dot_r, fill=WHITE, id=f"open{fmt(v)}"))
    return out, positions

def dimension(a: XY, b: XY, label: str, *, offset: float = 16, inset: float = 0, label_gap: float = 14, side: int = 1) -> list[dict]:
    """A double-headed dimension arrow parallel to a→b, `offset` px to the side (side=±1), labelled beyond it."""
    nx, ny = normal(a, b)
    nx, ny = nx * side, ny * side
    ux, uy = unit(a, b)
    pa = (a[0] + nx * offset + ux * inset, a[1] + ny * offset + uy * inset)
    pb = (b[0] + nx * offset - ux * inset, b[1] + ny * offset - uy * inset)
    mid = ((pa[0] + pb[0]) / 2 + nx * label_gap, (pa[1] + pb[1]) / 2 + ny * label_gap)
    return [arrow(pa, pb, head="both", width=1.5, id=_id("dim")), text(mid, label, id=_id("dimlbl"))]

def side_label(a: XY, b: XY, label: str, *, gap: float = 14, side: int = 1, t: float = 0.5) -> list[dict]:
    """A label beside segment a→b at fraction t, `gap` px off to the side (side=±1)."""
    nx, ny = normal(a, b)
    m = lerp(a, b, t)
    return [text((m[0] + nx * gap * side, m[1] + ny * gap * side), label, id=_id("sl"))]

def venn(rect: tuple[float, float, float, float], ca: XY, cb: XY, r: float, *, labels: dict[str, XY] | None = None, universal: str = "ε") -> list[dict]:
    """A two-set Venn diagram: the universal rectangle, two circles, the set names and the universal-set letter.
    `labels` = {"A": (x,y), "B": (x,y)} for the set names; put the ELEMENT letters with `text` yourself."""
    x, y, w, h = rect
    out = [{"id": "univ", "type": "rect", "x": r2(x), "y": r2(y), "width": r2(w), "height": r2(h)}, circle(ca, r, id="setA"), circle(cb, r, id="setB")]
    out.append(text((x + w - 12, y + 14), universal, id="eps"))
    for k, at in (labels or {}).items():
        out.append(text(at, k, id=f"name{k}"))
    return out

def pie(c: XY, r: float, sectors: Sequence[tuple[float, str | None, bool]], *, start: float = -90) -> list[dict]:
    """A pie chart: sectors as (sweep_degrees, label or None, shaded?) clockwise from `start`."""
    out = [circle(c, r, id="pie")]
    a = start
    for i, (sweep, label, shaded) in enumerate(sectors):
        if shaded:
            out.insert(0, polygon([c] + sampled_arc(c, r, a, a + sweep), fill=SHADE, stroke_width=0, id=f"shade{i}"))
        out.append(line(c, polar(c, r, a), id=f"cut{i}"))
        if label:
            out.append(text(polar(c, r * 0.6, a + sweep / 2), label, id=f"plbl{i}"))
        a += sweep
    return out

def compass_rose(c: XY, arm: float = 60, *, labels: bool = True, gap: float = 14) -> list[dict]:
    """A N/E/S/W cross at c (arrowhead on N), labelled."""
    out = [arrow((c[0], c[1] + arm), (c[0], c[1] - arm), head="end", id="ns"), line((c[0] - arm, c[1]), (c[0] + arm, c[1]), id="ew")]
    if labels:
        out += [text((c[0], c[1] - arm - gap), "N", id="N"), text((c[0], c[1] + arm + gap), "S", id="S"),
                text((c[0] + arm + gap, c[1]), "E", id="E"), text((c[0] - arm - gap, c[1]), "W", id="W")]
    return out

def axes(origin: XY, x_len: float, y_len: float, *, x_label: str | None = None, y_label: str | None = None,
         x_ticks: Sequence[tuple[float, str]] = (), y_ticks: Sequence[tuple[float, str]] = (), tick: float = 5) -> list[dict]:
    """Two arrowed axes from `origin` (x right, y up on screen), with (position_px, label) ticks."""
    ox, oy = origin
    out = [arrow((ox, oy), (ox + x_len, oy), id="xaxis"), arrow((ox, oy), (ox, oy - y_len), id="yaxis")]
    if x_label: out.append(text((ox + x_len, oy + 38), x_label, align="end", id="xlbl"))   # a second row: the first is the numerals (measured collision with the last tick)
    if y_label: out.append(text((ox - 8, oy - y_len - 10), y_label, align="start", id="ylbl"))
    for i, (px, lab) in enumerate(x_ticks):
        out += [line((ox + px, oy - tick), (ox + px, oy + tick), width=1.5, id=f"xt{i}"), text((ox + px, oy + 18), lab, id=f"xn{i}")]
    for i, (py, lab) in enumerate(y_ticks):
        out += [line((ox - tick, oy - py), (ox + tick, oy - py), width=1.5, id=f"yt{i}"), text((ox - 10, oy - py), lab, align="end", id=f"yn{i}")]
    return out

# ── geometry solvers for constructing anchors from claims (S6b §3.1) ──────────────────────────────
def point_at_angle(vertex: XY, along: XY, deg: float, length: float) -> XY:
    """The point `length` from `vertex`, `deg` degrees (screen-clockwise) from the ray vertex→along."""
    return polar(vertex, length, angle_of(along, vertex) + deg)

def triangle_from_angles(A: XY, B: XY, angle_A: float, angle_B: float, *, c_side: int = -1) -> XY:
    """The third vertex C of triangle ABC given base AB and the interior angles at A and B.
    c_side=-1 puts C above the base on screen (smaller y) when A is left of B."""
    ab = dist(A, B)
    angle_C = 180 - angle_A - angle_B
    ac = ab * math.sin(math.radians(angle_B)) / math.sin(math.radians(angle_C))
    base = angle_of(B, A)
    return polar(A, ac, base + c_side * angle_A)

def foot_of_perpendicular(p: XY, a: XY, b: XY) -> XY:
    ux, uy = unit(a, b)
    t = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
    return (a[0] + ux * t, a[1] + uy * t)

def intersect(p1: XY, p2: XY, p3: XY, p4: XY) -> XY:
    d = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
    t = ((p1[0] - p3[0]) * (p3[1] - p4[1]) - (p1[1] - p3[1]) * (p3[0] - p4[0])) / d
    return lerp(p1, p2, t)

# ── demo + self-test ──────────────────────────────────────────────────────────────────────────────
def _demos() -> dict[str, tuple[dict, dict[str, XY]]]:
    reset_ids()
    out = {}
    A, B, C = (60.0, 40.0), (60.0, 220.0), (240.0, 220.0)
    els = polygon_sides({"A": A, "B": B, "C": C}, "ABC") + right_angle_mask(B, A, C, 16) + angle_label(A, B, C, r=28, label="58°") \
        + angle_label(C, B, A, r=26, label="x") + vertex_labels({"A": A, "B": B, "C": C}, {"A": (-16, -4), "B": (-16, 12), "C": (10, 12)})
    out["triangle"] = (doc(300, 260, els, title="Right-angled triangle ABC with the right angle at B, 58° at A and x at C",
                           description="Triangle ABC: A at the top, B bottom-left, C bottom-right. AB is vertical and BC horizontal; the right angle at B is marked with a square. The angle at A is labelled 58° and the angle at C is labelled x."), {"A": A, "B": B, "C": C})
    O = (170.0, 170.0)
    els = filled_sector(O, 120, 90, 270, radii=False) + [line((170, 50), (170, 290), id="BA")] + vertex_labels({"B": (170, 50), "A": (170, 290), "O": O}, {"B": (10, 0), "A": (10, 6), "O": (10, -6)})
    out["semicircle"] = (doc(320, 340, els, title="Shaded semicircle on the vertical diameter BA with centre O", description="A vertical line BA, B above A, O its midpoint; a semicircle with centre O bulges to the left and is shaded."), {"B": (170, 50), "A": (170, 290), "O": O})
    els, pos = number_line(40, 400, 60, -4, 5, closed=[3], open=[-2], heavy=(-2, 3))
    out["numberline"] = (doc(440, 110, els, title="Number line from -4 to 5 with an open circle at -2, a filled circle at 3 and the segment between them marked", description="A horizontal number line with arrowheads at both ends, labelled from -4 to 5 at unit intervals. An open (hollow) circle sits at -2 and a filled circle at 3; the part of the line between -2 and 3 is drawn heavier."), {})
    els = grid((40, 40), 3, 2, 80, shaded=[(0, 0), (0, 1), (1, 1)])
    out["grid"] = (doc(320, 240, els, title="A 3 by 2 grid of equal rectangles with three cells shaded in an L shape", description="Six equal rectangles in three columns and two rows. The left column's two cells and the middle cell of the bottom row are shaded; the other three are not."), {})
    els = venn((20, 20, 300, 200), (120, 120), (200, 120), 70, labels={"A": (60, 60), "B": (270, 60)}) + [text((90, 125), "g", id="g"), text((160, 125), "f", id="f"), text((235, 125), "c", id="c"), text((40, 190), "a", id="a")]
    out["venn"] = (doc(340, 240, els, title="Venn diagram of sets A and B inside the universal set with elements a, c, f, g placed", description="A rectangle for the universal set ε holds two overlapping circles A (left) and B (right). g is in A only, f in both, c in B only, a outside both."), {})
    els = pie((150, 130), 100, [(45, None, True), (315, None, False)])
    out["pie"] = (doc(300, 260, els, title="Pie chart with one shaded 45° sector", description="A circle divided by two radii into a small shaded sector of 45 degrees and a large unshaded sector."), {})
    els = compass_rose((150, 150), 70) + [line((150, 150), polar((150, 150), 110, -20), id="OA"), dot((150, 150), label="O", offset=(-18, 10))] + angle_label((150, 150), (150, 80), polar((150, 150), 110, -20), r=36, label="70°")
    out["compass"] = (doc(300, 300, els, title="Compass cross at O with a line OA drawn 70° clockwise from north", description="A north-south and an east-west line cross at O, north arrowed and labelled N, E, S, W. A line from O runs up to the right, 70° from north toward east, marked with an angle arc."), {"O": (150, 150)})
    els = axes((60, 220), 220, 170, x_label="time (h)", y_label="distance (km)", x_ticks=[(i * 50, str(i * 2)) for i in range(1, 5)], y_ticks=[(i * 50, str(i * 100)) for i in range(1, 4)]) + [line((60, 220), (260, 70), width=2.5, id="graph")]
    out["graph"] = (doc(320, 260, els, title="Distance-time graph: a straight line from the origin", description="Axes with time in hours along the bottom (2, 4, 6, 8) and distance in km up the side (100, 200, 300); a straight line rises from the origin."), {})
    return out

def _self_test() -> int:
    ok = True
    def t(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and cond
    c, r = (100.0, 100.0), 50.0
    pts = sampled_arc(c, r, 90, 270)
    t("sampled_arc: every vertex on the circle", all(abs(dist(p, c) - r) < 1e-9 for p in pts))
    t("sampled_arc: 90 steps for a semicircle at 2°", len(pts) == 91)
    els, pos = number_line(40, 400, 60, -4, 5, closed=[3], open=[-2], heavy=(-2, 3))
    xs = [pos[v][0] for v in range(-4, 6)]
    t("number_line: ticks on a 40 px lattice", all(abs(b - a - 40) < 1e-9 for a, b in zip(xs, xs[1:])))
    t("number_line: closed dot filled with ink, open dot white", any(e.get("fill", {}).get("color") == INK for e in els) and any(e.get("fill", {}).get("color") == WHITE for e in els))
    t("number_line: 10 numerals rendered as text", sum(1 for e in els if e["type"] == "text") == 10)
    m = right_angle_mask((0, 0), (0, -10), (10, 0), 10)[0]
    t("right_angle_mask: a white 4-gon with the vertex as a corner", m["fill"]["color"] == WHITE and [0, 0] in m["points"] and len(m["points"]) == 4)
    C = triangle_from_angles((0, 0), (100, 0), 60, 60)
    t("triangle_from_angles: equilateral apex", abs(dist(C, (0, 0)) - 100) < 1e-6 and abs(dist(C, (100, 0)) - 100) < 1e-6 and C[1] < 0)
    g = grid((0, 0), 3, 2, 10, shaded=[(0, 0)])
    t("grid: 6 rects, 1 shaded", len(g) == 6 and sum(1 for e in g if "fill" in e) == 1)
    s = filled_sector(c, r, 0, 90)
    t("filled_sector: polygon(stroke 0) + rim + 2 radii, fill first", s[0]["type"] == "polygon" and s[0]["stroke"]["width"] == 0 and s[1]["type"] == "arc" and len(s) == 4)
    demos = _demos()
    t("demos: every element id unique per figure", all(len({e["id"] for e in d["elements"]}) == len(d["elements"]) for d, _ in demos.values()))
    t("demos: budget ≤ 32 except the number line's ticks", all(len(d["elements"]) <= 32 for k, (d, _) in demos.items() if k != "numberline"))
    try:
        text((0, 0), "$x$"); t("text refuses $", False)
    except AssertionError:
        t("text refuses $", True)
    print("SELF-TEST PASS" if ok else "SELF-TEST FAIL")
    return 0 if ok else 1

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    if "--demo" in sys.argv:
        d = sys.argv[sys.argv.index("--demo") + 1]
        os.makedirs(d, exist_ok=True)
        for name, (document, anchors) in _demos().items():
            write_figure(os.path.join(d, f"{name}.json"), document, anchors)
            print("wrote", os.path.join(d, f"{name}.json"))
        sys.exit(0)
    print(__doc__)
