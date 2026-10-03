#!/usr/bin/env python3
"""critic-read.py — the qgen-critic's ONE-COMMAND read of a playground batch (W6).

    python3 tools/critic-read.py <batch_id> --out DIR [--db-env PATH] [--queries PATH]
                              [--previous DIR-or-FILE]
    python3 tools/critic-read.py hashes <batch_id> [--out FILE] [--db-env PATH] [--queries PATH]

`hashes` (W9-H1) prints the `Q<n> <sha256 of the exact q4b line>` lines hashes.txt would hold —
nothing else is written unless --out is given — so two critic rounds can be diffed without
re-opening actor files. `--previous` (W9-H2) takes the earlier round's report dir (its
hashes.txt) or a hashes file: fields.json + figures.txt then cover only CHANGED-or-NEW
questions, the unchanged ones land in `carried.txt` (`Q<n> <hash>` each), and stdout prints
`changed: […] · carried: […] · gone: […]`.

Slices the Q4a/Q4b/Q4c blocks out of `queries.sql` (from each `-- Q4x` header comment line to the
terminating `;` of its statement — a `;` inside a `-- ` comment line does not terminate), asserts
each slice is a single SELECT with no write token (a
smoke check — the read-only transaction is the guard; slicing stops at the first `;` on a
non-comment line, so Q4 must never hold a `;` inside a literal), and runs each read-only through `psql -X -A -t -q -w
-v ON_ERROR_STOP=1 -v batch_id=<id> -f -` with the SQL on stdin prefixed
`set default_transaction_read_only=on;`. The DB URL is NEVER on argv or printed — it is split into
PG* environment variables (the session-db.mjs `pgEnvFromUrl` approach, ported).

DB URL resolution: `--db-env` file → `DATABASE_URL` env → `publish.load_db_url` (env, then
`Vibhaga-DB/.env` beside Vibhaga-Admin — reused, not copied). The SOURCE (never the value) is
printed to stderr as `critic-read: DB URL from <…>`.

Writes into DIR:
  q4a.json     the session row (exactly one object — else exit 1 "session not found")
  q4b.jsonl    one JSON object per question, exactly as psql printed it (0 lines → exit 1)
  q4c.jsonl    one JSON object per OTHER question sharing a lesson (0 lines is a valid answer)
  fields.json  markdown-gate input [{id, field, text}] for every non-null student string:
               `Q1.stem`/`Q1.stem_sinhala`, `Q2.b.text`/`Q2.b.text_sinhala`, `Q2.b.approach`/
               `Q2.b.final` per answer (nested label paths `Q3.a.i`; `ans<k>` suffix when a node
               carries more than one answer)
  hashes.txt   `Q<n> <sha256 of the exact q4b line>` per question — the critic's tamper anchor
  figures.txt  every non-null diagram_dsl location in visual-check's id scheme, one line per figure:
               `Q<n>[.<label>][.ans<k>]<TAB><answer_id | sub_answer_id | ->` — `ans<k>` is the
               1-based index into the node's answer list. The uuid column exists because
               visual-check numbers ans<k> by STAGED order while q4b's arrays are ordered by
               created_at,id — on a multi-answer node the two can disagree, so map by uuid.

A part whose parent_sub_question_id is not in the batch's part set is never dropped: it lands under
`Q<n>.ORPHAN<k>` (fields + figures + part count) with a `critic-read: WARNING …` line on stderr.

Summary line: `critic-read: N question(s) · P part(s) · F figure(s) · K other row(s) on the same
lessons → DIR`.

Exit: 0 ok · 1 ran but the batch is not there (session not found / 0 questions) or a query failed ·
2 usage / missing input (non-uuid batch_id, no DB URL, queries.sql block missing or fails the
read-only assertion).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _admin_auth as _auth  # noqa: E402  (shared env-file resolver; ENV_PATH is resolved at import)
from publish import load_db_url, read_env  # noqa: E402  (the W1 loader — reused, not copied)

HERE = Path(__file__).resolve().parent
QUERIES = HERE.parent / "queries.sql"
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# A smoke check, not a sandbox: the read-only transaction is the real guard. Word-bounded so
# `updated_at`/`inserted` can't trip it.
WRITE_TOKENS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE|CREATE|GRANT|REVOKE|COPY|CALL|DO|MERGE|INTO|EXPLAIN)\b",
    re.I)
BLOCKS = {"q4a": "Q4a", "q4b": "Q4b", "q4c": "Q4c"}

# Message prefix — sql-proof.py imports these helpers and sets its own name before calling them.
PROG = "critic-read"


def die(msg: str, code: int = 2) -> "SystemExit":
    print(f"{PROG}: {msg}", file=sys.stderr)
    raise SystemExit(code)


def slice_block(sql_text: str, marker: str) -> str:
    """From the `-- <marker>` header comment line through the statement's terminating `;`.
    The terminator is the first `;` on a NON-comment line — `-- ` comment lines may legitimately
    end a bullet with `;` (Q2's header does), and cutting there would slice mid-comment. A `;`
    inside a statement's string literal still breaks the slice — queries.sql holds none."""
    lines = sql_text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(rf"-- {marker}\b", l)), None)
    if start is None:
        die(f"queries.sql has no `-- {marker}` block")
    out = []
    for line in lines[start:]:
        if line.lstrip().startswith("--"):
            out.append(line)
            continue
        if ";" in line:
            # Cut at the first `;` — unless what follows it is a real statement tail rather than a
            # trailing `-- ` comment: keep the whole line so the single-statement assertion sees it.
            tail = line[line.index(";") + 1:]
            out.append(line[: line.index(";") + 1] if not tail.strip() or tail.strip().startswith("--")
                       else line)
            return "\n".join(out)
        out.append(line)
    die(f"queries.sql `-- {marker}` block has no terminating `;`")


