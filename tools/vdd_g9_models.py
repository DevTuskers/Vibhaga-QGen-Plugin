"""vdd_g9_models.py — bounded G9 models for patterns, fractions and outcomes.

Five bounded builders covering the inventory's confirmed residuals
(wt/g9-readiness/inventory.md, packages B6/B7/B8), each matching an actual
G9 source figure shape:

  • matchstick_pattern(kind="diamond_chain") — L03's matchstick figures: a
    k diamond units with vertex contacts; each consecutive pair also has
    a single lower horizontal connector, so stage k draws
    4*k + (k-1) sticks (the shared vertex is counted once per diamond, the
    connector is the added stick). One panel per stage, a stage numeral
    marking each panel.
  • sequence_jumps — L03's sequence diagrams: the terms in a row with an arc
    beneath each consecutive pair labelled "+d" — the common difference shown
    as repeated jumps (the lesson prints 4 such figures; KaTeX cannot draw
    the arcs).
  • fraction_disc — L04's circular fraction models: panels of a circle
    divided into k EQUAL sectors with m consecutive sectors shaded, including
    the two-panel 8/8 + 3/8 = 1 3/8 improper-fraction figure.
  • polygon_spinner(n=5|6|8) — L24's resting spinners: a regular n-gon
    divided into n equal triangular sectors, outcomes[0] in the bottom
    (resting) sector, the rest clockwise, a pointer arrow above.
  • die_faces — L24's flat die faces: square faces in canonical face-pip
    layout (2/3 on a diagonal, 6 in two columns), in one row (<=3) or two
    rows of three — flat, never the dishonest perspective cuboid.

Numeric inputs pass ONE gate before any arithmetic — bools, strings and
non-finite numbers are refused before int/finite conversion. `values="stem"`
stem-checks every printed count; `values="figure"` declares the counts
figure content. Claims are emitted by the same code that draws, tied to the
computed ink (T-QG-2).

This module is NOT registered in vdd_templates.TEMPLATES — the lead actor
owns that file; registration is a one-line lazy entry there.
"""
from __future__ import annotations

import math
import re
import inspect
from functools import wraps

import vdd_cookbook as vc

XY = tuple[float, float]

_re_glyph = re.compile(r"^[A-Za-z0-9+\-*/=°]{1,4}$")
_re_num = re.compile(r"^[+\-]?\d+(?:\.\d+)?$")
_signed_tokens = re.compile(r"(?<![\w.+\-−–])([+\-−–]?\s*\d+(?:\.\d+)?)(?!\w|\.\d)")


def _entry(builder):
    signature = inspect.signature(builder)

    @wraps(builder)
    def checked(*args, **kwargs):
        from vdd_templates import TemplateError
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as exc:
            raise TemplateError(f"{builder.__name__}: {exc}") from None
        for key in ("figure_id", "stem"):
            if not isinstance(bound.arguments.get(key), str):
                raise TemplateError(f"{builder.__name__}: {key} must be text")
        for key in ("title", "description", "medium", "values", "kind"):
            value = bound.arguments.get(key)
            if value is not None and not isinstance(value, str):
                raise TemplateError(f"{builder.__name__}: {key} must be text")
        ask = bound.arguments.get("ask")
        if ask is not None and (
            not isinstance(ask, (list, tuple)) or not ask
            or any(not isinstance(part, (list, tuple)) or len(part) != 2
                   or not all(isinstance(item, str) for item in part) for part in ask)
        ):
            raise TemplateError(f"{builder.__name__}: ask must list pairs of text")
        return builder(*args, **kwargs)

    return checked


def _require_signed(stem, **values):
    import vdd_templates as vt
    vt.require_stem(stem, **{name: abs(v) for name, v in values.items()})
    tokens = [float(re.sub(r"\s+", "", token).replace("−", "-").replace("–", "-"))
              for token in _signed_tokens.findall(stem)]
    for name, value in values.items():
        if value not in tokens:
            raise vt.TemplateError(f"{name}={value:g} is not a signed number the stem states")


