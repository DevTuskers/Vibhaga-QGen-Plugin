#!/usr/bin/env python3
"""
check-suite.py — the vibhaga-qgen offline gate. Run before every commit:

    PYTHONDONTWRITEBYTECODE=1 VIBHAGA_ADMIN_ENV=/nonexistent/offline-test-only \
        python3 tools/check-suite.py

(`VIBHAGA_ADMIN_ENV` is set for you when absent — this suite never reads real credentials.)

Part A — doc lint (carried from Vibhaga-Docs `.devin/skills/_maths-onboarding/check-suite.py` @08c09a9;
its rationale stands: every fix round produced an enum with no consumer, a `§N` cited after its body was
deleted, a table silently losing cells. All of it mechanical, all of it catchable):
  1. `§N` cross-references into the orchestrator skill (skills/generate) resolve to real headings.
  2. Every docs/TRAPS.md entry has an inbound citation from skills/agents (warn-only — a ledger nobody
     cites is the shape it exists to warn about).
  3. Enum values named in ENUMS are both produced and consumed (list is empty until the generation
     skills land their verdict values — populate it then).
  4. Relative markdown links resolve.
  5. Substantive lines deleted in the staged diff are surfaced as warnings.
  6. A GFM table row must not have more cells than its header (extras are silently DELETED).
  7. A blank line inside a pipe table splits it; rows after render as a paragraph with pipes in it.
  8. Every skills/*/SKILL.md + agents/*.md frontmatter parses as YAML with non-empty `name`/`description`
     (T-QG-1: the CLI drops a skill whose frontmatter does not parse — silently, at install).

Part B — the real test run, all offline:
  · `python3 -m unittest discover -s tests -p 'test_*.py'`
  · tool self-tests: `audit-claim-set.py --self-test`, `playground-publish.py --self-test`,
    `scope-cards.py --self-test`, `vdd_templates.py --self-test`, `critic-read.py --self-test`
    (always);
    `node markdown-gate.mjs --self-test` (needs Vibhaga-Web + Vibhaga-Admin), `node vdd-check.mjs
    --self-test` (needs Vibhaga-Admin — playwright/chromium). A missing sibling checkout prints a
    SKIP line, not a failure.
  · `node --test` over tests/*.mjs (skipped without Vibhaga-Admin — vdd-layout resolves its deps).
  · a build-staged smoke run: tests/fixtures/content.yaml → a temp staged.json.

Exit non-zero on any error, so it can gate a commit.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS: list[str] = []
WARNS: list[str] = []
SKIPS: list[str] = []


def doc_files() -> dict[Path, str]:
    """skills/*/SKILL.md + agents/*.md + docs/*.md — the plugin's prose corpus."""
    paths = sorted(ROOT.glob("skills/*/*.md")) + sorted((ROOT / "agents").glob("*.md")) \
        + sorted((ROOT / "docs").glob("*.md"))
    return {p: p.read_text(encoding="utf-8") for p in paths if p.is_file()}


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# ---------------------------------------------------------------------------------------------
# A1. `§N` cross-references into the orchestrator skill resolve to headings that still exist.
#     (`§N` self-references are deliberately unchecked — noise, same as the source suite.)
# ---------------------------------------------------------------------------------------------
def check_section_anchors(docs: dict[Path, str]) -> None:
    headings: dict[str, set[str]] = {}
    for p, s in docs.items():
        found = set()
        for m in re.finditer(r"^#{2,4}\s+(\d+(?:\.\d+)*)[.\s]", s, re.M):
            found.add(m.group(1))
        if re.search(r"^#{2,4}\s+0\.\s", s, re.M) or "## 0. Non-negotiables" in s:
            for m in re.finditer(r"^\s{0,3}(\d+)\.\s", s, re.M):
                found.add(f"0.{m.group(1)}")
        headings[rel(p)] = found

    orchestrator = "skills/generate/SKILL.md"
    if orchestrator not in headings:
        WARNS.append(f"{orchestrator} missing — §-anchor check on orchestrator citations skipped")
        return
    for p, s in docs.items():
        for m in re.finditer(r"(generate|orchestrator)[^\n.]{0,40}?§(\d+(?:\.\d+)*)", s, re.I):
            sec = m.group(2)
            if sec not in headings.get(orchestrator, set()):
                ERRORS.append(f"{rel(p)}: cites generate §{sec}, which has no such heading")


