import math


def build_calculator_square(*, figure_id, stem, operand, ask=None, title=None,
                            description=None, medium="english"):
    import vdd_templates as vt

    operand = _number(operand, "operand", 0, 999)
    if operand != int(operand):
        raise vt.TemplateError("calculator_square: whole operands only")
    return build_calculator_keys(figure_id=figure_id, stem=stem,
                                 keys=["ON", operand, "x²", "="], ask=ask,
                                 title=title, description=description, medium=medium)


def build_calculator_keys(*, figure_id, stem, keys, result=None, evaluation="scientific",
                          values="stem", ask=None, title=None, description=None,
                          medium="english"):
    import vdd_templates as vt
    import vdd_cookbook as vc

    if evaluation not in ("scientific", "immediate"):
        raise vt.TemplateError("calculator_keys: evaluation must be scientific or immediate")
    if values not in ("stem", "figure"):
        raise vt.TemplateError("calculator_keys: values must be stem or figure")
    if not isinstance(keys, (list, tuple)) or not 3 <= len(keys) <= 24:
        raise vt.TemplateError("calculator_keys: 3..24 semantic input tokens required")
    if keys[0] not in ("ON", "AC") or keys[-1] != "=":
        raise vt.TemplateError("calculator_keys: begin with ON/AC and end with equals")
    allowed = {"+", "−", "-", "×", "÷", "x²", "√", "(", ")", "%", "SHIFT", "="}
    basic = {"+", "−", "-", "×", "÷"}
    tokens, faces, operands = [], [keys[0]], []
    pos = 1
    while pos < len(keys) - 1:
        key = keys[pos]
        if isinstance(key, (int, float)) and not isinstance(key, bool):
            value = _number(key, "operand", 0, 1000000)
            text = f"{value:.6f}".rstrip("0").rstrip(".") if value else "0"
            if float(text) != value:
                raise vt.TemplateError("calculator_keys: at most six decimal places")
            if values == "stem":
                vt.require_stem(stem, operand=value)
            operands.append(value)
            tokens.append(value)
            faces.extend(text)
        elif isinstance(key, str) and key in allowed:
            if evaluation == "immediate" and key not in basic:
                raise vt.TemplateError("calculator_keys: an immediate calculator has digits and + - × ÷ only")
            if key == "SHIFT":
                if pos + 1 >= len(keys) - 1 or keys[pos + 1] != "=":
                    raise vt.TemplateError("calculator_keys: SHIFT only activates percent on equals")
                tokens.append("%")
                faces.extend(["SHIFT", "=%"])
                pos += 1
            elif key == "=":
                raise vt.TemplateError("calculator_keys: intermediate equals requires SHIFT")
            else:
                tokens.append("−" if key == "-" else key)
                faces.append("−" if key == "-" else key)
        else:
            raise vt.TemplateError("calculator_keys: numeric operands must be numbers; unsupported key")
        pos += 1
    faces.append("=")
    if not operands or not 4 <= len(faces) <= 24:
        raise vt.TemplateError("calculator_keys: 4..24 drawn key faces required")
    for i, token in enumerate(tokens):
        if token == "%":
            if i < 2 or not isinstance(tokens[i - 1], float) or tokens[i - 2] not in ("×", "÷"):
                raise vt.TemplateError(
                    "calculator_keys: percent applies only to a plain right operand of × or ÷")
    if not any(token in ("+", "−", "×", "÷", "x²", "√") for token in tokens):
        raise vt.TemplateError("calculator_keys: the sequence must compute something")
    claims = []
    cursor = 0

    def bounded(value):
        if not math.isfinite(value) or abs(value) > 1e12:
            raise vt.TemplateError("calculator_keys: intermediate outside finite result bounds")
        return value

    def record(left, operator, right, value):
        value = bounded(value)
        claims.append((f"derive ({left:.12f}) {operator} ({right:.12f}) = {value:.12f}",
                       "inferred", "computed key sequence arithmetic"))
        return value

    def atom(depth=0):
        nonlocal cursor
        if depth > 4 or cursor >= len(tokens):
            raise vt.TemplateError("calculator_keys: incomplete expression or nesting exceeds four")
        token = tokens[cursor]
        cursor += 1
        if isinstance(token, float):
            value = token
        elif token == "(":
            value = expression(depth + 1)
            if cursor >= len(tokens) or tokens[cursor] != ")":
                raise vt.TemplateError("calculator_keys: unmatched bracket")
            cursor += 1
        elif token == "√":
            value = atom(depth + 1)
            if value < 0:
                raise vt.TemplateError("calculator_keys: negative square-root operand")
            root = bounded(math.sqrt(value))
            claims.append((f'describe "square root of {value:.12f} is {root:.12f}"',
                           "inferred", "computed with math.sqrt; root arithmetic is not a derive predicate"))
            record(root, "*", root, value)
            value = root
        else:
            raise vt.TemplateError("calculator_keys: expected operand, root, or opening bracket")
        while cursor < len(tokens) and tokens[cursor] in ("x²", "%"):
            postfix = tokens[cursor]
            cursor += 1
            if postfix == "x²":
                value = record(value, "*", value, value * value)
            else:
                value = record(value, "/", 100, value / 100)
        return value

    def combine(left, operator, right):
        if operator == "+":
            return record(left, "+", right, left + right)
        if operator == "−":
            return record(left, "-", right, left - right)
        if operator == "×":
            return record(left, "*", right, left * right)
        if right == 0:
            raise vt.TemplateError("calculator_keys: division by zero")
        return record(left, "/", right, left / right)

    def expression(depth=0, minimum=0):
        nonlocal cursor
        left = atom(depth)
        while cursor < len(tokens) and tokens[cursor] in ("+", "−", "×", "÷"):
            operator = tokens[cursor]
            precedence = 1 if evaluation == "immediate" or operator in ("+", "−") else 2
            if precedence < minimum:
                break
            cursor += 1
            right = expression(depth, precedence + 1)
            left = combine(left, operator, right)
        return left

    answer = expression()
    if cursor != len(tokens):
        raise vt.TemplateError("calculator_keys: unused token or unmatched closing bracket")
    if result is not None:
        result = _number(result, "result", -1e12, 1e12)
        if not math.isclose(result, answer, rel_tol=1e-10, abs_tol=1e-10):
            raise vt.TemplateError("calculator_keys: supplied result disagrees with computed sequence")
    if values == "figure":
        claims.append(('describe "the operand digit keys are figure content; the question asks the student to read them from the figure"',
                       "inferred", "read-the-figure mode"))
    vc.reset_ids()
    elements = []
    seats = []
    for i, face in enumerate(faces):
        row, column = divmod(i, 4)
        x = (column if row % 2 == 0 else 3 - column) * 116
        y = row * 116
        seats.append((x, y))
        elements += [vc.polygon([(x - 43, y - 36), (x + 43, y - 36),
                                 (x + 43, y + 36), (x - 43, y + 36)], id=f"region_key{i}"),
                     vc.text((x, y), face, size=16)]
        if i:
            px, py = seats[i - 1]
            if py == y:
                direction = 1 if x > px else -1
                a, b = (px + direction * 48, y), (x - direction * 48, y)
            else:
                a, b = (x, py + 42), (x, y - 42)
            elements.append(vc.arrow(a, b, id=f"next{i}"))
        claims.append((f'describe "key position {i + 1} is {face}"', "inferred", "follow connecting arrows"))
    seen_faces = {}
    for i, face in enumerate(faces):
        if face not in seen_faces:
            seen_faces[face] = i
            claims.append((f'label "{face}" names region_key{i}', "inferred", "key face"))
    if result is not None:
        x, y = seats[-1]
        text = f"{answer:.6f}".rstrip("0").rstrip(".") if answer else "0"
        if not math.isclose(float(text), answer, rel_tol=0, abs_tol=1e-10):
            raise vt.TemplateError("calculator_keys: shown result must be exact to six decimal places")
        if len(text) > 14:
            raise vt.TemplateError("calculator_keys: result display exceeds fourteen characters")
        elements += [vc.polygon([(54, y + 64), (294, y + 64), (294, y + 128), (54, y + 128)], id="region_display"),
                     vc.text((174, y + 96), text, size=18)]
        if text not in faces:
            claims.append((f'label "{text}" names region_display', "inferred", "computed final display, not an independent given"))
        claims.append((f'describe "the separate final display contains {text}"', "inferred", "computed result"))
    claims += [(f'describe "evaluation convention is {evaluation}; SHIFT followed by equals activates postfix percent; follow arrows across alternating rows"',
                "inferred", "explicit bounded calculator convention, not arbitrary hardware semantics"),
               ("none tickMark parallelMark angleMark angleArc dashed shaded", "inferred", "key flow only")]
    return vt.finish(kind="calculator_keys", figure_id=figure_id, stem=stem,
                     elements=elements, anchors={}, points=[], segments=[], claims=claims,
                     ask=ask, title=title or "Calculator key sequence",
                     description=description or "Boxed calculator keys connected by arrows across alternating rows; begin at the top left.",
                     scale="symbolic keypress flow, not a hardware interface", medium=medium,
                     budget=len(elements) if len(elements) > 32 else None,
                     departures=["wrapped key flow uses one card per keypress"] if len(elements) > 32 else None)