def _num(kind: str, name: str, v):
    """The numeric gate EVERY spec value passes before any arithmetic — bools,
    strings and non-finite numbers are refused before int/finite conversion."""
    from vdd_templates import TemplateError
    if (isinstance(v, bool) or not isinstance(v, (int, float))
            or abs(v) > 10**12 or not math.isfinite(v)):
        raise TemplateError(f"{kind}: {name} must be a bounded finite number")
    return v


def _glyph(s: str) -> bool:
    return bool(_re_glyph.fullmatch(s))


def _is_num(s: str) -> bool:
    return bool(_re_num.fullmatch(s))


def _values(kind: str, values: str) -> str:
    from vdd_templates import TemplateError
    values = str(values).strip().lower()
    if values not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure' — got {values!r}")
    return values


def _budget(elements):
    return len(elements) if len(elements) > 32 else None





@_entry
def build_matchstick_pattern(*, figure_id, stem, stages, kind="diamond_chain",
                             values="stem", ask=None, title=None,
                             description=None, medium="english",
                             half_w=22.0, half_h=32.0):
    """One panel per stage 1..`stages` of the diamond matchstick chain.

    Stage k is k diamonds in a row — neighbours touch at one side vertex and
    are joined by a horizontal matchstick between their bottom vertices —
    so it draws 4*k + (k-1) sticks. A stage numeral marks each panel.
    `stages` is 1–4 (element budget). `values="stem"` requires the
    stage count in the stem; the per-stage stick counts are computed and
    claimed via `stage`/`derive` lines — `values="figure"` declares them
    figure content (the student counts the sticks)."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind_name = "matchstick_pattern"
    vc.reset_ids()
    if kind != "diamond_chain":
        raise TemplateError(f"{kind_name}: only kind='diamond_chain' is "
                            "implemented — other matchstick geometries are out of scope")
    values = _values(kind_name, values)
    stages = _num(kind_name, "stages", stages)
    if not float(stages).is_integer() or not 1 <= int(stages) <= 4:
        raise TemplateError(f"{kind_name}: stages {stages!r} must be a whole number in 1–4")
    stages = int(stages)
    half_w = _num(kind_name, "half_w", half_w)
    half_h = _num(kind_name, "half_h", half_h)
    if not 16 <= half_w <= 40 or not 16 <= half_h <= 44:
        raise TemplateError(f"{kind_name}: diamond half-extents {half_w:g}x{half_h:g} "
                            "are outside 16–40 x 16–44 units")
    if values == "stem":
        vt.require_stem(stem, stages=stages)

    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))


    num_gap = 24.0
    panel_gap = 60.0
    x_off = 0.0
    cy = 0.0
    for k in range(1, stages + 1):
        x0 = x_off + half_w
        for i in range(k):
            cx = x0 + 2 * half_w * i
            t, r_, b, l_ = (cx, cy - half_h), (cx + half_w, cy), (cx, cy + half_h), (cx - half_w, cy)
            elements += [vc.line(t, r_, id=f"s{k}_{i}a"),
                         vc.line(r_, b, id=f"s{k}_{i}b"),
                         vc.line(b, l_, id=f"s{k}_{i}c"),
                         vc.line(l_, t, id=f"s{k}_{i}d")]
            if i:
                elements.append(vc.line((cx - 2 * half_w, cy + half_h), b, id=f"s{k}_{i}j"))
        sticks = 4 * k + (k - 1)

        elements.append(vc.text((x0 - half_w - num_gap - 6, cy), f"{k}",
                                id=f"stnum{k}"))
        x_off += half_w * (2 * k - 1) + half_w + panel_gap

        add(f"stage {k} shows {sticks} sticks", "inferred",
            f"{k} diamond{'s' if k > 1 else ''} = 4*{k} sticks plus {k - 1} "
            "bottom connector(s), counted on the drawn figure")
        add(f"derive 4 * {k} + ( {k} - 1 ) = {sticks}", "inferred",
            "4 sticks per diamond, one bottom-connector stick per added diamond")
        add(f'label "{k}" names stage{k}', "inferred",
            "the stage numeral printed beside the panel")
    add('describe "each panel is a row of diamonds marked by a stage '
        'numeral beside it; neighbouring diamonds touch at one side vertex '
        'and are joined by one horizontal matchstick along the bottom"',
        "inferred", "the chain structure of every stage")
    if values == "figure":
        add('describe "the stick counts are figure content — the student '
            'counts the matchsticks on each stage"', "inferred",
            "values='figure' read-off mode")
    add("none arc arrow tickMark parallelMark angleMark angleArc dashed shaded",
        "inferred", "matchsticks are straight strokes; numerals are circled, not marked")

    return vt.finish(kind=kind_name, figure_id=figure_id, stem=stem,
                     elements=elements, anchors={}, points=[], segments=[],
                     claims=claims, ask=ask,
                     title=title or "A matchstick pattern of diamonds",
                     description=description or (
                         f"Panels 1 to {stages} of a matchstick pattern; panel k "
                         "is a row of k diamonds, each pair joined along the "
                         "bottom by one horizontal matchstick, with a stage "
                         "numeral beside the panel."),
                     scale="stick lengths are a canvas choice — only the stick "
                           "COUNT per stage matters",
                     budget=_budget(elements), medium=medium)





@_entry
def build_sequence_jumps(*, figure_id, stem, first, difference, terms,
                         values="stem", ask=None, title=None, description=None,
                         medium="english"):
    """A row of `terms` terms with an arc under each consecutive pair labelled
    "+d"/"-d" — the lesson's common-difference figure.

    `first` and `difference` are integers; `difference != 0`; `terms` 2–7.
    In `values="stem"` mode the stem must state EVERY printed term and the
    signed difference (a stem that gives only the rule belongs in
    `values="figure"`, which declares the printed terms figure content)."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind = "sequence_jumps"
    vc.reset_ids()
    values = _values(kind, values)
    first = _num(kind, "first", first)
    difference = _num(kind, "difference", difference)
    terms = _num(kind, "terms", terms)
    for name, v in (("first", first), ("difference", difference), ("terms", terms)):
        if not float(v).is_integer():
            raise TemplateError(f"{kind}: {name} {v:g} must be a whole number — "
                                "the lesson's jump figures are integer sequences")
    first, difference, terms = int(first), int(difference), int(terms)
    if difference == 0:
        raise TemplateError(f"{kind}: a zero difference draws a constant row — "
                            "that is a stem sentence, not this figure")
    if not 2 <= terms <= 7:
        raise TemplateError(f"{kind}: terms {terms} is outside 2–7")
    seq = [first + i * difference for i in range(terms)]
    if max(abs(v) for v in seq) > 9999:
        raise TemplateError(f"{kind}: term {max(seq, key=abs)} is too wide to print")
    if values == "stem":
        for i, v in enumerate(seq):
            _require_signed(stem, **{f"term{i + 1}": v})
        _require_signed(stem, difference=difference)


    span_guess = (terms - 1) * 100.0
    lab_size = 16.0
    widest = max(vt._label_width(f"{v:g}", lab_size) for v in seq)
    widest = max(widest, vt._label_width(f"{difference:+g}", lab_size))
    spacing = max(80.0, widest + vt._clearance_units(4.0 + 1.0, span_guess) + 44.0)
    sag = 24.0
    chord = spacing
    r = (sag * sag + (chord / 2) ** 2) / (2 * sag)
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    y_term, y_chord = 0.0, 26.0
    xs = [i * spacing for i in range(terms)]
    for i, v in enumerate(seq):
        elements.append(vc.text((xs[i], y_term), f"{v:g}", id=f"term{i + 1}", size=lab_size))
    for i in range(terms - 1):
        mid = (xs[i] + xs[i + 1]) / 2
        cc = (mid, y_chord - (r - sag))
        a0 = math.degrees(math.atan2(y_chord - cc[1], xs[i] - cc[0]))
        a1 = math.degrees(math.atan2(y_chord - cc[1], xs[i + 1] - cc[0]))

        elements += [vc.polyline(vc.sampled_arc(cc, r, a1, a0), id=f"jump{i + 1}"),
                     vc.text((mid, y_chord + sag + 27), f"{difference:+g}",
                             id=f"jlbl{i + 1}", size=lab_size)]
        add(f"derive {seq[i + 1]:g} - {seq[i]:g} = {difference:g}", "inferred",
            "the jump under this arc, computed from the printed terms")

    seen = set()
    for i, v in enumerate(seq):
        g = f"{v:g}"
        if g in seen:
            continue
        seen.add(g)
        add(f'label "{g}" names term{i + 1}', "stem" if values == "stem" else "inferred",
            "a printed term of the sequence")
    add(f'label "{difference:+g}" names jump1', "stem" if values == "stem" else "inferred",
        "the jump label under every arc — the common difference")
    add(f'describe "a shallow arc joins each consecutive pair of terms; every '
        f'arc is labelled {difference:+g} — the constant jump between terms"',
        "inferred", "the arcs show the common difference as repeated equal jumps")
    if values == "figure":
        add('describe "the printed terms are figure content — the student reads '
            'the sequence and its jumps off the figure"', "inferred",
            "values='figure' read-off mode")
    add("none circle arc arrow tickMark parallelMark angleMark dashed shaded",
        "inferred", "terms, jump curves (polylines) and jump labels only")

    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors={}, points=[], segments=[],
                     claims=claims, ask=ask,
                     title=title or "A number sequence with its jumps",
                     description=description or (
                         f"The terms {', '.join(f'{v:g}' for v in seq)} in a row; "
                         f"an arc beneath each consecutive pair is labelled "
                         f"{difference:+g}, the common difference."),
                     scale="arc height and spacing are canvas choices — only the "
                           "terms and the jump value matter",
                     medium=medium)