# ---------------------------------------------------------------------------------------------
# A2. Every TRAPS entry has at least one inbound citation.
# ---------------------------------------------------------------------------------------------
def check_trap_references(docs: dict[Path, str]) -> None:
    traps_path = ROOT / "docs" / "TRAPS.md"
    if not traps_path.is_file():
        WARNS.append("docs/TRAPS.md missing — trap-citation check skipped")
        return
    traps = set(re.findall(r"^## (T\d+)", traps_path.read_text(encoding="utf-8"), re.M))
    cited: set[str] = set()
    for p, s in docs.items():
        if p == traps_path:
            continue
        cited |= {f"T{n}" for n in re.findall(r"\bT(\d+)\b", s)}
    for t in sorted(traps, key=lambda x: int(x[1:])):
        if t not in cited:
            WARNS.append(f"TRAPS {t} has no inbound citation from any skill/agent — it will not be read")


# ---------------------------------------------------------------------------------------------
# A3. Every enum value that is PRODUCED is also READ somewhere else.
#     Empty for now: the paper-side verdict enums (R1..R6, F-R1…) went out with the paper pipeline.
#     Add the generation verdict values here when the generation skills land them.
# ---------------------------------------------------------------------------------------------
ENUMS: list[str] = []


def check_enum_consumers(docs: dict[Path, str]) -> None:
    for value in ENUMS:
        holders = [rel(p) for p, s in docs.items() if value in s]
        if len(holders) == 1:
            ERRORS.append(
                f"'{value}' appears in ONE file ({holders[0]}) — a value with no second reader is inert. "
                f"Either something must consume it, or it should not exist."
            )
        elif not holders:
            WARNS.append(f"'{value}' appears nowhere — stale entry in this checker?")


# ---------------------------------------------------------------------------------------------
# A4. Relative links resolve (skills/agents/docs AND the root README/AGENTS).
# ---------------------------------------------------------------------------------------------
def check_links(docs: dict[Path, str]) -> None:
    all_md = dict(docs)
    for p in sorted(ROOT.glob("*.md")):
        all_md[p] = p.read_text(encoding="utf-8")
    for p, s in all_md.items():
        for m in re.finditer(r"\]\(([^)#][^)]*)\)", s):
            target = m.group(1).split("#")[0]
            if not target or target.startswith(("http", "mailto")) or "?!" in target:
                continue
            if not (p.parent / target).resolve().exists():
                ERRORS.append(f"{rel(p)}: broken link -> {target}")


