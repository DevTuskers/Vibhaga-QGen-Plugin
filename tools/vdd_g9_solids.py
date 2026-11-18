"""vdd_g9_solids.py — bounded G9 solid/net families the catalogue cannot print.

Three builders, each confirmed against the corpus (see
wt/g9-readiness/solids/integration.md for the exact coverage and residuals):

  • open_cuboid_net     — G9 L09 p.4 activity: a cut-and-fold net for an OPEN
                          cuboid (base + four walls, no top), all five faces at
                          one true unit scale, fold edges dashed.
                          (09-Liquid-Measurements.md:391-476)
  • cuboid_water        — G9 L09 p.3: a rectangular tank holding water to a
                          stated depth; the water surface is COMPUTED at
                          depth/height along the true front edges — the same
                          oblique foreshortening as build_cuboid applies to
                          depth edges only. (09-Liquid-Measurements.md:307-337)
  • regular_polyhedron  — G9 L17: the tetrahedron and the octahedron behind the
                          Euler-relation formula, drawn by a bounded
                          orthographic rotation of exact 3-D coordinates (no
                          arbitrary-solid engine; other shapes refuse).
                          (17-Formulae.md:77-87, 783-789)

This module is NOT registered in vdd_templates — the lead owns that file.
`vdd_templates` is imported lazily inside each builder so importing this module
stays side-effect-free; `vdd_cookbook` (pure geometry) is imported at top.
"""
from __future__ import annotations

import math

import vdd_cookbook as vc

WATER_FILL = "#dbeafe"
WATER_SIDE = "#bfdbfe"
WATER_EDGE = "#1d4ed8"


def _num(kind: str, name: str, v):
    """The numeric gate EVERY dimensional input passes BEFORE any arithmetic or
    conversion — bools, strings, non-numbers and non-finite values refuse."""
    from vdd_templates import TemplateError
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TemplateError(f"{kind}: {name} {v!r} must be a finite number, not bool/string")
    try:
        out = float(v)
    except (OverflowError, ValueError):
        raise TemplateError(f"{kind}: {name} {v!r} is outside the finite range") from None
    if not math.isfinite(out) or not 0 < out <= 10000:
        raise TemplateError(f"{kind}: {name} {v!r} must be a finite number in (0, 10000]")
    return out


MEDIA = ("english", "sinhala")


def _common(kind: str, stem, values, unit, scale_px, medium,
            ask=None, title=None, description=None):
    from vdd_templates import TemplateError
    if not isinstance(stem, str):
        raise TemplateError(f"{kind}: stem must be text, not {type(stem).__name__}")
    if values not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure'")
    if not isinstance(unit, str) or not unit.isascii() or not unit.isalpha() or len(unit) > 5:
        raise TemplateError(f"{kind}: unit must be 1-5 English letters (never Sinhala)")
    if isinstance(scale_px, bool) or not isinstance(scale_px, (int, float)) \
            or not 0.5 <= float(scale_px) <= 3:
        raise TemplateError(f"{kind}: scale_px must be 0.5-3")
    if not isinstance(medium, str) or medium.strip().lower() not in MEDIA:
        raise TemplateError(f"{kind}: medium must be one of {MEDIA}")
    if ask is not None:
        try:
            pairs = [[ref, text] for ref, text in ask]
        except (TypeError, ValueError):
            raise TemplateError(f"{kind}: ask must be (ref, text) pairs") from None
        if not all(isinstance(ref, str) and isinstance(text, str) for ref, text in pairs):
            raise TemplateError(f"{kind}: ask entries must be (ref, text) string pairs")
    for name, v in (("title", title), ("description", description)):
        if v is not None and not isinstance(v, str):
            raise TemplateError(f"{kind}: {name} must be text or None")
    return float(scale_px)


