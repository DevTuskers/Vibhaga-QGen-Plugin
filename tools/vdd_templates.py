#!/usr/bin/env python3
"""vdd_templates.py — the eighteen figure TEMPLATES of the vibhaga-qgen plugin.

A template turns a question's STEM NUMBERS into a finished figure — a VDD document, an
anchors sidecar and a `channel: constructed` claim set — in one `Built` object:

    from vdd_templates import build_cuboid
    b = build_cuboid(figure_id="q8", stem="A cuboid has length 5 cm, width 3 cm and height 2 cm.",
                     length=5, width=3, height=2)
    paths = b.write("out/")          # q8.json + q8.anchors.json + q8-claims.txt

    python3 tools/vdd_templates.py list
    python3 tools/vdd_templates.py build spec.json [--out DIR]
    python3 tools/vdd_templates.py --self-test

WHY THIS EXISTS (the 2026-09-29 cuboid, T-QG-2): a hand-drawn figure drew the stem's 5:2
face at 1.5:1 and its claim set recorded the DRAWN ratio, so the audit agreed with itself.
A template is the opposite direction: the numbers come from the stem (checked with
`require_stem` against the same regex the audit applies to `stem:`), the geometry is
computed from them, and the claim set is emitted by the same code — drawn and claimed can
never drift apart. Numbers that live ON the figure (pictograph counts, printed side
labels, dot counts, marked positions) are figure content, the same convention the corpus
claim sets use: only values the stem itself must own are stem-checked.

Every build runs the clearance pre-flight (`finish` step 2): each label's estimated box —
the real renderer's align/baseline/`labelOffset` semantics, not a guess — must keep
>= 6 rendered px to every stroke (measured to the stroke's EDGE) and >= 8 rendered px to
the canvas edge, evaluated at the narrowest render width (320 px → 296 content px). The
rendered measurement in `tools/vdd-check.mjs` remains the truth; this is the pre-flight.
"""
from __future__ import annotations

import copy
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vdd_cookbook as vc                          # noqa: E402

XY = tuple[float, float]
SINHALA = re.compile(r"[඀-෿]")
STEM_NUM = re.compile(r"\d+(?:\.\d+)?")            # audit-claim-set's own stem regex
FIG_ID = re.compile(r"[A-Za-z0-9._-]+")

FS = 18.0                    # renderer default font size (DiagramRenderer DEFAULT_FONT_SIZE)
MARGIN = 12.0                # canvas margin around ALL ink, canvas units
CHAR_EM = 0.62               # measured label advance; the renderer measured 0.53–0.69 em/char
LABEL_GAP = 18.0             # angleMark label gap (DiagramRenderer)
EDGE_PX, STROKE_PX = 8.0, 6.0   # vdd-check rule: rendered px to canvas edge / to stroke edge
SLACK_EDGE, SLACK_STROKE = 1.0, 2.0   # the estimator errs — require the render limits plus slack
# The narrowest render surface is the StudentPreview figure plate at 320 px: its content box is
# 320 − 2×12 px padding − 2×1 px border = 294 px (measured: svg width = 294 on /diagtest). A canvas
# wider than that renders BELOW 1 px per unit — clearance thresholds scale by 1/s, s = min(1,
# PLATE_INNER / canvas_width); canvases narrower than it render ≥1 px/unit but get no credit for it.
PLATE_INNER = 294.0
# canvas height/width bound — a figure much taller than wide renders taller than a phone screen
# on the 375 px plate (W8 dogfood: a 1×10 shaded grid came out 375×2253). The same constant is
# the `aspect` rule in vdd-check.mjs and visual-metrics.mjs; no override — re-lay the figure out.
MAX_ASPECT = 2.0
# DOM getBBox on a `dominantBaseline="middle"` <text> returns the font's ~1.22em line box, biased
# UP — measured on Inter (2026-10-01, capital "P" at size 18): −0.674·size above centre,
# +0.543·size below. The old ±size/2 estimate under-measures the top by ~3 units and real renders
# failed the edge rule while the estimate passed (rebuild Q4: 7.9 px at 320).
MID_UP, MID_DOWN = 0.70, 0.58
# …but a lone point label reaches only ~0.50·size below its dominant-baseline middle anchor —
# measured on the rendered DOM box (2026-10-02, Inter capital "P"/"Q" at 18: point→box distance
# mark_off − 9.0, i.e. +0.50·size; DiagramRenderer's own label box uses ±0.5·size). Modelled at
# 0.53 to keep a small pad over the measurement. A descender glyph (gjpqy…) reaches ~MID_DOWN.
POINT_LABEL_DOWN = 0.53

# Floating labels — a `text` element carrying `_near` asks finish() to place it (W10a).
FLOAT_GAP = 14.0          # default `_gap`: units from the anchor to the box's NEAR edge
FLOAT_REACH, FLOAT_STEP = 36.0, 6.0   # candidates try _gap, _gap+6, …, _gap+36
FLOAT_DIRS = [0.0, -45.0, -90.0, -135.0, 180.0, 135.0, 90.0, 45.0,     # E NE N NW W SW S SE
              -22.5, -67.5, -112.5, -157.5, 157.5, 112.5, 67.5, 22.5]  # ENE NNE NNW WNW WSW SSW SSE ESE
OWN_PX = 6.0              # a floater's centre must beat other anchors/dots by this many px
OWN_FIXED_PX = 3.0        # …and a fixed label its claim's anchor by this much (pre-flight)
ON_TOL = 2.0              # a point this close to an outline lies ON it (the same-region case)

COMPASS = {"N": -90.0, "NE": -45.0, "E": 0.0, "SE": 45.0,
           "S": 90.0, "SW": 135.0, "W": 180.0, "NW": -135.0}
# claims whose absence can be claimed on the `none` line
MARK_CLASSES = ("tickMark", "parallelMark", "angleMark", "angleArc", "arrow", "dashed", "shaded")
NON_KEY = ("label ", "free-text ", "none ", "paint ")   # not load-bearing on their own


class TemplateError(ValueError):
    """An input the stem does not support, or a layout the clearance pre-flight refuses."""


@dataclass
class Built:
    """A finished figure: the VDD document, the fitted anchors and the claim-set text."""
    figure_id: str
    doc: dict
    anchors: dict[str, XY]
    claims: str

    def write(self, out_dir) -> dict[str, Path]:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        fig = out / f"{self.figure_id}.json"
        anch = out / f"{self.figure_id}.anchors.json"
        cl = out / f"{self.figure_id}-claims.txt"
        vc.write_figure(str(fig), self.doc, anchors=self.anchors)   # writes <id>.anchors.json itself
        if not anch.exists():
            # write_figure skips an empty anchors dict (a figure with no named points —
            # dot_pattern, pictograph); every template still emits the trio so the
            # printed list is always true
            anch.write_text("{}\n", encoding="utf-8")
        cl.write_text(self.claims, encoding="utf-8")
        return {"figure": fig, "anchors": anch, "claims": cl}


# ────────────────────────────────────────────────────────────────────────────────
# Stem discipline
# ────────────────────────────────────────────────────────────────────────────────
def stem_numbers(stem: str) -> list[float]:
    """The numbers a stem states — the SAME regex `audit-claim-set.py` runs over `stem:`."""
    return [float(x) for x in STEM_NUM.findall(stem)]


def _has_stem(nums: list[float], v: float) -> bool:
    return any(abs(v - n) <= 1e-9 for n in nums)


def require_stem(stem: str, **values: float) -> None:
    """Refuse a number the stem never states — geometry is computed FROM the stem, never the reverse."""
    nums = stem_numbers(stem)
    missing = [f"{k}={v:g}" for k, v in values.items() if not _has_stem(nums, v)]
    if missing:
        raise TemplateError(
            f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not a number the stem "
            f"states (stem numbers {', '.join(f'{n:g}' for n in nums)}) — a template draws only "
            f"what the stem gives it")


def _ratio_justified(nums: list[float], v: float) -> bool:
    """The audit's stem check for a `ratio`: some pair of stem numbers gives v (±0.5%)."""
    return bool(v) and any(a != 0 and b != 0 and abs(a / b - v) / v <= 0.005
                           for a in nums for b in nums)


# ────────────────────────────────────────────────────────────────────────────────
# Label boxes — the REAL renderer's placement (DiagramRenderer.tsx), not a guess
# ────────────────────────────────────────────────────────────────────────────────
# Sinhala combining codepoints — vowel signs, the virama and zero-width joiners add NO
# advance of their own; counting them as full glyphs triples the label estimate and the
# whole figure renders small (lead review R2: q5's day names at ~11 px in a widened canvas).
# Measured on the real renderer: one visible Sinhala cluster ≈ 0.8 em incl. its marks.
_SINHALA_MARK = re.compile(
    r"[\u0DCA\u0DCF-\u0DD4\u0DD6-\u0DD9\u0DDA-\u0DDF\u0DF2-\u0DF3\u200C\u200D]")
SINHALA_CLUSTER_EM = 0.80


def _label_half_along(text: str, size: float, nx: float, ny: float) -> float:
    """Half-extent of a middle/middle text label's box along the unit direction (nx,ny) —
    needed to place a label off a stroke by its NEAR side. The DOM box is asymmetric
    (MID_UP/MID_DOWN): a label pushed DOWN (ny>0) faces the figure with its taller top."""
    w = _label_width(text, size)
    return w * abs(nx) / 2 + (MID_UP if ny > 0 else MID_DOWN) * size * abs(ny)


def _label_width(text: str, size: float) -> float:
    # width ≈ size · Σ em per VISIBLE glyph — Sinhala marks ride on their base cluster
    return size * sum(
        CHAR_EM if not (SINHALA.match(ch) or ch in "‌‍") else
        (0.0 if _SINHALA_MARK.match(ch) else SINHALA_CLUSTER_EM)
        for ch in text)


def math_visible(latex: str) -> str:
    """The text a math label draws, for SIZING its box only (KaTeX does the real render).
    `x\\ \\text{m}` -> `x   m` — latex commands become spacing."""
    return re.sub(r"[{}\\]", "", re.sub(r"\\[a-zA-Z]+", " ", latex))


def _bisector_deg(from_deg: float, to_deg: float, reflex: bool) -> float:
    """DiagramRenderer's bisectorDeg: midpoint of the drawn sweep (long way when reflex)."""
    d = (to_deg - from_deg) % 360
    if d > 180:
        d -= 360
    if reflex:
        d = d - 360 if d > 0 else d + 360
    return from_deg + d / 2


def _sweep_delta(from_deg: float, to_deg: float, sweep: str | None) -> float:
    d = to_deg - from_deg
    if sweep == "cw" and d < 0:
        d += 360
    if sweep == "ccw" and d > 0:
        d -= 360
    return max(-360.0, min(360.0, d))


def _angle_of(p, o) -> float:
    return math.degrees(math.atan2(p[1] - o[1], p[0] - o[0]))


def label_boxes(elements: list[dict], font_size: float = FS) -> list[tuple[str, float, float, float, float]]:
    """(text, x0, y0, x1, y1) for every label the renderer draws — <text> runs and math overlays.

    text:       align start|middle|end (default start — SVG's own default), baseline
                `top` → [y, y+size], `alphabetic` → [y−0.72s, y+0.28s], else middle → y±size/2;
                each `\\n` line sits size·1.2 below the previous anchor.
    point:      label at `at + labelOffset` (default [8,-8]), always start/middle, size=fontSize.
    angleMark:  centred on the drawn sweep's bisector at r+18+0.28·size·len (r·√2 for `right`),
                middle/middle, size=0.9·fontSize.
    math:       HTML overlay — translate x −0/−50/−100% (start/middle/end), y −0/−50/−100%
                (top/other/alphabetic). Its rendered width is KaTeX's — estimated generously.
    """
    out: list[tuple[str, float, float, float, float]] = []

    def box(x, y, w, h):
        out.append((None, x, y, x + w, y + h))   # type: ignore[arg-type]

    for el in elements:
        t = el["type"]
        if t == "text":
            size = el.get("fontSize", font_size)
            align = el.get("align", "start")     # renderer: anything but middle/end anchors start
            baseline = el.get("baseline", "middle")
            for i, line_ in enumerate(str(el["value"]).split("\n")):
                w = _label_width(line_, size)
                ax, ay = el["at"][0], el["at"][1] + i * size * 1.2
                x = ax - w / 2 if align == "middle" else ax - w if align == "end" else ax
                if baseline == "top":
                    y0, y1 = ay, ay + size
                elif baseline == "alphabetic":
                    y0, y1 = ay - size * 0.72, ay + size * 0.28
                else:
                    y0, y1 = ay - size * MID_UP, ay + size * MID_DOWN
                out.append((line_, x, y0, x + w, y1))
        elif t == "point" and el.get("label"):
            size = font_size                      # the point label ignores el.fontSize — always defaults
            ox, oy = el.get("labelOffset", [8, -8])
            w = _label_width(el["label"], size)
            # the rendered box is shallower below the anchor than the text-run MID_DOWN bound —
            # a lone capital has no descender (measured ~0.50·size); keep MID_DOWN for labels
            # carrying a descender letter.
            down = size * (MID_DOWN if re.search(r"[gjpqy]", str(el["label"])) else POINT_LABEL_DOWN)
            out.append((el["label"], el["at"][0] + ox, el["at"][1] + oy - size * MID_UP,
                        el["at"][0] + ox + w, el["at"][1] + oy + down))
        elif t == "angleMark" and el.get("label"):
            size = font_size * 0.9
            r = el["r"] * (math.sqrt(2) if el.get("variant") == "right" else 1)
            d = r + LABEL_GAP + 0.28 * size * len(el["label"])
            bis = _bisector_deg(_angle_of(el["from"], el["vertex"]),
                                _angle_of(el["to"], el["vertex"]), bool(el.get("reflex")))
            cx, cy = el["vertex"][0] + d * math.cos(math.radians(bis)), \
                     el["vertex"][1] + d * math.sin(math.radians(bis))
            w = _label_width(el["label"], size)
            out.append((el["label"], cx - w / 2, cy - size * MID_UP, cx + w / 2, cy + size * MID_DOWN))
        elif t == "math":
            # KaTeX is an HTML overlay, not <text> — vdd-check cannot measure it, so templates
            # never put a claim-set label on one; still bound it for the canvas fit.
            size = el.get("fontSize", font_size)
            visible = math_visible(el["latex"])
            w = max(_label_width(visible, size), size * 0.8)
            h = size * 1.2
            ax, ay = el["at"]
            x0 = ax - w / 2 if el.get("align") == "middle" else ax - w if el.get("align") == "end" else ax
            bl = el.get("baseline")
            y0 = ay if bl == "top" else ay - h if bl == "alphabetic" else ay - h / 2
            out.append((el["latex"], x0, y0, x0 + w, y0 + h))
    return out


# ────────────────────────────────────────────────────────────────────────────────
# Stroke geometry — what vdd-check measures labels against (the stroke's EDGE)
# ────────────────────────────────────────────────────────────────────────────────
def _sample_arc(c, r, start, delta, step=8.0) -> list[XY]:
    n = max(2, math.ceil(abs(delta) / step))
    return [(c[0] + r * math.cos(math.radians(start + delta * i / n)),
             c[1] + r * math.sin(math.radians(start + delta * i / n))) for i in range(n + 1)]


def stroke_segments(elements: list[dict], stroke_w: float = 2.0) -> list[tuple[XY, XY, float]]:
    """(a, b, width) for every shape outline vdd-check's render pass measures — INCLUDING
    fill-only polygons/rects/circles (their outline path is measured regardless of width)."""
    segs: list[tuple[XY, XY, float]] = []

    def add(pts, w, closed=False):
        w = max(float(w), 0.0)
        for i in range(len(pts) - 1):
            segs.append((pts[i], pts[i + 1], w))
        if closed and len(pts) > 1:
            segs.append((pts[-1], pts[0], w))

    def w_of(el):
        return (el.get("stroke") or {}).get("width", stroke_w)

    for el in elements:
        t = el["type"]
        if t in ("line", "arrow"):
            add(el["points"], w_of(el))
        elif t == "polyline":
            add(el["points"], w_of(el))
        elif t == "polygon":
            add(el["points"], w_of(el), closed=True)
        elif t == "rect":
            x, y, w_, h = el["x"], el["y"], el["width"], el["height"]
            add([(x, y), (x + w_, y), (x + w_, y + h), (x, y + h)], w_of(el), closed=True)
        elif t == "circle":
            r = el["r"]
            if r > 0:
                add(_sample_arc(el["center"], r, 0, 360), w_of(el))
        elif t == "point":
            r = el.get("r", 3.5)
            if r > 0:
                add(_sample_arc(el["at"], r, 0, 360), 1.0)   # an unstoked dot still measures ~1px
        elif t == "arc":
            delta = _sweep_delta(el["start"], el["end"], el.get("sweep"))
            add(_sample_arc(el["center"], el["r"], el["start"], delta), w_of(el))
        elif t == "angleMark":
            v = el["vertex"]
            f, tt = _angle_of(el["from"], v), _angle_of(el["to"], v)
            if el.get("variant") == "right":
                r = el["r"]
                a = (v[0] + r * math.cos(math.radians(f)), v[1] + r * math.sin(math.radians(f)))
                b = (v[0] + r * math.cos(math.radians(tt)), v[1] + r * math.sin(math.radians(tt)))
                corner = (a[0] + b[0] - v[0], a[1] + b[1] - v[1])
                add([a, corner, b], w_of(el))
            else:
                swept = _bisector_deg(f, tt, bool(el.get("reflex"))) * 2 - f
                for k in range(el.get("arcs", 1)):
                    add(_sample_arc(v, el["r"] - k * 5, f, swept - f), w_of(el))
        elif t == "tickMark":
            m = vc.lerp(tuple(el["on"][0]), tuple(el["on"][1]), el.get("at", 0.5))
            nx, ny = vc.normal(tuple(el["on"][0]), tuple(el["on"][1]))
            ux, uy = vc.unit(tuple(el["on"][0]), tuple(el["on"][1]))
            s = el.get("size", 8)
            # the renderer spreads `count` strokes 6 units apart, each a FULL-size
            # perpendicular stroke — under-modelling this lets a label sit inside ink
            for k in range(el.get("count", 1)):
                off = (k - (el.get("count", 1) - 1) / 2) * 6
                c = (m[0] + ux * off, m[1] + uy * off)
                add([(c[0] - nx * s, c[1] - ny * s), (c[0] + nx * s, c[1] + ny * s)],
                    w_of(el))
        elif t == "parallelMark":
            m = vc.lerp(tuple(el["on"][0]), tuple(el["on"][1]), el.get("at", 0.5))
            ux, uy = vc.unit(tuple(el["on"][0]), tuple(el["on"][1]))
            nx, ny = -uy, ux
            s = el.get("size", 8)
            # `count` chevrons, 6 units apart along the line, tip a FULL size ahead —
            # the class-2 double-arrow is wider than a single-chevron model admits
            for k in range(el.get("count", 1)):
                off = (k - (el.get("count", 1) - 1) / 2) * 6
                cx, cy = m[0] + ux * off, m[1] + uy * off
                tip = (cx + ux * s, cy + uy * s)
                for sign in (1, -1):
                    tail = (cx - ux * s + sign * nx * s, cy - uy * s + sign * ny * s)
                    add([tail, tip], w_of(el))
    return segs


def _pt_seg(a: XY, u: XY, v: XY) -> float:
    dx, dy = v[0] - u[0], v[1] - u[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(a[0] - u[0], a[1] - u[1])
    t = max(0.0, min(1.0, ((a[0] - u[0]) * dx + (a[1] - u[1]) * dy) / L2))
    return math.hypot(a[0] - u[0] - t * dx, a[1] - u[1] - t * dy)


def _seg_seg_dist(p: XY, q: XY, r: XY, s: XY) -> float:
    """0 when the segments cross, else the smallest endpoint-to-segment distance."""
    den = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])   # cross(d1, d2)
    if den:
        t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / den
        u = ((r[0] - p[0]) * (q[1] - p[1]) - (r[1] - p[1]) * (q[0] - p[0])) / den
        if 0 <= t <= 1 and 0 <= u <= 1:
            return 0.0
    return min(_pt_seg(p, r, s), _pt_seg(q, r, s), _pt_seg(r, p, q), _pt_seg(s, p, q))