@_entry
def build_fraction_disc(*, figure_id, stem, panels, values="stem", ask=None,
                        title=None, description=None, medium="english",
                        radius=80.0):
    """1–3 fraction circles, each divided into `sectors` EQUAL sectors with
    `shaded` consecutive sectors shaded (from the top, clockwise) — the
    lesson's circle fraction model, including its two-panel improper
    figure (8 of 8 plus 3 of 8).

    `panels` is a list of (sectors, shaded) pairs or {"sectors","shaded"}
    dicts; sectors 2–12, shaded 0..sectors. `values="stem"` stem-checks every
    panel's sector count AND shaded count; `values="figure"` declares the
    shaded counts figure content (the student writes the fraction)."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind = "fraction_disc"
    vc.reset_ids()
    values = _values(kind, values)
    if not isinstance(panels, (list, tuple)) or not 1 <= len(panels) <= 3:
        raise TemplateError(f"{kind}: panels must be a list of 1–3 "
                            "(sectors, shaded) entries")
    parsed = []
    for i, p in enumerate(panels):
        if isinstance(p, dict):
            if set(p) != {"sectors", "shaded"}:
                raise TemplateError(f"{kind}: each panel needs exactly sectors and shaded")
            k, m = p["sectors"], p["shaded"]
        elif isinstance(p, (list, tuple)) and len(p) == 2:
            k, m = p
        else:
            raise TemplateError(f"{kind}: panel {i + 1} must be a (sectors, shaded) pair")
        k = _num(kind, f"panel {i + 1} sectors", k)
        m = _num(kind, f"panel {i + 1} shaded", m)
        if not float(k).is_integer() or not 2 <= int(k) <= 12:
            raise TemplateError(f"{kind}: panel {i + 1} sectors {k!r} must be a whole number in 2–12")
        if not float(m).is_integer() or not 0 <= int(m) <= int(k):
            raise TemplateError(f"{kind}: panel {i + 1} shaded {m!r} must be a whole number in 0–{int(k)}")
        parsed.append((int(k), int(m)))
    panels = parsed
    radius = _num(kind, "radius", radius)
    if not 40 <= radius <= 110:
        raise TemplateError(f"{kind}: radius {radius:g} is outside 40–110 units")
    if values == "stem":
        for i, (k, m) in enumerate(panels):
            vt.require_stem(stem, **{f"panel{i + 1}_sectors": k, f"panel{i + 1}_shaded": m})

    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []
    anchors: dict[str, XY] = {}

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    names = "CDE"
    for i, (k, m) in enumerate(panels):
        c = (i * (2 * radius + 70.0), 0.0)
        anchors[names[i]] = c
        elements.append(vc.circle(c, radius, id=f"disc{i + 1}"))
        for j in range(k):
            a0 = -90 + j * 360.0 / k
            if j < m:
                pts = [c] + vc.sampled_arc(c, radius, a0, a0 + 360.0 / k)
                elements.append(vc.polygon(pts, fill=vc.SHADE, stroke_width=0,
                                           id=f"sh{i + 1}_{j + 1}"))
            elements.append(vc.line(c, vc.polar(c, radius, a0), id=f"cut{i + 1}_{j + 1}"))
        add(f"circle centre {names[i]} radius {radius:g}", "inferred",
            f"panel {i + 1}'s outline — the radius is a canvas choice")
        add(f'shaded {m} of {k} sectors on panel{i + 1}', "stem" if values == "stem" else "inferred",
            "equal sectors, shaded count as drawn")
        add(f'describe "panel {i + 1} is a circle divided into {k} equal '
            f'sectors; {m} consecutive sector{"s are" if m != 1 else " is"} '
            f'shaded — the fraction {m}/{k}"', "inferred",
            "the equal-sector fraction model")
        add(f"derive {k} - {m} = {k - m}", "inferred",
            "the unshaded sectors of this panel")
    if len(panels) > 1 and len({k for k, _ in panels}) == 1:
        k = panels[0][0]
        total = sum(m for _, m in panels)
        add("derive " + " + ".join(f"{m}" for _, m in panels) + f" = {total}",
            "inferred", f"shaded parts across the panels, all in {k}ths")
    if values == "figure":
        add('describe "the shaded counts are figure content — the student '
            'writes the fraction each panel shows"', "inferred",
            "values='figure' read-off mode")
    add("none arrow tickMark parallelMark angleMark angleArc dashed",
        "inferred", "circle outlines, equal-sector radii and shading only")

    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors=anchors,
                     points=list(anchors), segments=[], claims=claims, ask=ask,
                     title=title or "Fraction circles",
                     description=description or (
                         "; ".join(f"a circle in {k} equal sectors with {m} shaded"
                                   for k, m in panels).capitalize() + "."),
                     scale="the disc radius is a canvas choice — only the sector "
                           "counts and shading matter",
                     budget=_budget(elements), medium=medium)





@_entry
def build_polygon_spinner(*, figure_id, stem, n, outcomes, values="stem",
                          ask=None, title=None, description=None,
                          medium="english", radius=92.0):
    """A regular n-gon spinner (n = 5, 6 or 8) divided into n equal triangular
    sectors, resting flat on its bottom edge. `outcomes` lists the n sector
    glyphs clockwise starting at the BOTTOM (resting) sector — numerals or
    short symbolic tokens, never prose. A pointer arrow above the polygon
    marks where it is spun.

    `values="stem"` stem-checks n and every NUMERIC outcome glyph;
    `values="figure"` declares the outcomes figure content (the student
    lists the sample space off the figure)."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind = "polygon_spinner"
    vc.reset_ids()
    values = _values(kind, values)
    n = _num(kind, "n", n)
    if not float(n).is_integer() or int(n) not in (5, 6, 8):
        raise TemplateError(f"{kind}: n {n!r} must be 5, 6 or 8 — the lesson's "
                            "resting spinners are the pentagon, hexagon and octagon")
    n = int(n)
    if not isinstance(outcomes, (list, tuple)) or len(outcomes) != n:
        raise TemplateError(f"{kind}: outcomes must list exactly {n} sector glyphs")
    outs = []
    for i, o in enumerate(outcomes):
        if isinstance(o, bool):
            raise TemplateError(f"{kind}: outcome {i + 1} must be a glyph, not a bool")
        if isinstance(o, (int, float)):
            o = _num(kind, f"outcome {i + 1}", o)
            o = f"{o:g}"
        if not isinstance(o, str):
            raise TemplateError(f"{kind}: outcome {i + 1} must be a numeral or symbolic text")
        o = o.strip()
        if not _glyph(o):
            raise TemplateError(f"{kind}: outcome {i + 1} {o!r} must be 1–4 plain "
                                "ASCII glyphs (a numeral or symbol, not prose)")
        outs.append(o)
    radius = _num(kind, "radius", radius)
    if not 56 <= radius <= 130:
        raise TemplateError(f"{kind}: radius {radius:g} is outside 56–130 units")
    if values == "stem":
        vt.require_stem(stem, sectors=n)
        numeric = {f"outcome{i + 1}": float(o) for i, o in enumerate(outs)
                   if _is_num(o)}
        if numeric:
            _require_signed(stem, **numeric)

    c = (0.0, 0.0)
    step = 360.0 / n
    verts = [vc.polar(c, radius, 90 - step / 2 + i * step) for i in range(n)]
    elements: list[dict] = [vc.polygon(verts, id="wheel"),
                            vc.circle(c, 4, fill=vc.INK, id="hub")]
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    for i in range(n):
        elements.append(vc.line(c, verts[i], id=f"spoke{i + 1}"))

    s_, c_ = math.sin(math.pi / n), math.cos(math.pi / n)
    t_lab = c_ / (s_ + c_)
    for i, o in enumerate(outs):
        mid = 90 + i * step
        elements.append(vc.text(vc.polar(c, radius * t_lab, mid), o,
                                id=f"out{i + 1}", size=14.0))

    top_y = min(v[1] for v in verts)
    elements.append(vc.arrow((c[0], top_y - 52), (c[0], top_y - 10), id="pointer"))

    seen = set()
    for i, o in enumerate(outs):
        if o in seen:
            continue
        seen.add(o)
        add(f'label "{o}" names sector{i + 1}', "stem" if values == "stem" and _is_num(o)
            else "inferred", "a sector outcome glyph")
    add(f"derive 360 / {n} = {360 // n}", "inferred",
        "the central angle of each equal sector")
    add(f'describe "a regular {n}-sided spinner divided into {n} equal '
        f'triangular sectors; the sector holding {outs[0]} rests flat on '
        f'the bottom edge, and a pointer above marks the spin"', "inferred",
        "the resting-spinner figure; outcomes run clockwise from the bottom sector")
    if values == "figure":
        add('describe "the sector outcomes are figure content — the student '
            'lists the possible results off the spinner"', "inferred",
            "values='figure' read-off mode")
    add("none arc tickMark parallelMark angleMark angleArc dashed shaded",
        "inferred", "polygon outline, spokes, outcome glyphs, hub dot and pointer only")

    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors={}, points=[], segments=[],
                     claims=claims, ask=ask,
                     title=title or f"A {n}-sector spinner",
                     description=description or (
                         f"A regular {n}-sided spinner resting on its bottom "
                         f"edge, divided into {n} equal triangular sectors "
                         f"showing {', '.join(outs)} clockwise from the bottom; "
                         "a pointer arrow above marks where it is spun."),
                     scale="the polygon radius is a canvas choice — only the "
                           "equal sectors and their outcomes matter",
                     budget=_budget(elements), medium=medium)





