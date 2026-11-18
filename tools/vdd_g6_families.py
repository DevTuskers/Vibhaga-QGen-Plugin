"""vdd_g6_families.py — the G6 tally-chart / balance-scale / solid-net families.

Three bounded builders covering confirmed G6 gaps in
`wt/g678-readiness/inventory-g6.md` (gaps 3, 4 and 5):

  • `build_tally_chart` — a ruled two-column tally table: a category glyph in
    the left cell, tally marks in the right cell grouped in the standard
    gate cluster (four strokes crossed by a fifth).  Counts are stem-checked
    in `values="stem"` mode; the total is emitted as a `derive`.

  • `build_balance_scale` — a two-pan beam balance: fulcrum triangle, a beam
    (level or tilted by a bounded, claimed angle), two hanger-yokes and
    trapezoid pans carrying labelled items (capital letters, numeric masses
    in the declared `unit`, or a single `?` unknown).  A level/tilted state
    that contradicts the numeric totals refuses.

  • `build_cube_net` — canonical nets: the cube cross (4-in-a-row + two
    flaps), the closed-cuboid four-face strip with two l×w flaps, and the
    tetrahedron four-triangle strip.  Shared edges draw dashed (fold lines),
    boundary edges solid; face letters and dimension labels are optional but
    each drawn glyph binds exactly one `label` claim — face letters claim the
    face's interior (`names region_face<i>`, the AREA convention), dimension
    labels draw as label-only `point` elements anchored just off the measured
    edge so their visual target is the anchor, not painted geometry.

Every meaningful number is stem-checked (`values="stem"`), declared figure
content (`values="figure"`), or computed here.  What stays OUTSIDE: ruled
data tables without tally marks (question markup, not a drawing), spring
balances and dial instruments, apparatus realism (produce shapes, strings,
painted scenery), non-canonical or partial nets, glue tabs, and nets of any
other solid (square_pyramid / triangular_prism / cylinder nets live in the
main `net` template).

This module is NOT registered in vdd_templates.TEMPLATES — the lead actor
owns that file; registration is a one-line lazy entry there.  vdd_templates
itself is imported lazily inside the builders so this module stays
import-light.
"""
from __future__ import annotations

import math
import re

import vdd_cookbook as vc

_LETTER = re.compile(r"^[A-Z]$")
_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9' ]{0,11}$")
_MASS = re.compile(r"^(\d+(?:\.\d+)?)(?:\s+([A-Za-z]+))?$")


def _num(kind: str, name: str, v):
    """The numeric gate EVERY spec value passes before any arithmetic — bools,
    strings and non-finite numbers are refused before int/float conversion."""
    from vdd_templates import TemplateError
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TemplateError(f"{kind}: {name} {v!r} must be a finite number")
    try:
        fv = float(v)
    except OverflowError:
        raise TemplateError(f"{kind}: {name} {v!r} must be a finite number")
    if not math.isfinite(fv):
        raise TemplateError(f"{kind}: {name} {v!r} must be a finite number")
    return fv


def _count(kind: str, name: str, v, lo: int, hi: int) -> int:
    """A whole-number count within [lo, hi] — the `_num` gate plus integrality."""
    from vdd_templates import TemplateError
    fv = _num(kind, name, v)
    if fv != int(fv):
        raise TemplateError(f"{kind}: {name} {v!r} must be a whole number")
    iv = int(fv)
    if not lo <= iv <= hi:
        raise TemplateError(f"{kind}: {name} {iv} is outside {lo}–{hi}")
    return iv


def _values_mode(kind: str, values) -> str:
    from vdd_templates import TemplateError
    v = str(values).strip().lower()
    if v not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure' — got {values!r}")
    return v


def _unit_text(unit) -> str | None:
    from vdd_templates import TemplateError
    if unit is None:
        return None
    if not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z]{1,6}", unit.strip()):
        raise TemplateError(f"unit must be a short token like 'kg' or 'cm' — got {unit!r}")
    return unit.strip()


