"""vdd_g9_area.py — G9 L06/L07 symbolic algebra-area figures + L10 arrow mapping.

One bounded builder each, grown ONLY from the confirmed source blocks
(wt/g9-readiness/inventory.md):

`build_algebra_area` — symbolic single-figure area models (NTS layout):
  • style="rectangle": one rectangle whose side labels are KaTeX tokens
    (covers 06:493 `x` by `x` square with `x^2` inside, 06:726 `x` by `2`
    plot, 07:629 square labelled `a`). `square=True` keeps it a square.
    Optional `area` token centred inside and right-angle corner marks.
  • style="corner_cut": a corner rectangle is removed from an outer
    rectangle — `mode="corner"` draws the L-shape that REMAINS plus the
    dashed cut (covers 06:751 L-shape, 07:650 `a` square with dashed `b`
    corner); `mode="strips"` removes a full right strip of width `cut_w`
    and a full bottom strip of height `cut_h`, leaving a smaller solid
    rectangle (covers 06:512, `(x-2) by (x-3)`). The residual area is
    ALWAYS the honest difference `outer - cut`, stated in the claims —
    never a guessed Boolean union.
  • style="frame": an inner rectangle inset inside an outer rectangle,
    the band between them shaded (covers 06:770). Band area is the
    difference `outer - inner` — justified, not dissected.

Dissection-rearrangement (07:683 L-shape -> rectangle, 06:372 square ->
grid composite, multi-panel figures) is REFUSED — it stays on the
handdrawn-residual route per the inventory; pass style="dissection" to
get the explicit refusal.

`build_mapping_arrows` — the L10 proportion arrow-mapping (10:276,
10:323, 10:380, 10:972, 10:1041): two columns under short KaTeX heading
tokens, one rightward arrow per row joining left value to right value.
Any row may carry a symbolic unknown (`x`); numeric entries in
`values="stem"` mode must be numbers the stem states. This is NOT a
generic relation diagram — rows map left[i] -> right[i] in order,
parallel arrows only; crossings and cycles are refused.

Drawn labels are KaTeX tokens only (ADR 0021 — never prose, never
Sinhala). All dimensions are symbolic: cell and column spacing are a
canvas choice, stated in the `scale` string. vdd_templates is imported
lazily inside the builders so this module stays import-light. This
module is NOT registered in vdd_templates.TEMPLATES — the lead actor
owns that file; registration is a one-line lazy entry there.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal

import vdd_cookbook as vc



def _num(kind: str, name: str, v):
    """The numeric gate every spec number passes before any arithmetic."""
    from vdd_templates import TemplateError
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TemplateError(f"{kind}: {name} {v!r} must be a finite number")
    try:
        finite = math.isfinite(float(v))
    except OverflowError:
        finite = False
    if not finite:
        raise TemplateError(f"{kind}: {name} {v!r} must be a finite number")
    return v


def _tok(kind: str, name: str, s, maxlen: int = 14) -> str:
    """A drawn token: a short KaTeX string, never empty, never prose."""
    from vdd_templates import TemplateError
    if not isinstance(s, str) or not 1 <= len(s.strip()) <= maxlen:
        raise TemplateError(
            f"{kind}: {name} {s!r} must be a non-empty latex token of "
            f"at most {maxlen} chars — no prose is drawn (ADR 0021)")
    t = s.strip()
    if " " in t and "\\" not in t:
        raise TemplateError(
            f"{kind}: {name} {s!r} contains a space — drawn tokens are "
            "latex, not phrases")
    return t


_SIGNED = re.compile(r"[+\-]?(?:\d+(?:\.\d+)?|\.\d+)")
_LIT = re.compile(r"\d+(?:\.\d+)?|\.\d+")
_EXP = re.compile(r"\^(?:\{[^}]*\}|\d)")
_MEDIA = ("english", "sinhala")


def _norm(t: str) -> str:
    """Unicode minus/en-dash → '-', spaces dropped — for parsing only."""
    return re.sub(r"\s+", "", t.replace("\u2212", "-").replace("\u2013", "-"))


def _numval(t: str):
    """The value of a WHOLE-token number — signed ('-3'), leading-dot
    ('.5') included — else None. A digit-grouping comma ('1,000') is
    refused by the caller, never read as symbolic."""
    n = _norm(t)
    return float(n) if _SIGNED.fullmatch(n) else None


def _common(kind: str, stem, medium) -> str:
    """Shared entry gate: stem must be a string, medium a known medium —
    malformed input refuses as TemplateError, never a raw TypeError."""
    from vdd_templates import TemplateError
    if not isinstance(stem, str):
        raise TemplateError(f"{kind}: stem must be a string — got "
                            f"{type(stem).__name__}")
    m = medium.strip().lower() if isinstance(medium, str) else None
    if m not in _MEDIA:
        raise TemplateError(f"{kind}: medium must be one of {_MEDIA} — got "
                            f"{medium!r}")
    return m


def _stem_check(vt, values: str, stem: str, derived=(), **tokens: str) -> None:
    """Every number a token PRINTS is checked, not only whole-number tokens.

      • a comma inside a number ('1,000') is refused outright (unsupported);
      • a whole signed/decimal token ('-3', '.5', '12') must be a stem
        number, sign included (require_stem_signed) — in values='stem';
      • numerals INSIDE a compound given token ('x-2', 'x+8', '2x') must
        each be stem numbers by magnitude (the same stem discipline the
        whole-token case has); exponents (x^{2}) are notation, not givens.
    `derived` names tokens whose truth is proved from other tokens (the
    product rule, identity checks) — their embedded numerals are skipped
    because they are computed, not given. values='figure' skips the stem
    (read-off mode) but never the comma refusal."""
    from vdd_templates import TemplateError
    for k, t in tokens.items():
        if re.search(r"\d,\d", t):
            raise TemplateError(
                f"{k} {t!r}: digit-grouping commas are unsupported — write "
                "the number without separators")
    if values != "stem":
        return
    whole, embedded = {}, {}
    for k, t in tokens.items():
        v = _numval(t)
        if v is not None:
            whole[k] = v
        elif k not in derived:
            for j, lit in enumerate(_LIT.findall(_EXP.sub("", _norm(t)))):
                embedded[f"{k}#{j}"] = float(lit)
    if whole:
        vt.require_stem_signed(stem, **whole)
    if embedded:
        vt.require_stem(stem, **embedded)


def _linear(t: str):
    """Parse a token as a linear form {var: coef, '': const} — 'x+8', '2x',
    'a-b', '-3', '.5'. Anything else (x^{2}, \\frac, products) → None
    (unverifiable). Single-letter variables only."""
    n = _norm(t)
    if not n:
        return None
    pos, out = 0, {}
    term = re.compile(r"([+\-]?)(\d+(?:\.\d+)?|\.\d+)?([A-Za-z])?")
    while pos < len(n):
        m = term.match(n, pos)
        if not m or m.end() == pos or (m[2] is None and m[3] is None):
            return None
        if pos > 0 and not m[1]:
            return None
        coef = float(m[2]) if m[2] else 1.0
        if m[1] == "-":
            coef = -coef
        key = m[3] or ""
        out[key] = out.get(key, 0.0) + coef
        pos = m.end()
    return {k: v for k, v in out.items() if abs(v) > 1e-12}


def _lin_sub(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0.0) - v
    return {k: v for k, v in out.items() if abs(v) > 1e-12}


def _lin_eq(a, b) -> bool:
    return not _lin_sub(a, b)


def _const(f):
    """The value of a constant linear form, else None."""
    if f is None:
        return None
    if not f:
        return 0.0
    return f.get("") if set(f) == {""} else None


_NUM = re.compile(r"\d+(?:\.\d+)?")
_SYM = re.compile(r"[A-Za-z](?:_\{?[A-Za-z0-9]+\}?)?")


def _product_forms(t1: str, t2: str) -> list[str]:
    """The canonical KaTeX products of two side tokens — the ONLY area labels
    the figure may print, so the centred token is a true product, never an
    arbitrary assertion.

      num × num   -> the computed product ("12")
      tok × tok   -> "tok^{2}" / "tok^2"
      num × sym   -> "numsym" ("2x") — numeric coefficient first
      sym × sym   -> "s1 s2" / "s1 \\cdot s2" (either order)
    Compound tokens (x+8 …) have no single-token product — expand in the
    STEM or use corner_cut/frame; printing a guessed product is refused."""
    if _NUM.fullmatch(t1) and _NUM.fullmatch(t2):
        return [f"{float(t1) * float(t2):g}"]
    if t1 == t2:
        return [f"{t1}^{{2}}", f"{t1}^2"]
    if _NUM.fullmatch(t1) and _SYM.fullmatch(t2):
        return [f"{float(t1):g}{t2}", f"{t1}{t2}",
                f"{float(t1):g} \\cdot {t2}", f"{float(t1):g} \\times {t2}",
                f"{t2} \\cdot {float(t1):g}", f"{t2} \\times {float(t1):g}"]
    if _NUM.fullmatch(t2) and _SYM.fullmatch(t1):
        return _product_forms(t2, t1)
    if _SYM.fullmatch(t1) and _SYM.fullmatch(t2):
        return [f"{t1}{t2}", f"{t2}{t1}", f"{t1} {t2}", f"{t2} {t1}",
                f"{t1} \\cdot {t2}", f"{t2} \\cdot {t1}"]
    return []


_CORNERS = {
    "tr": lambda W, H, cw, ch: (W - cw, 0.0, W, ch),
    "tl": lambda W, H, cw, ch: (0.0, 0.0, cw, ch),
    "br": lambda W, H, cw, ch: (W - cw, H - ch, W, H),
    "bl": lambda W, H, cw, ch: (0.0, H - ch, cw, H),
}


def _l_polygon(W, H, x0, y0, x1, y1):
    """The outer rectangle minus the corner rectangle (x0,y0)-(x1,y1)."""
    out = [(0.0, 0.0), (W, 0.0), (W, H), (0.0, H)]
    cut = {(x0, y0), (x1, y0), (x1, y1), (x0, y1)}

    if (x1, y0) == (W, 0.0):
        return [(0.0, 0.0), (x0, 0.0), (x0, y1), (W, y1), (W, H), (0.0, H)]
    if (x0, y0) == (0.0, 0.0):
        return [(x1, 0.0), (W, 0.0), (W, H), (0.0, H), (0.0, y1), (x1, y1)]
    if (x1, y1) == (W, H):
        return [(0.0, 0.0), (W, 0.0), (W, y0), (x0, y0), (x0, H), (0.0, H)]

    return [(0.0, 0.0), (W, 0.0), (W, H), (x1, H), (x1, y0), (0.0, y0)]


def build_algebra_area(*, figure_id, stem, style, ask=None, title=None,
                       description=None, medium="english", values="stem",
                       top=None, side=None, area=None, square=False,
                       right_marks=True,
                       outer_top=None, outer_side=None,
                       inner_top=None, inner_side=None,
                       cut_w=None, cut_h=None, corner="tr", mode="corner",
                       gap_top=None, gap_side=None, shaded=True,
                       W=150.0, H=110.0, frac=0.32, scale_at_x=None):
    """An algebra-area figure, symbolic unless scale_at_x is specified.

    `style` = "rectangle" | "corner_cut" | "frame" | "dissection"(refused).

    rectangle: `top`/`side` latex tokens label the top and left edges;
      `area` (optional) centres inside; `square=True` forces W=H.
    corner_cut: `outer_top`/`outer_side` label the outer rectangle;
      `cut_w`/`cut_h` label the removed corner/strip edges; `inner_top`/
      `inner_side` (optional) label the remaining edges (mode="strips"
      needs both — the remaining rectangle's sides); `corner` is which
      corner is removed; `shaded` fills the remaining region.
      A corner cut can use `scale_at_x` (a positive x), deriving the height
      and both cut dimensions from the outer width on a single scale.
    frame: `outer_top`/`outer_side`, `inner_top`/`inner_side` label the
      two rectangles; `gap_top`/`gap_side` label the band width at the
      top and left (the inner rectangle hugs the bottom-right per the
      source layout); the band is shaded.

    `values="stem"` runs require_stem over every purely-numeric token;
    "figure" declares them read-off figure content."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind = "algebra_area"
    vc.reset_ids()
    if style == "dissection":
        raise TemplateError(
            f"{kind}: dissection-rearrangement is a handdrawn residual "
            "(wt/g9-readiness/inventory.md) — a two-panel rearrangement "
            "is not this bounded single-figure builder")
    if style not in ("rectangle", "corner_cut", "frame"):
        raise TemplateError(f"{kind}: style must be 'rectangle', 'corner_cut' "
                            f"or 'frame' — got {style!r}")
    medium = _common(kind, stem, medium)
    values = str(values).strip().lower()
    if values not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure'")
    W = _num(kind, "W", W)
    H = _num(kind, "H", W if square else H)
    if not 60.0 <= float(W) <= 400.0 or not 60.0 <= float(H) <= 400.0:
        raise TemplateError(f"{kind}: W/H {W}x{H} outside 60-400 units")
    W, H = float(W), float(H)
    frac = _num(kind, "frac", frac)
    if not 0.15 <= frac <= 0.45:
        raise TemplateError(f"{kind}: frac {frac} outside 0.15-0.45 — the cut/"
                            "inner part must stay a visible but minor part")
    if square:
        H = W
    if mode not in ("corner", "strips"):
        raise TemplateError(f"{kind}: mode must be 'corner' or 'strips'")
    if style == "frame" and mode == "strips":
        raise TemplateError(f"{kind}: a frame has one inner rectangle — "
                            "mode='strips' belongs to corner_cut")
    if scale_at_x is not None and (style != "corner_cut" or mode != "corner"):
        raise TemplateError(f"{kind}: scale_at_x requires a corner cut")

    tok = lambda n, s, m=14: None if s is None else _tok(kind, n, s, m)
    top, side, area = tok("top", top), tok("side", side), tok("area", area)
    outer_top, outer_side = tok("outer_top", outer_top), tok("outer_side", outer_side)
    inner_top, inner_side = tok("inner_top", inner_top), tok("inner_side", inner_side)
    cut_w, cut_h = tok("cut_w", cut_w), tok("cut_h", cut_h)
    gap_top, gap_side = tok("gap_top", gap_top), tok("gap_side", gap_side)

    need = {"rectangle": ("top", "side"),
            "corner_cut": ("outer_top", "outer_side", "cut_w", "cut_h"),
            "frame": ("outer_top", "outer_side")}[style]
    have = {"top": top, "side": side, "outer_top": outer_top,
            "outer_side": outer_side, "cut_w": cut_w, "cut_h": cut_h,
            "inner_top": inner_top, "inner_side": inner_side}
    missing = [n for n in need if have.get(n) is None]
    if missing:
        raise TemplateError(f"{kind}: style '{style}' needs {missing} — "
                            "the side labels ARE the figure")
    if style == "corner_cut" and mode == "strips" and \
            (inner_top is None or inner_side is None):
        raise TemplateError(
            f"{kind}: mode='strips' leaves a smaller rectangle — pass "
            "inner_top/inner_side (e.g. 'x-2', 'x-3'); the figure never "
            "implies them")
    if style == "corner_cut" and corner not in _CORNERS:
        raise TemplateError(f"{kind}: corner must be one of "
                            f"{sorted(_CORNERS)} — got {corner!r}")
    if style == "rectangle" and area is not None:
        forms = _product_forms(top, side)
        if area.strip() not in forms:
            raise TemplateError(
                f"{kind}: area {area!r} is not a true product of "
                f"{top!r} x {side!r} (accepted {forms or 'none — compound '
                'sides cannot print a single product token'}) — the centred "
                "label states a fact, never an assertion")


    for n_, t_ in list(have.items()) + [("gap_top", gap_top),
                                        ("gap_side", gap_side)]:
        v_ = None if t_ is None else _numval(t_)
        if v_ is not None and v_ <= 0:
            raise TemplateError(f"{kind}: {n_} {t_!r} is not a positive "
                                "length")

    def lin(t):
        return None if t is None else _linear(t)

    def must_be_less(part, whole, pn, wn):
        """A cut/inner side must be shorter than the side it sits in,
        whenever the difference is a provable constant."""
        p, w = lin(part), lin(whole)
        if p is None or w is None:
            return
        d = _const(_lin_sub(w, p))
        if d is not None and d <= 0:
            raise TemplateError(f"{kind}: {pn} {part!r} is not shorter than "
                                f"{wn} {whole!r} — the figure would be false")

    ident_top = ident_side = False
    derived: set = set()
    if style == "corner_cut":
        must_be_less(cut_w, outer_top, "cut_w", "outer_top")
        must_be_less(cut_h, outer_side, "cut_h", "outer_side")
    if style == "corner_cut" and mode == "strips":

        for it, ot, ct, nm in ((inner_top, outer_top, cut_w, "inner_top"),
                               (inner_side, outer_side, cut_h, "inner_side")):
            i_, o_, c_ = lin(it), lin(ot), lin(ct)
            if None not in (i_, o_, c_):
                if not _lin_eq(i_, _lin_sub(o_, c_)):
                    raise TemplateError(
                        f"{kind}: {nm} {it!r} is not {ot!r} − {ct!r} — the "
                        "remaining side must be the outer side less its strip")
                derived.add(nm)
                if nm == "inner_top":
                    ident_top = True
                else:
                    ident_side = True
    if style == "frame":
        if inner_top is not None:
            must_be_less(inner_top, outer_top, "inner_top", "outer_top")
        if inner_side is not None:
            must_be_less(inner_side, outer_side, "inner_side", "outer_side")

        for gt, ot, it, nm in ((gap_top, outer_side, inner_side, "gap_top"),
                               (gap_side, outer_top, inner_top, "gap_side")):
            if gt is None or it is None:
                continue
            g_, o_, i_ = lin(gt), lin(ot), lin(it)
            if None in (g_, o_, i_):
                raise TemplateError(
                    f"{kind}: {nm} {gt!r} cannot be verified against "
                    f"{ot!r} − {it!r} — a printed band width must be provable")
            if not _lin_eq(g_, _lin_sub(o_, i_)):
                raise TemplateError(
                    f"{kind}: {nm} {gt!r} is not {ot!r} − {it!r} — the band "
                    "width would contradict the two rectangles")
            derived.add(nm)
    if area is not None:
        derived.add("area")

    _stem_check(vt, values, stem, derived=derived,
                **{k: v for k, v in have.items() if v is not None},
                **({"area": area} if area else {}),
                **({"gap_top": gap_top} if gap_top else {}),
                **({"gap_side": gap_side} if gap_side else {}))

    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    if values == "figure":
        add('describe "the printed numbers are figure content — the '
            'student reads them off the figure"', "inferred",
            "read-the-figure mode")

    fs = 18.0
    clear = vt._clearance_units(vt.STROKE_PX + vt.SLACK_STROKE + 1.0,
                                W + 140.0)

    def lab_w(t):
        return vt._label_width(vt.math_visible(t).strip() or "0", fs)

    def side_labels(w_tok, h_tok, x0, y0, x1, y1, pfx):
        if w_tok:
            elements.append(vc.math_label(
                ((x0 + x1) / 2, y0 - fs * vt.MID_UP - clear), w_tok,
                id=f"{pfx}w"))
        if h_tok:
            hw = lab_w(h_tok) / 2
            if hw > 10.0:

                el = vc.math_label((x0 - hw - 15.0, (y0 + y1) / 2), h_tok,
                                   id=f"{pfx}h")
                el["rotation"] = -90
                elements.append(el)
            else:
                elements.append(vc.math_label(
                    (x0 - hw - clear - 6.0, (y0 + y1) / 2), h_tok,
                    id=f"{pfx}h"))

    if style == "rectangle":
        A, B, C, D = (0.0, 0.0), (W, 0.0), (W, H), (0.0, H)
        P = dict(zip("ABCD", (A, B, C, D)))
        elements.append(vc.polygon([A, B, C, D], id="frame"))
        side_labels(top, side, 0.0, 0.0, W, H, "m")
        if area:

            elements.append(vc.math_label(
                (W / 2, H - clear - fs * vt.MID_DOWN - 2.0), area, id="mz"))
        if right_marks:
            elements += vc.right_angle_mark(C, B, D, r=12)
        add(f'describe "the {"square" if square else "rectangle"} has top '
            f'{vt.math_visible(top).strip()} and side '
            f'{vt.math_visible(side).strip()}"', "inferred",
            "the two side labels")
        for i, nm in enumerate("ABCD"):
            add(f"right {'ABCD'[i - 1]} {nm} {'ABCD'[(i + 1) % 4]}", "inferred",
                "a rectangle's corner")
        if area:
            add(f'describe "the centre label '
                f'{vt.math_visible(area).strip()} is the product '
                f'{vt.math_visible(top).strip()} x '
                f'{vt.math_visible(side).strip()}"', "inferred",
                "the area label is the product of the sides")
        add("derive 360 / 90 = 4", "inferred",
            "four right corners — the rectangle's own count")
        add("none tickMark parallelMark angleMark arrow dashed shaded",
            "inferred", "one outline plus KaTeX labels only")
        return vt.finish(
            kind=kind, figure_id=figure_id, stem=stem, elements=elements,
            anchors=dict(P), points=list(P),
            segments=["AB", "BC", "CD", "DA"], claims=claims, ask=ask,
            title=title or ("A square with symbolic sides" if square else
                            "A rectangle with symbolic sides"),
            description=description or (
                "A single " + ("square" if square else "rectangle") +
                " whose sides are labelled with algebraic tokens" +
                ("; the area product is written inside." if area else ".")),
            scale="symbolic — the drawn size does not encode the labels' "
                  "values", medium=medium)

    if style == "corner_cut":
        cw, ch = frac * W, frac * H
        scale = "symbolic — the cut fraction does not encode the labels' values"
        if scale_at_x is not None:
            x = _num(kind, "scale_at_x", scale_at_x)
            forms = [lin(t) for t in (outer_top, outer_side, cut_w, cut_h)]
            if not x > 0 or any(f is None or f.keys() - {"", "x"} for f in forms):
                raise TemplateError(f"{kind}: scale_at_x needs positive x and linear lengths in x")
            ow, oh, sw, sh = [f.get("", 0) + x * f.get("x", 0) for f in forms]
            if not (0 < sw < ow and 0 < sh < oh):
                raise TemplateError(f"{kind}: scale_at_x must give positive cuts inside the outer rectangle")
            units = W / ow
            H, cw, ch = oh * units, sw * units, sh * units
            if not 60 <= H <= 400:
                raise TemplateError(f"{kind}: scaled height {H:g} outside 60-400 units; adjust W")
            scale = f"to scale at x = {Decimal(str(x)):f} — one scale for all four lengths"
        x0, y0, x1, y1 = _CORNERS[corner](W, H, cw, ch)
        A, B, C, D = (0.0, 0.0), (W, 0.0), (W, H), (0.0, H)
        P = dict(zip("ABCD", (A, B, C, D)))
        if mode == "corner":
            lp = _l_polygon(W, H, x0, y0, x1, y1)
            elements.append(vc.polygon(
                lp, fill=vc.SHADE if shaded else None, id="rem"))

            elements.append(vc.polygon(
                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], id="cut"))
            elements[-1]["stroke"] = {"style": "dashed"}
            elements[-1].pop("fill", None)
            side_labels(outer_top, outer_side, 0.0, 0.0, W, H, "mo")

            if x1 == W:
                elements.append(vc.math_label(
                    ((x0 + x1) / 2, y1 + fs * vt.MID_UP + clear), cut_w,
                    id="mcw"))
            else:
                elements.append(vc.math_label(
                    ((x0 + x1) / 2, y0 - fs * vt.MID_UP - clear), cut_w,
                    id="mcw"))
            hw = lab_w(cut_h) / 2
            if y1 == H:
                elements.append(vc.math_label(
                    (x0 - hw - clear, (y0 + y1) / 2), cut_h, id="mch"))
            else:
                elements.append(vc.math_label(
                    (x1 + hw + clear, (y0 + y1) / 2), cut_h, id="mch"))
            add(f'describe "the outer rectangle is '
                f'{vt.math_visible(outer_top).strip()} by '
                f'{vt.math_visible(outer_side).strip()}"', "inferred",
                "the outer side labels")
            add(f'describe "the dashed corner cut is '
                f'{vt.math_visible(cut_w).strip()} by '
                f'{vt.math_visible(cut_h).strip()} at corner {corner}"',
                "inferred", "the removed rectangle")

            gone = {"tr": "B", "tl": "A", "br": "C", "bl": "D"}[corner]
            whole_sides = {"tr": ["CD", "DA"], "tl": ["BC", "CD"],
                           "br": ["AB", "DA"], "bl": ["AB", "BC"]}[corner]
            for i, nm in enumerate("ABCD"):
                if nm != gone:
                    add(f"right {'ABCD'[i - 1]} {nm} {'ABCD'[(i + 1) % 4]}",
                        "inferred", "a surviving outer corner")
            add(f'describe "the {"shaded " if shaded else ""}L is the outer '
                f'{vt.math_visible(outer_top).strip()} x '
                f'{vt.math_visible(outer_side).strip()} rectangle less the '
                f'{vt.math_visible(cut_w).strip()} x '
                f'{vt.math_visible(cut_h).strip()} corner"', "inferred",
                "the L-shape is the outer rectangle less the corner "
                "rectangle — a difference, not a dissection")
            add("derive 360 / 90 = 4", "inferred",
                "the outer rectangle's four right corners")
            if scale_at_x is not None:
                width_segment = next(s for s in whole_sides if s in ("AB", "CD"))
                height_segment = next(s for s in whole_sides if s in ("BC", "DA"))
                if width_segment == "CD":
                    next(el for el in elements if el["id"] == "mow")["at"] = (
                        W / 2, H + fs * vt.MID_UP + clear)
                if height_segment == "BC":
                    label = next(el for el in elements if el["id"] == "moh")
                    label["at"] = (W - label["at"][0], H / 2)
                sx = x0 if y1 == H else x1
                sy = y1 if x1 == W else y0
                P.update(E=(sx, sy), F=(x1 if sx == x0 else x0, sy),
                         G=(sx, y1 if sy == y0 else y0))
                for segment, token in ((width_segment, outer_top), (height_segment, outer_side),
                                       ("EF", cut_w), ("EG", cut_h)):
                    add(f"scale-length {segment} = {_norm(token)}", "inferred",
                        "printed length at the common substitution")
                    if segment not in whole_sides:
                        whole_sides.append(segment)
            add("none tickMark parallelMark angleMark arrow"
                + ("" if shaded else " shaded"), "inferred",
                "one " + ("shaded" if shaded else "unshaded")
                + " L, one dashed cut and labels only")
            return vt.finish(
                kind=kind, figure_id=figure_id, stem=stem, elements=elements,
                anchors=dict(P), points=list(P),
                segments=whole_sides, claims=claims, ask=ask,
                title=title or "A rectangle with a corner cut away",
                description=description or (
                    "A rectangle with a smaller corner rectangle dashed off; "
                    "the " + ("shaded " if shaded else "")
                    + "L-shape that remains has the outer minus the "
                    "corner area."),
                scale=scale, medium=medium)

        iw, ih = W - cw, H - ch
        elements.append(vc.polygon([A, B, C, D], id="outer"))
        elements[-1]["stroke"] = {"style": "dashed"}
        elements.append(vc.polygon([(0.0, 0.0), (iw, 0.0), (iw, ih),
                                    (0.0, ih)],
                                   fill=vc.SHADE if shaded else None,
                                   id="rem"))

        elements.append(vc.math_label(
            (W / 2, H + fs * vt.MID_UP + clear), outer_top, id="mow"))
        elements.append(vc.math_label(
            (W + lab_w(outer_side) / 2 + clear + 4.0, H / 2), outer_side,
            id="moh"))
        elements.append(vc.math_label(
            (iw / 2, -fs * vt.MID_UP - clear), inner_top, id="miw"))
        elements.append(vc.math_label(
            (iw + cw / 2, -fs * vt.MID_UP - clear), cut_w, id="mcw"))

        for t, y, i in ((inner_side, ih / 2, "mih"),
                        (cut_h, ih + ch / 2, "mch")):
            hw_ = lab_w(t) / 2
            if hw_ > 10.0:
                el = vc.math_label((-hw_ - 15.0, y), t, id=i)
                el["rotation"] = -90
            else:
                el = vc.math_label((-hw_ - clear - 6.0, y), t, id=i)
            elements.append(el)
        add(f'describe "the dashed outer rectangle is '
            f'{vt.math_visible(outer_top).strip()} by '
            f'{vt.math_visible(outer_side).strip()}"', "inferred",
            "the original rectangle")
        add(f'describe "a right strip of width '
            f'{vt.math_visible(cut_w).strip()} and a bottom strip of '
            f'height {vt.math_visible(cut_h).strip()} are cut away"',
            "inferred", "the two strips")
        mv = lambda t: vt.math_visible(t).strip()
        idents = []
        if ident_top:
            idents.append(f"{mv(inner_top)} = {mv(outer_top)} - {mv(cut_w)}")
        if ident_side:
            idents.append(f"{mv(inner_side)} = {mv(outer_side)} - "
                          f"{mv(cut_h)}")

        if len(idents) == 2:
            add(f'describe "the remaining rectangle is {mv(inner_top)} by '
                f'{mv(inner_side)}, where {idents[0]} and {idents[1]}"',
                "inferred",
                "each remaining side is the outer side less its strip — "
                "subtraction along one axis, not a Boolean dissection")
        else:
            add(f'describe "the remaining rectangle is labelled '
                f'{mv(inner_top)} by {mv(inner_side)}'
                + (", where " + idents[0] if idents else "") + '"',
                "inferred",
                "only the verified identity is stated; an unparseable "
                "inner label is printed as given" if idents else
                "the given inner labels; no identity is verifiable")
        add("derive 360 / 90 = 4", "inferred",
            "the remaining rectangle's four right corners")
        add("none tickMark parallelMark angleMark arrow"
            + ("" if shaded else " shaded"), "inferred",
            "one dashed outline, one "
            + ("solid" if shaded else "unshaded")
            + " rectangle and labels only")
        return vt.finish(
            kind=kind, figure_id=figure_id, stem=stem, elements=elements,
            anchors=dict(P), points=list(P),
            segments=["AB", "BC", "CD", "DA"], claims=claims, ask=ask,
            title=title or "A rectangle with two strips cut away",
            description=description or (
                "A dashed outer rectangle with a right strip and a bottom "
                "strip removed; the solid remaining rectangle's sides are "
                "the outer sides less the strips."),
            scale="symbolic — the strip sizes do not encode the labels' "
                  "values", medium=medium)


    gx, gy = frac * W, frac * H
    iw, ih = W - gx, H - gy

    need_band = 2 * clear + fs * (vt.MID_UP + vt.MID_DOWN)
    if (gap_top and gy < need_band) or (gap_side and gx < need_band):
        raise TemplateError(
            f"{kind}: the band is {gx:.0f}x{gy:.0f} units but its labels "
            f"need {need_band:.0f} — raise frac or drop the gap labels")
    A, B, C, D = (0.0, 0.0), (W, 0.0), (W, H), (0.0, H)
    P = dict(zip("ABCD", (A, B, C, D)))
    if shaded:

        band = [(0.0, 0.0), (W, 0.0), (W, gy), (gx, gy), (gx, H), (0.0, H)]
        elements.append(vc.polygon(band, fill=vc.SHADE, id="band"))
        elements[-1]["stroke"] = {"width": 0}
    elements.append(vc.polygon([A, B, C, D], id="outer"))

    elements.append(vc.polygon([(gx, gy), (W, gy), (W, H), (gx, H)],
                               id="inner"))
    side_labels(outer_top, outer_side, 0.0, 0.0, W, H, "mo")
    if gap_top:
        elements.append(vc.math_label(((gx + W) / 2, gy / 2), gap_top,
                                      id="mgt"))
    if gap_side:
        elements.append(vc.math_label((gx / 2, (gy + H) / 2), gap_side,
                                      id="mgs"))

    if inner_top and inner_side and gap_top:
        raise TemplateError(
            "frame: gap_top with both inner labels has no unambiguous bounded layout")
    else:
        if inner_top:
            y_t = (gy - clear - fs * vt.MID_UP if not gap_top
                   else gy + clear + fs * vt.MID_UP)
            elements.append(vc.math_label((gx + iw / 2, y_t), inner_top,
                                          id="miw"))
        if inner_side:
            hw_ = lab_w(inner_side) / 2
            el = vc.math_label((gx + hw_ + clear, gy + ih / 2), inner_side,
                               id="mih")
            if hw_ > 10.0:
                el["rotation"] = -90
            elements.append(el)
    add(f'describe "the outer rectangle is '
        f'{vt.math_visible(outer_top).strip()} by '
        f'{vt.math_visible(outer_side).strip()}"', "inferred",
        "the outer side labels")
    if inner_top and inner_side:
        add(f'describe "the inner rectangle is '
            f'{vt.math_visible(inner_top).strip()} by '
            f'{vt.math_visible(inner_side).strip()}"', "inferred",
            "the inner side labels")
    band_word = "shaded band" if shaded else "band"
    if gap_top:
        add(f'describe "the {band_word} is '
            f'{vt.math_visible(gap_top).strip()} thick at the top"',
            "inferred", "verified as outer_side - inner_side"
            if "gap_top" in derived else "the given top band width")
    if gap_side:
        add(f'describe "the {band_word} is '
            f'{vt.math_visible(gap_side).strip()} thick at the left"',
            "inferred", "verified as outer_top - inner_top"
            if "gap_side" in derived else "the given left band width")
    if inner_top and inner_side:
        add(f'describe "the {band_word} is the outer '
            f'{vt.math_visible(outer_top).strip()} x '
            f'{vt.math_visible(outer_side).strip()} rectangle less the '
            f'{vt.math_visible(inner_top).strip()} x '
            f'{vt.math_visible(inner_side).strip()} inner one"',
            "inferred",
            f"the {band_word} is the outer rectangle less the inner — a "
            "difference of two rectangles")
    add("derive 360 / 90 = 4", "inferred",
        "the outer rectangle's four right corners")
    add("none tickMark parallelMark angleMark arrow dashed"
        + ("" if shaded else " shaded"), "inferred",
        "two rectangles" + (", the shaded band" if shaded else "")
        + " and labels only")
    return vt.finish(
        kind=kind, figure_id=figure_id, stem=stem, elements=elements,
        anchors=dict(P), points=list(P),
        segments=["AB", "BC", "CD", "DA"], claims=claims, ask=ask,
        title=title or "A rectangular frame",
        description=description or (
            "An outer rectangle with a smaller rectangle set into its "
            "bottom-right corner; the band between them"
            + (" is shaded" if shaded else " is unshaded")
            + (" and its widths are labelled." if (gap_top or gap_side)
               else ".")),
        scale="symbolic — the inset does not encode the labels' values",
        medium=medium)


