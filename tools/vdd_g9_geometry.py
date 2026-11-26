"""vdd_g9_geometry.py — the G9 open-line / locus / regular-polygon families.

Three bounded builders covering the confirmed geometry residuals of
`wt/g9-readiness/inventory.md` (packages B4, B5 and the polygon half of B7):

  • `build_marked_lines` — L08/L15/L16 open-line mathematics: rays at a common
    vertex, a point on a straight line with rays, two crossing lines, two
    parallels cut by a transversal, and a collinear segment with division
    points and validated equality ticks.  No caller coordinates: division
    points and crossings are fractions/intersections the builder computes, so
    a tick or an `equal`/`collinear` claim can never disagree with the ink.

  • `build_locus_scene` — L13 locus mathematics: a circle locus, the
    perpendicular-bisector locus, the parallel-offset (fixed distance from a
    line) locus and the angle-bisector locus.  Sample points, perpendicular
    feet and the midpoint are COMPUTED; the caller names them, never places
    them.  The locus itself is dashed, matching the corpus convention.

  • `build_polygon_angles` — L25 regular n-gon angle mathematics: equal
    interior-arc figures, the one-vertex triangulation fan, the centre-joined
    n-triangle figure, and produced-side exterior angles.

Every number that carries meaning is either stem-checked (`values="stem"`),
declared figure content (`values="figure"`), or computed here — a drawn tick,
arc or `equal`/`right`/`parallel` claim is re-validated against the computed
geometry and anything the geometry cannot honestly carry is a TemplateError,
never a fudged mark.  Arbitrary coordinate soup, irregular n-gons, compass
traces and decorative locus artwork stay outside the contract.

This module is NOT registered in vdd_templates.TEMPLATES — the lead actor owns
that file; registration is a one-line lazy entry there.  vdd_templates itself
is imported lazily inside the builders so this module stays import-light.
"""
from __future__ import annotations

import math
import re
from itertools import combinations

import vdd_cookbook as vc

_LETTER = re.compile(r"^[A-Z]$")
_GLYPH = re.compile(r"^[A-Za-z][A-Za-z0-9' ]{0,7}$|^\d+(?:\.\d+)?°?$")
_FOOT_POOL = "FGHIJKNQRSTUWXYZ"


def _num(kind: str, name: str, v):
    """The numeric gate EVERY spec value passes before any arithmetic — bools,
    strings and non-finite numbers are refused before int/finite conversion."""
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


def _letters(kind: str, name: str, seq) -> list[str]:
    from vdd_templates import TemplateError
    if isinstance(seq, str):
        seq = list(seq)
    if not isinstance(seq, (list, tuple)) or not seq:
        raise TemplateError(f"{kind}: {name} must be a non-empty list of capitals")
    out = []
    for x in seq:
        if not isinstance(x, str) or not _LETTER.fullmatch(x):
            raise TemplateError(f"{kind}: {name} entries are single capital letters — got {x!r}")
        out.append(x)
    if len(set(out)) != len(out):
        raise TemplateError(f"{kind}: {name} repeats a letter — {out}")
    return out


def _rays_map(kind: str, rays, lo=2, hi=6) -> dict[str, float]:
    from vdd_templates import TemplateError
    if not isinstance(rays, dict) or not lo <= len(rays) <= hi:
        raise TemplateError(f"{kind}: rays must be a dict of {lo}–{hi} {{letter: deg}}")
    out = {}
    for k, v in rays.items():
        if not isinstance(k, str) or not _LETTER.fullmatch(k):
            raise TemplateError(f"{kind}: ray names are single capitals — got {k!r}")
        out[k] = _num(kind, f"ray {k} deg", v) % 360.0
    dirs = sorted(out.values())
    if len(dirs) < 2:
        return out
    for i, d in enumerate(dirs):
        gap = (dirs[(i + 1) % len(dirs)] - d) % 360.0
        if gap < 10.0:
            raise TemplateError(
                f"{kind}: two rays sit {gap:g}° apart — a wedge under 10° cannot "
                "mark or read honestly at figure size")
    return out


def _angle_between(d1: float, d2: float) -> float:
    """The smaller angle between two directions (degrees), in (0, 180]."""
    return min((d2 - d1) % 360.0, (d1 - d2) % 360.0)


def _adjacent_pairs(rays: dict[str, float]) -> list[tuple[str, str]]:
    """Consecutive (cyclic) direction pairs at a shared vertex — the wedges an arc may mark."""
    order = sorted(rays, key=rays.get)
    out = []
    for i in range(len(order)):
        gap = (rays[order[(i + 1) % len(order)]] - rays[order[i]]) % 360.0
        if gap <= 180.0:
            out.append((order[i], order[(i + 1) % len(order)]))

    return out


def _parse_mark_label(kind: str, lab, deg: float, at: str, a1: str, a2: str,
                      values: str, stem):
    """Validate one mark label against the COMPUTED angle.  Returns (printed
    text, numeric value or None).  A numeric label that disagrees with the
    drawn angle is a refusal — the figure never asserts a wrong size."""
    from vdd_templates import TemplateError
    import vdd_templates as vt
    if lab is None:
        return None, None
    if isinstance(lab, bool):
        raise TemplateError(f"{kind}: mark label {lab!r} is not a glyph")
    if isinstance(lab, (int, float)):
        v = _num(kind, f"mark label on {a1}{a2}", lab)
    elif isinstance(lab, str):
        if not _GLYPH.fullmatch(lab):
            raise TemplateError(f"{kind}: mark label {lab!r} — glyphs are short letters "
                                "or numbers (drawn text is simple English)")
        v = float(lab.rstrip("°")) if re.fullmatch(r"\d+(?:\.\d+)?°?", lab) else None
    else:
        raise TemplateError(f"{kind}: mark label {lab!r} is not a glyph")
    if v is None:
        return str(lab), None
    if abs(v - deg) > 0.5:
        raise TemplateError(f"{kind}: label {v:g}° at {at} misstates the drawn {deg:g}° "
                            "— fix the label, never the figure")
    if values == "stem":
        vt.require_stem(stem, **{f"angle {a1}{at}{a2}": v})
    return f"{v:g}°", v


def _check_marks(kind: str, marks, allowed_pairs: dict, letter_names):
    """Validate an arc-mark list.  `allowed_pairs` maps a vertex letter to the
    set of frozenset arm pairs that bound drawn wedges there (None as key = the
    figure's single vertex)."""
    from vdd_templates import TemplateError
    if marks is None:
        return []
    if not isinstance(marks, (list, tuple)) or len(marks) > 8:
        raise TemplateError(f"{kind}: marks must be a list of at most 8 arc marks")
    seen, out = set(), []
    for i, m in enumerate(marks):
        if not isinstance(m, dict) or not set(m) <= {"arms", "at", "arcs", "label"}:
            raise TemplateError(f"{kind}: mark {i + 1} keys must be arms/at/arcs/label")
        at = m.get("at")
        if at is not None and (not isinstance(at, str) or not _LETTER.fullmatch(at)):
            raise TemplateError(f"{kind}: mark {i + 1} `at` must be a vertex "
                                f"capital or absent — got {at!r}")
        arms = m.get("arms")
        if not isinstance(arms, (list, tuple)) or len(arms) != 2 or arms[0] == arms[1]:
            raise TemplateError(f"{kind}: mark {i + 1} needs two distinct arm letters")
        for a_ in arms:
            if not isinstance(a_, str) or not _LETTER.fullmatch(a_):
                raise TemplateError(f"{kind}: mark {i + 1} arms are single capitals")
            if a_ not in letter_names:
                raise TemplateError(f"{kind}: mark {i + 1} names {a_!r}, which is not an "
                                    "endpoint of the figure")
        key = at if len(allowed_pairs) > 1 else None
        if len(allowed_pairs) == 1 and at not in (None, *allowed_pairs):
            raise TemplateError(f"{kind}: mark {i + 1} `at` must be the figure's "
                                "single vertex")
        if key not in allowed_pairs:
            raise TemplateError(f"{kind}: mark {i + 1} `at` must be one of "
                                f"{sorted(x for x in allowed_pairs if x)}")
        pair = frozenset(arms)
        if pair not in allowed_pairs[key]:
            raise TemplateError(f"{kind}: mark {i + 1} arms {tuple(arms)} bound no drawn "
                                "wedge — arcs may mark only adjacent rays at their vertex")
        if (key, pair) in seen:
            raise TemplateError(f"{kind}: two marks on the same wedge {tuple(arms)}")
        seen.add((key, pair))
        arcs = m.get("arcs", 1)
        if isinstance(arcs, bool) or not isinstance(arcs, int) or not 1 <= arcs <= 3:
            raise TemplateError(f"{kind}: mark {i + 1} arcs must be a whole 1–3")
        out.append({"at": key, "arms": (arms[0], arms[1]), "arcs": arcs,
                    "label": m.get("label")})
    return out


def _tick_classes():
    """A fresh drawn-length → tick-count registry.  Equal lengths share one
    tick count; DIFFERENT lengths take the next count — a global tick class
    may never assert equality between unequal pairs."""
    reg = {}

    def cls(px):
        return reg.setdefault(round(px, 1), len(reg) + 1)

    return cls


