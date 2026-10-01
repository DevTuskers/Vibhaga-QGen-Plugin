#!/usr/bin/env python3
"""
Audit A for a figure CLAIM SET — the mechanical half, run with **no page, no drawing and no VDD**.

    python3 tools/audit-claim-set.py <claim-set.txt>
    python3 tools/audit-claim-set.py --self-test

Plugin move (2026-09-29): `channel:` is OPTIONAL and defaults to `constructed` — a generated figure
is authored on the canvas, not read off a printed page. A constructed set then REQUIRES a `stem:`
header (free text, may wrap), and every `ratio … = v` / `angle … = v` claim must be justified by a
pair of stem numbers (|a/b − v|/v ≤ TOL_RATIO · within TOL_ANGLE) or cite a matching `derive Kn`
claim — and a cited derive counts only when every literal in its expression is a stem number, a
canonical constant (1, 2, 90, 180, 360), or the value of another backed derive (transitively, no
cycles): an invented `derive 3 / 2 = 1.5` must not rescue a copied ratio. The stem is the only
ground truth a generated figure has.

⚠️ **WHY THIS EXISTS, AND WHAT IT IS NOT.**
S6a (`read-figure-claim-set`) emits a claim set precisely so that a *second* agent can check a figure
without seeing the drawing — the only escape from TRAPS **T25** (an agent shown its own output cannot
unsee it). This script is the part of that audit a machine can do.

⚠️ **IT IS NOT THE AUDIT.** Running it does not satisfy S12 §3.2, and a green run is not independence:
- it cannot tell you the reading is **right** — a self-consistent misreading passes every assertion here
  (source comparison is S6b §5 + S13 C4; Audit B is text-only, S6a §5.2);
- it cannot tell you the claims are **sufficient** — it checks that a `load-bearing:` list *exists* per
  part of the `ask` and that every id it cites exists, never that the listed claims actually answer it.
  ⚠️ **That is the commonest real defect**: a `load-bearing:` list that cites *value* claims (an angle, a
  ratio) where the answer actually turns on an *incidence* claim (`collinear`, `on`, `right`). A blind
  audit of this file's own §4 example found exactly that. The judgement is the separate agent's.
- it does check the **trail's own honesty** (W12c): an `ask:` line that wraps spawns phantom parts
  (ii07b v1's "makes"/"cube"/"8"/"6"), a part ref naming the wrong item fails, a `# RE-READ`/`# DELTA`
  preamble claiming stability while its own items edit K-lines fails, and a `K*→<number>` literal that
  the current anchors no longer give is reported stale.
⇒ **Run this first so the human/agent turn is spent on judgement rather than arithmetic.**

⚠️ **THIS CHECKER FAILS CLOSED.** A predicate it does not recognise is a **FAILURE**, not a pass, and a
predicate it recognises but cannot verify from anchors is **counted and named** in the footer. Silence is
the failure this whole suite is about; a checker may not be the thing that is silent. (It was, until
2026-08-26: an `elif` chain with no `else` waved through every unimplemented predicate, and a claim line
that lost its `|` separators was appended to the previous claim's note and **vanished with exit 0** — T99
reproduced inside the tool built to make T99 mechanical.)

Input: a claim set as S6a §3 specifies it. Either a standalone file, or a markdown file whose worked
example sits in the first fenced block after a `## 4.` heading (so this runs against S6a's own §4
unchanged — which is also how the format's machine-parseability is asserted).

Exit 1 on any failure, 2 on a parse error, so it can gate a handoff.
"""
from __future__ import annotations

import math
import re
import shlex
import sys

TOL_ANGLE = 0.02        # deg — anchors and claims came from ONE measurement; they cannot honestly differ
TOL_RIGHT = 0.05        # deg — a `right` claim, against 90, on a VECTOR channel
TOL_RIGHT_RASTER = 1.0  # deg — the same claim read off pixels: S6a §2 says a raster read is good to ±1°, so a
                        #       printed square whose fitted strokes meet at 89.3° is a reading, not a failure
                        #       (2026-09-05: four run-9 and one run-8 `right` claims had to be adjudicated for
                        #       nothing else)
TOL_RATIO = 0.005       # 0.5% — a stated ratio against the anchors
TOL_LEN = 0.02          # 2% — an `equal` claim
MAX_RESIDUAL = 0.5      # % of the span — above this, "collinear"/"on" is not a reading, it is a hope
INVENTORIES = ("labels", "points", "segments")
# ⚠️ `channel` is NOT required (plugin move, 2026-09-29): a missing channel means `constructed` —
# the default for generated question figures, which are authored on the canvas rather than read off
# a printed page. An unknown channel value when present still fails closed.
REQUIRED_HEADERS = ("figure", "source", "ask", "unreadable", "ambiguous")
# ⚠️ The claim-id grammar, documented in S6a §3.2. Validated on parse, never used to GUESS whether a
# line is a claim — see the parser.
ID_GRAMMAR = re.compile(r"[A-Z]\d+[a-z]?")
# An `ask:` entry's leading part ref. Corpus shapes: `4` `15` `18` `20` (bare item), `7.b.i` `12.a`
# `1.a.iii` (dotted), `II-01.b.i` (canonical), `b.ii` `b.iii` (part-only), `i`–`iv` (roman),
# `(i)` `(ii)` (parenthesised). A bare alphabetic token is a ref only at ≤3 chars — `makes`/`cube`
# are wrapped prose, not refs (ii07b v1's phantom parts).
PART_REF = re.compile(r"(?:[IVX]+-?\d+|\d+)(?:\.[A-Za-z0-9]+)*|[a-z]{1,3}(?:\.[a-z0-9]+)*|\([a-z0-9]+\)")
# A `<claim-id>→<number>` (or `->`/`=`/`:`/`is`/`was`/`≈`/`~`/parens/bare space) literal anywhere in
# notes or trail comments — the stale-literal shape W12c hunts: a value asserted for a claim id that
# the CURRENT anchors no longer give. Quoted spans, mid-expression positions and `# AUDIT B` findings
# reports (whose literals are historical record) are filtered at the scan site. The trailing
# `(?![A-Za-z0-9.])` keeps unit-suffixed tokens (`K3 4x`, `K3 300dpi`, `K3 1.5cm`) from being read
# as claim-id literals, and a space-flanked `-` is a connector while `K3 -4.00` keeps its sign.
STALE_LIT = re.compile(
    r"\b([A-Z]\d+[a-z]?)(?:'s)?\s*\)?\s*(?:(?:now|still|also|just|only|currently)\s+)?"
    r"(?:→|->|=>|:=|>=?|=+|≈|~|≃|⇒|—|–|−|(?<=\s)-(?=\s)|:|\bis\b|\bwas\b|\breads?\b|"
    r"\bremains?\b|\bstays?\b|\bbecame\b|\bbecomes\b|\bshows?\b|\bsays\b)"
    r"\s*(?:(?:now|still|also|just|only|currently)\s+)?([+−-]?\d+(?:\.\d+)?)(?![A-Za-z0-9.])"
    r"|\b([A-Z]\d+[a-z]?)\s*\(([+−-]?\d+(?:\.\d+)?)\s*\)"   # `(1.10)` — parens WITHOUT a closing
    #                                                          `)` after the number are coords `(45, 40)`
    r"|\b([A-Z]\d+[a-z]?)(?:'s)?\s*\)?\s+(?:(?:now|still|also|just|only|currently)\s+)?"
    r"([+−-]?\d+(?:\.\d+)?)(?![A-Za-z0-9.])")
# A `#`-comment line that opens a trail block. Case-SENSITIVE on purpose: block headers are
# capitalised (`# RE-READ`, `# AUDIT B`, `# DELTA`), while lowercase `delta:`/`delta-status:`/
# `delta-v2-status:` lines are body references inside other blocks — not headers. A `-status`
# suffix keeps the caps spelling out of header-hood too. Any non-word char (or EOL) bounds the
# header — `# RE-READ.`, `# DELTA,`, `# AUDIT  B`, `# RE-READ/v2`, `# RE-READv2` all open blocks;
# an optional `v2`/`2` version tag is absorbed.
TRAIL_HEAD = re.compile(
    r"#\s*(RE[-\s]*READ|AUDIT[\s-]*B|DELTA)(?!-?v?\d*-?(?i:status))(?:\s*v?\d+)?(?=\W|$)")
# An UNSCOPED stability claim — "K-lines unchanged", "claims byte-stable", "no changes" — false
# when the block's own items edit K-lines (ii07b v2). The lookahead keeps the honest scoped forms:
# "K-line predicates/verdicts byte-stable" — and ONLY those: `note`/`text`/`content`/`literal` are
# the very fields items edit, so "K-line notes unchanged" IS a stability claim, not a scope. An
# exception word ("other", "except", "remaining") scopes the single match it precedes (or, for the
# "unchanged except K3" order, the one it follows within the same clause).
STABLE_CLAIM = re.compile(
    r"K[\s-]+lines?\b(?!\s+(?:predicate|verdict|anchor)s?\b)"
    r"(?:[\s,:;—–-]+(?!not\b|never\b|no\b|hardly\b|barely\b)\w+){0,6}?[\s,:;—–-]*"
    r"(?:unchanged|byte\s*-?\s*stable|stable|identical|untouched|unedited|verbatim|as[\s-]is|"
    r"as\s+before|left\s+alone|stand|stood|hold|remains?)"
    r"|\bclaims?\s+(?:(?:are|were|was|is|remains?|remained|still|left|kept|stood|stand|stayed)\s+){0,2}"
    r"(?:unchanged|byte\s*-?\s*stable|stable|identical|untouched|unedited|verbatim)"
    r"|\beverything\s+(?:else\s+)?(?:was\s+)?(?:unchanged|byte-?stable|stable|identical)"
    r"|\ball\s+else\s+(?:was\s+)?(?:unchanged|byte-?stable|stable|identical|untouched|unedited)"
    r"|\bnothing\s+(?:(?:except|excepting|save|bar|but|other\s+than|apart\s+from|barring|minus)\s+"
    r"(?:for\s+|the\s+|those\s+|these\s+)*[A-Z]\d+[a-z]?(?:\s*[,&]\s*[A-Z]\d+[a-z]?)*\s+)?"
    r"(?:else\s+)?(?:was\s+)?(?:moved|changed|edited|touched|altered|modified)\b"
    # The gap between `no` and the noun takes only auxiliaries/adverbs — `no content change` is a
    # claim about TEXT, not about K-lines (ii07b's trail says exactly that).
    r"|\bno\s+(?:(?:K[\s-]+lines?|claims?|assertions?)\s+)?"
    r"(?:(?:were|are|was|is|have|has|had|been|being|still|all|really|actually|truly|indeed|now|"
    r"left|kept|remained?|ever|even)\s+){0,3}?"
    r"(?:changes?|edits?|corrections?|fixes?|adjustments?|amendments?|modifications?|"
    r"alterations?|revisions?|updates?|rewordings?|moves?|movement|changed|edited|modified|"
    r"corrected|fixed|adjusted|amended|altered|revised|moved|updated|reworded|"
    r"touch(?:ed|es)?\b(?!\s+(?:up|down)))\b"
    r"(?!\s+(?:to|of|in|among|for)\s+(?:the\s+)?(?:predicate|verdict|anchor|geometry|ask|scale|"
    r"orientation|labels?|segments?|points?|evidence|content|text|wording|notes?|layout|order|"
    r"structure|numbering|markup|presentation|formatting|appearance|rendering|literals?|values?|"
    r"figures?|diagrams?|drawings?|arrows?|ticks?|intervals?|axes|axis|positions?|placements?|"
    r"styles?|coordinates?|spellings?|glyphs?|comments?|provenance)\b)", re.I)
    # notes/text/content/literals/values are the very fields items edit — `no changes to the
    # notes` is NOT a K-line claim
EXCEPTION_SCOPE = re.compile(
    r"\b(?:other|otherwise|except|excepting|exception|remaining|rest|apart|save|else|bar|barring|"
    r"minus|beyond|aside)\b", re.I)
# The FORWARD form of an exception — `unchanged except K3`, `unchanged (save K4)` — where the scope
# word follows the claim inside the same clause. It must be FOLLOWED by what is excepted (a claim
# id or `as noted`/`the items`): `unchanged but verified` scopes nothing — `but` leads a predicate,
# not an exception.
EXCEPTION_FWD = re.compile(
    r"^\s*[,;—–(-]*\s*(?:except|excepting|save|bar|but|other\s+than|apart\s+from|barring|minus)\b"
    r"\s*[:;,—–]?\s*(?:for\s+|the\s+|those\s+|these\s+)*"
    r"(?=[A-Z]\d|as\b|the\b|those\b|these\b|that\b|noted\b)", re.I)
# An edit verb — word-boundary forms only (`change` inside "unchanged", `fix` inside "prefix" and
# `revis` inside "revisited" must NOT count), checked under a negation guard at the scan site.
# `reads` alone is excluded — "K3 reads fine" is prose; the edit form is "now reads".
EDIT_VERB = re.compile(
    r"\b(?<![Uu]n-)(?:edits?|edited|editing|corrects|corrected|correcting|corrections?|changes?|changed|changing|"
    r"rewrites?|rewrote|rewritten|rewriting|re-?folds?|re-?folded|re-?folding|amends?|amended|amending|"
    r"updates?|updated|updating|rewords?|reworded|rewording|revises?|revised|revising|"
    r"revisions?|re-?measures?|re-?measured|re-?measuring|replaces?|replaced|replacing|replacements?|"
    r"adjusts?|adjusted|adjusting|adjustments?|moves?|moved|moving|repairs?|repaired|repairing|"
    r"restates?|restated|restating|renames?|renamed|renaming|swaps?|swapped|swapping|adds?|added|"
    r"adding|removes?|removed|removing|removals?|deletions?|modifies|modified|modifying|"
    r"modifications?|alters?|altered|altering|alterations?|tweaks?|tweaked|recomputes?|recomputed|"
    r"recalculates?|recalculated|recalculating|recalculations?|reverts?|reverted|reverting|"
    r"reversions?|rolls?(?:ed|ing)?\s*-?\s*back|restores?|restored|restoring|restorations?|redone|"
    r"redos?|re-?did|undoes?|undid|undone|clarifies|clarified|clarifying|clarifications?|amendments?|"
    r"fix(?:es|ed|ing)?\b(?!\s*-\s*\w)|re-?measurements?|deletes?|deleted|deleting|"
    r"(?:was|were|being)\s+set\b|sets?\s+to\b|recomputing|reworks?|reworked|reworking|movements?|"
    r"tweaking|now\s+reads?\s+(?=\d))\b", re.I)
# `additions?` is deliberately absent — "in addition, …" is prose, not an edit. `reads` fires only
# as `now reads <digit>` — "K3 now reads fine" is not an edit either.
# A negation up to ~6 words before an edit verb — "none of the K3 notes were changed", "not a
# single K3 line was edited", "K3 wasn't edited". `'?\w*` keeps possessives/contractions as
# single window words.
# The window word is `[\w'-]+` — `K-lines` itself is hyphenated, so a hyphen must not break the
# reach ("no K-lines were changed", "K3 wasnt un-edited").
# Contrastives (`but`/`though`/`however`…) end the window — `not K3 but K5 was changed`
# negates K3's change, not K5's.
NEGATED = re.compile(
    r"(?:no|not|never|without|un|nothing|zero|none|wasn't|wasnt|weren't|werent|didn't|didn|"
    r"didnt|doesn't|doesnt|don't|dont|won't|wont|isn't|isnt|aren't|arent|hasn't|hasnt|"
    r"haven't|havent|hadn't|hadnt|can't|cant|cannot)\s+"
    r"(?:(?!but\b|though\b|however\b|yet\b|although\b|whereas\b)[\w'-]+\s+){0,8}$", re.I)
# A verb-shaped word made negative by `un-` (`un-edited`, `un-changed`) — EDIT_VERB's lookbehind
# stops it matching there, but a clause containing one is explicitly NON-editing (R7-8/R7-12).
UNVERB = re.compile(r"\bun-(?:edit|chang|correct|modif|alter|touch|mov|adjust|fix|rewrit|revis|"
                    r"reword|updat|amend|tweak|swapp|renam|replac|delet|remov|add|repair|restat|"
                    r"clarif|recomput|recalcul|revert|restor|undo)\w*", re.I)
# A clause carrying one of these and no non-negated edit verb records what did NOT change
# (`K5 unchanged`, `K3 is correct`, `K5-K6 were left unchanged`) — its ids are exempt (R7-12).
NOCHANGE_WORD = re.compile(
    r"\b(?:un-?changed|un-?touched|un-?edited|un-?modified|un-?altered|kept|retained|stayed|held|"
    r"left\s+(?:alone|unchanged|untouched|as[\s-]is)|as[\s-]is|stable|intact|reviewed|verified|"
    r"re-?checked|spot-?checked|confirmed|re-?affirmed|no\s+changes?|correct|fine|ok|okay)\b", re.I)