def build_mapping_arrows(*, figure_id, stem, left, right, ask=None,
                         title=None, description=None, medium="english",
                         values="stem", heads=None, row_gap=44.0,
                         col_gap=170.0):
    """The L10 proportion arrow-mapping: left[i] -> right[i], i = 0..n-1.

    `left`/`right` are equal-length lists of 1-4 tokens — numerals or
    short latex (an unknown like `x`). `heads` is an optional pair of
    short latex tokens printed above the columns (e.g. 'n', 'Rs') —
    math labels, never prose (ADR 0021). Arrows are parallel rightward;
    crossing or backward mappings are refused. `values="stem"` runs
    require_stem over every purely-numeric token on BOTH columns;
    "figure" declares them read-off content."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind = "mapping_arrows"
    vc.reset_ids()
    medium = _common(kind, stem, medium)
    values = str(values).strip().lower()
    if values not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure'")
    for nm, seq in (("left", left), ("right", right)):
        if not isinstance(seq, (list, tuple)) or not 1 <= len(seq) <= 4:
            raise TemplateError(f"{kind}: {nm} must be a list of 1-4 tokens")
    if len(left) != len(right):
        raise TemplateError(f"{kind}: left and right must have the same "
                            "length — every row maps one left token to one "
                            "right token")
    left = [_tok(kind, f"left[{i}]", t, 10) for i, t in enumerate(left)]
    right = [_tok(kind, f"right[{i}]", t, 10) for i, t in enumerate(right)]
    if heads is not None:
        if not isinstance(heads, (list, tuple)) or len(heads) != 2:
            raise TemplateError(f"{kind}: heads must be a pair of tokens")
        heads = tuple(_tok(kind, f"heads[{i}]", h, 10)
                      for i, h in enumerate(heads))
    row_gap = _num(kind, "row_gap", row_gap)
    col_gap = _num(kind, "col_gap", col_gap)
    if not 28.0 <= row_gap <= 90.0 or not 90.0 <= col_gap <= 300.0:
        raise TemplateError(f"{kind}: row_gap/col_gap "
                            f"{row_gap}/{col_gap} outside 28-90/90-300")
    _stem_check(vt, values, stem,
                **{f"left[{i}]": t for i, t in enumerate(left)},
                **{f"right[{i}]": t for i, t in enumerate(right)},
                **({f"heads[{i}]": h for i, h in enumerate(heads)}
                   if heads else {}))


    for side_nm, seq in (("left", left), ("right", right)):
        keys = [_numval(t) if _numval(t) is not None else _norm(t)
                for t in seq]
        if len(set(keys)) != len(keys):
            raise TemplateError(
                f"{kind}: {side_nm} repeats a token {list(seq)} — a direct "
                "proportion maps each value once (duplicate or contradiction)")
    pairs = []
    for l_tok, r_tok in zip(left, right):
        lv, rv = _numval(l_tok), _numval(r_tok)
        if lv is not None and rv is not None:
            if (lv == 0) != (rv == 0):
                raise TemplateError(
                    f"{kind}: {l_tok}→{r_tok} — in a direct proportion 0 "
                    "maps only to 0")
            if lv != 0:
                pairs.append((l_tok, r_tok, rv / lv))
    if len(pairs) >= 2:
        k0 = pairs[0][2]
        bad = [(l, r) for l, r, k in pairs[1:]
               if abs(k - k0) > 1e-9 * max(1.0, abs(k0))]
        if bad:
            raise TemplateError(
                f"{kind}: {bad} do not share the unit rate {k0:g} of "
                f"{pairs[0][0]}→{pairs[0][1]} — not a direct proportion")

    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    n = len(left)
    fs = 18.0
    clear = vt._clearance_units(vt.STROKE_PX + vt.SLACK_STROKE + 1.0,
                                float(col_gap) + 140.0)
    lw = max(vt._label_width(vt.math_visible(t).strip() or "0", fs)
             for t in left)
    rw = max(vt._label_width(vt.math_visible(t).strip() or "0", fs)
             for t in right)
    for i in range(n):
        y = i * float(row_gap)
        elements.append(vc.math_label((0.0, y), left[i], id=f"ml{i}"))
        elements.append(vc.math_label((float(col_gap), y), right[i],
                                      id=f"mr{i}"))
        a0 = (lw / 2 + clear, y)
        a1 = (float(col_gap) - rw / 2 - clear, y)
        if a1[0] <= a0[0]:
            raise TemplateError(
                f"{kind}: the columns overlap — widen col_gap "
                f"({col_gap:g}) for tokens {left[i]!r}->{right[i]!r}")
        elements.append(vc.arrow(a0, a1, id=f"ar{i}", width=1.5))
        add(f'describe "{vt.math_visible(left[i]).strip()} maps to '
            f'{vt.math_visible(right[i]).strip()}"', "inferred",
            f"row {i + 1}: a rightward arrow")
    if heads:
        hy = -fs * vt.MID_UP - 14.0
        elements.append(vc.math_label((0.0, hy), heads[0], id="hl"))
        elements.append(vc.math_label((float(col_gap), hy), heads[1],
                                      id="hr"))
        add(f'describe "the columns are headed '
            f'{vt.math_visible(heads[0]).strip()} and '
            f'{vt.math_visible(heads[1]).strip()}"', "inferred",
            "the column headings")

    if pairs:

        for l_tok, r_tok, k in pairs:
            add(f"derive {_numval(r_tok):g} / {_numval(l_tok):g} = {k:g}",
                "inferred",
                "the unit rate of the known pair — the proportion's constant"
                if len(pairs) == 1 else
                "this pair's unit rate — verified equal across every "
                "numeric pair")
    elif n >= 2:
        add("derive " + " + ".join("1" for _ in range(n)) + f" = {n}",
            "inferred", "the count of mapped pairs")
    else:
        add("derive 2 / 2 = 1", "inferred", "a single mapped pair")
    if values == "figure":
        add('describe "the numbers are figure content — the student reads '
            'them off the mapping"', "inferred", "read-the-figure mode")
    add("none tickMark parallelMark angleMark dashed shaded", "inferred",
        "two columns and parallel arrows only")
    return vt.finish(
        kind=kind, figure_id=figure_id, stem=stem, elements=elements,
        anchors={}, points=[], segments=[], claims=claims, ask=ask,
        title=title or "A proportion arrow mapping",
        description=description or (
            f"Two columns of {n} entr{'ies' if n != 1 else 'y'} under "
            "short headings; each left entry is joined by a rightward "
            "arrow to its right entry — a direct-proportion mapping."),
        scale="column spacing is a canvas choice — only the tokens and "
              "the pairing matter",
        budget=len(elements) if len(elements) > 32 else None,
        medium=medium)