def assert_single_select(block: str, marker: str) -> str:
    """The slice minus its `-- ` comment lines must be ONE statement, starting SELECT, and carry no
    write token. Returns the bare statement (comments stripped)."""
    stmt = "\n".join(l for l in block.splitlines() if not l.lstrip().startswith("--")).strip()
    if not stmt.endswith(";"):
        die(f"queries.sql `{marker}` block is not a terminated statement")
    core = stmt[:-1].strip()
    if ";" in core:
        die(f"queries.sql `{marker}` block holds more than one statement")
    if not re.match(r"(?i)select\b", core):
        die(f"queries.sql `{marker}` block does not start with SELECT")
    m = WRITE_TOKENS.search(core)
    if m:
        die(f"queries.sql `{marker}` block contains write token {m.group(1).upper()} — refused")
    return stmt


def pg_env_from_url(raw: str) -> dict[str, str]:
    """postgres URL → libpq env vars, so the password is never on psql's argv (session-db.mjs
    `pgEnvFromUrl`, ported). `?sslmode=` honoured; default `require`."""
    u = urllib.parse.urlsplit(raw)  # raises ValueError on a malformed URL — caller surfaces it
    if not u.hostname or not u.username:
        die("the DB URL is not a postgres URL (needs host + user)")
    q = urllib.parse.parse_qs(u.query)
    return {
        "PGHOST": u.hostname,  # urlsplit already strips IPv6 brackets and lowercases
        "PGPORT": str(u.port or 5432),
        "PGUSER": urllib.parse.unquote(u.username),
        "PGPASSWORD": urllib.parse.unquote(u.password or ""),
        "PGDATABASE": urllib.parse.unquote(u.path.lstrip("/")) or "postgres",
        "PGSSLMODE": (q.get("sslmode") or ["require"])[0],
    }


def resolve_db_url(db_env: str | None) -> str:
    """`--db-env` file → `DATABASE_URL` env → publish.load_db_url (env, then Vibhaga-DB/.env beside
    Admin). An explicit --db-env beats an ambient env var. Prints the SOURCE — never the value."""
    if db_env:
        p = Path(db_env)
        if not p.is_file():
            die(f"--db-env {db_env} is not a readable file")
        url = read_env(p).get("DATABASE_URL")
        if not url:
            die(f"--db-env {db_env} has no DATABASE_URL line")
        print(f"{PROG}: DB URL from --db-env {db_env}", file=sys.stderr)
        return url
    if os.environ.get("DATABASE_URL"):
        print(f"{PROG}: DB URL from DATABASE_URL env", file=sys.stderr)
        return os.environ["DATABASE_URL"]
    url = load_db_url(_auth.ENV_PATH)
    if not url:
        die("no DATABASE_URL in the environment, no --db-env, and no Vibhaga-DB/.env beside "
            f"Vibhaga-Admin ({_auth.ENV_PATH})")
    print(f"{PROG}: DB URL from Vibhaga-DB/.env", file=sys.stderr)
    return url