# One itemised entry inside a trail block — `# F:`, `# F.`, `# (F)`, `# F)`, `# item G`, `# - x`,
# `# 1. x`.
ITEM_LINE = re.compile(
    r"#\s*(?:[A-Za-z]\s*[:.](?!\w)|\([A-Za-z]{1,3}\)|[A-Za-z]{1,3}\)|items?\s+[A-Za-z\d]|"
    r"[-*•](?:\s|$)|\d+[.)](?:\s|$))", re.I)
# Quoted spans stripped before claim/edit/literal matching — quoted history is not a claim. The
# opening `'` may not follow a word char, or possessives (`K3's`, "the reader's") eat the text.
QUOTED = re.compile(r'"[^"]*"|(?<![A-Za-z0-9\'])\'(?:[^\']|\'(?=[A-Za-z0-9]))*\'|`[^`]*`')
# A note continuation is a HANGING indent, not a slightly-deeper line. Anything between the claim indent
# and this gap is refused as ambiguous — a claim mis-indented by two spaces looked exactly like a note.
CONT_MIN_GAP = 6
# The claim-set section vocabulary is FIXED (S6a §3 + every corpus file). A col-0 `word:` inside
# `claims:` otherwise opens a phantom section and every following claim line is filed under it —
# silently unaudited (the T99 swallow this tool exists to catch). An unknown dedented key dies.
SECTION_KEYS = {"figure", "source", "channel", "read", "ask", "labels", "points", "segments",
                "anchors", "claims", "load-bearing", "unreadable", "ambiguous", "departures",
                "scale", "allow", "verification-scope", "budget",
                # `stem:` (plugin move, 2026-09-29): the question's stem text, free text that may
                # wrap. REQUIRED on a constructed claim set — it is the only ground truth a
                # generated figure has, and the stem-justification check measures `ratio`/`angle`
                # values against the numbers it states.
                "stem"}
# A zoom declaration: `4x`, `4×`, `300 dpi`. The digit lookahead after `x` keeps `1200x800` (image
# dimensions) from dodging the raster `measured` zoom requirement.
ZOOM = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?\s*(?:x|×)(?![A-Za-z0-9])|\b\d+\s*dpi\b", re.I)


def die(msg: str) -> None:
    print(f"  PARSE  {msg}")
    print("\n⚠️ A claim set that does not parse has NOT been audited. Fix the text, do not ignore this.")
    sys.exit(2)


# --------------------------------------------------------------------------------------------- parse
def parse(text: str) -> dict:
    m = re.search(r"^#{2,4}\s+4\.(?:\s|$).*?\n```[^\n]*\n(.*?)\n```", text, re.S | re.M)
    if m:
        text = m.group(1)
    cs: dict = {"anchors": {}, "claims": [], "meta": {}, "comments": []}
    sec = None
    claim_indent: int | None = None
    for lineno, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            # trail blocks (`# RE-READ`/`# AUDIT B`/`# DELTA`) and provenance comments are kept for
            # the W12c lint — they are evidence, not claim text
            cs["comments"].append((lineno, line.lstrip()))
            continue
        head = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if head:
            key = head.group(1)
            if ID_GRAMMAR.fullmatch(key):
                die(f"line {lineno}: `{key}:` looks like an id written as a `key:` header — a "
                    f"claim is `<id> <predicate> | <evidence> | <note>`, not `{key}: ...`. As "
                    f"parsed, every line below would be filed under `{key}` and never audited")
            if key not in SECTION_KEYS:
                die(f"line {lineno}: `{key}:` is not a known section header (the vocabulary is "
                    f"fixed — S6a §3). A dedented line inside a section silently files every "
                    f"following line under `{key}` (the T99 swallow). Indent it, fix the typo, "
                    f"or extend SECTION_KEYS if `{key}` is a real new section")
            sec, rest = key, head.group(2).strip()
            cs["meta"].setdefault(sec, [])
            if rest:
                cs["meta"][sec].append(rest)
            continue
        body = line.strip()
        if sec is None:
            die(f"line {lineno}: content before any `key:` header — {body!r}")
        if sec == "anchors":
            parts = body.split()
            if len(parts) != 3:
                die(f"line {lineno}: anchors want `<name> <x> <y>`, got {body!r}")
            try:
                if parts[0] in cs["anchors"]:
                    die(f"line {lineno}: duplicate anchor {parts[0]} — the second declaration "
                        f"silently discards the first's coordinates")
                cs["anchors"][parts[0]] = (float(parts[1]), float(parts[2]))
            except ValueError:
                die(f"line {lineno}: anchor coordinates are not numbers — {body!r}")
        elif sec == "claims":
            # ⚠️ B1, ROUND 2 (2026-08-28): THE TEST IS POSITIVE, ON INDENTATION, AND THAT IS THE WHOLE
            # POINT. It used to be negative — "if the first token does not look like a claim id, fold
            # this line into the previous claim's note" — and a negative test fails OPEN on every shape
            # nobody enumerated: `k24`, `K24.`, `(K24)`, `KK24`, `K24ab`, `K-24`, `24`, `k4b` were all
            # swallowed silently, each producing a byte-identical report, which is why "count what you
            # parsed" did not catch it either (the count was unchanged). ⇒ A claim line is now defined
            # by WHERE IT STARTS, not by what it looks like: the first content line under `claims:` sets
            # the claim indent, and every line at or left of that indent IS a claim and MUST have `|`s.
            indent = len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())
            if claim_indent is None:
                claim_indent = indent          # the first line under `claims:` cannot be a continuation
            if indent <= claim_indent:
                if "|" not in body:
                    die(f"line {lineno}: this is a CLAIM line (indent {indent} <= {claim_indent}) and it "
                        f"has no `|` separators — a claim is `<id> <predicate> | <evidence> | <note>`. "
                        f"Refusing to fold it into "
                        f"{cs['claims'][-1]['id'] if cs['claims'] else '(nothing)'}'s note. Got: {body!r}")
            elif indent < claim_indent + CONT_MIN_GAP:
                die(f"line {lineno}: AMBIGUOUS INDENTATION (indent {indent}). A claim line starts at "
                    f"column {claim_indent}; a note continuation must be a hanging indent of at least "
                    f"{claim_indent + CONT_MIN_GAP}. Got: {body!r}")
            else:
                first = body.split(None, 1)[0]
                if "|" in body and ID_GRAMMAR.fullmatch(first):
                    die(f"line {lineno}: claim {first} is indented like a note continuation "
                        f"(indent {indent} > {claim_indent}). Claim lines start at column {claim_indent}.")
                if not cs["claims"]:
                    die(f"line {lineno}: continuation line before any claim — {body!r}")
                cs["claims"][-1]["note"] += " " + body            # a wrapped note: fine
                continue
            bits = [p.strip() for p in body.split("|", 2)]
            left, ev, note = bits[0], bits[1], (bits[2] if len(bits) > 2 else "")
            if " " not in left:
                die(f"line {lineno}: want `<id> <predicate>` before the first `|`, got {left!r}")
            kid, pred = left.split(None, 1)
            if not ID_GRAMMAR.fullmatch(kid):
                die(f"line {lineno}: claim id {kid!r} is not of the form K1 / K1b (S6a §3.2: one capital, "
                    f"digits, an optional single lower-case suffix)")
            if any(c["id"] == kid for c in cs["claims"]):
                die(f"line {lineno}: duplicate claim id {kid}")
            cs["claims"].append({"id": kid, "pred": pred.strip(), "ev": ev, "note": note, "line": lineno})
        else:
            # A claim-shaped line filed under a META section is the other half of the T99 swallow:
            # `K7 angle ... | measured` indented under `ambiguous:`/`departures:`/`scale:` is stored
            # as meta text and never audited — and under `ambiguous:` it even invents a phantom
            # adjudication. The claim shape is `<id-token> … <|>`; corpus meta lines never match it.
            if "|" in body and ID_GRAMMAR.match(body.split(None, 1)[0]):
                die(f"line {lineno}: this looks like a CLAIM (id + `|` separators) but it is filed "
                    f"under `{sec}:`, not `claims:` — it would never be audited. Got: {body!r}")
            cs["meta"][sec].append(body)
    # ⚠️ M2: join EVERY line of an inventory before tokenising — §3.1's own example wraps `ask:` over
    # four lines, and `vals[0]` silently kept the first.  ⚠️ M1: shlex, so `"7 cm"` is ONE label.
    for key in INVENTORIES:
        joined = " ".join(cs["meta"].get(key, []))
        try:
            cs[key] = shlex.split(joined, posix=True) if joined else []
        except ValueError as exc:
            die(f"{key}: unbalanced quote — {exc}")
    return cs


# ------------------------------------------------------------------------------------------ geometry
def angle(p, q, r) -> float:
    a = math.degrees(math.atan2(p[1] - q[1], p[0] - q[0]) - math.atan2(r[1] - q[1], r[0] - q[0]))
    return abs((a + 180) % 360 - 180)


def dist(p, q) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def anchor_value(pred: str, ev: str, a: dict) -> tuple[float, float, bool] | None:
    """The anchor-derived value a `<id>=<num>` literal most plausibly cites, for the W12c
    stale-literal lint: `(value, tolerance, is_relative)` — or None when no comparison is sound.

    Deliberately narrower than step 2's evaluators: only `angle` and `ratio` state the SAME
    quantity the literal asserts. For `right`/`equal`/`collinear`/`on` the derived quantity
    (≈90°, ratio≈1, residual≈0) is not what a `K*=n` literal usually means — `K4=90` on a `right`
    claim is the nominal constant, `K7=26.60` on an `equal` claim is a segment length — so those
    are skipped rather than misjudged. `angle` inherits step 2's evidence gate: a non-`measured`
    angle MAY differ from anchors (`scale:`), so its literal is not stale when it does."""
    if (m := re.match(r"^angle ([A-Z]) ([A-Z]) ([A-Z]) = \d+(?:\.\d+)?$", pred)) and ev == "measured" \
            and all(g in a for g in m.groups()[:3]):
        return angle(a[m[1]], a[m[2]], a[m[3]]), TOL_ANGLE, False
    if (m := re.match(r"^ratio len ([A-Z])([A-Z]) / len ([A-Z])([A-Z]) = \d+(?:\.\d+)?$", pred)) \
            and all(g in a for g in m.groups()[:4]):
        d1, d2 = dist(a[m[1]], a[m[2]]), dist(a[m[3]], a[m[4]])
        if d1 and d2:
            return d1 / d2, TOL_RATIO, True
    return None


def residual(p, q, r) -> float:
    """Perpendicular distance of q from line p-r, as a fraction of |p-r|. Scale-free, so it survives a
    change of canvas — which is why claim sets state residuals and never absolute offsets."""
    span = dist(p, r)
    if span == 0:
        return 1.0
    return abs((r[0] - p[0]) * (p[1] - q[1]) - (p[0] - q[0]) * (r[1] - p[1])) / span**2


# --------------------------------------------------------- the ANSWER-SIDE arithmetic (2026-08-30)
# ⚠️ WHY THIS EXISTS. A CONSTRUCTED answer figure has no printed counterpart for its added claims. The old
# page-based Audit B wording is superseded: Audit B is text-only; S6b §5 + S13 C4 check the source. Measured
# 2026-08-30: an internally consistent claim set whose hop lands on **5** where the ask is `4 - (-2)`
# scored **78 assertions, 0 failures, exit 0 — a footer byte-identical to the correct set.** Every input
# needed to catch it was already parsed.
#
# ⭐ THE POSITIVE TEST (T99's rule: never "if it does not look wrong, pass"): the claim set must DECLARE
# the answer's own arithmetic as `derive <expr> = <value>`, and then two things are checked, so both doors
# are closed —
#   (1) `<expr>` really evaluates to `<value>`   ⇒ catches "I drew 5 and wrote 5"
#   (2) the `arrow` claim's END, projected onto the `axis` scale, IS `<value>`
#                                                ⇒ catches "I wrote 6 and drew 5"
# It cannot tell you the DERIVATION is the right one for the question — that is S8 §3's two-method check
# and S13's C4 — but it makes the figure and the arithmetic answer to each other, which nothing did.
_EXPR_OK = re.compile(r"^[0-9\s+\-*/().]+$")


def arith(expr: str) -> float | None:
    """Evaluate a bare arithmetic expression, or None. Digits/operators/parens only — no names, no
    attributes, no calls, so there is nothing to inject."""
    if not _EXPR_OK.match(expr or "") or re.search(r"[*/]{2,}", expr or ""):
        # `**`/`//` are not in the documented grammar — and `9**9**9` is also a hang: eval builds a
        # ~370M-digit integer. Reject doubled operators before eval ever sees them.
        return None
    try:
        return float(eval(compile(expr, "<derive>", "eval"), {"__builtins__": {}}, {}))  # noqa: S307
    except Exception:  # noqa: BLE001 — a malformed expression is a FAILURE reported by the caller
        return None


def project_value(pt_xy, p, q, v0, v1) -> float:
    """The value at `pt_xy`, projected onto the axis p->q which runs v0->v1."""
    ax, ay = q[0] - p[0], q[1] - p[1]
    den = ax * ax + ay * ay
    if den == 0:
        return v0
    t = ((pt_xy[0] - p[0]) * ax + (pt_xy[1] - p[1]) * ay) / den
    return v0 + t * (v1 - v0)


# ------------------------------------------------------------------- the predicate registry (M10)
# name -> "anchor" (verified below) | "text" (recognised, not verifiable from anchors, and SAID SO)
PREDICATES = {
    "collinear": "anchor", "angle": "anchor", "right": "anchor", "ratio": "anchor",
    "parallel": "anchor", "equal": "anchor", "on": "anchor", "inside": "anchor",
    "circle": "anchor", "arc": "anchor", "axis": "anchor", "tick": "anchor", "interval": "anchor",
    "gradient": "anchor", "at": "anchor", "derive": "anchor",
    "label": "text", "free-text": "text", "paint": "text", "none": "text",
    # ⚠️ `arrow` MOVED "text" -> "anchor" on 2026-08-30. It was `continue`d by the `kind == "text"` gate
    # above, so an `arrow P -> Q` claim was never even closure-checked — and it is the claim that carries
    # the MOVE on an answer-side figure, i.e. the one check 2c has to project onto the scale. It still
    # reports as recognised-not-verifiable when there is no scale to project onto.
    "arrow": "anchor",
    "shaded": "text", "grid": "text", "stage": "text", "describe": "text",
}


