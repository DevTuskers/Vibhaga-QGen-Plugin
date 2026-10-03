#!/usr/bin/env python3
"""run-gates.py — the two mechanical chains of generate §2 as ONE command each (W9 item E).

    run-gates.py build <run> --medium M [--vc-out DIR] [--card KEY=NN …] --grade N
    run-gates.py ship  <run> --sid SID --scope K=V,… [--session-check]
                       [--vc-session-out DIR] [--accept-signatures N] [--expected N]

<run> is the generate §2 actor dir: `content.yaml`, `specs/figures.json`, `figures/`,
`staged.json`, `ids.json`, `ledger.json`.

This tool ONLY chains the existing tools as subprocesses with their own flags — nothing is
forked or re-implemented and no gate is lowered:

  build:  1. vdd_templates.py build specs/figures.json → figures/ (skipped when the file is
             absent or [] — every figure is then hand-drawn)
          2. per figure id — ids from specs/figures.json ∪ the basenames of every file in
             content.yaml's `figures:` map, so HAND-DRAWN figures are gated exactly like
             template-built ones: audit-claim-set.py <id>-claims.txt · vdd-check.mjs <id>.json
             --claims … --medium M (a figure file or claim set missing fails the stage)
          3. build-staged.py content.yaml --out staged.json --ids-out ids.json
          4. markdown-gate.mjs --fields <run>/fields.json — the fields list is the same set
             run-gate.sh's fields_py produces; any BLOCKED field fails the stage
          5. visual-check.mjs staged.json --claims-dir figures --out DIR (default ../vc)
          6. precritic-lint.py (only when --card is given — else a skipped line)
  ship:   1. validate · 2. doc put --ledger · 3. doc get → compare questions against
             staged.json by question_id key-by-key (server-added `published`/`published_at`
             and the renormalised `sort_order` ignored; a server-only id is a WARN, not a fail)
          4. visual-check --session --staged staged.json --claims-dir figures
             (only with --session-check) ·
             5. publish --dry-run --accept-signatures N · 6. publish --accept-signatures N ·
             7. sql-proof.py q2 --expected (default: len(ids.json))

Each chain STOPS at the first failing stage, prints that stage's exit code plus its last
~15 output lines, and propagates the exit code (so a NOT-ok Q3 inside publish exits 5
here too). On success build prints one line per figure (`Q1 audit ok · vdd-check ok ·
vc PASS 375×131`) then `gates: ok — N figures, M questions, contact sheet <path>`; ship
quotes the key lines (validate summary, published k/n, read-back 1, t77, provenance, every
q3: line, the q2 line) then `ship: ok`. Every run that reaches stage 1 writes
<run>/gates.json — {stage: rc} (a die before stage 1 — missing inputs, `--card` sans
`--grade` — exits 2 without one).

Exit: 0 ok · the first failing stage's code otherwise · 2 usage/missing input.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent
PROG = "run-gates"
TAIL = 15

PUBLISH = TOOLS / "playground-publish.py"
SQLPROOF = TOOLS / "sql-proof.py"

_pl = importlib.util.spec_from_file_location("precritic_lint", TOOLS / "precritic-lint.py")
pl = importlib.util.module_from_spec(_pl)            # figure_specs — the shared specs normaliser
_pl.loader.exec_module(pl)


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


def _load_content(path: Path) -> dict:
    """content.yaml / .yml / .json — same file build-staged.py reads."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text) or {}


def _fig_sort(fid: str):
    m = re.match(r"^([A-Za-z]*?)(\d+)", str(fid))
    return (m.group(1), int(m.group(2)), str(fid)) if m else (str(fid), 0, str(fid))