def run_block(pg: dict[str, str], batch_id: str, block: str, marker: str) -> list[str]:
    """One Q4 block through psql, read-only, SQL on stdin. Returns the non-empty stdout lines."""
    argv = ["psql", "-X", "-A", "-t", "-q", "-w", "-v", "ON_ERROR_STOP=1", "-v",
            f"batch_id={batch_id}", "-f", "-"]  # -w: never prompt for a password
    env = {**os.environ, **pg}
    try:
        proc = subprocess.run(argv, input=f"set default_transaction_read_only=on;\n{block}",
                              capture_output=True, text=True, env=env)
    except FileNotFoundError:
        die("psql is not on PATH")
    if proc.returncode != 0:
        err = proc.stderr.strip().splitlines()
        print(f"{PROG}: psql failed on {marker} (exit {proc.returncode})"
              + (f" — {err[-1]}" if err else ""), file=sys.stderr)
        raise SystemExit(1)
    return [l for l in proc.stdout.splitlines() if l.strip()]


# --------------------------------------------------------------------------- derived artefacts
def answers_of(node: dict, key: str) -> list[dict]:
    a = node.get(key)
    return a if isinstance(a, list) else []


def part_tree(parts: list[dict], qid: str) -> tuple[list[tuple[dict, str]], int]:
    """`parts` is q4b's FLAT list (parent_sub_question_id links it). Returns ((part, full id) in
    reading order — roots sorted by sort_order, then depth-first; the id is the label path
    `Q3.a`, `Q3.a.i`, …) and the orphan count. A part unreachable from the roots — a missing or
    cross-question parent, or a cycle — never vanishes: it lands under `Q<n>.ORPHAN<k>` with its
    own subtree hanging off it, in (sort_order, label) order."""
    children: dict = {}
    for p in parts:
        children.setdefault(p.get("parent_sub_question_id"), []).append(p)
    order = lambda s: (s.get("sort_order") or 0, s.get("label") or "")
    out: list[tuple[dict, str]] = []
    visited: set = set()

    def walk(parent_id, prefix):
        for p in sorted(children.get(parent_id, []), key=order):
            sid = p.get("sub_question_id")
            if sid in visited:  # cycle guard
                continue
            visited.add(sid)
            pid = f"{prefix}.{p.get('label')}"
            out.append((p, pid))
            walk(sid, pid)

    walk(None, qid)
    n_orphans = 0
    for p in sorted((p for p in parts if p.get("sub_question_id") not in visited), key=order):
        sid = p.get("sub_question_id")
        visited.add(sid)
        n_orphans += 1
        pid = f"{qid}.ORPHAN{n_orphans}"
        out.append((p, pid))
        walk(sid, pid)
    return out, n_orphans


def question_artefacts(q: dict) -> tuple[list[dict], list[str], int]:
    """(fields, figure lines, part count) for one q4b row. A figure line is
    `<visual-check id>\t<answer_id | sub_answer_id | ->` — the uuid lets the critic map an ans<k>
    position to a row even when q4b's created_at ordering disagrees with the staged order."""
    fields: list[dict] = []
    figs: list[str] = []
    qid = f"Q{q.get('question_number')}"
    if q.get("question_text"):
        fields.append({"id": f"{qid}.stem", "field": "question_text", "text": q["question_text"]})
    if q.get("question_text_sinhala"):
        fields.append({"id": f"{qid}.stem_sinhala", "field": "question_text_sinhala",
                       "text": q["question_text_sinhala"]})
    if q.get("diagram_dsl") is not None:
        figs.append(f"{qid}\t-")
    answers = answers_of(q, "answers")
    for k, a in enumerate(answers, 1):
        base = qid if len(answers) == 1 else f"{qid}.ans{k}"
        if a.get("approach"):
            fields.append({"id": f"{base}.approach", "field": "approach", "text": a["approach"]})
        if a.get("final_answer_latex"):
            fields.append({"id": f"{base}.final", "field": "final_answer_latex",
                           "text": a["final_answer_latex"]})
        if a.get("diagram_dsl") is not None:
            figs.append(f"{qid}.ans{k}\t{a.get('answer_id') or '-'}")
    parts, n_orphans = part_tree(q.get("parts") or [], qid)
    if n_orphans:
        print(f"{PROG}: WARNING {qid}: {n_orphans} orphan part(s)", file=sys.stderr)
    for p, pid in parts:
        if p.get("text"):
            fields.append({"id": f"{pid}.text", "field": "text", "text": p["text"]})
        if p.get("text_sinhala"):
            fields.append({"id": f"{pid}.text_sinhala", "field": "text_sinhala",
                           "text": p["text_sinhala"]})
        if p.get("diagram_dsl") is not None:
            figs.append(f"{pid}\t-")
        subs = answers_of(p, "sub_answers")
        for k, a in enumerate(subs, 1):
            base = pid if len(subs) == 1 else f"{pid}.ans{k}"
            if a.get("approach"):
                fields.append({"id": f"{base}.approach", "field": "approach", "text": a["approach"]})
            if a.get("final_answer_latex"):
                fields.append({"id": f"{base}.final", "field": "final_answer_latex",
                               "text": a["final_answer_latex"]})
            if a.get("diagram_dsl") is not None:
                figs.append(f"{pid}.ans{k}\t{a.get('sub_answer_id') or '-'}")
    return fields, figs, len(parts)


