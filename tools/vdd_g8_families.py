"""vdd_g8_families.py — three bounded G8 gap families.

Covers the confirmed residuals of `wt/g678-readiness/inventory-g8.md`
(confirmed-gaps rows 1, 2 and 7):

  • `build_stem_leaf` — lesson 27 stem-and-leaf plots (~20 source blocks): a
    two-column ruled plot, stem digits left of a vertical rule, leaf digits
    right, plus a `s | l means v` key line.  The caller supplies raw data;
    the builder sorts and groups it, so a drawn row can never disagree with
    the numbers.  Leaves are single digits by construction — integer data
    only, rows ≤ 8, ≤ 8 leaves per row, ≤ 24 leaves total.  Decimal-point
    keys, back-to-back plots and boxed-table variants stay OUT.

  • `build_tessellation` — lesson 30 periodic tiling patches (~40 source
    blocks, the largest single G8 gap): ONE regular-tile family per call —
    `tile="square"|"triangle"|"hexagon"`, a `rows`×`cols` patch of the
    lattice (edges deduplicated, so every seam is one stroke), an optional
    `shade=[cells]` subset and an optional `vertex` letter marking the most
    interior lattice vertex for vertex-figure (angles-round-a-point) work.
    Semi-regular vertex-configs (4.6.12, 8.8.4, …), strip patterns and
    Escher-style cut-and-translate tiles stay OUT — say so in the plan,
    do not stretch this builder.

  • `build_bearing_map` — lesson 24 two-centre bearing triangulation (~8
    source blocks): two observation points on an abstract map frame, a north
    arrow at each, and bearing rays to a single target.  The caller states
    the bearings; the builder COMPUTES the target as the ray intersection —
    a ray that misses is a refusal, never a fudged placement.  Parallel or
    coincident rays, rays that diverge, and centre frames that collapse to
    a point refuse.

Every number that carries meaning is either stem-checked (`values="stem"`
where the mode exists; `build_bearing_map` is stem-only — the bearings are
always givens, never read off), declared figure content, or computed here.
Drawn arcs, `right`/`parallel`/`equal` claims and the computed intersection
are re-validated against the geometry; anything the ink cannot honestly
carry is a TemplateError.

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
_NEIGHBOUR_POOL = "ABCDEFGHIJKLMNPQRUWXYZ"  # V, T, O, S kept for named points


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


def _whole(kind: str, name: str, v) -> int:
    from vdd_templates import TemplateError
    fv = _num(kind, name, v)
    if fv != int(fv):
        raise TemplateError(f"{kind}: {name} {v!r} must be a whole number")
    return int(fv)


def _one_letter(kind: str, name: str, v) -> str:
    from vdd_templates import TemplateError
    if not isinstance(v, str) or not _LETTER.fullmatch(v):
        raise TemplateError(f"{kind}: {name} must be one capital letter — got {v!r}")
    return v


def _values_mode(kind: str, values) -> str:
    from vdd_templates import TemplateError
    v = str(values).strip().lower()
    if v not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure' — got {values!r}")
    return v


def _point_label(anchor, letter: str):
    """A floating point letter — finish() seats it clear of the ink."""
    return {"type": "text", "id": f"t{letter}", "at": [0, 0], "value": letter,
            "align": "middle", "baseline": "middle", "_near": list(anchor)}


def _dot(at, eid: str, r: float = 4.0):
    return {"type": "circle", "id": eid, "center": list(at), "r": r,
            "fill": {"color": "#000"}}


class _Labels:
    """One `label` claim per distinct drawn glyph; repeats are honestly
    described — exactly one claim may bind a glyph."""

    def __init__(self, add):
        self.add = add
        self.seen: dict[str, str] = {}

    def __call__(self, glyph: str, target: str, note: str):
        if glyph in self.seen:
            self.add(f'describe "the glyph {glyph} prints more than once"',
                     "inferred", f"first bound to {self.seen[glyph]}; also on {target}")
        else:
            self.seen[glyph] = target
            self.add(f'label "{glyph}" names {target}', "inferred", note)


def _seat_bearing_label(centre, bearing: float, text: str, elements: list, mark: dict):
    """A seat for the degree glyph near a bearing arc: sweep directions about
    the wedge middle and the ray's outside shoulder, keeping the label box
    ≥12 units from every stroke — then take the seat NEAREST the angle-mark's
    own arc, so the numeral sits by the mark it reads (the visual target rule
    measures glyph-to-ink distance; roominess pushed it far past the allowed
    1.5·fontSize).  Returns (x, y) or None."""
    import vdd_templates as vt
    strokes = vt.stroke_segments(elements)
    arc = vt.stroke_segments([mark])                # the numeral's own ink
    hw, hh = 5.2 * len(text) + 3.0, 12.0
    mid = math.radians(bearing / 2.0 - 90.0)        # wedge middle (canvas deg)
    ray = math.radians(bearing - 90.0)              # the ray's direction
    side = 1.0 if bearing <= 180.0 else -1.0        # outside of the wedge
    cand = [mid]
    for off in (30.0, 45.0, 60.0, 80.0, 100.0):
        cand += [ray + side * math.radians(off)]
        if bearing <= 180.0:
            cand.append(ray - side * math.radians(off))
    best = None
    for d in cand:
        for rr in (48.0, 58.0, 70.0, 84.0):
            cx = centre[0] + rr * math.cos(d)
            cy = centre[1] + rr * math.sin(d)
            box = (cx - hw, cy - hh, cx + hw, cy + hh)
            gap = min(vt._seg_rect_dist(a, b, box) - w / 2
                      for a, b, w in strokes)
            if gap < 12.0:
                continue
            arc_d = min(vt._seg_rect_dist(a, b, box)
                        for a, b, _w in arc)
            score = (arc_d, rr)                  # nearest the arc, then near the vertex
            if best is None or score < best[0]:
                best = (score, (cx, cy))
    return best[1] if best else None


# ────────────────────────────────────────────────────────────────────────────────
# 1. Stem-and-leaf plot
# ────────────────────────────────────────────────────────────────────────────────
def build_stem_leaf(*, figure_id, stem, data, key=None,
                    values="stem", ordered=True,
                    ask=None, title=None, description=None,
                    medium="english"):
    """A ruled two-column stem-and-leaf table with a key line — each row's
    digits sit between horizontal rules, so every leaf reads off a stroke.

    `data` is the raw leaf list — 3–24 values, each a non-negative whole
    number < 1000.  The builder groups by stem (`v // 10`) and orders the
    rows; leaves are single digits `v % 10` by construction.  At most 8
    distinct stems (rows) and 8 leaves per row — wider real data crowds past
    an honest figure width and refuses.

    `ordered=True` (default) sorts each row's leaves — the standard "ordered
    stem-and-leaf".  `ordered=False` draws the leaves in data order and
    declares that; it REFUSES when the data already sorts every row — an
    "unordered" flag on ordered ink would lie.  `key=(stem_digit, leaf_digit)`
    draws `s | l means v` with `v = 10·s + l` computed here; it defaults to
    the first datum, so the key always restates a real row.  In
    `values="stem"` mode every data value and the key's value must be a stem
    number; `values="figure"` declares the digits figure content.

    Decimal keys, back-to-back (two-sided) plots and boxed-table variants
    stay outside this contract.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "stem_leaf"
    values = _values_mode(kind, values)
    if not isinstance(data, (list, tuple)):
        raise TemplateError(f"{kind}: data must be a list of 3–24 values")
    if not 3 <= len(data) <= 24:
        raise TemplateError(f"{kind}: data takes 3–24 values — got {len(data)}")
    vals = [_whole(kind, f"data[{i}]", v) for i, v in enumerate(data)]
    for i, v in enumerate(vals):
        if not 0 <= v <= 999:
            raise TemplateError(f"{kind}: data[{i}] = {v} — keep values in 0–999 "
                                "(leaves are single digits, stems 1–2 digits)")
    if values == "stem":
        for v in sorted(set(vals)):
            vt.require_stem(stem, **{f"data value {v}": float(v)})

    rows: dict[int, list[int]] = {}
    for v in vals:
        rows.setdefault(v // 10, []).append(v % 10)
    if len(rows) > 8:
        raise TemplateError(f"{kind}: {len(rows)} distinct stems — at most 8 rows")
    for s, leaves in rows.items():
        if len(leaves) > 8:
            raise TemplateError(f"{kind}: stem {s} carries {len(leaves)} leaves — "
                                "more than 8 cannot read honestly")
    if ordered:
        row_list = [(s, sorted(leaves)) for s, leaves in sorted(rows.items())]
    else:
        row_list = [(s, list(leaves)) for s, leaves in sorted(rows.items())]
        if all(leaves == sorted(leaves) for _s, leaves in row_list):
            raise TemplateError(f"{kind}: ordered=False on data whose leaves all "
                                "sort already — the unordered flag would lie; "
                                "shuffle the data or set ordered=True")

    if key is None:
        ks, kl = row_list[0][0], row_list[0][1][0]
    else:
        if not isinstance(key, (list, tuple)) or len(key) != 2:
            raise TemplateError(f"{kind}: key=(stem_digit, leaf_digit) — got {key!r}")
        ks = _whole(kind, "key stem", key[0])
        kl = _whole(kind, "key leaf", key[1])
        if not 0 <= ks <= 99 or not 0 <= kl <= 9:
            raise TemplateError(f"{kind}: key stem must be 0–99 and the leaf a "
                                f"single digit — got ({ks}, {kl})")
        present = dict(row_list)
        if ks not in present or kl not in present[ks]:
            raise TemplateError(f"{kind}: the key ({ks} | {kl}) does not restate a "
                                "printed stem and leaf — the key must read a "
                                "drawn row")
    kv = 10 * ks + kl
    if values == "stem":
        vt.require_stem(stem, **{f"key value {kv}": float(kv)})

    vc.reset_ids()
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    glyph = _Labels(add)

    # A stem-and-leaf plot is naturally RULED — every digit's row sits between
    # two horizontal rules like a table row (the tally_chart already rules its
    # frame).  Half-pitch spacing keeps each glyph ~12-14u from a rule — clear
    # of the stroke floor, well inside the visual target rule's reach.
    pitch_y, stem_x, rule_x, leaf_x0, leaf_pitch = 50.0, 30.0, 56.0, 78.0, 30.0
    max_leaves = max(len(leaves) for _s, leaves in row_list)
    y_rule_top, y_rule_bot = -pitch_y / 2, (len(row_list) - 1) * pitch_y + pitch_y / 2
    x_rule_l, x_rule_r = 6.0, leaf_x0 + (max_leaves - 1) * leaf_pitch + 24.0
    for i in range(len(row_list) + 1):
        y = -pitch_y / 2 + i * pitch_y
        elements.append(vc.line((x_rule_l, y), (x_rule_r, y), id=f"hrule{i}"))
    elements.append(vc.line((rule_x, y_rule_top), (rule_x, y_rule_bot), id="rule"))
    add('describe "each row is ruled — digits sit between horizontal rules"',
        "inferred", "a ruled table, like a tally chart's frame")
    for i, (s, leaves) in enumerate(row_list):
        y = i * pitch_y
        elements.append({"type": "text", "id": f"s{i}", "at": [stem_x, y],
                         "value": str(s), "align": "middle", "baseline": "middle"})
        glyph(str(s), f"stem{i}", f"the stem digit of row {i + 1}")
        add(f'describe "stem {s}: leaves {" ".join(map(str, leaves))}"', "inferred",
            f"{len(leaves)} leaf digit(s) right of the rule")
        for j, lf in enumerate(leaves):
            elements.append({"type": "text", "id": f"l{i}_{j}",
                             "at": [leaf_x0 + j * leaf_pitch, y], "value": str(lf),
                             "align": "middle", "baseline": "middle"})
            glyph(str(lf), f"leaf{i}_{j}", f"a leaf digit of row {i + 1}")

    ky = y_rule_bot + 36.0
    ksw = 11.0 * 0.62 * len(str(ks))       # the rule sits clear of the stem glyph
    krx = 8.0 + ksw + 20.0
    elements.append({"type": "text", "id": "ks", "at": [8.0 + ksw / 2.0, ky],
                     "value": str(ks), "align": "middle", "baseline": "middle"})
    elements.append(vc.line((krx, ky - 11), (krx, ky + 11), id="krule"))
    elements.append({"type": "text", "id": "kl", "at": [krx + 24.0, ky],
                     "value": str(kl), "align": "middle", "baseline": "middle"})
    elements.append({"type": "text", "id": "kv", "at": [krx + 84.0, ky],
                     "value": f"means {kv}", "align": "middle", "baseline": "middle"})
    glyph(str(ks), "keystem", "the key's stem digit")
    glyph(str(kl), "keyleaf", "the key's leaf digit")
    glyph(f"means {kv}", "keyline", "the key line's reading")
    add(f'describe "the key reads stem {ks} with leaf {kl} as {kv}"', "inferred",
        "how one row is read — the separator is drawn as a short rule")
    if not ordered:
        add('describe "the leaves are shown in data order (unsorted)"', "inferred",
            "an unordered stem-and-leaf plot")

    if len(row_list) >= 2:
        add(f"derive {' + '.join(str(len(l)) for _s, l in row_list)} = {len(vals)}",
            "inferred", "the leaf counts total the data set")
    if max(vals) > min(vals):
        add(f"derive {max(vals)} - {min(vals)} = {max(vals) - min(vals)}",
            "inferred", "the data range the plot spans")
    elif len(row_list) == 1:
        add(f"derive {len(vals)} * 1 = {len(vals)}", "inferred",
            "one stem row holds the whole data set")
    if values == "figure":
        add('describe "the printed stem and leaf digits are figure content — the '
            'student reads the plot"', "inferred", "read-off mode")
    add("none tickMark parallelMark angleMark angleArc arrow dashed shaded",
        "inferred", "a ruled plot of digits only")

    title_d = title or "A stem-and-leaf plot"
    desc_d = description or ("An ordered stem-and-leaf plot of the data with a "
                             "key line." if ordered else
                             "A stem-and-leaf plot of the data in given order "
                             "with a key line.")
    n = len(elements)
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors={}, points=[], segments=[],
                     claims=claims, ask=ask, title=title_d, description=desc_d,
                     scale="the digits are the data; spacing is a canvas choice",
                     budget=n if n > 32 else None,
                     departures=([f"{n} elements — one text per printed digit"] if n > 32 else None),
                     medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 2. Tessellation patch
# ────────────────────────────────────────────────────────────────────────────────
def build_tessellation(*, figure_id, stem, tile, rows, cols,
                       shade=None, vertex=None,
                       cell=42.0, values="stem",
                       ask=None, title=None, description=None,
                       medium="english"):
    """A `rows`×`cols` patch of ONE regular-tile lattice.

    `tile` is "square", "triangle" or "hexagon" — the three regular tiles
    that tessellate alone.  `rows`/`cols` are whole 1–6 each; the patch is
    bounded (square ≤ 36 cells, triangle ≤ 24 unit pairs = 48 triangles,
    hexagon ≤ 24 cells) so every seam still reads at figure size.

    For "triangle" each (c, r) is a unit PAIR of one down- and one
    up-pointing equilateral triangle — cells are counted as triangles, so
    the patch holds `2·rows·cols`.  `shade=[i, …]` shades whole cells by
    index, row-major over the patch (for triangles, index i is the i-th
    triangle in strip order: down, up, down, up …).  At most 12 shaded
    cells; duplicates and off-patch indices refuse.

    `vertex="V"` marks the lattice vertex shared by the most tiles (nearest
    the patch centre on a tie) with a dot and its letter seated inside the
    nearest incident-tile pocket — for vertex-figure questions.  Its lattice
    neighbours take the next spare capitals in angle order; the builder emits
    `equal` spoke claims, and REAL per-sector `right`/`angle` claims measured
    between consecutive spokes (`angle` upgrades to stem evidence only when
    the sector is a stem number); the 360° vertex `derive` is emitted only at
    a fully-surrounded vertex — a patch-edge vertex is never assumed 360/k.

    Semi-regular tilings, strip patterns, Escher-style custom tiles and
    overlapping/multi-family mixes stay OUT.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "tessellation"
    values = _values_mode(kind, values)
    if tile not in ("square", "triangle", "hexagon"):
        raise TemplateError(f"{kind}: tile must be square|triangle|hexagon — "
                            f"got {tile!r} (mixed and irregular tiles stay outside)")
    rows = _whole(kind, "rows", rows)
    cols = _whole(kind, "cols", cols)
    if not 1 <= rows <= 6 or not 1 <= cols <= 6:
        raise TemplateError(f"{kind}: rows and cols must be whole 1–6 — "
                            f"got {rows}×{cols}")
    limit = {"square": 36, "triangle": 24, "hexagon": 24}[tile]
    if rows * cols > limit:
        raise TemplateError(f"{kind}: a {rows}×{cols} {tile} patch holds "
                            f"{rows * cols} "
                            f"{'unit pairs' if tile == 'triangle' else 'cells'} — "
                            f"the bound is {limit}; bigger patches cannot draw "
                            "honestly")
    cell = _num(kind, "cell", cell)
    if not 24.0 <= cell <= 70.0:
        raise TemplateError(f"{kind}: cell {cell:g} outside 24–70 units")
    if values == "stem":
        vt.require_stem(stem, rows=float(rows), cols=float(cols))
    if vertex is not None:
        vertex = _one_letter(kind, "vertex", vertex)
        min_cell = {"square": 46.0, "triangle": 70.0, "hexagon": 42.0}[tile]
        if cell < min_cell:
            raise TemplateError(f"{kind}: a marked vertex seats its letters inside "
                                f"a tile — {tile} needs cell ≥ {min_cell:g} units "
                                f"(got {cell:g})")
        if tile == "triangle" and (rows < 3 or cols < 3):
            raise TemplateError(f"{kind}: a marked vertex on the triangular "
                                "lattice needs a full neighbourhood — rows and "
                                "cols must both be ≥ 3")

    s = cell
    h = s * math.sqrt(3.0) / 2.0
    # cells: list of corner-point lists, in the shade/claim index order
    cells: list[list[tuple[float, float]]] = []
    if tile == "square":
        for r in range(rows):
            for c in range(cols):
                x, y = c * s, r * s
                cells.append([(x, y), (x + s, y), (x + s, y + s), (x, y + s)])
    elif tile == "triangle":
        # strip r sits between vertex rows r and r+1; row j's vertices are
        # x = i·s + (j%2)·s/2.  In each strip: down, up, down, up …
        def vtx(i, j):
            return (i * s + (j % 2) * s / 2.0, j * h)
        for r in range(rows):
            for c in range(cols):
                cells.append([vtx(c, r), vtx(c + 1, r), vtx(c + (r % 2), r + 1)])
                cells.append([vtx(c, r + 1), vtx(c + 1, r + 1), vtx(c + 1 - (r % 2), r)])
    else:  # hexagon — flat-top columns, odd columns shifted h/2 down
        hh = math.sqrt(3.0) * s
        for r in range(rows):
            for c in range(cols):
                cx, cy = c * 1.5 * s, r * hh + (c % 2) * hh / 2.0
                cells.append([(cx + s * math.cos(math.radians(60 * k)),
                               cy + s * math.sin(math.radians(60 * k)))
                              for k in range(6)])
    n_cells = len(cells)

    if shade is None:
        shade_idx: list[int] = []
    else:
        if not isinstance(shade, (list, tuple)):
            raise TemplateError(f"{kind}: shade must be a list of cell indices")
        if len(shade) > 12:
            raise TemplateError(f"{kind}: at most 12 shaded cells")
        shade_idx = []
        for i, k in enumerate(shade):
            kk = _whole(kind, f"shade[{i}]", k)
            if not 0 <= kk < n_cells:
                raise TemplateError(f"{kind}: shade[{i}] = {kk} — the patch has "
                                    f"{n_cells} cells")
            if kk in shade_idx:
                raise TemplateError(f"{kind}: cell {kk} is shaded twice")
            shade_idx.append(kk)

    def rkey(p):
        return (round(p[0], 3), round(p[1], 3))

    edges: set[tuple] = set()
    incidence: dict[tuple, int] = {}
    adjacency: dict[tuple, set] = {}
    for pts in cells:
        for p in pts:
            incidence[rkey(p)] = incidence.get(rkey(p), 0) + 1
        for i in range(len(pts)):
            a, b = rkey(pts[i]), rkey(pts[(i + 1) % len(pts)])
            edges.add(frozenset((a, b)))
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)

    vc.reset_ids()
    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []
    anchors: dict[str, tuple[float, float]] = {}
    declared_segments: list[str] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    glyph = _Labels(add)

    for i in sorted(shade_idx):
        elements.append(vc.polygon(cells[i], fill=vc.SHADE, stroke_width=0,
                                   id=f"cell{i}"))
    # unique seams, deterministic order (sorted — never set iteration)
    for k, e in enumerate(sorted(edges, key=lambda f: sorted(f))):
        a, b = sorted(e)
        elements.append(vc.line(a, b, id=f"e{k}"))

    unit_name = {"square": "square tiles", "triangle": "equilateral-triangle "
                 "tiles", "hexagon": "regular-hexagon tiles"}[tile]
    add(f'describe "a {rows} by {cols} patch of {unit_name}"', "inferred",
        f"{n_cells} cells share full edges — a regular tiling")
    if tile == "triangle":
        add(f"derive {rows} * {cols} = {rows * cols}", "inferred", "unit pairs")
        add(f"derive 2 * {rows * cols} = {n_cells}", "inferred",
            "each pair splits into two triangles")
    else:
        add(f"derive {rows} * {cols} = {n_cells}", "inferred", "the cell count")
    for i in shade_idx:
        add(f"paint cell{i} shaded", "inferred", f"cell {i} is filled")
    if shade_idx:
        add(f"shaded {len(shade_idx)} of {n_cells} cells", "inferred",
            "the filled subset")
    if values == "figure":
        add('describe "the patch dimensions are figure content — the student '
            'counts the cells"', "inferred", "read-off mode")

    if vertex is not None:
        # the most interior lattice vertex, tie-broken nearest the centroid —
        # deterministic order, never set iteration order
        allpts = [p for cellpts in cells for p in cellpts]
        cen = (sum(p[0] for p in allpts) / len(allpts),
               sum(p[1] for p in allpts) / len(allpts))
        best_deg = max(incidence.values())
        cand = sorted([p for p, d in incidence.items() if d == best_deg],
                      key=lambda p: (vc.dist(p, cen), p[0], p[1]))
        V = cand[0]
        anchors[vertex] = V
        nbr_pts = sorted(adjacency[V],
                         key=lambda p: math.atan2(p[1] - V[1], p[0] - V[0]))
        pool = [c for c in _NEIGHBOUR_POOL if c != vertex]
        if len(nbr_pts) > len(pool):
            raise TemplateError(f"{kind}: too many neighbours at {vertex}")
        nbrs = {lt: p for lt, p in zip(pool, nbr_pts)}
        anchors.update(nbrs)
        # vertex letters seat INSIDE an incident cell — a floater's sparse
        # sweep cannot hit the pocket a tile leaves between its edges.  The
        # seat that hugs the vertex's own corner of a tile is what the visual
        # target rule wants (a letter must sit ≤1.5·fontSize from SOME ink —
        # here its vertex dot) — so sweep the wedge pocket and take the
        # FEASIBLE seat NEAREST the vertex, not the roomiest.
        cells_of: dict[tuple, list[int]] = {}
        for ci, cellpts in enumerate(cells):
            for p in cellpts:
                cells_of.setdefault(rkey(p), []).append(ci)
        order = [vertex] + list(nbrs)
        for lt in order:
            elements.append(_dot(anchors[lt], f"d{lt}"))
        # everything emitted so far is the paint a letter must clear:
        # lattice seams, shaded cell rims (fill outlines) and the vertex dots
        strokes = vt.stroke_segments(elements)
        # mirror finish()'s own scale estimate: label boxes stay inside the
        # patch or hang ~10u past it; margins follow the same 9px slack rule
        allpts = [p for cellpts in cells for p in cellpts]
        span_x = max(p[0] for p in allpts) - min(p[0] for p in allpts) + 20.0
        span_y = max(p[1] for p in allpts) - min(p[1] for p in allpts) + 20.0
        margin = max(12.0, 9.0 * (max(span_x, span_y) + 60.0) / 276.0)
        s_est = min(1.0, 294.0 / (span_x + 2 * margin + 60.0),
                    276.0 / (span_y + 2 * margin + 60.0))
        need_ink = 8.0 / s_est + 0.4         # label box ↔ any ink, est units
        need_own = 3.0 / s_est + 0.3         # nearer own vertex than rivals
        need_gap = 4.0 / s_est + 0.3         # letter box ↔ letter box
        seated_boxes: list[tuple[float, float, float, float]] = []

        def seat(P: tuple, lt: str):
            """The box-centre of letter `lt` inside an incident cell: clear of
            every stroke, nearer P than every other lettered anchor, clear of
            seated letters — the feasible seat NEAREST P, or None."""
            rivals = [a for o, a in anchors.items() if a != P]
            hw = vt._label_width(lt, 11.0) / 2.0
            hu, hd = 0.70 * 11.0, 0.58 * 11.0
            inc = sorted(cells_of.get(rkey(P), []),
                         key=lambda ci: (sum(q[0] for q in cells[ci]),
                                         sum(q[1] for q in cells[ci])))
            best = None
            for ci in inc:
                pts = cells[ci]
                i0 = next(i for i, q in enumerate(pts)
                          if rkey(q) == rkey(P))
                u1 = vc.unit(P, pts[(i0 - 1) % len(pts)])
                u2 = vc.unit(P, pts[(i0 + 1) % len(pts)])
                cen = (sum(q[0] for q in pts) / len(pts),
                       sum(q[1] for q in pts) / len(pts))
                r_max = vc.dist(P, cen) * 1.25
                rr = 12.0
                while rr <= r_max:
                    if best is not None and rr > best[0] + 1.0:
                        break                    # only a nearer seat can win
                    for t in (0.10, 0.18, 0.26, 0.34, 0.42, 0.5,
                              0.58, 0.66, 0.74, 0.82, 0.90):
                        dx = u1[0] + (u2[0] - u1[0]) * t
                        dy = u1[1] + (u2[1] - u1[1]) * t
                        dl = math.hypot(dx, dy)
                        if dl < 1e-9:
                            continue
                        p = (P[0] + rr * dx / dl, P[1] + rr * dy / dl)
                        box = (p[0] - hw, p[1] - hu, p[0] + hw, p[1] + hd)
                        gap = min(vt._seg_rect_dist(a, b, box) - w / 2
                                  for a, b, w in strokes)
                        if gap < need_ink:
                            continue
                        own = vc.dist(p, P)
                        if any(vc.dist(p, r) - own < need_own
                               for r in rivals):
                            continue
                        if any(vt._rect_gap(box, qb) < need_gap
                               for qb in seated_boxes):
                            continue
                        if best is None or own < best[0]:
                            best = (own, p, box)
                    rr += 1.0
            return best

        for lt in order:
            P = anchors[lt]
            found = seat(P, lt)
            if found is None:
                raise TemplateError(
                    f"{kind}: letter {lt} cannot seat inside a tile clear of "
                    f"its edges — raise cell (≥{min_cell:g} for {tile} tiles)")
            _own, spot, box = found
            seated_boxes.append(box)
            elements.append({"type": "text", "id": f"t{lt}", "at": list(spot),
                             "value": lt, "align": "middle", "baseline": "middle",
                             "fontSize": 11})
            glyph(lt, lt, "a lattice vertex")
        k = len(nbrs)
        lts = list(nbrs)                       # already in angular order round V
        declared_segments += [f"{vertex}{lt}" for lt in lts]
        for i in range(k - 1):                 # consecutive pairs ⇒ all spokes equal
            add(f"equal {vertex}{lts[i]} {vertex}{lts[i + 1]}", "measured",
                "lattice edges out of the marked vertex are equal")
        tname = {"square": "square", "triangle": "equilateral triangle",
                 "hexagon": "regular hexagon"}[tile]
        tile_int = {"square": 90.0, "triangle": 60.0, "hexagon": 120.0}[tile]
        add(f'describe "{best_deg} {tname} corner{"" if best_deg == 1 else "s"} '
            f'meet at {vertex}"', "inferred",
            f"{k} lattice edges run out of the vertex")
        # claim the REAL angular sectors between consecutive spokes — a vertex on
        # the patch edge is not fully surrounded, so 360/k is never assumed
        stem_ns = vt.stem_numbers(stem)
        for i in range(k):
            a, b = lts[i], lts[(i + 1) % k]
            g = round((math.degrees(math.atan2(nbrs[b][1] - V[1],
                                             nbrs[b][0] - V[0])
                       - math.atan2(nbrs[a][1] - V[1],
                                    nbrs[a][0] - V[0])) % 360.0), 2)
            if g > 180.0 + 1e-6:
                continue                     # the open side of a patch-edge vertex
            if abs(g - 90.0) < 0.5:
                add(f"right {a} {vertex} {b}", "measured",
                    "a right angle between consecutive seams")
            elif abs(g - 180.0) < 0.5:
                add(f"collinear {a} {vertex} {b}", "measured",
                    "the seam runs straight through the vertex")
            elif any(abs(g - n_) <= 0.5 for n_ in stem_ns):
                add(f"angle {a} {vertex} {b} = {g:g}", "stem",
                    "the stated angle between consecutive seams")
            else:
                add(f'describe "the seams at {vertex} bound a {g:g}° sector"',
                    "inferred", "measured between consecutive spokes")
        if abs(best_deg * tile_int - 360.0) < 1.0:
            add(f"derive {best_deg} * {tile_int:g} = 360", "inferred",
                "the tile corners round the vertex fill a turn")

    add("none tickMark parallelMark angleMark angleArc arrow dashed"
        + ("" if shade_idx else " shaded"), "inferred",
        "lattice seams" + (", fills" if shade_idx else "") + " and markers only")

    title_d = title or f"A {tile}-tile tessellation patch"
    desc_d = description or (f"A {rows} by {cols} patch of {unit_name}"
                             + (f" with vertex {vertex} marked" if vertex else "")
                             + (f", {len(shade_idx)} cells shaded" if shade_idx else "") + ".")
    n = len(elements)
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors=anchors,
                     points=list(anchors), segments=declared_segments,
                     claims=claims, ask=ask, title=title_d, description=desc_d,
                     scale="every tile is congruent; cell size is a canvas choice",
                     budget=n if n > 32 else None,
                     departures=([f"{n} elements — deduplicated lattice seams"] if n > 32 else None),
                     medium=medium)


# ────────────────────────────────────────────────────────────────────────────────
# 3. Two-centre bearing triangulation
# ────────────────────────────────────────────────────────────────────────────────
def build_bearing_map(*, figure_id, stem, centres, bearings,
                      target="T", unit_px=45.0,
                      ask=None, title=None, description=None,
                      medium="english"):
    """Two observation points, a north arrow at each, and bearing rays that
    MEET at a computed target.

    `centres={"A": (x, y), "B": (x, y)}` gives the two points on an abstract
    map frame — grid coordinates with +y NORTH (the canvas flips it, so the
    bearings stay honest clockwise-from-north).  `bearings={"A": deg,
    "B": deg}` are the stated bearings, 0–360, ALWAYS stem-checked: this
    figure is stem-only — bearings are givens, never read off the ink.

    The target `target="T"` is COMPUTED as the intersection of the two
    bearing rays — the caller never places it.  Parallel or coincident rays
    (|cross| under ~5°), rays that diverge (the intersection lies behind a
    centre), and an implausibly remote fix all refuse.  A bearing over 180°
    draws its reflex arc honestly and is claimed as a `describe`; a bearing
    up to 180° carries an `angle` claim against the stem.  The angle the two
    rays make at the target is emitted as a derive-cited `angle` claim.  Each
    printed bearing numeral seats by its own angle-mark's arc — a numeral's
    claim names the three-letter angle.

    Distance labels, map landmarks and three-centre fixes stay OUT — the
    frame is abstract, only the bearings carry meaning.
    """
    import vdd_templates as vt
    TemplateError = vt.TemplateError
    kind = "bearing_map"
    if not isinstance(centres, dict) or len(centres) != 2:
        raise TemplateError(f"{kind}: centres must be exactly two "
                            "{letter: (x, y)} entries")
    if not isinstance(bearings, dict) or set(bearings) != set(centres):
        raise TemplateError(f"{kind}: bearings must give one bearing per centre — "
                            "same letters as `centres`")
    target = _one_letter(kind, "target", target)
    unit_px = _num(kind, "unit_px", unit_px)
    if not 20.0 <= unit_px <= 90.0:
        raise TemplateError(f"{kind}: unit_px {unit_px:g} outside 20–90")

    pts: dict[str, tuple[float, float]] = {}
    for lt, xy in centres.items():
        _one_letter(kind, "centre", lt)
        if lt == target:
            raise TemplateError(f"{kind}: centre {lt} collides with the target letter")
        if not isinstance(xy, (list, tuple)) or len(xy) != 2:
            raise TemplateError(f"{kind}: centre {lt} needs (x, y)")
        x = _num(kind, f"centre {lt} x", xy[0])
        y = _num(kind, f"centre {lt} y", xy[1])
        if max(abs(x), abs(y)) > 50.0:
            raise TemplateError(f"{kind}: centre {lt} at ({x:g}, {y:g}) — keep the "
                                "map frame within ±50 units")
        pts[lt] = (x, y)
    (la, pa), (lb, pb) = sorted(pts.items())
    if vc.dist(pa, pb) < 0.5:
        raise TemplateError(f"{kind}: centres {la} and {lb} coincide on the map frame")

    bdeg: dict[str, float] = {}
    for lt, b in bearings.items():
        bv = _num(kind, f"bearing {lt}", b)
        if not 0.0 <= bv < 360.0:
            raise TemplateError(f"{kind}: bearing {lt} = {bv:g} — bearings are 0–360")
        vt.require_stem(stem, **{f"bearing {lt}": bv})
        bdeg[lt] = bv

    def ray_dir(b):  # bearing → map-frame unit vector (north = +y)
        t = math.radians(b)
        return (math.sin(t), math.cos(t))

    dA, dB = ray_dir(bdeg[la]), ray_dir(bdeg[lb])
    cross = dA[0] * dB[1] - dA[1] * dB[0]
    if abs(cross) < math.sin(math.radians(5.0)):
        raise TemplateError(f"{kind}: the bearing rays from {la} and {lb} are "
                            "parallel or near-parallel — no clean fix exists")
    # solve pa + t·dA = pb + u·dB
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    t = (dx * dB[1] - dy * dB[0]) / cross
    u = (dx * dA[1] - dy * dA[0]) / cross
    if t <= 0.05 or u <= 0.05:
        raise TemplateError(f"{kind}: the rays from {la} and {lb} diverge — their "
                            "intersection lies behind a centre, so no forward fix")
    T_g = (pa[0] + t * dA[0], pa[1] + t * dA[1])
    far = vc.dist((0.0, 0.0), (min(pa[0], pb[0], T_g[0]), min(pa[1], pb[1], T_g[1])))
    if max(abs(T_g[0]), abs(T_g[1])) > 60.0 or far > 120.0:
        raise TemplateError(f"{kind}: the fix lands outside the drawable map frame")

    def to_canvas(p):
        return (p[0] * unit_px, -p[1] * unit_px)

    vc.reset_ids()
    anchors = {la: to_canvas(pa), lb: to_canvas(pb), target: to_canvas(T_g)}
    tips = {}
    pool = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if c not in anchors and c != target]
    for i, lt in enumerate((la, lb)):
        tips[lt] = pool[i]
        anchors[tips[lt]] = (anchors[lt][0], anchors[lt][1] - 46.0)

    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))

    glyph = _Labels(add)

    for lt in (la, lb):
        elements.append(vc.arrow(anchors[lt], anchors[tips[lt]], id=f"north{lt}"))
        elements.append(_dot(anchors[lt], f"d{lt}"))
        elements.append(_point_label(anchors[lt], lt))
        glyph(lt, lt, "an observation point")
        elements.append({"type": "text", "id": f"nlab{lt}", "at": [0, 0],
                         "value": "N", "align": "middle", "baseline": "middle",
                         "_near": list(anchors[tips[lt]]), "_gap": 10})
        glyph("N", f"north{lt.lower()}", "the north arrow's mark")

    for lt in (la, lb):
        elements.append(vc.line(anchors[lt], anchors[target], id=f"ray{lt}"))
    elements.append(_dot(anchors[target], f"d{target}"))
    elements.append(_point_label(anchors[target], target))
    glyph(target, target, "the computed target")

    add(f"parallel {la}{tips[la]} {lb}{tips[lb]}", "measured",
        "the two north arrows point the same way")
    add(f'describe "the bearing rays from {la} and {lb} meet at {target}"',
        "measured", "the target sits on both rays by construction")

    for lt in (la, lb):
        b = bdeg[lt]
        tip = tips[lt]
        mark = vc.angle_label(anchors[lt], anchors[tip], anchors[target],
                              r=30, arcs=1, reflex=b > 180.0)[0]
        elements.append(mark)
        text = f"{b:03.0f}°" if float(b).is_integer() else f"{b:g}°"
        pos = _seat_bearing_label(anchors[lt], b, text, elements, mark)
        if pos is None:
            raise TemplateError(f"{kind}: the {text} label finds no clear seat "
                                f"around {lt} — a very narrow wedge; spread the "
                                "centres or pick a less acute bearing")
        elements.append({"type": "text", "id": f"gl{lt}", "at": list(pos),
                         "value": text, "align": "middle", "baseline": "middle"})
        glyph(text, f"{tip}{lt}{target}", "the printed bearing")
        if b <= 180.0:
            add(f"angle {tip} {lt} {target} = {b:g}", "stem",
                "the stated bearing, north arrow to ray")
        else:
            add(f'describe "the reflex bearing at {lt} is {b:g}° from north '
                f'clockwise to the ray"', "inferred",
                "a bearing over 180° draws the major arc")

    def emit_derive(expr, val, note):
        add(f"derive {expr} = {val:g}", "inferred", note)
        return f"K{len(claims)}"

    # the angle the fix makes at the target — derive-cited, stem-backed
    dAB = abs(bdeg[lb] - bdeg[la]) % 360.0
    atT = min(dAB, 360.0 - dAB)
    if atT > 0.5:
        if dAB <= 180.0:
            cid = emit_derive(f"{max(bdeg[la], bdeg[lb]):g} - "
                              f"{min(bdeg[la], bdeg[lb]):g}", dAB,
                              "the two stated bearings differ")
        else:
            c1 = emit_derive(f"{max(bdeg[la], bdeg[lb]):g} - "
                             f"{min(bdeg[la], bdeg[lb]):g}", dAB,
                             "the two stated bearings differ")
            cid = emit_derive(f"360 - {dAB:g}", atT,
                              f"the reflex supplement of derive {c1}")
        add(f"angle {la} {target} {lb} = {atT:g}", "measured",
            f"the angle at the fix — derive {cid}")

    add("none tickMark parallelMark angleArc dashed shaded", "inferred",
        "dots, north arrows, rays and bearing arcs only")

    title_d = title or "Bearings from two points"
    desc_d = description or (f"Bearing rays from {la} and {lb}, each measured "
                             f"from a north arrow, meet at {target}.")
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors=anchors, points=list(anchors),
                     segments=[], claims=claims, ask=ask,
                     title=title_d, description=desc_d,
                     scale="the map frame is abstract — only the bearings and "
                          "the fix carry meaning",
                     medium=medium)