def figure_ids(run: Path, specs_path: Path, content: dict) -> tuple[list, list[tuple]]:
    """The two figure sources of a run dir, as (spec_ids, hand_figures).

    spec_ids: figure_ids from specs/figures.json (via precritic-lint's shared normaliser) —
    template-built, <run>/figures/<id>.json emitted by stage 1.
    hand_figures: [(fid, fig_path, claims_path)] from content.yaml's `figures:` map — fid is the
    basename minus .json (the staged id convention: `figures/Q5.json` → Q5, which is also the
    name vdd_templates.finish() uses for its claim set), claims beside the figure file.
    """
    spec_ids: list[str] = []
    if specs_path.is_file():
        specs = pl.figure_specs(json.loads(specs_path.read_text(encoding="utf-8")))
        spec_ids = [s.get("figure_id") for s in specs
                    if isinstance(s, dict) and s.get("figure_id")]
        if specs and not spec_ids:
            die("specs/figures.json is non-empty but yielded no figure ids — "
                "nothing would be audited or vdd-checked")
    hand = []
    for key, val in ((content.get("figures") or {}).items()):
        rel = val if isinstance(val, str) else (val or {}).get("file")
        if not isinstance(rel, str) or not rel:
            die(f"content.yaml figures:{key}: not a figure path (want 'figures/<id>.json')")
        fpath = run / rel
        fid = Path(rel).stem
        hand.append((fid, fpath, fpath.with_name(f"{fid}-claims.txt")))
    return spec_ids, hand