def _dim_labels(kind: str, dims, segments_for, anchors, values, unit, claims, elements):
    """Floating `<v> <unit>` labels, one per distinct glyph — equal dimensions
    share a glyph, so a second occurrence becomes an honest `describe` instead of
    a duplicate label binding (audit rule: one label claim per printed glyph)."""
    import vdd_templates as vt
    seen: dict[str, str] = {}
    emitted: dict[str, tuple[int, str]] = {}
    for i, (name, value) in enumerate(dims.items()):
        glyph = f"{value:g} {unit}"
        a, b = segments_for[name]
        target = f"{a}{b}"
        if glyph in seen:
            claims.append((f'describe "true dimension {target} equals {seen[glyph]}, '
                           f'already labelled {glyph}"', "inferred",
                           "equal physical dimensions, not a claim about drawn lengths"))
            continue
        seen[glyph] = target
        elements.append(vt._float_label(f"dim{i}", glyph,
                                        vc.lerp(anchors[a], anchors[b], 0.5), gap=16))
        claims.append((f'label "{glyph}" names {target}',
                       "stem" if values == "stem" else "inferred",
                       f"the stated {name} dimension"))
        emitted[name] = (len(claims), target)
    return emitted





def build_open_cuboid_net(*, figure_id, stem, length, width, height, unit="cm",
                          values="stem", scale_px=1.0, ask=None, title=None,
                          description=None, medium="english"):
    """The L09 activity net: a length x width base with the four walls folded
    out — front/back walls length x height, left/right walls width x height —
    and NO top face. All faces share one true scale; the four fold edges are
    dashed. Refuses degenerate proportions (thinnest face under 10% of the
    largest dimension) — a wall that thin cannot read as a rectangle."""
    import vdd_templates as vt
    kind = "open_cuboid_net"
    k_scale = _common(kind, stem, values, unit, scale_px, medium,
                      ask=ask, title=title, description=description)
    L = _num(kind, "length", length)
    W = _num(kind, "width", width)
    H = _num(kind, "height", height)
    if values == "stem":
        vt.require_stem(stem, length=L, width=W, height=H)
    if min(L, W, H) / max(L, W, H) < 0.1:
        raise vt.TemplateError(
            f"{kind}: the thinnest dimension is under 10% of the largest — "
            "a wall would render as a sliver, not a readable rectangle")

    k = k_scale * min(320.0 / (L + 2 * H), 220.0 / (W + 2 * H))
    if min(L, W, H) * k < 14:
        raise vt.TemplateError(f"{kind}: the smallest face renders under 14 units "
                               "— adjust scale_px or the proportions")
    l, w, h = L * k, W * k, H * k
    vc.reset_ids()

    P = {"A": (0.0, 0.0), "B": (l, 0.0), "C": (l, w), "D": (0.0, w),
         "E": (0.0, -h), "F": (l, -h), "G": (0.0, w + h), "H": (l, w + h),
         "I": (-h, 0.0), "J": (-h, w), "K": (l + h, 0.0), "M": (l + h, w)}
    elements = []

    outer = (("E", "F"), ("F", "B"), ("E", "A"),
             ("G", "H"), ("D", "G"), ("C", "H"),
             ("I", "J"), ("A", "I"), ("D", "J"),
             ("K", "M"), ("B", "K"), ("C", "M"))
    for a_, b_ in outer:
        elements.append(vc.line(P[a_], P[b_], id=f"{a_}{b_}"))
    for a_, b_ in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")):
        elements.append(vc.line(P[a_], P[b_], id=f"fold{a_}{b_}", dashed=True))
    claims = []
    claims.append(('describe "an open-cuboid net: a rectangular base with four '
                   'rectangular walls folded out on its edges and no top face; '
                   'the four shared edges are the dashed fold lines"',
                   "inferred", "five faces at one true scale"))
    if values == "figure":
        claims.append(('describe "the printed dimensions are figure content — '
                       'the student reads them from the figure"', "inferred",
                       "read-the-figure mode (values=figure)"))
    _dim_labels(kind, {"length": L, "width": W, "height": H},
                {"length": ("D", "C"), "width": ("B", "C"), "height": ("E", "A")},
                P, values, unit, claims, elements)
    for a_, b_ in (("E", "F"), ("G", "H")):
        claims.append((f"equal {a_}{b_} DC", "inferred",
                       "each wall's outer edge equals the base edge it folds from"))
    claims.append(("equal EF GH", "inferred", "opposite walls are congruent"))
    claims.append(("equal IJ KM", "inferred", "opposite walls are congruent"))
    for b_ in ("BF", "DG", "CH"):
        claims.append((f"equal AE {b_}", "inferred", "every wall has the same height"))
    for x, q, y in (("D", "A", "B"), ("A", "B", "C"), ("B", "C", "D"), ("C", "D", "A")):
        claims.append((f"right {x} {q} {y}", "inferred", "the base is a true rectangle"))
    claims.append((f"derive {L:g} * {W:g} = {vt._num_exact(L * W)}", "inferred",
                   "the base face's area from the stem's own numbers"))
    claims.append(("none tickMark parallelMark angleMark angleArc arrow shaded", "inferred",
                   "five face outlines and dashed fold lines only"))
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                     anchors=P, points=list(P),
                     segments=["AB", "BC", "CD", "DA", "EF", "GH", "IJ", "KM",
                               "AE", "BF", "DG", "CH", "AI", "BK", "DJ", "CM"],
                     claims=claims, ask=ask,
                     title=title or "Net of an open cuboid",
                     description=description or (
                         "The net of an open cuboid: a rectangular base with four "
                         "rectangular walls folded out on its edges, no top face; "
                         "fold edges are dashed."),
                     scale="all five faces at one true unit scale — measure any "
                           "edge; dashed lines are folds, not cuts", medium=medium)





