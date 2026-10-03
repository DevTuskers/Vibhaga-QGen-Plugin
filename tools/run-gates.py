#!/usr/bin/env python3
"""run-gates.py — the two mechanical chains of generate §2 as ONE command each (W9 item E).

    run-gates.py build <run> --medium M [--vc-out DIR] [--card KEY=NN …] --grade N
    run-gates.py ship  <run> --sid SID --scope K=V,… [--session-check]
                       [--vc-session-out DIR] [--accept-signatures N] [--expected N]

<run> is the generate §2 actor dir: `content.yaml`, `specs/figures.json`, `figures/`,
`staged.json`, `ids.json`, `ledger.json`.

This tool ONLY chains the existing tools as subprocesses with their own flags — nothing is
forked or re-implemented and no gate is lowered:

  build:  1. vdd_templates.py build specs/figures.json → figures/
          2. per figure id: audit-claim-set.py <id>-claims.txt · vdd-check.mjs <id>.json
             --claims … --medium M
          3. build-staged.py content.yaml --out staged.json --ids-out ids.json
          4. visual-check.mjs staged.json --claims-dir figures --out DIR (default ../vc)
          5. precritic-lint.py (only when --card is given — else a skipped line)
  ship:   1. validate · 2. doc put --ledger · 3. doc get → compare questions against
             staged.json by question_id key-by-key (server-added `published`/`published_at`
             and the renormalised `sort_order` ignored; a server-only id is a WARN, not a fail)
          4. visual-check --session (only with --session-check) · 5. publish --dry-run
             --accept-signatures N · 6. publish --accept-signatures N ·
          7. sql-proof.py q2 --expected (default: len(ids.json))

Each chain STOPS at the first failing stage, prints that stage's exit code plus its last
~15 output lines, and propagates the exit code (so a NOT-ok Q3 inside publish exits 5
here too). On success build prints one line per figure (`Q1 audit ok · vdd-check ok ·
vc PASS 375×131`) then `gates: ok — N figures, M questions, contact sheet <path>`; ship
quotes the key lines (validate summary, published k/n, read-back 1, t77, provenance, every
q3: line, the q2 line) then `ship: ok`. Every run writes <run>/gates.json — {stage: rc}.

Exit: 0 ok · the first failing stage's code otherwise · 2 usage/missing input.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PROG = "run-gates"
TAIL = 15

PUBLISH = TOOLS / "playground-publish.py"
SQLPROOF = TOOLS / "sql-proof.py"


def die(msg: str) -> "None":
    print(f"{PROG}: {msg}", file=sys.stderr)
    sys.exit(2)


def run_cmd(argv: list[str]) -> tuple[int, str]:
    """The default subprocess runner — (exit code, combined stdout+stderr). Injected in tests."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError:
        return 127, f"{argv[0]} not found"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def fail(gates: dict, run: Path, stage: str, rc: int, out: str,
         shown: tuple[str, ...] = ()) -> int:
    gates[stage] = rc
    write_gates(run, gates)
    print(f"stage {stage}: exit {rc} — stopping")
    skip = set(shown)                               # lines quote() already echoed are not reprinted
    for line in out.strip().splitlines()[-TAIL:]:
        if line.strip() not in skip:
            print(f"  {line}")
    return rc


def write_gates(run: Path, gates: dict) -> None:
    (run / "gates.json").write_text(json.dumps(gates, indent=1, sort_keys=True) + "\n",
                                    encoding="utf-8")


def quote(out: str, *patterns: str, log=print) -> tuple[str, ...]:
    """Echo the lines of `out` matching any pattern (the tool's own words, verbatim). Returns the
    echoed lines so a later fail() tail never re-prints what the stage already streamed."""
    shown = []
    for line in out.splitlines():
        if any(re.search(p, line) for p in patterns):
            log(f"  {line.strip()}")
            shown.append(line.strip())
    return tuple(shown)


