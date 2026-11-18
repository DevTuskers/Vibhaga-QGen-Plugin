"""Bounded G7 vertical scales, prime factor trees and unit-cube heightmaps.

Scales have 2–10 equal intervals, integer bounds and half-step readings.
Factor trees have depth <=4, <=8 prime leaves, and values <=1000000;
a split keyed by a value applies to every occurrence of that value.
Cube arrays use a front-left-origin heightmap, footprint <=5 by 4,
height <=4 and total <=64. Exposed front/right/top unit faces are computed;
fully hidden cubes are explicitly counted in claims. No caller coordinates.
Dual scales, factor ladders, terminal ones, floating cubes, dimension arrows,
arbitrary cameras and decorative apparatus are outside these contracts.
Registration is deliberately left to the lead. Template imports are lazy.
"""
from __future__ import annotations

from decimal import Decimal
import math
import re
import vdd_cookbook as vc


def _num(name, value):
    from vdd_templates import TemplateError
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TemplateError(f"{name} must be a finite number")
    try:
        f = float(value)
    except OverflowError:
        raise TemplateError(f"{name} must be a finite number") from None
    if not math.isfinite(f) or abs(f) > 1000000:
        raise TemplateError(f"{name} must be finite and at most 1000000 in magnitude")
    return f


def _integer(name, value, lo, hi):
    from vdd_templates import TemplateError
    f = _num(name, value)
    if not f.is_integer() or not lo <= f <= hi:
        raise TemplateError(f"{name} must be an integer in {lo}..{hi}")
    return int(f)


def _letters(seq):
    from vdd_templates import TemplateError
    if isinstance(seq, str):
        seq = list(seq)
    if not isinstance(seq, (list, tuple)) or not seq:
        raise TemplateError("leaves must be a nonempty sequence of capitals")
    if any(not isinstance(s, str) or not re.fullmatch('[A-Z]', s) for s in seq):
        raise TemplateError("leaves must be single capitals")
    if len(set(seq)) != len(seq):
        raise TemplateError("leaf letters must be distinct")
    return list(seq)


def _mode(values):
    from vdd_templates import TemplateError
    if values not in ('stem', 'figure'):
        raise TemplateError('values must be stem or figure')
    return 'stem' if values == 'stem' else 'inferred'


def _end(kind, figure_id, stem, el, anchors, claims, ask, title, description,
         medium, segments=(), scale='symbolic layout; not a length scale'):
    from vdd_templates import finish
    claims.append(('describe "numeric values are figure content where marked inferred"', 'inferred', 'computed or read-the-figure content; stem-backed givens are marked stem'))
    claims.append(('none tickMark parallelMark angleArc', 'inferred', 'no geometric equality or angle marks'))
    if len(el) > 32:
        departures = ['Unit subdivisions or branching require one element per visible face, edge or node.']
    else:
        departures = None
    return finish(kind=kind, figure_id=figure_id, stem=stem, elements=el,
                  anchors=anchors, points=list(anchors), segments=list(segments),
                  claims=claims, ask=ask if ask is not None else [('a', 'Read the diagram.')], title=title or kind.replace('_', ' '),
                  description=description or 'A mathematical diagram with marked features.',
                  medium=medium, scale=scale, budget=len(el) if len(el) > 32 else None,
                  departures=departures)