def build_cuboid_water(*, figure_id, stem, length, width, height, depth,
                       unit="cm", values="stem", scale_px=1.0,
                       depth_angle=35.0, depth_scale=0.5,
                       ask=None, title=None, description=None, medium="english"):
    """The L09 partially filled tank: a cuboid length x width x height with
    water occupying the bottom `depth`. The water surface is COMPUTED — a
    horizontal line at fraction depth/height up the true front edges — plus its
    oblique projection across the side faces. Front face is true shape; depth
    (width) edges run `depth_scale`x at `depth_angle` degrees, exactly the
    build_cuboid convention, and that foreshortening is declared `contested`
    on the width label. `depth` must lie strictly inside (0, height): a full or
    empty tank is a cuboid, not this figure."""
    import vdd_templates as vt
    kind = "cuboid_water"
    k_scale = _common(kind, stem, values, unit, scale_px, medium,
                      ask=ask, title=title, description=description)
    L = _num(kind, "length", length)
    W = _num(kind, "width", width)
    H = _num(kind, "height", height)
    D = _num(kind, "depth", depth)
    for _name, _v in (("depth_angle", depth_angle), ("depth_scale", depth_scale)):
        if isinstance(_v, bool) or not isinstance(_v, (int, float)) or not math.isfinite(_v):
            raise vt.TemplateError(f"{kind}: {_name} {_v!r} must be a finite number")
    if not (0 < depth_angle < 90):
        raise vt.TemplateError(f"{kind}: depth_angle {depth_angle} must be in (0, 90)")
    if not (0 < depth_scale <= 1):
        raise vt.TemplateError(f"{kind}: depth_scale {depth_scale} must be in (0, 1]")
    if D >= H:
        raise vt.TemplateError(f"{kind}: depth {D:g} must be strictly below height "
                               f"{H:g} — a full tank is a plain cuboid")
    if min(L, W, H) / max(L, W, H) < 0.08:
        raise vt.TemplateError(f"{kind}: proportions too thin for readable geometry")
    if D / H < 0.05:
        raise vt.TemplateError(f"{kind}: depth {D:g} is under 5% of height {H:g} — "
                               "the water film cannot read as a region")
    if values == "stem":
        vt.require_stem(stem, length=L, width=W, height=H, depth=D)
    u = k_scale * min(150.0 / L, 62.0 / H, 120.0 / (depth_scale * W))
    lpx, hpx = L * u, H * u
    dx, dy = (depth_scale * W * u * math.cos(math.radians(-depth_angle)),
              depth_scale * W * u * math.sin(math.radians(-depth_angle)))
    y_s = hpx * (1 - D / H)
    A, B, C, Dd = (0.0, 0.0), (lpx, 0.0), (lpx, hpx), (0.0, hpx)
    E = (A[0] + dx, A[1] + dy); F = (B[0] + dx, B[1] + dy)
    G = (C[0] + dx, C[1] + dy); Hh = (Dd[0] + dx, Dd[1] + dy)
    Pp = (0.0, y_s); Q = (lpx, y_s)
    R = (Q[0] + dx, Q[1] + dy); S = (Pp[0] + dx, Pp[1] + dy)
    P = {"A": A, "B": B, "C": C, "D": Dd, "E": E, "F": F, "G": G, "H": Hh,
         "P": Pp, "Q": Q, "R": R, "S": S}
    hidden = {"DH", "GH", "EH"}
    vc.reset_ids()
    elements = [

        vc.polygon([Pp, Q, C, Dd], fill=WATER_FILL, stroke_width=0, id="waterFront"),
        vc.polygon([Q, C, G, R], fill=WATER_SIDE, stroke_width=0, id="waterSide"),
        vc.polygon([Pp, Q, R, S], fill=WATER_SIDE, stroke_width=0, id="waterTop"),
    ]
    for seg, a_, b_ in (("AB", "A", "B"), ("BC", "B", "C"), ("CD", "C", "D"),
                        ("DA", "D", "A"), ("AE", "A", "E"), ("BF", "B", "F"),
                        ("CG", "C", "G"), ("DH", "D", "H"), ("EF", "E", "F"),
                        ("FG", "F", "G"), ("GH", "G", "H"), ("EH", "E", "H")):
        elements.append(vc.line(P[a_], P[b_], id=seg, dashed=(seg in hidden)))
    elements += [
        dict(vc.line(Pp, Q, id="PQ", width=3), stroke={"width": 3, "color": WATER_EDGE}),
        dict(vc.line(Q, R, id="QR", width=2), stroke={"width": 2, "color": WATER_EDGE}),
        dict(vc.line(R, S, id="RS", width=2),
             stroke={"width": 2, "color": WATER_EDGE, "style": "dashed"}),
        dict(vc.line(S, Pp, id="SP", width=2),
             stroke={"width": 2, "color": WATER_EDGE, "style": "dashed"}),
    ]
    claims = []
    if values == "figure":
        claims.append(('describe "the printed dimensions are figure content — '
                       'the student reads them from the figure"', "inferred",
                       "read-the-figure mode (values=figure)"))

    dim_claims = _dim_labels(kind, {"length": L, "height": H, "width": W, "depth": D},
                             {"length": ("D", "C"), "height": ("F", "G"),
                              "width": ("C", "G"), "depth": ("D", "P")},
                             P, values, unit, claims, elements)
    dr = len(claims) + 1
    claims.append((f"derive {D:g} / {H:g} = {vt._num_exact(D / H)}", "stem"
                   if values == "stem" else "inferred",
                   "the water's share of the tank's height"))
    if values == "stem":
        claims.append((f"ratio len CQ / len CB = {D / H:g}", "stem",
                       f"the surface line sits at the computed fraction of the true "
                       f"front edge, per derive K{dr}"))
    else:
        claims.append(('describe "the surface line sits at the computed fraction '
                       'depth/height of the true front edge"', "inferred",
                       "computed from the figure's own printed dimensions"))
    claims += [
        ('describe "a cuboid tank in oblique projection, holding water that fills '
         'the shaded lower region; the bold horizontal line is the water surface '
         'on the front face and the surface continues across the side faces as a '
         'parallelogram; hidden tank edges and the two far surface edges are '
         'dashed"', "inferred", "the water volume is a smaller cuboid"),
        ('describe "the water surface is horizontal in the solid — it is drawn as '
         'one level line on the true front face, not tilted"', "inferred",
         "a free liquid surface"),
    ]
    for seg in sorted(hidden):
        claims.append((f"paint {seg} dashed", "inferred", "a hidden edge drawn broken"))
    claims.append(("none tickMark parallelMark angleMark angleArc arrow", "inferred",
                   "tank edges, shaded water and the surface outline only"))

    contested = []
    if "width" in dim_claims:
        k_i, _t = dim_claims["width"]
        contested.append((f"K{k_i}",
                          f"{W:g} {unit} prints the stem's true width on depth "
                          "edge CG while the oblique convention foreshortens "
                          f"depth edges ({depth_scale:g}x at {depth_angle:g} "
                          "deg); the water depth DP is on the true front "
                          "face and is NOT foreshortened"))
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                     anchors=P, points=list(P),
                     segments=["AB", "BC", "CD", "DA", "AE", "BF", "CG", "DH",
                               "EF", "FG", "GH", "EH", "PQ", "QR", "RS", "SP",
                               "CQ", "DP"],
                     claims=claims, ask=ask, contested=contested,
                     title=title or "A rectangular tank partly filled with water",
                     description=description or (
                         f"A cuboid tank {L:g} by {W:g} by {H:g} {unit} in oblique "
                         f"projection, shaded water filling it to a depth of "
                         f"{D:g} {unit}; the bold horizontal line marks the water "
                         "surface."),
                     scale="front face true (length, height and water depth as "
                           f"stated); width edges foreshortened {depth_scale:g}x "
                           f"at {depth_angle:g} degrees — do not measure depth edges",
                     medium=medium)