_PIPS = {
    1: [(0, 0)],
    2: [(-1, -1), (1, 1)],
    3: [(-1, -1), (0, 0), (1, 1)],
    4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
    5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
    6: [(-1, -1), (-1, 0), (-1, 1), (1, -1), (1, 0), (1, 1)],
}


@_entry
def build_die_faces(*, figure_id, stem, faces, values="figure", ask=None,
                    title=None, description=None, medium="english",
                    side=64.0):
    """Flat square die faces in canonical pip layout — one row of up to 3, or
    two rows of three for 4–6 faces (the lesson's own arrangements). Never a
    perspective cuboid: the pip COUNT per face is the whole content.

    `faces` lists the pip counts 1–6, in order. `values="stem"` additionally
    requires the face count in the stem; either way the per-face pip counts
    are figure content (the student counts the pips)."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind = "die_faces"
    vc.reset_ids()
    values = _values(kind, values)
    if not isinstance(faces, (list, tuple)) or not 1 <= len(faces) <= 6:
        raise TemplateError(f"{kind}: faces must be a list of 1–6 pip counts")
    fs = []
    for i, f in enumerate(faces):
        f = _num(kind, f"face {i + 1}", f)
        if not float(f).is_integer() or not 1 <= int(f) <= 6:
            raise TemplateError(f"{kind}: face {i + 1} is {f!r} — a die face "
                                "carries 1–6 pips")
        fs.append(int(f))
    side = _num(kind, "side", side)
    if not 40 <= side <= 110:
        raise TemplateError(f"{kind}: side {side:g} is outside 40–110 units")
    if values == "stem":
        vt.require_stem(stem, faces=len(fs))

    gap = side * 0.55
    rows = [fs] if len(fs) <= 3 else [fs[:3], fs[3:]]
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    for ri, row in enumerate(rows):
        y = ri * (side + gap)
        for ci, f in enumerate(row):
            x = ci * (side + gap)
            elements.append({"id": f"face{ri + 1}{ci + 1}", "type": "rect",
                             "x": vc.r2(x), "y": vc.r2(y),
                             "width": vc.r2(side), "height": vc.r2(side)})
            for pi, (px, py) in enumerate(_PIPS[f]):
                elements.append(vc.circle(
                    (x + side / 2 + px * side / 4, y + side / 2 + py * side / 4),
                    side / 11, fill=vc.INK, id=f"pip{ri + 1}{ci + 1}_{pi + 1}"))
            add(f'describe "face {ri * 3 + ci + 1} shows {f} pip{"s" if f > 1 else ""} '
                f'in the standard die layout"', "inferred",
                "flat face, canonical pip positions — counted on the drawing")
    add("derive " + " + ".join(str(f) for f in fs) + f" = {sum(fs)}", "inferred",
        "the pips across every shown face, counted")
    add('describe "square die faces drawn flat — no perspective, no hidden '
        'faces; only the pip counts matter"', "inferred",
        "a flat face row, not a 3-D cube")
    if values == "figure":
        add('describe "the pip counts are figure content — the student counts '
            'the pips on each face"', "inferred", "values='figure' read-off mode")
    add("none arc arrow tickMark parallelMark angleMark angleArc dashed shaded",
        "inferred", "square outlines and filled pips only")

    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors={}, points=[], segments=[],
                     claims=claims, ask=ask,
                     title=title or "Die faces",
                     description=description or (
                         f"{len(fs)} flat die face{'s' if len(fs) > 1 else ''} "
                         f"showing {', '.join(str(f) for f in fs)} "
                         "pip(s) in the standard layouts."),
                     scale="face size is a canvas choice — only the pip counts "
                           "and their canonical positions matter",
                     budget=_budget(elements), medium=medium)
