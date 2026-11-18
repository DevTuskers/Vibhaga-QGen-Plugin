"""vdd_g9_binary.py — the G9 L02 (Number Base Two) place-value frame.

One bounded builder, `build_place_value_frame`, covering the lesson's two
figure shapes the abacus cannot print honestly (the inventory's confirmed
`exponent-rod-labels` residual — wt/g9-readiness/inventory.md):

  • rods:   a spike frame whose rods are headed by POWER-FORM labels `bᵉ`
            (plain <text> with Unicode superscripts — the plain abacus only
            prints `8 4 2 1`, and a KaTeX × <text> mix fails visual-check's
            font rule), each rod carrying `digit` beads; an optional value
            numeral `b**e` prints under the base bar.
  • digits: a row of digits with one downward arrow per digit onto its
            power header — the lesson's digit-to-place mapping figure.

The place values are COMPUTED (`base**exp`), never passed in; in
`values="stem"` mode the represented total and the base must be numbers the
stem states. Everything else — division ladders, column arithmetic with
carries, multi-frame A+B→C compositions — stays on the honest Markdown/KaTeX
route (inventory "Non-diagram types") and is refused, not approximated.

This module is NOT registered in vdd_templates.TEMPLATES — the lead actor owns
that file; registration is a one-line lazy entry there. vdd_templates itself is
imported lazily inside the builder so this module stays import-light.
"""
from __future__ import annotations

import math
import inspect
from functools import wraps

import vdd_cookbook as vc


def _num(kind: str, name: str, v):
    """The numeric gate EVERY spec value passes before any arithmetic — bools,
    strings and non-finite numbers are refused before int/finite conversion."""
    from vdd_templates import TemplateError
    if (isinstance(v, bool) or not isinstance(v, (int, float))
            or abs(v) > 10**100 or not math.isfinite(v)):
        raise TemplateError(f"{kind}: {name} must be a bounded finite number")
    return v


_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _power_glyph(base: int, exp: int) -> str:
    """The drawn header: '2³' — a plain <text> with Unicode superscripts so the
    figure sets ONE font (visual-check's font rule fails a KaTeX × <text> mix)."""
    return f"{base}{str(exp).translate(_SUP)}"


def _spec_contract(builder):
    signature = inspect.signature(builder)

    @wraps(builder)
    def checked(*args, **kwargs):
        from vdd_templates import TemplateError
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as exc:
            raise TemplateError(f"{builder.__name__}: malformed spec: {exc}") from exc
        bound.apply_defaults()
        for key in ("figure_id", "stem"):
            if not isinstance(bound.arguments.get(key), str):
                raise TemplateError(f"{builder.__name__}: {key} must be text")
        for key in ("title", "description", "values"):
            value = bound.arguments.get(key)
            if value is not None and not isinstance(value, str):
                raise TemplateError(f"{builder.__name__}: {key} must be text")
        medium = bound.arguments.get("medium")
        if not isinstance(medium, str) \
                or medium.strip().lower() not in ("english", "sinhala"):
            raise TemplateError(f"{builder.__name__}: medium must be "
                                "'english' or 'sinhala'")
        ask = bound.arguments.get("ask")
        if ask is not None and (
            not isinstance(ask, (list, tuple)) or not ask
            or any(not isinstance(part, (list, tuple)) or len(part) != 2
                   or not all(isinstance(item, str) for item in part) for part in ask)
        ):
            raise TemplateError(f"{builder.__name__}: ask must list pairs of text")
        return builder(*args, **kwargs)

    return checked