_POLY_SHAPES = ("tetrahedron", "octahedron")
_POLY_YAW = math.radians(-14.0)
_POLY_PITCH = math.radians(28.0)
_POLY_FACES = {"tetrahedron": (4, 6, 4), "octahedron": (6, 12, 8)}


def _poly_project(p, yaw=_POLY_YAW, pitch=_POLY_PITCH):
    """One fixed orthographic view: rotate about y by `yaw`, about x by `pitch`,
    drop depth. Returns (screen_x, screen_y_down, depth)."""
    x, y, z = p
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cp, sp = math.cos(pitch), math.sin(pitch)
    y, z = y * cp - z * sp, y * sp + z * cp
    return (x, -y, z)


def _poly_vertices(shape):
    """Exact coordinates, edge length 1 — tetrahedron on its base (apex up, one
    base vertex toward the viewer); octahedron as two square pyramids base to
    base (equatorial half-diagonal = edge / sqrt(2) so every edge is 1)."""
    s3 = math.sqrt(3.0)
    if shape == "tetrahedron":
        return {"A": (0.0, math.sqrt(2.0 / 3.0), s3 / 6.0),
                "B": (-0.5, 0.0, 0.0), "C": (0.5, 0.0, 0.0),
                "D": (0.0, 0.0, s3 / 2.0)}
    s = 1.0 / math.sqrt(2.0)
    return {"T": (0.0, s, 0.0), "B": (0.0, -s, 0.0),
            "P": (s, 0.0, 0.0), "Q": (0.0, 0.0, s),
            "R": (-s, 0.0, 0.0), "S": (0.0, 0.0, -s)}