# ────────────────────────────────────────────────────────────────────────────────
# 1. tally_chart — a ruled two-column tally table
# ────────────────────────────────────────────────────────────────────────────────
def build_tally_chart(*, figure_id, stem, rows=None, values="stem",
                      ask=None, title=None, description=None, medium="english"):
    """A tally table: `rows=[(label, count)]`, 1–6 rows.

    `label` is a short category glyph (single word, e.g. "Cars"); `count` a
    whole number 0–30.  Each count draws as ⌈count/5⌉ gate clusters — every
    full group is four vertical strokes crossed by a fifth diagonal — plus
    the single-stroke remainder.  In `values="stem"` mode every count must
    be a number the stem states; in `values="figure"` mode the counts are
    honestly figure content (the student counts the strokes).

    A long count is one stroke element per mark, so a full table legitimately
    tops 32 elements — `budget:`/`departures:` declares it.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "tally_chart"
    values = _values_mode(kind, values)

    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= 6:
        raise TemplateError(f"{kind}: rows must be a list of 1–6 (label, count) pairs")
    cats, counts = [], []
    for i, r in enumerate(rows):
        if not isinstance(r, (list, tuple)) or len(r) != 2:
            raise TemplateError(f"{kind}: row {i + 1} must be a (label, count) pair")
        lab, c = r
        if not isinstance(lab, str) or not _WORD.fullmatch(lab):
            raise TemplateError(f"{kind}: category {lab!r} — labels are single words "
                                "(drawn text is simple English)")
        cats.append(lab)
        counts.append(_count(kind, f"count for {lab!r}", c, 0, 30))
    if len(set(cats)) != len(cats):
        raise TemplateError(f"{kind}: a category label repeats — {cats}")
    if values == "stem":
        for lab, c in zip(cats, counts):
            vt.require_stem(stem, **{f"count {lab}": c})

    # layout: left column holds the category word, right column the marks.
    lab_w = max(60.0, max(len(c) for c in cats) * 11.5 + 24.0)
    group_w, group_gap, single_w = 26.0, 14.0, 8.0

    def row_marks_width(c):
        g, r = divmod(c, 5)
        return g * (group_w + group_gap) + r * single_w

    tal_w = max(90.0, max(row_marks_width(c) for c in counts) + 30.0)
    row_h, stroke_len = 42.0, 24.0
    W, H = lab_w + tal_w, row_h * len(cats)

    vc.reset_ids()
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    # ruled frame — horizontal rules (incl. top/bottom border) + the column rule
    for i in range(len(cats) + 1):
        elements.append(vc.line((0, i * row_h), (W, i * row_h), id=f"rule{i}"))
    elements.append(vc.line((lab_w, 0), (lab_w, H), id="col"))
    elements.append(vc.line((0, 0), (0, H), id="edgeL"))
    elements.append(vc.line((W, 0), (W, H), id="edgeR"))

    for i, (lab, c) in enumerate(zip(cats, counts)):
        y = i * row_h + row_h / 2.0
        elements.append(vc.text((lab_w / 2.0, y), lab, id=f"cat{i}", size=16))
        add(f'label "{lab}" names cat{i}', "inferred", "the row's category glyph")
        x = lab_w + 16.0
        g, rem = divmod(c, 5)
        for gi in range(g):
            for j in range(4):                    # four uprights of the gate
                xs = x + 3.0 + j * 6.5
                elements.append(vc.line((xs, y - stroke_len / 2),
                                        (xs, y + stroke_len / 2),
                                        id=f"tal{i}_{gi}_{j}"))
            elements.append(vc.line((x - 1.0, y + 9.0),       # the crossing fifth
                                    (x + 23.0, y - 9.0),
                                    id=f"x{i}_{gi}"))
            x += group_w + group_gap
        for j in range(rem):
            xs = x + j * single_w
            elements.append(vc.line((xs, y - stroke_len / 2),
                                    (xs, y + stroke_len / 2),
                                    id=f"tal{i}_r{j}"))
        bits = []
        if g:
            bits.append(f"{g} group{'s' if g != 1 else ''} of five")
        if rem:
            bits.append(f"{rem} single stroke{'s' if rem != 1 else ''}")
        how = " and ".join(bits) if bits else "no strokes"
        add(f'describe "the {lab} row tallies {c} — {how}"', "inferred",
            "count the strokes in the row's tally cell")
    total = sum(counts)
    add("derive " + " + ".join(f"{c:g}" for c in counts) + f" = {total:g}",
        "inferred", "the rows' tally counts summed")
    if values == "figure":
        add('describe "the tally counts are figure content — the student reads '
            'the strokes"', "inferred", "read-off mode")
    add("none angleMark parallelMark tickMark arrow dashed shaded circle grid",
        "inferred", "ruled cells, a word and tally strokes only")

    budget = len(elements) if len(elements) > 32 else None
    departures = (["one element per tally mark — a long count exceeds the "
                   "32-element guideline"] if budget else None)
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                     anchors={}, points=[], segments=[], claims=claims, ask=ask,
                     title=title or "A tally chart",
                     description=description or
                     "A two-column tally table; each row's marks are grouped "
                     "in fives, the fifth stroke crossing the first four.",
                     scale="mark spacing is a canvas choice — only the counts "
                           "matter",
                     budget=budget, departures=departures, medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 2. balance_scale — a two-pan beam balance
# ────────────────────────────────────────────────────────────────────────────────
def build_balance_scale(*, figure_id, stem, left=None, right=None,
                        state="level", unit="kg", values="stem",
                        tilt_deg=12.0, ask=None, title=None, description=None,
                        medium="english"):
    """A two-pan balance: `left=[items]`, `right=[items]` (1–4 each).

    An item is a single capital (a named object), `?` (an unknown), or a
    numeric mass — a number, `"5"` or `"5 kg"`; a numeric item prints as
    `"<v> <unit>"` and is stem-checked in `values="stem"` mode.  `state` is
    `level | left_down | right_down`; the beam tilts a bounded `tilt_deg`
    (8–18°, claimed).  When EVERY item is a numeric mass the totals are
    computed — a state that contradicts them refuses (the heavier pan hangs
    lower, a level beam needs equal totals) and the sums land as `derive`s.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "balance_scale"
    values = _values_mode(kind, values)
    unit = _unit_text(unit) or "kg"
    if state not in ("level", "left_down", "right_down"):
        raise TemplateError(f"{kind}: state must be level|left_down|right_down "
                            f"— got {state!r}")
    tilt = _num(kind, "tilt_deg", tilt_deg)
    if not 8.0 <= tilt <= 18.0:
        raise TemplateError(f"{kind}: tilt_deg {tilt:g} outside 8–18° — smaller "
                            "is unreadable, larger is cartoonish")

    def item_glyph(side, j, it):
        """-> (printed glyph, numeric value or None)."""
        if isinstance(it, bool):
            raise TemplateError(f"{kind}: {side} item {j + 1} {it!r} is not a "
                                "label or a mass")
        if isinstance(it, (int, float)):
            v = _num(kind, f"{side} item {j + 1}", it)
            if v <= 0:
                raise TemplateError(f"{kind}: a mass must be positive — got {v:g}")
            return f"{v:g} {unit}", v
        if not isinstance(it, str) or not it.strip():
            raise TemplateError(f"{kind}: {side} item {j + 1} {it!r} is not a "
                                "label or a mass")
        s = it.strip()
        if s == "?":
            return "?", None
        if _LETTER.fullmatch(s):
            return s, None
        m = _MASS.fullmatch(s)
        if m:
            v = _num(kind, f"{side} item {j + 1}", float(m.group(1)))
            if v <= 0:
                raise TemplateError(f"{kind}: a mass must be positive — got {v:g}")
            if m.group(2) is not None and m.group(2) != unit:
                raise TemplateError(f"{kind}: item {s!r} carries unit "
                                    f"{m.group(2)!r} — the figure's unit is {unit!r}")
            return f"{v:g} {unit}", v
        raise TemplateError(f"{kind}: item {s!r} on the {side} pan is not a "
                            "capital letter, '?' or a mass")

    def pan(name, items):
        if not isinstance(items, (list, tuple)) or not 1 <= len(items) <= 4:
            raise TemplateError(f"{kind}: {name} must be a list of 1–4 items")
        return [item_glyph(name, j, it) for j, it in enumerate(items)]

    pl, pr = pan("left", left), pan("right", right)
    masses = [v for _, v in pl + pr]
    if values == "stem":
        for k, v in enumerate(masses):
            if v is not None:
                vt.require_stem(stem, **{f"item {k + 1}": v})

    all_numeric = all(v is not None for _, v in pl + pr)
    lsum = sum(v for _, v in pl if v is not None)
    rsum = sum(v for _, v in pr if v is not None)
    if all_numeric:
        if state == "level" and lsum != rsum:
            raise TemplateError(f"{kind}: a level beam cannot hold {lsum:g} {unit} "
                                f"against {rsum:g} {unit} — the pans are equal "
                                "or the beam tilts")
        if state == "left_down" and not lsum > rsum:
            raise TemplateError(f"{kind}: the left pan hangs lower but "
                                f"{lsum:g} ≤ {rsum:g} {unit} — a lighter side "
                                "never drops")
        if state == "right_down" and not rsum > lsum:
            raise TemplateError(f"{kind}: the right pan hangs lower but "
                                f"{rsum:g} ≤ {lsum:g} {unit} — a lighter side "
                                "never drops")

    # ── geometry ──────────────────────────────────────────────────────────
    beam_half = 150.0                        # pans hang clear of the fulcrum
    t = math.radians(tilt if state != "level" else 0.0)
    sgn = 1.0 if state == "left_down" else -1.0          # y down: which end drops
    bend_l = (-beam_half * math.cos(t), sgn * beam_half * math.sin(t))
    bend_r = (beam_half * math.cos(t), -sgn * beam_half * math.sin(t))
    hang, depth = 42.0, 52.0
    inset = 30.0                                          # bottom narrower than rim

    fedges = [((-26.0, 66.0), (26.0, 66.0)), ((26.0, 66.0), (0.0, 4.0)),
              ((0.0, 4.0), (-26.0, 66.0))]           # the fulcrum triangle

    def _xsub(u, v):
        return (u[0] - v[0], u[1] - v[1])

    def _cross(u, v):
        return u[0] * v[1] - u[1] * v[0]

    def _pt_seg(pt, a, b):
        ab = _xsub(b, a)
        L = ab[0] ** 2 + ab[1] ** 2
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((pt[0] - a[0]) * ab[0]
                                                + (pt[1] - a[1]) * ab[1]) / L))
        return math.hypot(pt[0] - (a[0] + t * ab[0]), pt[1] - (a[1] + t * ab[1]))

    def _seg_seg(p, q, a, b):
        r, s = _xsub(q, p), _xsub(b, a)
        den = _cross(r, s)
        if abs(den) > 1e-12:
            t = _cross(_xsub(a, p), s) / den
            u = _cross(_xsub(a, p), r) / den
            if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
                return 0.0
        return min(_pt_seg(p, a, b), _pt_seg(q, a, b),
                   _pt_seg(a, p, q), _pt_seg(b, p, q))

    def _in_tri(p):
        sgns = [_cross(_xsub(b, a), _xsub(p, a)) for a, b in fedges]
        return all(v >= 0 for v in sgns) or all(v <= 0 for v in sgns)

    def pan_layout(items, end):
        """Widths per item at font 15; the rim grows to fit the row."""
        ws = [15.0 * 0.62 * len(g) + 10.0 for g, _ in items]
        row = sum(ws) + (len(ws) - 1) * 10.0
        rim_w = max(110.0, row + 2 * (inset + 8.0) + 16.0)
        rim_y = end[1] + hang
        sgn = -1.0 if end[0] < 0 else 1.0
        ic = (end[0] - sgn * rim_w / 2.0, rim_y)               # inner rim corner
        ib = (end[0] - sgn * (rim_w / 2.0 - inset), rim_y + depth)
        if rim_w > 240.0 or _in_tri(ic) or _in_tri(ib) or any(
                _seg_seg(s0, s1, a, b) < 8.0
                for s0, s1 in ((end, ic), (ic, ib)) for a, b in fedges):
            raise TemplateError(f"{kind}: the {len(items)} labels need a {rim_w:g} "
                                "unit pan — the rim or its yoke would cross the "
                                "fulcrum; shorten the glyphs")
        inner_half = rim_w / 2.0 - inset * 0.4 - 12.0      # walls slope in ~0.4·inset at row level
        if row / 2.0 > inner_half:
            raise TemplateError(f"{kind}: the item row ({row:g} units) crowds the "
                                "pan walls — widen the pan or shorten the glyphs")
        return ws, rim_w

    ws_l, rim_l = pan_layout(pl, bend_l)
    ws_r, rim_r = pan_layout(pr, bend_r)

    vc.reset_ids()
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []
    drawn: dict[str, str] = {}          # glyph -> first element id

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    elements.append(vc.line(bend_l, bend_r, id="beam", width=3.0))
    elements.append(vc.polygon([(-26.0, 66.0), (26.0, 66.0), (0.0, 4.0)],
                               id="fulcrum"))
    if state == "level":
        add('describe "the beam is level — the pans balance"', "measured",
            "the beam is drawn horizontal")
    else:
        side = "left" if state == "left_down" else "right"
        add(f'describe "the beam tilts {tilt:g}° — the {side} pan hangs lower"',
            "measured", "the beam is drawn rotated by the claimed tilt")

    def draw_pan(end, rim_w, ws, items, tag):
        cx, ey = end
        rim_y = ey + hang
        cl, cr = (cx - rim_w / 2, rim_y), (cx + rim_w / 2, rim_y)
        bl, br = (cx - rim_w / 2 + inset, rim_y + depth), \
                 (cx + rim_w / 2 - inset, rim_y + depth)
        elements.append(vc.line(end, cl, id=f"y{tag}l"))   # yoke strings
        elements.append(vc.line(end, cr, id=f"y{tag}r"))
        elements.append(vc.line(cl, bl, id=f"pan{tag}l"))
        elements.append(vc.line(bl, br, id=f"pan{tag}b"))
        elements.append(vc.line(br, cr, id=f"pan{tag}r"))
        # item row just under the rim, inside the bowl
        row_y = rim_y + 26.0
        x = cx - (sum(ws) + (len(ws) - 1) * 10.0) / 2.0
        for j, ((g, _v), w) in enumerate(zip(items, ws)):
            elements.append(vc.text((x + w / 2.0, row_y), g,
                                    id=f"it{tag}{j}", size=15))
            if g not in drawn:
                drawn[g] = f"it{tag}{j}"
                add(f'label "{g}" names it{tag}{j}', "inferred",
                    "an item on the pan")
            else:
                add(f'describe "{g} also prints on the '
                    f'{"left" if tag == "l" else "right"} pan"', "inferred",
                    "a repeated glyph binds one claim")
            x += w + 10.0

    draw_pan(bend_l, rim_l, ws_l, pl, "l")
    draw_pan(bend_r, rim_r, ws_r, pr, "r")

    def contents(items):
        return " and ".join(g for g, _ in items)

    add(f'describe "the left pan carries {contents(pl)}"', "inferred",
        "read the glyphs in the bowl")
    add(f'describe "the right pan carries {contents(pr)}"', "inferred",
        "read the glyphs in the bowl")
    if all_numeric:
        add("derive " + " + ".join(f"{v:g}" for _, v in pl) + f" = {lsum:g}",
            "inferred", "the left pan's masses summed")
        add("derive " + " + ".join(f"{v:g}" for _, v in pr) + f" = {rsum:g}",
            "inferred", "the right pan's masses summed")
        if state == "level":
            add('describe "the totals are equal — the beam balances"',
                "inferred", f"{lsum:g} {unit} against {rsum:g} {unit}")
    else:
        add("derive 1 + 1 = 2", "inferred", "the balance has two pans")
        if values == "stem":
            unk = ", ".join(g for g, v in pl + pr if v is None)
            add(f'describe "the items {unk} are named objects or '
                'unknowns — not weighed amounts"', "inferred",
                "letters and ? are not masses")
    if values == "figure":
        add('describe "the item labels are figure content — the student reads '
            'the pans"', "inferred", "read-off mode")
    add("none angleMark parallelMark tickMark arrow dashed shaded circle grid",
        "inferred", "a beam, a fulcrum, two yokes and two pans only")

    budget = len(elements) if len(elements) > 32 else None
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                     anchors={}, points=[], segments=[], claims=claims, ask=ask,
                     title=title or "A two-pan balance",
                     description=description or
                     "A beam balance on a fulcrum; each pan hangs from a beam "
                     "end and carries labelled items.",
                     scale="not to scale — pan sizes and item glyphs are "
                           "symbolic; only the masses and the beam's state "
                           "carry meaning",
                     budget=budget, medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 3. cube_net — canonical cube / cuboid / tetrahedron nets