def _point_label(anchor, letter: str):
    """A floating point letter — finish() seats it clear of the ink."""
    return {"type": "text", "id": f"t{letter}", "at": [0, 0], "value": letter,
            "align": "middle", "baseline": "middle", "_near": list(anchor)}


def _values_mode(kind: str, values) -> str:
    from vdd_templates import TemplateError
    v = str(values).strip().lower()
    if v not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure' — got {values!r}")
    return v





def build_marked_lines(*, figure_id, stem, profile,
                       rays=None, vertex="O",
                       lines=None, transversal=None, crossings=("X", "Y"),
                       parallel_marks=True,
                       segment=None, divisions=None, equal=None,
                       length=None, unit=None, labels=None,
                       marks=None, draw_length=150.0,
                       values="stem", ask=None, title=None, description=None,
                       medium="english"):
    """Straight-line / angle profiles without a closed polygon.

    `profile` is one of:

      • "rays"          — `rays={letter: deg}` 2–6 rays at `vertex` (no two
                          180° apart — that is "point_on_line").
      • "point_on_line" — `rays` containing exactly ONE opposite pair (the
                          straight line) plus 1–4 further rays at `vertex`.
      • "cross"         — `lines={"AB": deg, "CD": deg}`: two full lines
                          through `vertex`; the four wedges are computed.
      • "transversal"   — `lines={"AB": deg, "CD": deg}` at equal degs (the
                          parallels) + `transversal={"PQ": deg}`; the two
                          crossings are COMPUTED and named by `crossings`.
      • "divided"       — `segment=("A","B")` with `rays={"A": deg}` giving the
                          direction; `divisions={letter: t}` 1–3 interior
                          points at fraction t∈[0.08,0.92] of AB (COMPUTED);
                          `equal=[[sub,sub], …]` up to 3 disjoint groups of
                          consecutive sub-segments drawn with tick counts —
                          a group that is not equal as drawn refuses.

    `marks=[{arms:(L1,L2), at:<vertex>, arcs:1–3, label:glyph}]` draws angle
    arcs; only arms bounding a drawn wedge are accepted, and a numeric label
    must equal the computed angle — the figure never asserts an angle the
    geometry does not carry.

    `length`/`unit`/`labels` put a physical scale on "divided" segments:
    `labels={"AP": "6 cm"}` prints a length label that must restate the
    sub-segment's share of `length` within 0.5% (and be a stem number in
    `values="stem"` mode).  Direction degrees are canvas choices, never data;
    the data are the givens the claims emit.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "marked_lines"

    if profile not in ("rays", "point_on_line", "cross", "transversal", "divided"):
        raise TemplateError(f"{kind}: profile must be rays|point_on_line|cross|"
                            f"transversal|divided — got {profile!r}")
    if not isinstance(vertex, str) or not _LETTER.fullmatch(vertex):
        raise TemplateError(f"{kind}: vertex must be one capital letter")
    values = _values_mode(kind, values)
    draw_length = _num(kind, "draw_length", draw_length)
    if not 90.0 <= draw_length <= 320.0:
        raise TemplateError(f"{kind}: draw_length {draw_length:g} outside 90–320 units")
    if unit is not None and (not isinstance(unit, str) or not unit.strip()):
        raise TemplateError(f"{kind}: unit must be a short string like 'cm'")
    if length is not None:
        length = _num(kind, "length", length)
        if length <= 0:
            raise TemplateError(f"{kind}: length must be positive")
        if values == "stem":
            vt.require_stem(stem, length=length)
    elif labels:
        raise TemplateError(f"{kind}: labels need a declared `length` to restate")
    if profile != "divided" and labels:
        raise TemplateError(f"{kind}: printed length labels belong to profile='divided'")
    if profile == "divided" and marks:
        raise TemplateError(f"{kind}: a straight segment carries no angle marks")

    vc.reset_ids()
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []
    anchors: dict[str, tuple[float, float]] = {}
    declared_segments: list[str] = []
    mark_specs: list[dict] = []
    wedges = None
    dir_of = {}

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    if profile in ("rays", "point_on_line"):
        rd = _rays_map(kind, rays, lo=2, hi=6)
        if vertex in rd:
            raise TemplateError(f"{kind}: a ray cannot share the vertex letter {vertex}")
        names = list(rd)
        opp = [(x, y) for x, y in combinations(names, 2)
               if abs(_angle_between(rd[x], rd[y]) - 180.0) < 1e-6]
        if profile == "rays" and opp:
            raise TemplateError(f"{kind}: rays {opp[0]} are 180° apart — that is "
                                "profile='point_on_line' (a straight line, not free rays)")
        if profile == "point_on_line":
            if len(opp) != 1:
                raise TemplateError(f"{kind}: 'point_on_line' needs exactly one pair of rays "
                                    "180° apart (the straight line)")
            if len(rd) < 3:
                raise TemplateError(f"{kind}: 'point_on_line' needs ≥3 rays — the line plus "
                                    "a ray")
        V = (0.0, 0.0)
        anchors[vertex] = V
        for lt, dg in rd.items():
            anchors[lt] = vc.polar(V, draw_length, dg)
            elements.append(vc.line(V, anchors[lt], id=f"ray{lt}"))
        for lt in rd:
            elements.append(_point_label(anchors[lt], lt))
        elements.append(_point_label(V, vertex))
        if opp:
            add(f"collinear {opp[0][0]} {vertex} {opp[0][1]}", "measured",
                "the two opposite rays form the straight line")
        dir_of = {lt: rd[lt] for lt in rd}
        wedges = {frozenset(p) for p in _adjacent_pairs(rd)}
        mark_specs = _check_marks(kind, marks, {None: wedges}, set(anchors))
    elif profile == "cross":
        if not isinstance(lines, dict) or len(lines) != 2:
            raise TemplateError(f"{kind}: 'cross' needs lines={{\"AB\": deg, \"CD\": deg}}")
        ends = {}
        for pair, dg in lines.items():
            _letters(kind, f"line {pair!r}", pair)
            if len(pair) != 2:
                raise TemplateError(f"{kind}: line keys are two capitals — got {pair!r}")
            if vertex in pair:
                raise TemplateError(f"{kind}: a line endpoint cannot share the vertex letter")
            ends[pair] = _num(kind, f"line {pair} deg", dg) % 360.0
        (p1, d1), (p2, d2) = ends.items()
        sep = _angle_between(d1, d2)
        if not 15.0 <= sep <= 165.0:
            raise TemplateError(f"{kind}: the lines meet at {sep:g}° — under 15° the wedges "
                                "cannot carry arcs honestly (parallel lines are "
                                "profile='transversal')")
        V = (0.0, 0.0)
        anchors[vertex] = V
        for pair, d in ends.items():
            anchors[pair[0]] = vc.polar(V, draw_length, d)
            anchors[pair[1]] = vc.polar(V, draw_length, d + 180.0)
            elements.append(vc.line(anchors[pair[0]], anchors[pair[1]], id=f"line{pair}"))
        for lt in (p1 + p2):
            elements.append(_point_label(anchors[lt], lt))
        elements.append(_point_label(V, vertex))
        add(f"collinear {p1[0]} {vertex} {p1[1]}", "measured", f"{p1} is a straight line")
        add(f"collinear {p2[0]} {vertex} {p2[1]}", "measured", f"{p2} is a straight line")
        add(f"nonparallel {p1} {p2}", "measured",
            f"the two lines cross at {sep:g}°, not parallel")
        dir_of = {p1[0]: d1, p1[1]: (d1 + 180.0) % 360.0,
                  p2[0]: d2, p2[1]: (d2 + 180.0) % 360.0}
        wedges = {frozenset(p) for p in _adjacent_pairs(dir_of)}
        mark_specs = _check_marks(kind, marks, {None: wedges}, set(anchors))
    elif profile == "transversal":
        if not isinstance(lines, dict) or len(lines) != 2:
            raise TemplateError(f"{kind}: 'transversal' needs lines={{\"AB\": deg, \"CD\": deg}}")
        ends = {}
        for pair, dg in lines.items():
            _letters(kind, f"line {pair!r}", pair)
            if len(pair) != 2:
                raise TemplateError(f"{kind}: line keys are two capitals — got {pair!r}")
            ends[pair] = _num(kind, f"line {pair} deg", dg) % 360.0
        if not isinstance(transversal, dict) or len(transversal) != 1:
            raise TemplateError(f"{kind}: transversal must be {{\"PQ\": deg}}")
        (tpair, tdeg), = transversal.items()
        _letters(kind, "transversal", tpair)
        if len(tpair) != 2:
            raise TemplateError(f"{kind}: the transversal key is two capitals — got {tpair!r}")
        tdeg = _num(kind, "transversal deg", tdeg) % 360.0
        names_all = list(ends)[0] + list(ends)[1] + tpair
        _letters(kind, "endpoint letters", names_all)
        cx = _letters(kind, "crossings", crossings)
        if len(cx) != 2:
            raise TemplateError(f"{kind}: crossings names the two crossings — two letters")
        for c in cx:
            if c in names_all:
                raise TemplateError(f"{kind}: crossing letter {c} collides with an endpoint")
        (p1, d1), (p2, d2) = ends.items()
        if _angle_between(d1, d2) > 0.5:
            raise TemplateError(f"{kind}: the two lines differ by "
                                f"{_angle_between(d1, d2):g}° — 'transversal' draws "
                                "PARALLEL lines (crossing lines are profile='cross')")
        sep = _angle_between(d1, tdeg)
        if not 20.0 <= sep <= 160.0:
            raise TemplateError(f"{kind}: the transversal meets the parallels at {sep:g}° — "
                                "under 20° the eight wedges cannot mark honestly")
        gap = draw_length * 0.55
        u = (math.cos(math.radians(d1)), math.sin(math.radians(d1)))
        tv = (math.cos(math.radians(tdeg)), math.sin(math.radians(tdeg)))

        along = gap / math.sin(math.radians(sep))
        c1 = (0.0, 0.0)
        c2 = (c1[0] + tv[0] * along, c1[1] + tv[1] * along)

        half_len = draw_length / 2.0 + gap / abs(math.tan(math.radians(sep)))
        anchors[cx[0]], anchors[cx[1]] = c1, c2
        anchors[p1[0]] = (c1[0] - u[0] * half_len, c1[1] - u[1] * half_len)
        anchors[p1[1]] = (c1[0] + u[0] * half_len, c1[1] + u[1] * half_len)
        anchors[p2[0]] = (c2[0] - u[0] * half_len, c2[1] - u[1] * half_len)
        anchors[p2[1]] = (c2[0] + u[0] * half_len, c2[1] + u[1] * half_len)
        elements.append(vc.line(anchors[p1[0]], anchors[p1[1]], id=f"line{p1}"))
        elements.append(vc.line(anchors[p2[0]], anchors[p2[1]], id=f"line{p2}"))
        anchors[tpair[0]] = (c1[0] - tv[0] * half_len * 0.4, c1[1] - tv[1] * half_len * 0.4)
        anchors[tpair[1]] = (c2[0] + tv[0] * half_len * 0.4, c2[1] + tv[1] * half_len * 0.4)
        elements.append(vc.line(anchors[tpair[0]], anchors[tpair[1]], id=f"line{tpair}"))
        if parallel_marks:
            elements += vc.parallel_marks(anchors[p1[0]], anchors[p1[1]])
            elements += vc.parallel_marks(anchors[p2[0]], anchors[p2[1]])
            add(f"parallel {p1} {p2}", "measured",
                "the two lines carry matching parallel marks")
        add(f"collinear {p1[0]} {cx[0]} {p1[1]}", "measured", f"{cx[0]} lies on {p1}")
        add(f"collinear {p2[0]} {cx[1]} {p2[1]}", "measured", f"{cx[1]} lies on {p2}")
        add(f"collinear {tpair[0]} {cx[0]} {cx[1]}", "measured", "the transversal is straight")
        add(f"collinear {cx[0]} {cx[1]} {tpair[1]}", "measured", "the transversal is straight")
        for lt in anchors:
            elements.append(_point_label(anchors[lt], lt))

        arms_at = {cx[0]: {p1[0], p1[1], tpair[0], cx[1]},
                   cx[1]: {p2[0], p2[1], cx[0], tpair[1]}}
        straight_at = {cx[0]: {frozenset(p1), frozenset((tpair[0], cx[1]))},
                       cx[1]: {frozenset(p2), frozenset((cx[0], tpair[1]))}}
        allowed = {at: {frozenset(pr) for pr in combinations(arms_at[at], 2)}
                   - straight_at[at] for at in cx}
        dir_of = {at: {lt: vc.angle_of(anchors[lt], anchors[at])
                       for lt in arms_at[at]} for at in cx}
        mark_specs = _check_marks(kind, marks, allowed, set(anchors))
    else:
        sn = _letters(kind, "segment", segment)
        if len(sn) != 2:
            raise TemplateError(f"{kind}: 'divided' needs segment=(\"A\",\"B\")")
        rd = _rays_map(kind, rays, lo=1, hi=1)
        if list(rd)[0] != sn[0]:
            raise TemplateError(f"{kind}: rays must give {sn[0]}'s direction — "
                                f"{{'{sn[0]}': deg}}")
        d_ab = rd[sn[0]]
        if not isinstance(divisions, dict) or not 1 <= len(divisions) <= 3:
            raise TemplateError(f"{kind}: divisions must be 1–3 {{letter: fraction}}")
        divs = {}
        for lt, t in divisions.items():
            if not isinstance(lt, str) or not _LETTER.fullmatch(lt):
                raise TemplateError(f"{kind}: division names are single capitals")
            if lt in sn:
                raise TemplateError(f"{kind}: division {lt} collides with a segment end")
            t = _num(kind, f"division {lt}", t)
            if not 0.08 <= t <= 0.92:
                raise TemplateError(f"{kind}: division {lt} at {t:g} — keep t in "
                                    "(0.08, 0.92) so the point and its label read")
            divs[lt] = t
        order = sorted(divs, key=divs.get)
        for a_, b_ in zip(order, order[1:]):
            if divs[b_] - divs[a_] < 0.12:
                raise TemplateError(f"{kind}: divisions {a_} and {b_} are under 12% of "
                                    "the segment apart — crowded marks lie")
        A = anchors[sn[0]] = (0.0, 0.0)
        B = anchors[sn[1]] = vc.polar(A, draw_length, d_ab)
        for lt in order:
            anchors[lt] = vc.lerp(A, B, divs[lt])
        elements.append(vc.line(A, B, id="seg"))
        for lt in anchors:
            elements.append(_point_label(anchors[lt], lt))
        chain = [sn[0]] + order + [sn[1]]
        for a_, b_, c_ in zip(chain, chain[1:], chain[2:]):
            add(f"collinear {a_} {b_} {c_}", "measured", "ordered along the segment")
        for lt in order:
            add(f"on {lt} {sn[0]}{sn[1]}", "measured", "a computed fraction of the segment")
        used = set()
        if equal:
            if not isinstance(equal, (list, tuple)) or not equal or len(equal) > 3:
                raise TemplateError(f"{kind}: equal takes 1–3 disjoint groups")
            subs = {a_ + b_ for a_, b_ in zip(chain, chain[1:])}
            for gi, group in enumerate(equal):
                if not isinstance(group, (list, tuple)) or not 2 <= len(group) <= 3:
                    raise TemplateError(f"{kind}: equal group {gi + 1} needs 2–3 sub-segments")
                for s in group:
                    if not isinstance(s, str) or len(s) != 2:
                        raise TemplateError(f"{kind}: sub-segment names are two letters — {s!r}")
                    if s not in subs:
                        raise TemplateError(f"{kind}: {s!r} is not a consecutive sub-segment "
                                            f"of {''.join(chain)} — a tick on a composite "
                                            "length asserts nothing")
                    if s in used:
                        raise TemplateError(f"{kind}: sub-segment {s} is in two equal groups")
                    used.add(s)
                d0 = vc.dist(anchors[group[0][0]], anchors[group[0][1]])
                for s in group[1:]:
                    d1 = vc.dist(anchors[s[0]], anchors[s[1]])
                    if abs(d0 - d1) / max(d0, d1) > 0.02:
                        raise TemplateError(
                            f"{kind}: group {group} is NOT equal as drawn "
                            f"({d0:.1f} vs {d1:.1f} units) — ticks would lie; "
                            "change the division fractions")
                for s in group:
                    elements += vc.tick_marks(anchors[s[0]], anchors[s[1]], count=gi + 1)
                for s in group[1:]:
                    add(f"equal {group[0]} {s}", "measured",
                        f"{gi + 1}-tick group — validated equal")
        if labels:
            if not isinstance(labels, dict):
                raise TemplateError(f"{kind}: labels must be a dict "
                                    "{sub-segment: glyph}")
            subs_all = {a_ + b_ for a_, b_ in zip(chain, chain[1:])}
            phys = {s: (vc.dist(anchors[s[0]], anchors[s[1]]) / draw_length) * length
                    for s in subs_all}
            claimed_glyphs = set()
            for s, glyph in labels.items():
                if s not in subs_all:
                    raise TemplateError(f"{kind}: label names {s!r}, not a consecutive "
                                        f"sub-segment of {''.join(chain)}")
                if isinstance(glyph, bool) or not isinstance(glyph, (int, float, str)):
                    raise TemplateError(f"{kind}: label {glyph!r} on {s} is not a glyph")
                v = None
                if isinstance(glyph, (int, float)):
                    v = _num(kind, f"label {s}", glyph)
                else:
                    mnum = re.fullmatch(r"(\d+(?:\.\d+)?)(?:\s*([A-Za-z]+))?", glyph)
                    if mnum:
                        v = float(mnum.group(1))
                        if mnum.group(2) is not None and mnum.group(2) != (unit or ""):
                            raise TemplateError(f"{kind}: label {glyph!r} carries unit "
                                                f"{mnum.group(2)!r} — the figure's "
                                                f"declared unit is {unit!r}")
                    elif not re.fullmatch(r"[A-Za-z]+", glyph):
                        raise TemplateError(f"{kind}: label {glyph!r} on {s} is not a "
                                            "measure or a simple glyph — signed, "
                                            "malformed and non-finite values refuse")
                if v is not None:
                    want = phys[s]
                    if abs(v - want) / want > 0.005:
                        raise TemplateError(f"{kind}: label {glyph!r} on {s} must restate its "
                                            f"share of the declared length "
                                            f"({want:g}{' ' + unit if unit else ''})")
                    if values == "stem":
                        vt.require_stem(stem, **{f"label {s}": v})
                mid = vc.lerp(anchors[s[0]], anchors[s[1]], 0.5)
                elements.append({"type": "text", "id": f"len{s}", "at": [0, 0],
                                 "value": str(glyph), "align": "middle",
                                 "baseline": "middle", "_near": list(mid), "_gap": 16})
                if str(glyph) in claimed_glyphs:

                    add(f'describe "{glyph} also prints on {s}"', "inferred",
                        "a repeated measure on an equal part")
                else:
                    claimed_glyphs.add(str(glyph))
                    add(f'label "{glyph}" names {s}', "inferred", "a printed length")
            declared_segments = list(labels)


    glyph_seen = set()
    numeric_wedges = []
    for m in mark_specs:
        at = m["at"] if m["at"] is not None else vertex
        a1, a2 = m["arms"]
        sub = dir_of[at] if isinstance(dir_of.get(at), dict) else dir_of
        deg = _angle_between(sub[a1], sub[a2])
        text_lab, lv = _parse_mark_label(kind, m["label"], deg, at, a1, a2, values, stem)
        if text_lab:
            if text_lab in glyph_seen:
                raise TemplateError(f"{kind}: glyph {text_lab!r} prints twice — a drawn "
                                    "glyph binds one claim; equal angles take equal arcs")
            glyph_seen.add(text_lab)
        elements += vc.angle_label(anchors[at], anchors[a1], anchors[a2],
                                   r=28, label=None, arcs=m["arcs"])
        if text_lab:

            u1 = vc.unit(anchors[at], anchors[a1])
            u2 = vc.unit(anchors[at], anchors[a2])
            bx, by = u1[0] + u2[0], u1[1] + u2[1]
            bl = math.hypot(bx, by) or 1.0

            r_lab = 48.0 + 6.0 * (m["arcs"] - 1) + 6.0 * len(text_lab)
            pos = (anchors[at][0] + bx / bl * r_lab, anchors[at][1] + by / bl * r_lab)
            elements.append({"type": "text", "id": f"gl{a1}{at}{a2}",
                             "at": list(pos), "value": text_lab,
                             "align": "middle", "baseline": "middle"})
        if text_lab:
            add(f'label "{text_lab}" names {a1}{at}{a2}', "inferred", "the arc's glyph")
        if lv is not None:
            if values == "stem":
                add(f"angle {a1} {at} {a2} = {deg:g}", "measured",
                    "the printed numeral equals the drawn wedge")
            else:
                add(f'describe "the arc at {at} on arms {a1} and {a2} is marked '
                    f'{deg:g}° — figure content"', "inferred",
                    "read-off mode: the numeral is what the student reads")
            numeric_wedges.append(deg)
        else:
            add(f'describe "an arc marks angle {a1}{at}{a2}"', "inferred",
                f"{m['arcs']}-arc mark" + (f" labelled {text_lab}" if text_lab else ""))
    if profile == "point_on_line" and len(numeric_wedges) >= 2 \
            and abs(sum(numeric_wedges) - 180.0) < 1.0:
        add(f"derive {' + '.join(f'{v:g}' for v in numeric_wedges)} = 180", "inferred",
            "the marked angles stand on the straight line")
    elif profile == "point_on_line":

        d_opp = sorted(dir_of[o] for o in opp[0])
        others = sorted(d for d in dir_of.values()
                        if not any(abs(d - x) < 1e-9 for x in d_opp))
        def _side(base):
            return sorted((d - base) % 360.0 for d in others
                          if 0.0 < (d - base) % 360.0 < 180.0)
        side = _side(d_opp[0]) if len(_side(d_opp[0])) >= len(_side(d_opp[1])) \
            else _side(d_opp[1])
        base = d_opp[0] if len(_side(d_opp[0])) >= len(_side(d_opp[1])) else d_opp[1]
        seq = [0.0] + side + [180.0]
        add(f"derive {' + '.join(f'{seq[i + 1] - seq[i]:g}' for i in range(len(seq) - 1))} = 180",
            "inferred", "the rays fan the straight line's 180°")
    elif profile == "rays":
        dirs_sorted = sorted(dir_of.values())
        add(f"derive {' + '.join(f'{(dirs_sorted[(i + 1) % len(dirs_sorted)] - dirs_sorted[i]) % 360.0:g}' for i in range(len(dirs_sorted)))} = 360",
            "inferred", "the angles at the point go once round")
    elif profile == "cross":
        dirs_sorted = sorted(dir_of.values())
        add(f"derive {_angle_between(dirs_sorted[0], dirs_sorted[1]):g} + "
            f"{_angle_between(dirs_sorted[1], dirs_sorted[2]):g} = 180", "inferred",
            "neighbouring wedges on a straight line are supplementary")
    elif profile == "transversal":
        s_ = _angle_between(d1, tdeg)
        add(f"derive {s_:g} + {180.0 - s_:g} = 180", "inferred",
            "adjacent crossing angles are supplementary")
    elif profile == "divided":
        if length is not None:
            t_first = divs[order[0]]
            add(f"derive {t_first:g} * {length:g} = {t_first * length:g}", "inferred",
                "the first division's share of the declared length")
        else:
            t_first = divs[order[0]]
            add(f"derive {t_first:g} + {1.0 - t_first:g} = 1", "inferred",
                "the fractions along the segment sum to the whole")

    for lt in anchors:

        if any(el.get("value") == lt for el in elements if el["type"] == "text"):
            add(f'label "{lt}" names {lt}', "inferred", "a point letter")
    if profile == "divided" and not equal:
        add("none parallelMark angleMark angleArc arrow dashed shaded tickMark",
            "inferred", "a straight segment and division points only")
    elif profile == "divided":
        add("none parallelMark angleMark angleArc arrow dashed shaded", "inferred",
            "a straight segment with division ticks only")
    else:
        add("none tickMark dashed shaded"
            + ("" if profile == "transversal" and parallel_marks else " parallelMark"),
            "inferred", "segments, dots and arcs only")
    if values == "figure" and profile != "divided":
        add('describe "the marked angles are figure content — the student reads '
            'the figure"', "inferred", "read-off mode")

    title_d = title or {
        "rays": "Rays meeting at a point",
        "point_on_line": "Angles on a straight line",
        "cross": "Two intersecting straight lines",
        "transversal": "Parallel lines cut by a transversal",
        "divided": "A divided line segment"}[profile]
    desc_d = description or {
        "rays": f"Rays from point {vertex} with marked angles between them.",
        "point_on_line": f"A straight line through {vertex} with further rays "
                         "and marked angles.",
        "cross": f"Two straight lines crossing at {vertex} with marked angles.",
        "transversal": "Two parallel straight lines cut by a transversal; the "
                       "crossing points are marked.",
        "divided": "A straight segment with interior division points; matching "
                   "tick counts mark equal sub-segments."}[profile]
    scale = ("the declared length applies to the named segment; spacing is a "
             "canvas choice" if length is not None else
             "not to scale — directions and spacing are canvas choices; only "
             "the marks and named points carry meaning")
    budget = len(elements) if len(elements) > 32 else None
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors=anchors, points=list(anchors),
                     segments=declared_segments, claims=claims, ask=ask,
                     title=title_d, description=desc_d, scale=scale,
                     budget=budget, medium=medium)





def _build_locus_setup(vt, figure_id, stem, constraints, ask, title, description, medium):
    if not isinstance(constraints, (list, tuple)) or not 1 <= len(constraints) <= 4:
        raise vt.TemplateError("locus_scene: setup needs 1–4 constraints")
    counts = {"circle": 1, "perp_bisector": 2, "parallel_offset": 2, "angle_bisector": 3}
    anchors, elements, claims, segments = {}, [], [], []
    for constraint in constraints:
        if not isinstance(constraint, dict) or set(constraint) - {"kind", "points", "distance"}:
            raise vt.TemplateError("locus_scene: setup constraint is {kind, points, distance?}")
        kind, points = constraint.get("kind"), constraint.get("points")
        if not isinstance(kind, str) or kind not in counts or not isinstance(points, dict) or len(points) != counts[kind]:
            raise vt.TemplateError("locus_scene: supply the centre, segment ends, or vertex and arm ends")
        names = list(points)
        if any(not isinstance(n, str) or not _LETTER.fullmatch(n) for n in names):
            raise vt.TemplateError("locus_scene: setup points need capital letters")
        if kind in ("circle", "parallel_offset"):
            d = _num(kind, "distance", constraint.get("distance"))
            if d <= 0:
                raise vt.TemplateError("locus_scene: distance must be positive")
            vt.require_stem(stem, distance=d)
        elif "distance" in constraint:
            raise vt.TemplateError("locus_scene: this setup constraint does not take a distance")
        for name, xy in points.items():
            if not isinstance(xy, (list, tuple)) or len(xy) != 2:
                raise vt.TemplateError("locus_scene: setup point must be (x, y)")
            at = tuple(_num(kind, name, v) for v in xy)
            if name in anchors and anchors[name] != at:
                raise vt.TemplateError(f"locus_scene: contradictory coordinates for {name}")
            if any(n != name and math.dist(at, p) < 1 for n, p in anchors.items()):
                raise vt.TemplateError("locus_scene: different setup letters cannot coincide")
            anchors[name] = at
        edges = [(names[0], name) for name in names[1:]]
        if kind == "angle_bisector":
            (x, y), (a, b), (c, d) = (anchors[n] for n in names)
            if abs((a - x) * (d - y) - (b - y) * (c - x)) < 1e-6:
                raise vt.TemplateError("locus_scene: angle setup arms cannot be collinear")
        for a, b in edges:
            if a + b not in segments and b + a not in segments:
                segments.append(a + b)
                elements.append(vc.line(anchors[a], anchors[b], id=f"given{a}{b}"))
        claims.append((f'describe "the {kind.replace("_", " ")} setup shows only the given points and arms"',
                       "inferred", "the locus itself is left for the student"))
    for name, at in anchors.items():
        elements.append({"type": "point", "id": f"pt{name}", "at": vc.P(at), "r": 3})
        elements.append(vt.place_point_label(f"lb{name}", name, target=name, at=at))
        claims.append((f'label "{name}" names {name}', "inferred", "a given point"))
    claims.extend([(f"derive {' + '.join(map(str, (len(anchors), len(segments))))} = {len(anchors) + len(segments)}",
                    "inferred", "count of distinct given points and segments"),
                   ("none tickMark parallelMark angleMark shaded arrow dashed", "inferred", "no solution curves or marks")])
    return vt.finish(kind="locus_scene", figure_id=figure_id, stem=stem, ask=ask,
                     elements=elements, anchors=anchors, points=list(anchors),
                     segments=segments, claims=claims, medium=medium,
                     title=title or "Locus construction setup",
                     description=description or "The given points and lines for a locus construction.",
                     scale="setup reference geometry")


def build_locus_scene(*, figure_id, stem, kind=None,
                      centre="O", vertex="V",
                      segment=("A", "B"), line_deg=0.0, radius=None, distance=None,
                      unit=None, unit_px=25.0, length=None,
                      arms=None, samples=None,
                      draw_length=170.0,
                      values="stem", ask=None, title=None, description=None,
                      medium="english", stage="completed", constraints=None):
    """A locus figure with COMPUTED sample points, feet and midpoint.

    `kind` is one of:

      • "circle"          — `radius` physical; `samples={P: deg}` 2–4 points ON
                            the dashed circle, each joined to `centre` by a
                            one-tick radius.
      • "perp_bisector"   — `segment=("A","B")` at `line_deg`; midpoint M and
                            the dashed perpendicular through it are computed;
                            `samples={P: s}` 1–3 points on the bisector at
                            signed fraction s (|s| 0.15–0.95) of the drawn
                            bisector half-length, each joined to both ends
                            with its own tick count.  `length` may declare the
                            physical AB.
      • "parallel_offset" — `segment=("A","B")` at `line_deg`, `distance`
                            physical; two dashed parallels at that offset;
                            `samples={P: (side, t)}` side ±1, t∈[0.15,0.85]
                            along the line, each with a COMPUTED perpendicular
                            foot on AB, a right-angle square and one-tick
                            distance.
      • "angle_bisector"  — `vertex` V with `arms={"A": deg, "B": deg}`; the
                            bisector is computed; `samples={P: s}` 1–3 points
                            at fraction s∈[0.25,0.9] along it, each with
                            COMPUTED perpendicular feet on both arms,
                            right-angle squares and equal ticks.

    Drawn values that matter (`radius`, `distance`, `length`) are stem givens
    in `values="stem"` mode; `values="figure"` declares the figure readable.
    Direction degrees and `unit_px` are canvas choices, never data.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    if stage not in ("setup", "completed") or (stage == "completed" and constraints is not None):
        raise TemplateError("locus_scene: constraints are for stage='setup'")
    if stage == "setup":
        if kind is not None or samples is not None:
            raise TemplateError("locus_scene: setup uses constraints instead of a completed kind or samples")
        return _build_locus_setup(vt, figure_id, stem, constraints, ask, title, description, medium)
    if kind not in ("circle", "perp_bisector", "parallel_offset", "angle_bisector"):
        raise TemplateError(f"locus_scene: kind must be circle|perp_bisector|"
                            f"parallel_offset|angle_bisector — got {kind!r}")
    k = f"locus_{kind}"
    values = _values_mode(k, values)
    line_deg = _num(k, "line_deg", line_deg) % 360.0
    draw_length = _num(k, "draw_length", draw_length)
    if not 90.0 <= draw_length <= 300.0:
        raise TemplateError(f"{k}: draw_length {draw_length:g} outside 90–300 units")
    unit_px = _num(k, "unit_px", unit_px)
    if not 12.0 <= unit_px <= 60.0:
        raise TemplateError(f"{k}: unit_px {unit_px:g} outside 12–60")
    if unit is not None and (not isinstance(unit, str) or not unit.strip()):
        raise TemplateError(f"{k}: unit must be a short string like 'cm'")

    def given(name, v):
        v = _num(k, name, v)
        if v <= 0:
            raise TemplateError(f"{k}: {name} must be positive")
        if values == "stem":
            vt.require_stem(stem, **{name: v})
        return v

    def letter_ok(lt, what):
        if not isinstance(lt, str) or not _LETTER.fullmatch(lt):
            raise TemplateError(f"{k}: {what} must be one capital letter — got {lt!r}")

    def unused(pool, n_):
        free = [c for c in _FOOT_POOL if c not in pool]
        if len(free) < n_:
            raise TemplateError(f"{k}: not enough spare capital letters for feet")
        return free[:n_]

    vc.reset_ids()
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []
    anchors: dict[str, tuple[float, float]] = {}

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    declared_segments: list[str] = []

    def finish_(title_d, desc_d, scale):
        for lt in anchors:
            if any(el.get("value") == lt for el in elements if el["type"] == "text"):
                add(f'label "{lt}" names {lt}', "inferred", "a point letter")
        budget = len(elements) if len(elements) > 32 else None
        return vt.finish(kind=k, figure_id=figure_id, stem=stem, elements=elements,
                         anchors=anchors, points=list(anchors),
                         segments=declared_segments,
                         claims=claims, ask=ask, title=title_d,
                         description=desc_d, scale=scale, budget=budget,
                         medium=medium)

    def dim_label(near, on, value, *, side=None):
        """A floating physical-measure label seated beside a drawn segment —
        `values="figure"` never leaves a physical given undrawn, and `values=
        "stem"` keeps the stem's number honest on the figure itself."""
        if side is None:
            elements.append({"type": "text", "id": f"dim{on}", "at": [0, 0],
                             "value": value, "align": "middle",
                             "baseline": "middle", "_near": list(near), "_gap": 14})
        else:
            elements.append(vt._seat_side_label(k, elements, [], *side, value, near,
                                                14.0, f"dim{on}", keep_near=True, start=0.25))
        declared_segments.append(on)
        add(f'label "{value}" names {on}',
            "stem" if values == "stem" else "inferred",
            "the drawn physical measure")

    if kind == "circle":
        letter_ok(centre, "centre")
        radius = given("radius", radius)
        r_px = radius * unit_px
        if not 40.0 <= r_px <= 160.0:
            raise TemplateError(f"{k}: radius {radius:g} at {unit_px:g} px/unit draws "
                                f"{r_px:g} units — keep the drawn circle 40–160")
        O = (0.0, 0.0)
        anchors[centre] = O
        circ = vc.circle(O, r_px, id="locus")
        circ["stroke"] = {"width": 2.0, "color": vc.INK, "dash": [7, 6]}
        elements.append(circ)
        if not isinstance(samples, dict) or not 2 <= len(samples) <= 4:
            raise TemplateError(f"{k}: samples must be 2–4 {{letter: deg}}")
        for lt, s in samples.items():
            letter_ok(lt, "sample names")
            if lt == centre:
                raise TemplateError(f"{k}: sample {lt} collides with the centre")
            dg = _num(k, f"sample {lt}", s) % 360.0
            p = anchors[lt] = vc.polar(O, r_px, dg)
            elements.append(vc.line(O, p, id=f"rad{lt}"))
            elements += vc.tick_marks(O, p, count=1)
            elements.append(vc.dot(p, 3, id=f"dot{lt}"))
            elements.append(_point_label(p, lt))
        elements.append(vc.dot(O, 3.5, id=f"dot{centre}"))
        elements.append(_point_label(O, centre))
        names = list(samples)
        dim_label(vc.lerp(O, anchors[names[0]], 0.5), f"{centre}{names[0]}",
                  f"{radius:g}{' ' + unit if unit else ''}")
        add(f"circle centre {centre} through {' '.join(names[:3])}", "measured",
            "the locus: every sample is one radius from the centre")
        for i in range(1, len(names)):
            add(f"equal {centre}{names[0]} {centre}{names[i]}", "measured",
                "one-tick radii — every point of the locus is equidistant")
        add(f'describe "the dashed circle is the locus of points {radius:g}'
            f'{" " + unit if unit else ""} from {centre}; each segment to a sample '
            'is a radius carrying one tick"', "stem" if values == "stem" else "inferred",
            "locus convention — the curve is the answer, not a boundary")
        add(f"derive {radius:g} * 2 = {radius * 2:g}", "inferred",
            "the diameter is twice the radius")
        if values == "figure":
            add('describe "the radius is figure content — the student reads the '
                'locus off the drawing"', "inferred", "read-off mode")
        add("none parallelMark angleMark angleArc arrow shaded", "inferred",
            "dashed circle, radii and ticks only")
        return finish_(title or "Points at a fixed distance from a centre",
                       description or (
                           f"A dashed circle centred on {centre}; dots on the rim "
                           "are joined to the centre by equal ticked radii — the "
                           "locus of points a fixed distance away."),
                       f"1 unit = {unit_px:g} canvas px; the circle's drawn radius "
                       f"is {radius:g}{' ' + unit if unit else ''}")

    if kind == "perp_bisector":
        sn = _letters(k, "segment", segment)
        if len(sn) != 2:
            raise TemplateError(f"{k}: 'perp_bisector' needs segment=(\"A\",\"B\")")
        if "M" in sn or "U" in sn or "W" in sn:
            raise TemplateError(f"{k}: M/U/W are reserved (midpoint and bisector ends)")
        if length is not None:
            length = given("length", length)
        half = draw_length / 2.0
        A = vc.polar((0.0, 0.0), half, line_deg + 180.0)
        B = vc.polar((0.0, 0.0), half, line_deg)
        M = (0.0, 0.0)
        anchors[sn[0]], anchors[sn[1]], anchors["M"] = A, B, M
        elements.append(vc.line(A, B, id="seg"))
        pdeg = line_deg + 90.0
        blen = half * 1.1
        U = vc.polar(M, blen, pdeg + 180.0)
        W = vc.polar(M, blen, pdeg)
        anchors["U"], anchors["W"] = U, W
        elements.append(vc.line(U, W, dashed=True, id="locus"))
        elements += vc.right_angle_mask(M, A, U, size=13)
        elements += vc.right_angle_mark(M, A, U, r=13)
        elements.append(vc.dot(M, 3, id="dotM"))
        for lt in sn:
            elements.append(_point_label(anchors[lt], lt))

        if not isinstance(samples, dict) or not 1 <= len(samples) <= 3:
            raise TemplateError(f"{k}: samples must be 1–3 {{letter: s}}")
        sample_pts = []
        for lt, s in samples.items():
            letter_ok(lt, "sample names")
            if lt in anchors:
                raise TemplateError(f"{k}: sample {lt} collides with a named point")
            s = _num(k, f"sample {lt}", s)
            if not 0.15 <= abs(s) <= 0.95:
                raise TemplateError(f"{k}: sample {lt} offset {s:g} — keep |s| in "
                                    "0.15–0.95 of the bisector half-length")
            sample_pts.append((lt, vc.lerp(M, W, s) if s > 0 else vc.lerp(M, U, -s)))

        tc = _tick_classes()
        m_count = tc(vc.dist(A, M))
        s_counts = [tc(vc.dist(p, A)) for _, p in sample_pts]
        elements += vc.tick_marks(A, M, count=m_count) + vc.tick_marks(M, B, count=m_count)
        for i, (lt, p) in enumerate(sample_pts):
            anchors[lt] = p
            elements.append(vc.line(p, A, id=f"j{lt}a"))
            elements.append(vc.line(p, B, id=f"j{lt}b"))
            elements += vc.tick_marks(p, A, count=s_counts[i]) + \
                vc.tick_marks(p, B, count=s_counts[i])
            elements.append(vc.dot(p, 3, id=f"dot{lt}"))
            elements.append(_point_label(p, lt))
        add(f"collinear {sn[0]} M {sn[1]}", "measured", "M is the midpoint of the segment")
        add(f"equal {sn[0]}M M{sn[1]}", "measured",
            f"{m_count}-tick pair — the bisector bisects")
        add(f"right {sn[0]} M U", "measured", "the square marks the perpendicular")
        add("collinear U M W", "measured", "the dashed bisector is straight")
        if length is not None:
            u_b = vc.unit(A, B)
            nrm2 = (-u_b[1], u_b[0])
            busy = (sum(1 for _, p in sample_pts
                        if p[0] * nrm2[0] + p[1] * nrm2[1] > 0)
                    - sum(1 for _, p in sample_pts
                          if p[0] * nrm2[0] + p[1] * nrm2[1] < 0))
            side_d = -1.0 if busy > 0 else 1.0
            q = vc.lerp(A, M, 0.5)
            dim_label((q[0] + nrm2[0] * 20.0 * side_d,
                       q[1] + nrm2[1] * 20.0 * side_d),
                      f"{sn[0]}{sn[1]}",
                      f"{length:g}{' ' + unit if unit else ''}", side=(A, B))
        for i, (lt, _) in enumerate(sample_pts):
            add(f"on {lt} UW", "measured", "the sample sits on the bisector")
            add(f"equal {sn[0]}{lt} {lt}{sn[1]}", "measured",
                f"{s_counts[i]}-tick pair — a point on the perpendicular bisector "
                "is equidistant from the ends")
        add('describe "the dashed line is the perpendicular bisector of '
            f'{sn[0]}{sn[1]}; each sample point joins both ends with equal '
            'ticked segments — the locus of points equidistant from the ends"',
            "inferred", "locus convention")
        if length is not None:
            add(f'describe "the segment is {length:g}{" " + unit if unit else ""}"',
                "stem" if values == "stem" else "inferred", "the stem's given")
            add(f"derive {length:g} / 2 = {length / 2:g}", "inferred",
                "the midpoint halves the segment")
        else:
            add("derive 1 / 2 = 0.5", "inferred",
                "the midpoint halves the segment")
        add("none parallelMark angleArc arrow shaded", "inferred",
            "segment, dashed bisector, right square and ticks only")
        return finish_(title or "The perpendicular-bisector locus",
                       description or (
                           f"A segment {sn[0]}{sn[1]} with its dashed perpendicular "
                           "bisector; dots on the bisector join both ends with "
                           "equal ticked segments."),
                       ("not to scale — only collinearity, the midpoint, the right "
                        "angle and the equal distances carry meaning"
                        if length is None else
                        f"the declared length {length:g}{' ' + unit if unit else ''} "
                        "applies to the whole segment"))

    if kind == "parallel_offset":
        sn = _letters(k, "segment", segment)
        if len(sn) != 2:
            raise TemplateError(f"{k}: 'parallel_offset' needs segment=(\"A\",\"B\")")
        distance = given("distance", distance)
        off = distance * unit_px
        if not 30.0 <= off <= 140.0:
            raise TemplateError(f"{k}: distance {distance:g} at {unit_px:g} px/unit draws "
                                f"{off:g} units — keep the offset 30–140")
        if any(c in sn for c in "UVST"):
            raise TemplateError(f"{k}: U/V/S/T are reserved for the offset lines")
        A = vc.polar((0.0, 0.0), draw_length / 2.0, line_deg + 180.0)
        B = vc.polar((0.0, 0.0), draw_length / 2.0, line_deg)
        anchors[sn[0]], anchors[sn[1]] = A, B
        elements.append(vc.line(A, B, id="line"))
        u = vc.unit(A, B)
        nrm = (-u[1], u[0])
        offs = {}
        for side, pair in ((1, ("U", "V")), (-1, ("S", "T"))):
            a_ = (A[0] + nrm[0] * off * side, A[1] + nrm[1] * off * side)
            b_ = (B[0] + nrm[0] * off * side, B[1] + nrm[1] * off * side)
            anchors[pair[0]], anchors[pair[1]] = a_, b_
            offs[side] = pair
            elements.append(vc.line(a_, b_, dashed=True, id=f"off{side:+d}"))
        if not isinstance(samples, dict) or not 1 <= len(samples) <= 3:
            raise TemplateError(f"{k}: samples must be 1–3 {{letter: (side, t)}}")
        feet_letters = unused(set(anchors) | set(samples), len(samples))
        for i, (lt, spec) in enumerate(samples.items()):
            letter_ok(lt, "sample names")
            if lt in anchors:
                raise TemplateError(f"{k}: sample {lt} collides with a named point")
            if not isinstance(spec, (list, tuple)) or len(spec) != 2:
                raise TemplateError(f"{k}: sample {lt} must be (side, t) — side ±1, "
                                    "t the fraction along the line")
            side, t = spec
            if isinstance(side, bool) or not isinstance(side, (int, float)) \
                    or side not in (-1, 1):
                raise TemplateError(f"{k}: sample {lt} side must be +1 or -1 "
                                    f"— got {side!r}")
            t = _num(k, f"sample {lt} t", t)
            if not 0.15 <= t <= 0.85:
                raise TemplateError(f"{k}: sample {lt} t={t:g} outside 0.15–0.85")
            a_, b_ = (anchors[offs[side][0]], anchors[offs[side][1]])
            p = anchors[lt] = vc.lerp(a_, b_, t)
            f_letter = feet_letters[i]
            f = anchors[f_letter] = vc.foot_of_perpendicular(p, A, B)
            elements.append(vc.line(p, f, id=f"ft{lt}"))
            elements += vc.right_angle_mask(f, p, A, size=12)
            elements += vc.right_angle_mark(f, p, A, r=12)
            elements += vc.tick_marks(p, f, count=1)
            elements.append(vc.dot(p, 3, id=f"dot{lt}"))
            elements.append(_point_label(p, lt))
            elements.append(_point_label(f, f_letter))
        for lt in sn:
            elements.append(_point_label(anchors[lt], lt))
        lt0, f0 = list(samples)[0], feet_letters[0]
        dim_label(vc.lerp(anchors[lt0], anchors[f0], 0.5), f"{lt0}{f0}",
                  f"{distance:g}{' ' + unit if unit else ''}")
        for i, lt in enumerate(samples):
            f_letter = feet_letters[i]
            add(f"on {f_letter} {sn[0]}{sn[1]}", "measured",
                "the computed perpendicular foot")
            add(f"right {sn[0]} {f_letter} {lt}", "measured",
                "the square marks the perpendicular distance")
        if len(samples) > 1:
            first = f"{list(samples)[0]}{feet_letters[0]}"
            for i, lt in enumerate(list(samples)[1:], 1):
                add(f"equal {first} {lt}{feet_letters[i]}", "measured",
                    "one-tick distances — every point of a parallel-offset locus "
                    "keeps the same distance")
        for side, pair in offs.items():
            add(f"parallel {sn[0]}{sn[1]} {pair[0]}{pair[1]}", "measured",
                "a computed offset — the locus line")
        add("parallel UV ST", "measured", "the two offset lines are parallel")
        add(f'describe "each dashed parallel is {distance:g}'
            f'{" " + unit if unit else ""} from {sn[0]}{sn[1]}; every sample joins '
            'the line by a perpendicular carrying one tick and a right-angle '
            'square"', "stem" if values == "stem" else "inferred",
            "locus convention")
        add(f"derive {distance:g} + {distance:g} = {distance * 2:g}", "inferred",
            "the two offsets flank the line at equal distances")
        if values == "figure":
            add('describe "the distance is figure content — the student reads it '
                'off the drawing"', "inferred", "read-off mode")
        add("none angleArc arrow shaded parallelMark", "inferred",
            "the parallels are proven by equal perpendicular distances, not "
            "parallel marks")
        return finish_(title or "The fixed-distance locus",
                       description or (
                           "A line with a dashed parallel on each side; dots on "
                           "each dashed line join the given line by equal "
                           "perpendicular distances."),
                       f"1 unit = {unit_px:g} canvas px; the drawn offset is "
                       f"{distance:g}{' ' + unit if unit else ''} from the line")


    letter_ok(vertex, "vertex")
    rd = _rays_map(k, arms, lo=2, hi=2)
    if vertex in rd:
        raise TemplateError(f"{k}: an arm cannot share the vertex letter {vertex}")
    (a1, d1), (a2, d2) = sorted(rd.items(), key=lambda kv: kv[1])
    whole = _angle_between(d1, d2)
    if not 20.0 <= whole <= 160.0:
        raise TemplateError(f"{k}: the arms make {whole:g}° — keep the given angle "
                            "between 20° and 160° so the bisector and feet read")
    if length is not None:
        length = given("length", length)
    if "W" in rd:
        raise TemplateError(f"{k}: W is reserved for the bisector end")
    V = (0.0, 0.0)
    anchors[vertex] = V
    anchors[a1] = vc.polar(V, draw_length, d1)
    anchors[a2] = vc.polar(V, draw_length, d2)
    elements.append(vc.line(V, anchors[a1], id=f"arm{a1}"))
    elements.append(vc.line(V, anchors[a2], id=f"arm{a2}"))
    delta = (d2 - d1) % 360.0
    mid = (d1 + (delta / 2.0 if delta <= 180.0 else (delta - 360.0) / 2.0)) % 360.0
    W = anchors["W"] = vc.polar(V, draw_length, mid)
    elements.append(vc.line(V, W, dashed=True, id="bis"))
    elements += vc.angle_label(V, anchors[a1], W, r=30, arcs=1)
    elements += vc.angle_label(V, W, anchors[a2], r=30, arcs=1)
    if not isinstance(samples, dict) or not 1 <= len(samples) <= 3:
        raise TemplateError(f"{k}: samples must be 1–3 {{letter: s}}")
    feet_letters = unused(set(anchors) | set(samples), 2 * len(samples))
    tc = _tick_classes()
    pair_counts = {}
    i = 0
    for lt, s in samples.items():
        letter_ok(lt, "sample names")
        if lt in anchors:
            raise TemplateError(f"{k}: sample {lt} collides with a named point")
        s = _num(k, f"sample {lt}", s)
        if not 0.25 <= s <= 0.9:
            raise TemplateError(f"{k}: sample {lt} fraction {s:g} outside 0.25–0.9")
        p = anchors[lt] = vc.lerp(V, W, s)

        f1 = vc.foot_of_perpendicular(p, V, anchors[a1])
        cnt = tc(vc.dist(p, f1))
        pair_counts[lt] = cnt
        for arm, f_letter in ((a1, feet_letters[i]), (a2, feet_letters[i + 1])):
            f = anchors[f_letter] = vc.foot_of_perpendicular(p, V, anchors[arm])
            elements.append(vc.line(p, f, id=f"ft{lt}{arm}"))
            elements += vc.right_angle_mark(f, p, V, r=11)
            elements += vc.tick_marks(p, f, count=cnt)

        elements.append(vc.dot(p, 3, id=f"dot{lt}"))
        lab = _point_label(p, lt)
        lab["_gap"] = 26
        elements.append(lab)
        i += 2
    for lt in (vertex, a1, a2):
        elements.append(_point_label(anchors[lt], lt))
    if values == "stem" and any(abs(whole / 2 - sn) <= 0.75
                                for sn in vt.stem_numbers(stem)):
        add(f"angle {a1} {vertex} W = {whole / 2:g}", "measured",
            "the bisector halves the given angle — stem-stated")
        add(f"angle W {vertex} {a2} = {whole / 2:g}", "measured",
            "equal arcs — the two halves match")
    else:
        add(f'describe "the dashed ray splits angle {a1}{vertex}{a2} into two '
            f'equal halves of {whole / 2:g}° each"', "inferred",
            "computed bisection — the arm directions carry the size")
    add(f'describe "the dashed ray bisects angle {a1}{vertex}{a2}"', "inferred",
        "locus convention — the dashed ray is the locus")
    i = 0
    for lt in samples:
        f1, f2 = feet_letters[i], feet_letters[i + 1]
        add(f"inside {lt} angle {a1} {vertex} {a2}", "measured",
            "the sample sits inside the given angle on the bisector")
        add(f"right {vertex} {f1} {lt}", "measured", "perpendicular foot on the first arm")
        add(f"right {vertex} {f2} {lt}", "measured", "perpendicular foot on the second arm")
        add(f"equal {lt}{f1} {lt}{f2}", "measured",
            f"{pair_counts[lt]}-tick distances — a point on the angle bisector "
            "is equidistant from the arms")
        i += 2
    add(f"derive {whole:g} / 2 = {whole / 2:g}", "inferred",
        "each half of the bisected angle")
    add("none parallelMark arrow shaded", "inferred",
        "rays, dashed bisector, right squares and ticks only")
    return finish_(title or "The angle-bisector locus",
                   description or (
                       f"An angle at {vertex} with its dashed bisector; dots on "
                       "the bisector join both arms by equal perpendicular "
                       "distances."),
                   "not to scale — the arm directions are canvas choices; the "
                   "bisection and equal distances are computed")