# ---------------------------------------------------------------------------------------------
# A5. Account for DELETED lines in the staged diff.
# ---------------------------------------------------------------------------------------------
def check_deletions() -> None:
    try:
        diff = subprocess.run(
            ["git", "diff", "--cached", "-U0"],
            capture_output=True, text=True, cwd=ROOT, check=False,
        ).stdout
    except Exception:  # noqa: BLE001 — the check is advisory, never fatal to the run
        return
    removed = [l[1:] for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    substantive = [l for l in removed if len(l.strip()) > 40]
    if substantive:
        WARNS.append(
            f"{len(substantive)} substantive line(s) DELETED in the staged diff. Read every one and "
            f"confirm it was meant to go. First: {substantive[0][:80]!r}"
        )


# ---------------------------------------------------------------------------------------------
# Shared by A6/A7: which lines are MARKDOWN, not code?
# ---------------------------------------------------------------------------------------------
FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def prose_lines(text: str) -> list[tuple[int, str, bool]]:
    """(1-based lineno, line, is_prose). `is_prose` is False inside a fence or an indented code block."""
    out: list[tuple[int, str, bool]] = []
    in_fence = False
    for n, line in enumerate(text.split("\n"), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            out.append((n, line, False))
            continue
        indented_code = line.startswith("    ") or line.startswith("\t")
        out.append((n, line, not in_fence and not indented_code))
    return out


# ---------------------------------------------------------------------------------------------
# A6. A GFM table row must not have MORE cells than its header — the extras are silently DELETED.
# ---------------------------------------------------------------------------------------------
def check_table_cells(_docs: dict[Path, str]) -> None:
    docs = {q: q.read_text(encoding="utf-8") for q in sorted(ROOT.rglob("*.md")) if ".git" not in q.parts}
    for p, s in docs.items():
        header_cells = None
        for lineno, line, is_prose in prose_lines(s):
            stripped = line.strip()
            if not is_prose:
                header_cells = None
                continue
            if not stripped.startswith("|"):
                header_cells = None
                continue
            body = re.sub(r"^\||\|$", "", stripped)
            cells = len(re.findall(r"(?<!\\)\|", body)) + 1
            if header_cells is None:
                header_cells = cells
                continue
            if re.fullmatch(r"[\s:|-]+", stripped):
                continue
            if cells > header_cells:
                ERRORS.append(
                    f"{rel(p)}:{lineno}: table row has {cells} cells against a {header_cells}-cell "
                    f"header — GFM DELETES the extras. Escape the pipe inside the code span as \\|"
                )


# ---------------------------------------------------------------------------------------------
# A7. A BLANK LINE inside a pipe table splits it; everything after renders as a paragraph.
# ---------------------------------------------------------------------------------------------
def check_table_breaks(_docs: dict[Path, str]) -> None:
    delim = re.compile(r"^[\s:|-]+$")
    for p in sorted(ROOT.rglob("*.md")):
        if ".git" in p.parts:
            continue
        rows = prose_lines(p.read_text(encoding="utf-8"))
        prose = [(n, l) for n, l, ok in rows if ok]
        for idx, (lineno, line) in enumerate(prose):
            if line.strip():
                continue
            prev = next((l for _, l in reversed(prose[:idx]) if l.strip()), "")
            nxt_i = next((j for j in range(idx + 1, len(prose)) if prose[j][1].strip()), None)
            if nxt_i is None:
                continue
            if idx and not prose[idx - 1][1].strip():
                continue
            nxt = prose[nxt_i][1]
            if not (prev.strip().startswith("|") and nxt.strip().startswith("|")):
                continue
            second = prose[nxt_i + 1][1].strip() if nxt_i + 1 < len(prose) else ""
            if delim.match(second) and "-" in second:
                continue
            ERRORS.append(
                f"{rel(p)}:{lineno}: BLANK LINE inside a pipe table — the rows after it "
                f"render as a paragraph with pipes in it, not as table rows. Delete the blank line(s), "
                f"or give the following block its own header + delimiter row. (First row lost: "
                f"{nxt.strip()[:60]!r})"
            )


# ---------------------------------------------------------------------------------------------
# A8. Frontmatter must parse — the CLI drops a skill whose frontmatter is not valid YAML, with no
#     error at install (T-QG-1: a plain-scalar `description:` containing `constructed channel: …`
#     cost a skill a whole debugging round).
# ---------------------------------------------------------------------------------------------
FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.S)


def frontmatter_errors(label: str, text: str, expect_name: str | None = None) -> list[str]:
    """Frontmatter lint for one file — returns error strings (empty = clean)."""
    import yaml  # lazy — same convention as the other tools

    m = FRONTMATTER.match(text)
    if not m:
        return [f"{label}: no `---` frontmatter block at the top — the CLI drops the skill silently (T-QG-1)"]
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return [
            f"{label}: frontmatter is not valid YAML — {e} — the CLI drops the skill with no "
            f"error at install (T-QG-1). Quote or fold (`>-`) any scalar containing a colon."
        ]
    if not isinstance(fm, dict):
        return [f"{label}: frontmatter is not a mapping — the CLI drops the skill silently (T-QG-1)"]
    errs: list[str] = []
    for key in ("name", "description"):
        if not isinstance(fm.get(key), str) or not fm[key].strip():
            errs.append(f"{label}: frontmatter needs a non-empty string `{key}`")
    if expect_name is not None and fm.get("name") != expect_name:
        errs.append(
            f"{label}: frontmatter `name:` {fm.get('name')!r} != directory name {expect_name!r}"
        )
    return errs


def check_frontmatter(docs: dict[Path, str]) -> None:
    for p, s in docs.items():
        if p.name == "SKILL.md" and p.parent.parent.name == "skills":
            expect = p.parent.name
        elif p.parent.name == "agents":
            expect = None
        else:
            continue
        ERRORS.extend(frontmatter_errors(rel(p), s, expect))


# ---------------------------------------------------------------------------------------------
# Part B — the offline test run.
# ---------------------------------------------------------------------------------------------
def sibling(name: str, env_key: str) -> Path:
    return Path(os.environ.get(env_key, ROOT.parent / name)).resolve()


def run(name: str, argv: list[str], env: dict, cwd: Path = ROOT) -> bool:
    print(f"  run    {name}: {' '.join(argv)}")
    r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()
    for line in tail[-6:]:
        print(f"         {line}")
    if r.returncode != 0:
        ERRORS.append(f"{name} exited {r.returncode} (last output lines above)")
        return False
    return True


def run_tests() -> None:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("VIBHAGA_ADMIN_ENV", "/nonexistent/offline-test-only")

    admin = sibling("Vibhaga-Admin", "VIBHAGA_ADMIN")
    web = sibling("Vibhaga-Web", "VIBHAGA_WEB")
    have_admin = (admin / "package.json").is_file()
    have_web = (web / "package.json").is_file()

    run("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], env)
    run("audit-claim-set --self-test", [sys.executable, "tools/audit-claim-set.py", "--self-test"], env)
    run("playground-publish --self-test", [sys.executable, "tools/playground-publish.py", "--self-test"], env)
    run("scope-cards --self-test", [sys.executable, "tools/scope-cards.py", "--self-test"], env)
    run("vdd_templates --self-test", [sys.executable, "tools/vdd_templates.py", "--self-test"], env)
    run("critic-read --self-test", [sys.executable, "tools/critic-read.py", "--self-test"], env)

    if have_web and have_admin:
        run("markdown-gate --self-test", ["node", "tools/markdown-gate.mjs", "--self-test"], env)
    else:
        SKIPS.append(f"markdown-gate --self-test SKIP (need Vibhaga-Web at {web} AND Vibhaga-Admin at {admin})")

    if have_admin:
        run("vdd-check --self-test", ["node", "tools/vdd-check.mjs", "--self-test"], env)
        for t in sorted((ROOT / "tests").glob("*.mjs")):
            run(f"node --test {t.name}", ["node", "--test", str(t)], env)
    else:
        SKIPS.append(f"vdd-check --self-test + node --test SKIP (need Vibhaga-Admin at {admin} — playwright lives there)")

    fixture = ROOT / "tests" / "fixtures" / "content.yaml"
    if fixture.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            run("build-staged smoke", [sys.executable, "tools/build-staged.py", str(fixture),
                                       "--out", str(Path(tmp) / "staged.json")], env)


def main() -> int:
    docs = doc_files()
    check_section_anchors(docs)
    check_table_cells(docs)
    check_table_breaks(docs)
    check_trap_references(docs)
    check_enum_consumers(docs)
    check_links(docs)
    check_frontmatter(docs)
    check_deletions()

    print("part B — offline test run:")
    run_tests()

    for s in SKIPS:
        print(f"  skip   {s}")
    for w in WARNS:
        print(f"  warn   {w}")
    for e in ERRORS:
        print(f"  ERROR  {e}")
    print(f"\n{len(docs)} doc files · {len(ERRORS)} errors · {len(WARNS)} warnings · {len(SKIPS)} skips")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--lint-frontmatter":
        target = Path(sys.argv[2])
        expect = target.parent.name if target.name == "SKILL.md" else None
        errs = frontmatter_errors(str(target), target.read_text(encoding="utf-8"), expect)
        for e in errs:
            print(f"ERROR  {e}")
        sys.exit(1 if errs else 0)
    sys.exit(main())