# -----------------------------------------------------------------------------------------------
def load_previous(spec: str) -> dict[str, str]:
    """`--previous` — a report dir holding hashes.txt, or a `Q<n> <sha256>` file directly."""
    p = Path(spec)
    f = p / "hashes.txt" if p.is_dir() else p
    if not f.is_file():
        die(f"--previous {spec}: {'no hashes.txt in that directory' if p.is_dir() else 'not a file'}")
    out: dict[str, str] = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(Q\d+)\s+([0-9a-f]{64})\s*$", line.strip())
        if not m:
            die(f"--previous {f}: bad line {line!r} — want `Q<n> <sha256>`")
        out[m.group(1)] = m.group(2)
    return out


def qnum(qid: str) -> int:
    return int(qid[1:]) if qid[1:].isdigit() else 10**9


def cmd_hashes(argv: list[str]) -> int:
    """`hashes <sid>` — the hashes.txt computation only: read Q4b, hash each line, print."""
    ap = argparse.ArgumentParser(
        prog="critic-read.py hashes",
        description="Print `Q<n> <sha256 of its Q4b line>` per question — exactly the hashes.txt "
                    "computation — so two critic rounds can be diffed without a report dir.")
    ap.add_argument("batch_id")
    ap.add_argument("--out", help="also write the lines to FILE")
    ap.add_argument("--db-env", help="a dotenv file to read DATABASE_URL from (wins over the env var)")
    ap.add_argument("--queries", default=str(QUERIES), help="queries.sql path (default: the plugin's)")
    a = ap.parse_args(argv)
    if not UUID_RE.match(a.batch_id):
        die(f"batch_id {a.batch_id!r} is not a uuid")
    block = slice_block(Path(a.queries).read_text(encoding="utf-8"), "Q4b")
    assert_single_select(block, "Q4b")
    pg = pg_env_from_url(resolve_db_url(a.db_env))
    lines = run_block(pg, a.batch_id, block, "q4b")
    if not lines:
        die(f"session {a.batch_id} has no questions — q4b returned 0 rows", 1)
    out = []
    for i, line in enumerate(lines):
        try:
            q = json.loads(line)
        except json.JSONDecodeError as e:
            die(f"q4b line {i + 1} is not JSON: {e}", 1)
        out.append(f"Q{q.get('question_number')} {hashlib.sha256(line.encode('utf-8')).hexdigest()}")
    text = "\n".join(out)
    print(text)
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
    return 0