def staged_fields(staged: dict) -> list[dict]:
    """[{id, field, text}] over a staged doc — the same field set run-gate.sh's fields_py
    produces for the markdown gate: question_text(+_sinhala), every answer's
    approach/final_answer_latex (the `answers[]` list AND the singular `sub_answer`), and
    per-part text(+text_sinhala), recursing sub_questions (sq/sa at depth 1, sq2/sa2 below)."""
    out: list[dict] = []

    def add(i, f, t):
        if isinstance(t, str) and t.strip():
            out.append({"id": i, "field": f, "text": t})

    def answers(node):
        yield from node.get("answers") or []
        sa = node.get("sub_answer")
        if isinstance(sa, dict):
            yield sa

    for q in staged.get("questions") or []:
        qn = f"Q{q.get('question_number')}"
        add(qn, "question_text", q.get("question_text"))
        add(qn, "question_text_sinhala", q.get("question_text_sinhala"))
        for a in answers(q):
            aid = a.get("answer_id") or a.get("sub_answer_id")
            add(qn, f"a:{aid}:approach", a.get("approach"))
            add(qn, f"a:{aid}:final", a.get("final_answer_latex"))

        def parts(lst, path, depth):
            sq, sa_ = ("sq", "sa") if depth == 1 else ("sq2", "sa2")
            for p in lst or []:
                pid = f"{path}/{p.get('label')}"
                add(pid, f"{sq}:{p.get('sub_question_id')}:text", p.get("text"))
                add(pid, f"{sq}:{p.get('sub_question_id')}:text_sinhala", p.get("text_sinhala"))
                for a in answers(p):
                    aid = a.get("sub_answer_id") or a.get("answer_id")
                    add(pid, f"{sa_}:{aid}:approach", a.get("approach"))
                    add(pid, f"{sa_}:{aid}:final", a.get("final_answer_latex"))
                parts(p.get("sub_questions"), pid, depth + 1)
        parts(q.get("sub_questions"), qn, 1)
    return out


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
    if content is None:
        die(f"no content.yaml in {run}")
    spec_ids, hand = figure_ids(run, specs_path, _load_content(content))
    # the audit/vdd-check set = specs ∪ content.yaml figures (hand-drawn figures are gated
    # exactly like template-built ones), each id once, sorted for a stable report
    fig_ids = sorted(set(spec_ids) | {fid for fid, _, _ in hand}, key=_fig_sort)
    if not fig_ids:
        die("no figures to gate — specs/figures.json is absent/empty and content.yaml "
            "declares no figures: nothing would be audited or vdd-checked")
    hand_by_id = {fid: (fig, claims) for fid, fig, claims in hand}
    gates: dict = {}
    per_fig: dict[str, dict] = {f: {} for f in fig_ids}

    # 1. template build — only when there are specs (an all-hand-drawn run has none)
    if specs_path.is_file() and spec_ids:
        rc, out = runner([sys.executable, str(TOOLS / "vdd_templates.py"), "build",
                          str(specs_path), "--out", str(figs_dir)])
        gates["templates"] = rc
        if rc:
            return fail(gates, run, "templates", rc, out)
    else:
        gates["templates"] = 0
        log("templates: skipped — no specs/figures.json (or it is empty); "
            "every figure is hand-drawn")

    # 2. per-figure audit + vdd-check — template-built AND hand-drawn alike; a figure file or
    #    its claim set missing fails the stage (hand figures get theirs from
    #    vdd_templates.finish(), which writes <id>-claims.txt beside the .json)
    for fid in fig_ids:
        fig, claims = hand_by_id.get(fid, (figs_dir / f"{fid}.json",
                                           figs_dir / f"{fid}-claims.txt"))
        missing = [str(p) for p in (fig, claims) if not p.is_file()]
        if missing:
            gates[f"audit:{fid}"] = 1
            return fail(gates, run, f"audit:{fid}", 1,
                        f"{fid}: missing {', '.join(missing)} — every figure needs its .json "
                        f"and <id>-claims.txt before the gates run")
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

    # 4. markdown gate over every text field of the staged doc — the fields list is written
    #    to <run>/fields.json so the same gate can be re-run standalone
    fields = staged_fields(json.loads(staged.read_text(encoding="utf-8")))
    fields_path = run / "fields.json"
    fields_path.write_text(json.dumps(fields, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    rc, out = runner([str(NODE_BIN), str(TOOLS / "markdown-gate.mjs"),
                      "--fields", str(fields_path)])
    gates["markdown-gate"] = rc
    if rc:
        shown = quote(out, r"\[block\]|BLOCKED", log=log)
        return fail(gates, run, "markdown-gate", rc, out, shown)
    m = re.search(r"\d+ fields · \d+ BLOCKED", out)
    log(f"  markdown-gate: {m.group(0) if m else f'{len(fields)} fields · 0 BLOCKED'}")

    # 5. visual-check mode 1
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
    diffs: list[str] = []
    got_by_id: dict = {}
    for i, g in enumerate(got):
        if not isinstance(g, dict) or not g.get("question_id"):
            diffs.append(f"server question[{i}]: not a question object with a question_id")
            continue
        got_by_id[g["question_id"]] = g
    want_ids: set = set()
    for i, w in enumerate(want):
        if not isinstance(w, dict) or not w.get("question_id"):
            diffs.append(f"staged question[{i}]: not a question object with a question_id")
            continue
        wid, qn = w["question_id"], w.get("question_number", "?")
        want_ids.add(wid)
        g = got_by_id.get(wid)
        if g is None:
            diffs.append(f"Q{qn} ({wid}): missing on the server")
            continue
        w2 = {k: v for k, v in w.items() if k not in strip}
        g2 = {k: v for k, v in g.items() if k not in strip}
        if w2 != g2:
            keys = sorted({k for k in set(w2) | set(g2) if w2.get(k) != g2.get(k)})
            diffs.append(f"Q{qn}: {keys}")
    extras = [f"Q{g.get('question_number', '?')} ({g['question_id']})"
              for g in got
              if isinstance(g, dict) and g.get("question_id") and g["question_id"] not in want_ids]
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

    # 4. optional --session visual check — the local staged.json IS the server doc (doc get
    #    just proved it), and the run's claim sets go with it so `allow:`/departures apply
    #    exactly as in mode 1
    if args.session_check:
        vc_out = args.vc_session_out or str(run.parent / "vc-session")
        rc, out = runner([str(NODE_BIN), str(TOOLS / "visual-check.mjs"), "--session", sid,
                          "--staged", str(staged), "--claims-dir", str(run / "figures"),
                          "--out", vc_out])
        gates["visual-check-session"] = rc
        shown = quote(out, r"CLIPPED|revocation:|q3:", log=log)
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
                       "build-staged → markdown-gate → visual-check → precritic-lint")
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