def _poly_face_list(shape):
    """Faces as vertex triples (winding irrelevant — normals are oriented outward
    at use). The octahedron's bottom faces list the equator pair reversed so the
    shared-edge adjacency still resolves two faces per edge."""
    if shape == "tetrahedron":
        return [("A", "B", "C"), ("A", "C", "D"), ("A", "D", "B"), ("B", "C", "D")]
    return [("T", "P", "Q"), ("T", "Q", "R"), ("T", "R", "S"), ("T", "S", "P"),
            ("B", "Q", "P"), ("B", "R", "Q"), ("B", "S", "R"), ("B", "P", "S")]


def _poly_hidden_edges(shape, edges):
    """Genuinely hidden edges, COMPUTED — not assumed: each face's outward normal
    (oriented away from the solid's centroid) is run through the SAME rotation
    the vertices get; a face is back-facing when its rotated normal points away
    from the viewer (z' < 0), and an edge is hidden iff every face sharing it is
    back-facing. Under this view the tetrahedron's back base edge BC is hidden
    (matching the corpus figure); the octahedron hides TS, BS, RS and SP — the
    two far equatorial edges plus the slant edges bounding the rear faces."""
    verts = _poly_vertices(shape)
    faces = _poly_face_list(shape)
    centre = tuple(sum(p[i] for p in verts.values()) / len(verts) for i in range(3))
    back = set()
    for fi, face in enumerate(faces):
        p0, p1, p2 = (verts[n] for n in face)
        u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        v = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        n = (u[1] * v[2] - u[2] * v[1],
             u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0])
        fc = tuple((p0[i] + p1[i] + p2[i]) / 3 for i in range(3))
        if sum(n[i] * (fc[i] - centre[i]) for i in range(3)) < 0:
            n = (-n[0], -n[1], -n[2])
        if _poly_project(n)[2] < -1e-9:
            back.add(fi)
    hidden = set()
    for a_, b_ in edges:
        adjacent = [fi for fi, f in enumerate(faces) if a_ in f and b_ in f]
        if adjacent and all(fi in back for fi in adjacent):
            hidden.add(f"{a_}{b_}")
    return hidden