def build_vertical_scale(*, figure_id, stem, v_min, v_max, step, level,
                         values='stem', unit='C', pointer='fluid', ask=None,
                         title=None, description=None, medium='english'):
    from vdd_templates import TemplateError, require_stem_signed
    ev = _mode(values)
    lo = _integer('v_min', v_min, -10000, 10000)
    hi = _integer('v_max', v_max, -10000, 10000)
    _num('step', step)
    _num('level', level)
    a, b, d, t = map(lambda x: Decimal(str(x)), (lo, hi, step, level))
    if b <= a or d <= 0 or (b-a) % d or not 2 <= (b-a)/d <= 10:
        raise TemplateError('scale needs 2..10 equal intervals without crowded numerals')
    if not a <= t <= b or (t-a) % (d/2):
        raise TemplateError('level must lie within bounds on the half-step lattice')
    if pointer not in ('fluid', 'marker') or not isinstance(unit, str) or not re.fullmatch('[A-Za-z°]{1,4}', unit):
        raise TemplateError('pointer must be fluid/marker; unit must be a short English symbol')
    if values == 'stem':
        require_stem_signed(stem, v_min=lo, v_max=hi, step=float(d), level=float(t))
    fmt = lambda x: format(x.normalize(), 'f')
    n = int((b-a)/d)
    height = 42*n
    y = lambda v: height * float((b-v)/(b-a))
    anchors = {'A': (0, height), 'B': (0, 0), 'T': (0, y(t))}
    el = [vc.line(anchors['A'], anchors['B'], id='AB')]
    claims = [(f'axis AB from {lo} to {hi}', ev, 'linear vertical calibration'),
              (f'tick AB step {fmt(d)}', ev, 'every graduation has a numeral'),
              (f'reads T {fmt(t)} on AB', 'inferred' if t < 0 else ev,
               'marked level on the real axis; negative levels are signed-stem-checked in stem mode, but the audit stem tokenizer is unsigned'),
              (f'derive {hi} - {lo} = {hi-lo}', 'inferred', 'calibrated span')]
    for i in range(n+1):
        v = a+i*d
        yy = y(v)
        el += [vc.line((-7, yy), (7, yy), id=f'tick{i}'),
               vc.text((-24, yy+4), fmt(v), align='end', id=fmt(v))]
        claims.append((f'label "{fmt(v)}" names {fmt(v)}', ev, 'graduation numeral'))
    tube_x = height * .4 + 40
    el += [vc.line((tube_x, 0), (tube_x, height), id='tubeleft'),
           vc.line((tube_x+20, 0), (tube_x+20, height), id='tuberight')]
    el.append(vc.text((tube_x+10, -34), unit, id='unit'))
    claims.append((f'label "{unit}" names unit', 'inferred', 'scale unit'))
    if pointer == 'fluid':
        if t == a:
            el.append(vc.line((tube_x, height), (tube_x+20, height), width=4, id='fluid'))
        else:
            el.append(vc.polygon([(tube_x,height),(tube_x+20,height),(tube_x+20,y(t)),(tube_x,y(t))], fill='#93c5fd', id='fluid'))
        claims.append(('describe "the fluid column ends at the marked level T"', 'inferred', 'column top aligns with T'))
    else:
        el.append(vc.polygon([(12,y(t)),(30,y(t)-7),(30,y(t)+7)], fill='#333333', id='marker'))
        claims.append(('describe "the triangular pointer marks level T"', 'inferred', 'pointer tip projects to T'))
    return _end('vertical_scale', figure_id, stem, el, anchors, claims, ask, title,
                description, medium, ['AB'], 'to scale along the vertical axis; tube width symbolic')


def build_factor_tree(*, figure_id, stem, n, splits, leaves=None, values='stem',
                      ask=None, title=None, description=None, medium='english'):
    from vdd_templates import TemplateError, require_stem
    ev = _mode(values)
    root = _integer('n', n, 2, 1000000)
    if not isinstance(splits, dict) or len(splits) > 7:
        raise TemplateError('splits must be a dictionary with at most seven entries')
    pairs = {}
    for parent, pair in splits.items():
        p = _integer('parent', parent, 2, 1000000)
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise TemplateError('each split must be a factor pair')
        x, y = [_integer('factor', v, 2, 1000000) for v in pair]
        if x*y != p:
            raise TemplateError('factor product does not equal parent')
        pairs[p] = (x, y)
    nodes, edges, terminals, used = [], [], [], set()
    def visit(v, depth):
        if depth > 4:
            raise TemplateError('factor tree depth exceeds four')
        idx = len(nodes)
        nodes.append([v, depth, 0])
        if v in pairs:
            used.add(v)
            children = [visit(w, depth+1) for w in pairs[v]]
            nodes[idx][2] = sum(nodes[c][2] for c in children)/2
            edges.extend((idx,c) for c in children)
        else:
            if any(v % k == 0 for k in range(2, math.isqrt(v)+1)):
                raise TemplateError('every terminal must be prime; missing composite split')
            if len(terminals) >= 8:
                raise TemplateError('factor tree exceeds eight leaves')
            nodes[idx][2] = len(terminals)*88
            terminals.append(idx)
        return idx
    visit(root, 0)
    if used != set(pairs):
        raise TemplateError('unreachable split or impossible tree')
    letters = _letters(leaves) if leaves is not None else None
    if letters is not None and len(letters) != len(terminals):
        raise TemplateError('one letter is required per prime leaf')
    if letters is not None and values == 'figure':
        raise TemplateError('letter-masked prime leaves are not readable numeric figure content')
    if values == 'stem':
        require_stem(stem, **{f'node{i}': v for i,(v,_,_) in enumerate(nodes)})
    el, claims = [], []
    for i,j in edges:
        _,di,xi = nodes[i]
        _,dj,xj = nodes[j]
        el.append(vc.line((xi,di*100+24),(xj,dj*100-32),id=f'e{i}_{j}'))
    seen_glyphs = set()
    for i,(v,depth,x) in enumerate(nodes):
        glyph = letters[terminals.index(i)] if letters and i in terminals else str(v)
        el.append(vc.text((x,depth*100),glyph,id=f'node{i}'))
        if glyph not in seen_glyphs:
            claims.append((f'label "{glyph}" names node{i}', ev, 'factor node; repeated equal numerals share this glyph claim'))
            seen_glyphs.add(glyph)
        else:
            claims.append((f'describe "node{i} repeats the value {v}"', 'inferred', 'same numeric glyph on a separate real node'))
        if v in pairs:
            p,q = pairs[v]
            claims.append((f'describe "{v} = {p} × {q}"', ev, 'validated factor split'))
    product = ' * '.join(str(nodes[i][0]) for i in terminals)
    claims.append((f'derive {product} = {root}', 'inferred', 'prime product of the terminal nodes'))
    return _end('factor_tree',figure_id,stem,el,{},claims,ask,title,description,medium)