@_spec_contract
def build_place_value_frame(*, figure_id, stem, base, digits, ask=None,
                            title=None, description=None, medium="english",
                            values="stem", style="digits", arrows=None,
                            show_value=True, bead_r=7.5):
    """A place-value frame for one number in `base` (2–10).

    `digits` lists the digits left→right, most significant first — 1–8 entries,
    each an int in [0, base), the first non-zero unless it is the only digit.

    `style="digits"` draws the digit row with an arrow per digit down to its
    power header (`arrows` defaults True here; pass False for a bare
    digit+header grid). `style="rods"` draws the bead frame — a base bar, one
    rod per column carrying `digit` beads, the power header above the rod —
    and `arrows` is refused. `show_value` adds the computed value numeral
    `b**e` under each column (plain text with a `label` claim, like the
    abacus's rod values).

    `values="stem"` requires `base` and the represented total in the stem;
    `values="figure"` declares the digits figure content (read-off mode).
    Column arithmetic, carries, division ladders and multi-frame sums are out
    of scope — TemplateError, use KaTeX in the stem."""
    import vdd_templates as vt
    TemplateError = vt.TemplateError

    kind = "place_value_frame"
    if arrows is not None and type(arrows) is not bool:
        raise TemplateError(f"{kind}: arrows must be bool or None")
    if type(show_value) is not bool:
        raise TemplateError(f"{kind}: show_value must be bool")
    vc.reset_ids()
    base = _num(kind, "base", base)
    if not float(base).is_integer():
        raise TemplateError(f"{kind}: base {base:g} is not an integer")
    base = int(base)
    if not 2 <= base <= 10:
        raise TemplateError(f"{kind}: base {base} is outside 2–10 — a rod frame "
                            "holds at most base−1 = 9 beads")
    if not isinstance(digits, (list, tuple)) or not 1 <= len(digits) <= 8:
        raise TemplateError(f"{kind}: digits must be a list of 1–8 entries")
    digits = [_num(kind, f"digit {i + 1}", d) for i, d in enumerate(digits)]
    if not all(float(d).is_integer() for d in digits):
        raise TemplateError(f"{kind}: every digit must be a whole number")
    digits = [int(d) for d in digits]
    for i, d in enumerate(digits):
        if not 0 <= d < base:
            raise TemplateError(f"{kind}: digit {i + 1} is {d} — a base-{base} "
                                f"column holds only 0–{base - 1} (the frame never "
                                "carries into the next place)")
    if len(digits) > 1 and digits[0] == 0:
        raise TemplateError(f"{kind}: a leading 0 digit draws a dead column — "
                            "drop it or the figure misstates the number")
    values = str(values).strip().lower()
    if values not in ("stem", "figure"):
        raise TemplateError(f"{kind}: values must be 'stem' or 'figure' — got {values!r}")
    if style not in ("digits", "rods"):
        raise TemplateError(f"{kind}: style must be 'digits' or 'rods' — got {style!r}")
    if style == "rods" and arrows:
        raise TemplateError(f"{kind}: arrows belong to the digit-to-place mapping — "
                            "a rod frame's rods do the mapping already")
    if arrows is None:
        arrows = style == "digits"
    bead_r = _num(kind, "bead_r", bead_r)
    if not 4.0 <= bead_r <= 12.0:
        raise TemplateError(f"{kind}: bead_r {bead_r:g} is outside 4–12 units")

    n = len(digits)
    exps = [n - 1 - i for i in range(n)]
    places = [base ** e for e in exps]
    total = sum(d * v for d, v in zip(digits, places))
    if values == "stem":
        vt.require_stem(stem, base=base, total=total)

    lab_size = 15.0
    head_size = 15.0
    dig_size = 19.0
    max_lab = max(
        [vt._label_width(f"{v:g}", lab_size) for v in places]
        + [vt._label_width(
            _power_glyph(base, e)
            + (f" = {p:g}" if style == "digits" and show_value else ""),
            head_size) for e, p in zip(exps, places)]
        + [dig_size * 0.62])

    spacing = 64.0
    for _ in range(4):
        span = (n - 1) * spacing + max(52.0, max_lab)
        new = max(64.0, max_lab + vt._clearance_units(4.0 + 1.0, span))
        if abs(new - spacing) < 0.5:
            break
        spacing = new
    xs = [i * spacing for i in range(n)]

    elements: list[dict] = []
    claims: list[tuple[str, str, str]] = []

    def add(pred, ev, note=""):
        claims.append((pred, ev, note))
        return f"K{len(claims)}"

    if style == "rods":
        rod_h = (base - 1) * (2 * bead_r + 3.0) + 24.0
        base_y = rod_h
        bar_half = max(26.0, (rod_h + 60.0) / 4.0 - (xs[-1] - xs[0]) / 2.0)
        head_y = base_y - rod_h + 12.0 - head_size - 10.0
        elements.append(vc.line((xs[0] - bar_half, base_y),
                                (xs[-1] + bar_half, base_y), id="base", width=3.0))
        val_y = base_y + 1.5 + vt._clearance_units(
            vt.STROKE_PX + vt.SLACK_STROKE + 1.0, span) + lab_size * vt.MID_UP
        for i, x in enumerate(xs):
            elements.append(vc.line((x, base_y), (x, base_y - rod_h + 12.0),
                                    id=f"rod{i + 1}", width=2.0))
            for j in range(digits[i]):
                elements.append(vc.circle(
                    (x, base_y - 10.0 - bead_r - j * (2 * bead_r + 3.0)),
                    bead_r, fill=vc.INK, id=f"b{i + 1}_{j + 1}"))
            elements.append(vc.text((x, head_y), _power_glyph(base, exps[i]),
                                    id=f"hv{i + 1}", size=head_size))
            if show_value:
                elements.append(vc.text((x, val_y), f"{places[i]:g}",
                                        id=f"lv{i + 1}", size=lab_size))
    else:
        dig_y = 0.0

        clear = vt._clearance_units(vt.STROKE_PX + vt.SLACK_STROKE + 2.5, span)
        ar_top = dig_y + dig_size * vt.MID_DOWN + clear
        head_y = ar_top + 34.0 + head_size * vt.MID_UP
        for i, x in enumerate(xs):
            elements.append(vc.text((x, dig_y), f"{digits[i]:g}",
                                    id=f"d{i + 1}", size=dig_size))
            if arrows:
                elements.append(vc.arrow((x, ar_top),
                                         (x, head_y - head_size * vt.MID_UP - clear),
                                         id=f"ar{i + 1}", width=1.5))

            elements.append(vc.text(
                (x, head_y),
                _power_glyph(base, exps[i])
                + (f" = {places[i]:g}" if show_value else ""),
                id=f"hv{i + 1}", size=head_size))


    bound: set[str] = set()
    for i in range(n):
        glyph = _power_glyph(base, exps[i])
        printed = glyph + (f" = {places[i]:g}"
                           if style == "digits" and show_value else "")
        add(f'label "{printed}" names hv{i + 1}', "inferred",
            "the column's power header" +
            (" and its value" if printed != glyph else ""))
        bound.add(printed)
        if style == "rods":
            add(f'describe "rod {i + 1} is headed {glyph} and carries '
                f'{digits[i]:g} bead{"s" if digits[i] != 1 else ""}"', "inferred",
                "the power header and the bead count")
        else:
            if f"{digits[i]:g}" not in bound:
                add(f'label "{digits[i]:g}" names d{i + 1}', "inferred",
                    "a digit of the number shown")
                bound.add(f"{digits[i]:g}")
            add(f'describe "digit {digits[i]:g} of column {i + 1} maps to {glyph}"',
                "inferred",
                "the digit, its arrow and the power header it lands on")

        if style == "rods" and show_value and f"{places[i]:g}" not in bound:
            add(f'label "{places[i]:g}" names col{i + 1}', "inferred",
                "the column's place value")
            bound.add(f"{places[i]:g}")
        add(f"derive {digits[i]:g} * {places[i]:g} = {digits[i] * places[i]:g}",
            "inferred", "digit times place value")
    add("derive " + " + ".join(f"{d:g} * {v:g}" for d, v in zip(digits, places))
        + f" = {total:g}", "inferred",
        "digits times place values, summed — the number the frame shows")
    if values == "figure":
        add('describe "the digits are figure content — the student reads them '
            'off the frame"', "inferred", "values='figure' read-off mode")
    add("none tickMark parallelMark angleMark"
        + ("" if arrows else " arrow") + " dashed shaded", "inferred",
        "columns, headers and beads only")

    if style == "rods":
        title_d = title or "A place-value frame showing a number"
        desc_d = description or (
            f"An abacus-style frame of {n} rods on a base bar; each rod is "
            f"headed by a power of {base} and carries beads for its digit."
            + (" A value numeral sits under each rod." if show_value else ""))
        scale = "bead size and rod spacing are a canvas choice — only the " \
                "counts and headers matter"
    else:
        title_d = title or "Digits mapped to their place values"
        desc_d = description or (
            f"A row of {n} digits of a base-{base} number"
            + (", each with an arrow down to" if arrows else " above")
            + f" its power header{'; the place value prints below.' if show_value else '.'}")
        scale = "column spacing is a canvas choice — only the digits and " \
                "headers matter"
    return vt.finish(kind=kind, figure_id=figure_id, stem=stem,
                     elements=elements, anchors={}, points=[], segments=[],
                     claims=claims, ask=ask,
                     title=title_d, description=desc_d, scale=scale,
                     budget=len(elements) if len(elements) > 32 else None,
                     medium=medium)