def audit(cs: dict) -> tuple[list[str], int, dict]:
    a, out, fails = cs["anchors"], [], 0
    # ⚠️ MAJOR 3 (2026-08-28): a claim named in `ambiguous:` is CONTESTED ON PURPOSE. It still gets
    # checked and its number still gets printed, but it reports ADJDCT and is EXCLUDED FROM THE EXIT
    # CODE — because this script is documented as a handoff gate, and a gate that a correct claim set
    # cannot pass is a gate people route around. The distinction is S6b §0.8's advisory-vs-blocking
    # lesson, applied to this tool. ⚠️ A contested claim with NO `ambiguous:` entry stays a hard FAIL:
    # that is the whole point — you must WRITE DOWN the adjudication to get it.
    adjudicated = set()
    ambiguous_idle: list = []
    for line in cs["meta"].get("ambiguous", []):
        if line.strip().lower() in ("(none)", "none", "-"):
            continue
        # An entry ADJUDICATES the claim id(s) it LEADS with — `K13 — re-measured …`, optionally
        # quoted or several ids (`K13, K14 — …`). An id mentioned mid-prose (`see K4`, `"K3"`)
        # describes context; it does not declare K4/K3 contested (those stay hard FAILs).
        lead_m = re.match(
            r"""\s*["'`(\[\]\s-]*([A-Z]\d+[a-z]?\b(?:(?:["'`)\s,\]/;:(–—-]|and\b|&)*[A-Z]\d+[a-z]?\b)*)""", line)
        if lead_m:
            adjudicated |= set(re.findall(r"[A-Z]\d+[a-z]?", lead_m.group(1)))
        else:
            ambiguous_idle.append(line.strip()[:40])
    stats = {"claims": len(cs["claims"]), "anchor_checked": 0, "recognised_unverifiable": [],
             "unrecognised": [], "adjudicated": [], "adjudicated_declared": sorted(adjudicated),
             "ambiguous_idle": ambiguous_idle}

    def check(ok: bool, msg: str, cid: str | None = None) -> bool:
        nonlocal fails
        if ok:
            out.append("  ok    " + msg)
            return True
        if cid and cid in adjudicated:
            if cid not in stats["adjudicated"]:
                stats["adjudicated"].append(cid)
            out.append("  ADJDCT " + msg + "   [named in `ambiguous:` — adjudicated, not a gate failure]")
            return False
        fails += 1
        out.append("  FAIL  " + msg)
        return False

    def pt(name: str, cid: str) -> tuple | None:
        if name not in a:
            check(False, f"{cid}: names point {name}, which has no anchor", cid)
            return None
        return a[name]

    def distinct(gs: tuple, cid: str, pred: str) -> bool:
        return check(len(set(gs)) == len(gs),
                     f"{cid}: {pred} -> names the same point twice — a degenerate claim is "
                     f"vacuously true, not evidence", cid)

    # 0. the headers a claim set is not a claim set without
    for h in REQUIRED_HEADERS:
        check(h in cs["meta"], f"header `{h}:` is present")
    # `figure:`/`channel:` are read first-wins (`[0]`), so a repeat silently loses the first
    # value. `source:`/`unreadable:` etc. are list-valued — a repeat just appends, which the
    # corpus legitimately uses (multi-source figures, several unreadable entries).
    for h in ("figure", "channel"):
        check(len(cs["meta"].get(h, [])) <= 1,
              f"`{h}:` declared once — a second `{h}:` line silently loses the first value")
    ch_val = (cs["meta"].get("channel") or [""])[0].strip()
    check(not ch_val or re.match(r"^(raster|vector|constructed|mixed)\b", ch_val, re.I),
          f"`channel:` names a known channel (raster|vector|constructed|mixed — "
          f"`{ch_val.split()[0] if ch_val else ''}` is not one; a typo'd channel silently takes "
          f"the vector tolerances and dodges the raster zoom requirement)")
    for h in ("figure", "source", "unreadable"):
        check(any(v.strip() for v in cs["meta"].get(h, [])),
              f"`{h}:` header is not empty (a bare `{h}:` line satisfies presence while dodging "
              f"the checks that read its value)")
    if "channel" in cs["meta"]:
        check(bool(ch_val), "`channel:` header is not empty (a bare `channel:` line satisfies "
                            "presence while dodging the checks that read its value)")
    # The EFFECTIVE channel: missing `channel:` means `constructed` (plugin move, 2026-09-29 — a
    # generated figure is authored on the canvas, not read off a page). A constructed set is then
    # REQUIRED to carry the stem it was built from — the stem is the only ground truth there is.
    eff_channel = (ch_val.split()[0].lower() if ch_val else "constructed")
    if eff_channel == "constructed":
        check(any(v.strip() for v in cs["meta"].get("stem", [])),
              "a `constructed` claim set carries a `stem:` header — the stem's own numbers are the "
              "ground truth the `ratio`/`angle` claims are checked against (no printed page exists)")
    check(bool(cs["claims"]), "at least one claim was parsed")

    # 1. closure — a claim set that names something it does not declare is not auditable at all
    for p in cs["points"]:
        check(p in a, f"point {p} has an anchor")
    named = set()
    for c in cs["claims"]:
        if not c["pred"].startswith(("label ", "free-text ", "none ", "describe ")):
            named |= set(re.findall(r"(?<![A-Za-z])[A-Z](?![A-Za-z])", c["pred"]))
    unknown = sorted(named - set(cs["points"]))
    check(not unknown, f"every point named in a claim is declared (unknown: {unknown})")
    for seg in cs["segments"]:
        check(all(ch in a for ch in seg) and len(seg) == 2,
              f"segment {seg}: two declared endpoints")
    for glyph in cs["labels"]:
        n = sum(1 for c in cs["claims"]
                if re.match(rf'^label "{re.escape(glyph)}" names', c["pred"]))
        check(n == 1, f'label "{glyph}" is bound by exactly one `label` claim (found {n})')

    axes: dict = {}        # (P, Q) -> the scale declared on that segment (direction is v0->v1)
    axis_pairs: set = set()  # frozensets — `axis QP` on the same segment as `axis PQ` is a dup
    ats: list = []         # (cid, value, (x, y)) from `at <v> <x> <y>` claims
    derives: list = []     # (cid, value) from `derive <expr> = <value>` — the ANSWER-SIDE ground truth
    derive_literals: dict = {}  # cid -> numeric literals in the derive's expression (2d's backing check)
    arrows: list = []      # (cid, P, Q) from `arrow P -> Q`, so 2c can project it onto a scale
    label_targets: dict = {}
    # `tick`/`interval` are collected, not checked inline: a claim may legitimately precede the
    # `axis` it rides on (order in the file is not a dependency), and the axis lookup needs the
    # whole loop to have run.
    pending_ticks: list = []       # (cid, pred, P, Q, step)
    pending_intervals: list = []   # (cid, pred, kind, lo, hi, P, Q)

    # 2. claims vs anchors — the check that finds a MISREAD with no other input.
    #    ⚠️ FAILS CLOSED: the final `else` is a failure, not a pass.
    for c in cs["claims"]:
        pred, ev, cid = c["pred"], c["ev"], c["id"]
        kind = PREDICATES.get(pred.split(None, 1)[0])
        if kind is None:
            stats["unrecognised"].append((cid, pred))
            check(False, f"{cid}: predicate {pred.split(None, 1)[0]!r} NOT RECOGNISED — this claim was "
                         f"NOT checked. Add it to PREDICATES and to S6a §3.2, or fix the claim")
            continue
        if kind == "text":
            stats["recognised_unverifiable"].append(cid)
            continue

        if (m := re.match(r"^angle ([A-Z]) ([A-Z]) ([A-Z]) = (\d+(?:\.\d+)?)$", pred)):
            if ev != "measured":
                stats["recognised_unverifiable"].append(cid)   # `printed`/`stem` MAY differ — `scale:`
                continue
            if all(pt(g, cid) for g in m.groups()[:3]) and distinct(m.groups()[:3], cid, pred):
                got = angle(a[m[1]], a[m[2]], a[m[3]])
                check(abs(got - float(m[4])) <= TOL_ANGLE, f"{cid}: {pred} -> anchors give {got:.2f} deg", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^right ([A-Z]) ([A-Z]) ([A-Z])$", pred)):
            if all(pt(g, cid) for g in m.groups()) and distinct(m.groups(), cid, pred):
                got = angle(a[m[1]], a[m[2]], a[m[3]])
                ch = (cs["meta"].get("channel") or [""])[0]
                tol = TOL_RIGHT_RASTER if (ch.startswith("raster") or ch.startswith("mixed")) else TOL_RIGHT
                check(abs(got - 90) <= tol, f"{cid}: {pred} -> anchors give {got:.2f} deg (tolerance ±{tol}° on {ch.split()[0] or 'vector'})", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^collinear ([A-Z]) ([A-Z]) ([A-Z])$", pred)):
            if all(pt(g, cid) for g in m.groups()) and distinct(m.groups(), cid, pred):
                r = residual(a[m[1]], a[m[2]], a[m[3]]) * 100
                check(r < MAX_RESIDUAL, f"{cid}: {pred} -> residual {r:.3f}% of the span", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^on ([A-Z]) ([A-Z])([A-Z])$", pred)):
            if all(pt(g, cid) for g in (m[1], m[2], m[3])) and \
                    distinct((m[1], m[2], m[3]), cid, pred):
                r = residual(a[m[2]], a[m[1]], a[m[3]]) * 100
                inside = dist(a[m[2]], a[m[1]]) + dist(a[m[1]], a[m[3]]) <= dist(a[m[2]], a[m[3]]) * 1.02
                check(r < MAX_RESIDUAL and inside,
                      f"{cid}: {pred} -> residual {r:.3f}%, between the endpoints: {inside}", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^parallel ([A-Z])([A-Z]) ([A-Z])([A-Z])$", pred)):
            if all(pt(g, cid) for g in m.groups()) and distinct(m.groups(), cid, pred):
                v1 = (a[m[2]][0] - a[m[1]][0], a[m[2]][1] - a[m[1]][1])
                v2 = (a[m[4]][0] - a[m[3]][0], a[m[4]][1] - a[m[3]][1])
                off = abs((math.degrees(math.atan2(v1[1], v1[0]) - math.atan2(v2[1], v2[0])) + 90) % 180 - 90)
                check(off < 1.0, f"{cid}: {pred} -> {off:.2f} deg apart", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^equal ([A-Z])([A-Z]) ([A-Z])([A-Z])$", pred)):
            # `equal AK KB` — adjacent segments sharing one endpoint — is a real claim (the
            # corpus uses it for K a midpoint). Degenerate only when a segment collapses or the
            # two segments are the same one.
            if all(pt(g, cid) for g in m.groups()) and \
                    check(m[1] != m[2] and m[3] != m[4] and {m[1], m[2]} != {m[3], m[4]},
                          f"{cid}: {pred} -> a degenerate or identical segment pair is "
                          f"vacuously equal, not evidence", cid):
                d1, d2 = dist(a[m[1]], a[m[2]]), dist(a[m[3]], a[m[4]])
                check(abs(d1 - d2) / max(d1, d2, 1e-9) < TOL_LEN, f"{cid}: {pred} -> {d1:.2f} vs {d2:.2f}", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^ratio len ([A-Z])([A-Z]) / len ([A-Z])([A-Z]) = (\d+(?:\.\d+)?)$", pred)):
            if all(pt(g, cid) for g in m.groups()[:4]) and \
                    check(m[1] != m[2] and m[3] != m[4] and {m[1], m[2]} != {m[3], m[4]},
                          f"{cid}: {pred} -> a length needs two distinct endpoints (and a "
                          f"segment ratioed to itself is vacuous)", cid):
                d1, d2 = dist(a[m[1]], a[m[2]]), dist(a[m[3]], a[m[4]])
                got = d1 / d2 if d2 else float("inf")
                want = float(m[5])
                check(want != 0 and abs(got - want) / abs(want) <= TOL_RATIO,
                      f"{cid}: {pred} -> anchors give {got:.4f}", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^inside ([A-Z]) angle ([A-Z]) ([A-Z]) ([A-Z])$", pred)):
            if all(pt(g, cid) for g in m.groups()) and distinct(m.groups(), cid, pred):
                x, p, q, r = a[m[1]], a[m[2]], a[m[3]], a[m[4]]
                whole, part1, part2 = angle(p, q, r), angle(p, q, x), angle(x, q, r)
                check(abs(part1 + part2 - whole) < TOL_ANGLE,
                      f"{cid}: {pred} -> {part1:.2f} + {part2:.2f} = {whole:.2f}", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^circle centre ([A-Z]) (?:through ([A-Z])|radius (\d+(?:\.\d+)?))$", pred)):
            if pt(m[1], cid) and (m[2] is None or (pt(m[2], cid) and
                    check(dist(a[m[1]], a[m[2]]) > 1e-9,
                          f"{cid}: {pred} -> centre {m[1]} and {m[2]} coincide — "
                          f"a zero-radius circle", cid))) and \
                    (m[2] is not None or check(m[3] is None or float(m[3]) > 0,
                          f"{cid}: {pred} -> a radius of {m[3]} is no circle", cid)):
                check(True, f"{cid}: {pred} -> centre declared" + (f", {m[2]} on it" if m[2] else ""), cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^arc centre ([A-Z]) from ([A-Z]) to ([A-Z])$", pred)):
            if all(pt(g, cid) for g in m.groups()) and distinct(m.groups(), cid, pred):
                r1, r2 = dist(a[m[1]], a[m[2]]), dist(a[m[1]], a[m[3]])
                check(abs(r1 - r2) / max(r1, r2, 1e-9) < TOL_LEN,
                      f"{cid}: {pred} -> radii {r1:.2f} vs {r2:.2f} (an arc has ONE radius)", cid)
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^axis ([A-Z])([A-Z]) from (-?\d+(?:\.\d+)?) to (-?\d+(?:\.\d+)?)$", pred)):
            if all(pt(g, cid) for g in (m[1], m[2])):
                if check(float(m[4]) != float(m[3]),
                         f"{cid}: {pred} -> a scale needs two distinct ends", cid):
                    if check(frozenset((m[1], m[2])) not in axis_pairs,
                             f"{cid}: {pred} -> no other `axis` already declared on "
                             f"{m[1]}{m[2]} or {m[2]}{m[1]} (a second scale on one segment "
                             f"silently splits the checks)", cid):
                        axis_pairs.add(frozenset((m[1], m[2])))
                        axes[(m[1], m[2])] = {"v0": float(m[3]), "v1": float(m[4]),
                                              "cid": cid, "step": None}
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^tick ([A-Z])([A-Z]) step (-?\d+(?:\.\d+)?)$", pred)):
            if all(pt(g, cid) for g in (m[1], m[2])):
                pending_ticks.append((cid, pred, m[1], m[2], float(m[3])))
                stats["anchor_checked"] += 1
        elif (m := re.match(r"^at (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)$", pred)):
            # NOT counted as anchor-checked here: the check happens in 2a, and only when an `axis`
            # exists to check it against (an `at` with no axis was silently counted before).
            ats.append((cid, float(m[1]), (float(m[2]), float(m[3]))))
        elif (m := re.match(r"^derive (.+?) = (-?\d+(?:\.\d+)?)$", pred)):
            got, want = arith(m[1]), float(m[2])
            if got is None:
                bad_form = not _EXPR_OK.match(m[1]) or re.search(r"[*/]{2,}", m[1])
                check(False, f"{cid}: {pred} -> `{m[1]}` "
                             f"{'is not a bare arithmetic expression (digits, + - * / and '
                               'parentheses only)' if bad_form else 'did not evaluate — e.g. a '
                               'division by zero'}", cid)
            else:
                check(abs(got - want) < 1e-9,
                      f"{cid}: {pred} -> `{m[1]}` evaluates to {got:g}", cid)
                derives.append((cid, want))
                derive_literals[cid] = tuple(float(x) for x in re.findall(r"\d+(?:\.\d+)?", m[1]))
            stats["anchor_checked"] += 1
        elif (m := re.match(r"^arrow ([A-Z]) -> ([A-Z])$", pred)):
            if all(pt(g, cid) for g in m.groups()) and \
                    check(m[1] != m[2], f"{cid}: {pred} -> a zero-length arrow moves nothing", cid):
                arrows.append((cid, m[1], m[2]))
        elif (m := re.match(r"^interval (open|closed) (-?\d+(?:\.\d+)?) to (-?\d+(?:\.\d+)?) on ([A-Z])([A-Z])$", pred)):
            pending_intervals.append((cid, pred, m[1], float(m[2]), float(m[3]), m[4], m[5]))
        elif (m := re.match(r"^gradient ([A-Z])([A-Z]) (=|steeper than|less steep than) (.+)$", pred)):
            # ⚠️ The claim step 2 got WRONG in prose: F1's description called HG "steeper" than FE/YX
            # when the gradients are 1.73 vs 4.02. A comparative is a claim; check it.
            if all(pt(g, cid) for g in (m[1], m[2])) and \
                    check(m[1] != m[2], f"{cid}: {pred} -> a degenerate segment has no gradient", cid):
                def grad(u, v):
                    dx = a[v][0] - a[u][0]
                    return float("inf") if dx == 0 else abs((a[v][1] - a[u][1]) / dx)
                g1 = grad(m[1], m[2])
                if m[3] == "=":
                    lit = float(m[4]) if re.fullmatch(r"-?\d+(?:\.\d+)?", m[4].strip()) else None
                    check((g1 == lit) or (lit is not None and math.isfinite(g1) and
                                          abs(g1 - lit) <= 0.02 * max(g1, lit, 1e-9)),
                          f"{cid}: {pred} -> anchors give {g1:.3f} (a vertical segment's gradient "
                          f"is infinite — a finite literal can never match it)", cid)
                else:
                    mm = re.fullmatch(r"([A-Z])([A-Z])", m[4].strip())
                    if not mm or not all(pt(g, cid) for g in mm.groups()):
                        check(False, f"{cid}: {pred} -> the right-hand side must be a segment like FE", cid)
                    else:
                        g2 = grad(mm[1], mm[2])
                        want = g1 > g2 if m[3] == "steeper than" else g1 < g2
                        check(want, f"{cid}: {pred} -> {m[1]}{m[2]} is {g1:.3f}, "
                                    f"{mm[1]}{mm[2]} is {g2:.3f}")
                stats["anchor_checked"] += 1
        else:
            stats["unrecognised"].append((cid, pred))
            check(False, f"{cid}: predicate is recognised by name but its ARGUMENTS did not parse — "
                         f"{pred!r} was NOT checked. Match S6a §3.2's form exactly")

    # Deferred axis-riders: `tick`/`interval` are checked only once every `axis` claim is registered —
    # file order is not a dependency (a `tick` written before its `axis` is legal).
    # A `tick`/`interval` names the physical segment, not the scale's direction — `tick QP`
    # resolves `axis PQ` too (the step size is direction-free; interval bounds compare
    # against min/max of the range either way).
    for cid, pred, P3, Q3, step in pending_ticks:
        ax = axes.get((P3, Q3)) or axes.get((Q3, P3))
        if not check(step != 0, f"{cid}: {pred} -> a tick step cannot be 0", cid):
            pass
        elif ax is None:
            check(False, f"{cid}: {pred} -> there is no `axis {P3}{Q3} from … to …` claim to "
                         f"put ticks on", cid)
        else:
            n = (ax["v1"] - ax["v0"]) / step
            if check(abs(n - round(n)) < 1e-6 and 0 < abs(n) < 10001,
                     f"{cid}: {pred} -> {ax['v1'] - ax['v0']:g} / {step:g} = {n:g}, which must be a "
                     f"positive whole number of steps", cid):
                if ax["step"] is not None:
                    check(False, f"{cid}: {pred} -> one `tick` step per axis — a second would "
                                 f"silently overwrite {ax['step']:g}", cid)
                else:
                    # The step is stored SIGNED toward v1 — a descending axis (`9 to 0`) walks
                    # 9,6,3,0, not 9,12,15 (R7-13).
                    ax["step"] = step if ax["v1"] >= ax["v0"] else -step
    for cid, pred, kind, lo, hi, P3, Q3 in pending_intervals:
        if not all(pt(g, cid) for g in (P3, Q3)):
            continue
        stats["anchor_checked"] += 1
        ax = axes.get((P3, Q3)) or axes.get((Q3, P3))
        if ax is None:
            check(False, f"{cid}: {pred} -> no `axis {P3}{Q3}` claim for this interval", cid)
        else:
            inside = min(ax["v0"], ax["v1"]) - 1e-9 <= lo <= hi <= max(ax["v0"], ax["v1"]) + 1e-9
            check((lo < hi or kind == "closed") and inside,
                  f"{cid}: {pred} -> {'(' if kind == 'open' else '['}{lo:g}, {hi:g}"
                  f"{')' if kind == 'open' else ']'} must be non-empty (an open interval needs "
                  f"lo < hi) and inside [{ax['v0']:g}, {ax['v1']:g}]", cid)

    # 2a. ⚠️ THE SCALE PASS (MAJOR 2, 2026-08-28). `axis` + `tick` DETERMINE every tick's coordinate,
    #     so a numbered scale is fully auditable and used not to be: the two checks it got were
    #     tautologies about literals (`-4 != 5`, `step != 0`) that touched no anchor at all.
    # ⚠️ Two axes (a graph) used to be impossible: every `at` was checked against EVERY axis, so the
    #     y-axis numerals failed the x-axis scale and vice versa (run 8 Q19, 2026-09-05). An `at` now belongs
    #     to the axis whose line it lies nearest (≤ 5% of that axis's span off the line); with one axis nothing changes.
    def nearest_axis(xy):
        best = None
        for (P2, Q2), ax2 in axes.items():
            if P2 not in a or Q2 not in a:
                continue
            sp = dist(a[P2], a[Q2])
            if sp == 0:
                continue
            off = residual(a[P2], xy, a[Q2]) * sp
            if best is None or off < best[0]:
                best = (off, (P2, Q2))
        return best[1] if best else None
    all_expect: set[str] = set()
    checked_ats: set = set()
    for (P, Q), ax in axes.items():
        if P not in a or Q not in a:
            continue
        span = dist(a[P], a[Q])
        if span == 0:
            check(False, f"{ax['cid']}: axis {P}{Q}'s anchors coincide — a zero-length axis "
                         f"carries no scale", ax["cid"])
            continue
        ats_here = [t for t in ats if len(axes) == 1 or nearest_axis(t[2]) == (P, Q)]
        def implied(v, P=P, Q=Q, ax=ax):
            t = (v - ax["v0"]) / (ax["v1"] - ax["v0"])
            return (a[P][0] + t * (a[Q][0] - a[P][0]), a[P][1] + t * (a[Q][1] - a[P][1]))
        # the axis ENDS are, by definition, the anchors of P and Q
        for v, name in ((ax["v0"], P), (ax["v1"], Q)):
            named = [(cid2, xy) for cid2, val, xy in ats_here if abs(val - v) < 1e-9]
            for cid2, xy in named:
                off = dist(xy, a[name])
                check(off <= 0.01 * span,
                      f"{cid2}: at {v:g} -> {off:.2f} from {name}'s anchor "
                      f"({off / span * 100:.2f}% of the axis), and {v:g} IS {name} by the axis claim", cid2)
                checked_ats.add(cid2)
                stats["anchor_checked"] += 1
        # every other `at` must sit where the linear map puts it — and inside the axis's own
        # range: an `at 15` on a −4..5 scale is not a reading, it is a typo the projection
        # alone would happily extrapolate past
        for cid2, v, xy in ats_here:
            check(min(ax["v0"], ax["v1"]) - 1e-9 <= v <= max(ax["v0"], ax["v1"]) + 1e-9,
                  f"{cid2}: at {v:g} -> inside {ax['cid']}'s range "
                  f"[{ax['v0']:g}, {ax['v1']:g}]", cid2)
            if abs(v - ax["v0"]) < 1e-9 or abs(v - ax["v1"]) < 1e-9:
                continue
            want = implied(v)
            off = dist(xy, want)
            check(off <= 0.01 * span,
                  f"{cid2}: at {v:g} -> {off:.2f} from the position {ax['cid']}'s scale implies "
                  f"({want[0]:.1f},{want[1]:.1f}), i.e. {off / span * 100:.2f}% of the axis", cid2)
            checked_ats.add(cid2)
            stats["anchor_checked"] += 1
        # ⚠️ and the LABEL SET must contain the arithmetic sequence the axis + step describe
        if ax["step"] is not None:
            n = int(round((ax["v1"] - ax["v0"]) / ax["step"]))
            want_vals = [ax["v0"] + k * ax["step"] for k in range(n + 1)]
            def fmt(v):
                return f"{v:g}"
            expect = {fmt(v) for v in want_vals}
            all_expect |= expect
    # The printed-numerals verdict is judged once, over every stepped axis's union. Missing
    # numerals are always a defect; EXTRA printed numerals are only a defect when every axis is
    # stepped — an unstepped axis legitimately prints numerals no `tick` predicts (R6-7).
    stepped = [ax2 for ax2 in axes.values() if ax2["step"] is not None]
    if stepped:
        printed = {t for t in cs["labels"] if re.fullmatch(r"-?\d+(\.\d+)?", t)}
        if len(stepped) == len(axes):
            check(printed == all_expect,
                  f"axes: the numeric labels must be the union of every axis's arithmetic "
                  f"sequence — missing {sorted(all_expect - printed) or 'none'}, unexpected "
                  f"{sorted(printed - all_expect) or 'none'}")
        else:
            check(all_expect <= printed,
                  f"axes: the stepped axes' numerals must all be printed — missing "
                  f"{sorted(all_expect - printed) or 'none'} (extra numerals may belong to an "
                  f"unstepped axis, which no `tick` predicts)")
    unchecked_ats = sorted(cid2 for cid2, _, _ in ats if cid2 not in checked_ats)
    check(not unchecked_ats,
          f"every `at` claim has an `axis` to check against, the same way `tick`/`interval` do"
          + (f" — unchecked: {unchecked_ats}" if unchecked_ats else ""))

    # 2b. ⚠️ A LABEL CLAIM MUST NAME A DISTINCT TARGET. The closure check above is glyph -> claim; it
    #     never asked claim -> target, so a claim set could bind NINE numerals of a number line to the
    #     SAME point and pass every assertion. That is an impossible figure reading as audited.
    for c in cs["claims"]:
        if not c["pred"].startswith("label "):
            continue
        m = re.match(r'^label "(.+)" names (\S+)$', c["pred"])
        if not check(bool(m), f"{c['id']}: a label claim is `label \"<glyph>\" names <target>` — "
                              f"got {c['pred']!r} (trailing words are not a target)", c["id"]):
            continue
        # A geometric-name target must be declared — `names Z` (point), `names AB` (segment or
        # two points), `names ABC` (an angle's three points), `names P1` (a digit-suffixed point).
        # `names Z` with Z nowhere in the inventories is the same unbound-name defect as an
        # undeclared point.
        # And claim -> glyph: the printed glyph a `label` claim binds must itself be declared in
        # `labels:` — `label "zz" names B` with no `zz` printed invents ink (R6-9).
        check(m[1] in cs["labels"],
              f"{c['id']}: label glyph {m[1]!r} is declared in `labels:`", c["id"])
        t = m[2]
        if re.fullmatch(r"[A-Z]", t):
            check(t in cs["points"], f"{c['id']}: label target {t} is declared in `points:`", c["id"])
        elif re.fullmatch(r"[A-Z]{2,}", t):
            check(t in cs["segments"] or all(ch in cs["points"] for ch in t),
                  f"{c['id']}: label target {t} is a declared segment or points", c["id"])
        elif re.fullmatch(r"[A-Z]\d+", t):
            check(t in cs["points"], f"{c['id']}: label target {t} is declared in `points:`", c["id"])
        elif re.search(r"[A-Z]", t):
            # `names A1b`, `names A.` — an uppercase-bearing non-shape is a botched geometric
            # name, not a free-form target. All-lowercase stays free-form: `names l` (a line),
            # `names x` (a variable), `names arc` are legitimate non-geometric targets.
            check(False, f"{c['id']}: label target {t!r} is not a declared geometric name "
                         f"(point, segment, or digit-suffixed point)", c["id"])
        label_targets.setdefault(t, []).append((c["id"], m[1]))
    for target, users in sorted(label_targets.items()):
        check(len(users) == 1,
              f"target {target} is named by {len(users)} label claim(s) "
              f"({', '.join(f'{i}={g!r}' for i, g in users)}) — a printed glyph names ONE thing",
              users[0][0] if len(users) == 1 else None)

    # 2c. ⭐ THE ANSWER-SIDE ARITHMETIC CHECK (2026-08-30). See `arith()`'s header: a constructed answer
    #     figure has no page to check against, so the claim set must declare its own arithmetic and the
    #     drawing must land on it. Measured: without this, an arrow drawn 4->5 under an ask of `4 - (-2)`
    #     produced a footer byte-identical to the correct set.
    if eff_channel == "constructed":
        check(bool(derives),
              "a `constructed` claim set carries at least one `derive <expr> = <value>` claim — the "
              "answer's own arithmetic, which is the only ground truth a constructed figure has")

        # 2d. ⭐ THE STEM-JUSTIFICATION CHECK (plugin move, 2026-09-29). Agents author figures with
        #     NO source paper now, so a `ratio`/`angle` claim's value must be justified by the
        #     STEM's own numbers — not by the drawing the claim describes (a claim set and its
        #     drawing can agree and both be wrong). Justification, either door:
        #       (1) a pair of stem numbers a,b (a≠0, b≠0, same number allowed) with
        #           |a/b − v|/v ≤ TOL_RATIO, for a `ratio` claim; a stem number within TOL_ANGLE,
        #           for an `angle` claim; OR
        #       (2) the claim's note cites `derive Kn`, where Kn is a BACKED `derive` claim in
        #           this set whose value matches under the same tolerance. A derive is backed
        #           only if every numeric literal in its expression is itself a stem number,
        #           one of the canonical constants {1, 2, 90, 180, 360} (counts and the angles
        #           a figure may own outright), or the value of another derive in this set
        #           that is itself backed — transitively, no cycles. Without that, an invented
        #           `derive 3 / 2 = 1.5` rescues any copied ratio (review F1).
        #     `right`/`equal`/`axis`/`tick`/`at`/etc are exempt — only `ratio` and `angle` state a
        #     bare value the stem must own.
        stem_nums = [float(x) for x in
                     re.findall(r"\d+(?:\.\d+)?", " ".join(cs["meta"].get("stem", [])))]
        derive_vals = {dcid: dv for dcid, dv in derives}
        derive_by_value: dict = {}
        for dcid, dv in derives:
            derive_by_value.setdefault(dv, []).append(dcid)
        DERIVE_CONSTANTS = (1.0, 2.0, 90.0, 180.0, 360.0)

        def lit_backed(lit: float, dcid: str) -> bool:
            return (any(abs(lit - s) <= 1e-9 for s in stem_nums)
                    or lit in DERIVE_CONSTANTS
                    or any(d2 != dcid and d2 in backed_derives
                           for d2 in derive_by_value.get(lit, ())))

        # backing is a fixpoint: a pure citation cycle never seeds, so neither member backs the
        # other — and a derive may not cite its OWN value (`derive 1.5 = 1.5` proves nothing).
        backed_derives: set = set()
        changed = True
        while changed:
            changed = False
            for dcid, _ in derives:
                if dcid not in backed_derives and \
                        all(lit_backed(l, dcid) for l in derive_literals.get(dcid, ())):
                    backed_derives.add(dcid)
                    changed = True

        def cited_derives(note: str, v: float, rel: bool) -> list:
            """Cited `derive Kn` references whose VALUE matches under the claim's tolerance."""
            hits = []
            for dref in re.findall(r"derive\s+([A-Z]\d+[a-z]?)\b", note):
                dv = derive_vals.get(dref)
                if dv is None:
                    continue
                if (rel and v != 0 and abs(dv - v) / v <= TOL_RATIO) or \
                        (not rel and abs(dv - v) <= TOL_ANGLE):
                    hits.append(dref)
            return hits

        def stem_check(c: dict, v: float, justified: bool, rel: bool) -> None:
            matches = cited_derives(c["note"], v, rel)
            backed = [d for d in matches if d in backed_derives]
            if justified or backed:
                return
            if matches:
                unb = sorted({f"{l:g}" for d in matches
                              for l in derive_literals.get(d, ()) if not lit_backed(l, d)})
                check(False,
                      f"{c['id']}: {c['pred']} -> {v:g} cites `derive "
                      f"{'`, `derive '.join(matches)}`, but its literal(s) "
                      f"{', '.join(unb)} are not backed by the stem (stem numbers "
                      f"{stem_nums}; a derive may only restate stem numbers, the constants "
                      f"1, 2, 90, 180, 360, or a backed derive's value)", c["id"])
            else:
                check(False,
                      f"{c['id']}: {c['pred']} -> {v:g} is not justified by the stem "
                      f"(stem numbers {stem_nums}; drawn ratio copied? — cite a matching "
                      f"`derive` if the value is derived)", c["id"])

        # 2e. TWO DOORS the stem-pair check alone leaves open (the 2026-09-29 cuboid: the stem
        #     states 5, 3 and 2, so the FORGED drawn ratio 1.5 = 3/2 is "stem-justified" — the
        #     claim set and the drawing agreed and both were wrong):
        #       (i)  MIS-CITATION — every `derive Kn` a ratio/angle claim cites must exist AND
        #            match the claim's own value. Citing a derive that says something else is a
        #            false justification, whatever the stem happens to allow.
        #       (ii) LABEL-RATIO — a ratio between two segments that carry NUMERIC labels is
        #            owned by the figure's own printed numbers: `ratio len PQ / len RS = v` with
        #            PQ labelled "5 cm" and RS "2 cm" must claim 2.5, not the drawn 1.5. A
        #            deliberately not-to-scale ratio between labelled segments is adjudicated
        #            in `ambiguous:` like any other contested claim.
        seg_label: dict = {}   # "PQ" -> (number, glyph, claim-id) — orientations tried at use
        for target, users in label_targets.items():
            if not re.fullmatch(r"[A-Z]{2}", target):
                continue
            lm = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[^\d\s]*\s*$", users[0][1])
            if not lm:
                continue
            cid0, glyph0 = users[0][0], users[0][1]
            # (iv) UNDECLARED-TARGET (critic forge2): a numeric label bound to a segment-shaped
            #      name that `segments:` never declares ("5 cm" names AC, a diagonal) dodges the
            #      whole drawn-vs-label machinery — the pair check below cannot see it. The
            #      label may name the segment either way around (DC for the declared CD).
            declared = target in cs["segments"] or target[::-1] in cs["segments"]
            if not check(declared,
                         f"{cid0}: numeric label {glyph0!r} bound to an undeclared segment "
                         f"{target} — declare it in `segments:` so the drawn-vs-label check "
                         f"can measure it", cid0):
                continue
            n = float(lm[1])
            # (v) a printed length of 0 or less is not a length — and a zero would silently
            #     no-op the pair check's ratio denominator.
            if not check(n > 0, f"{cid0}: {target} is labelled {glyph0!r} — a length label "
                                "must be a positive number", cid0):
                continue
            seg_label[target] = (n, glyph0, cid0)
        for c in cs["claims"]:
            if (m := re.match(r"^ratio len ([A-Z])([A-Z]) / len ([A-Z])([A-Z]) = (\d+(?:\.\d+)?)$",
                              c["pred"])):
                v, rel = float(m[5]), True
                if v == 0:
                    continue            # a zero ratio already fails the anchor check above
                justified = any(a_ != 0 and b_ != 0 and abs(a_ / b_ - v) / v <= TOL_RATIO
                                for a_ in stem_nums for b_ in stem_nums)
            elif (m := re.match(r"^angle ([A-Z]) ([A-Z]) ([A-Z]) = (\d+(?:\.\d+)?)$", c["pred"])):
                v, rel = float(m[4]), False
                justified = any(abs(n - v) <= TOL_ANGLE for n in stem_nums)
            else:
                continue
            # (i) every cited derive must exist and state THIS value — not just any derive
            for dref in re.findall(r"derive\s+([A-Z]\d+[a-z]?)\b", c["note"]):
                dv = derive_vals.get(dref)
                ok = dv is not None and ((rel and abs(dv - v) / v <= TOL_RATIO)
                                         or (not rel and abs(dv - v) <= TOL_ANGLE))
                check(ok, f"{c['id']}: {c['pred']} -> cites `derive {dref}`"
                          + (f" (= {dv:g}), matching the claim" if ok
                             else (f" (= {dv:g}), which does not match {v:g} — citing a derive "
                                   f"that says something else is a false justification"
                                   if dv is not None
                                   else ", but no `derive` claim with that id exists")), c["id"])
            # (ii) a ratio between two LABELLED segments must equal their printed numbers
            if rel:
                n1 = seg_label.get(m[1] + m[2]) or seg_label.get(m[2] + m[1])
                n2 = seg_label.get(m[3] + m[4]) or seg_label.get(m[4] + m[3])
                if n1 is not None and n2 is not None and n2[0] != 0:
                    check(abs(n1[0] / n2[0] - v) / v <= TOL_RATIO,
                          f"{c['id']}: {c['pred']} -> the figure labels {m[1]}{m[2]} {n1[1]!r} and "
                          f"{m[3]}{m[4]} {n2[1]!r}, so the drawn ratio must be "
                          f"{n1[0] / n2[0]:g}, not {v:g} (a not-to-scale ratio on labelled "
                          f"segments belongs in `ambiguous:`)", c["id"])
                    stats["anchor_checked"] += 1
            stem_check(c, v, justified, rel)
        # (iii) DRAWN-LENGTH-vs-LABEL pairs (critic forge1): a forge can claim the copied ratio
        #       on the UNLABELLED parallel edge so that (ii) never sees the labelled one. So —
        #       regardless of what any claim names — every PAIR of declared segments carrying
        #       plain-numeric labels must have its DRAWN anchor ratio equal the printed ratio:
        #       the figure's own labels are the ground truth. A deliberately foreshortened edge
        #       (an oblique-projection depth edge) is adjudicated by naming ITS label claim's id
        #       in `ambiguous:`.
        lab_segs = sorted(seg_label.items())
        for i, (s1, (n1, g1, c1)) in enumerate(lab_segs):
            if not (s1[0] in a and s1[1] in a):
                continue
            d1 = dist(a[s1[0]], a[s1[1]])
            for s2, (n2, g2, c2) in lab_segs[i + 1:]:
                if not (s2[0] in a and s2[1] in a) or n2 == 0 or d1 == 0:
                    continue
                d2 = dist(a[s2[0]], a[s2[1]])
                drawn, want = d1 / d2, n1 / n2
                cid = c1 if c1 in adjudicated else c2
                check(abs(drawn - want) / want <= TOL_RATIO,
                      f"labels {c1}/{c2} ({g1!r} on {s1}, {g2!r} on {s2}): the anchors draw "
                      f"len {s1} / len {s2} = {drawn:g} but the printed numbers say {want:g} — "
                      f"the drawing disagrees with its own labels (a deliberately foreshortened "
                      f"edge is adjudicated by naming its label claim in `ambiguous:`)", cid)
                stats["anchor_checked"] += 1
    checked_arrows = set()
    for acid, P, Q in arrows:
        for (P2, Q2), ax in axes.items():
            if P2 not in a or Q2 not in a:
                continue
            # an arrow belongs to the axis its HEAD lies on — projecting it onto every axis makes
            # a diagonal arrow fail the axis it isn't on (and on a multi-derive scale it must land
            # on SOME declared value, not every one: requiring all derives made a multi-part answer
            # figure unwriteable — i18-ans's documented workaround was to avoid `arrow` entirely).
            # An axis with no `tick` still carries a scale — the arrow check must not silently
            # skip just because the label sequence is undeclared (R5-1): tolerance falls back to
            # 2% of the value range.
            if len(axes) > 1 and nearest_axis(a[Q]) != (P2, Q2):
                continue
            span_v = abs(ax["v1"] - ax["v0"])
            tol = abs(ax["step"]) * 0.25 if ax["step"] is not None else span_v * 0.02
            if not span_v:
                continue
            tol_why = "a quarter step" if ax["step"] is not None else \
                      "2% of the range — no `tick` declared"
            v_from = project_value(a[P], a[P2], a[Q2], ax["v0"], ax["v1"])
            v_to = project_value(a[Q], a[P2], a[Q2], ax["v0"], ax["v1"])
            if derives:
                hit = [dcid for dcid, want in derives if abs(v_to - want) <= tol]
                check(bool(hit),
                      f"{acid}: arrow {P} -> {Q} projects onto {ax['cid']}'s scale as "
                      f"{v_from:g} -> {v_to:g} — the move must LAND on a derived value "
                      f"({', '.join(f'{d}={w:g}' for d, w in derives)}; tolerance {tol:g} = "
                      f"{tol_why})", acid)
                stats["anchor_checked"] += 1
                checked_arrows.add(acid)
    stats["recognised_unverifiable"] += [acid for acid, _, _ in arrows if acid not in checked_arrows]

    # 3. arithmetic BETWEEN claims — what a reader with a calculator and no picture can do
    vals: dict = {}
    for c in cs["claims"]:
        m = re.match(r"^angle ([A-Z]) ([A-Z]) ([A-Z]) = (\d+(?:\.\d+)?)$", c["pred"])
        if m:
            vals[(m[1], m[2], m[3])] = (float(m[4]), c["ev"], c["id"])

    def at(p, q, r):
        return vals.get((p, q, r)) or vals.get((r, q, p))

    for (p, q, r), (v, _ev, cid) in list(vals.items()):
        for s in cs["points"]:                                  # angle addition through an inside ray
            if s in (p, q, r):
                continue
            a1, a2 = at(p, q, s), at(s, q, r)
            if a1 and a2 and any(c["pred"] == f"inside {s} angle {p} {q} {r}" for c in cs["claims"]):
                check(abs(a1[0] + a2[0] - v) < TOL_ANGLE,
                      f"{a1[2]} + {a2[2]} = {cid}: {a1[0]} + {a2[0]} vs {v}")

    coll = [re.match(r"^collinear ([A-Z]) ([A-Z]) ([A-Z])$", c["pred"]).groups()
            for c in cs["claims"] if re.match(r"^collinear [A-Z] [A-Z] [A-Z]$", c["pred"])]
    for (p, q, r) in coll:
        for s in cs["points"]:
            v1, v2 = at(p, q, s), at(s, q, r)
            if v1 and v2:
                check(abs(v1[0] + v2[0] - 180) < 0.5 or bool(cs["meta"].get("scale")),
                      f"{v1[2]} + {v2[2]} = {v1[0] + v2[0]:.2f} on the straight line {p}{q}{r} "
                      f"(needs 180, or a `scale:` block — "
                      f"{'present' if cs['meta'].get('scale') else 'MISSING'})")
    for i, (p, q, r) in enumerate(coll):
        for (p2, q2, r2) in coll[i + 1:]:
            if q != q2:
                continue
            v1, v2 = at(p, q, p2), at(r, q, r2)                 # vertically opposite pair
            if v1 and v2:
                check(abs(v1[0] - v2[0]) < 0.5,
                      f"{v1[2]} and {v2[2]} are vertically opposite at {q}: {v1[0]} vs {v2[0]}")

    # 4. scale honesty — a `printed`/`stem` value that disagrees with a `measured` one MUST be declared
    for key, (v, ev, cid) in vals.items():
        if ev in ("printed", "stem"):
            for v2, cid2 in [(v2, cid2) for k2, (v2, ev2, cid2) in vals.items()
                             if ev2 == "measured" and set(k2) == set(key)]:
                if abs(v - v2) > 0.5:
                    check(bool(cs["meta"].get("scale")),
                          f"{cid} ({ev} {v}) disagrees with {cid2} (measured {v2}) -> `scale:` required")

    # 5. evidence discipline
    channel = (cs["meta"].get("channel") or [""])[0]
    from_pixels = channel.startswith("raster") or channel.startswith("mixed")   # ⚠️ M9: mixed too
    zoom_declared = any(ZOOM.search(x) for x in cs["meta"].get("read", []))
    for c in cs["claims"]:
        check(c["ev"] in ("printed", "measured", "stem", "inferred"),
              f"{c['id']}: evidence is one of printed/measured/stem/inferred (got {c['ev']!r})")
        if c["ev"] == "inferred":
            check(bool(c["note"].strip()), f"{c['id']}: an `inferred` claim states its reason")
        if c["ev"] == "measured" and from_pixels:
            check(zoom_declared or bool(ZOOM.search(c["note"])),
                  f"{c['id']}: `measured` on a {channel} channel needs the zoom it was read at — a "
                  f"`read:` header (e.g. `read: 4x`) or a zoom in the note")

    # 6. sufficiency for the ask — EXISTENCE only. See the docstring: the judgement is the agent's.
    #    W12b: a real `ask:` parse, not first-token substring — a line opens a part only when its
    #    first token is a part ref; anything else folds into the previous entry AND fails (one part
    #    per line is the convention — ii07b v1's wrapped ask spawned phantom parts "makes"/"cube"/"8"/"6",
    #    which then passed-or-failed the load-bearing check on substring luck).
    # `load-bearing:` values can carry `#` comments — a cross-ref in a comment (`# per S6a`)
    # is not a claim citation and a commented-out `a ->` entry does not cover part `a`.
    lb = " ".join(v.split("#", 1)[0] for v in cs["meta"].get("load-bearing", []))
    asks: list[str] = []
    for raw_ask in cs["meta"].get("ask", []):
        toks = raw_ask.split(None, 1)
        first = toks[0].rstrip(",;:.") if toks else ""
        if PART_REF.fullmatch(first):
            asks.append(first)
        elif asks:
            check(False, f"ask {asks[-1]}: continuation line {raw_ask[:40]!r} wraps the ask over "
                         f"two lines — ONE part per line; a wrapped ask spawns phantom parts")
        else:
            check(False, f"ask: line does not open with a part ref — {raw_ask[:50]!r}")
    check(bool(asks), "ask: names at least one part")
    seen_parts: set = set()
    fig = (cs["meta"].get("figure") or [""])[0].split()[0] if cs["meta"].get("figure") else ""
    # the figure id is the item scheme — `<letters><digits>` (`i18`, `ii07b`, `fig7`, `item7`,
    # `q7`, `v3`) or a bare/trailing number (`7`, `7b`, `2016-ii07` → 7 — the LAST digit run,
    # not the first: a leading `2016` is a year, not an item)
    # `2016-ii07` -> 7 (last digit-run), `v3.2` -> 3 (letter prefix), `7.2` -> 7 (dotted ids
    # name the item once — the `.2` is a version or sub-fig, not the item number). A bare
    # 4+-digit id is a year/code, not an item number — treat as unnumbered.
    item_m = (re.match(r"^[a-z]+[-_]?(\d+)", fig, re.I)
              or re.match(r"^(\d+)(?:\.\d+)*[a-z]?$", fig)
              or re.search(r"(\d+)(?=[a-z]*$)", fig))
    if item_m and re.fullmatch(r"\d{4,}", fig):
        item_m = None
    for part in asks:
        check(part not in seen_parts, f"ask part {part}: is declared once")
        seen_parts.add(part)
        # the part must key a `load-bearing:` entry (`<part> -> K*`), not merely appear inside a
        # longer token — "a" lives inside "area", "7.b.i" is a prefix of "7.b.ii", and a wrapped
        # ask's stray token is not a real key. Lookarounds not `\b`: `(i)` opens on a non-word char.
        check(re.search(rf"(?<![A-Za-z0-9_.]){re.escape(part)}(?![A-Za-z0-9_.])\s*(?:->|→)", lb),
              f"ask {part}: has a `load-bearing:` claim list (a wrapped continuation whose first "
              f"token still parses as a ref — 'the', 'net', '8' — also lands here; one part per line)")
        # a ref that names a question must name THIS claim set's item — the figure id is the scheme
        num_m = re.match(r"^[IVX]+-?(\d+)", part) or re.match(r"^(\d+)", part)
        if num_m and item_m is None:
            check(False, f"ask part {part}: names question {num_m.group(1)} but figure `{fig}` "
                         f"carries no item number to bind it to — a numberless figure id leaves "
                         f"the ask↔figure link unverifiable")
        elif num_m and item_m:
            check(int(num_m.group(1)) == int(item_m.group(1)),
                  f"ask part {part}: names question {num_m.group(1)} — figure `{fig}` is item "
                  f"{item_m.group(1)} (a wrapped ask's first token can still parse as a ref)")
    ids = {c["id"] for c in cs["claims"]}
    for cited in sorted(set(re.findall(r"\b[A-Z]\d+[a-z]?\b", lb))):
        check(cited in ids, f"load-bearing cites {cited}, which exists")

    # 7. the negative inventory, and the honest half
    check(any(c["pred"].startswith("none ") for c in cs["claims"]),
          "a `none` negative inventory exists (a MISSING mark is as invisible as an invented one)")

    # 8. trail + stale-literal lint (W12c) — `# RE-READ`/`# AUDIT B`/`# DELTA` comment blocks and
    #    `<id>=<number>` literals, checked against the CURRENT anchors and the trail's own items.
    #    ii07b took four Audit-B rounds on exactly these defects.
    def unquoted(l: str) -> str:
        return QUOTED.sub("", l)

    # Trail blocks carry their comment line-numbers so the stale-literal scan can exempt `AUDIT B`
    # lines — a findings report's `K28 3.98 vs anchors 4.0036` is the historical record itself.
    blocks: list[tuple[str, str, list[tuple[int, str]]]] = []
    auditb_lines: set = set()
    for ln, cl in cs.get("comments", []):
        if m := TRAIL_HEAD.match(cl):
            kind = re.sub(r"[\s-]+", "", m.group(1))
            blocks.append((kind, cl.lstrip("# "), []))
            if kind == "AUDITB":
                auditb_lines.add(ln)
        elif blocks:
            blocks[-1][2].append((ln, cl))
            if blocks[-1][0] == "AUDITB":
                auditb_lines.add(ln)
    for kind, hdr, lines in blocks:
        # The stability-vs-edits check applies to CHANGE RECORDS (RE-READ/DELTA) — blocks that both
        # assert what stayed stable AND enumerate the edits they made. An `AUDIT B` block is a
        # findings report: its K-ids+edit-words describe defects to fix, not edits performed.
        if kind == "AUDITB":
            continue
        # A stability claim lives in the block's PREAMBLE — the header plus its continuation lines,
        # up to the first itemised entry. Inside an item, "both claims untouched" is the edit's own
        # detail, not a stability assertion. Quoted spans are stripped everywhere: quoted history
        # is not a claim and a quoted "edit" is not an edit.
        preamble = [hdr]
        for _, l in lines:
            if ITEM_LINE.match(l):
                break
            preamble.append(l)
        # The preamble is scanned as ONE joined string — an `unchanged except` at end-of-line
        # binds the id on the next line (R6-15). Scoping channels:
        #   back  — an exception word BEFORE the match in the same clause (`except K3, K-lines
        #           unchanged`); the ids it names are bound (R6-1).
        #   fwd   — `unchanged except K3` / `except for K3` / `save for K4`; binds ids.
        #   mid   — `K-lines except K3 unchanged` — the exception sits inside the match's word
        #           bridge; binds ids.
        #   impl  — `all else`/`the other`/`the rest`/`otherwise` inside the match — the
        #           exception is implicitly "the items" — scopes but binds nothing.
        # A scoped match CONJOINED to a claim-subject (`K-lines and everything else unchanged`)
        # is still universal on the conjunct — `and`/`with`/`,` before the match means the
        # K-lines part is a plain stability claim (R6-2).
        # Comment markers are stripped and lines joined with `\n`: a phrase split across `#`-lines
        # still matches (a wrapped `K-lines`/`unchanged` is ONE claim), while `\n` stays visible as
        # a boundary for the scope checks below (R7-1).
        decl = lambda l: re.sub(r"^\s*#\s?", "", l)  # noqa: E731 — strip the `# ` marker once
        lu = unquoted("\n".join(decl(l) for l in preamble))
        stable_hits = []
        excepted: set = set()
        EXCEPT_WORD = (r"(?:except|excepting|save|bar|but|other\s+than|apart\s+from|barring|minus)")
        KRANGE = r"\bK(\d+)[a-z]?\s*(?:[–—-]|to|through|thru)\s*K?(\d+)[a-z]?\b"
        # Between an exception word and its claim, only the exception's own object may sit — ids,
        # list punctuation, glue words. `the rest were spot-checked\nK-lines unchanged` has
        # `were`/`spot-checked` in the tail — `rest` belongs to a FINISHED clause, not this claim.
        EXC_TAIL = re.compile(
            r"^(?:[\s,()—–-]|(?:[A-Z]\d+[a-z]?|of|the|as|noted|items?|above|below|for|from|those|"
            r"these|that|than|and|or|&)\b)*$", re.I)

        def bind_ids(txt: str, into: set):
            for lo, hi in re.findall(KRANGE, txt):
                lo_i, hi_i = sorted((int(lo), int(hi)))
                into.update(f"K{k}" for k in range(lo_i, min(hi_i, lo_i + 200) + 1))
            into |= set(re.findall(r"\b[A-Z]\d+[a-z]?\b", re.sub(KRANGE, "", txt)))

        for m in STABLE_CLAIM.finditer(lu):
            pre = lu[max(0, m.start() - 30):m.start()]
            conjoined = re.search(r"(?:K[\s-]*lines?|claims?|assertions?)\s*"
                                  r"(?:,|and\b|&|with|plus)\s*$", pre)
            back_ids: set = set()
            back_scoped = False
            for em in EXCEPTION_SCOPE.finditer(pre):
                tail = pre[em.end():]
                if not EXC_TAIL.match(tail):
                    continue            # `the rest; K-lines unchanged` — a finished clause breaks scope
                back_scoped = True
                bind_ids(tail, back_ids)
            fwd = EXCEPTION_FWD.match(lu[m.end():])
            mid = re.search(EXCEPT_WORD + r"\s+(?:for\s+|the\s+|those\s+|these\s+)*[A-Z]\d",
                            m.group(0))
            # `otherwise` is always an exception ("except as noted"); `else`/`other`/`rest`/
            # `remaining` scope only when the match's SUBJECT is the universal phrase itself —
            # inside a `K-lines …` match they are conjuncts, not exceptions (R6-2).
            impl = re.search(r"\botherwise\b", m.group(0), re.I) or (
                not re.match(r"(?:K[\s-]*lines?|claims?|assertions?)\b", m.group(0), re.I)
                and re.search(r"\b(?:all|everything|the|nothing|what'?s?\s+left)\s+(?:else|other)\b|"
                              r"\b(?:the\s+)?(?:rest|remaining|left)\b", m.group(0), re.I))
            if not (back_scoped or fwd or mid or impl) or conjoined:
                stable_hits.append(m.group(0))
            else:
                excepted |= back_ids
                scan = m.group(0) if mid else ""
                if fwd:
                    # The exception's object ends the clause — `except K3. K4 was verified` binds
                    # K3, not K4. A dash inside a `K3—K5` RANGE is not a boundary. A wrap
                    # continues past `\n` only on a continuation marker (`except`/`,`/`-`/`(`/
                    # glue word at EOL — R6-15/R7-3).
                    seg = lu[m.end():m.end() + 60]
                    rspans = [rm.span() for rm in re.finditer(KRANGE, seg)]
                    stop = len(seg)
                    for i, ch in enumerate(seg):
                        if ch in ".;:!?" or (ch in "—–-" and
                                             not any(a <= i < b for a, b in rspans)):
                            stop = i
                            break
                        if ch == "\n":
                            before = seg[:i].rstrip()
                            if not (re.search(r"[,&–—(-]$", before) or re.search(
                                    r"\b(?:except|excepting|save|bar|but|than|from|barring|minus|"
                                    r"for|the|those|these|that|and|or|other|apart|as)\s*$",
                                    before)):
                                stop = i
                                break
                    scan += seg[:stop]
                bind_ids(scan, excepted)
        # Items, grouped into clauses: a `;` or `,` ends a clause, so `K3 was un-edited; K5
        # corrected` edits K5 only — a group-wide "any verb marks every id" rule flags ids the
        # trail itself says were not touched (R7-12). A clause EDITS on its own unquoted
        # edit-verb or `id -> n` arrow; a clause whose verbs are all negated (`un-edited`,
        # `wasn't corrected`) or that carries a no-change word (`unchanged`, `kept`, `left
        # unchanged`, `is correct`) explicitly does NOT edit its ids. An id in a verb-less
        # clause binds only when another clause in the group edits — `- K3\n  corrected` spans
        # a continuation line. The header is scanned too — a preamble can contradict itself in
        # one line. Id rule: a `K\d+` counts unconditionally (K is the claim namespace); a
        # non-K id must name a real claim, or `S13`/`D9`/`T128`/`B4` cross-refs read as edits.
        edited: set = set()
        groups = [[hdr]] if hdr else []
        for _, l in lines:
            if ITEM_LINE.match(l):
                groups.append([l])
            else:
                groups[-1].append(l)
        for grp in groups:
            whole_raw = "\n".join(decl(l) for l in grp)
            # A quoted span carrying a NUMBER is quoted history (`"K3 -> 1.10" kept for history`);
            # a quoted bare id is emphasis (`"K3" corrected` still edits K3 — R7-12).
            whole_hist = QUOTED.sub(lambda q: "" if re.search(r"\d", q.group(0)) else q.group(0),
                                    whole_raw)
            pend: set = set()
            grp_edit = False
            # A no-change TAIL right after an id/range — `K5 left unchanged`, `K7-K9 reviewed` —
            # exempts that id even inside an editing clause (R6-18, generalised R8-2); a `not`
            # directly BEFORE it (`not K3 but K5 was changed`) does the same.
            NOCH_TAIL = re.compile(
                r"^\s*[,;—–(]?\s*(?:were\s+|was\s+|are\s+|is\s+|remains?\s+|stays?\s+)?"
                r"(?:unchanged|untouched|unedited|unmodified|unaltered|reviewed|verified|"
                r"re-?checked|stable|intact|as[\s-]is|left\s+(?:alone|unchanged|untouched|as[\s-]is)"
                r"|kept|retained|correct|fine|ok(?:ay)?|stands?(?!\s+corrected)|holds?"
                r"|(?:was\s+|were\s+|is\s+|are\s+)?(?:not|never)\s+\w+)\b", re.I)
            NOT_BEFORE = re.compile(r"\b(?:not|never|nor)\s+$", re.I)

            def id_exempt(txt: str, start: int, end: int) -> bool:
                """The id at txt[start:end] is exempt only if its no-change tail SURVIVES to the
                clause end — `K3 verified and corrected` / `K5 not only corrected but
                re-measured` / `K3 stands corrected` still edit (R9-1): a later un-negated edit
                verb, or an `and`/`but`/`then` continuation, cancels the exemption."""
                rest = txt[end:]
                nxt = re.search(r"\b[A-Z]\d+[a-z]?\b", rest)
                rest = rest[:nxt.start()] if nxt else rest   # up to the next id
                if NOT_BEFORE.search(txt[:start]) and not re.match(r"\s*only\b", rest):
                    return not any(not NEGATED.search(rest[:vm.start()]) and
                                   re.search(r"\b(?:but|yet|though|however)\b", rest[:vm.start()])
                                   for vm in EDIT_VERB.finditer(rest))
                tm = NOCH_TAIL.match(rest)
                if not tm or re.match(r"\s*(?:not|never)\s+only\b", rest):
                    return False
                after = rest[tm.end():]
                # a conjunction cancels only with CONTINUATION text behind it — `K3 unchanged and
                # K5 corrected` sliced at K5 leaves a bare ` and `, which joins two statements
                if re.match(r"\s*(?:and|but|then|yet|&)\s+\S", after):
                    return False
                return not any(not NEGATED.search(rest[:vm.start()])
                               for vm in EDIT_VERB.finditer(rest))

            # `.`/`;`/`,` all end a clause — `K3 corrected. K5 left unchanged` is two statements.
            # A `.` inside a number (`1.10`) or an abbreviation (`e.g.`) is not a boundary.
            for clause in re.split(r"[;,]|(?<!\d)(?<!\b[a-z])\.(?!\d)", whole_hist):
                vtext = unquoted(clause)
                vms = list(EDIT_VERB.finditer(vtext))
                c_arrow = any(am.group(1).startswith("K") or am.group(1) in ids
                              for am in re.finditer(r"\b([A-Z]\d+[a-z]?)\s*(?:->|→)\s*[+−-]?\d",
                                                    vtext))
                c_edit = c_arrow or any(not NEGATED.search(vtext[:vm.start()]) for vm in vms)
                grp_edit = grp_edit or c_edit
                c_exempt = (not c_edit) and bool(
                    UNVERB.search(vtext) or NOCHANGE_WORD.search(vtext)
                    or NOT_BEFORE.search(re.split(r"\b[A-Z]\d+[a-z]?\b", vtext)[0] + " ")
                    or (vms and all(NEGATED.search(vtext[:vm.start()]) for vm in vms)))
                here: set = set()
                for rm in re.finditer(KRANGE, clause):
                    if id_exempt(clause, rm.start(), rm.end()):
                        continue
                    lo_i, hi_i = sorted((int(rm[1]), int(rm[2])))
                    here.update(f"K{k}" for k in range(lo_i, min(hi_i, lo_i + 200) + 1))
                wo = re.sub(KRANGE, lambda r_: " " * len(r_.group(0)), clause)
                for im in re.finditer(r"\b[A-Z]\d+[a-z]?\b", wo):
                    n = im.group(0)
                    if not (n.startswith("K") or n in ids):
                        continue
                    if id_exempt(wo, im.start(), im.end()):
                        continue
                    here.add(n)
                if c_edit:
                    edited |= here
                elif not c_exempt:
                    pend |= here
            # `K3, K5, corrected` — the verb sits in an id-less trailing clause; any editing
            # clause in the group binds the verb-less ids (R8-1)
            if grp_edit:
                edited |= pend
        if stable_hits and edited:
            check(False, f"`{hdr.strip()[:60]}` claims {stable_hits[0]!r} while its own items edit "
                         f"{sorted(edited)[:12]} — a trail preamble that disagrees with its recorded "
                         f"deltas is false (ii07b's 'K-lines unchanged')")
        if excepted and (edited - excepted):
            check(False, f"`{hdr.strip()[:60]}` scopes its stability claim to exceptions "
                         f"{sorted(excepted)} but its items also edit "
                         f"{sorted(edited - excepted)[:12]} — a scoped trail claim that disagrees "
                         f"with its recorded deltas is false")
    claims_by_id = {c["id"]: c for c in cs["claims"]}
    stale_sites = [(f"{c['id']}'s note", c["note"]) for c in cs["claims"]]
    # `departures:` records old-vs-new discrepancies and `scale:` declares printed-vs-drawn
    # factors — a literal there is the historical record itself, like an AUDIT B line.
    stale_sites += [(f"{k}: line", v) for k, vals in cs["meta"].items() for v in vals
                    if k not in ("departures", "scale")]
    stale_sites += [(f"comment line {ln}", t) for ln, t in cs.get("comments", [])
                    if ln not in auditb_lines]
    for where, txt in stale_sites:
        txt_u = unquoted(txt)
        for m in STALE_LIT.finditer(txt_u):
            cid = m.group(1) or m.group(3) or m.group(5)
            lit = float((m.group(2) or m.group(4) or m.group(6)).replace("−", "-"))
            # subject position only: in `K5 + K6 = 90.00` the `K6 = 90.00` is the sum, not a
            # K6-literal — reject when the preceding text ends on an operator (incl. the word
            # operators `and`/`plus`/`minus`/`times`/`over`/`&`), or on a comma after a claim id
            # (`K5, K6 = n` is still an expression)
            pre = txt_u[:m.start()]
            # an operator rejects only with an OPERAND before it — `# - K3 -> 90.00`'s bullet `-`
            # and `note - K3`'s dash are not `K6 - ` (R6-6/R7-9): the operand must be an id,
            # a number or a closing bracket, while `K5 + K6 = 90.00`'s `K6 =` is mid-expression
            if (re.search(r"(?:[A-Z]\d+[a-z]?|\d+(?:\.\d+)?|[)\]])\s*[+\-*/÷=≈~×·→−]\s*$", pre)
                    or re.search(r"[A-Z]\d+[a-z]?\s*,\s*$", pre)
                    or re.search(r"(?:\band\b|\bplus\b|\bminus\b|\btimes\b|\bover\b|\bmod\b|"
                                 r"\bdiv\b|&)\s*$", pre)):
                continue
            c = claims_by_id.get(cid)
            if not c or cid in adjudicated:
                continue
            v = anchor_value(c["pred"], c["ev"], a)
            if v is None:
                continue
            value, tol, rel = v
            bad = abs(lit - value) / abs(value) > tol if rel and value else abs(lit - value) > tol
            check(not bad, f"{where}: `{m.group(0)}` vs anchors' {value:g} for {cid} "
                           f"(a literal left behind by re-measurement)")
    return out, fails, stats


# ----------------------------------------------------------------------------------------- self-test
SELF_TEST = """\
figure:   selftest
source:   nowhere.pdf, page 1, bbox [0, 0, 200, 200]
channel:  vector
ask:      a find angle DCE
labels:   A B C D E "7 cm"
points:   A B C D E
segments: AB BC CD CE
anchors:
  A 0 -100
  B 0 0
  C 100 0
  D 150 0
  E 150 50
claims:
  K1  right A B C                | measured | 90.00
  K2  collinear B C D            | measured | ordered along the line
  K3  angle A C B = 45.00        | measured |
  K4  angle A C D = 135.00       | measured |
  K5  label "A" names A          | printed  |
  K6  label "B" names B          | printed  |
  K7  label "C" names C          | printed  |
  K8  label "D" names D          | printed  |
  K9  label "E" names E          | printed  |
  K10 none tick parallel arc arrow shade | printed |
  K11 label "7 cm" names AB      | printed  | a whitespace label, quoted
load-bearing:
  a -> K2, K3
unreadable: (none)
ambiguous:  (none)
"""

# ⚠️ A SECOND fixture, for the class that used to PARSE but not be AUDITED (MAJOR 2): a numbered
# scale. Coordinates follow a published number line's canvas shape, "marked from -4 to 5".
SELF_TEST_SCALE = """\
figure:   selftest-scale
source:   a published number line, canvas 760x120 (synthetic coordinates)
channel:  vector
ask:      a read the integers marked on the line
labels:   -4 -3 -2 -1 0 1 2 3 4 5
points:   P Q
segments: PQ
anchors:
  P 42.2 60
  Q 690.6 60
claims:
  K1  axis PQ from -4 to 5       | printed  |
  K2  tick PQ step 1             | printed  |
  K3  at -4 42.2 60              | measured |
  K4  at 5 690.6 60              | measured |
  K5  at 0 330.2 60              | measured | 0.18 off the implied position: the live figure rounds
                                             its tick pitch to 72.0 where the ends imply 72.044
  K6  label "-4" names -4        | printed  |
  K7  label "-3" names -3        | printed  |
  K8  label "-2" names -2        | printed  |
  K9  label "-1" names -1        | printed  |
  K10 label "0" names 0          | printed  |
  K11 label "1" names 1          | printed  |
  K12 label "2" names 2          | printed  |
  K13 label "3" names 3          | printed  |
  K14 label "4" names 4          | printed  |
  K15 label "5" names 5          | printed  |
  K16 none tickMark parallelMark angleArc shaded | printed | the axis DOES carry an arrowhead
load-bearing:
  a -> K1, K2
unreadable: (none)
ambiguous:  (none)
"""

SCALE_MUTATIONS = [
    ("every numeral bound to ONE target",   'names -3', 'names -4'),
    ("a numeral missing from the sequence",  'labels:   -4 -3 -2 -1 0 1 2 3 4 5', 'labels:   -4 -3 -2 -1 0 1 2 4 5'),
    ("an `at` position 5% off the scale",    'at 0 330.2 60', 'at 0 300.0 60'),
    ("a tick step that does not divide",     'tick PQ step 1', 'tick PQ step 2'),
    ("a second `axis` on the same segment (reversed order is still a dup)",
     "K2  tick PQ step 1", "K2  axis QP from 5 to -4    | printed  |\n  K2a tick PQ step 1             | printed  |"),
    ("a second `tick` on an axis silently overwrites the first",
     "K3  at -4 42.2 60", "K3  tick PQ step 1             | printed  |\n  K3b at -4 42.2 60              | measured |"),
    ("`tick QP` resolves `axis PQ` — a step is direction-free (must PASS)",
     "K2  tick PQ step 1", "K2  tick QP step 1"),
    ("ticks with no axis claim",             'K1  axis PQ from -4 to 5       | printed  |', 'K1  paint PQ solid             | printed  |'),
    ("an interval outside the axis",         'K16 none', 'K17 interval closed 3 to 9 on PQ | printed |\n  K16 none'),
]

# ⭐ THE CONSTRUCTED (ANSWER-SIDE) FIXTURE, added 2026-08-30 with check 2c.
# ⚠️ WHY IT EXISTS, measured: a critique authored an internally consistent claim set for an answer figure
# whose arrow lands on **5** where the ask is `4 - (-2)`, and this tool reported **78 assertions, 0
# failures, exit 0 — a footer BYTE-IDENTICAL to the correct set.** Both doors are now shut, and both are
# exercised below. Coordinates follow a published number line's canvas shape, extended for an answer.
# `stem:` (added 2026-09-29): required on a constructed set — it is the text the numbers come from.
SELF_TEST_CONSTRUCTED = """\
figure:   selftest-constructed-6
source:   ANSWER-SIDE, CONSTRUCTED. Extends a published question figure; frame is its own canvas.
channel:  constructed
stem:     The number line shows the integers from -3 to 7. Using the number line, find the
          value of 4 - (-2).
ask:      6 the value of 4 - (-2), worked on the number line the stem names
labels:   -3 -2 -1 0 1 2 3 4 5 6 7 "+2"
points:   P Q S T
segments: PQ ST
anchors:
  P 63.8 107.9
  Q 441.8 107.9
  S 328.5 63.3
  T 403.7 63.3
claims:
  K1  axis PQ from -3 to 7      | printed  |
  K2  tick PQ step 1            | printed  |
  K3  at -3 63.8 107.9          | printed  |
  K4  at 7 441.8 107.9          | printed  |
  K5  label "-3" names -3       | printed  |
  K6  label "-2" names -2       | printed  |
  K7  label "-1" names -1       | printed  |
  K8  label "0" names 0         | printed  |
  K9  label "1" names 1         | printed  |
  K10 label "2" names 2         | printed  |
  K11 label "3" names 3         | printed  |
  K12 label "4" names 4         | printed  |
  K13 label "5" names 5         | printed  |
  K14 label "6" names 6         | printed  |
  K15 label "7" names 7         | printed  |
  K16 arrow S -> T              | inferred | the answer-side addition: two unit steps right from 4
  K17 label "+2" names ST       | inferred | names the move
  K18 derive 4 - (-2) = 6       | inferred | the answer's own arithmetic — the ground truth 2c projects
                                            K16's arrow against
  K19 none tickMark parallelMark angleArc shaded | printed |
load-bearing:
  6 -> K1, K2, K16, K18
unreadable: (none)
ambiguous:  (none)
"""

CONSTRUCTED_MUTATIONS = [
    # ⛔ the exact figure a critique built: the arrow lands on 5, the arithmetic still says 6.
    ("the arrow LANDS ON THE WRONG VALUE (draws 5, claims 6)", "  T 403.7 63.3", "  T 365.9 63.3", False),
    # ⛔ the consistent liar: draws 5 AND claims 5, so nothing is internally contradictory.
    ("the arithmetic is WRONG (draws 5, claims 5)", "  T 403.7 63.3", "  T 365.9 63.3", True),
    ("`derive` deleted from a constructed claim set", "  K18 derive 4 - (-2) = 6", "  K18 paint PQ solid", False),
    ("`derive`'s expression is not arithmetic", "derive 4 - (-2) = 6", "derive the answer = 6", False),
    # --- plugin move, 2026-09-29: the `stem:` header and the optional channel ---
    ("`stem:` deleted from a constructed claim set",
     "stem:     The number line shows the integers from -3 to 7. Using the number line, find the\n"
     "          value of 4 - (-2).\n", "", False),
    ("missing `channel:` defaults to `constructed` (must PASS)",
     "channel:  constructed\n", "", False),
]

# ⭐ THE STEM-RATIO FIXTURE (plugin move, 2026-09-29). A CONSTRUCTED question figure — a cuboid face —
# whose `ratio` claim states the value the CANVAS was drawn at (1.5), not the value the STEM states
# (5 cm × 2 cm → 2.5). Anchors agree with the claim, so every check the pre-plugin tool ran passes;
# only the stem-justification check (2d) catches that no pair of stem numbers gives 1.5. This is the
# planted-bad baseline: it MUST fail, and the failure must cite K2.
# ⚠️ Since R1 (the label-ratio check, 2e-ii): the same 1.5 ALSO fails because the LABELS say 5:2 —
# a stem that HAPPENS to name 3 and 2 can no longer rescue the drawn ratio on labelled segments.
SELF_TEST_STEM_RATIO = """\
figure:   selftest-stem-ratio-1
source:   constructed; frame is the question figure's own canvas
channel:  constructed
stem:     A cuboid has a rectangular face 5 cm long and 2 cm wide.
ask:      1 the ratio of the face's length to its width
labels:   A B C D "5 cm" "2 cm"
points:   A B C D
segments: AB BC CD DA
anchors:
  A 60 40
  B 210 40
  C 210 140
  D 60 140
claims:
  K1  right A B C                 | stem     | the face is a rectangle
  K2  ratio len AB / len BC = 1.5 | stem     | the drawn ratio — copied from the canvas, not the stem
  K3  label "A" names A           | printed  |
  K4  label "B" names B           | printed  |
  K5  label "C" names C           | printed  |
  K6  label "D" names D           | printed  |
  K7  label "5 cm" names AB       | stem     | the stem's own length
  K8  label "2 cm" names BC       | stem     | the stem's own width
  K9  derive 5 / 2 = 2.5          | inferred | the ratio the stem actually states
  K10 none tickMark parallelMark angleArc arrow shaded | printed |
load-bearing:
  1 -> K2
unreadable: (none)
ambiguous:  (none)
"""

STEM_RATIO_MUTATIONS = [
    # (name, [(old, new), ...], must_pass)
    ("the corrected set — anchors and claim at the stem's own 2.5 (must PASS)",
     [("  B 210 40", "  B 310 40"), ("  C 210 140", "  C 310 140"),
      ("ratio len AB / len BC = 1.5", "ratio len AB / len BC = 2.5")], True),
    ("the wrong ratio citing a BACKED `derive` STILL fails — stem 3:2 justifies it, but the "
     "labels say 5:2 (the label-ratio door, 2e-ii)",
     [("stem:     A cuboid has a rectangular face 5 cm long and 2 cm wide.",
       "stem:     A cuboid has a rectangular face 5 cm long and 2 cm wide, divided in the "
       "ratio 3 : 2."),
      ("K9  derive 5 / 2 = 2.5", "K9  derive 3 / 2 = 1.5"),
      ("the drawn ratio — copied from the canvas, not the stem",
       "the face's 3:2 division, per derive K9")], False),
    ("the wrong ratio rescued by an UNBACKED `derive` (fails — the literal 3 is no stem number)",
     [("K9  derive 5 / 2 = 2.5", "K9  derive 3 / 2 = 1.5"),
      ("the drawn ratio — copied from the canvas, not the stem",
       "the face's drawn proportions, per derive K9")], False),
    ("a `derive` chain — backed via another derive's value — STILL fails against the labels "
     "(2e-ii)",
     [("stem:     A cuboid has a rectangular face 5 cm long and 2 cm wide.",
       "stem:     A cuboid has a rectangular face 5 cm long and 2 cm wide, with a mark every "
       "3 cm along the face."),
      ("K9  derive 5 / 2 = 2.5          | inferred | the ratio the stem actually states",
       "K9  derive 3 / 2 = 1.5          | inferred | the stem's mark spacing\n"
       "  K11 derive 1.5 * 1 = 1.5        | inferred | restates K9"),
      ("the drawn ratio — copied from the canvas, not the stem",
       "the face's drawn proportions, per derive K11")], False),
    ("a `derive` cited but with a NON-matching value (still fails — mis-citation, 2e-i)",
     [("the drawn ratio — copied from the canvas, not the stem",
       "the face's drawn proportions, per derive K9")], False),
    ("a `derive` cited that does not exist at all (still fails — mis-citation, 2e-i)",
     [("the drawn ratio — copied from the canvas, not the stem",
       "the face's drawn proportions, per derive K99")], False),
    ("the corrected set citing the MATCHING derive (must PASS) — label-ratio and stem agree",
     [("  B 210 40", "  B 310 40"), ("  C 210 140", "  C 310 140"),
      ("ratio len AB / len BC = 1.5 | stem     | the drawn ratio — copied from the canvas, not "
       "the stem",
       "ratio len AB / len BC = 2.5 | stem     | the stem's ratio, per derive K9")], True),
    ("a deliberately not-to-scale ratio on labelled segments, ADJUDICATED in `ambiguous:` "
     "(must PASS — a contested claim is written down, not hidden; the label claim's id is what "
     "adjudicates the drawn-vs-label pair)",
     [("ambiguous:  (none)",
       "ambiguous:\n  K2, K7 - the face is drawn 1.5:1 for readability while the labels state "
       "5 cm : 2 cm — deliberately not to scale")], True),
    # ⭐ CRITIC R3 — the parallel-edge door: labels moved onto the parallel DC/DA while the claim
    # rides the UNLABELLED AB/BC, anchors drawn 1.5, a BACKED `derive 3 / 2` (3 and 2 are stem
    # numbers). Checks 2d/2e-i/2e-ii all pass it — only the anchor-vs-label PAIR check (2e-iii)
    # sees that the DRAWN DC/DA disagree with their own printed "5 cm"/"2 cm".
    ("the forged ratio claimed on the UNLABELLED parallel edge — drawn-vs-labels pair check "
     "(2e-iii) still sees the printed numbers disagree with the anchors (fails)",
     [("stem:     A cuboid has a rectangular face 5 cm long and 2 cm wide.",
       "stem:     A cuboid is 5 cm long, 3 cm wide and 2 cm high."),
      ("K7  label \"5 cm\" names AB", "K7  label \"5 cm\" names DC"),
      ("K8  label \"2 cm\" names BC", "K8  label \"2 cm\" names DA"),
      ("K9  derive 5 / 2 = 2.5", "K9  derive 3 / 2 = 1.5"),
      ("the drawn ratio — copied from the canvas, not the stem",
       "the front-face ratio, per derive K9")], False),
    # ⭐ CRITIC R4 — the labels bound to names `segments:` never declared (AC is a DIAGONAL here):
    # the pair check can only measure declared segments, so the binding itself must fail.
    ("a numeric label on a name `segments:` never declared (2e-iv — the diagonal dodge, fails)",
     [("  B 210 40", "  B 310 40"), ("  C 210 140", "  C 310 140"),
      ("ratio len AB / len BC = 1.5", "ratio len AB / len BC = 2.5"),
      ("K7  label \"5 cm\" names AB", "K7  label \"5 cm\" names AC")], False),
    # and a non-positive printed length is not a length at all — the zero would silently no-op
    # the pair check's denominator
    ("a ZERO numeric label on a segment (2e-v — not a length, fails)",
     [("K8  label \"2 cm\" names BC", "K8  label \"0 cm\" names BC"),
      ('"2 cm"', '"0 cm"')], False),
    ("`stem:` deleted — no ground truth to justify anything (fails)",
     [("stem:     A cuboid has a rectangular face 5 cm long and 2 cm wide.\n", "")], False),
]

MUTATIONS = [
    ("a claim: collinear -> a point not on the line",  "collinear B C D",   "collinear B C E"),
    ("an anchor: C moved off the line",                "  C 100 0",         "  C 100 9"),
    ("a claimed angle value",                          "angle A C B = 45.00", "angle A C B = 60.00"),
    ("a label left unbound",                           'K9  label "E" names E', 'K9  free-text "E" beside CE'),
    ("the negative inventory removed",                 "K10 none tick parallel arc arrow shade", "K10 paint AB solid"),
    # ⚠️ B1: the separators removed. This MUST be a parse error, not a silent deletion.
    ("a claim's `|` separators removed (B1)",          "K3  angle A C B = 45.00        | measured |",
                                                       "K3  angle A C B = 45.00          measured"),
    # ⚠️ M10: fail closed.
    ("an unknown predicate",                           "K2  collinear B C D",  "K2  perpendicularish B C D"),
    ("a recognised predicate with bad arguments",       "K3  angle A C B = 45.00", "K3  angle ACB = 45.00"),
    # ⚠️ M2: a wrapped inventory must not be truncated.
    ("a point declared on a WRAPPED inventory line",   "points:   A B C D E", "points:   A B C\n          D E"),
    # ⚠️ M1: a quoted whitespace label must stay one token.
    ("a quoted label left unbound",                    'K11 label "7 cm" names AB', 'K11 paint AB solid'),
    # --- W12 round-5/6 gates ---
    ("a second `figure:` header silently loses the first",
     "figure:   selftest", "figure:   selftest\nfigure:   selftest2"),
    ("a typo'd channel fails closed",                  "channel:  vector", "channel:  vactor"),
    ("a degenerate claim — one point named twice",     "K2  collinear B C D", "K2  collinear B C C"),
    ("`equal` on the same segment twice is vacuous",   "K2  collinear B C D", "K2  equal AB AB"),
    ("a zero-radius circle",                           "K2  collinear B C D", "K2  circle centre B radius 0"),
    ("a `label` claim binding a glyph absent from `labels:`",
     'K5  label "A" names A', 'K5  label "zz" names B'),
    ("`names` on an uppercase non-shape (a botched target)",
     'K8  label "D" names D', 'K8  label "D" names D.'),
    ("`equal` on adjacent segments sharing an endpoint is legal (must PASS)",
     "K2  collinear B C D", "K2  equal AB BC"),
    # a comparative is a CLAIM: step 2 shipped "steeper" on gradients of 1.73 vs 4.02.
    ("a false `steeper than` comparative",             "K2  collinear B C D",  "K2  gradient CD steeper than CE"),
    # ⚠️ MAJOR 3: a contested claim with NO `ambiguous:` entry must still be a hard FAIL.
    ("a contested claim not named in `ambiguous:`",     "K2  collinear B C D",  "K2  collinear B C E"),
]

# ⚠️ And the inverse, which must NOT fail: the same broken claim, declared in `ambiguous:`.
ADJUDICATION_CASE = (("K2  collinear B C D", "K2  collinear B C E"),
                     ("ambiguous:  (none)", "ambiguous:  K2 - contested: 0.7% off, 1.25 printed stroke widths"))


# ⭐ THE GRAPH FIXTURE (two axes), added 2026-09-05 after run 8 Q19's distance–time graph could not be
# claimed: every `at` was checked against every `axis`, so the y-axis numerals failed the x-axis scale.
# An `at` now belongs to the axis whose line it lies nearest, and the label set is judged as the union.
SELF_TEST_GRAPH = """\
figure:   selftest-graph
source:   run 8 Q19 shape, canvas 320x260
channel:  vector
ask:      a the speed from the graph
labels:   0 2 4 6 8 10 100 200 300
points:   O X Y T
segments: OX OY OT
anchors:
  O 60 220
  X 260 220
  Y 60 70
  T 260 70
claims:
  K1  axis OX from 0 to 10       | printed  |
  K2  tick OX step 2             | printed  |
  K3  axis OY from 0 to 300      | printed  |
  K4  tick OY step 100           | printed  |
  K5  at 0 60 220                | measured |
  K6  at 4 140 220               | measured |
  K7  at 10 260 220              | measured |
  K8  at 100 60 170              | measured |
  K9  at 300 60 70               | measured |
  K10 label "0" names 0          | printed  |
  K11 label "2" names 2          | printed  |
  K12 label "4" names 4          | printed  |
  K13 label "6" names 6          | printed  |
  K14 label "8" names 8          | printed  |
  K15 label "10" names 10        | printed  |
  K16 label "100" names 100      | printed  |
  K17 label "200" names 200      | printed  |
  K18 label "300" names 300      | printed  |
  K19 right X O Y                | printed  |
  K20 none tickMark parallelMark angleArc shaded | printed |
load-bearing:
  a -> K1, K3, K6, K8
unreadable: (none)
ambiguous:  (none)
"""
GRAPH_MUTATIONS = [
    ("a y-axis `at` moved off its own scale (must FAIL)", "K8  at 100 60 170", "K8  at 100 60 150"),
    ("an x-axis numeral missing from labels (must FAIL)", "labels:   0 2 4 6 8 10 100 200 300", "labels:   0 2 4 8 10 100 200 300"),
]

# W12 fixture — an ii07b-shaped set with a trail. Anchors give AB/BC = 2.00, right at B = 90°.
SELF_TEST_TRAIL = """\
figure:   ii07b
source:   p5
channel:  raster
read:     4x
ask:      7.b.i  what solid the net makes
          7.b.ii edges and vertices
          7.b.iii area of one face
labels:   A B C
points:   A B C
segments: AB BC
anchors:
  A 10 10
  B 10 50
  C 30 50
claims:
  K1  label "A" names A          | printed  |
  K2  label "B" names B          | printed  |
  K3  ratio len AB / len BC = 2.00 | measured | K3=2.00 recorded
  K4  right A B C                | printed  |
  K5  none other                 | measured |
  K6  label "C" names C          | printed  |
load-bearing:
  7.b.i -> K1, K2
  7.b.ii -> K3
  7.b.iii -> K4
unreadable: (none)
ambiguous:  (none)

# RE-READ v1 — initial pass, K-lines byte-stable
# AUDIT B v1 — exit 0
# DELTA v1 — none needed
"""
TRAIL_MUTATIONS = [
    ("a wrapped ask continuation (ii07b v1's phantom 'makes'/'cube'/'8'/'6')",
     "ask:      7.b.i  what solid the net makes",
     "ask:      7.b.i  what solid the net\n          makes when folded into a cube"),
    ("an ask part naming the WRONG item (a wrapped token that still parses as a ref)",
     "          7.b.ii edges and vertices",
     "          8.b.ii edges and vertices"),
    ("a `RE-READ` preamble claiming stability while its items edit K-lines (ii07b v3)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged\n#   item G: K13 note tail corrected per adjudication"),
    ("a stale `K*→<number>` literal vs current anchors (K28's 3.98)",
     "measured | K3=2.00 recorded", "measured | K3=1.10 recorded"),
    ("an item marker in lowercase (`# g:`) still ends the preamble",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged\n# g: K13 note corrected"),
    # --- must-PASS shapes: the lint must not flag honest trails or idiomatic arithmetic
    ("a `Kx + Ky = n` sum in a note is not a Ky-literal (must PASS)",
     "measured | K3=2.00 recorded", "measured | K1 + K3 = 3.00, so the segments sum"),
    ("an item saying a claim is `unchanged` is not an edit (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v1 — K-lines byte-stable\n# G: K13 unchanged — revisited, left as printed"),
    ("an exception-scoped preamble is honest (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v1 — all other K-lines unchanged\n# G: K13 note corrected"),
    ("a predicate-scoped preamble is honest (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v1 — K-line predicates/verdicts byte-stable\n# G: K13 note corrected"),
    ("a stale literal quoted as history is not a claim (must PASS)",
     "measured | K3=2.00 recorded", "measured | old \"K3=1.10\" was stale; K3=2.00 now"),
    # --- W12c round-5/6: exception binding, hyphenated negations, bullet literals
    ("`unchanged except K3` while editing K5 — the exception binds",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged except K3\n# G: K5 note corrected"),
    ("`unchanged except K3` while editing K3 — the honest case (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged except K3\n# G: K3 note corrected"),
    ("`except K3, K-lines unchanged` — a pre-position named exception binds",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — except K3, K-lines unchanged\n# G: K5 corrected"),
    ("`K-lines and everything else unchanged` is universal on the conjunct",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines and everything else unchanged\n# G: K3 corrected"),
    ("a hyphenated negated edit inside an item is not an edit (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged\n# G: no K-lines were changed"),
    ("an `e.g.` line does not end the preamble — the claim below still scans",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2\n# e.g. noted earlier\n# K-lines unchanged\n# G: K3 corrected"),
    ("a bullet `-` is not an expression operator — `# - K3 -> 1.10` is stale",
     "# DELTA v1 — none needed",
     "# DELTA v2\n# - K3 -> 1.10"),
    ("a possessive `K3's <n>` literal is stale",
     "measured | K3=2.00 recorded", "measured | K3's 1.10 was recorded once"),
    ("`K3 remains <n>` — a stale-literal connector",
     "measured | K3=2.00 recorded", "measured | K3 remains 1.10"),
    # --- W12c round-8: clause-split regression probes
    ("a serial-comma list whose verb trails in an id-less clause still edits",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged\n# - K3, K5, corrected"),
    ("a `.` ends an item's clause — `K5 left unchanged` is not an edit (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged except K3\n# - K3 corrected. K5 left unchanged"),
    ("a `not K3 but K5` contrastive exempts the negated id (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged except K5\n# - not K3 but K5 was changed"),
    ("a `K-lines`/`unchanged` wrap across `#`-lines is ONE claim",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines\n#   unchanged\n# - K3 corrected"),
    ("a `.` ends the forward exception — `except K3. K4 was verified` binds K3 only",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged except K3. K4 was verified\n# - K4 corrected"),
    ("`no K-line changes` is a stability claim",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — no K-line changes\n# - K3 corrected"),
    ("`no content change` is about TEXT, not K-lines (must PASS)",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — no content change\n# - K3 corrected"),
    # --- W12c round-9: a no-change tail must SURVIVE to the clause end
    ("`K3 verified and corrected` — the `verified` tail does not exempt an id that was then edited",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged\n# - K3 verified and corrected"),
    ("`K5 not only corrected but re-measured` — `not only` is not a negation",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged\n# - K5 not only corrected but re-measured"),
    ("`K3 stands corrected` — the idiom records an edit",
     "# RE-READ v1 — initial pass, K-lines byte-stable",
     "# RE-READ v2 — K-lines unchanged\n# - K3 stands corrected"),
]

def self_test() -> int:
    print("--- baseline (must PASS)")
    out, fails, stats = audit(parse(SELF_TEST))
    print(f"    {len(out)} assertions, {fails} failures, {stats['claims']} claims parsed, "
          f"{stats['anchor_checked']} anchor-checked")
    bad = 0
    if fails:
        print("\n".join(l for l in out if l.startswith("  FAIL")))
        print("  SELF-TEST BROKEN: the clean fixture must pass")
        bad += 1
    print("\n--- F-CLAIM mutations (each must FAIL or die, or this tool is decorative)")
    for name, old, new in MUTATIONS:
        if old not in SELF_TEST:
            print(f"    STALE     mutation no longer applies: {name}")
            bad += 1
            continue
        text = SELF_TEST.replace(old, new, 1)
        try:
            out, fails, _ = audit(parse(text))
        except SystemExit as exc:
            print(f"    caught (parse error, exit {exc.code})   <- {name}")
            continue
        # ⚠️ M2's mutation is a WRAPPED-but-valid inventory: it must still PASS. Everything else fails.
        want_pass = "WRAPPED" in name or "(must PASS)" in name
        ok = (fails == 0) if want_pass else (fails > 0)
        print(f"    {'ok      ' if ok else 'MISSED  '} {fails:>2} failure(s)  <- {name}"
              f"{'  (this one must PASS)' if want_pass else ''}")
        if not ok:
            bad += 1
            print("      " + "\n      ".join(out))
    print("\n--- the SCALE fixture (a numbered scale: parses AND is audited, since 2026-08-28)")
    out, fails, stats = audit(parse(SELF_TEST_SCALE))
    print(f"    baseline: {len(out)} assertions, {fails} failures, {stats['anchor_checked']} anchor-checked")
    if fails:
        print("\n".join(l for l in out if l.startswith("  FAIL")))
        bad += 1
    for name, old_s, new_s in SCALE_MUTATIONS:
        if old_s not in SELF_TEST_SCALE:
            print(f"    STALE     {name}")
            bad += 1
            continue
        text = SELF_TEST_SCALE.replace(old_s, new_s) if "ONE target" in name else SELF_TEST_SCALE.replace(old_s, new_s, 1)
        try:
            out, fails, _ = audit(parse(text))
        except SystemExit as exc:
            print(f"    caught (parse error, exit {exc.code})   <- {name}")
            continue
        want_pass = "(must PASS)" in name
        ok = (fails == 0) if want_pass else fails > 0
        print(f"    {'ok      ' if ok else 'MISSED  '} {fails:>2} failure(s)  <- {name}")
        if not ok:
            bad += 1

    print("\n--- the GRAPH fixture (two axes: each `at` judged against its own axis, since 2026-09-05)")
    out, fails, stats = audit(parse(SELF_TEST_GRAPH))
    print(f"    baseline: {len(out)} assertions, {fails} failures, {stats['anchor_checked']} anchor-checked")
    if fails:
        print("\n".join(l for l in out if l.startswith("  FAIL")))
        bad += 1
    for name, old_g, new_g in GRAPH_MUTATIONS:
        if old_g not in SELF_TEST_GRAPH:
            print(f"    STALE     {name}")
            bad += 1
            continue
        out, fails, _ = audit(parse(SELF_TEST_GRAPH.replace(old_g, new_g, 1)))
        print(f"    {'ok      ' if fails else 'MISSED  '} {fails:>2} failure(s)  <- {name}")
        if not fails:
            bad += 1

    print("\n--- the TRAIL fixture (W12b ask grammar + W12c trail/stale-literal lint)")
    out, fails, stats = audit(parse(SELF_TEST_TRAIL))
    print(f"    baseline: {len(out)} assertions, {fails} failures")
    if fails:
        print("\n".join(l for l in out if l.startswith("  FAIL")))
        bad += 1
    for name, old_t, new_t in TRAIL_MUTATIONS:
        if old_t not in SELF_TEST_TRAIL:
            print(f"    STALE     {name}")
            bad += 1
            continue
        try:
            out, fails, _ = audit(parse(SELF_TEST_TRAIL.replace(old_t, new_t, 1)))
        except SystemExit as exc:
            print(f"    caught (parse error, exit {exc.code})   <- {name}")
            continue
        want_pass = "(must PASS)" in name
        ok = (fails == 0) if want_pass else (fails > 0)
        print(f"    {'ok      ' if ok else 'MISSED  '} {fails:>2} failure(s)  <- {name}")
        if not ok:
            bad += 1
            print("      " + "\n      ".join(l for l in out if l.startswith("  FAIL")))

    print("\n--- the CONSTRUCTED fixture (an ANSWER-side figure: check 2c, since 2026-08-30)")
    out, fails, stats = audit(parse(SELF_TEST_CONSTRUCTED))
    print(f"    baseline: {len(out)} assertions, {fails} failures, {stats['anchor_checked']} anchor-checked")
    if fails:
        print("\n".join(l for l in out if l.startswith("  FAIL")))
        bad += 1
    for name, old_c, new_c, also_lie in CONSTRUCTED_MUTATIONS:
        if old_c not in SELF_TEST_CONSTRUCTED:
            print(f"    STALE     {name}")
            bad += 1
            continue
        text = SELF_TEST_CONSTRUCTED.replace(old_c, new_c, 1)
        if also_lie:
            text = text.replace("derive 4 - (-2) = 6", "derive 4 - (-2) = 5", 1)
        try:
            out, fails, _ = audit(parse(text))
        except SystemExit as exc:
            print(f"    caught (parse error, exit {exc.code})   <- {name}")
            continue
        want_pass = "(must PASS)" in name
        ok = (fails == 0) if want_pass else fails > 0
        print(f"    {'ok      ' if ok else 'MISSED  '} {fails:>2} failure(s)  <- {name}")
        if not ok:
            bad += 1
            print("      " + "\n      ".join(l for l in out if l.startswith("  FAIL")))

    print("\n--- the STEM-RATIO fixture (a constructed QUESTION figure; the stem is the only ground "
          "truth — the planted-bad set must FAIL, citing K2)")
    out, fails, stats = audit(parse(SELF_TEST_STEM_RATIO))
    print(f"    baseline: {len(out)} assertions, {fails} failure(s)")
    bad_cites = [l for l in out if l.startswith("  FAIL") and "K2" in l and "stem" in l]
    print("      " + "\n      ".join(l for l in out if l.startswith("  FAIL")))
    if not (fails > 0 and bad_cites):
        bad += 1
        print("      SELF-TEST BROKEN: the planted-bad fixture must FAIL and the failure must cite K2")
    for name, replacements, want_pass in STEM_RATIO_MUTATIONS:
        text = SELF_TEST_STEM_RATIO
        stale = [old for old, _ in replacements if old not in text]
        if stale:
            print(f"    STALE     {name}: {stale[0][:50]!r} not in fixture")
            bad += 1
            continue
        for old, new in replacements:
            text = text.replace(old, new, 1)
        try:
            out, fails, _ = audit(parse(text))
        except SystemExit as exc:
            print(f"    caught (parse error, exit {exc.code})   <- {name}")
            bad += 0 if not want_pass else 1
            continue
        ok = (fails == 0) if want_pass else fails > 0
        print(f"    {'ok      ' if ok else 'MISSED  '} {fails:>2} failure(s)  <- {name}")
        if not ok:
            bad += 1
            print("      " + "\n      ".join(l for l in out if l.startswith("  FAIL")))

    print("\n--- adjudication (MAJOR 3): the SAME broken claim, undeclared then declared")
    (c_old, c_new), (a_old, a_new) = ADJUDICATION_CASE
    undeclared = SELF_TEST.replace(c_old, c_new, 1)
    declared = undeclared.replace(a_old, a_new, 1)
    _, f_un, s_un = audit(parse(undeclared))
    _, f_de, s_de = audit(parse(declared))
    ok = f_un > 0 and f_de == 0 and len(s_de["adjudicated"]) == 1
    print(f"    {'ok      ' if ok else 'BROKEN  '} undeclared -> {f_un} failure(s); "
          f"declared -> {f_de} failure(s), {len(s_de['adjudicated'])} adjudicated")
    if not ok:
        bad += 1

    print("\n⚠️ A gate never observed to fail has not been tested (S12 §5). "
          f"{'ALL MUTATIONS BEHAVED.' if not bad else 'BROKEN.'}")
    return 1 if bad else 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    if sys.argv[1] == "--self-test":
        return self_test()
    try:
        text = open(sys.argv[1], encoding="utf-8").read()
    except OSError as exc:
        die(f"cannot read {sys.argv[1]!r}: {exc.strerror or exc}")
    cs = parse(text)
    out, fails, stats = audit(cs)
    print("\n".join(out))
    print(f"\nAudit A: {len(out)} assertions, {fails} failure(s) — no page, no drawing, no VDD.")
    print(f"  claims parsed:              {stats['claims']}")
    print(f"  checked against the anchors: {stats['anchor_checked']}")
    print(f"  recognised, NOT verifiable here: {len(stats['recognised_unverifiable'])} "
          f"({', '.join(stats['recognised_unverifiable']) or 'none'})")
    print(f"  adjudicated (named in `ambiguous:`): {len(stats['adjudicated'])} "
          f"({', '.join(stats['adjudicated']) or 'none'}) — excluded from the exit code")
    stale = [i for i in stats["adjudicated_declared"]
             if i not in stats["adjudicated"] and i in {c['id'] for c in cs['claims']}]
    if stale:
        print(f"  ⚠️ `ambiguous:` names {stale}, which PASSED — either the contest is resolved and the "
              f"entry should go, or the claim was changed to dodge it")
    ghost = [i for i in stats["adjudicated_declared"] if i not in {c['id'] for c in cs['claims']}]
    if ghost:
        print(f"  ⚠️ `ambiguous:` names {ghost}, which are not claim ids — a typo'd adjudication "
              f"silently does nothing")
    if stats["ambiguous_idle"]:
        print(f"  ⚠️ `ambiguous:` entries lead with prose, not a claim id — they adjudicate "
              f"nothing: {stats['ambiguous_idle']}")
    if stats["unrecognised"]:
        print(f"  ⚠️ UNRECOGNISED: {stats['unrecognised']}")
    print("⚠️ This is the MECHANICAL half only. Sufficiency and correctness still need the separate "
          "agent turn (S12 §3.2) — a self-consistent misreading passes every line above, and a "
          "`load-bearing:` list that cites values where the answer needs an incidence claim passes too.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