def build_cube_array(*, figure_id, stem, stacks, unit_cube=1, values='stem',
                     ask=None, title=None, description=None, medium='english'):
    from vdd_templates import TemplateError, require_stem
    ev = _mode(values)
    edge = _num('unit_cube', unit_cube)
    if edge <= 0:
        raise TemplateError('unit_cube edge must be positive')
    if not isinstance(stacks, dict) or not 1 <= len(stacks) <= 20:
        raise TemplateError('stacks must be a nonempty heightmap with at most twenty columns')
    grid = {}
    for pos,h in stacks.items():
        if not isinstance(pos, tuple) or len(pos) != 2:
            raise TemplateError('stack keys must be (column,row) pairs')
        c = _integer('column',pos[0],0,4)
        r = _integer('row',pos[1],0,3)
        grid[c,r] = _integer('height',h,1,4)
    if min(c for c,r in grid) or min(r for c,r in grid):
        raise TemplateError('heightmap must use the front-left origin')
    total = sum(grid.values())
    if total > 64:
        raise TemplateError('cube total exceeds 64')
    if values == 'stem':
        require_stem(stem, edge=edge, **{f'height{i}': grid[p] for i,p in enumerate(sorted(grid))})
    project = lambda c,r,z: (c*44+r*22, -z*44-r*22)
    el, claims, hidden = [], [], 0
    for c,r in sorted(grid, key=lambda p:(-p[1],p[0])):
        h = grid[c,r]
        claims.append((f'describe "stack at column {c} row {r} contains {h} unit cubes"',ev,'front-left origin; contiguous from ground'))
        for z in range(h):
            faces = []
            if grid.get((c,r-1),0) <= z:
                faces.append(('front',[(c,r,z),(c+1,r,z),(c+1,r,z+1),(c,r,z+1)],'#dbeafe'))
            if grid.get((c+1,r),0) <= z:
                faces.append(('right',[(c+1,r,z),(c+1,r+1,z),(c+1,r+1,z+1),(c+1,r,z+1)],'#93c5fd'))
            if z == h-1:
                faces.append(('top',[(c,r,z+1),(c+1,r,z+1),(c+1,r+1,z+1),(c,r+1,z+1)],'#eff6ff'))
            if not faces:
                hidden += 1
            for name,pts,fill in faces:
                el.append(vc.polygon([project(*p) for p in pts],fill=fill,id=f'cube{c}_{r}_{z}_{name}'))
    claims += [(f'describe "{hidden} cubes have no exposed front right or top face; hidden cubes are included in the total"','inferred','occluded faces are suppressed, never counted as absent cubes'),
               (f'describe "each unit cube has edge {edge:g}"',ev,'physical edge, not projected length'),
               (f'derive {" + ".join(str(grid[p]) for p in sorted(grid))} = {total}','inferred','sum of all stack heights')]
    # A true edge label, on its own separated leader outside the stack footprint.
    y = 40
    el += [vc.line((0,y),(44,y),id='edge'), vc.text((22,y+32),f'{edge:g}',id='edgevalue')]
    claims.append((f'label "{edge:g}" names edge','inferred','unit-cube edge on separate reference segment'))
    return _end('cube_array',figure_id,stem,el,{},claims,ask,title,description,medium,
                scale='oblique projection; receding edges foreshortened; all cells are equal cubes')
