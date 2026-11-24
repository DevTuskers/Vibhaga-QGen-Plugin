#!/usr/bin/env python3
"""note-gates.py — the lesson-short-notes preflight as ONE command.

    note-gates.py WORK --grade N [--admin PATH]

WORK holds `en.md`, `si.md` and `diagrams.json` (a JSON array, `[]` when the note has no figure).
Checks, in order — the first hard failure exits 1:

  1. each body is nonblank, NUL-free UTF-8 under 50,000 characters;
  2. every `$…$` is on one line and every display is `$$` alone on its fence lines with a blank
     line (or the file edge) on both sides; no Sinhala inside any maths span (`\\text{}` included);
  3. English and Sinhala carry byte-identical maths spans in the same order (the first difference
     is printed with its line in each file);
  4. every `::diagram[i]` reference exists in diagrams.json, which holds at most 20 documents;
  5. `tools/check-si-terms.py --grade N` over a generated WORK/terms.json (`note` + `note_si`);
  6. when diagrams.json is non-empty, every document parses as VDD v1 with clean a11y and paints
     (`@vibhaga/shared/vdd-schema`, resolved from Vibhaga-Admin: `--admin` > VIBHAGA_ADMIN env >
     `<plugin>/../Vibhaga-Admin`).

Warnings (never fail): pipe-table rows (notes use HTML tables) and display lines long enough to
scroll at a 375 px column — split those with `\\begin{aligned}` identically in both languages.
The real render (`note-render.mjs`) is the proof; this is a text preflight, not a Markdown parser.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SINHALA = re.compile(r"[\u0d80-\u0dff]")
DISPLAY = re.compile(r"^\$\$[ \t]*\r?\n([^$]+?)^\$\$[ \t]*(?=\r?$)", re.M)
INLINE = re.compile(r"\$([^$\r\n]+)\$")
DIAGRAM_REF = re.compile(r"^::diagram\[(\d+)\]\s*$", re.M)
MAX_CHARS, MAX_VDD = 50_000, 20
WIDE_DISPLAY = 44   # rendered-width proxy: characters left after stripping LaTeX control words


class GateError(Exception):
    pass


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def spans(name: str, text: str) -> list[tuple[bool, str, int]]:
    """(is_display, exact span, line) for every maths span; raises GateError on a bad fence."""
    if not text.strip() or "\0" in text:
        raise GateError(f"{name}: blank body or NUL byte")
    if len(text) > MAX_CHARS:
        raise GateError(f"{name}: {len(text)} characters (API ceiling {MAX_CHARS})")
    out, i = [], 0
    while (start := text.find("$", i)) != -1:
        block = text.startswith("$$", start)
        m = (DISPLAY if block else INLINE).match(text, start)
        ln = line_of(text, start)
        if not m or not m[1].strip():
            raise GateError(f"{name}:{ln}: bad maths span or fence (currency is `Rs.`, never `$`)")
        if SINHALA.search(m[1]):
            raise GateError(f"{name}:{ln}: Sinhala inside maths — move the words outside the span")
        if block:
            before = text[:start].rstrip(" \t")
            after = text[m.end():]
            after_ok = not after.strip() or re.match(r"[ \t]*\r?\n[ \t]*\r?\n", after)
            if (before.strip() and not re.search(r"\n[ \t]*\r?\n$", before)) or not after_ok:
                raise GateError(f"{name}:{ln}: a display needs a blank line before and after it")
        out.append((block, m[0], ln))
        i = m.end()
    return out


def compare(a: list, b: list) -> None:
    for k, (x, y) in enumerate(zip(a, b)):
        if x[:2] != y[:2]:
            raise GateError(f"maths span {k + 1} differs: en.md:{x[2]} {x[1]!r} vs si.md:{y[2]} {y[1]!r}"
                            " — reorder the Sinhala prose, never the maths")
    if len(a) != len(b):
        raise GateError(f"maths span count differs: en {len(a)} vs si {len(b)}")


def warnings(name: str, text: str, found: list) -> list[str]:
    out = [f"{name}:{line_of(text, m.start())}: pipe-table row — use a standalone HTML table"
           for m in re.finditer(r"^\s*\|.*\|\s*$", text, re.M)]
    for block, span, ln in found:
        if not block:
            continue
        for off, row in enumerate(span.splitlines()[1:-1], 1):
            visible = re.sub(r"\\[A-Za-z]+|[{}&]|\\\\", "", row).strip()
            if len(visible) > WIDE_DISPLAY:
                out.append(f"{name}:{ln + off}: display line may scroll at 375 px — split with aligned")
    return out


def check_diagrams(work: Path, en: str, si: str) -> list:
    try:
        docs = json.loads((work / "diagrams.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise GateError(f"diagrams.json: {e}")
    if not isinstance(docs, list) or len(docs) > MAX_VDD:
        raise GateError(f"diagrams.json must be a JSON array of at most {MAX_VDD} documents")
    for name, text in (("en.md", en), ("si.md", si)):
        for m in DIAGRAM_REF.finditer(text):
            if int(m[1]) >= len(docs):
                raise GateError(f"{name}:{line_of(text, m.start())}: ::diagram[{m[1]}] has no document")
    return docs


def admin_dir(flag: str | None) -> Path:
    return Path(flag or os.environ.get("VIBHAGA_ADMIN") or HERE.parent.parent / "Vibhaga-Admin")


VDD_JS = """
import { readFileSync } from "node:fs";
import { parseVdd, a11yIssues, refusedPaintsIn } from "@vibhaga/shared/vdd-schema";
const docs = JSON.parse(readFileSync(process.argv[1], "utf8"));
for (const [i, raw] of docs.entries()) {
  const doc = parseVdd(raw);
  if (!doc || doc.schemaVersion !== 1 || a11yIssues(doc).length || refusedPaintsIn(raw).length) {
    console.error(`invalid VDD at index ${i}`); process.exit(1);
  }
}
console.log(`${docs.length} VDD documents passed`);
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="note-gates.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("work", type=Path)
    ap.add_argument("--grade", type=int, required=True)
    ap.add_argument("--admin", help="Vibhaga-Admin checkout (VDD parser)")
    a = ap.parse_args(argv)
    work = a.work.resolve()
    try:
        en = (work / "en.md").read_text(encoding="utf-8")
        si = (work / "si.md").read_text(encoding="utf-8")
        sa, sb = spans("en.md", en), spans("si.md", si)
        compare(sa, sb)
        docs = check_diagrams(work, en, si)
    except (GateError, OSError, UnicodeDecodeError) as e:
        print(f"note-gates: FAIL {e}")
        return 1
    for w in warnings("en.md", en, sa) + warnings("si.md", si, sb):
        print(f"note-gates: WARN {w}")
    print(f"note-gates: {len(sa)} identical maths spans, {sum(s[0] for s in sa)} display, "
          f"0 Sinhala in maths; en {len(en)} / si {len(si)} chars; {len(docs)} diagrams")
    (work / "terms.json").write_text(json.dumps({"note": en, "note_si": si}, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(HERE / "check-si-terms.py"), str(work / "terms.json"),
                        "--grade", str(a.grade)], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    if r.returncode:
        print("note-gates: FAIL Sinhala terminology — read each finding in context")
        return 1
    if docs:
        adm = admin_dir(a.admin)
        r = subprocess.run(["node", "--input-type=module", "-e", VDD_JS, str(work / "diagrams.json")],
                           cwd=adm, capture_output=True, text=True)
        print((r.stdout + r.stderr).strip())
        if r.returncode:
            print("note-gates: FAIL VDD")
            return 1
    print("note-gates: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