def _seg_rect_dist(p: XY, q: XY, box_: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = box_
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
             ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(_seg_seg_dist(p, q, a, b) for a, b in edges)


# ────────────────────────────────────────────────────────────────────────────────
# finish — fit to canvas, clearance pre-flight, emit the claim set
# ────────────────────────────────────────────────────────────────────────────────
def _clearance_units(px: float, span_x: float) -> float:
    """How many CANVAS units still render as `px` on the tightest surface once a figure of
    content width `span_x` is fitted — builders use it to size label gaps on wide canvases."""
    edge = EDGE_PX + SLACK_EDGE
    margin = max(MARGIN, edge * (span_x + 60.0) / (PLATE_INNER - 2 * edge))
    # clearance in units = px / s with s = min(1, PLATE_INNER/(span+2m+60)) — a canvas narrower
    # than the plate renders ABOVE 1 px/unit but earns no credit for it (never under `px` units).
    return px * max(1.0, (span_x + 2 * margin + 60.0) / PLATE_INNER)


def _fit_extent(strokes: list[tuple[XY, XY, float]], boxes: list[tuple]) -> tuple[float, float, int, int]:
    """(dx, dy, W, H) — the canvas fit finish() computes for this ink, factored out so the
    floating-label search can estimate rendered px on the SAME scale the final pre-flight
    uses: the margin must still clear the edge after the render scales down to the narrowest
    surface — a fixed 12 units drops under 8 rendered px once the canvas widens (critic R3
    finding 3: number line 0–10+ refused). Solve edge ≥ EDGE_PX + SLACK_EDGE on the TIGHTER
    card scale:  margin·294/(span + 2·margin + 60) ≥ 9  ⇒  margin ≥ (9·span + 540)/276."""
    xs, ys = [], []
    for a, b, w in strokes:
        xs += [a[0] - w / 2, b[0] - w / 2, a[0] + w / 2, b[0] + w / 2]
        ys += [a[1] - w / 2, b[1] - w / 2, a[1] + w / 2, b[1] + w / 2]
    for _s, x0, y0, x1, y1 in boxes:
        xs += [x0, x1]
        ys += [y0, y1]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    span_x, span_y = maxx - minx, maxy - miny
    margin = max(MARGIN, (EDGE_PX + SLACK_EDGE) *
                 (span_x + 60.0) / (PLATE_INNER - 2 * (EDGE_PX + SLACK_EDGE)) + 0.05)
    return (margin - minx, margin - miny,
            math.ceil(span_x + 2 * margin), math.ceil(span_y + 2 * margin))


# ────────────────────────────────────────────────────────────────────────────────
# Floating labels — a `text` element carrying `_near` (+ optional `_gap`) asks finish()
# to place it: the pre-flight already knows the constraints, so it solves them too.
# ────────────────────────────────────────────────────────────────────────────────
def _pt_in_poly(p: XY, pts: list[XY]) -> bool:
    x, y = p
    inside, j = False, len(pts) - 1
    for i in range(len(pts)):
        xi, yi, xj, yj = pts[i][0], pts[i][1], pts[j][0], pts[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _regions(elements: list[dict]) -> list[tuple]:
    """("c", centre, r) | ("p", pts) outlines the same-region rule respects — unfilled
    circles, unfilled closed polygons and unfilled rects (a FILLED circle is a dot, not
    a region). Any of these may carry `_region: false` to stay decorative — a small
    unfilled marker around an anchor must not trap its label inside it."""
    out = []
    for el in elements:
        if el.get("_region") is False:
            continue
        if el["type"] == "circle" and not el.get("fill") and el.get("r", 0) > 0:
            out.append(("c", (float(el["center"][0]), float(el["center"][1])), float(el["r"])))
        elif el["type"] == "polygon" and not el.get("fill") and len(el.get("points") or []) >= 3:
            out.append(("p", [tuple(map(float, p)) for p in el["points"]]))
        elif el["type"] == "rect" and not el.get("fill") and \
                all(isinstance(el.get(k), (int, float)) for k in ("x", "y", "width", "height")):
            x, y, w, h = (float(el[k]) for k in ("x", "y", "width", "height"))
            out.append(("p", [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]))
    return out


def _side_of(p: XY, reg) -> str:
    """'on' | 'in' | 'out' — 'on' means within ON_TOL of the outline itself."""
    if reg[0] == "c":
        d = math.hypot(p[0] - reg[1][0], p[1] - reg[1][1])
        return "on" if abs(d - reg[2]) <= ON_TOL else ("in" if d < reg[2] else "out")
    pts = reg[1]
    if min(_pt_seg(p, a, b) for a, b in zip(pts, pts[1:] + pts[:1])) <= ON_TOL:
        return "on"
    return "in" if _pt_in_poly(p, pts) else "out"


def _dot_centres(elements: list[dict]) -> list[XY]:
    """Positions a floating label must beat for its own anchor: `point` marks and
    filled circles (the dots a hand-drawn figure's `_near` points sit on)."""
    return [tuple(map(float, el["at"])) if el["type"] == "point"
            else tuple(map(float, el["center"]))
            for el in elements
            if el["type"] == "point" or (el["type"] == "circle" and el.get("fill"))]


def _union_centre(boxes: list[tuple]) -> XY:
    return ((min(b[1] for b in boxes) + max(b[3] for b in boxes)) / 2,
            (min(b[2] for b in boxes) + max(b[4] for b in boxes)) / 2)


FLOAT_RULES = ("the stroke-clearance rule", "the label-gap rule", "the own-anchor rule",
               "the same-region rule")


def _floater_bad(cbs: list[tuple], near: XY, rivals: list[XY], strokes: list[tuple],
                 others: list[tuple], regions: list[tuple], s: float) -> int:
    """Bitmask of the four placement rules for a floater's candidate boxes `cbs` at rendered
    scale s — 1 stroke clearance · 2 label gap · 4 own-anchor · 8 same-region. `others` is
    every label box that is not this floater's (fixed labels + the other floaters')."""
    bad = 0
    if strokes and min(_seg_rect_dist(a, b, cb[1:5]) - w / 2
                       for a, b, w in strokes for cb in cbs
                       ) * s < STROKE_PX + SLACK_STROKE:
        bad |= 1
    if any(_rect_gap(cb[1:5], pb[1:5]) * s < 4.0 for cb in cbs for pb in others):
        bad |= 2
    ctr = _union_centre(cbs)
    own = math.hypot(ctr[0] - near[0], ctr[1] - near[1])
    if any((math.hypot(ctr[0] - o[0], ctr[1] - o[1]) - own) * s < OWN_PX for o in rivals):
        bad |= 4
    for r in regions:
        sn = _side_of(near, r)
        if _side_of(ctr, r) != ("out" if sn == "on" else sn):
            bad |= 8
            break
    return bad


def _search_floater(kind: str, el: dict, near: XY, gap: float, off: XY,
                    rivals: list[XY], strokes: list[tuple], others: list[tuple],
                    regions: list[tuple], fs: float) -> tuple[list, list]:
    """Sweep FLOAT_DIRS × `_gap … _gap+FLOAT_REACH` for `el` against the given fixed boxes;
    (at, label boxes) of the first candidate passing all four rules, or a TemplateError
    naming the rule that rejected most candidates."""
    size = float(el.get("fontSize", fs))
    tally = [0] * len(FLOAT_RULES)
    for k in range(int(FLOAT_REACH / FLOAT_STEP) + 1):
        d = gap + FLOAT_STEP * k
        for deg in FLOAT_DIRS:
            ux, uy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
            half = _label_half_along(str(el["value"]), size, ux, uy)
            want = (near[0] + (d + half) * ux, near[1] + (d + half) * uy)
            at = [vc.r2(want[0] - off[0]), vc.r2(want[1] - off[1])]
            cbs = label_boxes([dict(el, at=at)], fs)
            _dx, _dy, W, _H = _fit_extent(strokes, others + cbs)
            bad = _floater_bad(cbs, near, rivals, strokes, others, regions,
                               min(1.0, PLATE_INNER / (W + 60.0)))
            if not bad:
                return at, cbs
            for i in range(len(FLOAT_RULES)):
                if bad & (1 << i):
                    tally[i] += 1
    n_cand = (int(FLOAT_REACH / FLOAT_STEP) + 1) * len(FLOAT_DIRS)
    i = tally.index(max(tally))
    raise TemplateError(
        f"{kind}: floating label {el.get('value')!r} found no clear spot near "
        f"{near} — {FLOAT_RULES[i].removeprefix('the ')} rejected {tally[i]} of "
        f"{n_cand} candidates")


def _place_floaters(kind: str, elements: list[dict], fs: float) -> None:
    """Place each `text` carrying `_near` (and optional `_gap`) clear of the figure.

    For every floater, in element order, candidates sweep FLOAT_DIRS × distances
    `_gap … _gap + FLOAT_REACH` — the box's near edge sits that many units off the
    anchor. The first candidate keeping, in RENDERED px on the fitted card scale:
    (a) ≥ STROKE_PX + SLACK_STROKE to every stroke edge, (b) ≥ 4 px to every other
    placed label box, (c) a centre ≥ OWN_PX nearer `_near` than every other floater's
    anchor and every dot centre, and (d) the centre on the same side of every region
    outline as `_near` — OUTSIDE one `_near` sits ON (within ON_TOL) — wins.

    Each placed floater keeps a `_floater` marker (its chosen `at`) so the pre-flight's
    refusals can name them honestly. After all floaters are placed the placement scale is
    re-derived with EVERY label box — a later floater can widen the canvas and shrink the
    rendered px under an earlier one's marginal pass — and any floater now failing a–d is
    re-searched with every other label fixed, twice at most. The normal fit + pre-flight
    then re-check everything and stay the final word."""
    floaters = [el for el in elements if el["type"] == "text" and "_near" in el]
    if not floaters:
        return
    strokes = stroke_segments(elements)
    fixed = label_boxes([el for el in elements if el not in floaters], fs)
    dots = _dot_centres(elements)
    regions = _regions(elements)
    prep: dict[int, tuple] = {}
    placed_of: dict[int, list] = {}
    for el in floaters:
        near = tuple(map(float, el["_near"]))
        gap = float(el.get("_gap", FLOAT_GAP))
        # where this element's box centre sits relative to its `at` (align/baseline/lines)
        off = _union_centre(label_boxes([dict(el, at=[0.0, 0.0])], fs))
        rivals = [tuple(map(float, f["_near"])) for f in floaters if f is not el] + \
                 [c for c in dots if math.hypot(c[0] - near[0], c[1] - near[1]) > ON_TOL]
        prep[id(el)] = (near, gap, off, rivals)

    def others_of(el) -> list:
        return fixed + [b for f in floaters if f is not el for b in placed_of.get(id(f), [])]

    for el in floaters:
        near, gap, off, rivals = prep[id(el)]
        at, cbs = _search_floater(kind, el, near, gap, off, rivals, strokes,
                                  others_of(el), regions, fs)
        el["at"], el["_floater"], placed_of[id(el)] = at, list(at), cbs

    for _pass in range(2):
        _dx, _dy, W, _H = _fit_extent(
            strokes, fixed + [b for cbs in placed_of.values() for b in cbs])
        s = min(1.0, PLATE_INNER / (W + 60.0))
        redo = [el for el in floaters
                if _floater_bad(placed_of[id(el)], prep[id(el)][0], prep[id(el)][3],
                                strokes, others_of(el), regions, s)]
        for el in redo:
            near, gap, off, rivals = prep[id(el)]
            at, cbs = _search_floater(kind, el, near, gap, off, rivals, strokes,
                                      others_of(el), regions, fs)
            el["at"], el["_floater"], placed_of[id(el)] = at, list(at), cbs
        if not redo:
            break


def _check_label_texts(elements: list[dict], extra: list[str], medium: str) -> None:
    """vdd-check rule 3 is medium-conditional: Sinhala in `math.latex` is refused ALWAYS (KaTeX
    cannot shape it); Sinhala in text/point labels is refused only when the question's `medium`
    is not `sinhala` — one diagram_dsl per node means a figure cannot be bilingual, and on a
    mono-medium Sinhala question Sinhala labels are the correct ink. `$`/backtick reach the
    student raw on any medium."""
    for el in elements:
        s = (el.get("value") if el["type"] == "text" else
             el.get("latex") if el["type"] == "math" else el.get("label"))
        if not isinstance(s, str):
            continue
        if el["type"] == "math":
            if SINHALA.search(s):
                raise TemplateError(
                    f"math label {s!r} contains Sinhala — KaTeX cannot shape it "
                    f"(refused on every medium)")
        else:
            extra.append(s)
    for s in extra:
        if SINHALA.search(s) and medium != "sinhala":
            raise TemplateError(
                f"label {s!r} contains Sinhala — vdd-check rule 3 refuses it when the "
                f"question's medium is {medium!r} (a figure cannot be bilingual); pass "
                f"medium='sinhala' when the question is sinhala-medium")
        if "$" in s or "`" in s:
            raise TemplateError(f"label {s!r} contains `$` or a backtick — it reaches the student raw")
        if "|" in s or '"' in s or "\n" in s:
            raise TemplateError(f"label {s!r} contains a claim-separator character (`|`, "
                                f"a double quote or a newline) — it would corrupt the "
                                f"claim set's `label \"{s}\" …` line")


def _translate(elements: list[dict], dx: float, dy: float) -> None:
    for el in elements:
        for key in ("points", "at", "center", "vertex", "from", "to", "on"):
            if key in el:
                v = el[key]
                if isinstance(v, list) and v and isinstance(v[0], (list, tuple)):
                    el[key] = [[vc.r2(p[0] + dx), vc.r2(p[1] + dy)] for p in v]
                elif isinstance(v, (list, tuple)):
                    el[key] = [vc.r2(v[0] + dx), vc.r2(v[1] + dy)]
                # a scalar (parallelMark's fractional `at`) is not a coordinate
        if "x" in el and "y" in el:                 # rect
            el["x"], el["y"] = vc.r2(el["x"] + dx), vc.r2(el["y"] + dy)


def finish(*, kind: str, figure_id: str, stem: str, elements: list[dict],
           anchors: dict[str, XY], points: list[str], segments: list[str],
           claims: list[tuple[str, str, str]], ask: list[tuple[str, str]] | None,
           title: str | None, description: str | None,
           scale: str, ambiguous: list[str] | None = None,
           departures: list[str] | None = None, budget: int | None = None,
           contested: list[tuple[str, str]] | None = None,
           medium: str = "english") -> Built:
    """Fit the figure to its canvas, run the label-clearance pre-flight, emit the claim set.

    `elements`/`anchors` are never mutated — the caller may reuse the same lists across
    retried finish() calls even after a raise."""
    elements = copy.deepcopy(elements)
    anchors = copy.deepcopy(anchors)
    if not FIG_ID.fullmatch(figure_id):
        raise TemplateError(f"figure_id {figure_id!r} must be one token (letters/digits/._-)")
    if not stem.strip():
        raise TemplateError("a constructed figure needs a `stem` — it is the only ground truth")
    medium = str(medium).strip().lower()
    ids = [el.get("id") for el in elements]
    if len(ids) != len(set(ids)):
        raise TemplateError(f"{kind}: duplicate element ids — {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    _check_label_texts(elements, [title or "", description or ""], medium)

    fs = FS
    _place_floaters(kind, elements, fs)      # `_near` texts get their `at` + `_floater` mark

    # 1. fit — bbox over ALL ink (shape outlines incl. half the stroke) plus the label boxes
    # `owners` maps each label box back to its element, so a pre-flight refusal on a placed
    # floater can say so instead of telling the author to "move" a label it placed itself.
    owners: list[dict] = []
    boxes: list[tuple] = []
    for el in elements:
        for b in label_boxes([el], fs):
            boxes.append(b)
            owners.append(el)
    strokes = stroke_segments(elements)
    dx, dy, W, H = _fit_extent(strokes, boxes)
    _translate(elements, dx, dy)
    anchors = {k: (vc.r2(v[0] + dx), vc.r2(v[1] + dy)) for k, v in anchors.items()}
    if H > MAX_ASPECT * W:
        raise TemplateError(
            f"{kind}: canvas is {H}×{W} (h/w {H / W:.1f} > {MAX_ASPECT:g}) — renders "
            f"~{round((375 - 26) * H / W)} px tall at 375; re-lay it out, e.g. a 1×10 grid as 5×2")

    # 2. clearance pre-flight — rendered px at the NARROWEST surface (the 294 px plate inner
    # width — PLATE_INNER). Edge distance is bound by OUR margin on the student surface
    # (s = min(1, 294/W)). Stroke distance is also measured on the CARD surface, where
    # normalizeVdd refits the canvas ~55–60 units wider (empirical) — model the tighter card
    # scale for stroke clearance. The min(1,·) caps keep a narrow canvas from claiming >1 px/unit.
    scale_edge = min(1.0, PLATE_INNER / W)
    scale_stroke = min(1.0, PLATE_INNER / (W + 60.0))
    boxes = [(_s, x0 + dx, y0 + dy, x1 + dx, y1 + dy) for _s, x0, y0, x1, y1 in boxes]
    strokes = [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), w) for a, b, w in strokes]

    def refuse_label(i: int, rule: str, msg: str):
        """A floater that still fails at the final scale gets the honest error — the author
        cannot 'move' a label finish() placed; only `_gap` or the geometry moves it."""
        el = owners[i]
        if el.get("_floater") is not None:
            raise TemplateError(
                f"{kind}: floating label {boxes[i][0]!r} was placed at {el['_floater']} but "
                f"fails {rule} at the final scale — raise _gap or widen the figure")
        raise TemplateError(msg)

    for i, (txt, x0, y0, x1, y1) in enumerate(boxes):
        edge = min(x0, y0, W - x1, H - y1) * scale_edge
        if edge < EDGE_PX + SLACK_EDGE:
            refuse_label(i, "the edge rule",
                         f"{kind}: label {txt!r} is ~{edge:.1f} rendered px from the canvas "
                         f"edge (needs {EDGE_PX}px + slack) — move it inward")
        worst = min(_seg_rect_dist(a, b, (x0, y0, x1, y1)) - w / 2 for a, b, w in strokes) if strokes else 99
        if worst * scale_stroke < STROKE_PX + SLACK_STROKE:
            refuse_label(i, "the stroke-clearance rule",
                         f"{kind}: label {txt!r} is ~{worst * scale_stroke:.1f} rendered px "
                         f"from stroke geometry (needs {STROKE_PX}px + slack) — move it clear")
    # labels must also clear EACH OTHER — two numerals on one wedge or a crowded number line
    # otherwise overlap silently until the render (needs ≥ 4 rendered px between boxes)
    for i in range(len(boxes)):
        _t1, ax0, ay0, ax1, ay1 = boxes[i]
        for j, (_t2, bx0, by0, bx1, by1) in enumerate(boxes[i + 1:], i + 1):
            gap = _rect_gap((ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1))
            if gap * scale_stroke < 4.0:
                k = i if owners[i].get("_floater") is not None else j
                refuse_label(k, "the label-gap rule",
                             f"{kind}: labels {_t1!r} and {_t2!r} are ~{gap * scale_stroke:.1f} "
                             f"rendered px apart (need 4) — move one clear")

    # own-anchor — a fixed label must sit nearer the anchor its claim names than any
    # OTHER anchor a label claim names (a letter nearer the wrong dot mislabels silently)
    named: dict[str, list[str]] = {}                     # anchor -> glyphs claimed for it
    for pred, _e, _n in claims:
        m = re.match(r'^label "(.+)" names (\S+)$', pred)
        if m and m.group(2) in anchors:
            named.setdefault(m.group(2), []).append(m.group(1))
    if named:
        centres: dict[str, list[tuple[XY, dict]]] = {}
        for i, (txt, x0, y0, x1, y1) in enumerate(boxes):
            centres.setdefault(txt, []).append((((x0 + x1) / 2, (y0 + y1) / 2), owners[i]))
        for target, glyphs in named.items():
            for g in glyphs:
                for (cx, cy), el in centres.get(g, []):
                    own = math.hypot(cx - anchors[target][0], cy - anchors[target][1])
                    other = min(((math.hypot(cx - anchors[o][0], cy - anchors[o][1]), o)
                                 for o in named if o != target), default=None)
                    if other and (other[0] - own) * scale_stroke < OWN_FIXED_PX:
                        if el.get("_floater") is not None:
                            raise TemplateError(
                                f"{kind}: floating label {g!r} was placed at "
                                f"{el['_floater']} but fails the own-anchor rule at the "
                                f"final scale — raise _gap or widen the figure")
                        raise TemplateError(
                            f"{kind}: label {g!r} is nearer anchor {other[1]} than its own "
                            f"{target} (~{other[0] * scale_stroke:.1f} vs "
                            f"{own * scale_stroke:.1f} rendered px, needs {OWN_FIXED_PX:g} "
                            f"clear) — move it or give it `_near` so finish() places it")

    for el in elements:                      # internal `_…` keys never reach the VDD doc —
        for key in [k for k in el if k.startswith("_")]:   # `_near`/`_gap`/`_floater`/`_region`
            del el[key]                                    # kept until now so the pre-flight
                                                           # could word floater refusals

    # 3. the claim set (audit-claim-set grammar; order is the corpus convention)
    # [A-Z]\d* — W11: bar-chart bar tops and other generated anchors may be digit-suffixed
    if points and any(not re.fullmatch(r"[A-Z]\d*", p) for p in points):
        raise TemplateError(f"{kind}: point names are capitals, optionally digit-suffixed "
                            f"— got {points}")
    drawn, math_labels = [], []
    for el in elements:
        if el["type"] == "math":
            # a math label's latex is NOT a claimable `labels:` glyph — it renders as a KaTeX
            # overlay, never a <text>, so vdd-check's coverage would fail it. It must instead
            # be declared in a claim's prose (a `describe` line) by its DISPLAY text.
            if isinstance(el.get("latex"), str):
                math_labels.append(el["latex"])
            continue
        s = el.get("value") if el["type"] == "text" else el.get("label")
        if isinstance(s, str):
            drawn.append(s)
    named_glyphs = set()
    for i, (pred, ev, note) in enumerate(claims, 1):
        if re.match(r'^label "(.+)" names (\S+)$', pred):
            g = re.match(r'^label "(.+)" names (\S+)$', pred).group(1)
            if g not in drawn:
                raise TemplateError(f"{kind}: claim K{i} binds label {g!r} that no element draws")
            named_glyphs.add(g)
    missing = [g for g in drawn if g not in named_glyphs]
    if missing:
        raise TemplateError(f"{kind}: drawn label(s) {missing} have no `label` claim")
    if math_labels:
        claim_blob = " ".join(f"{p} {n}" for p, _e, n in claims)
        unclaimed = [l for l in math_labels
                     if l not in claim_blob and
                     re.sub(r"\s+", " ", math_visible(l)).strip() not in claim_blob]
        if unclaimed:
            raise TemplateError(
                f"{kind}: math label(s) {unclaimed} have no claim — a math overlay cannot be a "
                f"`label` claim (it is not a <text>); declare it in a `describe`/`departures` "
                f"line by its display text")

    if ask is None:
        digits = re.search(r"\d+", figure_id)
        if not digits:
            raise TemplateError(
                f"{kind}: the default `ask` part '1' cannot bind to a digit-less figure_id "
                f"{figure_id!r} — the audit leaves the ask↔figure link unverifiable. Pass "
                f"ask=[[\"a\", \"…\"]] explicitly or a figure_id carrying the item number")
        ask = [(digits.group(0), f"the figure's stated facts for {kind}")]
    key_ids = [f"K{i}" for i, (pred, _, _2) in enumerate(claims, 1)
               if not pred.startswith(NON_KEY)]
    stem_line = " ".join(stem.split())
    q = lambda s: f'"{s}"' if not re.fullmatch(r"\S+", s) else s

    L: list[str] = [
        f"figure:   {figure_id} — {title or kind}",
        f"source:   constructed; frame is the figure's own canvas, {W} x {H}, y down; "
        f"built by vdd_templates.{kind}",
        "channel:  constructed",
        f"stem:     {stem_line}",
    ]
    for i, (ref, text) in enumerate(ask):
        L.append(f"{'ask:' if i == 0 else ' ' * 10:<10}{ref}  {text}")
    L.append(f"labels:   {' '.join(q(g) for g in drawn) or ''}")
    L.append(f"points:   {' '.join(points)}")
    L.append(f"segments: {' '.join(segments)}")
    L.append("anchors:")
    for p in points:
        if p in anchors:
            L.append(f"  {p} {anchors[p][0]:g} {anchors[p][1]:g}")
    def subst(pred: str) -> str:
        def rep(m):
            n = m.group(1)
            if n not in anchors:
                raise TemplateError(f"{kind}: claim @{n} names no anchor")
            return f"{anchors[n][0]:g} {anchors[n][1]:g}"
        return re.sub(r"@([A-Z]\d*)\b", rep, pred)

    L.append("claims:")
    for i, (pred, ev, note) in enumerate(claims, 1):
        L.append(f"  K{i}  {subst(pred)} | {ev} | {note}".rstrip())
    if budget is not None:
        L.append(f"budget:   {budget}")
    L += [f"scale:    {scale}", "load-bearing:"]
    for ref, _ in ask:
        L.append(f"  {ref} -> {', '.join(key_ids)}")
    L.append("unreadable: (none)")
    if ambiguous or contested:
        L.append("ambiguous:")
        L += [f"  {a}" for a in (ambiguous or [])]
        L += [f"  {k} — {why}" for k, why in (contested or [])]
    else:
        L.append("ambiguous:  (none)")
    if departures:
        L.append("departures:")
        L += [f"  {d}" for d in departures]
    else:
        L.append("departures: (none)")

    document = vc.doc(W, H, elements,
                      title=title or f"A {kind.replace('_', ' ')} figure",
                      description=description or f"A {kind.replace('_', ' ')} figure built from the stem's numbers.",
                      font_size=fs)
    return Built(figure_id=figure_id, doc=document, anchors=anchors, claims="\n".join(L) + "\n")


# ────────────────────────────────────────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────────────────────────────────────────
def _arange(a: float, b: float, step: float):
    v = a
    while v < b:
        yield v
        v += step


def _rect_gap(a, b) -> float:
    """Gap between two (x0, y0, x1, y1) boxes — 0 when they touch or overlap."""
    return math.hypot(max(0.0, b[0] - a[2], a[0] - b[2]),
                      max(0.0, b[1] - a[3], a[1] - b[3]))


def _num_exact(v: float) -> str:
    """A decimal literal that parses back to v exactly — `:g` truncates 8/3 to 2.66667,
    which fails the audit's `derive <expr> = <value>` check (tolerance 1e-9)."""
    return f"{v:g}" if float(f"{v:g}") == v else repr(v)


def _unused_letters(used: set[str], n: int) -> list[str]:
    pool = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in used]
    if len(pool) < n:
        raise TemplateError("out of single-capital point names")
    return pool[:n]


def _derive_backed(add, need: list[float], stem: str) -> dict[float, str]:
    """Emit `derive` claims so every value in `need` is STEM-BACKED: each emitted derive's
    literals are stem numbers, the constants {1, 2, 90, 180, 360}, or the value of an
    already-backed derive — the audit's own backing rule (2d), intermediates included.
    A value the stem states needs no derive and is skipped (the claim is justified directly);
    a bare constant like 90 still needs one — constants back LITERALS, not claims.
    The search plans first and emits only on success, so a dead end never leaves orphan
    derives behind. Returns {value: claim id}; unreachable → TemplateError."""
    nums = stem_numbers(stem)
    backed = set(nums) | {1.0, 2.0, 90.0, 180.0, 360.0}
    emitted: dict[float, str] = {}
    visiting: set[float] = set()

    def is_backed(v: float) -> bool:
        return any(abs(v - b) <= 1e-9 for b in backed)

    def solve(v: float, limit: int, depth: int = 0, force: bool = False) -> list | None:
        """Best plan of `derive` steps producing v — a list of (a, b, template, value) emitted
        in order — or None. Operands of each step are backed or produced by earlier steps.
        `force` asks for a derive even when v is already a backed constant (a claim can only
        cite a stem number or a derive — a bare constant justifies a LITERAL only)."""
        if is_backed(v) and not force:
            return []
        if depth >= limit or v <= 0 or not math.isfinite(v) or v in visiting:
            return None
        visiting.add(v)
        try:
            cands = []
            for a in sorted(backed):
                for b, t in ((v - a, "{a} + {b}"), (a - v, "{a} - {b}"), (v + a, "{b} - {a}"),
                             (v / a if a else None, "{a} * {b}"),
                             (a / v if v else None, "{a} / {b}"), (v * a, "{b} / {a}")):
                    # b = v is refused — `derive 1 * v = v` cites its own value (never backed)
                    if b is None or not math.isfinite(b) or b <= 0 or abs(b - v) <= 1e-9:
                        continue
                    cands.append((a, b, t))
            # prefer +/− over a bare `a * 1`/`a / 1` restatement, and avoid v as a literal
            op_pref = {"{a} + {b}": 0, "{a} - {b}": 0, "{b} - {a}": 0,
                       "{a} / {b}": 1, "{b} / {a}": 1, "{a} * {b}": 2}
            direct = [c for c in cands if is_backed(c[1])]
            if direct:
                a, b, t = min(direct, key=lambda c: (abs(c[0] - v) <= 1e-9,
                                                     op_pref[c[2]], c[1], c[0]))
                return [(a, b, t, v)]
            best = None

            def rank(plan):
                # fewest non-integer intermediates (0.0222 is junk next to 45), then fewest
                # steps, then ± before */, then smallest intermediates
                inter = [s[3] for s in plan[:-1]]
                bad = sum(not x.is_integer() for x in inter) + sum(x > 360 for x in inter)
                return (bad, len(plan), op_pref[plan[-1][2]],
                        tuple(sorted(inter, reverse=True)))

            for c in cands:
                sub = solve(c[1], limit, depth + 1)
                if sub is None:
                    continue
                plan = sub + [c + (v,)]
                if best is None or rank(plan) < rank(best):
                    best = plan
            return best
        finally:
            visiting.discard(v)

    for v in need:
        if _has_stem(nums, v) or any(abs(v - k) <= 1e-9 for k in emitted):
            continue
        plan = next((p for lim in (1, 2, 3) if (p := solve(v, lim, force=True)) is not None),
                    None)
        if plan is None:
            raise TemplateError(
                f"cannot express {v:g} from the stem's numbers "
                f"({', '.join(f'{n:g}' for n in nums)}) and the constants 1, 2, 90, 180, 360 "
                f"— pass a stem number or a reachable value")
        for a, b, t, val in plan:
            if any(abs(val - k) <= 1e-9 for k in emitted):
                continue
            cid = add(f"derive {t.format(a=f'{a:g}', b=f'{b:g}')} = {val:g}", "inferred",
                      "construction arithmetic — stem numbers and the constants "
                      "1, 2, 90, 180, 360")
            backed.add(val)
            emitted[val] = cid
    return emitted


# ────────────────────────────────────────────────────────────────────────────────
# Points inside/outside regions — for hand-drawn figures (circles holding dots)
# ────────────────────────────────────────────────────────────────────────────────
def on_circle_point(centre: XY, r: float, deg: float) -> XY:
    """A point ON a circle — the cookbook's polar convention (0° = east, y down, so
    90° points DOWN on the canvas). Pair with a `circle centre X radius r` claim."""
    return vc.polar(centre, r, deg)


def region_point(circles: dict[str, tuple[XY, float]], inside: list[str], outside: list[str],
                 prefer: XY, margin: float = 15.0, avoid: list[XY] = (),
                 min_sep: float = 30.0, step: float = 2.0) -> XY:
    """The point nearest `prefer` ON THE FIRST expanding Chebyshev ring (outward at `step`
    resolution) that holds any valid point — nearest within that ring, not globally
    nearest. Valid = ≥`margin` inside every `inside` circle, ≥`margin` outside every
    `outside` circle and ≥`min_sep` from every `avoid` point. No valid point within 400
    units → TemplateError. Pure geometry — no elements, same canvas frame as the doc."""
    for n in (*inside, *outside):
        if n not in circles:
            raise TemplateError(f"region_point: unknown circle {n!r} — known: {sorted(circles)}")

    def ok(x: float, y: float) -> bool:
        for n in inside:
            (cx, cy), r = circles[n]
            if math.hypot(x - cx, y - cy) > r - margin:
                return False
        for n in outside:
            (cx, cy), r = circles[n]
            if math.hypot(x - cx, y - cy) < r + margin:
                return False
        return all(math.hypot(x - ax, y - ay) >= min_sep for ax, ay in avoid)

    px, py = float(prefer[0]), float(prefer[1])
    k = 0
    while k * step <= 400.0:
        if k == 0:
            ring = [(px, py)]
        else:
            r_ = k * step
            ring = [(px + i * step, py - r_) for i in range(-k, k + 1)] + \
                   [(px + i * step, py + r_) for i in range(-k, k + 1)] + \
                   [(px - r_, py + i * step) for i in range(-k + 1, k)] + \
                   [(px + r_, py + i * step) for i in range(-k + 1, k)]
        best = None
        for x, y in ring:
            if ok(x, y):
                d = math.hypot(x - px, y - py)
                if best is None or d < best[0]:
                    best = (d, x, y)
        if best:
            return (vc.r2(best[1]), vc.r2(best[2]))
        k += 1
    raise TemplateError(
        f"region_point: no spot within 400 units of {prefer} that is inside {inside}, "
        f"outside {outside} and {min_sep:g} from {len(avoid)} point(s) — widen the geometry")


def membership_claims(name: str, point: XY, circles: dict[str, tuple[XY, float]],
                      ) -> list[tuple[str, str, str]]:
    """The `describe` claim tuple(s) recording which of `circles` `point` lies in/on/out
    of — 'on the X circle' within ON_TOL of the outline, else inside/outside by side.
    The words are decided by the point's actual side; the margin region_point placed it
    with belongs to that call, not to this claim."""
    words = []
    for cname, (c, r) in circles.items():
        d = math.hypot(point[0] - c[0], point[1] - c[1])
        if abs(d - r) <= ON_TOL:
            words.append(f"on the {cname} circle")
        elif d < r:
            words.append(f"inside the {cname} circle")
        else:
            words.append(f"outside the {cname} circle")
    return [(f'describe "{name} lies {" and ".join(words)}"',
             "inferred", "the point's drawn position")]


