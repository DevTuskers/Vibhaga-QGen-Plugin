#!/usr/bin/env python3
"""vdd_templates.py — the nine figure TEMPLATES of the vibhaga-qgen plugin (W3).

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
# DOM getBBox on a `dominantBaseline="middle"` <text> returns the font's ~1.22em line box, biased
# UP — measured on Inter (2026-10-01, capital "P" at size 18): −0.674·size above centre,
# +0.543·size below. The old ±size/2 estimate under-measures the top by ~3 units and real renders
# failed the edge rule while the estimate passed (rebuild Q4: 7.9 px at 320).
MID_UP, MID_DOWN = 0.70, 0.58

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
            out.append((el["label"], el["at"][0] + ox, el["at"][1] + oy - size * MID_UP,
                        el["at"][0] + ox + w, el["at"][1] + oy + size * MID_DOWN))
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
            s = el.get("size", 8)
            for k in range(el.get("count", 1)):
                off = (k - (el.get("count", 1) - 1) / 2) * 4
                ux, uy = vc.unit(tuple(el["on"][0]), tuple(el["on"][1]))
                c = (m[0] + ux * off, m[1] + uy * off)
                add([(c[0] - nx * s / 2, c[1] - ny * s / 2), (c[0] + nx * s / 2, c[1] + ny * s / 2)], w_of(el))
        elif t == "parallelMark":
            m = vc.lerp(tuple(el["on"][0]), tuple(el["on"][1]), el.get("at", 0.5))
            ux, uy = vc.unit(tuple(el["on"][0]), tuple(el["on"][1]))
            nx, ny = -uy, ux
            s = el.get("size", 8)
            tip = (m[0] + ux * s / 2, m[1] + uy * s / 2)
            for sign in (1, -1):
                tail = (m[0] - ux * s / 2 + sign * nx * s / 2, m[1] - uy * s / 2 + sign * ny * s / 2)
                add([tail, tip], w_of(el))
    return segs


def _seg_seg_dist(p: XY, q: XY, r: XY, s: XY) -> float:
    """0 when the segments cross, else the smallest endpoint-to-segment distance."""

    def pt_seg(a, u, v):
        dx, dy = v[0] - u[0], v[1] - u[1]
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return math.hypot(a[0] - u[0], a[1] - u[1])
        t = max(0.0, min(1.0, ((a[0] - u[0]) * dx + (a[1] - u[1]) * dy) / L2))
        return math.hypot(a[0] - u[0] - t * dx, a[1] - u[1] - t * dy)

    den = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])   # cross(d1, d2)
    if den:
        t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / den
        u = ((r[0] - p[0]) * (q[1] - p[1]) - (r[1] - p[1]) * (q[0] - p[0])) / den
        if 0 <= t <= 1 and 0 <= u <= 1:
            return 0.0
    return min(pt_seg(p, r, s), pt_seg(q, r, s), pt_seg(r, p, q), pt_seg(s, p, q))


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


def _translate(elements: list[dict], dx: float, dy: float) -> None:
    for el in elements:
        for key in ("points", "at", "center", "vertex", "from", "to", "on"):
            if key in el:
                v = el[key]
                if isinstance(v, list) and v and isinstance(v[0], (list, tuple)):
                    el[key] = [[vc.r2(p[0] + dx), vc.r2(p[1] + dy)] for p in v]
                else:
                    el[key] = [vc.r2(v[0] + dx), vc.r2(v[1] + dy)]
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
    """Fit the figure to its canvas, run the label-clearance pre-flight, emit the claim set."""
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
    # 1. fit — bbox over ALL ink (shape outlines incl. half the stroke) plus the label boxes
    boxes = label_boxes(elements, fs)
    strokes = stroke_segments(elements)
    xs, ys = [], []
    for a, b, w in strokes:
        xs += [a[0] - w / 2, b[0] - w / 2, a[0] + w / 2, b[0] + w / 2]
        ys += [a[1] - w / 2, b[1] - w / 2, a[1] + w / 2, b[1] + w / 2]
    for _s, x0, y0, x1, y1 in boxes:
        xs += [x0, x1]
        ys += [y0, y1]
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    # the margin must still clear the edge after the render scales down to the narrowest
    # surface — a fixed 12 units drops under 8 rendered px once the canvas widens (critic R3
    # finding 3: number line 0–10+ refused). Solve edge ≥ EDGE_PX + SLACK_EDGE on the TIGHTER
    # card scale:  margin·294/(span + 2·margin + 60) ≥ 9  ⇒  margin ≥ (9·span + 540)/276.
    span_x, span_y = maxx - minx, maxy - miny
    margin = max(MARGIN, (RENDER_EDGE := EDGE_PX + SLACK_EDGE) *
                 (span_x + 60.0) / (PLATE_INNER - 2 * RENDER_EDGE) + 0.05)
    dx, dy = margin - minx, margin - miny
    _translate(elements, dx, dy)
    anchors = {k: (vc.r2(v[0] + dx), vc.r2(v[1] + dy)) for k, v in anchors.items()}
    W, H = math.ceil(maxx - minx + 2 * margin), math.ceil(maxy - miny + 2 * margin)

    # 2. clearance pre-flight — rendered px at the NARROWEST surface (the 294 px plate inner
    # width — PLATE_INNER). Edge distance is bound by OUR margin on the student surface
    # (s = min(1, 294/W)). Stroke distance is also measured on the CARD surface, where
    # normalizeVdd refits the canvas ~55–60 units wider (empirical) — model the tighter card
    # scale for stroke clearance. The min(1,·) caps keep a narrow canvas from claiming >1 px/unit.
    scale_edge = min(1.0, PLATE_INNER / W)
    scale_stroke = min(1.0, PLATE_INNER / (W + 60.0))
    boxes = [(_s, x0 + dx, y0 + dy, x1 + dx, y1 + dy) for _s, x0, y0, x1, y1 in boxes]
    strokes = [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), w) for a, b, w in strokes]
    for txt, x0, y0, x1, y1 in boxes:
        edge = min(x0, y0, W - x1, H - y1) * scale_edge
        if edge < EDGE_PX + SLACK_EDGE:
            raise TemplateError(
                f"{kind}: label {txt!r} is ~{edge:.1f} rendered px from the canvas edge "
                f"(needs {EDGE_PX}px + slack) — move it inward")
        worst = min(_seg_rect_dist(a, b, (x0, y0, x1, y1)) - w / 2 for a, b, w in strokes) if strokes else 99
        if worst * scale_stroke < STROKE_PX + SLACK_STROKE:
            raise TemplateError(
                f"{kind}: label {txt!r} is ~{worst * scale_stroke:.1f} rendered px from stroke "
                f"geometry (needs {STROKE_PX}px + slack) — move it clear")
    # labels must also clear EACH OTHER — two numerals on one wedge or a crowded number line
    # otherwise overlap silently until the render (needs ≥ 4 rendered px between boxes)
    for i in range(len(boxes)):
        _t1, ax0, ay0, ax1, ay1 = boxes[i]
        for _t2, bx0, by0, bx1, by1 in boxes[i + 1:]:
            gap = math.hypot(max(0.0, bx0 - ax1, ax0 - bx1), max(0.0, by0 - ay1, ay0 - by1))
            if gap * scale_stroke < 4.0:
                raise TemplateError(
                    f"{kind}: labels {_t1!r} and {_t2!r} are ~{gap * scale_stroke:.1f} "
                    f"rendered px apart (need 4) — move one clear")

    # 3. the claim set (audit-claim-set grammar; order is the corpus convention)
    if points and any(not re.fullmatch(r"[A-Z]", p) for p in points):
        raise TemplateError(f"{kind}: point names are single capitals — got {points}")
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
        return re.sub(r"@([A-Z])\b", rep, pred)

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
# 1. grid_polygon — a closed rectilinear polygon on a cm grid
# ────────────────────────────────────────────────────────────────────────────────
def build_grid_polygon(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                       cell, vertices, cols=None, rows=None, cell_px=30.0,
                       vertex_labels=False, shade=True):
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
        cx = sum(p[0] for p in pts.values()) / len(pts)
        cy = sum(p[1] for p in pts.values()) / len(pts)
        for n, v in pts.items():
            ox = -22 if v[0] < cx - 1 else 12
            oy = -12 if v[1] < cy else 4
            elements.append({"id": f"lbl{n}", "type": "point", "at": vc.P(v), "r": 0,
                             "label": n, "labelOffset": [ox, oy]})
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
    return finish(kind="shaded_grid", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=gnames, segments=segs, claims=claims, ask=ask,
                  title=title or f"A {cols} by {rows} rectangle of squares, some shaded",
                  description=description or (
                      f"A rectangle of {cols * rows} equal squares ({cols} by {rows}); "
                      f"{len(full)} fully shaded and {len(half)} cut by a diagonal with one "
                      f"half shaded."),
                  scale="to scale — every cell is one unit square", medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 3. rays_from_point — bearings from a centre O, a north arrow, numbered angle arcs
# ────────────────────────────────────────────────────────────────────────────────
def build_rays_from_point(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                          rays: dict, centre="O", ray_len=110.0, north_arrow=True,
                          north_label="N", angles=(), arc_r=34.0):
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
                       for a, b, w2 in stroke_segments(elements)) >= 11.0:
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
            if worst >= 11.0:
                placed = (vc.r2(px), vc.r2(py))
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
def build_number_line(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                      v0, v1, parts_per_unit, points=None, unit_px=None, overhang=30.0):
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
    num_step = next((k for k in range(1, n_units + 1)
                     if n_units % k == 0 and k * unit_px >= wlab + num_gap), n_units)
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
    # the point label must clear its own major tick (top at 11 units + half its stroke) by
    # 6 px + slack ON THE RENDER — on a wide canvas that is more canvas units than a fixed
    # offset provides, so size the lift from the figure's own width
    est_span = span_v * unit_px + 2 * overhang + 12
    mark_off = 21.0 + FS * (MID_DOWN - 0.5) + _clearance_units(STROKE_PX + SLACK_STROKE, est_span)
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
    return finish(kind="pictograph", figure_id=figure_id, stem=stem, elements=elements,
                  anchors=anchors, points=[], segments=[], claims=claims, ask=ask,
                  title=title or "A pictograph of symbols in rows",
                  description=description or (
                      f"A pictograph with {len(rows)} rows of identical circles; one full "
                      f"circle stands for {per_symbol:g}, a right half-circle for half that."),
                  scale="symbols are uniform — the count is the content", medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 6. rectangle_points — rectangle ABCD with points on sides and extra segments
# ────────────────────────────────────────────────────────────────────────────────
def build_rectangle_points(*, figure_id, stem, ask=None, title=None, description=None, medium="english",
                           length=None, width=None, aspect=(4, 3), on_points=None,
                           extra_segments=(), masks=None, base_px=208.0):
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
    for name, (side, t) in (on_points or {}).items():
        add(f"on {name} {side[0]}{side[1]}", "inferred", f"{name} sits {t:g} of the way along {side}")
    if on_points:
        name, (side, t) = next(iter(on_points.items()))
        from fractions import Fraction
        fr = Fraction(t).limit_denominator(64)
        add(f"derive {fr.numerator} / {fr.denominator} = {t:g}", "inferred",
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
    add(f"derive {' + '.join(f'{v:g}' for v in sides.values())} = {sum(sides.values()):g}",
        "inferred", "the perimeter as a sum of the five sides")
    for k, t in texts.items():
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
    # the width label sits on the OUTWARD normal of the bottom depth edge CG's midpoint —
    # beside FG it reads as naming a height edge, and inside the silhouette it reads as a
    # bottom edge. CG's outward normal is (−dy, dx)/|CG| (below-right of the figure).
    g_mid = vc.lerp(C, (C[0] + dx, C[1] + dy), 0.5)
    dcg = math.hypot(dx, dy)
    nx, ny = -dy / dcg, dx / dcg
    wlab = _label_width(f"{width:g} {unit}", 16)
    off = 12 + _label_half_along(f"{width:g} {unit}", 16, nx, ny)
    elements.append(vc.text((g_mid[0] + nx * off, g_mid[1] + ny * off),
                            f"{width:g} {unit}", id="slW", size=16))
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    dr = add(f"derive {length:g} / {height:g} = {length / height:g}", "stem",
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
    for pred, seg in ((f"{length:g} {unit}", "DC"), (f"{height:g} {unit}", "DA"),
                      (f"{width:g} {unit}", "CG")):
        kid = add(f'label "{pred}" names {seg}', "stem", f"the stem's {pred}")
        if seg == "CG":
            # depth edges are drawn at depth_scale — the anchor-vs-label pair check (2e-iii)
            # must see this declared, or DC/CG and DA/CG pairs look like a misdrawn ratio
            contested.append((kid, f"{pred} prints the stem's true width on CG while the "
                                   "oblique convention draws depth edges foreshortened "
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
# CLI + self-test
# ────────────────────────────────────────────────────────────────────────────────
BUILDERS = {fn.__name__[6:]: fn for fn in
            (build_grid_polygon, build_shaded_grid, build_rays_from_point, build_number_line,
             build_pictograph, build_rectangle_points, build_house_pentagon, build_cuboid,
             build_dot_pattern)}

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