# ────────────────────────────────────────────────────────────────────────────────
def build_cube_net(*, figure_id, stem, shape="cube", dims=None, labels=None,
                   unit=None, values="stem", scale_px=30.0,
                   ask=None, title=None, description=None, medium="english"):
    """A canonical solid net on one physical scale.

      • `shape="cube"`        — `dims={"edge": e}`; the cross net: four
                                squares in a row, one flap above and one
                                below the second square.
      • `shape="cuboid"`      — `dims={"length","width","height"}`; the
                                closed net: a strip front/side/back/side
                                (l×h, w×h, l×h, w×h) with the l×w top and
                                bottom faces flapped onto the first face.
      • `shape="tetrahedron"` — `dims={"edge": e}`; the strip of four
                                equilateral triangles (a parallelogram).

    Shared edges draw dashed — the fold lines; boundary edges are solid.
    `dims` values are stem-checked in `values="stem"` mode and printed on an
    outer edge of a face that owns them; `labels=[capitals]`, one per face
    in layout order, prints a face letter at each centroid.  `scale_px` is
    the units-per-edge scale — every face must draw ≥34 units on its short
    side so a letter seats honestly.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "cube_net"
    values = _values_mode(kind, values)
    unit = _unit_text(unit)
    px = _num(kind, "scale_px", scale_px)
    if not 16.0 <= px <= 90.0:
        raise TemplateError(f"{kind}: scale_px {px:g} outside 16–90")
    if shape not in ("cube", "cuboid", "tetrahedron"):
        raise TemplateError(f"{kind}: shape must be cube|cuboid|tetrahedron — "
                            f"got {shape!r}")
    need = {"cube": ("edge",), "cuboid": ("length", "width", "height"),
            "tetrahedron": ("edge",)}[shape]
    if not isinstance(dims, dict) or set(dims) != set(need):
        raise TemplateError(f"{kind}: {shape} dims must be exactly "
                            f"{sorted(need)} — got {dims!r}")
    dv = {}
    for k_ in need:
        v = _num(kind, f"dim {k_}", dims[k_])
        if v <= 0:
            raise TemplateError(f"{kind}: {k_} must be positive")
        if values == "stem":
            vt.require_stem(stem, **{k_: v})
        dv[k_] = v

    # ── faces as vertex loops ────────────────────────────────────────────
    # each face: (list of corner pts in order, short side, dim-tag for its
    # printed edge) — plus one named outer edge that carries the dim label.
    faces: list[list[tuple[float, float]]] = []
    dim_edges: list[tuple[str, tuple, tuple]] = []        # (dim key, a, b)

    if shape == "cube":
        e = dv["edge"] * px
        for c, r in [(0, 0), (1, 0), (2, 0), (3, 0), (1, -1), (1, 1)]:
            x0, y0 = c * e, r * e
            faces.append([(x0, y0), (x0 + e, y0), (x0 + e, y0 + e), (x0, y0 + e)])
        dim_edges.append(("edge", (0.0, e), (e, e)))      # under face 0
    elif shape == "cuboid":
        l, w, h = (dv[k_] * px for k_ in ("length", "width", "height"))
        xs = [0.0, l, l + w, 2 * l + w, 2 * l + 2 * w]
        for i in range(4):                                 # the side strip
            faces.append([(xs[i], 0.0), (xs[i + 1], 0.0),
                          (xs[i + 1], h), (xs[i], h)])
        faces.append([(0.0, -w), (l, -w), (l, 0.0), (0.0, 0.0)])    # top flap
        faces.append([(0.0, h), (l, h), (l, h + w), (0.0, h + w)])  # bottom flap
        dim_edges += [("length", (0.0, h + w), (l, h + w)),         # under flap
                      ("width", (0.0, -w), (0.0, 0.0)),             # left of flap
                      ("height", (xs[4], 0.0), (xs[4], h))]         # right of strip
    else:                                                  # tetrahedron strip
        e = dv["edge"] * px
        ht = e * math.sqrt(3.0) / 2.0
        b = [(0.0, 0.0), (e, 0.0), (2 * e, 0.0)]
        u = [(e / 2.0, -ht), (1.5 * e, -ht), (2.5 * e, -ht)]
        faces += [[b[0], b[1], u[0]], [b[1], u[0], u[1]],
                  [b[1], b[2], u[1]], [b[2], u[1], u[2]]]
        dim_edges.append(("edge", b[0], b[1]))

    nfaces = len(faces)
    if labels is not None:
        if not isinstance(labels, (list, tuple)) or len(labels) != nfaces:
            raise TemplateError(f"{kind}: labels must name all {nfaces} faces "
                                f"— got {labels!r}")
        for lt in labels:
            if not isinstance(lt, str) or not _LETTER.fullmatch(lt):
                raise TemplateError(f"{kind}: face labels are single capitals "
                                    f"— got {lt!r}")
        if len(set(labels)) != len(labels):
            raise TemplateError(f"{kind}: face labels repeat — {labels}")
    # corner anchors for the claims are UNPRINTED — pick letters outside the
    # caller's label pool so an anchor can never alias a face letter
    spare = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in (labels or [])]
    if len(spare) < 6:
        raise TemplateError(f"{kind}: the face labels take every spare capital — "
                            "no letters remain for the corner anchors")
    an1, an2, an3, an4, an5, an6 = spare[:6]
    min_side = min(vc.dist(f[i], f[(i + 1) % len(f)]) for f in faces
                   for i in range(len(f)))
    need_side = 40.0 if labels else 30.0
    if min_side < need_side:
        raise TemplateError(f"{kind}: the thinnest face draws {min_side:g} "
                            f"units (needs {need_side:g}) — raise scale_px")
    span = max(max(p[0] for f in faces for p in f) - min(p[0] for f in faces for p in f),
               max(p[1] for f in faces for p in f) - min(p[1] for f in faces for p in f))
    if span > 1200.0:
        raise TemplateError(f"{kind}: the net spans {span:g} units — over 1200 "
                            "renders unreadably small; lower scale_px")

    # ── unique edges: boundary solid, shared (fold) dashed ───────────────
    edge_seen: dict[tuple, int] = {}
    edge_ids: dict[tuple, str] = {}

    def ekey(a, b):
        ka, kb = (round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3))
        return (ka, kb) if ka <= kb else (kb, ka)

    vc.reset_ids()
    elements: list[dict] = []
    for fi, f in enumerate(faces):
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            k = ekey(a, b)
            edge_seen[k] = edge_seen.get(k, 0) + 1
            edge_ids.setdefault(k, f"e{len(edge_ids)}")
    for k, n in edge_seen.items():          # insertion order — stable emission
        (a, b) = k
        elements.append(vc.line(a, b, id=edge_ids[k], dashed=(n == 2)))
    folds = sorted(edge_ids[k] for k, n in edge_seen.items() if n == 2)

    claims: list[tuple[str, str, str]] = []
    anchors: dict[str, tuple[float, float]] = {}

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    def centroid(f):
        return (sum(p[0] for p in f) / len(f), sum(p[1] for p in f) / len(f))

    if shape == "cube":
        anchors[an1], anchors[an2], anchors[an3] = \
            faces[1][0], faces[1][1], faces[1][2]
        anchors[an4], anchors[an5], anchors[an6] = \
            faces[4][0], faces[4][1], faces[4][2]
        add(f"right {an1} {an2} {an3}", "measured", "a corner of a square face")
        add(f"right {an4} {an5} {an6}", "measured", "a corner of the square flap")
        add("derive 4 + 2 = 6", "inferred",
            "four squares in the row and two flaps — a cube's six faces")
        add(f'describe "a cube net: {nfaces} square faces joined by '
            f'{len(folds)} dashed fold edges"', "inferred", "the cross layout")
    elif shape == "cuboid":
        anchors[an1], anchors[an2], anchors[an3] = \
            faces[0][0], faces[0][1], faces[0][2]
        anchors[an4], anchors[an5], anchors[an6] = \
            faces[4][0], faces[4][1], faces[4][2]
        add(f"right {an1} {an2} {an3}", "measured", "a corner of the front face")
        add(f"right {an4} {an5} {an6}", "measured", "a corner of the top flap")
        add("derive 4 + 2 = 6", "inferred",
            "four side faces in the strip and two end faces — a cuboid's six")
        add(f'describe "a cuboid net: {nfaces} rectangular faces joined by '
            f'{len(folds)} dashed fold edges"', "inferred", "the strip layout")
    else:
        b0, b1, b2 = faces[0][0], faces[0][1], faces[2][1]
        u0, u1, u2 = faces[0][2], faces[1][2], faces[3][2]
        anchors[an1], anchors[an2], anchors[an3] = b0, b1, b2
        anchors[an4], anchors[an5], anchors[an6] = u0, u1, u2
        add(f"equal {an1}{an2} {an2}{an3}", "measured", "equilateral edges on the strip")
        add(f"equal {an4}{an5} {an5}{an6}", "measured", "equilateral edges on the strip")
        add("derive 1 + 1 + 1 + 1 = 4", "inferred",
            "the strip is four triangular faces — a tetrahedron's four")
        add(f'describe "a tetrahedron net: {nfaces} equilateral-triangle '
            f'faces joined by {len(folds)} dashed fold edges"', "inferred",
            "the parallelogram strip")

    # face letters at centroids — each names the face's INTERIOR (a `region_`
    # target, the venn_sets convention): an area label's roomiest point sits
    # legitimately far from every outline, so the visual-check target rule
    # skips it while edge/stroke clearance still measures.
    dim_glyphs = []
    if labels:
        for i, (lt, f) in enumerate(zip(labels, faces)):
            elements.append(vc.text(centroid(f), lt, id=f"fl{i}", size=15))
            add(f'label "{lt}" names region_face{i}', "inferred",
                f"the letter inside face {i + 1}")

    # dimension labels — a label-only `point` (r=0) anchored on the edge's
    # outward normal, its label seated ~30u off the edge.  A whole net renders
    # ~0.35 px/unit, where the build-time stroke floor (~25u from the edge) all
    # but meets the visual target ceiling (1.5·fontSize ≈ 27u): a `point`
    # label is measured to its own `at` — 16u off the edge on the measurement
    # normal, like a leader's station — instead of to the paint, so the glyph
    # can sit honestly far enough out without tripping either rule.
    net_c = (sum(p[0] for f in faces for p in f) / sum(len(f) for f in faces),
             sum(p[1] for f in faces for p in f) / sum(len(f) for f in faces))
    seen_dim_glyphs = set()
    for i, (k_, a, b) in enumerate(dim_edges):
        v = dv[k_]
        g = f"{v:g} {unit}" if unit else f"{v:g}"
        if labels and g in labels:
            raise TemplateError(f"{kind}: dim glyph {g!r} collides with a face letter")
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        ux, uy = vc.unit(a, b)
        nx, ny = -uy, ux                                  # a unit edge normal
        if (mid[0] - net_c[0]) * nx + (mid[1] - net_c[1]) * ny < 0:
            nx, ny = -nx, -ny                             # …outward of the net
        w_lab = vt._label_width(g, vt.FS)
        hu, hd = 0.70 * vt.FS, 0.58 * vt.FS               # label-box up/down
        half_n = w_lab * abs(nx) / 2.0 + (hu + hd) * abs(ny) / 2.0
        ctr = (mid[0] + (30.0 + half_n) * nx,
               mid[1] + (30.0 + half_n) * ny)             # box centre
        anch_xy = (ctr[0] - w_lab / 2.0, ctr[1] + (hu - hd) / 2.0)
        at = (mid[0] + 16.0 * nx, mid[1] + 16.0 * ny)
        elements.append({"type": "point", "id": f"dim{i}", "at": list(at),
                         "r": 0, "label": g,
                         "labelOffset": [anch_xy[0] - at[0], anch_xy[1] - at[1]]})
        if g in seen_dim_glyphs:
            add(f'describe "{g} also prints on another edge"', "inferred",
                "a repeated dimension binds one claim")
        else:
            seen_dim_glyphs.add(g)
            add(f'label "{g}" names {edge_ids[ekey(a, b)]}', "inferred",
                f"the {k_} on a boundary edge")
        dim_glyphs.append(g)

    if values == "figure":
        add('describe "the printed dimensions are figure content — the '
            'student reads the net"', "inferred", "read-off mode")
    add(f'describe "the {len(folds)} dashed segments are the fold edges"',
        "inferred", "internal shared edges draw dashed; the boundary is solid")
    add("none angleMark parallelMark tickMark arrow shaded circle grid",
        "inferred", "face outlines and fold lines only")

    names = {"cube": "cube", "cuboid": "cuboid",
             "tetrahedron": "tetrahedron"}[shape]
    budget = len(elements) if len(elements) > 32 else None
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                     anchors=anchors, points=list(anchors), segments=[],
                     claims=claims, ask=ask,
                     title=title or f"A {names} net",
                     description=description or
                     f"The canonical net of a {names}; dashed edges are the "
                     "fold lines.",
                     scale="one physical scale throughout — face edges draw "
                           "proportional to the declared dimensions",
                     budget=budget, medium=medium)