# ────────────────────────────────────────────────────────────────────────────────
# 1. grid_polygon — a closed rectilinear polygon on a cm grid
# ────────────────────────────────────────────────────────────────────────────────
def build_grid_polygon(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                       cell, vertices, cols=None, rows=None, cell_px=30.0,
                       vertex_labels=False, shade=True):
    vc.reset_ids()
    require_stem(stem, cell=cell)
    verts = [tuple(map(float, v)) for v in vertices]
    if len(verts) < 3:
        raise TemplateError("grid_polygon: need at least 3 vertices")
    for i, (x, y) in enumerate(verts):
        if abs(x - round(x)) > 1e-9 or abs(y - round(y)) > 1e-9:
            raise TemplateError(f"grid_polygon: vertex {v} is off the grid lattice")
        nx, ny = verts[(i + 1) % len(verts)]
        if not (abs(x - nx) < 1e-9 or abs(y - ny) < 1e-9):
            raise TemplateError(
                f"grid_polygon: edge {verts[i]}→{(nx, ny)} is not rectilinear — only "
                f"axis-aligned edges on the grid")
    cols = cols or int(max(x for x, _ in verts)) + 1
    rows = rows or int(max(y for _, y in verts)) + 1
    names = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: len(verts)])
    pts = {n: (x * cell_px, y * cell_px) for n, (x, y) in zip(names, verts)}
    elements: list[dict] = []
    if shade:
        elements.append(vc.polygon(list(pts.values()), fill=vc.SHADE, stroke_width=0, id="fill"))
    for c in range(cols + 1):
        elements.append({"id": f"gv{c}", "type": "line",
                         "points": [[c * cell_px, 0], [c * cell_px, rows * cell_px]],
                         "stroke": {"color": "#d1d5db", "width": 1}})
    for r in range(rows + 1):
        elements.append({"id": f"gh{r}", "type": "line",
                         "points": [[0, r * cell_px], [cols * cell_px, r * cell_px]],
                         "stroke": {"color": "#d1d5db", "width": 1}})
    for a, b in zip(names, names[1:] + names[:1]):
        elements.append(vc.line(pts[a], pts[b], id=f"{a}{b}", width=2.5))
    if vertex_labels:
        # a vertex label seats on the corner's EXTERIOR bisector: for a convex corner that is
        # the diagonal away from the polygon; for a reflex corner it is the notch. Seats
        # inside the grid are impossible — a capital's box (~11x22 units) cannot clear the
        # 30-unit grid lines AND the two meeting edges at once — so the search only ever
        # succeeds when the exterior wedge runs out of the grid, and an interior corner
        # (reflex, or a convex corner whose outside is grid-covered) is refused up front
        # rather than left for the generic label pre-flight to find.
        signed = sum(verts[i][0] * verts[(i + 1) % len(verts)][1]
                     - verts[(i + 1) % len(verts)][0] * verts[i][1]
                     for i in range(len(verts)))
        strokes_now = stroke_segments(elements)
        seated: list = []
        for i, (n, v) in enumerate(pts.items()):
            pv = tuple(c * cell_px for c in verts[i - 1])
            nv = tuple(c * cell_px for c in verts[(i + 1) % len(verts)])
            e1 = vc.unit(v, pv)
            e2 = vc.unit(v, nv)
            bx, by = e1[0] + e2[0], e1[1] + e2[1]
            if math.hypot(bx, by) < 1e-9:
                raise TemplateError(f"grid_polygon: vertex {n} is straight, not a corner — "
                                    "drop the doubled vertex")
            bx, by = bx / math.hypot(bx, by), by / math.hypot(bx, by)
            # turn sign vs the polygon's signed area tells convex from reflex: the bisector
            # already points at the labelable wedge — the notch for a reflex corner, the
            # interior for a convex one — so convex labels go the opposite way
            cross = (v[0] - pv[0]) * (nv[1] - v[1]) - (v[1] - pv[1]) * (nv[0] - v[0])
            if cross * signed > 0:                      # convex: opposite the interior
                bx, by = -bx, -by
            w_ = _label_width(n, FS)
            h_ = (MID_UP + POINT_LABEL_DOWN) * FS       # capitals carry no descender
            seat = None
            # beyond ~40 units the box's near edge lands >1.5·fontSize from the vertex —
            # visual-metrics' target rule would fail it even if the seat is clear. The fan
            # off the bisector finds seats like "above the top edge, shy of the corner"
            # when the grid's spare row/column hems the diagonal.
            for off in (0.0, -15.0, 15.0, -30.0, 30.0, -45.0, 45.0, -60.0, 60.0,
                        -75.0, 75.0):
                dx_, dy_ = (bx * math.cos(math.radians(off)) - by * math.sin(math.radians(off)),
                            bx * math.sin(math.radians(off)) + by * math.cos(math.radians(off)))
                for r_ in _arange(26.0, 40.0, 2.0):
                    cx_, cy_ = v[0] + dx_ * r_, v[1] + dy_ * r_
                    box_ = (cx_ - w_ / 2, cy_ - h_ / 2, cx_ + w_ / 2, cy_ + h_ / 2)
                    if min(_seg_rect_dist(a, b, box_) - w2 / 2
                           for a, b, w2 in strokes_now) >= 12.0 and \
                            all(_rect_gap(box_, pb) >= 8.0 for pb in seated):
                        seat = (cx_, cy_)
                        break
                if seat:
                    break
            if seat is None:
                raise TemplateError(
                    f"grid_polygon: vertex {n}'s label has no seat within reach that clears "
                    f"the edges and grid lines — drop vertex_labels for this shape")
            cx_, cy_ = seat
            seated.append((cx_ - w_ / 2, cy_ - h_ / 2, cx_ + w_ / 2, cy_ + h_ / 2))
            # point labels anchor top-left-ish: box = at + offset, y pulled up by MID_UP·size
            ox = cx_ - w_ / 2 - v[0]
            oy = cy_ - v[1] + FS * (MID_UP - POINT_LABEL_DOWN) / 2
            elements.append({"id": f"lbl{n}", "type": "point", "at": vc.P(v), "r": 0,
                             "label": n, "labelOffset": [vc.r2(ox), vc.r2(oy)]})
    gx, gy = _unused_letters(set(names), 2)
    anchors = dict(pts)
    anchors[gx], anchors[gy] = (0.0, 0.0), (cols * cell_px, rows * cell_px)
    gpoints = names + [gx, gy]
    segments = [f"{a}{b}" for a, b in zip(names, names[1:] + names[:1])]

    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    add(f"grid {rows} by {cols} over {gx} {gy}", "inferred",
        f"a {rows}x{cols} grid of {cell:g}-unit squares — the stem's {cell:g}")
    for i, n in enumerate(names):
        add(f"right {names[i - 1]} {n} {names[(i + 1) % len(names)]}", "inferred",
            "every corner of a rectilinear polygon on a square grid")
    fwd = sum(x * verts[(i + 1) % len(verts)][1] for i, (x, _y) in enumerate(verts))
    rev = sum(verts[(i + 1) % len(verts)][0] * y for i, (_x, y) in enumerate(verts))
    s1 = " + ".join(f"{int(x)}*{int(verts[(i + 1) % len(verts)][1])}"
                    for i, (x, _y) in enumerate(verts))
    s2 = " + ".join(f"{int(verts[(i + 1) % len(verts)][0])}*{int(y)}"
                    for i, (_x, y) in enumerate(verts))
    big, small = (s1, s2) if fwd >= rev else (s2, s1)
    add(f"derive ( {big} - ( {small} ) ) / 2 = {abs(fwd - rev) / 2:g}", "inferred",
        "shoelace over the grid vertices — the area in squares")
    per = [vc.dist(verts[i], verts[(i + 1) % len(verts)]) for i in range(len(verts))]
    add(f"derive {' + '.join(f'{p:g}' for p in per)} = {sum(per):g}", "inferred",
        "the side lengths counted in grid units — the perimeter")
    if vertex_labels:
        for n in names:
            add(f'label "{n}" names {n}', "inferred", "vertex label")
    add("none tickMark parallelMark angleMark arrow dashed", "inferred",
        "plain outline strokes on a light grid")
    return finish(kind="grid_polygon", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=gpoints, segments=segments, claims=claims, ask=ask,
                  title=title or f"A closed rectilinear shape on a grid of {cell:g}-unit squares",
                  description=description or (
                      f"A closed rectilinear polygon drawn on a grid of {cell:g}-unit squares; "
                      f"{len(verts)} vertices, all corners right angles."),
                  scale="to scale — vertices sit on the grid lattice, one square is one unit", medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 2. shaded_grid — a rectangle of unit squares, some fully and some half shaded
# ────────────────────────────────────────────────────────────────────────────────
def build_shaded_grid(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                      cols, rows, full=(), half=(), cell_px=40.0):
    vc.reset_ids()
    nums = stem_numbers(stem)
    if not (_has_stem(nums, cols) and _has_stem(nums, rows) or _has_stem(nums, cols * rows)):
        raise TemplateError(
            f"shaded_grid: neither cols={cols} and rows={rows} nor their product {cols * rows} "
            f"is stated by the stem (stem numbers {', '.join(f'{n:g}' for n in nums)})")
    full = {tuple(f) for f in full}
    half = [tuple(h) for h in half]
    cells = set(full) | {(c, r) for c, r, _ in half}
    for c, r in cells:
        if not (0 <= c < cols and 0 <= r < rows):
            raise TemplateError(f"shaded_grid: cell ({c},{r}) is outside a {cols}x{rows} grid")
    if len(cells) != len(full) + len(half):
        raise TemplateError("shaded_grid: a cell is listed as both full and half shaded")
    elements: list[dict] = []
    s = cell_px
    for c, r in sorted(full):
        elements.append({"id": f"full{c}{r}", "type": "rect", "x": c * s, "y": r * s,
                         "width": s, "height": s, "fill": {"color": vc.SHADE},
                         "stroke": {"width": 0}})
    CORNER = {"tl": (0, 0), "tr": (1, 0), "bl": (0, 1), "br": (1, 1)}
    for i, (c, r, corner) in enumerate(half):
        if corner not in CORNER:
            raise TemplateError(f"shaded_grid: half cell ({c},{r}) corner {corner!r} — one of tl,tr,bl,br")
        x, y = c * s, r * s
        cx, cy = CORNER[corner]
        # the shaded triangle is THREE points: the named right-angle corner plus its two
        # EDGE-adjacent cell corners (the diagonally opposite corner is not part of it).
        # The diagonal joins the two adjacent corners — it is the triangle's hypotenuse.
        corner_pt = (x + cx * s, y + cy * s)
        adj = [(x + px * s, y + py * s) for k, (px, py) in CORNER.items()
               if (px == cx) != (py == cy)]
        elements.append(vc.polygon([corner_pt] + adj, fill=vc.SHADE, stroke_width=0,
                                   id=f"half{i}"))
        elements.append(vc.line(adj[0], adj[1], id=f"diag{i}", width=1.5))
    for c in range(1, cols):
        elements.append(vc.line((c * s, 0), (c * s, rows * s), id=f"gv{c}", width=1))
    for r in range(1, rows):
        elements.append(vc.line((0, r * s), (cols * s, r * s), id=f"gh{r}", width=1))
    frame = [(0, 0), (cols * s, 0), (cols * s, rows * s), (0, rows * s)]
    elements.append(vc.polygon(frame, id="frame"))
    gnames = _unused_letters(set(), 4)
    anchors = {n: p for n, p in zip(gnames, frame)}
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    add(f"grid {rows} by {cols} over {gnames[0]} {gnames[2]}", "stem",
        f"the stem's {cols * rows:g} squares ({cols} by {rows})")
    add(f"shaded {len(full)} of {cols * rows} cells", "inferred",
        "the fully shaded cells; the halves are described next")
    for c, r, corner in half:
        add(f'describe "cell ({c},{r}) is half shaded, the {corner} corner triangle"',
            "inferred", "a cell cut by a diagonal")
    add(f"derive {len(full)} + {len(half)} / 2 = {len(full) + len(half) / 2:g}", "inferred",
        "full cells plus half cells over two — the shaded area in squares")
    add("none tickMark parallelMark angleMark arrow dashed", "inferred", "a filled grid only")
    segs = [f"{a}{b}" for a, b in zip(gnames, gnames[1:] + gnames[:1])]
    elements_n = len(elements)
    return finish(kind="shaded_grid", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=gnames, segments=segs, claims=claims, ask=ask,
                  title=title or f"A {cols} by {rows} rectangle of squares, some shaded",
                  description=description or (
                      f"A rectangle of {cols * rows} equal squares ({cols} by {rows}); "
                      f"{len(full)} fully shaded and {len(half)} cut by a diagonal with one "
                      f"half shaded."),
                  scale="to scale — every cell is one unit square",
                  budget=elements_n if elements_n > 32 else None,
                  departures=([f"{elements_n} elements — one rect per shaded cell plus one line "
                               "per interior grid line is the honest drawing (S6b §3.4)"]
                              if elements_n > 32 else None), medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 3. rays_from_point — bearings from a centre O, a north arrow, numbered angle arcs
# ────────────────────────────────────────────────────────────────────────────────
def build_rays_from_point(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                          rays: dict, centre="O", ray_len=110.0, north_arrow=True,
                          north_label="N", angles=(), arc_r=34.0):
    vc.reset_ids()
    nums = stem_numbers(stem)
    bearings: dict[str, float] = {}
    for name, b in rays.items():
        if isinstance(b, str):
            if b.upper() not in COMPASS:
                raise TemplateError(f"rays_from_point: bearing {b!r} is not a compass point")
            bearings[name] = COMPASS[b.upper()]
        else:
            require_stem(stem, **{f"bearing {name}": float(b)})
            bearings[name] = float(b) - 90.0          # numeric bearings are clockwise from N
    if len(bearings) < 2:
        raise TemplateError("rays_from_point: need at least two rays")
    for tok in re.findall(r"\d+(?:\.\d+)?", north_label):
        require_stem(stem, **{f"north label {north_label!r}": float(tok)})
    O = (0.0, 0.0)
    tips = {n: vc.polar(O, ray_len, deg) for n, deg in bearings.items()}
    elements: list[dict] = []
    anchors: dict[str, XY] = {centre: O}
    for n, deg in bearings.items():
        elements.append(vc.line(O, tips[n], id=f"{centre}{n}"))
        anchors[n] = tips[n]
        # the point label sits just outside the tip, away from the centre
        ux, uy = vc.unit(O, tips[n])
        # a left-bound label needs its box to END left of the tip (align is always `start`)
        off = [vc.r2(14 if ux >= -0.3 else -26), vc.r2(uy * 16 - (6 if uy >= 0 else -6))]
        elements.append({"id": f"lbl{n}", "type": "point", "at": vc.P(tips[n]), "r": 0,
                         "label": n, "labelOffset": off})
    if north_arrow:
        ax = max(p[0] for p in tips.values()) + 46
        elements.append({"id": "north", "type": "arrow", "head": "end",
                         "points": [[ax, 8.0], [ax, -38.0]], "headSize": 12})
        elements.append(vc.text((ax, -60.0), north_label, id="lblN", size=16))
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    # angle values first: every marked angle's size must be backed (constants + stem)
    specs = []
    for i, spec in enumerate(angles):
        a, b = spec[0], spec[1]
        label = spec[2] if len(spec) > 2 else str(i + 1)
        reflex = bool(spec[3]) if len(spec) > 3 else False
        if a not in bearings or b not in bearings:
            raise TemplateError(f"rays_from_point: angle {spec} names an unknown ray")
        d = _sweep_delta(bearings[a], bearings[b], "ccw" if reflex else None)
        v = abs(d)
        specs.append((a, b, label, reflex, v))
    backed = _derive_backed(add, sorted({v for *_, v in specs}), stem)
    if not backed:
        # a constructed claim set needs at least one `derive` — with no marked angles there
        # is nothing to back, so state the compass's own arithmetic (all canonical constants)
        add("derive 360 / 90 = 4", "inferred",
            "the full turn about the centre divides into four quarter-turns")
    arcs = []
    for i, (a, b, label, reflex, v) in enumerate(specs):
        # the 26-unit ladder leaves room for a numeral INSIDE its own arc — a numeral may
        # never sit beyond a LARGER arc covering its wedge, and adjacent arcs are too thin
        # a band to hold one anyway (lead review: numeral 2 read as labelling the reflex arc)
        r = arc_r + i * 26
        start, end = bearings[a], bearings[b]
        el = {"id": f"arc{i + 1}", "type": "arc", "center": [0, 0], "r": r,
              "start": vc.r2(start), "end": vc.r2(end)}
        if reflex:
            el["sweep"] = "ccw"
        elements.append(el)
        arcs.append((start, _sweep_delta(start, end, "ccw" if reflex else None), r))

    def _covers(start, delta, th) -> bool:
        """Is direction `th` inside the arc's drawn sweep?"""
        rel = (th - start) % 360.0
        return rel <= delta + 1e-9 if delta >= 0 else rel >= 360.0 + delta - 1e-9

    placed_boxes: list = []       # text labels already seated — they are not strokes, so
    #                             # the segment-distance check alone misses them (a numeral
    #                             # and the centre label once landed in the same spot)

    def place(text_, near_bis, own_r) -> tuple[float, float]:
        """A numeral's box must clear the rays AND every arc — and it must never sit BEYOND a
        larger arc covering its wedge (a numeral past the reflex arc reads as labelling the
        reflex, not its own angle). So the label sits INSIDE its own arc, or between it and
        the next larger arc covering that direction (no larger arc → unbounded outward)."""
        w_ = _label_width(text_, FS)
        half = max(w_, FS * (MID_UP + MID_DOWN)) / 2 + 6.0  # box half-extent + a clear arc gap
        for th in [near_bis, near_bis - 12, near_bis + 12, near_bis - 24, near_bis + 24]:
            cap = min((rj for sj, dj, rj in arcs if rj > own_r and _covers(sj, dj, th)),
                      default=math.inf)
            for d in _arange(14.0, ray_len + 36.0, 2.0):
                in_band = (d + half <= own_r) or (d - half >= own_r and d + half <= cap)
                if not in_band:
                    continue
                px, py = vc.polar(O, d, th)
                box = (px - w_ / 2, py - FS * MID_UP, px + w_ / 2, py + FS * MID_DOWN)
                if min(_seg_rect_dist(a, b, box) - w2 / 2
                       for a, b, w2 in stroke_segments(elements)) >= 11.0 and \
                        all(_rect_gap(box, pb) >= 8.0 for pb in placed_boxes):
                    placed_boxes.append(box)
                    return px, py
        raise TemplateError(f"rays_from_point: angle label {text_!r} cannot be placed clear "
                            "of the arcs — widen the ray spacing")

    for i, (a, b, label, reflex, v) in enumerate(specs):
        start, sweep, r = arcs[i]
        lx, ly = place(label, start + sweep / 2, r)
        elements.append(vc.text((lx, ly), label, id=f"num{i + 1}"))
        cite = f", per derive {backed[v]}" if v in backed else ""
        if reflex:
            add(f'describe "angle {label} is the reflex angle from {centre}{a} to {centre}{b}, '
                f'{v:g} degrees"', "inferred", f"360 minus the smaller angle{cite}")
        else:
            add(f"angle {a} {centre} {b} = {v:g}", "inferred", f"the marked angle {label}{cite}")
        add(f'label "{label}" names angle{label}', "inferred", f"the marked angle {label}")
    # O's label goes on a gap bisector at the SMALLEST radius that still clears the rays and
    # every angle arc — inside a narrow wedge a label fits either tight inside the innermost
    # arc or past it; a fixed offset cannot know which, so search the space (canvas units).
    degs = sorted(bearings.values())
    gaps = sorted(((degs[(i + 1) % len(degs)] - degs[i]) % 360, degs[i])
                  for i in range(len(degs)))
    w_lab = _label_width(centre, FS)
    placed = None
    for gap_w, gap_lo in reversed(gaps):                # widest gap first
        bis = gap_lo + gap_w / 2
        for d in _arange(12.0, ray_len + 42.0, 2.0):
            px, py = vc.polar(O, d, bis)
            box = (px, py - FS * MID_UP, px + w_lab, py + FS * MID_DOWN)
            worst = min(_seg_rect_dist(a, b, box) - w2 / 2
                        for a, b, w2 in stroke_segments(elements))
            if worst >= 11.0 and all(_rect_gap(box, pb) >= 8.0 for pb in placed_boxes):
                placed = (vc.r2(px), vc.r2(py))
                placed_boxes.append(box)
                break
        if placed:
            break
    if not placed:
        raise TemplateError("rays_from_point: no gap between the rays can hold the centre "
                            "label clear of the arcs — widen the ray spacing")
    elements.append({"id": f"lbl{centre}", "type": "point", "at": vc.P(O), "r": 0,
                     "label": centre, "labelOffset": list(placed)})
    for n in bearings:
        add(f'label "{n}" names {n}', "stem", "a named ray endpoint")
    add(f'label "{centre}" names {centre}', "stem", "the centre point")
    if north_arrow:
        add(f'label "{north_label}" names north', "stem", "the north arrow's label")
        add('describe "a north arrow points up the page"', "inferred", "orientation reference")
    add("none tickMark parallelMark shaded dashed", "inferred",
        "rays, a north arrow and angle arcs only")
    segs = [f"{centre}{n}" for n in bearings]
    points = [centre] + list(bearings)
    return finish(kind="rays_from_point", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=points, segments=segs, claims=claims, ask=ask,
                  title=title or f"{len(bearings)} rays from point {centre} with marked angles",
                  description=description or (
                      f"{len(rays)} rays run from the centre point {centre} to "
                      + ", ".join(bearings)
                      + ", each at a different compass bearing"
                      + ("; a north arrow marks the top of the page" if north_arrow else "")
                      + (", and the angles between the rays are marked "
                         + " ".join(str(lbl) for _a, _b, lbl, _r, _v in specs)
                         if specs else "")
                      + "."),
                  scale="to scale — bearings are compass-true", medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 4. number_line — a subdivided scale with marked points
# ────────────────────────────────────────────────────────────────────────────────
# numeral steps a reader expects, nicest-first: the 1·2·5 decades plus the 25s
# (60 65 70 …, 730 735 740 …) — never the smallest fitting divisor, which labels
# 60 63 66 … 90 and lands on no round ten
_NICE_STEPS = sorted({m * 10 ** e for e in range(4) for m in (1, 2, 5)}
                     | {25 * 10 ** e for e in range(3)})


def build_number_line(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                      v0, v1, parts_per_unit, points=None, unit_px=None, overhang=30.0):
    vc.reset_ids()
    require_stem(stem, v0=v0, v1=v1, parts_per_unit=parts_per_unit)
    if not (v1 > v0 and isinstance(parts_per_unit, int) and parts_per_unit >= 1):
        raise TemplateError("number_line: need v1 > v0 and a positive integer parts_per_unit")
    if not (float(v0).is_integer() and float(v1).is_integer()):
        raise TemplateError("number_line: the axis endpoints must be integers (the `tick … step 1` "
                            "claim draws a numeral at every integer)")
    marks = {n: float(v) for n, v in (points or {}).items()}
    for n, v in marks.items():
        if not re.fullmatch(r"[A-Z]", n):
            raise TemplateError(f"number_line: point name {n!r} is not a single capital")
        if not (v0 <= v <= v1):
            raise TemplateError(f"number_line: point {n}={v:g} is outside the axis [{v0:g}, {v1:g}]")
        k = v * parts_per_unit
        if abs(k - round(k)) > 1e-9:
            raise TemplateError(
                f"number_line: point {n}={v:g} is not on the 1/{parts_per_unit} lattice "
                f"(off by {abs(k - round(k)):g} of a part)")
    unit_px = unit_px or min(90.0, 340.0 / (v1 - v0))
    span_v = v1 - v0
    n_units = int(round(span_v))
    axis_y = 0.0
    x_of = lambda v: (v - v0) * unit_px                    # noqa: E731
    # the audit requires the numeric labels to be EXACTLY the `tick` step's arithmetic
    # sequence — so when the pitch shrinks enough that adjacent numeral boxes would crowd
    # (render <4 px apart), label every k-th integer that divides the span, and claim that
    est_span = span_v * unit_px + 2 * overhang + 12
    num_gap = _clearance_units(4.0, est_span)
    wlab = max(_label_width(f"{v:g}", 16) for v in (v0, v1, v0 + 1))
    fits = lambda k: n_units % k == 0 and k * unit_px >= wlab + num_gap   # noqa: E731
    num_step = next((k for k in _NICE_STEPS if fits(k)), None)
    if num_step is None:                                # no nice divisor fits
        num_step = next((k for k in range(1, n_units + 1) if fits(k)), n_units)
    elements: list[dict] = []
    elements.append({"id": "axis", "type": "arrow", "head": "both",
                     "points": [[-overhang, axis_y], [span_v * unit_px + overhang, axis_y]]})
    for i in range(int(round(span_v * parts_per_unit)) + 1):
        v = v0 + i / parts_per_unit
        x = x_of(v)
        if abs(v - round(v)) < 1e-9:                        # an integer: major tick + numeral
            elements.append(vc.line((x, axis_y - 11), (x, axis_y + 11), id=f"tk{i}", width=2))
            if (i // parts_per_unit) % num_step == 0:
                # 40 = tick bottom (11) + the DOM label box's taller TOP extent (MID_UP·16)
                # + clearance — measured middle-baseline boxes reach 0.7·size above the anchor
                elements.append(vc.text((x, axis_y + 40), f"{round(v):g}", id=f"num{i}", size=16))
        elif parts_per_unit % 2 == 0 and abs(v - math.floor(v) - 0.5) < 1e-9:
            elements.append(vc.line((x, axis_y - 7), (x, axis_y + 7), id=f"tk{i}", width=1.5))
        else:
            elements.append(vc.line((x, axis_y - 4), (x, axis_y + 4), id=f"tk{i}", width=1))
    anchors: dict[str, XY] = {}
    u, vv = _unused_letters(set(marks), 2)
    anchors[u] = (x_of(v0), axis_y)
    anchors[vv] = (x_of(v1), axis_y)
    # the point label sits in a pinched window: its box bottom — POINT_LABEL_DOWN·FS below the
    # anchor, the real DOM reach of a lone capital (the text-run MID_DOWN overstates it, and the
    # extra lift pushed point→label past the target bound) — must clear the tick's top stroke
    # edge (11 + half its 2-unit stroke) by 6 px + slack ON THE RENDER, while the point→box
    # distance stays inside visual-check's target rule: 1.5 × fontSize from the named point.
    est_span = span_v * unit_px + 2 * overhang + 12
    mark_off = 12.0 + POINT_LABEL_DOWN * FS + _clearance_units(STROKE_PX + SLACK_STROKE, est_span)
    if mark_off - 0.5 * FS > 1.5 * FS:   # target bound on the measured DOM reach (~0.5·size)
        raise TemplateError(f"number_line: the stroke-cleared point-label lift puts the label "
                            f"~{mark_off - 0.5 * FS:.1f} units from its point (> {1.5 * FS:g} = "
                            f"1.5×fontSize {FS:g}) — the range is too wide for one canvas")
    for n, v in marks.items():
        anchors[n] = (x_of(v), axis_y)
        elements.append({"id": f"dot{n}", "type": "point", "at": vc.P((x_of(v), axis_y)), "r": 3,
                         "label": n, "labelOffset": [0, -vc.r2(mark_off)]})
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    add(f"axis {u}{vv} from {v0:g} to {v1:g}", "stem", f"the stem's {v0:g} to {v1:g}")
    add(f"tick {u}{vv} step {num_step}", "stem",
        "a numeral at every integer" if num_step == 1 else
        f"numerals every {num_step} integers — closer would crowd at this canvas width")
    for n, v in marks.items():
        add(f"at {v:g} @{n}", "inferred",
            f"{n} sits on the {'integer' if float(v).is_integer() else 'minor'} tick for {v:g}")
    add(f"derive 1 / {parts_per_unit} = {1 / parts_per_unit:g}", "stem",
        f"each unit divides into the stem's {parts_per_unit} equal parts")
    for i in range(0, n_units + 1, num_step):
        add(f'label "{v0 + i:g}" names {v0 + i:g}', "stem", "the numeral under the major tick")
    for n in marks:
        add(f'label "{n}" names {n}', "stem", "a marked point")
    add("none tickMark parallelMark angleArc shaded", "inferred",
        "the axis carries an arrowhead — nothing else")
    points_all = [u, vv] + list(marks)
    elements_n = len(elements)
    return finish(kind="number_line", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=points_all, segments=[f"{u}{vv}"], claims=claims,
                  ask=ask,
                  title=title or f"A number line from {v0:g} to {v1:g} divided into tenths",
                  description=description or (
                      f"A number line marked from {v0:g} to {v1:g}, each unit divided into "
                      f"{parts_per_unit} equal parts" +
                      (", with " + ", ".join(f"{n} marked" for n in marks) if marks else "") + "."),
                  scale="to scale — the axis is a true linear map",
                  budget=elements_n if elements_n > 32 else None,
                  departures=([f"{elements_n} elements — one short line per minor tick is the "
                               "honest drawing (S6b §3.4)"] if elements_n > 32 else None), medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 5. pictograph — rows of identical symbols (+ halves), a key row below a separator
# ────────────────────────────────────────────────────────────────────────────────
def build_pictograph(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                     per_symbol, rows, r=11.0, gap=28.0):
    vc.reset_ids()
    require_stem(stem, per_symbol=per_symbol)
    if not rows:
        raise TemplateError("pictograph: at least one row")
    if len({l for l, _ in rows}) != len(rows):
        raise TemplateError("pictograph: duplicate row labels — each row names a distinct category")
    for label, _ in rows:
        for tok in re.findall(r"\d+(?:\.\d+)?", str(label)):
            require_stem(stem, **{f"row label {label!r}": float(tok)})
    for label, count in rows:
        if not isinstance(count, (int, float)) or count <= 0:
            raise TemplateError(f"pictograph: row {label!r} count {count} is not positive")
        sym = count / per_symbol
        if abs(sym - round(sym)) > 1e-9 and not (per_symbol % 2 == 0 and
                                                 abs(sym * 2 - round(sym * 2)) < 1e-9):
            raise TemplateError(
                f"pictograph: row {label!r} count {count} is {sym:g} symbols — only whole "
                f"symbols or halves (count a multiple of {per_symbol:g} or of {per_symbol / 2:g})")
    label_w = max(_label_width(str(l), 16) for l, _ in rows)
    # the label box must clear the first symbol by 6 px + slack ON THE RENDER — a fixed
    # unit gap shrinks under the narrow-surface scale as the canvas widens, so size it
    # from the figure's own width estimate (same reasoning as the edge margin)
    row_w = max(int(c // per_symbol) * gap + (r if abs(c / per_symbol -
              round(c / per_symbol)) > 1e-9 else 0.0) for _, c in rows)
    x0 = label_w + r + _clearance_units(STROKE_PX + SLACK_STROKE + 1.0,
                                        label_w + row_w + 2 * MARGIN + 60)  # +1 = circle half-stroke
    y0, step = 0.0, 42.0
    elements: list[dict] = []
    anchors: dict[str, XY] = {}
    for ri, (label, count) in enumerate(rows):
        y = y0 + ri * step
        elements.append(vc.text((0.0, y), str(label), id=f"row{ri}", align="start", size=16))
        full_n = int(count // per_symbol)
        half_n = count % per_symbol
        for k in range(full_n):
            elements.append(vc.circle((x0 + k * gap, y), r, id=f"r{ri}c{k}"))
        if half_n:
            cx = x0 + full_n * gap
            elements.append({"id": f"r{ri}h", "type": "arc", "center": [vc.r2(cx), vc.r2(y)],
                             "r": r, "start": 270, "end": 90})
            elements.append(vc.line((cx, y - r), (cx, y + r), id=f"r{ri}hd"))
    sep_y = y0 + len(rows) * step - step / 2 + 6
    widest_cols = max(int(-(-count // per_symbol)) for _, count in rows)
    # the separator ends just past the widest row's last symbol — a long Sinhala row label
    # already pushes the canvas wide; dead space would only shrink every rendered px
    elements.append({"id": "sep", "type": "line", "stroke": {"color": "#d1d5db", "width": 1},
                     "points": [[0.0, vc.r2(sep_y)],
                                [x0 + (widest_cols - 1) * gap + r + 4, vc.r2(sep_y)]]})
    key_y = sep_y + 29   # the DOM label box reaches 0.70·size above centre — leave real room
    elements.append(vc.circle((x0, key_y), r, id="key"))
    elements.append(vc.text((x0 + gap, key_y), f"= {per_symbol:g}", id="keyt",
                            align="start", size=16))
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    for ri, (label, count) in enumerate(rows):
        sym = count / per_symbol
        add(f'describe "row {label} shows {sym:g} symbols — {count:g} items at '
            f'{per_symbol:g} per symbol"', "inferred", "the row's count reads off the symbols")
        add(f'label "{label}" names row{ri + 1}', "stem", "the row label")
    add(f'label "= {per_symbol:g}" names key', "stem", "the key row under the separator")
    add(f"derive {per_symbol:g} / 2 = {per_symbol / 2:g}", "stem",
        "a half symbol stands for half the key value")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "symbol circles, a separator and labels only")
    elements_n = len(elements)
    return finish(kind="pictograph", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=[], segments=[], claims=claims, ask=ask,
                  title=title or "A pictograph of symbols in rows",
                  description=description or (
                      f"A pictograph with {len(rows)} rows of identical circles; one full "
                      f"circle stands for {per_symbol:g}, a right half-circle for half that."),
                  scale="symbols are uniform — the count is the content",
                  budget=elements_n if elements_n > 32 else None,
                  departures=([f"{elements_n} elements — one circle per item is the honest "
                               "drawing (S6b §3.4)"] if elements_n > 32 else None),
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 6. rectangle_points — rectangle ABCD with points on sides and extra segments
# ────────────────────────────────────────────────────────────────────────────────
def build_rectangle_points(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                           length=None, width=None, aspect=(4, 3), on_points=None,
                           extra_segments=(), masks=None, base_px=208.0):
    vc.reset_ids()
    nums = stem_numbers(stem)
    if length is not None and width is not None:
        require_stem(stem, length=length, width=width)
        ar = length / width
    else:
        ar = aspect[0] / aspect[1]
    W_, H_ = base_px, base_px / ar
    A, B, C, D = (0, 0), (W_, 0), (W_, H_), (0, H_)
    corners = {"A": A, "B": B, "C": C, "D": D}
    pts = dict(corners)
    for name, (side, t) in (on_points or {}).items():
        if not re.fullmatch(r"[A-Z]", name):
            raise TemplateError(f"rectangle_points: point name {name!r} is not a single capital")
        if not (0.0 < t < 1.0):
            raise TemplateError(f"rectangle_points: {name}'s position t={t} must be between 0 and 1")
        a, b = side[0], side[1]
        if len(side) != 2 or a == b or a not in corners or b not in corners:
            raise TemplateError(f"rectangle_points: {name}'s side {side!r} is not a side of ABCD")
        if not ((corners[a][0] == corners[b][0]) or (corners[a][1] == corners[b][1])):
            raise TemplateError(f"rectangle_points: {side} is a diagonal, not a side")
        pts[name] = vc.lerp(corners[a], corners[b], t)
    elements: list[dict] = []
    for a, b in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")):
        elements.append(vc.line(corners[a], corners[b], id=f"{a}{b}"))
    for seg in extra_segments:
        a, b = seg[0], seg[1]
        if len(seg) != 2 or a not in pts or b not in pts:
            raise TemplateError(f"rectangle_points: extra segment {seg!r} names unknown points")
        elements.append(vc.line(pts[a], pts[b], id=seg))
    incident = {seg[i] for seg in extra_segments for i in (0, 1)}
    mask_corners = masks if masks is not None else [c for c in "ABCD" if c not in incident]
    for c in mask_corners:
        if c not in corners:
            raise TemplateError(f"rectangle_points: mask corner {c!r} is not one of A,B,C,D")
        # the mask's two arms point at the corners sharing exactly one coordinate with this one
        nbrs = [n for n in "ABCD" if (corners[n][0] == corners[c][0])
                != (corners[n][1] == corners[c][1])]
        elements += vc.right_angle_mask(corners[c], corners[nbrs[0]], corners[nbrs[1]], size=14)
    # vertex labels: offsets pushed diagonally OUT of the corners — a capital at fontSize 18 is
    # ~11 px wide and 18 tall, and the box must clear BOTH sides meeting at the corner
    offs = {"A": (-22, -24), "B": (12, -24), "C": (12, 24), "D": (-24, 24)}
    for n, v in pts.items():
        if n in offs:
            off = offs[n]
        else:   # a point on a side — push the label outward
            off = [(0, -28) if v[1] == 0 else (0, 26) if v[1] == H_ else
                   (-28, 0) if v[0] == 0 else (28, 0)][0]
        elements.append({"id": f"lbl{n}", "type": "point", "at": vc.P(v), "r": 0,
                         "label": n, "labelOffset": list(off)})
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    for x, q, y in (("D", "A", "B"), ("A", "B", "C"), ("B", "C", "D"), ("C", "D", "A")):
        add(f"right {x} {q} {y}", "inferred", "a rectangle's corner")
    if length is not None:
        add(f"ratio len AB / len BC = {ar:g}", "stem",
            f"the stem's {length:g} by {width:g}")
        add(f"derive {length:g} * {width:g} = {_num_exact(length * width)}", "inferred",
            "the stem's length times width — the rectangle's area")
    else:
        # a constructed claim set needs a `derive`; a shape with no stated lengths owns only
        # its four right corners (canonical constants)
        add("derive 360 / 90 = 4", "inferred",
            "the four right corners share the full turn")
    for name, (side, t) in (on_points or {}).items():
        add(f"on {name} {side[0]}{side[1]}", "inferred", f"{name} sits {t:g} of the way along {side}")
    if on_points:
        name, (side, t) = next(iter(on_points.items()))
        from fractions import Fraction
        fr = Fraction(t).limit_denominator(64)
        add(f"derive {fr.numerator} / {fr.denominator} = {_num_exact(t)}", "inferred",
            f"{name}'s position along {side} as a fraction")
    for n in pts:
        add(f'label "{n}" names {n}', "stem", "a named point")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "plain sides and square masks only")
    segs = ["AB", "BC", "CD", "DA"] + list(extra_segments)
    amb = None
    scale = "to scale" if length is not None else \
        f"NOT to scale — the stem states no side lengths; the {aspect[0]}:{aspect[1]} aspect is a canvas choice"
    if length is None:
        amb = [f"K1 - aspect {aspect[0]}:{aspect[1]} is a construction freedom — the stem states "
               "no side lengths, so no ratio claim is made"]
    return finish(kind="rectangle_points", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=pts, points=list(pts), segments=segs, claims=claims, ask=ask,
                  title=title or "A rectangle with a point on one side",
                  description=description or (
                      f"A rectangle ABCD" +
                      (f" drawn {length:g} by {width:g}" if length is not None
                       else " drawn wider than it is tall") +
                      ("; " + ", ".join(f"{n} lies on side {s}"
                                        for n, (s, _t) in on_points.items())
                       if on_points else "") +
                      (", joined by the drawn segment" + ("s " if len(extra_segments) > 1 else " ")
                       + " and ".join(extra_segments) if extra_segments else "") +
                      ("; right angles are marked at " + " and ".join(mask_corners)
                       if mask_corners else "") + "."),
                  scale=scale, ambiguous=amb, medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 7. house_pentagon — a house: rectangular body + two slants meeting at apex P
# ────────────────────────────────────────────────────────────────────────────────
def build_house_pentagon(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                         AB, BC, DA, CP, PD, unit="m", labels=None, unit_px=None):
    """Sides are FIGURE-PRINTED values (like a pictograph's counts): a side whose label
    restates its value ("8 m") is content the figure itself asserts; a side drawn with a
    non-numeric label ("x m") cannot restate its value, so THAT value must come from the
    stem (require_stem) — the question's only other ground truth."""
    vc.reset_ids()
    labels = labels or {}
    nums = stem_numbers(stem)
    sides = {"AB": AB, "BC": BC, "CP": CP, "PD": PD, "DA": DA}
    texts = {k: labels.get(k, f"{v:g} {unit}") for k, v in sides.items()}
    for k, v in sides.items():
        if v <= 0:
            raise TemplateError(f"house_pentagon: side {k}={v} must be positive")
        for tok in re.findall(r"\d+(?:\.\d+)?", texts[k]):
            if abs(float(tok) - v) > 1e-9:
                raise TemplateError(
                    f"house_pentagon: label {texts[k]!r} on side {k} prints the number {tok} "
                    f"but {k} is {v:g} {unit} — a side label may only restate its own value")
        if not re.search(rf"(?<![\d.]){re.escape(f'{v:g}')}(?![\d.])", texts[k]):
            require_stem(stem, **{f"side {k} ({texts[k]!r})": v})
    u = unit_px or min(160.0 / AB, 56.0 / max(BC, DA))
    A, B = (0.0, 0.0), (AB * u, 0.0)
    C, D = (AB * u, -BC * u), (0.0, -DA * u)
    # apex: intersection of circle(C, CP·u) and circle(D, PD·u), the root above the body
    d = vc.dist(C, D)
    if not d or CP * u + PD * u <= d + 1e-9 or abs(CP * u - PD * u) >= d - 1e-9:
        raise TemplateError(
            f"house_pentagon: slants |CP|={CP:g} and |PD|={PD:g} cannot meet above the body "
            f"(|CD|={d / u:g} {unit}) — check the side lengths")
    a = (CP * u * CP * u - PD * u * PD * u + d * d) / (2 * d)
    h = math.sqrt(max(CP * u * CP * u - a * a, 0.0))
    mx, my = C[0] + a * (D[0] - C[0]) / d, C[1] + a * (D[1] - C[1]) / d
    rx, ry = -(D[1] - C[1]) / d, (D[0] - C[0]) / d
    P = min(((mx + rx * h, my + ry * h), (mx - rx * h, my - ry * h)), key=lambda p: p[1])
    pts = {"A": A, "B": B, "C": C, "D": D, "P": P}
    centroid = (sum(p[0] for p in pts.values()) / 5, sum(p[1] for p in pts.values()) / 5)
    elements: list[dict] = []
    for a_, b_ in (("A", "B"), ("B", "C"), ("C", "P"), ("P", "D"), ("D", "A")):
        elements.append(vc.line(pts[a_], pts[b_], id=f"{a_}{b_}"))
    for k, (a_, b_) in zip(("AB", "BC", "CP", "PD", "DA"),
                           (("A", "B"), ("B", "C"), ("C", "P"), ("P", "D"), ("D", "A"))):
        mid = vc.lerp(pts[a_], pts[b_], 0.5)
        nx, ny = vc.normal(pts[a_], pts[b_])
        if (nx * (centroid[0] - mid[0]) + ny * (centroid[1] - mid[1])) > 0:
            nx, ny = -nx, -ny           # outward
        # the label box must clear the side by ~12 units — the centre sits clearance +
        # the box's half-extent along the outward normal away (width is the DISPLAY text)
        half = _label_half_along(texts[k], 16, nx, ny)
        lx, ly = mid[0] + nx * (12 + half), mid[1] + ny * (12 + half)
        # a letter label ("x m") stays plain text — VDD `text` has no italic (fontFamily is
        # sans/serif/mono only) and a KaTeX `math` label would be a serif face among sans
        elements.append(vc.text((lx, ly), texts[k], id=f"sl{k}", size=16))
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    add("right D A B", "inferred", "the body's bottom-left corner")
    add("right A B C", "inferred", "the body's bottom-right corner")
    eq = [(a_, b_) for i, a_ in enumerate(sides) for b_ in list(sides)[i + 1:]
          if abs(sides[a_] - sides[b_]) <= 1e-9]
    for a_, b_ in eq:
        add(f"equal {a_} {b_}", "inferred", "the stem's equal sides")
    for a_, b_ in (("AB", "BC"), ("CP", "PD"), ("AB", "DA")):
        v = sides[a_] / sides[b_]
        if _ratio_justified(nums, v):
            add(f"ratio len {a_} / len {b_} = {v:g}", "stem",
                f"the stem's {sides[a_]:g} and {sides[b_]:g}")
    add(f"derive {' + '.join(f'{v:g}' for v in sides.values())} = "
        f"{_num_exact(sum(sides.values()))}", "inferred",
        "the perimeter as a sum of the five sides")
    claimed_texts = set()
    for k, t in texts.items():
        # audit rule 1: ONE label claim per printed glyph — two sides of equal length print
        # the same text, so the second binds nothing new
        if t in claimed_texts:
            continue
        claimed_texts.add(t)
        add(f'label "{t}" names {k}', "stem",
            f"the figure's own {k} label" if t == f"{sides[k]:g} {unit}" else f"the stem's {t}")
    add('describe "a five-sided figure: a rectangular body with two slanting sides meeting at apex P"',
        "inferred", "shape summary for a reader")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred", "outline only")
    return finish(kind="house_pentagon", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=pts, points=list(pts), segments=list(sides), claims=claims, ask=ask,
                  title=title or "A five-sided figure with side lengths",
                  description=description or (
                      f"A five-sided figure like a house: bottom side {texts['AB']}, right side "
                      f"{texts['BC']}, two slanting sides {texts['CP']} and {texts['PD']} meeting "
                      f"at the apex, left side {texts['DA']}."),
                  scale="to scale — every side's drawn length is its stated length", medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 8. cuboid — oblique projection; the front face is true, depth is foreshortened
# ────────────────────────────────────────────────────────────────────────────────
def build_cuboid(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                 length, width, height, unit="cm", unit_px=None,
                 depth_angle=35.0, depth_scale=0.5):
    vc.reset_ids()
    # the hidden-edge set {DH,GH,EH} and the label placement assume depth runs UP-RIGHT —
    # an angle outside (0°,90°) or a non-positive scale would draw something else silently
    if not (0 < depth_angle < 90):
        raise TemplateError(f"cuboid: depth_angle {depth_angle} must be in (0, 90) — the "
                            "hidden-edge set assumes an up-right oblique projection")
    if not (0 < depth_scale <= 1):
        raise TemplateError(f"cuboid: depth_scale {depth_scale} must be in (0, 1] — "
                            "foreshortened depth, not inverted or enlarged")
    require_stem(stem, length=length, width=width, height=height)
    u = unit_px or min(150.0 / length, 62.0 / height)
    L, Hh = length * u, height * u
    dx, dy = (depth_scale * width * u * math.cos(math.radians(-depth_angle)),
              depth_scale * width * u * math.sin(math.radians(-depth_angle)))
    A, B, C, D = (0.0, 0.0), (L, 0.0), (L, Hh), (0.0, Hh)
    E = (A[0] + dx, A[1] + dy)
    F = (B[0] + dx, B[1] + dy)
    G = (C[0] + dx, C[1] + dy)
    Hh_ = (D[0] + dx, D[1] + dy)
    pts = {"A": A, "B": B, "C": C, "D": D, "E": E, "F": F, "G": G, "H": Hh_}
    elements: list[dict] = []
    hidden = {"DH", "GH", "EH"}                     # the three edges at the hidden corner H
    for seg, a_, b_ in (("AB", "A", "B"), ("BC", "B", "C"), ("CD", "C", "D"), ("DA", "D", "A"),
                        ("AE", "A", "E"), ("BF", "B", "F"), ("CG", "C", "G"), ("DH", "D", "H"),
                        ("EF", "E", "F"), ("FG", "F", "G"), ("GH", "G", "H"), ("EH", "E", "H")):
        el = vc.line(pts[a_], pts[b_], id=seg)
        if seg in hidden:
            el["stroke"] = {"style": "dashed"}
        elements.append(el)
    elements.append(vc.text((vc.lerp(D, C, 0.5)[0], vc.lerp(D, C, 0.5)[1] + 24),
                            f"{length:g} {unit}", id="slL", size=16))
    # height label beside DA — visual-check's target rule wants a label within 1.5 × fontSize of
    # the edge it names (16u → ≤24u); 16u off keeps ≥6 rendered px of stroke clearance.
    elements.append(vc.text(((A[0] + D[0]) / 2 - 16, (A[1] + D[1]) / 2), f"{height:g} {unit}",
                            id="slH", align="end", size=16))
    # the width label sits on the OUTWARD normal of a depth edge's midpoint — CG first
    # (below-right of the figure; beside FG it would read as naming a height edge, and inside
    # the silhouette as a bottom edge). A tall narrow front face crowds that seat against the
    # length label, so fall back to the top depth edge AE (above-left of the figure). An edge
    # is refused when its seat cannot clear the strokes and the labels already placed.
    d_dep = math.hypot(dx, dy)
    ctr_x = sum(p[0] for p in pts.values()) / 8
    ctr_y = sum(p[1] for p in pts.values()) / 8
    seats: list = []
    for seg, mid in (("CG", vc.lerp(C, (C[0] + dx, C[1] + dy), 0.5)),
                     ("AE", vc.lerp(A, E, 0.5))):
        nx_, ny_ = -dy / d_dep, dx / d_dep
        if nx_ * (ctr_x - mid[0]) + ny_ * (ctr_y - mid[1]) > 0:
            nx_, ny_ = -nx_, -ny_                     # outward = away from the solid
        off_ = 12 + _label_half_along(f"{width:g} {unit}", 16, nx_, ny_)
        px_, py_ = mid[0] + nx_ * off_, mid[1] + ny_ * off_
        w_ = _label_width(f"{width:g} {unit}", 16)
        # the label is middle/middle — its box is CENTRED on the anchor, not start-aligned
        seats.append((seg, px_, py_,
                      (px_ - w_ / 2, py_ - 16 * MID_UP, px_ + w_ / 2, py_ + 16 * MID_DOWN)))
    strokes_now = stroke_segments(elements)
    placed_now = [b for _t, *b in label_boxes(elements, 16)]
    width_seg = None
    for seg, px_, py_, box_ in seats:
        # 9.5 units ≈ the 8 rendered px the pre-flight wants once the 12-unit normal offset
        # loses the edge's half-stroke and the half-extent estimate errs
        if min(_seg_rect_dist(a, b, box_) - w2 / 2 for a, b, w2 in strokes_now) >= 9.5 and \
                all(_rect_gap(box_, pb) >= 8.0 for pb in placed_now):
            elements.append(vc.text((px_, py_), f"{width:g} {unit}", id="slW", size=16))
            width_seg = seg
            break
    if width_seg is None:
        raise TemplateError("cuboid: the width label has no seat clear of the other labels "
                            "and edges — adjust the proportions")
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    dr = add(f"derive {length:g} / {height:g} = {_num_exact(length / height)}", "stem",
             "the front face's ratio from the stem's own numbers")
    add(f"ratio len DC / len DA = {length / height:g}", "stem",
        f"the stem's {length:g} {unit} by {height:g} {unit}, per derive {dr}")
    for x, q, y in (("D", "A", "B"), ("A", "B", "C"), ("B", "C", "D"), ("C", "D", "A")):
        add(f"right {x} {q} {y}", "inferred", "the front face is a true rectangle")
    for a_, b_ in (("AB", "CD"), ("AB", "EF"), ("BC", "DA"), ("BC", "FG"),
                   ("AE", "BF"), ("AE", "CG")):
        add(f"parallel {a_} {b_}", "inferred", "a cuboid's edge classes")
    for seg in sorted(hidden):
        add(f"paint {seg} dashed", "inferred", "a hidden edge drawn broken")
    contested = []
    lab_pairs = [(f"{length:g} {unit}", "DC"), (f"{height:g} {unit}", "DA"),
                 (f"{width:g} {unit}", width_seg)]
    claimed_glyphs: set = set()
    for pred, seg in lab_pairs:
        # audit rule 1: ONE label claim per printed glyph — equal dimensions print the same
        # text, so a repeated glyph binds nothing new. When the shared text also prints on
        # the foreshortened edge, the claim names THAT edge: the drawn-vs-label pair check
        # (2e-iii) then measures the edge that needs adjudication, not only a true one.
        if pred in claimed_glyphs:
            continue
        claimed_glyphs.add(pred)
        target = width_seg if any(s == width_seg for p, s in lab_pairs if p == pred) else seg
        kid = add(f'label "{pred}" names {target}', "stem", f"the stem's {pred}")
        if target == width_seg:
            # depth edges are drawn at depth_scale — the anchor-vs-label pair check (2e-iii)
            # must see this declared, or pairs with the depth edge look like a misdrawn ratio
            contested.append((kid, f"{pred} prints the stem's true width on {width_seg} while "
                                   "the oblique convention draws depth edges foreshortened "
                                   f"({depth_scale:g}x at {depth_angle:g} deg)"))
    add('describe "a cuboid in oblique projection — the front face is true shape, '
        'depth edges run 35 degrees up-right at half the true width"', "inferred",
        "the drawing convention")
    add("none tickMark parallelMark angleMark arrow shaded", "inferred",
        "edges only; hidden edges are dashed (claimed)")
    return finish(kind="cuboid", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=pts, points=list(pts),
                  segments=["AB", "BC", "CD", "DA", "AE", "BF", "CG", "DH", "EF", "FG", "GH", "EH"],
                  claims=claims, ask=ask,
                  title=title or f"A cuboid {length:g} by {width:g} by {height:g} {unit}",
                  description=description or (
                      f"A cuboid in oblique projection, {length:g} {unit} long, {width:g} {unit} "
                      f"wide and {height:g} {unit} high; the three edges meeting at the hidden "
                      f"back corner are drawn dashed."),
                  scale="front face true (length:height as stated); depth edges foreshortened "
                        "to half the stated width at 35 degrees — an oblique convention, not to "
                        "scale in depth", contested=contested, medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 9. dot_pattern — stages of a dot pattern (triangle / square / rectangle counts)
# ────────────────────────────────────────────────────────────────────────────────
def build_dot_pattern(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                      stages, kind="triangle", dot_r=5.0, dx=26.0, dy=22.5, gap=36.0):
    vc.reset_ids()
    if kind not in ("triangle", "square", "rectangle"):
        raise TemplateError(f"dot_pattern: kind {kind!r} — one of triangle, square, rectangle")
    if not (isinstance(stages, int) and 1 <= stages <= 8):
        raise TemplateError("dot_pattern: stages must be a whole number in 1..8")
    nums = stem_numbers(stem)
    count = {"triangle": lambda n: n * (n + 1) // 2,
             "square": lambda n: n * n,
             "rectangle": lambda n: n * (n + 1)}[kind]
    expr = {"triangle": lambda n: f"{n} * {n + 1} / 2",
            "square": lambda n: f"{n} * {n}",
            "rectangle": lambda n: f"{n} * {n + 1}"}[kind]
    elements: list[dict] = []
    anchors: dict[str, XY] = {}
    # the stage label must clear the lowest dot row's stroke by 6 px + slack ON THE
    # RENDER — the fixed 22-unit drop shrinks under the narrow-surface scale once the
    # stages row runs wider than the plate, so widen it when the figure's own span
    # demands (number_line's mark_off and pictograph's x0 size gaps the same way;
    # +1 ≈ the dot circle's half-stroke)
    est_span = (sum((((n + 1) if kind == "rectangle" else n) - 1) * dx + gap
                    for n in range(1, stages + 1))
                - gap + 2 * dot_r + _label_width(f"({stages})", 13))
    lab_drop = dot_r + max(22.0, MID_UP * 13.0 +
                           _clearance_units(STROKE_PX + SLACK_STROKE + 1.0, est_span))
    x = 0.0
    for n in range(1, stages + 1):
        cols_n = n if kind != "rectangle" else n + 1
        block_w = (cols_n - 1) * dx
        cx = x + block_w / 2
        # every stage's bottom row sits on ONE common baseline; a triangle's apex points up
        base = (stages - 1) * dy
        for r_ in range(n):                                  # row 0 is the TOP row on screen
            dots_in_row = (r_ + 1) if kind == "triangle" else cols_n
            for d_ in range(dots_in_row):
                elements.append(vc.circle(
                    (cx + (d_ - (dots_in_row - 1) / 2) * dx, base - (n - 1 - r_) * dy), dot_r,
                    fill=vc.INK, id=f"t{n}r{r_}d{d_}"))
        elements.append(vc.text((cx, base + lab_drop), f"({n})", id=f"lbl{n}", size=13))
        x += block_w + gap
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    for n in range(1, stages + 1):
        add(f"stage {n} shows {count(n)} dots", "inferred", f"the {kind} count of stage {n}")
        add(f"derive {expr(n)} = {count(n)}", "inferred", f"the count of stage {n} from the pattern")
        add(f'label "({n})" names stage{n}', "stem", "the stage numeral")
    add("none tickMark parallelMark angleMark angleArc arrow dashed shaded", "inferred",
        "dots and numerals only")
    amb = None if _has_stem(nums, stages) else \
        [f"K1 - the stage count {stages} is a construction choice — the stem does not state it "
         f"as a number (stem numbers {', '.join(f'{v:g}' for v in nums)})"]
    elements_n = len(elements)
    return finish(kind="dot_pattern", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=[], segments=[], claims=claims, ask=ask,
                  title=title or f"A dot pattern of {stages} stages",
                  description=description or (
                      f"The first {stages} figures of a dot pattern shown side by side; the dot "
                      f"counts are {kind} numbers."),
                  scale="dots are uniform — the count is the content", ambiguous=amb,
                  budget=elements_n if elements_n > 32 else None,
                  departures=([f"{elements_n} elements — one circle per dot is the honest "
                               "drawing (S6b §3.4)"] if elements_n > 32 else None),
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# W10c — membership/collection figures. Dots in/on/out of circles, rings sorting
# items, abacus rods, a row of named shapes. Every label is either placed by
# finish()'s `_near` float or sits at a position the builder computes — the caller
# never picks label coordinates.
# ────────────────────────────────────────────────────────────────────────────────
def _float_label(id_: str, glyph: str, near: XY, gap: float | None = None,
                 size: float | None = None) -> dict:
    """A `text` element that finish() places itself — `_near` is the anchor it labels
    (element coords; `at` is ignored). `glyph` is the printed value."""
    el = vc.text(list(near), glyph, id=id_, size=size)
    el["_near"] = [vc.r2(near[0]), vc.r2(near[1])]
    if gap is not None:
        el["_gap"] = gap
    return el


def _named_dots(kind: str, points) -> list[str]:
    """Validate a region figure's `points` dict (name -> spec) and return the names
    in order. Names are the claim-set's point names — single capitals."""
    if not isinstance(points, dict) or not points:
        raise TemplateError(f"{kind}: `points` must be a non-empty dict of name -> spec")
    for nm in points:
        if not isinstance(nm, str) or not re.fullmatch(r"[A-Z]", nm):
            raise TemplateError(f"{kind}: point names are single capitals — got {nm!r}")
        spec = points[nm]
        if spec is not None and not isinstance(spec, dict):
            raise TemplateError(f"{kind}: {nm}'s spec must be a dict of placement keys "
                                f"— got {spec!r}")
    return list(points)


def _distinct_glyphs(kind: str, glyphs: list[str]) -> None:
    """Every drawn label binds exactly one claim — two glyphs that print alike make the
    binding ambiguous, so refuse them up front."""
    if len(set(glyphs)) != len(glyphs):
        dup = next(g for g in glyphs if glyphs.count(g) > 1)
        raise TemplateError(f"{kind}: two labels print {dup!r} — glyphs must be distinct")


# deterministic candidate angles for a dot ON an outline (deg, 0° = east, y down)
_ON_DEG_CANDS = (-90.0, 90.0, 0.0, 180.0, -45.0, 45.0, -135.0, 135.0,
                 -30.0, 30.0, -60.0, 60.0, -120.0, 120.0, -150.0, 150.0,
                 -15.0, 15.0, -75.0, 75.0, -105.0, 105.0, -165.0, 165.0)


def _deg_clear(deg: float, used: list[float], min_deg: float = 18.0) -> bool:
    d = lambda a, b: abs((a - b + 180.0) % 360.0 - 180.0)
    return all(d(deg, u) >= min_deg for u in used)


def _spread_deg(i: int) -> float:
    """The i-th direction on a golden-angle spiral — seeds that spread instead of
    clustering when several dots share a region."""
    return (-90.0 + 137.508 * i) % 360.0


def _circle_claim(add, cname: str, r: float, on_names: list[str]) -> None:
    """The circle claim vdd-check actually evaluates: `through` names two or three
    REAL on-outline anchors (their distances to the centre are compared — a lone
    through-point is recognised but unverifiable); with fewer, `radius r` is
    measured straight against the drawn circle element."""
    if len(on_names) >= 2:
        add(f"circle centre {cname} through {' '.join(on_names[:3])}", "inferred",
            "the ring drawn through the on-dots")
    else:
        add(f"circle centre {cname} radius {r:g}", "inferred", "the drawn circle's radius")


# ────────────────────────────────────────────────────────────────────────────────
# 10. circle_points — one circle with dots inside it, on its outline or outside it
# ────────────────────────────────────────────────────────────────────────────────
def build_circle_points(*, figure_id, stem, ask=None, title=None, description=None,
                        medium="english", points, r=100.0, labelled=True, dot_r=4.2):
    """A circle holding named dots. `points` = {name: {"where": "in"|"on"|"out",
    "label": glyph-or-None, "deg": angle-or-None}} — `deg` pins an on-outline dot,
    otherwise on-dots spread by a fixed pattern; in/out dots go through region_point
    on golden-angle seeds (min_sep 34, margin 18). labelled=False draws stones — dots
    with no labels."""
    vc.reset_ids()
    names = _named_dots("circle_points", points)
    if not (isinstance(r, (int, float)) and r >= 40.0):
        raise TemplateError("circle_points: radius r must be at least 40 units")
    centre = (0.0, 0.0)
    circles = {"main": (centre, float(r))}
    specs = {}
    for nm in names:
        spec = points[nm] or {}
        where = spec.get("where")
        if where not in ("in", "on", "out"):
            raise TemplateError(f"circle_points: {nm} has where={where!r} — 'in', 'on' or 'out'")
        if spec.get("deg") is not None and where != "on":
            raise TemplateError(f"circle_points: {nm} carries deg but is {where!r} — "
                                "deg pins an 'on' dot only")
        deg = spec.get("deg")
        if deg is not None and (not isinstance(deg, (int, float))
                                or isinstance(deg, bool)):
            raise TemplateError(f"circle_points: {nm}'s deg must be a number of "
                                f"degrees — got {deg!r}")
        specs[nm] = spec
    elements = [vc.circle(centre, r, id="circ")]
    anchors: dict[str, XY] = {}
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    cname = "Z" if "Z" not in names else _unused_letters(set(names), 1)[0]
    anchors[cname] = centre

    placed: list[XY] = []
    used_degs: list[float] = []
    pos: dict[str, XY] = {}
    # on-outline dots pin their angles first, so the region search for in/out dots
    # can avoid them
    for nm in names:
        spec = specs[nm]
        if spec["where"] != "on":
            continue
        if spec.get("deg") is not None:
            deg = float(spec["deg"])
            # a pinned deg gets the same separation rules as an auto-placed one —
            # otherwise deg=0 + deg=5 draws two near-coincident dots and the failure
            # only surfaces later as a mis-labelled "no clear spot" refusal
            if not _deg_clear(deg, used_degs):
                raise TemplateError(
                    f"circle_points: {nm} pins deg {deg:g} — within 18° of another "
                    "on-outline dot; spread the pinned angles")
            p = on_circle_point(centre, r, deg)
            if any(math.hypot(p[0] - o[0], p[1] - o[1]) < 30.0 for o in placed):
                raise TemplateError(
                    f"circle_points: {nm} at deg {deg:g} lands under 30 units from "
                    "another dot — pick a clearer angle")
            used_degs.append(deg)
        else:
            p = None
            for cand in _ON_DEG_CANDS:
                if not _deg_clear(cand, used_degs):
                    continue
                q = on_circle_point(centre, r, cand)
                if all(math.hypot(q[0] - o[0], q[1] - o[1]) >= 30.0 for o in placed):
                    p = q
                    used_degs.append(cand)
                    break
            if p is None:
                raise TemplateError("circle_points: no clear angle left on the outline for "
                                    f"{nm} — pass deg= or drop a dot")
        pos[nm] = p
        placed.append(p)
    in_i = out_i = 0
    n_in = sum(1 for s in specs.values() if s["where"] == "in")
    n_out = sum(1 for s in specs.values() if s["where"] == "out")
    for nm in names:
        spec = specs[nm]
        if spec["where"] == "on":
            continue
        if spec["where"] == "in":
            rad = (r - 30.0) * math.sqrt((in_i + 0.5) / n_in)
            prefer = vc.polar(centre, max(rad, 0.0), _spread_deg(in_i))
            # dots are circle elements — off the centre so a `radius` claim sees
            # one circle at C, not the dot too
            p = region_point(circles, inside=["main"], outside=[], prefer=prefer,
                             margin=18.0, avoid=placed + [centre], min_sep=34.0)
            in_i += 1
        else:
            prefer = vc.polar(centre, r + 55.0, _spread_deg(out_i + 1) + 45.0)
            p = region_point(circles, inside=[], outside=["main"], prefer=prefer,
                             margin=18.0, avoid=placed, min_sep=34.0)
            out_i += 1
        pos[nm] = p
        placed.append(p)

    glyphs = [str(specs[nm].get("label") or nm) for nm in names]
    if labelled:
        _distinct_glyphs("circle_points", glyphs)
    word = {"in": "inside", "on": "on", "out": "outside"}
    for i, nm in enumerate(names):
        p = pos[nm]
        anchors[nm] = p
        elements.append({"id": f"pt{nm}", "type": "point", "at": vc.P(p), "r": dot_r})
        add(f'describe "{nm} lies {word[specs[nm]["where"]]} the circle"', "inferred",
            "the dot's drawn position")
        if labelled:
            elements.append(_float_label(f"lb{nm}", glyphs[i], p))
            add(f'label "{glyphs[i]}" names {nm}', "stem", f"the label on dot {nm}")
    _circle_claim(add, cname, r, [nm for nm in names if specs[nm]["where"] == "on"])
    add(f"derive {n_in} + {len(used_degs)} + {n_out} = {len(names)}", "inferred",
        "inside + on + outside counts make the dot total")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "a circle and dots only")
    lays = [w for w in ("in", "on", "out") if any(specs[nm]["where"] == w for nm in names)]
    desc_bits = {"in": "inside it", "on": "on its outline", "out": "outside it"}
    return finish(kind="circle_points", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=list(anchors), segments=[], claims=claims,
                  ask=ask, title=title or "A circle with dots",
                  description=description or (
                      ("One circle fills the figure on its own, with a single dot "
                       + desc_bits[specs[names[0]]["where"]] + "; nothing else is drawn.")
                      if len(names) == 1 else
                      "One circle fills the figure, and several dots are placed in "
                      "and around it — " + ", ".join(desc_bits[w] for w in lays) + "."),
                  scale="the circle's size is a canvas choice — only in/on/out matters",
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 11. two_circles_points — two overlapping circles with dots in their regions
# ────────────────────────────────────────────────────────────────────────────────
def build_two_circles_points(*, figure_id, stem, ask=None, title=None, description=None,
                             medium="english", points, r=100.0, overlap=0.45, dot_r=4.2):
    """Two overlapping circles L (left) and R (right), centre distance 2r(1-overlap).
    `points` = {name: {"in": ["L"|"R", ...], "on": "L"|"R"|None, "label": glyph-or-None}} —
    `in` lists the circles whose interior holds the dot; `on` pins it to that circle's
    outline while `in` still governs the OTHER circle (on L inside R = on the overlap
    arc). Free dots go through region_point (margin 18, min_sep 34); outline dots pick
    the first clear angle toward or away from the other centre."""
    vc.reset_ids()
    names = _named_dots("two_circles_points", points)
    for reserved in ("L", "R"):
        if reserved in names:
            raise TemplateError(f"two_circles_points: {reserved} names the "
                                f"{'left' if reserved == 'L' else 'right'} circle's centre — "
                                "pick another point name")
    if not (isinstance(overlap, (int, float)) and 0.0 < overlap < 1.0):
        raise TemplateError(f"two_circles_points: overlap {overlap!r} must be in (0, 1) — "
                            "the circles must overlap")
    if not (isinstance(r, (int, float)) and r >= 40.0):
        raise TemplateError("two_circles_points: radius r must be at least 40 units")
    d = 2.0 * r * (1.0 - overlap)
    cL, cR = (0.0, 0.0), (d, 0.0)
    circles = {"left": (cL, float(r)), "right": (cR, float(r))}
    specs = {}
    for nm in names:
        spec = points[nm] or {}
        inside = spec.get("in") or []
        on = spec.get("on")
        if not isinstance(inside, list) or any(s not in ("L", "R") for s in inside):
            raise TemplateError(f"two_circles_points: {nm}'s `in` must be a list drawn from "
                                "'L' and 'R'")
        if len(set(inside)) != len(inside):
            raise TemplateError(f"two_circles_points: {nm}'s `in` repeats a circle")
        if on not in ("L", "R", None):
            raise TemplateError(f"two_circles_points: {nm}'s `on` must be 'L', 'R' or absent")
        if on is not None and on in inside:
            raise TemplateError(f"two_circles_points: {nm} is ON the {on} circle — it cannot "
                                "also be IN it; `in` governs the other circle")
        specs[nm] = (list(inside), on)

    elements = [vc.circle(cL, r, id="cL"), vc.circle(cR, r, id="cR")]
    anchors: dict[str, XY] = {"L": cL, "R": cR}
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    placed: list[XY] = []
    pos: dict[str, XY] = {}

    def outline_spot(nm: str, inside: list, on: str) -> XY:
        c_on = cL if on == "L" else cR
        c_other = cR if on == "L" else cL
        inside_other = ("R" if on == "L" else "L") in inside
        # the arc of `on`'s outline inside the other circle faces its centre; outside
        # faces away
        base = (0.0 if inside_other else 180.0) if on == "L" \
            else (180.0 if inside_other else 0.0)
        for k in range(13):
            for sign in ((0,) if k == 0 else (1, -1)):
                p = vc.polar(c_on, r, base + sign * 15.0 * k)
                d_other = math.hypot(p[0] - c_other[0], p[1] - c_other[1])
                if inside_other and d_other > r - 12.0:
                    continue
                if not inside_other and d_other < r + 12.0:
                    continue
                # a dot is itself a circle element — sitting within the checker's
                # 1.5-unit centre window would hijack the other circle's `radius` claim
                if d_other <= 3.0:
                    continue
                if any(math.hypot(p[0] - o[0], p[1] - o[1]) < 30.0 for o in placed):
                    continue
                return p
        raise TemplateError(
            f"two_circles_points: {nm} has no clear spot on the {on} outline "
            f"{'inside' if inside_other else 'outside'} the other circle — "
            "widen overlap or drop a dot")

    def region_prefer(inside: list, i: int) -> XY:
        if inside == ["L", "R"]:
            base = (d / 2.0, 0.0)
        elif inside == ["L"]:
            base = vc.polar(cL, 0.45 * r, 180.0)
        elif inside == ["R"]:
            base = vc.polar(cR, 0.45 * r, 0.0)
        else:
            base = (d / 2.0, r + 55.0)   # below the pair
        return vc.polar(base, 0.0 if i == 0 else 20.0 + 14.0 * i, _spread_deg(i))

    for nm in names:
        inside, on = specs[nm]
        if on:
            pos[nm] = outline_spot(nm, inside, on)
            placed.append(pos[nm])
    i_free = 0
    for nm in names:
        inside, on = specs[nm]
        if on:
            continue
        in_names = ["left" if s == "L" else "right" for s in inside]
        out_names = [n for n in ("left", "right") if n not in in_names]
        pos[nm] = region_point(circles, inside=in_names, outside=out_names,
                               prefer=region_prefer(inside, i_free),
                               margin=18.0, avoid=placed + [cL, cR], min_sep=34.0)
        i_free += 1
        placed.append(pos[nm])

    glyphs = [str(points[nm].get("label") or nm) for nm in names]
    _distinct_glyphs("two_circles_points", glyphs)
    n_on = n_in = n_out = 0
    for i, nm in enumerate(names):
        inside, on = specs[nm]
        p = pos[nm]
        anchors[nm] = p
        elements.append({"id": f"pt{nm}", "type": "point", "at": vc.P(p), "r": dot_r})
        claims += membership_claims(nm, p, circles)
        elements.append(_float_label(f"lb{nm}", glyphs[i], p))
        add(f'label "{glyphs[i]}" names {nm}', "stem", f"the label on dot {nm}")
        if on:
            n_on += 1
        elif inside:
            n_in += 1
        else:
            n_out += 1
    for cn, cx in (("L", cL), ("R", cR)):
        _circle_claim(add, cn, r, [nm for nm in names if specs[nm][1] == cn])
    add(f"derive {n_in} + {n_on} + {n_out} = {len(names)}", "inferred",
        "inside + on + outside counts make the dot total")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "two circles and dots only")
    return finish(kind="two_circles_points", figure_id=figure_id, stem=stem,
                  elements=elements, anchors=anchors, points=list(anchors),
                  segments=[], claims=claims, ask=ask,
                  title=title or "Two overlapping circles with dots",
                  description=description or
                  ("Two overlapping circles are drawn side by side, with a single dot "
                   "placed inside one outline, on it or around them." if len(names) == 1
                   else "Two overlapping circles are drawn side by side, with several "
                   "dots placed inside their outlines, on them and around them."),
                  scale="the overlap is a canvas choice — only the dots' membership "
                        "matters",
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 12. circles_in_circle — small circles inside and outside a big circle
# ────────────────────────────────────────────────────────────────────────────────
def build_circles_in_circle(*, figure_id, stem, ask=None, title=None, description=None,
                            medium="english", n_in=None, n_out=None, R=120.0, r=16.0):
    """A big circle with n_in small equal circles fully inside it and n_out fully
    outside it — none touching: every small circle is ≥10 units clear of the big
    stroke and of every other small circle. Inside centres land on golden-angle seeds
    via region_point; outside centres prefer a ring 42 units past the outline."""
    vc.reset_ids()
    for nm_, v in (("n_in", n_in), ("n_out", n_out)):
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise TemplateError(f"circles_in_circle: {nm_} must be an int ≥ 0 — got {v!r}")
    if n_in + n_out < 1:
        raise TemplateError("circles_in_circle: at least one small circle")
    if not (r > 0 and R > r + 26.0):
        raise TemplateError("circles_in_circle: need R > r + 26 so a small circle fits "
                            f"inside with 10 units to spare (R={R:g}, r={r:g})")
    centre = (0.0, 0.0)
    circles = {"big": (centre, float(R))}
    elements = [vc.circle(centre, R, id="big")]
    placed: list[XY] = [centre]     # keep a small circle off the claimed centre —
    for i in range(n_in):           # `radius` checks every circle element at Z
        rad = (R - r - 14.0) * math.sqrt(i / max(n_in, 1))
        prefer = vc.polar(centre, rad, _spread_deg(i))
        p = region_point(circles, inside=["big"], outside=[], prefer=prefer,
                         margin=r + 10.0, avoid=placed, min_sep=2 * r + 10.0)
        elements.append(vc.circle(p, r, id=f"in{i + 1}"))
        placed.append(p)
    for j in range(n_out):
        prefer = vc.polar(centre, R + r + 42.0, (-90.0 + j * 360.0 / n_out) % 360.0)
        p = region_point(circles, inside=[], outside=["big"], prefer=prefer,
                         margin=r + 10.0, avoid=placed, min_sep=2 * r + 10.0)
        elements.append(vc.circle(p, r, id=f"out{j + 1}"))
        placed.append(p)
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    anchors: dict[str, XY] = {"Z": centre}
    _circle_claim(add, "Z", R, [])   # no on-dots — `radius` names the drawn circle
    if n_in:
        add(f'describe "{n_in} small circles lie inside the big circle"', "inferred",
            "count the inner rings")
    if n_out:
        add(f'describe "{n_out} small circles lie outside the big circle"', "inferred",
            "count the outer rings")
    add(f"derive {n_in} + {n_out} = {n_in + n_out}", "inferred",
        "inside + outside counts make the small-circle total")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "circles only — nothing is labelled")
    bits = [w for w, n in (("inside it", n_in), ("outside it", n_out)) if n]
    noun = "a small circle" if n_in + n_out == 1 else "several small circles"
    return finish(kind="circles_in_circle", figure_id=figure_id, stem=stem,
                  elements=elements, anchors=anchors, points=list(anchors), segments=[],
                  claims=claims, ask=ask,
                  title=title or "Small circles in and out of a big circle",
                  description=description or
                  f"A large circle with {noun} " + " and ".join(bits) +
                  " — nothing touches the big circle's outline.",
                  scale="the big circle's size is a canvas choice — only in/out counts",
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 13. abacus — place-value rods with beads, value labels below
# ────────────────────────────────────────────────────────────────────────────────
def build_abacus(*, figure_id, stem, ask=None, title=None, description=None,
                 medium="english", place_values=None, beads=None, bead_r=7.5):
    """A spike abacus: one vertical rod per place value (left to right, e.g.
    [10000, 1000, 100, 10, 1]), `beads[i]` ink beads threaded on rod i (0–9 — the
    lesson's own rule that a rod never carries ten), a base bar under the rods and
    the value printed below each rod — a FIXED label centred on its rod (a floater
    drifts sideways off it), rod spacing wide enough that adjacent labels keep
    ≥4 rendered px on the tightest plate.
    The derive claim sums beads × place value to the number shown."""
    vc.reset_ids()
    if not isinstance(place_values, (list, tuple)) or not place_values:
        raise TemplateError("abacus: place_values must be a non-empty list")
    if not isinstance(beads, (list, tuple)) or len(beads) != len(place_values):
        raise TemplateError("abacus: beads must be a list parallel to place_values")
    seen_v = set()
    for v in place_values:
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            raise TemplateError(f"abacus: place value {v!r} must be a positive number")
        if v in seen_v:
            raise TemplateError(f"abacus: place value {v:g} is repeated — two rods would "
                                "print the same label")
        seen_v.add(v)
    for i, b in enumerate(beads):
        if not isinstance(b, int) or isinstance(b, bool) or b < 0:
            raise TemplateError(f"abacus: rod {i + 1}'s bead count {b!r} must be an int ≥ 0")
        if b > 9:
            raise TemplateError(f"abacus: rod {i + 1} carries {b} beads — a place-value rod "
                                "never holds ten (the lesson's own rule)")
    lab_size = 15.0
    max_lab = max(_label_width(f"{v:g}", lab_size) for v in place_values)
    # adjacent value labels must keep ≥4 RENDERED px on the tightest plate; the
    # spacing feeds the span and the span sets the scale — iterate to a fixpoint
    spacing = 64.0
    for _ in range(4):
        span = (len(place_values) - 1) * spacing + max(52.0, max_lab)
        new = max(64.0, max_lab + _clearance_units(4.0 + 1.0, span))
        if abs(new - spacing) < 0.5:
            break
        spacing = new
    rod_h = 9 * (2 * bead_r + 3.0) + 24.0          # room for nine beads on a rod
    base_y = rod_h                                 # local coords; finish() translates
    xs = [i * spacing for i in range(len(place_values))]
    # a 1–2 rod abacus is taller than wide — the rod height is fixed by nine beads,
    # so a short abacus widens its base bar to keep the canvas inside the 2:1 rule
    bar_half = max(26.0, (rod_h + 60.0) / 4.0 - (xs[-1] - xs[0]) / 2.0)
    span = max(span, (xs[-1] - xs[0]) + 2 * bar_half)
    lab_y = base_y + 1.5 + _clearance_units(STROKE_PX + SLACK_STROKE + 1.0, span) \
        + lab_size * MID_UP                        # box top a fixed gap under the bar
    elements = [vc.line((xs[0] - bar_half, base_y), (xs[-1] + bar_half, base_y),
                        id="base", width=3.0)]
    for i, x in enumerate(xs):
        elements.append(vc.line((x, base_y), (x, base_y - rod_h + 12.0), id=f"rod{i + 1}",
                                width=2.0))
        for j in range(beads[i]):
            elements.append(vc.circle((x, base_y - 10.0 - bead_r - j * (2 * bead_r + 3.0)),
                                      bead_r, fill=vc.INK, id=f"b{i + 1}_{j + 1}"))
        elements.append(vc.text((x, lab_y), f"{place_values[i]:g}",
                                id=f"lv{i + 1}", size=lab_size))
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    total = 0
    for i, (v, b) in enumerate(zip(place_values, beads)):
        add(f'label "{v:g}" names rod{i + 1}', "inferred", "the rod's place value")
        add(f'describe "the {v:g} rod holds {b} bead{"s" if b != 1 else ""}"', "inferred",
            "count the beads on the rod")
        total += b * v
    add("derive " + " + ".join(f"{b:g} * {v:g}" for v, b in zip(place_values, beads))
        + f" = {total:g}", "inferred", "beads times place value, summed over the rods")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "rods, beads and a base bar only")
    return finish(kind="abacus", figure_id=figure_id, stem=stem, elements=elements,
                  anchors={}, points=[], segments=[], claims=claims, ask=ask,
                  title=title or "An abacus showing a number",
                  description=description or
                  f"An abacus with {len(place_values)} rods standing on a base bar; "
                  "each rod is labelled with its place value and may carry a stack "
                  "of beads.",
                  scale="bead size and rod spacing are a canvas choice — only the "
                        "counts matter",
                  budget=len(elements) if len(elements) > 32 else None,
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 14. sorting_rings — labelled rings, each holding a column of item cards
# ────────────────────────────────────────────────────────────────────────────────
def build_sorting_rings(*, figure_id, stem, ask=None, title=None, description=None,
                        medium="english", groups=None, ring_gap=16.0):
    """Two or three sorting rings. `groups` = [(name, [items…])]: each item is a
    numeral/word drawn at the default font size on a thin stroke-only rect card,
    the cards stack vertically inside the ring (≥6 units apart, ≥8 from the ring
    stroke) and the group's name prints above the ring. Ring radius grows to fit
    its card column; three groups lay out 2 + 1 — a 3-wide row widens the canvas
    until card text renders too small at 375 px."""
    vc.reset_ids()
    if not isinstance(groups, (list, tuple)) or not (2 <= len(groups) <= 3):
        raise TemplateError("sorting_rings: groups must be a list of 2 or 3 "
                            "(name, items) pairs")
    names_seen: set[str] = set()
    glyphs: list[str] = []
    norm: list[tuple[str, list[str]]] = []
    for g in groups:
        if not isinstance(g, (list, tuple)) or len(g) != 2:
            raise TemplateError("sorting_rings: each group is a (name, items) pair")
        gname, items = str(g[0]), [str(x) for x in (g[1] or [])]
        if not gname.strip():
            raise TemplateError("sorting_rings: a group name is empty")
        if gname in names_seen:
            raise TemplateError(f"sorting_rings: group name {gname!r} is repeated")
        if not items:
            raise TemplateError(f"sorting_rings: group {gname!r} has no items")
        names_seen.add(gname)
        glyphs.append(gname)
        glyphs += items
        norm.append((gname, items))
    _distinct_glyphs("sorting_rings", glyphs)
    # card text and ring names carry NO size override — they render at the
    # renderer's default (FS) and the cards/rings grow to fit, not vice versa
    it_size = name_size = FS
    name_h = name_size * (MID_UP + MID_DOWN)
    rows = ([[0, 1], [2]] if len(norm) == 3 else [list(range(len(norm)))])
    # centre each item's label BOX in its card — the box reaches higher than it
    # hangs (MID_UP > MID_DOWN), so the anchor shifts down by the half-delta and
    # every card edge gets the same pad
    box_dy = it_size * (MID_UP - MID_DOWN) / 2.0
    # pad = ≥8 rendered px label-box to card stroke — the pre-flight measures to
    # the stroke's centreline minus its half-width, hence +1.1. The span feeds the
    # scale and the pad feeds the span, so iterate to a fixpoint — and feed the
    # CONTENT span (the +margins+fudge belongs to _clearance_units' own model;
    # double-counting them here inflated pad ~19 units and the canvas to 423).
    pad = _clearance_units(STROKE_PX + SLACK_STROKE, 320.0) + 1.1
    for _ in range(8):
        card_h = it_size * (MID_UP + MID_DOWN) + 2 * pad
        card_ws = [max(_label_width(x, it_size) for x in items) + 2 * pad
                   for _, items in norm]
        stack_hs = [len(items) * card_h + (len(items) - 1) * 6.0 for _, items in norm]
        radii = [math.hypot(w / 2.0, h / 2.0) + 8.0 for w, h in zip(card_ws, stack_hs)]
        span = sum(2 * radii[i] for i in rows[0]) + ring_gap * (len(rows[0]) - 1)
        if len(rows) == 2:
            span = max(span, 2 * radii[rows[1][0]])
        new_pad = _clearance_units(STROKE_PX + SLACK_STROKE, span) + 1.1
        if abs(new_pad - pad) < 0.05:
            pad = new_pad
            break
        pad = new_pad
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    name_drop = name_size * MID_DOWN + _clearance_units(STROKE_PX + SLACK_STROKE + 2.0,
                                                        span) + 1.0
    cxs: dict[int, float] = {}
    cys: dict[int, float] = {}
    x = 0.0
    for i in rows[0]:
        cxs[i] = x + radii[i]
        cys[i] = 0.0
        x += 2 * radii[i] + ring_gap
    row0_r = x - ring_gap                          # right edge of the first row
    if len(rows) == 2:
        i = rows[1][0]
        cxs[i] = row0_r / 2.0
        # the lone ring's name must still clear the first row's deepest bottom
        cys[i] = (max(radii[j] for j in rows[0])
                  + _clearance_units(STROKE_PX + SLACK_STROKE + 0.5, span)
                  + name_drop + name_size * MID_UP + radii[i])
    for i, ((gname, items), card_w, stack_h, ring_r) in enumerate(
            zip(norm, card_ws, stack_hs, radii)):
        cx, cy0 = cxs[i], cys[i]
        elements.append(vc.circle((cx, cy0), ring_r, id=f"ring{i + 1}"))
        elements.append(vc.text((cx, cy0 - ring_r - name_drop), gname, id=f"nm{i + 1}"))
        top = cy0 - stack_h / 2.0
        for j, item in enumerate(items):
            cy = top + j * (card_h + 6.0) + card_h / 2.0
            elements.append({"id": f"cd{i + 1}_{j + 1}", "type": "rect",
                             "x": vc.r2(cx - card_w / 2.0), "y": vc.r2(cy - card_h / 2.0),
                             "width": vc.r2(card_w), "height": vc.r2(card_h)})
            elements.append(vc.text((cx, cy + box_dy), item, id=f"it{i + 1}_{j + 1}"))
            add(f'label "{item}" names it{i + 1}_{j + 1}', "inferred", "an item card")
        add(f'label "{gname}" names ring{i + 1}', "inferred", "the ring's label")
        add(f'describe "ring {i + 1} holds the {gname} cards — '
            f'{len(items)} items"', "inferred", "what the ring contains")
    add("derive " + " + ".join(str(len(items)) for _, items in norm)
        + f" = {sum(len(items) for _, items in norm)}", "inferred",
        "the rings' card counts make the item total")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "rings and cards only")
    return finish(kind="sorting_rings", figure_id=figure_id, stem=stem, elements=elements,
                  anchors={}, points=[], segments=[], claims=claims, ask=ask,
                  title=title or "Sorting rings",
                  description=description or
                  f"{len(norm)} rings side by side; each has a name above it and a "
                  "column of labelled cards stacked inside.",
                  scale="ring size follows its cards — only the grouping matters",
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 15. shape_row — a row of named shapes, three per row, a letter under each
# ────────────────────────────────────────────────────────────────────────────────
SHAPE_KINDS = ("circle", "small_circle", "square", "rectangle", "triangle",
               "oval", "semicircle")
# curved-outline kinds vs straight-sided kinds — feeds the derive partition
_CURVED_KINDS = {"circle", "small_circle", "oval", "semicircle"}
_SHAPE_DESCS = {
    "circle": "a circle — a curved outline with no corners",
    "small_circle": "a small circle — a curved outline with no corners",
    "square": "a square — four equal sides and four corners",
    "rectangle": "a rectangle — four sides and four corners",
    "triangle": "a triangle — three sides and three corners",
    "oval": "an oval — a curved outline with no corners",
    "semicircle": "a semicircle — one straight side and one curved edge",
}


def build_shape_row(*, figure_id, stem, ask=None, title=None, description=None,
                    medium="english", shapes=None, cell_w=120.0, row_h=132.0):
    """A row of shapes, three to a row, each tagged by a capital letter floating
    below it (`_near` = the shape's bottom point — on its outline, so the label lands
    outside). `shapes` = [(letter, kind)] with kind in SHAPE_KINDS. Ovals and
    semicircles are many-point polygons so the outline is a real closed region."""
    vc.reset_ids()
    if not isinstance(shapes, (list, tuple)) or not shapes:
        raise TemplateError("shape_row: shapes must be a non-empty list of "
                            "(letter, kind) pairs")
    letters: list[str] = []
    for s in shapes:
        if not isinstance(s, (list, tuple)) or len(s) != 2:
            raise TemplateError("shape_row: each shape is a (letter, kind) pair")
        letter, kind = s
        if not isinstance(letter, str) or not re.fullmatch(r"[A-Z]", letter):
            raise TemplateError(f"shape_row: letter {letter!r} is not a single capital")
        if kind not in SHAPE_KINDS:
            raise TemplateError(f"shape_row: kind {kind!r} is not one of "
                                f"{', '.join(SHAPE_KINDS)}")
        if letter in letters:
            raise TemplateError(f"shape_row: letter {letter!r} is used twice")
        letters.append(letter)
    centre_pool = _unused_letters(set(letters),
                                  sum(1 for _, k in shapes if k in ("circle",
                                                                    "small_circle")))
    elements: list[dict] = []
    anchors: dict[str, XY] = {}
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    for i, (letter, kind) in enumerate(shapes):
        col, row = i % 3, i // 3
        cx = col * cell_w + cell_w / 2.0
        cy = row * row_h + 56.0
        if kind == "circle":
            elements.append(vc.circle((cx, cy), 34.0, id=f"sh{letter}"))
            bottom = (cx, cy + 34.0)
        elif kind == "small_circle":
            elements.append(vc.circle((cx, cy), 22.0, id=f"sh{letter}"))
            bottom = (cx, cy + 22.0)
        elif kind == "square":
            # a 4-corner polygon draws exactly like a rect but the coverage check
            # counts its EDGES — the letter's bottom anchor sits on one
            elements.append(vc.polygon([(cx - 29.0, cy - 29.0), (cx + 29.0, cy - 29.0),
                                        (cx + 29.0, cy + 29.0), (cx - 29.0, cy + 29.0)],
                                       id=f"sh{letter}"))
            bottom = (cx, cy + 29.0)
        elif kind == "rectangle":
            elements.append(vc.polygon([(cx - 38.0, cy - 22.0), (cx + 38.0, cy - 22.0),
                                        (cx + 38.0, cy + 22.0), (cx - 38.0, cy + 22.0)],
                                       id=f"sh{letter}"))
            bottom = (cx, cy + 22.0)
        elif kind == "triangle":
            elements.append(vc.polygon([(cx, cy - 30.0), (cx - 32.0, cy + 24.0),
                                        (cx + 32.0, cy + 24.0)], id=f"sh{letter}"))
            bottom = (cx, cy + 24.0)
        elif kind == "oval":
            elements.append(vc.polygon(
                [(cx + 44.0 * math.cos(math.radians(k * 360.0 / 28)),
                  cy + 27.0 * math.sin(math.radians(k * 360.0 / 28)))
                 for k in range(28)], id=f"sh{letter}"))
            bottom = (cx, cy + 27.0)
        else:   # semicircle — arc over the top, diameter flat on the bottom
            elements.append(vc.polygon(
                [vc.polar((cx, cy + 17.0), 34.0, dg) for dg in range(180, 361, 12)],
                id=f"sh{letter}"))
            bottom = (cx, cy + 17.0)
        anchors[letter] = bottom
        if kind in ("circle", "small_circle"):
            # the letter anchor sits on the rim — the coverage check reads outlines,
            # and `radius` is measured against this drawn circle element
            cname = centre_pool.pop(0)
            rad = 34.0 if kind == "circle" else 22.0
            anchors[cname] = (cx, cy)
            add(f"circle centre {cname} radius {rad:g}", "inferred",
                f"the outline of circle {letter}")
        elements.append(_float_label(f"lb{letter}", letter, bottom, gap=10.0, size=16))
        add(f'label "{letter}" names {letter}', "stem", f"the letter under the {kind}")
        add(f'describe "{letter} is {_SHAPE_DESCS[kind]}"', "inferred", "the shape's kind")
    n_curved = sum(1 for _, k in shapes if k in _CURVED_KINDS)
    add(f"derive {n_curved} + {len(shapes) - n_curved} = {len(shapes)}", "inferred",
        "curved + straight-sided shapes make the total")
    add("none tickMark parallelMark angleMark arrow dashed shaded", "inferred",
        "plain outlines and letters only")
    return finish(kind="shape_row", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=list(anchors), segments=[], claims=claims,
                  ask=ask, title=title or "A row of shapes",
                  description=description or
                  ("Shapes laid out in a single row" if len(shapes) <= 3 else
                   "Shapes laid out in rows of three") +
                  "; each shape has a letter label below it — every outline is "
                  "plain, unshaded and unmarked.",
                  scale="shape sizes are uniform icons — only the kinds matter",
                  medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# W11 — Grade 7 scale figures. The coordinate plane and the bar chart ride the
# audit's `axis` + `tick` + `reads` machinery (every claimed number projects onto a
# declared scale), and `parallel_lines` is the first template whose claim set uses
# `nonparallel` — the ≥5° tilt that makes a crossing honest.
# ────────────────────────────────────────────────────────────────────────────────
def _pick_label_spot(kind: str, text: str, size: float, anchor_xy: XY | None,
                     candidates: list[XY], strokes: list[tuple],
                     others: list[tuple], rivals: list[XY],
                     s_est: float) -> tuple[XY, tuple] | None:
    """First candidate centre whose `size`-pt box clears every stroke and label and —
    when `anchor_xy` is given — sits nearer it than any `rivals` anchor, all at the
    same rendered-px tolerances finish() applies. Fixed-label counterpart of the
    floater sweep, for spots the sweep's fixed steps can't reach."""
    w = _label_width(text, size)
    need_stroke = (STROKE_PX + SLACK_STROKE + 1.0) / s_est
    need_label = 4.0 / s_est
    need_own = OWN_FIXED_PX / s_est
    for cx, cy in candidates:
        box = (cx - w / 2, cy - MID_UP * size, cx + w / 2, cy + MID_DOWN * size)
        if strokes and min(_seg_rect_dist(a, b, box) - sw / 2
                           for a, b, sw in strokes) < need_stroke:
            continue
        if any(_rect_gap(box, pb[1:5]) < need_label for pb in others):
            continue
        if anchor_xy is not None and rivals:
            own = math.hypot(cx - anchor_xy[0], cy - anchor_xy[1])
            if min((math.hypot(cx - r[0], cy - r[1]) - own
                    for r in rivals), default=99.0) < need_own:
                continue
        return (cx, cy), box
    return None


_GRID_INK = "#d1d5db"          # light ruling ink — same convention as grid_polygon
_PL_TILT = (0.0, 16.0, 34.0, 52.0)   # tilt off `direction`: class-1 0°, class-2 16°,
                                     # unclassed lines take 34° then 52° — every pair
                                     # stays ≥12° apart by construction
_PL_GAP_MIN = 44.0             # smallest centre-to-centre stack gap (units)
_PL_DIST_PPU = 18.0            # perpendicular-distance label -> drawn units per unit
_PL_MARK_ATS = (0.5, 0.4, 0.6, 0.32, 0.68, 0.24, 0.76, 0.18, 0.82)
                               # fractional `at` positions tried for a parallelMark —
                               # the transversal hits every line's centre, so 0.5 is
                               # rarely legal when `crossing` is drawn
_BAR_FILLS = ("#1d4ed8", "#f59e0b", "#10b981")   # blue / amber / emerald
_BAR_OUTLINE = vc.INK
_PLACE_FAIL = re.compile(r"rendered px|no clear spot|canvas is .*past|h/w .*>")


def build_coordinate_plane(*, figure_id, stem, ask=None, title=None, description=None,
                           medium="english", x_max=None, y_max=None, points=None,
                           join=None, closed=False, sym_axis=None, guides=None,
                           grid=True, coords="stem", origin_label=False, unit_px=None):
    """A first-quadrant coordinate plane (L23 scope: INTEGER coords, axes from 0, no
    equation text). `points` = {letter: (x, y)}; `join` = lists of point names drawn
    as polylines (or polygons when `closed`); `sym_axis` = {"x": k} draws the vertical
    midline x = k dashed, {"y": k} the horizontal one; `guides` = point names that get
    dashed perpendiculars to both axes; `coords` = "stem" (each coordinate must be a
    stem number) or "figure" (read-the-figure mode — `reads` carry ev `inferred`)."""
    vc.reset_ids()
    for nm, v in (("x_max", x_max), ("y_max", y_max)):
        if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 10):
            raise TemplateError(f"coordinate_plane: {nm} must be an integer in 1..10 "
                                f"— got {v!r}")
    if coords not in ("stem", "figure"):
        raise TemplateError(f"coordinate_plane: coords must be 'stem' or 'figure' — got "
                            f"{coords!r}")
    pts: dict[str, tuple[int, int]] = {}
    for n, xy in (points or {}).items():
        if not isinstance(n, str) or not re.fullmatch(r"[A-Z]", n):
            raise TemplateError(f"coordinate_plane: point name {n!r} is not a single capital")
        if n in "OXY":
            raise TemplateError(f"coordinate_plane: {n} is reserved for the axes — pick "
                                f"another letter")
        try:
            px, py = xy
        except (TypeError, ValueError):
            raise TemplateError(f"coordinate_plane: point {n} must be an (x, y) pair — "
                                f"got {xy!r}") from None
        if not all(isinstance(c, (int, float)) and not isinstance(c, bool)
                   and float(c).is_integer() for c in (px, py)):
            raise TemplateError(f"coordinate_plane: {n} = {xy!r} — integer coordinates "
                                f"only (first-quadrant scope)")
        px, py = int(px), int(py)
        if not (0 <= px <= x_max and 0 <= py <= y_max):
            raise TemplateError(f"coordinate_plane: {n} = ({px}, {py}) lies outside "
                                f"[0, {x_max}] x [0, {y_max}]")
        if (px, py) in pts.values():
            raise TemplateError(f"coordinate_plane: two points sit at ({px}, {py}) — one "
                                f"dot cannot wear two letters")
        if (px, py) in ((0, 0), (x_max, 0), (0, y_max)):
            raise TemplateError(f"coordinate_plane: {n} = ({px}, {py}) sits on an axis "
                                f"anchor (O, X or Y) — its letter can never own the "
                                f"anchor; shift it off the axis end")
        pts[n] = (px, py)
    if coords == "stem":
        for n, (px, py) in pts.items():
            require_stem(stem, **{f"{n}'s x": px, f"{n}'s y": py})
    joins: list[list[str]] = []
    for path in (join or []):
        if not isinstance(path, (list, tuple)) or len(path) < 2:
            raise TemplateError("coordinate_plane: each `join` entry is a list of at "
                                "least two point names")
        for n in path:
            if n not in pts:
                raise TemplateError(f"coordinate_plane: join names {n!r}, which is not "
                                    f"one of the points")
        for a_, b_ in zip(path, path[1:]):
            if a_ == b_:
                raise TemplateError(f"coordinate_plane: a join step visits {a_} twice "
                                    f"in a row — a zero-length segment")
        joins.append(list(path))
    sym = None
    if sym_axis is not None:
        if not isinstance(sym_axis, dict) or len(sym_axis) != 1 or \
                next(iter(sym_axis)) not in ("x", "y"):
            raise TemplateError("coordinate_plane: sym_axis is {\"x\": k} (the vertical "
                                "midline) or {\"y\": k} (the horizontal one)")
        sk, sv = next(iter(sym_axis.items()))
        lim = x_max if sk == "x" else y_max
        if not isinstance(sv, (int, float)) or isinstance(sv, bool) or not (0 < sv < lim):
            raise TemplateError(f"coordinate_plane: the symmetry midline {sk}={sv!r} must "
                                f"be a number strictly inside (0, {lim})")
        if coords == "stem":
            require_stem(stem, **{f"the {sk} midline": float(sv)})
        sym = (sk, float(sv))
    gset: list[str] = []
    for n in (guides or []):
        if n not in pts:
            raise TemplateError(f"coordinate_plane: guide point {n!r} is not one of "
                                f"the points")
        gset.append(n)

    def assemble(unit: float):
        ov = max(10.0, 0.3 * unit)                    # arrowhead overhang past x_max/y_max
        elements: list[dict] = []
        if grid:
            for i in range(1, x_max + 1):
                elements.append({"id": f"gv{i}", "type": "line", "stroke":
                                 {"color": _GRID_INK, "width": 1},
                                 "points": [[i * unit, 0], [i * unit, -y_max * unit]]})
            for j in range(1, y_max + 1):
                elements.append({"id": f"gh{j}", "type": "line", "stroke":
                                 {"color": _GRID_INK, "width": 1},
                                 "points": [[0, -j * unit], [x_max * unit, -j * unit]]})
        elements.append({"id": "axX", "type": "arrow", "head": "end",
                         "points": [[0, 0], [x_max * unit + ov, 0]]})
        elements.append({"id": "axY", "type": "arrow", "head": "end",
                         "points": [[0, 0], [0, -y_max * unit - ov]]})
        for i in range(1, x_max + 1):                 # the lattice marks on each axis
            elements.append(vc.line((i * unit, -5), (i * unit, 5), id=f"tx{i}", width=1.5))
        for j in range(1, y_max + 1):
            elements.append(vc.line((-5, -j * unit), (5, -j * unit), id=f"ty{j}",
                                    width=1.5))
        # numerals — number_line's crowding rule, per axis: the printed set must equal
        # the union of the two arithmetic sequences, and the last numeral IS the axis
        # end, so the step must divide the max
        span_x = x_max * unit + 2 * ov + 2 * (26 + _label_width(f"{y_max:g}", 16))
        span_y = y_max * unit + 2 * ov + 80.0
        num_gap_x = _clearance_units(4.0, span_x)
        wlab_x = max(_label_width(f"{v:g}", 16) for v in range(0, x_max + 1))
        fits_x = lambda k: x_max % k == 0 and k * unit >= wlab_x + num_gap_x  # noqa: E731
        step_x = next((k for k in _NICE_STEPS if fits_x(k)),
                      next((k for k in range(1, x_max + 1) if fits_x(k)), x_max))
        num_gap_y = _clearance_units(4.0, span_y)
        hlab = (MID_UP + MID_DOWN) * 16.0
        fits_y = lambda k: y_max % k == 0 and k * unit >= hlab + num_gap_y  # noqa: E731
        step_y = next((k for k in _NICE_STEPS if fits_y(k)),
                      next((k for k in range(1, y_max + 1) if fits_y(k)), y_max))
        nclr_x = _clearance_units(STROKE_PX + SLACK_STROKE + 1.0, span_x)
        for k in range(step_x, x_max + 1, step_x):    # 0 is the single origin numeral
            elements.append(vc.text((k * unit, 5 + MID_UP * 16.0 + nclr_x),
                                    f"{k:g}", id=f"nx{k}", size=16))
        wlab_y = max(_label_width(f"{v:g}", 16) for v in range(0, y_max + 1))
        nx_ = -(wlab_y / 2 + 5 + nclr_x)
        for k in range(step_y, y_max + 1, step_y):
            elements.append(vc.text((nx_, -k * unit), f"{k:g}", id=f"ny{k}", size=16))
        anchors: dict[str, XY] = {"O": (0.0, 0.0), "X": (x_max * unit, 0.0),
                                  "Y": (0.0, -y_max * unit)}
        for n in gset:                                # guides first — dots sit on top
            px, py = pts[n]
            cx, cy = px * unit, -py * unit
            if px:
                elements.append(vc.line((cx, cy), (cx, 0.0), id=f"gd{n}x", dashed=True))
            if py:
                elements.append(vc.line((cx, cy), (0.0, cy), id=f"gd{n}y", dashed=True))
        sym_pts: list[str] = []
        if sym:
            sk, sv = sym
            S, T = _unused_letters(set(pts) | {"O", "X", "Y"}, 2)
            s_a, s_b = ((sv * unit, 0.0), (sv * unit, -y_max * unit)) if sk == "x" \
                else ((0.0, -sv * unit), (x_max * unit, -sv * unit))
            anchors[S], anchors[T] = s_a, s_b
            elements.append(vc.line(s_a, s_b, id="sym", dashed=True, width=1.5))
            sym_pts = [S, T]
        for n, (px, py) in pts.items():
            cx, cy = px * unit, -py * unit
            anchors[n] = (cx, cy)
            elements.append({"id": f"pt{n}", "type": "point", "at": vc.P((cx, cy)),
                             "r": 3.5})
        join_segs: list[str] = []
        for pi, path in enumerate(joins):
            cpts = [(pts[n][0] * unit, -pts[n][1] * unit) for n in path]
            if closed and len(path) > 2:
                elements.append(vc.polygon(cpts, id=f"jn{pi}", stroke_width=2))
                ring = path + [path[0]]
            else:
                elements.append(vc.polyline(cpts, id=f"jn{pi}"))
                ring = path
            for a_, b_ in zip(ring, ring[1:]):
                if f"{a_}{b_}" not in join_segs:
                    join_segs.append(f"{a_}{b_}")
        elements.append(_float_label("axlX", "x", (x_max * unit + ov, 0.0),
                                     gap=4.0, size=16))
        elements.append(_float_label("axlY", "y", (0.0, -y_max * unit - ov),
                                     gap=4.0, size=16))
        # point letters and the shared "0" sit in SCORED pockets — fixed spots, not
        # `_near` floaters: a grid point's only clear pockets are slivers between the
        # ruling lines and join edges, and a floater's fixed-step sweep lands in them
        # by luck only. Each pocket is scored by the same clearances finish() applies,
        # PLUS visual-check's target rule — a label box must come within
        # 1.5·fontSize of SOME painted ink (stroke centrelines and dots both count),
        # which the far pockets of a wide-scaled canvas break.
        strokes = stroke_segments(elements)
        s_est = min(1.0, PLATE_INNER / (span_x + 1.6 * unit + 60.0))
        need_stroke = (STROKE_PX + SLACK_STROKE) / s_est
        need_label = 4.0 / s_est
        need_own = OWN_FIXED_PX / s_est
        placed: list[tuple] = []                  # boxes this pass committed
        fixed_boxes = label_boxes(elements, FS)

        def seat(cx, cy, text, size, offsets, rivals=(), first_ok=False):
            """(score, bx, by) — score <0 fails a rule. `first_ok` returns the FIRST
            legal offset (the list is then a preference order); otherwise the best."""
            w = _label_width(text, size)
            best = None
            for dx, dy in offsets:
                bx, by = cx + dx, cy + dy
                box = (bx - w / 2, by - MID_UP * size,
                       bx + w / 2, by + MID_DOWN * size)
                stroke_gap = min((_seg_rect_dist(a, b, box) - sw / 2
                                  for a, b, sw in strokes), default=99.0)
                paint_gap = min((_seg_rect_dist(a, b, box)
                                 for a, b, _s in strokes), default=99.0)
                label_gap = min((_rect_gap(box, pb[1:5])
                                 for pb in fixed_boxes + placed), default=99.0)
                own = math.hypot(bx - cx, by - cy)
                own_gap = min((math.hypot(bx - r[0], by - r[1]) - own
                               for r in rivals), default=99.0)
                score = min(stroke_gap - need_stroke, label_gap - need_label,
                            own_gap - need_own, 1.5 * size - 2.0 - paint_gap)
                if first_ok and score >= 0:
                    return (score, bx, by)
                if best is None or score > best[0]:
                    best = (score, bx, by)
            return best

        # the single "0" serves both axes (the audit unions the two sequences) — it sits
        # on the x-numeral row centred UNDER the origin first (the classic position —
        # the y-axis above it never reaches its box), then slightly off-centre seats,
        # then plain pockets outside the plot quadrant as a last resort.
        zw, zup, zdn = _label_width("0", 16), MID_UP * 16.0, MID_DOWN * 16.0
        zs = max(_clearance_units(STROKE_PX + SLACK_STROKE, span_x),
                 need_stroke) + 2.5
        z_off = [(0.0, zs + zup), (-(zw / 2 + 2.0), zs + zup),
                 (zw / 2 + 2.0, zs + zup), (-(zs + zw / 2), zs + zup),
                 (-(zs + zw / 2), 2.0)]
        z_off += [(sx * f * unit, sy * f * unit)
                  for f in (0.5, 0.42, 0.62, 0.72, 0.85)
                  for sx, sy in ((-1, 1), (-1, 0), (0, 1), (1, 1), (-1, -1))]
        best = seat(0.0, 0.0, "0", 16, z_off, first_ok=True)
        if best is None or best[0] < 0:
            raise TemplateError(
                "coordinate_plane: the shared \"0\" numeral found no seat that both "
                f"clears the axes and stays within 1.5×fontSize of the painted corner "
                f"(~{(best[0] if best else 0) * s_est:.1f} rendered px short)")
        elements.append(vc.text((best[1], best[2]), "0", id="n0", size=16))
        placed.append(("0", best[1] - zw / 2, best[2] - zup,
                       best[1] + zw / 2, best[2] + zdn))
        if origin_label:
            # the capital "O" is pocket-seated like the numerals, preferring the
            # classic corner down-LEFT of the origin — a floater's sweep stacks it
            # over the "0" instead (W11 review). Down-left first, then the rest of
            # the outside-quadrant ring; the "0"'s committed box is already in
            # `placed`, so the two can never collide.
            ow = _label_width("O", 16)
            o_off = [(sx * f * unit, sy * f * unit)
                     for f in (0.42, 0.33, 0.55, 0.68, 0.85)
                     for sx, sy in ((-1, 1), (-1, 0), (0, 1), (-1, -1), (1, 1))]
            rivals_o = [p for nm_, p in anchors.items() if nm_ != "O"]
            best = seat(0.0, 0.0, "O", 16, o_off, rivals_o, first_ok=True)
            if best is None or best[0] < 0:
                raise TemplateError(
                    "coordinate_plane: origin_label's \"O\" found no seat clear of the "
                    "axes, the \"0\" and the point letters — drop origin_label")
            elements.append(vc.text((best[1], best[2]), "O", id="org", size=16))
            placed.append(("O", best[1] - ow / 2, best[2] - MID_UP * 16.0,
                           best[1] + ow / 2, best[2] + MID_DOWN * 16.0))
        ring = tuple((sx * f * unit, sy * f * unit)
                     for f in (0.5, 0.42, 0.6, 0.72, 0.85, 0.33)
                     for sx, sy in ((1, -1), (-1, -1), (1, 1), (-1, 1),
                                    (1, 0), (-1, 0), (0, -1), (0, 1)))
        for n, (px, py) in pts.items():
            cx, cy = px * unit, -py * unit
            rivals = [anchors[m] for m in pts if m != n] + \
                     ([anchors["O"]] if origin_label else [])
            best = seat(cx, cy, n, 14, ring, rivals)
            if best is not None and best[0] >= 0:
                w = _label_width(n, 14)
                elements.append(vc.text((best[1], best[2]), n, id=f"lb{n}", size=14))
                placed.append((n, best[1] - w / 2, best[2] - MID_UP * 14.0,
                               best[1] + w / 2, best[2] + MID_DOWN * 14.0))
            else:
                raise TemplateError(
                    f"coordinate_plane: point {n}'s letter found no clear half-cell "
                    f"pocket (~{(best[0] if best else 0) * s_est:.1f} rendered px "
                    f"short) — the labels need room the strokes don't leave")
        return elements, anchors, sym_pts, join_segs, step_x, step_y, span_x

    ev_pts = "stem" if coords == "stem" else "inferred"
    units = [float(unit_px)] if unit_px is not None else \
        [u for u in (min(52.0, 430.0 / x_max, 300.0 / y_max) * f
                     for f in (1.0, 0.8, 0.62, 0.48)) if u >= 14]
    if not units:
        raise TemplateError("coordinate_plane: unit_px must be a positive number")
    err = None
    for u in units:
        elements, anchors, sym_pts, join_segs, step_x, step_y, span_x = assemble(u)
        claims: list[tuple[str, str, str]] = []

        def add(pred, ev, note=""):
            claims.append((pred, ev, note))
            return f"K{len(claims)}"

        add(f"axis OX from 0 to {x_max:g}", "inferred", "the x extent is layout")
        add(f"axis OY from 0 to {y_max:g}", "inferred", "the y extent is layout")
        add(f"tick OX step {step_x}", "inferred",
            "a numeral at every integer" if step_x == 1 else
            f"numerals every {step_x} integers — closer would crowd at this canvas width")
        add(f"tick OY step {step_y}", "inferred",
            "a numeral at every integer" if step_y == 1 else
            f"numerals every {step_y} integers — closer would crowd at this canvas width")
        add("right X O Y", "inferred", "the axes are perpendicular")
        for n, (px, py) in pts.items():
            add(f"reads {n} {px:g} on OX", ev_pts, f"{n}'s x coordinate")
            add(f"reads {n} {py:g} on OY", ev_pts, f"{n}'s y coordinate")
        if sym:
            sk, sv = sym
            ax_ = "OX" if sk == "x" else "OY"
            add(f"reads {sym_pts[0]} {sv:g} on {ax_}", ev_pts,
                "the dashed midline's lower end")
            add(f"reads {sym_pts[1]} {sv:g} on {ax_}", ev_pts,
                "the dashed midline's upper end")
            add(f"paint {sym_pts[0]}{sym_pts[1]} dashed", "inferred",
                "the symmetry axis is drawn broken")
        for n in gset:
            add(f'describe "dashed guides run from {n} to both axes"', "inferred",
                "the guide pair under the point")
        add(f"derive {x_max:g} + {y_max:g} = {x_max + y_max:g}", "inferred",
            "the two axis extents bound the plane")
        if coords == "figure":
            add('describe "the marked positions are figure content — the question asks '
                'the student to read them"', "inferred", "read-the-figure mode")
        # labels — one claim per drawn glyph; the numeral claims bind numeric targets so
        # the scale check sees them, "x"/"y" name the axis segments, "0" serves both axes
        add('label "x" names OX', "inferred", "the axis letter")
        add('label "y" names OY', "inferred", "the axis letter")
        claimed_nums = set()
        for k in range(0, x_max + 1, step_x):
            claimed_nums.add(k)
        for k in range(0, y_max + 1, step_y):
            claimed_nums.add(k)
        for k in sorted(claimed_nums):
            add(f'label "{k:g}" names {k:g}', ev_pts, "a printed numeral")
        for n in pts:
            add(f'label "{n}" names {n}', ev_pts, "a marked point")
        if origin_label:
            add('label "O" names O', "stem", "the origin letter")
        dashed_drawn = bool(sym or gset)
        add("none tickMark parallelMark angleMark angleArc" +
            (" " if dashed_drawn else " dashed ") + "shaded", "inferred",
            "no marks beyond the axis arrowheads" +
            ("" if dashed_drawn else " — nothing is dashed"))
        elements_n = len(elements)
        try:
            return finish(kind="coordinate_plane", figure_id=figure_id, stem=stem,
                          elements=elements, anchors=anchors,
                          points=["O", "X", "Y"] + list(pts) + sym_pts,
                          segments=["OX", "OY"] + join_segs +
                                   ([f"{sym_pts[0]}{sym_pts[1]}"] if sym else []),
                          claims=claims, ask=ask,
                          title=title or "A coordinate plane",
                          description=description or (
                              f"A coordinate plane with the axes running 0 to {x_max} "
                              f"and 0 to {y_max}" +
                              (f"; points {', '.join(pts)} are marked" if pts else "") +
                              (" and joined" if joins else "") +
                              ("; a dashed symmetry line crosses the plane" if sym else "")
                              + "."),
                          scale="to scale — both axes are true linear maps",
                          budget=elements_n if elements_n > 32 else None,
                          departures=([f"{elements_n} elements — one short line per grid "
                                       "cell edge and tick"] if elements_n > 32 else None),
                          medium=medium)
        except TemplateError as e:
            if unit_px is not None or not _PLACE_FAIL.search(str(e)) or \
                    "canvas is" in str(e):   # an aspect refusal is not a cell-size issue
                raise
            err = e
    raise TemplateError(f"coordinate_plane: no cell size inside the width cap lays the "
                        f"figure out cleanly ({err}) — pass grid=False or fewer points")


def build_parallel_lines(*, figure_id, stem, ask=None, title=None, description=None,
                         medium="english", lines=None, parallel=None, direction=0.0,
                         crossing=None, distance=None, length=None):
    """A stack of straight lines, some parallel. `lines` = 2–4 two-capital names with
    all endpoint letters distinct; `parallel` = 1–2 classes of line names (each ≥2);
    `direction` = degrees of the first class (0 = horizontal, screen-clockwise);
    `crossing` = a two-capital name for a transversal through every line;
    `distance` = {"between": [two ADJACENT same-class lines], "value": v, "unit": "cm"}
    draws the perpendicular MN with the right-angle mark at its foot N and the spacing
    drawn at value x _PL_DIST_PPU. Unclassed lines tilt ≥12° off every other; drawn
    segments never cross except `crossing`."""
    vc.reset_ids()
    if not isinstance(lines, (list, tuple)) or not (2 <= len(lines) <= 4):
        raise TemplateError("parallel_lines: `lines` must be a list of 2–4 segment names")
    seen: dict[str, str] = {}
    for nm in lines:
        if not isinstance(nm, str) or not re.fullmatch(r"[A-Z]{2}", nm) or nm[0] == nm[1]:
            raise TemplateError(f"parallel_lines: line name {nm!r} must be two DISTINCT "
                                f"capitals")
        for ch in nm:
            if ch in seen:
                raise TemplateError(f"parallel_lines: letter {ch} is used by both "
                                    f"{seen[ch]} and {nm} — every endpoint letter must "
                                    f"be distinct")
            seen[ch] = nm
    if not isinstance(parallel, (list, tuple)) or not (1 <= len(parallel) <= 2):
        raise TemplateError("parallel_lines: `parallel` must be a list of 1–2 classes")
    cls_of: dict[str, int] = {}
    for ci, cls in enumerate(parallel):
        if not isinstance(cls, (list, tuple)) or len(cls) < 2:
            raise TemplateError("parallel_lines: each parallel class needs ≥2 lines")
        for nm in cls:
            if nm not in lines:
                raise TemplateError(f"parallel_lines: class member {nm!r} is not in `lines`")
            if nm in cls_of:
                raise TemplateError(f"parallel_lines: {nm} is in two parallel classes")
            cls_of[nm] = ci
    if not isinstance(direction, (int, float)) or isinstance(direction, bool):
        raise TemplateError(f"parallel_lines: direction must be degrees — got "
                            f"{direction!r}")
    tilt: dict[str, float] = {}
    extra = [34.0, 52.0]
    for nm in lines:
        tilt[nm] = _PL_TILT[cls_of[nm]] if nm in cls_of else extra.pop(0)
    if crossing is not None:
        if not isinstance(crossing, str) or not re.fullmatch(r"[A-Z]{2}", crossing) \
                or crossing[0] == crossing[1] or any(ch in seen for ch in crossing):
            raise TemplateError(f"parallel_lines: crossing {crossing!r} must be two "
                                f"distinct capitals not used by any line")
        for ch in crossing:
            seen[ch] = crossing
    dist_idx = None
    if distance is not None:
        if not isinstance(distance, dict):
            raise TemplateError("parallel_lines: distance is a dict "
                                "{\"between\": [l1, l2], \"value\": n, \"unit\": s}")
        pair = distance.get("between")
        val, unit_s = distance.get("value"), distance.get("unit")
        if (not isinstance(pair, (list, tuple)) or len(pair) != 2 or
                pair[0] not in lines or pair[1] not in lines or pair[0] == pair[1]):
            raise TemplateError("parallel_lines: distance['between'] must be two "
                                "different lines")
        if cls_of.get(pair[0]) is None or cls_of.get(pair[0]) != cls_of.get(pair[1]):
            raise TemplateError(f"parallel_lines: a perpendicular distance only exists "
                                f"between two PARALLEL lines — {pair[0]} and {pair[1]} "
                                f"are not in one class")
        i0, i1 = sorted(lines.index(nm) for nm in pair)
        if i1 - i0 != 1:
            raise TemplateError(f"parallel_lines: {pair[0]} and {pair[1]} are not "
                                f"adjacent in `lines` — the perpendicular would cross "
                                f"the line(s) between them")
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val <= 0:
            raise TemplateError("parallel_lines: distance['value'] must be a positive "
                                "number")
        if not isinstance(unit_s, str) or not unit_s.strip():
            raise TemplateError("parallel_lines: distance['unit'] must be a non-empty "
                                "string like 'cm'")
        _check_label_texts([], [unit_s], medium)   # it prints inside the "v unit" label
        require_stem(stem, distance_value=val)
        for ch in "MN":
            if ch in seen:
                raise TemplateError("parallel_lines: letters M and N are reserved for "
                                    "the perpendicular's feet")
        seen["M"] = seen["N"] = "MN"
        dist_idx = (i0, i1, float(val), unit_s.strip())
    L = float(length or 170.0)
    if L <= 0:
        raise TemplateError(f"parallel_lines: length must be positive — got {length!r}")

    d = math.radians(float(direction))
    u_n = (-math.sin(d), math.cos(d))                  # the stack direction
    u_dir = {nm: (math.cos(d + math.radians(tilt[nm])),
                  math.sin(d + math.radians(tilt[nm]))) for nm in lines}
    centres: list[XY] = []
    seg_pts: dict[str, tuple[XY, XY]] = {}
    for L in (L, L * 0.78, L * 0.6):        # a near-vertical stack is bounded by the
        centres = [(0.0, 0.0)]              # canvas aspect — shorten the lines instead
        for i in range(1, len(lines)):
            h_prev = (L / 2) * abs(math.sin(math.radians(tilt[lines[i - 1]])))
            h_cur = (L / 2) * abs(math.sin(math.radians(tilt[lines[i]])))
            need = max(_PL_GAP_MIN, h_prev + h_cur + 20.0)
            if dist_idx and dist_idx[1] == i:         # the named pair's gap carries its label
                forced = dist_idx[2] * _PL_DIST_PPU / \
                    math.cos(math.radians(tilt[lines[i]]))
                if forced < need:
                    raise TemplateError(
                        f"parallel_lines: distance {dist_idx[2]:g} draws the lines "
                        f"{forced:.0f} units apart — the tilted lines need ≥ "
                        f"{need:.0f} to stay clear; raise the distance value")
                need = forced
            centres.append((centres[-1][0] + need * u_n[0],
                            centres[-1][1] + need * u_n[1]))
        seg_pts = {}
        for i, nm in enumerate(lines):
            ux, uy = u_dir[nm]
            seg_pts[nm] = ((centres[i][0] - ux * L / 2, centres[i][1] - uy * L / 2),
                           (centres[i][0] + ux * L / 2, centres[i][1] + uy * L / 2))
        # endpoint letters name ENDS — two different lines' ends nearer than ~1.5×font
        # size in the render make a letter read on the wrong line (W11 review). Sliding
        # a line along its own direction moves its ENDS but not its axis — the stack
        # gaps, the drawn MN spacing and every parallel/nonparallel claim survive.
        shifts = [0.0] * len(lines)
        for _sep in range(12):
            xs = [p[0] for ab in seg_pts.values() for p in ab]
            s_it = min(1.0, PLATE_INNER / (max(xs) - min(xs) + 130.0))
            sep = (1.5 * FS + 2.0) / s_it               # ~24 rendered px, as units
            worst = None
            for i in range(len(lines)):
                for j in range(i + 1, len(lines)):
                    for pa in seg_pts[lines[i]]:
                        for pb in seg_pts[lines[j]]:
                            dd = vc.dist(pa, pb)
                            if dd < sep and (worst is None or dd < worst[0]):
                                worst = (dd, i, j)
            if worst is None:
                break
            dd, i, j = worst
            ux, uy = u_dir[lines[j]]
            pa = min(seg_pts[lines[i]],
                     key=lambda p: min(vc.dist(p, q) for q in seg_pts[lines[j]]))
            pb = min(seg_pts[lines[j]], key=lambda p: vc.dist(p, pa))
            sgn = 1.0 if (pb[0] - pa[0]) * ux + (pb[1] - pa[1]) * uy >= 0 else -1.0
            step = sep - dd + 4.0
            if abs(shifts[j] + sgn * step) > L * 0.22:
                raise TemplateError(
                    f"parallel_lines: {lines[i]} and {lines[j]}'s ends sit ~{dd:.0f} "
                    f"units apart — too close to letter unambiguously, and sliding "
                    f"{lines[j]} further would unseat its marks; try fewer lines or "
                    f"a shallower `direction`")
            shifts[j] += sgn * step
            centres[j] = (centres[j][0] + ux * sgn * step,
                          centres[j][1] + uy * sgn * step)
            seg_pts[lines[j]] = ((centres[j][0] - ux * L / 2,
                                  centres[j][1] - uy * L / 2),
                                 (centres[j][0] + ux * L / 2,
                                  centres[j][1] + uy * L / 2))
        else:
            raise TemplateError("parallel_lines: the endpoint letters cannot be kept "
                                "1.5×fontSize apart — the tilts pack the ends too "
                                "tightly; try fewer lines or another `direction`")
        xs = [p[0] for ab in seg_pts.values() for p in ab]
        ys = [p[1] for ab in seg_pts.values() for p in ab]
        est_w = max(xs) - min(xs) + 70.0
        est_h = max(ys) - min(ys) + 70.0
        if max(est_w, est_h) <= 1.9 * min(est_w, est_h):
            break
    else:
        raise TemplateError("parallel_lines: no line length keeps this stack inside "
                            "the canvas aspect — try a shallower `direction` or "
                            "fewer lines")
    for i in range(len(lines)):                       # defensive: the gap rule is exact,
        for j in range(i + 1, len(lines)):            # verify it anyway
            if cls_of.get(lines[i]) is not None and \
                    cls_of.get(lines[i]) == cls_of.get(lines[j]):
                continue                              # parallel — never cross
            if _seg_seg_dist(*seg_pts[lines[i]], *seg_pts[lines[j]]) < 2.0:
                raise TemplateError(f"parallel_lines: the layout cannot keep {lines[i]} "
                                    f"and {lines[j]} from touching")
    cr_pts = None
    if crossing:
        c_mid = ((centres[0][0] + centres[-1][0]) / 2,
                 (centres[0][1] + centres[-1][1]) / 2)
        th_c = d + math.pi / 2            # perpendicular to the STACK — crosses every
        for nm in lines:                  # line at its centre whatever its tilt
            off = abs((math.degrees(th_c - d - math.radians(tilt[nm])) + 90)
                      % 180 - 90)
            if off < 5.0:
                raise TemplateError(f"parallel_lines: the crossing sits only {off:.1f}° "
                                    f"off {nm} — `nonparallel` needs ≥5°")
        uc = (math.cos(th_c), math.sin(th_c))
        half = (vc.dist(centres[0], centres[-1])) / 2 + 30.0
        cr_pts = ((c_mid[0] - uc[0] * half, c_mid[1] - uc[1] * half),
                  (c_mid[0] + uc[0] * half, c_mid[1] + uc[1] * half))
        for nm in lines:
            ix = vc.intersect(cr_pts[0], cr_pts[1], *seg_pts[nm])
            if _pt_seg(ix, *seg_pts[nm]) > 1.0:
                raise TemplateError(f"parallel_lines: crossing {crossing} cannot reach "
                                    f"{nm} inside its drawn length")
    # a parallelMark is real ink — with a transversal or the MN perpendicular drawn its
    # chevrons must stand ≥8 rendered px clear of those strokes or the mark reads
    # struck-through. The crossing hits each line's centre, so the default `at` = 0.5
    # is usually illegal — probe positions along the line until the marks clear
    # (W11 review, MAJOR 2). The MN candidates are then filtered against the CHOSEN
    # mark positions, so whichever perpendicular the label probing picks stays clear.
    s_est = min(1.0, PLATE_INNER / (est_w + 60.0))
    pm_need = (8.0 + 2.0) / s_est           # 8 rendered px + the two strokes' half-widths

    def _mark_clears(nm, t):
        a_, b_ = seg_pts[nm]
        probe = stroke_segments(
            vc.parallel_marks(a_, b_, cls_of[nm] + 1, at=t, size=10))
        return cr_pts is None or all(
            _seg_seg_dist(p, q, cr_pts[0], cr_pts[1]) >= pm_need
            for p, q, _w in probe)

    # same class ⇒ same `at`: the chevrons of parallel lines must sit on the same
    # side of a transversal or the mark reads as decoration, not a class symbol
    # (W11 review round 3). Try every candidate as a SHARED position first; only
    # when no single `at` clears the crossing for every member does a class fall
    # back to per-line picks.
    mark_at: dict[str, float] = {}
    by_class: dict[int, list[str]] = {}
    for nm in lines:
        if nm in cls_of:
            by_class.setdefault(cls_of[nm], []).append(nm)
    for members in by_class.values():
        shared = next((t for t in _PL_MARK_ATS
                       if all(_mark_clears(nm, t) for nm in members)), None)
        if shared is not None:
            for nm in members:
                mark_at[nm] = shared
            continue
        for nm in members:
            for t in _PL_MARK_ATS:
                if _mark_clears(nm, t):
                    mark_at[nm] = t
                    break
            else:
                raise TemplateError(
                    f"parallel_lines: no spot on {nm} keeps its parallel mark 8 px "
                    f"clear of the crossing — drop `crossing` or give the lines "
                    f"another `direction`")
    mark_strokes = stroke_segments([el for nm in lines if nm in cls_of
                                    for el in vc.parallel_marks(
                                        *seg_pts[nm], cls_of[nm] + 1,
                                        at=mark_at[nm], size=10)])
    mn_cands: list[tuple] = []
    if dist_idx:
        i0, i1, val, unit_s = dist_idx
        lm, ln = lines[i0], lines[i1]
        m_seg, n_seg = seg_pts[lm], seg_pts[ln]
        # with a transversal the channel's mid-zone is crossed — park the
        # perpendicular near a line end so the value label gets the long run
        t_opts = ((0.15, 0.22, 0.85, 0.78, 0.10, 0.90, 0.30, 0.70, 0.45, 0.55)
                  if cr_pts else
                  (0.62, 0.70, 0.55, 0.78, 0.45, 0.85, 0.35, 0.30, 0.90))
        for t_par in t_opts:
            M_ = vc.lerp(m_seg[0], m_seg[1], t_par)
            N_ = vc.foot_of_perpendicular(M_, *n_seg)
            t_n = ((N_[0] - n_seg[0][0]) * (n_seg[1][0] - n_seg[0][0]) +
                   (N_[1] - n_seg[0][1]) * (n_seg[1][1] - n_seg[0][1])) / (L * L)
            if not (0.08 <= t_n <= 0.92):
                continue
            # the value label lives in the channel beside MN — keep the crossing
            # (which runs parallel to MN) a label-width away
            if cr_pts and _seg_seg_dist(M_, N_, *cr_pts) < 30.0:
                continue
            if any(_seg_seg_dist(M_, N_, p, q) < pm_need
                   for p, q, _w in mark_strokes):
                continue                            # would strike through a mark
            if abs(vc.dist(M_, N_) - val * _PL_DIST_PPU) > 1e-6 * L:
                continue
            mn_cands.append((M_, N_))
        if not mn_cands:
            raise TemplateError(f"parallel_lines: the perpendicular between {lm} and "
                                f"{ln} cannot land inside both drawn segments (the "
                                f"crossing and the tilt leave no room)")
    elements: list[dict] = []
    anchors: dict[str, XY] = {}
    for nm in lines:
        a_, b_ = seg_pts[nm]
        elements.append(vc.line(a_, b_, id=f"ln{nm}", width=2.5))
        if nm in cls_of:
            elements += vc.parallel_marks(a_, b_, cls_of[nm] + 1, at=mark_at[nm],
                                          size=10)
        for k, p in ((0, a_), (1, b_)):
            anchors[nm[k]] = p
            elements.append(_float_label(f"lb{nm[k]}", nm[k], p, gap=8.0, size=16))
    if cr_pts:
        elements.append(vc.line(*cr_pts, id=f"ln{crossing}", width=2))
        for k, p in enumerate(cr_pts):
            anchors[crossing[k]] = p
            elements.append(_float_label(f"lb{crossing[k]}", crossing[k], p,
                                         gap=8.0, size=16))
    mn = None
    if mn_cands:
        # the junctions are where every stroke meets — fixed spots, not floaters:
        # feet letters outside the strip, the value text sliding along the channel.
        # Probe each candidate perpendicular for label room before committing.
        u_par = vc.unit(m_seg[0], m_seg[1])
        base_boxes = label_boxes(elements, FS)
        for M_, N_ in mn_cands:
            probe = [{"id": "dist", "type": "line", "points": [list(M_), list(N_)],
                      "stroke": {"width": 2}}] + \
                    vc.right_angle_mark(N_, M_, seg_pts[ln][1], r=12)
            strokes = stroke_segments(elements + probe)
            u_mn = vc.unit(M_, N_)
            placed: list[tuple] = []
            spots: list[tuple[str, XY]] = []
            for letter, base, u_out in (("M", M_, (-u_mn[0], -u_mn[1])),
                                        ("N", N_, u_mn)):
                cands = [(base[0] + u_out[0] * t + u_par[0] * s_,
                          base[1] + u_out[1] * t + u_par[1] * s_)
                         for t in (14.0, 20.0, 27.0, 36.0)
                         for s_ in (0.0, 14.0, -14.0, 26.0, -26.0, 42.0, -42.0,
                                    58.0, -58.0)]
                cands += [(base[0] - u_out[0] * t + u_par[0] * s_,   # inside the
                           base[1] - u_out[1] * t + u_par[1] * s_)  # strip
                          for t in (13.0, 20.0, 27.0, 34.0, 44.0)
                          for s_ in (26.0, -26.0, 38.0, -38.0, 14.0, -14.0,
                                     52.0, -52.0, 66.0, -66.0)]
                other_foot = N_ if letter == "M" else M_
                rivals = [p for nm, p in anchors.items()] + [other_foot]
                spot = _pick_label_spot("parallel_lines", letter, 16, base, cands,
                                        strokes, base_boxes + placed, rivals, s_est)
                if spot is None:
                    break
                spots.append((letter, spot[0]))
                placed.append((letter, *spot[1]))
            else:
                mid = ((M_[0] + N_[0]) / 2, (M_[1] + N_[1]) / 2)
                half_mn = vc.dist(M_, N_) / 2
                v_cands = [(mid[0] + u_par[0] * s_ + u_mn[0] * t,
                            mid[1] + u_par[1] * s_ + u_mn[1] * t)
                           for s_ in (0.0, 15.0, -15.0, 25.0, -25.0, 38.0, -38.0,
                                      52.0, -52.0, 66.0, -66.0)
                           for t in (0.0, 9.0, -9.0)]
                # outside the strip on either side, sliding past the foot letters
                v_cands += [(M_[0] - u_mn[0] * t + u_par[0] * s_,
                             M_[1] - u_mn[1] * t + u_par[1] * s_)
                            for t in (18.0, 28.0)
                            for s_ in (26.0, -26.0, 40.0, -40.0, 55.0, -55.0)]
                v_cands += [(N_[0] + u_mn[0] * t + u_par[0] * s_,
                             N_[1] + u_mn[1] * t + u_par[1] * s_)
                            for t in (18.0, 28.0)
                            for s_ in (26.0, -26.0, 40.0, -40.0, 55.0, -55.0)]
                v_cands += [(mid[0] + u_mn[0] * t, mid[1] + u_mn[1] * t)
                            for t in (half_mn + 16.0, -(half_mn + 16.0))]
                vspot = _pick_label_spot("parallel_lines",
                                         f"{dist_idx[2]:g} {dist_idx[3]}", 14, None,
                                         v_cands, strokes, base_boxes + placed,
                                         [], s_est)
                if vspot is not None:
                    elements += probe
                    anchors["M"], anchors["N"] = M_, N_
                    for letter, at_ in spots:
                        elements.append(vc.text(at_, letter, id=f"lb{letter}",
                                                size=16))
                    elements.append(vc.text(vspot[0], f"{dist_idx[2]:g} "
                                            f"{dist_idx[3]}", id="lbMN", size=14))
                    mn = (M_, N_, lm, ln)
                    break
        if mn is None:
            raise TemplateError(
                f"parallel_lines: no position for the perpendicular between {lm} and "
                f"{ln} leaves room for its letters and the distance label — fewer "
                f"lines, or no crossing")
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    def off_deg(m1, m2):
        return abs((tilt[m1] - tilt[m2] + 90) % 180 - 90)

    n_par = n_non = 0
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            if cls_of.get(lines[i]) is not None and \
                    cls_of.get(lines[i]) == cls_of.get(lines[j]):
                add(f"parallel {lines[i]} {lines[j]}", "inferred",
                    "one parallel class — the marks say so")
                n_par += 1
            else:
                add(f"nonparallel {lines[i]} {lines[j]}", "inferred",
                    f"drawn {off_deg(lines[i], lines[j]):g}° apart")
                n_non += 1
    for ci, cls in enumerate(parallel):
        arrows = ("one arrow", "two arrows")[ci] if ci < 2 else f"{ci + 1} arrows"
        add(f'describe "the parallel mark on {" and ".join(cls)} is {arrows}"',
            "inferred", f"parallelMark count {ci + 1} identifies this class")
    if cr_pts:
        for nm in lines:
            add(f"nonparallel {crossing} {nm}", "inferred",
                "the transversal meets every line — no angle marks claimed (L07 scope)")
    for nm in lines:
        for ch in nm:
            add(f'label "{ch}" names {ch}', "stem", "an endpoint letter")
    if cr_pts:
        for ch in crossing:
            add(f'label "{ch}" names {ch}', "stem", "the transversal's endpoint")
    if mn:
        M_, N_, lm, ln = mn
        add(f"on M {lm}", "inferred", "the perpendicular starts on the first line")
        add(f"on N {ln}", "inferred", "the perpendicular ends on the second")
        add('label "M" names M', "stem", "the perpendicular's foot letter")
        add('label "N" names N', "stem", "the perpendicular's other foot letter")
        add(f"right M N {ln[1]}", "inferred",
            "the right-angle mark sits at the foot of the perpendicular")
        add(f'label "{dist_idx[2]:g} {dist_idx[3]}" names MN', "stem",
            "the perpendicular distance the stem states")
        add(f'describe "MN is the perpendicular distance between {lm} and {ln}"',
            "inferred", "the lambawa (perpendicular) segment")
    n = len(lines)
    add(f"derive {n} * {n - 1} / 2 = {n * (n - 1) // 2}", "inferred",
        f"the {n} lines make {n * (n - 1) // 2} unordered pairs — {n_par} claimed "
        f"parallel, {n_non} nonparallel"
        + (f"; the transversal adds {n} further nonparallel claims" if cr_pts else ""))
    add("none tickMark angleArc dashed arrow shaded" + ("" if mn else " angleMark"),
        "inferred", "parallel marks only" +
        (", plus the one right-angle mark at N" if mn else " — no angle marks at all"))
    elements_n = len(elements)
    return finish(kind="parallel_lines", figure_id=figure_id, stem=stem,
                  elements=elements, anchors=anchors, points=list(anchors),
                  segments=list(lines) + ([crossing] if cr_pts else []) +
                           (["MN"] if mn else []),
                  claims=claims, ask=ask,
                  title=title or "Parallel lines",
                  description=description or (
                      f"{n} straight line{'s are' if n != 1 else ' is'} shown, each "
                      f"endpoint lettered" +
                      (f"; {n_par} parallel pair{'s are' if n_par != 1 else ' is'} "
                       f"marked with arrow marks" if n_par else "") +
                      (f"; a transversal {crossing} crosses all of them" if cr_pts
                       else "") +
                      (f"; the perpendicular distance between {mn[2]} and {mn[3]} is "
                       f"marked with a right-angle square" if mn else "") + "."),
                  scale="the drawn angles are the claimed ones; segment lengths are not "
                        "to scale" + (", except the marked perpendicular spacing"
                                    if mn else ""),
                  budget=elements_n if elements_n > 32 else None,
                  departures=([f"{elements_n} elements — letter floaters, marks and "
                               "the dashed/transversal strokes"] if elements_n > 32
                              else None),
                  medium=medium)


def build_bar_chart(*, figure_id, stem, ask=None, title=None, description=None,
                    medium="english", categories=None, series=None, step=None,
                    v_max=None, values="stem", value_title=None, category_title=None,
                    gridlines=True):
    """A vertical bar chart (L26 scope: simple or grouped bars only). `categories` =
    2–8 label strings printed under the groups; `series` = 1–3 dicts
    {"name": str, "values": [one per category]} — one series draws no legend; `step`
    is the value-axis interval (stem-checked, always); `v_max` defaults to the smallest
    multiple of step ≥ the largest bar. Every bar top is anchor T1..Tn — the `reads`
    claim is what makes the height auditable. `values="figure"` is the honest
    read-the-figure mode (ev `inferred`, no stem check)."""
    vc.reset_ids()
    if not isinstance(categories, (list, tuple)) or not (2 <= len(categories) <= 8):
        raise TemplateError("bar_chart: categories must be a list of 2–8 label strings")
    cats = []
    for c in categories:
        if not isinstance(c, str) or not c.strip():
            raise TemplateError(f"bar_chart: a category label must be non-empty text — "
                                f"got {c!r}")
        cats.append(c.strip())
    if not isinstance(series, (list, tuple)) or not (1 <= len(series) <= 3):
        raise TemplateError("bar_chart: series must be a list of 1–3 "
                            "{\"name\": str, \"values\": [...]} dicts")
    srs = []
    for i, s in enumerate(series):
        if not isinstance(s, dict) or not isinstance(s.get("values"), (list, tuple)):
            raise TemplateError(f"bar_chart: series {i} must be a dict with a values list")
        vals = list(s["values"])
        if len(vals) != len(cats):
            raise TemplateError(f"bar_chart: series {i} has {len(vals)} values for "
                                f"{len(cats)} categories")
        name = s.get("name") or ""
        if not isinstance(name, str):
            raise TemplateError(f"bar_chart: series {i} name must be text — got {name!r}")
        if len(series) > 1 and not name.strip():
            raise TemplateError("bar_chart: every series in a multi-series chart needs a "
                                "name — the legend prints it")
        srs.append((name.strip(), vals))
    n_cat, n_ser = len(cats), len(srs)
    if values not in ("stem", "figure"):
        raise TemplateError(f"bar_chart: values must be 'stem' or 'figure' — got "
                            f"{values!r}")
    if not isinstance(step, (int, float)) or isinstance(step, bool) or step <= 0:
        raise TemplateError(f"bar_chart: step must be a positive number — got {step!r}")
    require_stem(stem, step=step)
    vmax = max((v for _n, vs in srs for v in vs), default=0)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
               for v in [v for _n, vs in srs for v in vs]):
        raise TemplateError("bar_chart: every bar value must be a non-negative number")
    half = step / 2
    for _n, vs in srs:
        for v in vs:
            if abs(v / half - round(v / half)) > 1e-9:
                raise TemplateError(f"bar_chart: value {v:g} is not a multiple of "
                                    f"step/2 ({half:g}) — a bar must land on the axis's "
                                    f"half-step lattice to be readable")
    if v_max is None:
        v_max = step * max(2, math.ceil(vmax / step))
    if not isinstance(v_max, (int, float)) or isinstance(v_max, bool) or v_max <= 0:
        raise TemplateError(f"bar_chart: v_max must be a positive number — got {v_max!r}")
    n_steps = v_max / step
    if abs(n_steps - round(n_steps)) > 1e-9 or not (2 <= round(n_steps) <= 12):
        raise TemplateError(f"bar_chart: v_max {v_max:g} must be a multiple of step "
                            f"{step:g} giving 2–12 steps — got {n_steps:g} steps")
    n_steps = int(round(n_steps))
    if vmax > v_max + 1e-9:
        raise TemplateError(f"bar_chart: a bar value ({vmax:g}) exceeds v_max "
                            f"({v_max:g}) — raise v_max")
    if values == "stem":
        require_stem(stem, **{f"bar {i + 1}": v
                              for i, v in enumerate(v for _n, vs in srs for v in vs)})
    for lbl, wh_ in (("value_title", value_title), ("category_title", category_title)):
        if wh_ is not None and (not isinstance(wh_, str) or not wh_.strip()):
            raise TemplateError(f"bar_chart: {lbl} must be non-empty text when given")
    # every user text below becomes a VDD label — check the raw-character/medium rules
    # up front so a `$` or a backtick is a stated refusal, not vc.text's assert
    _check_label_texts([], cats + [nm for nm, _v in srs] +
                       [t for t in (value_title, category_title) if t], medium)
    _distinct_glyphs("bar_chart",
                     [f"{k * step:g}" for k in range(int(round(n_steps)) + 1)] + cats +
                     ([nm for nm, _v in srs] if n_ser > 1 else []) +
                     ([value_title] if value_title else []) +
                     ([category_title] if category_title else []))

    # ── layout — bar sizes adapt to the category count, bounded by the 560-unit cap ──
    plot_h = 240.0
    uv = plot_h / v_max                       # canvas units per unit of value
    cat_w = [_label_width(c, 14) for c in cats]
    title_w = _label_width(value_title, 16) if value_title else 0.0
    # the head row (value title + legend swatches/names) sits ABOVE the plot and may
    # outrun the baseline's width — the cap sees whichever is wider
    head_end = 8.0 + title_w
    # swatch -> name gap must clear the stroke rule at the final scale; the estimate
    # (a typical canvas) errs by a unit or two, which the +1.0 px margin absorbs
    sw_gap = _clearance_units(STROKE_PX + SLACK_STROKE + 1.0, 460.0)
    if n_ser > 1:
        head_end += (26.0 if title_w else 0.0) + \
            sum(14.0 + sw_gap + _label_width(nm, 14) + 24.0 for nm, _v in srs)
    chosen = None
    for bw in (30.0, 26.0, 22.0, 18.0, 15.0, 12.0):
        ig, gg = max(4.0, bw * 0.28), max(16.0, bw * 0.9)
        grp = n_ser * bw + (n_ser - 1) * ig
        pitch = grp + gg
        for i in range(n_cat - 1):
            pitch = max(pitch, cat_w[i] / 2 + cat_w[i + 1] / 2 + 14)
        plot_w = n_cat * pitch + 12.0
        if plot_w < 260.0:                    # keep the canvas from going tall (aspect)
            plot_w = 260.0
            pitch = (plot_w - 12.0) / n_cat
        span_x = max(plot_w, head_end)
        est_w = (max(_label_width(f"{k * step:g}", 16) for k in range(n_steps + 1))
                 + 22 + span_x + 2 * MARGIN + 20)
        if est_w <= 540.0:
            chosen = (bw, ig, pitch, grp, plot_w, est_w)
            break
    if chosen is None:
        raise TemplateError(f"bar_chart: {n_cat} categories x {n_ser} series need "
                            f"~{est_w:.0f} canvas units — the 560-unit cap admits "
                            f"~540; shorten the labels or drop categories")
    bw, ig, pitch, grp, plot_w, est_w = chosen
    num_size = 16.0
    num_h = (MID_UP + MID_DOWN) * num_size
    if plot_h / n_steps < num_h + _clearance_units(4.0, est_w):
        for num_size in (14.0, 12.0):
            num_h = (MID_UP + MID_DOWN) * num_size
            if plot_h / n_steps >= num_h + _clearance_units(4.0, est_w):
                break
        else:
            raise TemplateError(f"bar_chart: {n_steps + 1} numerals crowd the value axis "
                                f"at {plot_h / n_steps:.0f} units a step — raise step or "
                                f"lower v_max (no thinning: every step numeral must print)")
    wlab_y = max(_label_width(f"{k * step:g}", num_size) for k in range(n_steps + 1))
    elements: list[dict] = []
    anchors: dict[str, XY] = {"O": (0.0, 0.0), "X": (plot_w, 0.0), "Y": (0.0, -plot_h)}
    if gridlines:
        for k in range(1, n_steps + 1):
            y = -k * step * uv
            elements.append({"id": f"gl{k}", "type": "line", "stroke":
                             {"color": _GRID_INK, "width": 1},
                             "points": [[0, y], [plot_w, y]]})
    elements.append({"id": "axY", "type": "arrow", "head": "end",
                     "points": [[0, 0], [0, -plot_h - 12]]})
    elements.append(vc.line((0, 0), (plot_w, 0), id="axX", width=2))
    numclr = _clearance_units(STROKE_PX + SLACK_STROKE, est_w)
    for k in range(n_steps + 1):
        y = -k * step * uv
        elements.append(vc.line((-5, y), (5, y), id=f"tk{k}", width=1.5))
        elements.append(vc.text((-(wlab_y / 2 + 5 + numclr), y), f"{k * step:g}",
                                id=f"nm{k}", size=num_size))
    tops: list[tuple[int, int, float]] = []           # (T index, series, value)
    for i in range(n_cat):
        gx = i * pitch + (pitch - grp) / 2            # group centred in its pitch
        for j, (_nm, vals) in enumerate(srs):
            v = vals[i]
            left = gx + j * (bw + ig)
            if v > 0:
                elements.append({"id": f"bar{i}_{j}", "type": "rect",
                                 "x": vc.r2(left), "y": vc.r2(-v * uv),
                                 "width": vc.r2(bw), "height": vc.r2(v * uv),
                                 "fill": {"color": _BAR_FILLS[j]},
                                 "stroke": {"color": _BAR_OUTLINE, "width": 1.5}})
            tops.append((i * n_ser + j + 1, j, v))
            anchors[f"T{i * n_ser + j + 1}"] = (left + bw / 2, -v * uv)
    # a short label (digit/1–2 letters) must ALSO stay within 1.5·fontSize of the
    # baseline ink (visual-check's target rule) — on a wide canvas the rendered-px
    # clearance inflates in units, so pad just past it, not a fixed 6 units more
    cat_y = 2.0 + MID_UP * 14.0 + _clearance_units(STROKE_PX + SLACK_STROKE, est_w)
    for i, c in enumerate(cats):
        elements.append(vc.text((i * pitch + pitch / 2, cat_y), c, id=f"cat{i}",
                                size=14))
    if category_title:
        elements.append(vc.text((plot_w / 2, cat_y + 30), category_title,
                                id="ctitle", size=16))
    head_y = -plot_h - 12 - MID_UP * 16.0 - _clearance_units(STROKE_PX + SLACK_STROKE,
                                                           est_w) - 10
    lx = 8.0
    if value_title:
        elements.append(vc.text((lx, head_y), value_title, id="vtitle",
                                align="start", size=16))
        lx += title_w + 26
    if n_ser > 1:
        for j, (nm, _v) in enumerate(srs):
            elements.append({"id": f"sw{j}", "type": "rect", "x": vc.r2(lx),
                             "y": vc.r2(head_y - 7), "width": 14, "height": 14,
                             "fill": {"color": _BAR_FILLS[j]},
                             "stroke": {"color": _BAR_OUTLINE, "width": 1.5}})
            elements.append(vc.text((lx + 14 + sw_gap, head_y), nm, id=f"lg{j}",
                                    align="start", size=14))
            lx += 14 + sw_gap + _label_width(nm, 14) + 24
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    add(f"axis OY from 0 to {v_max:g}", "inferred", "the value axis")
    add(f"tick OY step {step:g}", "stem", f"a numeral every {step:g} — all {n_steps + 1} "
                                          f"printed, none thinned")
    ev_v = "stem" if values == "stem" else "inferred"
    for t_i, _j, v in tops:
        add(f"reads T{t_i} {v:g} on OY", ev_v, "the bar's top edge reads its value")
    if values == "figure":
        add('describe "the bar heights are figure content — the question asks the '
            'student to read them"', "inferred", "read-the-figure mode")
    add(f"derive {v_max:g} / {step:g} = {n_steps}", "inferred", "the axis's step count")
    for k in range(n_steps + 1):
        add(f'label "{k * step:g}" names {k * step:g}', "stem", "a scale numeral")
    for i, c in enumerate(cats):
        add(f'label "{c}" names cat{i}', ev_v, "a category label under its group")
    if n_ser > 1:
        for j, (nm, _v) in enumerate(srs):
            add(f'label "{nm}" names series{j}', ev_v, "a legend name by its swatch")
    if value_title:
        add(f'label "{value_title}" names OY', "stem", "the value axis's title")
    if category_title:
        add(f'label "{category_title}" names OX', "stem", "the category axis's title")
    for j, (nm, _v) in enumerate(srs):
        add(f'describe "the {nm or "only"} series bars are filled {_BAR_FILLS[j]} '
            f'outlined {_BAR_OUTLINE}"', "inferred", "the series paint")
    add("none tickMark parallelMark angleMark angleArc dashed shaded", "inferred",
        "bars, numerals and the axis arrowhead — no marks")
    elements_n = len(elements)
    return finish(kind="bar_chart", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=["O", "X", "Y"] +
                                         [f"T{t}" for t, _j, _v in tops],
                  segments=["OX", "OY"], claims=claims, ask=ask,
                  title=title or "A bar chart",
                  description=description or (
                      f"A vertical bar chart over {n_cat} categories" +
                      (f" in {n_ser} series (legend at the top)" if n_ser > 1 else "") +
                      f"; the value axis runs 0 to {v_max:g} in steps of {step:g} and "
                      f"each bar's top edge reads its value on it."),
                  scale="to scale — the value axis is a true linear map of the bar "
                        "heights",
                  budget=elements_n if elements_n > 32 else None,
                  departures=([f"{elements_n} elements — one rect per bar plus the "
                               "ruling gridlines"] if elements_n > 32 else None),
                  medium=medium)


BUILDERS = {fn.__name__[6:]: fn for fn in
            (build_grid_polygon, build_shaded_grid, build_rays_from_point, build_number_line,
             build_pictograph, build_rectangle_points, build_house_pentagon, build_cuboid,
             build_dot_pattern, build_circle_points, build_two_circles_points,
             build_circles_in_circle, build_abacus, build_sorting_rings, build_shape_row,
             build_coordinate_plane, build_parallel_lines, build_bar_chart)}

CATALOGUE = """
template            stem-checked numbers                          inputs
grid_polygon        cell                                          vertices (grid units), cols/rows?, cell_px, vertex_labels
shaded_grid         cols*rows OR cols and rows                    full=[(c,r)], half=[(c,r,corner)] corner tl|tr|bl|br
rays_from_point     numeric bearings/angle sizes (compass free)   rays={A:"NE"}, angles=[(a,b,label,reflex)], north_arrow
number_line         v0, v1, parts_per_unit                        points={P:0.7}, unit_px
pictograph          per_symbol                                    rows=[(label,count)] — whole or half symbols only
rectangle_points    length,width if given (else declared freedom) on_points={E:("DC",t)}, extra_segments, masks, aspect
house_pentagon      sides a label cannot restate (e.g. "x m")     AB,BC,DA,CP,PD, unit, labels={CP:"x m"}
cuboid              length, width, height                         unit, depth_angle=35, depth_scale=0.5
dot_pattern         stages, only if the stem states it            kind=triangle|square|rectangle
circle_points       none — counts are figure content              points={P:{"where":"in"|"on"|"out","label"?,"deg"?}}, r, labelled=False for stones
two_circles_points  none — counts are figure content              points={P:{"in":["L","R"],"on":"L"|"R"|null,"label"?}}, r, overlap
circles_in_circle   none — counts are figure content              n_in, n_out, R, r — small circles never touch the big one or each other
abacus              none — printed values are figure content      place_values=[10000,…,1], beads=[b per rod 0–9] — >9 refuses
sorting_rings       none — item texts are figure content          groups=[(name,[items])] 2–3 rings; cards stack inside each ring
shape_row           none — shape kinds are figure content         shapes=[(letter,kind)] kind in circle small_circle square rectangle triangle oval semicircle — 3 per row
coordinate_plane    each point's x,y when coords="stem"           x_max,y_max≤10, points={A:(x,y)}, join, closed, sym_axis={"x"|"y":k}, guides, grid, origin_label
parallel_lines      distance.value                                lines=["AB","CD"], parallel=[[…]], direction, crossing="PQ", distance={"between","value","unit"}
bar_chart           step; every value when values="stem"          categories 2–8, series 1–3 {"name","values"}, step, v_max, value_title, category_title, gridlines
""".strip()

SELF_TEST = [
    {"template": "grid_polygon", "figure_id": "selftest-grid",
     "stem": "A closed shape is drawn on a grid of squares, each of side 1 cm. (a) Find its "
             "area in squares. (b) Find its perimeter.",
     "ask": [["a", "the area in squares"], ["b", "the perimeter"]],
     "cell": 1, "vertices": [[1, 1], [5, 1], [5, 3], [3, 3], [3, 5], [1, 5]]},
    {"template": "shaded_grid", "figure_id": "selftest-shade",
     "stem": "A rectangle is made of 12 equal squares of side 1 cm. Some squares are fully "
             "shaded and some are halved by a diagonal. (a) Find the shaded area.",
     "ask": [["a", "the shaded area"]],
     "cols": 4, "rows": 3, "full": [[0, 0], [1, 0], [0, 1], [3, 2]],
     "half": [[2, 0, "bl"], [1, 1, "tr"], [3, 1, "bl"], [2, 2, "tl"]]},
    {"template": "rays_from_point", "figure_id": "selftest-rays",
     "stem": "A school is at O, and a temple, a well and a shop are at A, B and C as shown. "
             "Three angles are marked 1, 2 and 3. (a) Say the direction of each place from O. "
             "(b) Say what kind of angle each marked angle is.",
     "ask": [["a", "the directions"], ["b", "the angle kinds"]],
     "rays": {"A": "NE", "B": "S", "C": "W"},
     "angles": [["A", "B", "1"], ["B", "C", "2"], ["A", "B", "3", True]]},
    {"template": "number_line", "figure_id": "selftest-line",
     "stem": "The number line shows 0 to 3. Each unit is divided into 10 equal parts. Points "
             "P, Q and R are marked. (a) Say the numbers P, Q and R stand for.",
     "ask": [["a", "the marked values"]],
     "v0": 0, "v1": 3, "parts_per_unit": 10, "points": {"P": 0.4, "Q": 1.7, "R": 2.5}},
    {"template": "pictograph", "figure_id": "selftest-pict",
     "stem": "The pictograph shows cups sold over four days. One full circle stands for 4 "
             "cups. (a) Say how many cups were sold each day.",
     "ask": [["a", "the day's counts"]],
     "per_symbol": 4, "rows": [["Mon", 8], ["Tue", 10], ["Wed", 6], ["Thu", 14]]},
    {"template": "rectangle_points", "figure_id": "selftest-rect",
     "stem": "ABCD is a rectangle. E is a point on DC. Segments AE and BE are drawn. "
             "(a) How many triangles does the figure have?",
     "ask": [["a", "the triangles"]],
     "on_points": {"E": ["DC", 0.375]}, "extra_segments": ["AE", "BE"]},
    {"template": "house_pentagon", "figure_id": "selftest-house",
     "stem": "A garden's five sides are 8 m, 5 m, 5 m, 6 m and 4 m; one slanting side is "
             "marked x m. (b) When x = 5, find the perimeter.",
     "ask": [["b", "the perimeter"]],
     "AB": 8, "BC": 5, "CP": 5, "PD": 6, "DA": 4, "unit": "m", "labels": {"CP": "x m"}},
    {"template": "cuboid", "figure_id": "selftest-cuboid",
     "stem": "A cuboid has length 5 cm, width 3 cm and height 2 cm. (a) Give the numbers of "
             "faces, edges and vertices. (b) Find the total edge length.",
     "ask": [["a", "the counts"], ["b", "the edge total"]],
     "length": 5, "width": 3, "height": 2},
    {"template": "dot_pattern", "figure_id": "selftest-dots",
     "stem": "The first 4 figures of a dot pattern are shown; their dot counts are triangular "
             "numbers. (a) Write the dot counts of the 5th and 6th figures.",
     "ask": [["a", "the next counts"]],
     "stages": 4, "kind": "triangle"},
    {"template": "circle_points", "figure_id": "selftest-cpts",
     "stem": "The circle has centre Z. Points P, Q, R, S and T are marked. (a) Say which "
             "points lie inside the circle, on it and outside it.",
     "ask": [["a", "where each point lies"]],
     "points": {"P": {"where": "in"}, "Q": {"where": "in"}, "R": {"where": "on", "deg": 35},
                "S": {"where": "out"}, "T": {"where": "out"}}},
    {"template": "two_circles_points", "figure_id": "selftest-2cpts",
     "stem": "The figure shows two overlapping circles. Points P, Q, R and S are marked. "
             "(a) Say which circle each marked point lies in.",
     "ask": [["a", "where each point lies"]],
     "points": {"P": {"in": ["L"]}, "Q": {"in": ["L", "R"]}, "S": {"in": ["R"]},
                "T": {"on": "L", "in": ["R"]}}},
    {"template": "circles_in_circle", "figure_id": "selftest-cin",
     "stem": "The figure shows a big circle with small rings around and inside it. "
             "(a) Count the small circles inside the big circle and outside it.",
     "ask": [["a", "the counts"]],
     "n_in": 5, "n_out": 4},
    {"template": "abacus", "figure_id": "selftest-abacus",
     "stem": "The abacus shows a four-digit number. (a) Write the number it shows.",
     "ask": [["a", "the number shown"]],
     "place_values": [1000, 100, 10, 1], "beads": [3, 0, 5, 7]},
    {"template": "sorting_rings", "figure_id": "selftest-rings",
     "stem": "Sort the number cards into the rings. (a) Say which cards go in each ring.",
     "ask": [["a", "the ring of each card"]],
     "groups": [["Even", ["2", "8", "14"]], ["Odd", ["3", "9"]]]},
    {"template": "shape_row", "figure_id": "selftest-shapes",
     "stem": "The shapes A to F are shown. (a) Name each shape. (b) Say which shapes have "
             "a curved outline.",
     "ask": [["a", "the shape names"], ["b", "the curved ones"]],
     "shapes": [["A", "circle"], ["B", "square"], ["C", "triangle"], ["D", "oval"],
                ["E", "rectangle"], ["F", "semicircle"]]},
    {"template": "coordinate_plane", "figure_id": "selftest-plane",
     "stem": "On the coordinate plane A is (2, 4), B is (5, 3) and C is (3, 1). "
             "(a) Write the coordinates of each marked point.",
     "ask": [["a", "the coordinates"]],
     "x_max": 6, "y_max": 5, "points": {"A": [2, 4], "B": [5, 3], "C": [3, 1]},
     "join": [["A", "B", "C"]], "closed": True, "sym_axis": {"x": 3},
     "guides": ["A"], "origin_label": True},
    {"template": "parallel_lines", "figure_id": "selftest-parallel",
     "stem": "The lines AB, CD and EF are drawn; AB and CD are parallel. The "
             "perpendicular distance between AB and CD is 3 cm. (a) Say which pairs "
             "are parallel.",
     "ask": [["a", "the parallel pair"]],
     "lines": ["AB", "CD", "EF"], "parallel": [["AB", "CD"]], "direction": 12,
     "distance": {"between": ["AB", "CD"], "value": 3, "unit": "cm"}},
    {"template": "bar_chart", "figure_id": "selftest-bars",
     "stem": "The bar chart shows books borrowed over four months: 4 in Jan, 7 in "
             "Feb, 5 in Mar and 8 in Apr, on a scale of 2 per step up to 10. "
             "(a) Which month had most borrowings?",
     "ask": [["a", "the busiest month"]],
     "categories": ["Jan", "Feb", "Mar", "Apr"],
     "series": [{"name": "", "values": [4, 7, 5, 8]}],
     "step": 2, "v_max": 10, "value_title": "Books", "category_title": "Month"},
]


def _self_test() -> int:
    import tempfile
    audit = HERE / "audit-claim-set.py"
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for spec in SELF_TEST:
            kind = spec["template"]
            try:
                b = BUILDERS[kind](**{k: v for k, v in spec.items() if k != "template"})
            except TemplateError as e:
                print(f"  FAIL  {kind}: build refused — {e}")
                bad += 1
                continue
            p = b.write(tmp)
            r = subprocess.run([sys.executable, str(audit), str(p["claims"])],
                               capture_output=True, text=True)
            ok = r.returncode == 0
            print(f"  {'PASS' if ok else 'FAIL'}  {kind:<16} "
                  f"{len(b.doc['elements'])} elements · canvas "
                  f"{b.doc['canvas']['width']}x{b.doc['canvas']['height']} · audit exit {r.returncode}")
            if not ok:
                bad += 1
                print("\n".join("         " + l for l in r.stdout.splitlines() if "FAIL" in l))
    print("\n⚠️ Each figure's render is checked separately — run vdd-check.mjs on the outputs "
          "before trusting them.")
    return 1 if bad else 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__ + "\n\n" + CATALOGUE)
        return 2
    if args[0] == "--self-test":
        return _self_test()
    if args[0] == "list":
        print(CATALOGUE)
        return 0
    if args[0] == "build":
        if len(args) < 2:
            print("usage: vdd_templates.py build SPEC.json [--out DIR]")
            return 2
        spec_path = Path(args[1])
        out = Path(args[args.index("--out") + 1]) if "--out" in args else spec_path.parent
        specs = json.loads(spec_path.read_text(encoding="utf-8"))
        if isinstance(specs, dict):
            specs = [specs]
        for spec in specs:
            spec = dict(spec)
            kind = spec.pop("template")
            vc.reset_ids()          # deterministic element ids even inside one process
            try:
                b = BUILDERS[kind](**spec)
            except TemplateError as e:
                # name the spec — in a multi-figure build a bare "dot_pattern: label …"
                # leaves the reader to guess which figure refused
                print(f"TemplateError: {spec.get('figure_id', '<no figure_id>')}: {e}",
                      file=sys.stderr)
                return 2
            paths = b.write(out)
            print(f"{kind:<17} {paths['figure']}")
            print(f"{'':17} {paths['anchors']}")
            print(f"{'':17} {paths['claims']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