# -----------------------------------------------------------------------------------------------
def self_test() -> int:
    """Offline smoke (the check-suite entry): slice the three Q4 blocks out of the REAL queries.sql
    and assert each is a single read-only SELECT — plus one pg_env_from_url round-trip. No DB."""
    fails = 0
    try:
        sql_text = QUERIES.read_text(encoding="utf-8")
    except OSError as e:
        print(f"critic-read --self-test: FAIL (queries.sql unreadable: {e})")
        return 1
    checks = 0
    for marker in BLOCKS.values():
        try:
            stmt = assert_single_select(slice_block(sql_text, marker), marker)
            assert stmt.lstrip().upper().startswith("SELECT")
            checks += 1
        except (SystemExit, AssertionError):
            print(f"critic-read --self-test: FAIL ({marker} block)")
            fails += 1
    env = pg_env_from_url("postgres://u%40x:p%40ss@db.example.test:6543/fakedb?sslmode=prefer")
    if (env["PGUSER"], env["PGPASSWORD"], env["PGPORT"], env["PGDATABASE"], env["PGSSLMODE"]) \
            == ("u@x", "p@ss", "6543", "fakedb", "prefer"):
        checks += 1
    else:
        print("critic-read --self-test: FAIL (pg_env_from_url)")
        fails += 1
    print(f"critic-read --self-test: {'PASS' if not fails else f'{fails} FAIL'} — {checks} check(s)")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--self-test"]:
        return self_test()
    if argv[:1] == ["hashes"]:
        return cmd_hashes(argv[1:])
    ap = argparse.ArgumentParser(prog="critic-read.py",
                                 description="Read one playground batch for the qgen-critic: Q4a/b/c "
                                             "read-only via psql, plus fields/hashes/figures artefacts.")
    ap.add_argument("batch_id", help="the playground session id (a question_batches uuid)")
    ap.add_argument("--out", required=True, help="output directory for q4a.json, q4b/q4c.jsonl, …")
    ap.add_argument("--db-env", help="a dotenv file to read DATABASE_URL from (wins over DATABASE_URL in the environment)")
    ap.add_argument("--queries", default=str(QUERIES), help="queries.sql path (default: the plugin's)")
    ap.add_argument("--previous", help="the previous round's report dir (its hashes.txt) or a "
                                       "`Q<n> <sha256>` file — fields.json/figures.txt then cover "
                                       "only changed-or-new questions, the rest land in carried.txt")
    a = ap.parse_args(argv)

    if not UUID_RE.match(a.batch_id):
        die(f"batch_id {a.batch_id!r} is not a uuid")

    sql_text = Path(a.queries).read_text(encoding="utf-8")
    blocks = {}
    for key, marker in BLOCKS.items():
        raw = slice_block(sql_text, marker)
        assert_single_select(raw, marker)
        blocks[key] = raw

    url = resolve_db_url(a.db_env)
    pg = pg_env_from_url(url)
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    q4a_lines = run_block(pg, a.batch_id, blocks["q4a"], "q4a")
    if len(q4a_lines) != 1:
        die(f"session not found — q4a returned {len(q4a_lines)} row(s), expected 1", 1)
    try:
        session = json.loads(q4a_lines[0])
    except json.JSONDecodeError as e:
        die(f"q4a row is not JSON: {e}", 1)
    (out_dir / "q4a.json").write_text(json.dumps(session, ensure_ascii=False, indent=1) + "\n",
                                    encoding="utf-8")

    q4b_lines = run_block(pg, a.batch_id, blocks["q4b"], "q4b")
    if not q4b_lines:
        die(f"session {a.batch_id} has no questions — q4b returned 0 rows", 1)
    (out_dir / "q4b.jsonl").write_text("\n".join(q4b_lines) + "\n", encoding="utf-8")
    questions = []
    for i, line in enumerate(q4b_lines):
        try:
            questions.append(json.loads(line))
        except json.JSONDecodeError as e:
            die(f"q4b line {i + 1} is not JSON: {e}", 1)

    q4c_lines = run_block(pg, a.batch_id, blocks["q4c"], "q4c")
    (out_dir / "q4c.jsonl").write_text(("\n".join(q4c_lines) + "\n") if q4c_lines else "",
                                     encoding="utf-8")

    parts_total = 0
    hashes: list[str] = []
    per_q: list[tuple[str, list, list]] = []
    for q, line in zip(questions, q4b_lines):
        f, g, nparts = question_artefacts(q)
        qid = f"Q{q.get('question_number')}"
        per_q.append((qid, f, g))
        parts_total += nparts
        hashes.append(f"{qid} {hashlib.sha256(line.encode('utf-8')).hexdigest()}")

    fields: list[dict] = []
    figs: list[str] = []
    if a.previous:
        # --previous: fields/figures cover only changed-or-new questions; the unchanged are
        # carried by hash into carried.txt — the critic re-derives only what moved (§6).
        prev = load_previous(a.previous)
        cur = dict(h.split(" ", 1) for h in hashes)
        changed = sorted((q for q in cur if prev.get(q) != cur[q]), key=qnum)
        carried = sorted((q for q in cur if prev.get(q) == cur[q]), key=qnum)
        gone = sorted((q for q in prev if q not in cur), key=qnum)
        for qid, f, g in per_q:
            if qid in set(changed):
                fields += f
                figs += g
        (out_dir / "carried.txt").write_text(
            ("\n".join(f"{q} {cur[q]}" for q in carried) + "\n") if carried else "",
            encoding="utf-8")
        print(f"changed: {changed} · carried: {carried}"
              + (f" · gone: {gone}" if gone else ""))
    else:
        for _qid, f, g in per_q:
            fields += f
            figs += g

    (out_dir / "fields.json").write_text(json.dumps(fields, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8")
    (out_dir / "hashes.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    (out_dir / "figures.txt").write_text(("\n".join(figs) + "\n") if figs else "", encoding="utf-8")

    print(f"{PROG}: {len(questions)} question(s) · {parts_total} part(s) · {len(figs)} figure(s) · "
          f"{len(q4c_lines)} other row(s) on the same lessons → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