def _number(value, name, low, high):
    import vdd_templates as vt

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise vt.TemplateError(f"{name}: finite numeric input required")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise vt.TemplateError(f"{name}: finite numeric input required") from None
    if not math.isfinite(result) or not low <= result <= high:
        raise vt.TemplateError(f"{name}: outside finite bounded range")
    return result


def build_graduated_vessel(*, figure_id, stem, capacity, step, reading,
                           values="stem", unit="ml", ask=None, title=None, description=None,
                           medium="english"):
    import vdd_templates as vt
    import vdd_cookbook as vc

    ex = vt._num_exact
    capacity = _number(capacity, "capacity", 0.001, 10000)
    step = _number(step, "step", 0.001, 10000)
    reading = _number(reading, "reading", 0, capacity)
    if unit not in ("ml", "cm³", "l"):
        raise vt.TemplateError("graduated_vessel: unit must be ml, cm³ or l")
    if values not in ("stem", "figure"):
        raise vt.TemplateError("graduated_vessel: values must be stem or figure")
    if values == "stem":
        vt.require_stem(stem, capacity=capacity, step=step, reading=reading)
    divisions = capacity / step
    lattice = reading / step * 2
    if abs(divisions - round(divisions)) > 1e-9 or not 2 <= round(divisions) <= 10:
        raise vt.TemplateError("graduated_vessel: requires 2..10 whole scale divisions")
    if abs(lattice - round(lattice)) > 1e-9:
        raise vt.TemplateError("graduated_vessel: reading must lie on a half-step")
    from decimal import Decimal
    div_n = round(divisions)
    step_d, cap_d = Decimal(str(step)), Decimal(str(capacity))
    if step_d * div_n != cap_d:
        raise vt.TemplateError(
            "graduated_vessel: the step cannot reach capacity exactly — the scale labels "
            "would disagree with the axis (e.g. a repeating decimal step)")
    ticks = []
    for i in range(div_n + 1):
        d = step_d * i
        s = format(d.normalize(), "f") if d else "0"
        if float(s) != float(d) or f"{float(s):g}" != s:
            raise vt.TemplateError(
                "graduated_vessel: a calibration label needs more than six significant "
                "digits — the audit's expected numeral could never match it")
        ticks.append(s)
    vc.reset_ids()
    height = 240 if divisions <= 8 else 320
    y = height * (1 - reading / capacity)
    anchors = {"O": (110, height), "Y": (110, 0), "P": (110, y)}
    elements = []
    if reading:
        elements.append({"type": "rect", "id": "liquid", "x": 0, "y": y,
                         "width": 90, "height": height - y,
                         "fill": {"color": "#dbeafe"}, "stroke": {"width": 0}})
    elements += [vc.line((0, -12), (0, height), id="left"),
                 vc.line((0, height), (90, height), id="base"),
                 vc.line((90, height), (90, -12), id="right"),
                 vc.line(anchors["O"], anchors["Y"], id="scale"),
                 dict(vc.line((0, y), anchors["P"], width=3, id="level"), stroke={"width": 3, "color": "#1d4ed8"}),
                 vc.text((110, -34), unit, align="start", id="unit")]
    evidence = "stem" if values == "stem" else "inferred"
    claims = [(f"axis OY from 0 to {ex(capacity)}", evidence,
               "stem-checked capacity" if values == "stem" else "calibration printed on the figure"),
              (f"tick OY step {ex(step)}", evidence,
               "stem-checked step" if values == "stem" else "calibration printed on the figure"),
              (f"reads P {ex(reading)} on OY", evidence,
               "horizontal liquid surface meets the calibrated scale"),
              (f"derive {ex(capacity)} / {ex(step)} = {div_n}", "inferred",
               "number of equal scale divisions"),
              (f'describe "open vessel in schematic front view; a horizontal blue line marks the liquid surface; scale is in {unit}"',
               "inferred", "no meniscus, curved body, or physical diameter is implied"),
              (f'label "{unit}" names unit', "inferred", "scale unit")]
    for i, s in enumerate(ticks):
        yy = height * (1 - float(step_d * i) / capacity)
        elements += [vc.line((110, yy), (123, yy), id=f"scale_tick{i}"),
                     vc.text((145, yy), s, align="start")]
        claims.append((f'label "{s}" names {s}', "inferred", "calibrated numeral"))
    for i in range(1, 2 * div_n, 2):
        yy = height * (1 - i * step / 2 / capacity)
        elements.append(vc.line((110, yy), (117, yy), id=f"minor{i}"))
    claims.append(('describe "short unlabelled ticks mark the half-step between each pair of numbered graduations"',
                   "inferred", "a half-step reading sits on a drawn mark"))
    if values == "figure":
        claims.append(('describe "the scale calibration and the liquid reading are figure content; the question asks the student to read them from the figure"',
                       "inferred", "read-the-figure mode"))
    claims.append(("none tickMark parallelMark angleMark angleArc arrow dashed", "inferred",
                   "scale ruling is not an equality tickMark"))
    return vt.finish(kind="graduated_vessel", figure_id=figure_id, stem=stem,
                     elements=elements, anchors=anchors, points=list(anchors), segments=["OY"],
                     claims=claims, ask=ask, title=title or "Graduated vessel",
                     description=description or f"A schematic open vessel beside an equally spaced {unit} scale, with a horizontal liquid surface and half-step marks.",
                     scale="linear calibrated volume scale; vessel width is symbolic, not a radius or diameter",
                     medium=medium,
                     budget=len(elements) if len(elements) > 32 else None,
                     departures=["half-step minor ticks raise the element count"] if len(elements) > 32 else None)