def build_polygon_angles(*, figure_id, stem, n,
                         show="interior", names=None, fan=None,
                         start_deg=-90.0, r_px=130.0,
                         labels=None, exterior_labels=None, ticks=True,
                         values="stem", ask=None, title=None, description=None,
                         medium="english"):
    """A REGULAR n-gon and the lesson's angle structures on it — nothing else.

    `n` is 3–8.  `show` is one of:

      • "interior"      — the polygon with one equal arc inside each vertex and
                          optional per-vertex `labels` (a glyph, or the interior
                          angle's number — which must equal (n−2)·180/n within
                          0.5° and be a stem number in stem mode).
      • "triangulation" — diagonals from `fan` (a vertex letter, default the
                          first) to every non-adjacent vertex: n−3 diagonals,
                          n−2 triangles; derives the interior-angle sum.
      • "centre"        — centre O joined to all n vertices: n triangles.
      • "exterior"      — every side produced past the next vertex in cyclic
                          order; `exterior_labels` (glyph or 360/n ±0.5°) mark
                          the outside arcs.

    `ticks` draws one tick per side (the regular equal-sides mark).  Irregular
    convex n-gons, symbolic-angle algebra and interior+exterior mixes stay
    outside the contract — those are residual hand-draw work.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "polygon_angles"
    n = _num(kind, "n", n)
    if not float(n).is_integer():
        raise TemplateError(f"{kind}: n must be a whole number of sides")
    n = int(n)
    if not 3 <= n <= 8:
        raise TemplateError(f"{kind}: n {n} outside 3–8 — larger n-gons crowd the "
                            "arcs past honest reading")
    if show not in ("interior", "triangulation", "centre", "exterior"):
        raise TemplateError(f"{kind}: show must be interior|triangulation|centre|exterior")
    values = _values_mode(kind, values)
    start_deg = _num(kind, "start_deg", start_deg)
    r_px = _num(kind, "r_px", r_px)
    if not 80.0 <= r_px <= 200.0:
        raise TemplateError(f"{kind}: r_px {r_px:g} outside 80–200 units")
    if names is None:
        names = list("ABCDEFGH")[:n]
    names = _letters(kind, "names", names)
    if len(names) != n:
        raise TemplateError(f"{kind}: names must supply exactly {n} letters")
    if values == "stem":
        vt.require_stem(stem, n=n)
    interior = (n - 2) * 180.0 / n
    exterior = 360.0 / n

    def glyph_check(lmap, want, what):
        out = {}
        if lmap is None:
            return out
        if not isinstance(lmap, dict):
            raise TemplateError(f"{kind}: {what} labels must be a dict")
        seen = set()
        for lt, g in lmap.items():
            if lt not in names:
                raise TemplateError(f"{kind}: {what} label names {lt!r}, not a vertex")
            if isinstance(g, bool) or not isinstance(g, (int, float, str)):
                raise TemplateError(f"{kind}: {what} label {g!r} is not a glyph")
            if isinstance(g, (int, float)):
                v = _num(kind, f"{what} label at {lt}", g)
            elif re.fullmatch(r"\d+(?:\.\d+)?°?", g):
                v = float(g.rstrip("°"))
            elif not re.fullmatch(r"[A-Za-z][A-Za-z0-9' ]{0,7}", g):
                raise TemplateError(f"{kind}: {what} label {g!r} — a numeric label "
                                    "is a plain unsigned decimal; signed, malformed "
                                    "or non-finite values refuse")
            else:
                v = None
            if v is not None:
                if abs(v - want) > 0.5:
                    raise TemplateError(f"{kind}: {what} label {v:g}° at {lt} misstates "
                                        f"{want:g}° — regular-{n} geometry is fixed")
                if values == "stem":
                    vt.require_stem(stem, **{f"{what} at {lt}": v})
                g = f"{v:g}°"

            seen.add(str(g))
            out[lt] = (str(g), v)
        return out

    if labels and show != "interior":
        raise TemplateError(f"{kind}: `labels` belongs to show='interior'")
    if exterior_labels and show != "exterior":
        raise TemplateError(f"{kind}: `exterior_labels` belongs to show='exterior'")
    lab_in = glyph_check(labels, interior, "interior")
    lab_ex = glyph_check(exterior_labels, exterior, "exterior")
    if fan is not None and fan not in names:
        raise TemplateError(f"{kind}: fan {fan!r} is not a vertex letter")

    vc.reset_ids()
    C = (0.0, 0.0)
    verts = {names[i]: vc.polar(C, r_px, start_deg + i * 360.0 / n) for i in range(n)}
    order = names
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []
    declared_segments: list[str] = []
    anchors = dict(verts)

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    for i in range(n):
        elements.append(vc.line(verts[order[i]], verts[order[(i + 1) % n]], id=f"s{i}"))
    if ticks:
        for i in range(n):
            elements += vc.tick_marks(verts[order[i]], verts[order[(i + 1) % n]],
                                      count=1)
    if show == "interior":
        add(f"derive {n} - 2 = {n - 2}", "inferred", "triangles an n-gon fans into")
        add(f"derive {n - 2} * 180 = {(n - 2) * 180}", "inferred",
            "the interior-angle sum of an n-gon")
        add(f"derive {(n - 2) * 180} / {n} = {interior:g}", "inferred",
            "one interior angle of the regular n-gon")
        seen_g = set()
        for i in range(n):
            v, prev_ = order[i], order[i - 1]
            next_ = order[(i + 1) % n]
            g = lab_in.get(v)
            elements += vc.angle_label(verts[v], verts[prev_], verts[next_],
                                       r=30, arcs=1, label=g[0] if g else None)
            if g and g[0] not in seen_g:
                seen_g.add(g[0])
                add(f'label "{g[0]}" names {prev_}{v}{next_}', "inferred",
                    "the arc's glyph")
            elif g:
                add(f'describe "{g[0]} also prints at vertex {v}"', "inferred",
                    "the same measure on an equal angle")
            if values == "stem":
                add(f"angle {prev_} {v} {next_} = {interior:g}", "measured",
                    "each interior angle of the regular n-gon — derive K3")
            elif i == 0:
                add(f'describe "each interior angle is {interior:g}°"', "inferred",
                    "computed from the regular n-gon")
        desc = ("A regular " + {3: "triangle", 4: "quadrilateral", 5: "pentagon",
                                6: "hexagon", 7: "heptagon", 8: "octagon"}[n] +
                "; one tick marks every side and one arc marks every angle.")
    elif show == "triangulation":
        fv = fan or order[0]
        f = order.index(fv)
        targets = [order[(f + j) % n] for j in range(2, n - 1)]
        for t in targets:
            elements.append(vc.line(verts[fv], verts[t], id=f"fan{t}"))
        for lt in order:
            elements.append(_point_label(verts[lt], lt))
        add(f'describe "diagonals from {fv} split the polygon into {n - 2} '
            'triangles"', "inferred", f"{n - 3} diagonals from one vertex")
        add(f"derive {n} - 3 = {n - 3}", "inferred", "diagonals from one vertex")
        add(f"derive {n} - 2 = {n - 2}", "inferred", "triangles the fan makes")
        add(f"derive {n - 2} * 180 = {(n - 2) * 180}", "inferred",
            "the interior-angle sum via the triangle fan")
        if values == "figure":
            add('describe "the fan is figure content — the student counts the '
                'triangles off the drawing"', "inferred", "read-off mode")
        desc = (f"A regular {n}-gon with the {n - 3} diagonals from vertex {fv} "
                f"drawn, splitting it into {n - 2} triangles.")
    elif show == "centre":
        if "O" in names:
            raise TemplateError(f"{kind}: O is reserved for the centre")
        anchors["O"] = C
        for lt in order:
            elements.append(vc.line(C, verts[lt], id=f"c{lt}"))
        elements.append(vc.dot(C, 3, id="dotO"))
        elements.append(_point_label(C, "O"))
        add(f"circle centre O through {' '.join(order[:3])}", "measured",
            "the regular polygon's vertices are one radius from its centre")
        for i in range(1, n):
            add(f"equal O{order[0]} O{order[i]}", "measured",
                "the spokes are equal radii")
        add(f'describe "the centre joins all {n} vertices, splitting the polygon '
            f'into {n} triangles meeting at O"', "inferred", "the lesson's figure")
        add(f"derive 360 / {n} = {exterior:g}", "inferred",
            "the centre angle of each triangle")
        desc = (f"A regular {n}-gon with its centre joined to all {n} vertices, "
                f"making {n} triangles that meet at the centre.")
    else:
        seen_ex = set()
        for i in range(n):
            prev_v, v, next_v = order[i], order[(i + 1) % n], order[(i + 2) % n]
            a_, b_ = verts[prev_v], verts[v]
            ext = (b_[0] + (b_[0] - a_[0]) * 0.45, b_[1] + (b_[1] - a_[1]) * 0.45)
            elements.append(vc.line(b_, ext, id=f"e{i}"))
            g = lab_ex.get(v)
            elements += vc.angle_label(b_, ext, verts[next_v], r=26, arcs=1,
                                       label=g[0] if g else None)
            if g and g[0] not in seen_ex:
                seen_ex.add(g[0])

                declared_segments.append(f"{prev_v}{v}")
                add(f'label "{g[0]}" names {prev_v}{v}', "inferred",
                    f"the exterior-angle glyph at {v}")
                add(f'describe "the glyph {g[0]} marks the exterior angle at '
                    f'{v} — {prev_v}{v} produced to {v}{next_v}"', "inferred",
                    "the exterior arc's direction")
            elif g:
                add(f'describe "{g[0]} also prints at vertex {v}"', "inferred",
                    "the same measure on an equal exterior angle")
        add(f"derive 360 / {n} = {exterior:g}", "inferred",
            "one exterior angle of the regular n-gon")
        add(f"derive {n} * {exterior:g} = 360", "inferred",
            "the exterior angles go once round — 360°")
        add(f"derive 180 - {interior:g} = {exterior:g}", "inferred",
            "each exterior angle supplements its interior")
        add('describe "every side is produced past its end and an arc marks the '
            'exterior angle at that vertex"', "inferred", "the lesson's figure")
        desc = (f"A regular {n}-gon with every side extended past the next "
                "vertex and an arc marking each exterior angle.")
    if show != "triangulation":
        for lt in order:
            elements.append(_point_label(verts[lt], lt))
    for lt in anchors:
        if any(el.get("value") == lt for el in elements if el["type"] == "text"):
            add(f'label "{lt}" names {lt}', "inferred", "a point letter")
    if ticks:
        for i in range(1, n):
            add(f"equal {order[0]}{order[1]} {order[i]}{order[(i + 1) % n]}",
                "measured", "one tick per side — the regular equal sides")
    add("none parallelMark dashed arrow shaded"
        + ("" if ticks else " tickMark"), "inferred",
        "polygon outline, " + ("diagonals" if show == "triangulation" else
                               "spokes" if show == "centre" else
                               "produced sides" if show == "exterior" else
                               "interior arcs") + (" and ticks" if ticks else ""))
    title_d = title or {
        "interior": f"A regular {n}-gon with equal angles",
        "triangulation": f"Triangulating a regular {n}-gon from one vertex",
        "centre": f"A regular {n}-gon split at its centre",
        "exterior": f"Exterior angles of a regular {n}-gon"}[show]
    budget = len(elements) if len(elements) > 32 else None
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                     anchors=anchors, points=list(anchors),
                     segments=declared_segments,
                     claims=claims, ask=ask, title=title_d,
                     description=description or desc,
                     scale="drawn on a true regular polygon; the equal marks and "
                          "derived angles carry the meaning",
                     budget=budget, medium=medium)