# ----------------------------------------------------------------------------- build
def cmd_build(args, runner=run_cmd, log=print) -> int:
    run = Path(args.run)
    if args.card and args.grade is None:
        die("--card needs --grade N (cards resolve under maths/grade-NN/scope-cards/)")
    if not run.is_dir():
        die(f"no run dir {run}")
    specs_path = run / "specs" / "figures.json"
    figs_dir = run / "figures"
    content = next((run / n for n in ("content.yaml", "content.yml", "content.json")
                    if (run / n).is_file()), None)
    staged, ids, ledger = run / "staged.json", run / "ids.json", run / "ledger.json"
    if not specs_path.is_file():
        die(f"no specs/figures.json in {run}")
    if content is None:
        die(f"no content.yaml in {run}")
    specs = json.loads(specs_path.read_text(encoding="utf-8"))
    if isinstance(specs, dict):
        specs = [specs]
    fig_ids = [s.get("figure_id") for s in specs if isinstance(s, dict) and s.get("figure_id")]
    gates: dict = {}
    per_fig: dict[str, dict] = {f: {} for f in fig_ids}

    # 1. template build
    rc, out = runner([sys.executable, str(TOOLS / "vdd_templates.py"), "build",
                      str(specs_path), "--out", str(figs_dir)])
    gates["templates"] = rc
    if rc:
        return fail(gates, run, "templates", rc, out)

    # 2. per-figure audit + vdd-check
    for fid in fig_ids:
        claims, fig = figs_dir / f"{fid}-claims.txt", figs_dir / f"{fid}.json"
        rc, out = runner([sys.executable, str(TOOLS / "audit-claim-set.py"), str(claims)])
        gates[f"audit:{fid}"] = rc
        per_fig[fid]["audit"] = rc
        if rc:
            return fail(gates, run, f"audit:{fid}", rc, out)
        rc, out = runner([str(NODE_BIN), str(TOOLS / "vdd-check.mjs"), str(fig),
                          "--claims", str(claims), "--medium", args.medium])
        gates[f"vdd-check:{fid}"] = rc
        per_fig[fid]["vdd"] = rc
        if rc:
            return fail(gates, run, f"vdd-check:{fid}", rc, out)

    # 3. staged doc + ids
    rc, out = runner([sys.executable, str(TOOLS / "build-staged.py"), str(content),
                      "--out", str(staged), "--ids-out", str(ids)])
    gates["build-staged"] = rc
    if rc:
        return fail(gates, run, "build-staged", rc, out)

    # 4. visual-check mode 1
    vc_out = Path(args.vc_out) if args.vc_out else run.parent / "vc"
    rc, vc_out_text = runner([str(NODE_BIN), str(TOOLS / "visual-check.mjs"), str(staged),
                              "--claims-dir", str(figs_dir), "--out", str(vc_out)])
    gates["visual-check"] = rc
    if rc:
        return fail(gates, run, "visual-check", rc, vc_out_text)

    # 5. pre-critic lint — only when cards are bound (--card ⇒ --grade checked up front)
    if args.card:
        argv = [sys.executable, str(TOOLS / "precritic-lint.py"), str(run),
                "--grade", str(args.grade)]
        for c in args.card:
            argv += ["--card", c]
        if args.cards_dir:
            argv += ["--cards-dir", args.cards_dir]
        rc, out = runner(argv)
        gates["precritic-lint"] = rc
        shown = quote(out, r"FAIL|WARN", log=log)
        if rc:
            return fail(gates, run, "precritic-lint", rc, out, shown)
    else:
        log("precritic-lint: skipped — no --card given")

    for fid in fig_ids:
        m = re.search(rf"^{re.escape(fid)}\s+(PASS|FAIL)\s.*?\b(\d+×\d+)\b",
                      vc_out_text, re.M)
        vc = f"{m.group(1)} {m.group(2)}" if m else "—"
        log(f"{fid} audit ok · vdd-check ok · vc {vc}")
    n_q = len(json.loads(staged.read_text(encoding="utf-8")).get("questions", []))
    m = re.search(r"contact: (\S+) (\d+×\d+)", vc_out_text)
    contact = m.group(1) if m else str(vc_out / "contact-light-375.png")
    log(f"gates: ok — {len(fig_ids)} figures, {n_q} questions, contact sheet {contact}")
    write_gates(run, gates)
    return 0


# ----------------------------------------------------------------------------- ship
def doc_diff(staged_path: Path, server_path: Path) -> tuple[list[str], list[str]]:
    """staged questions vs server questions matched by `question_id`, key-by-key, ignoring the
    server-added `published`/`published_at` stamps. `doc put` merges into the server array (server
    order kept, sort_order renormalised), so position and sort_order are never the match key.
    Returns (diffs, extras): a staged id missing on the server or differing → a diff; a server-only
    id (`kept_unlisted`) is an extra — the caller prints it as a WARN, it is not a failure."""
    strip = {"published", "published_at", "sort_order"}
    want = json.loads(staged_path.read_text(encoding="utf-8")).get("questions")
    got = json.loads(server_path.read_text(encoding="utf-8")).get("questions")
    if not isinstance(want, list) or not isinstance(got, list):
        return ["<doc shape: questions is not a list>"], []
    got_by_id = {g.get("question_id"): g for g in got if isinstance(g, dict)}
    diffs: list[str] = []
    for w in want:
        wid, qn = w.get("question_id"), w.get("question_number", "?")
        g = got_by_id.get(wid)
        if g is None:
            diffs.append(f"Q{qn} ({wid}): missing on the server")
            continue
        w2 = {k: v for k, v in w.items() if k not in strip}
        g2 = {k: v for k, v in g.items() if k not in strip}
        if w2 != g2:
            keys = sorted({k for k in set(w2) | set(g2) if w2.get(k) != g2.get(k)})
            diffs.append(f"Q{qn}: {keys}")
    want_ids = {w.get("question_id") for w in want}
    extras = [f"Q{g.get('question_number', '?')} ({g.get('question_id')})"
              for g in got if g.get("question_id") not in want_ids]
    return diffs, extras