def build_regular_polyhedron(*, figure_id, stem, shape, edge=None, unit="cm",
                             values="stem", scale_px=1.0, ask=None, title=None,
                             description=None, medium="english"):
    """A regular tetrahedron or octahedron — the two L17 solids the catalogue
    lacks. Exact 3-D coordinates run through ONE fixed orthographic rotation;
    the genuinely hidden edges are drawn dashed and every edge in the solid is
    equal, which the claims state as solid facts (projected lengths differ —
    do NOT claim drawn `equal`). `edge` is optional: a number prints one edge
    label (declared contested against the projection); omit it for the
    unlabelled source-style figure. Any other shape refuses — this is a bounded
    family, not a generic polyhedron engine."""
    import vdd_templates as vt
    kind = "regular_polyhedron"
    k_scale = _common(kind, stem, values, unit, scale_px, medium,
                      ask=ask, title=title, description=description)
    if shape not in _POLY_SHAPES:
        raise vt.TemplateError(f"{kind}: shape must be one of {_POLY_SHAPES} — "
                               "other polyhedra are not built")
    if edge is not None:
        edge = _num(kind, "edge", edge)
        if values == "stem":
            vt.require_stem(stem, edge=edge)
    verts = _poly_vertices(shape)
    proj = {n: _poly_project(p) for n, p in verts.items()}
    k = 150.0 * k_scale
    P = {n: (x * k, y * k) for n, (x, y, _z) in proj.items()}
    if shape == "tetrahedron":
        edges = [("A", "B"), ("A", "C"), ("A", "D"),
                 ("B", "D"), ("C", "D"), ("B", "C")]
    else:
        edges = [("T", "P"), ("T", "Q"), ("T", "R"), ("T", "S"),
                 ("B", "P"), ("B", "Q"), ("B", "R"), ("B", "S"),
                 ("P", "Q"), ("Q", "R"), ("R", "S"), ("S", "P")]

    hidden_set = _poly_hidden_edges(shape, edges)
    vc.reset_ids()
    elements = []
    hidden = []
    for a_, b_ in edges:
        is_hidden = f"{a_}{b_}" in hidden_set
        elements.append(vc.line(P[a_], P[b_], id=f"{a_}{b_}", dashed=is_hidden))
        if is_hidden:
            hidden.append(f"{a_}{b_}")
    claims = []
    v_, e_, f_ = _POLY_FACES[shape]
    claims.append((f'describe "a regular {shape} drawn in a fixed orthographic '
                   f'projection: {v_} vertices, {e_} edges and {f_} faces; every '
                   'edge is equal in the solid"', "inferred",
                   "the solid's own combinatorics"))
    if values == "figure" and edge is not None:
        claims.append(('describe "the printed dimension is figure content — the '
                       'student reads it from the figure"', "inferred",
                       "read-the-figure mode (values=figure)"))
    contested = []
    if edge is not None:

        a_, b_ = max(edges, key=lambda e: vc.dist(P[e[0]], P[e[1]]))
        glyph = f"{edge:g} {unit}"
        elements.append(vt._float_label("dim0", glyph,
                                        vc.lerp(P[a_], P[b_], 0.5), gap=16))
        claims.append((f'label "{glyph}" names {a_}{b_}',
                       "stem" if values == "stem" else "inferred",
                       "the stated edge; every edge of a regular solid is equal"))
        contested.append((f"K{len(claims)}",
                          f"{glyph} prints the stem's true edge on {a_}{b_} while "
                          "the orthographic projection foreshortens every edge "
                          "differently — do not measure projected lengths"))
        claims.append((f"derive 2 * {edge:g} = {vt._num_exact(2 * edge)}", "inferred",
                       "two edges of the solid"))
    else:
        claims.append(("derive 1 * 1 = 1", "inferred", "unit scale"))
    for seg in hidden:
        claims.append((f"paint {seg} dashed", "inferred",
                       "an edge hidden behind the front faces"))
    claims.append(("none tickMark parallelMark angleMark angleArc arrow shaded", "inferred",
                   "solid and dashed edge strokes only"))
    nice = shape.replace("_", " ")
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                     anchors=P, points=list(P),
                     segments=[f"{a}{b}" for a, b in edges],
                     claims=claims, ask=ask, contested=contested,
                     title=title or f"A regular {nice}",
                     description=description or (
                         f"A regular {nice} in orthographic projection: {e_} edges, "
                         f"the {'hidden edge is' if len(hidden) == 1 else 'hidden edges are'} "
                         "dashed."),
                     scale="a fixed orthographic projection of the exact solid — "
                           "projected edge lengths are foreshortened, not to be measured",
                     medium=medium)