def cmd_ship(args, runner=run_cmd, log=print) -> int:
    run = Path(args.run)
    if not run.is_dir():
        die(f"no run dir {run}")
    staged, ids, ledger = run / "staged.json", run / "ids.json", run / "ledger.json"
    for p, what in ((staged, "staged.json"), (ids, "ids.json"), (ledger, "ledger.json")):
        if not p.is_file():
            die(f"no {what} in {run}")
    expected = args.expected
    if expected is None:
        try:
            expected = len(json.loads(ids.read_text(encoding="utf-8")))
        except (ValueError, TypeError):
            die(f"{ids} is not a JSON list")
    gates: dict = {}
    sid = args.sid

    # 1. validate — warnings are quoted, errors stop
    rc, out = runner([sys.executable, str(PUBLISH), "validate", sid, "--staged", str(staged)])
    gates["validate"] = rc
    shown = quote(out, r"^\s*(validate:|.*warn|.*error)", log=log)
    if rc:
        return fail(gates, run, "validate", rc, out, shown)

    # 2. doc put
    rc, out = runner([sys.executable, str(PUBLISH), "doc", "put", sid,
                      "--staged", str(staged), "--ledger", str(ledger)])
    gates["doc-put"] = rc
    shown = quote(out, r"doc put:", log=log)
    if rc:
        return fail(gates, run, "doc-put", rc, out, shown)

    # 3. doc get → compare against staged
    server_path = run / "server.json"
    rc, out = runner([sys.executable, str(PUBLISH), "doc", "get", sid, "--out", str(server_path)])
    gates["doc-get"] = rc
    shown = quote(out, r"doc get:", log=log)
    if rc:
        return fail(gates, run, "doc-get", rc, out, shown)
    diffs, extras = doc_diff(staged, server_path)
    for e in extras:
        log(f"  WARN server holds {e} not in staged.json (kept_unlisted) — not a failure")
    gates["doc-diff"] = 0 if not diffs else 1
    if diffs:
        return fail(gates, run, "doc-diff", 1,
                    "server doc differs from staged.json (matched by question_id, ignoring "
                    "published/published_at/sort_order):\n" + "\n".join(diffs))

    # 4. optional --session visual check
    if args.session_check:
        vc_out = args.vc_session_out or str(run.parent / "vc-session")
        rc, out = runner([str(NODE_BIN), str(TOOLS / "visual-check.mjs"), "--session", sid,
                          "--out", vc_out])
        gates["visual-check-session"] = rc
        shown = quote(out, r"CLIPPED|revocation:", log=log)
        if rc:
            return fail(gates, run, "visual-check-session", rc, out, shown)
    else:
        log("visual-check --session: skipped — no --session-check")

    # 5–6. publish dry-run, then the real publish
    base = [sys.executable, str(PUBLISH), "publish", sid, "--staged", str(staged),
            "--scope", args.scope, "--ids-file", str(ids), "--ledger", str(ledger),
            "--accept-signatures", str(args.accept_signatures)]
    rc, out = runner(base + ["--dry-run"])
    gates["publish-dry-run"] = rc
    shown = quote(out, r"dry-run:", log=log)
    if rc:
        return fail(gates, run, "publish-dry-run", rc, out, shown)
    rc, out = runner(base)
    gates["publish"] = rc
    shown = quote(out, r"published \d|read-back 1:|t77:|provenance:|q3:|logout", log=log)
    if rc:
        return fail(gates, run, "publish", rc, out, shown)

    # 7. the Q2 proof
    rc, out = runner([sys.executable, str(SQLPROOF), "q2", sid,
                      "--expected", str(expected)])
    gates["q2"] = rc
    shown = quote(out, r"^q2:", log=log)
    if rc:
        return fail(gates, run, "q2", rc, out, shown)

    log("ship: ok")
    write_gates(run, gates)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="run-gates.py",
                                 description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="the offline chain: templates → audit+vdd-check → "
                       "build-staged → visual-check → precritic-lint")
    b.add_argument("run")
    b.add_argument("--medium", required=True, choices=["sinhala", "english", "tamil"])
    b.add_argument("--vc-out", help="visual-check output dir (default: <run>/../vc)")
    b.add_argument("--card", action="append", default=[], help="KEY=NN for precritic-lint")
    b.add_argument("--grade", type=int, help="required with --card")
    b.add_argument("--cards-dir", help="passed through to precritic-lint")
    s = sub.add_parser("ship", help="the live chain: validate → doc put → doc get diff → "
                       "[--session check] → publish dry-run → publish → q2")
    s.add_argument("run")
    s.add_argument("--sid", required=True)
    s.add_argument("--scope", required=True)
    s.add_argument("--session-check", action="store_true")
    s.add_argument("--vc-session-out")
    s.add_argument("--accept-signatures", type=int, default=0)
    s.add_argument("--expected", type=int, default=None)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        return cmd_build(args)
    return cmd_ship(args)


NODE_BIN = "node"

if __name__ == "__main__":
    sys.exit(main())
