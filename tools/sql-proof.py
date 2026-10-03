#!/usr/bin/env python3
"""sql-proof.py — the generate flow's two queries.sql proofs as ONE command (W7).

    sql-proof.py q2 <session_id> --expected N [--db-env FILE] [--out FILE.json]
    sql-proof.py q3 --actor <uuid> [--auth-env FILE] [--out FILE.json]

q2 runs queries.sql Q2 — the post-publish proof — on the CONTENT database; q3 runs Q3 — the auth
revocation proof — on the ADMIN AUTH project (a different Supabase project: zero sessions for a user
that does not exist there proves nothing, which is why Q3 carries the wrong_project check). Each block
is sliced out of the REAL queries.sql (from its `-- Q2` / `-- Q3` header comment to the statement's
terminating `;`), then guarded locally: ONE statement starting WITH or SELECT — Q2 opens `WITH`, so
critic-read's SELECT-only assertion does not apply — and no write token (a smoke check; the read-only
transaction is the real guard; slicing stops at the first `;` on a non-comment line, so a block must
never hold one inside a string literal).

psql runs `-X -q -w -A -F '\\t' -P footer=off -v ON_ERROR_STOP=1 -v batch_id=… -v expected=…` (q3:
`-v actor_id=…`) with the SQL on stdin (`-f -`) prefixed `set default_transaction_read_only=on;`.
Unaligned output keeps the header row so each count maps to its column name. The DB URL is split into
PG* environment variables — NEVER on argv, never printed (critic-read.py's pg_env_from_url, itself a
port of session-db.mjs's pgEnvFromUrl — reused, not copied).

URL resolution — the SOURCE is announced on stderr, never the value:
  q2 (content):  --db-env FILE → DATABASE_URL env → Vibhaga-DB/.env beside Vibhaga-Admin
                 (identical to critic-read.py's resolve_db_url — reused, not copied)
  q3 (auth):     --auth-env FILE (its VIBHAGA_ADMIN_AUTH_DB_URL line) → the same env var → the line
                 in Vibhaga-Admin/.env.local (VIBHAGA_ADMIN_ENV wins, else _admin_auth's ENV_PATH)

Output: one `key=value` counts line (every column the query returned), then `q2: ok` or
`q2: NOT ok — <the failing counts>` (same for q3). `--out` writes
{"query": "Q2"|"Q3", "session_id"|"actor_id": …, "counts": {…}, "ok": bool, "checked_at": ISO}.
Counts only — never a token, an email, or a row's contents.

Exit: 0 ok is t · 1 not ok / psql failed / unexpected output · 2 usage or env (non-uuid id,
--expected < 1, no URL source, queries.sql block missing or failing the guard).
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _admin_auth as _auth  # noqa: E402  (ENV_PATH resolves VIBHAGA_ADMIN_ENV → .env.local)

_spec = importlib.util.spec_from_file_location("critic_read", HERE / "critic-read.py")
cr = importlib.util.module_from_spec(_spec)  # noqa: E402  (hyphenated — imported, not copied)
_spec.loader.exec_module(cr)
cr.PROG = "sql-proof"

PROG = "sql-proof"
QUERIES = HERE.parent / "queries.sql"
UUID_RE = cr.UUID_RE


def die(msg: str, code: int = 2) -> "SystemExit":
    print(f"{PROG}: {msg}", file=sys.stderr)
    raise SystemExit(code)


def slice_proof(sql_text: str, marker: str) -> str:
    """The marker block sliced to ONE statement — critic-read.slice_block does the cutting; the
    guard here is the local one (WITH or SELECT — Q2 opens WITH — and no write token)."""
    raw = cr.slice_block(sql_text, marker)
    stmt = "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith("--")).strip()
    if not stmt.endswith(";"):
        die(f"queries.sql `{marker}` block is not a terminated statement")
    core = stmt[:-1].strip()
    if ";" in core:
        die(f"queries.sql `{marker}` block holds more than one statement")
    if not re.match(r"(?i)(with|select)\b", core):
        die(f"queries.sql `{marker}` block does not start with WITH or SELECT")
    m = cr.WRITE_TOKENS.search(core)
    if m:
        die(f"queries.sql `{marker}` block contains write token {m.group(1).upper()} — refused")
    return raw  # sent to psql WITH its comments, same as critic-read


def find_auth_url(auth_env: str | None, env_path: Path | None = None) -> tuple[str | None, str]:
    """`--auth-env` file → VIBHAGA_ADMIN_AUTH_DB_URL env → that key's line in the admin env file
    (env_path when given, else VIBHAGA_ADMIN_ENV, else _admin_auth.ENV_PATH). Returns
    (url, source) or (None, reason); prints nothing — callers announce the source or the miss.
    Shared with playground-publish.py's post-logout Q3 — resolution order is never copied."""
    if auth_env:
        p = Path(auth_env)
        if not p.is_file():
            return None, f"--auth-env {auth_env} is not a readable file"
        url = cr.read_env(p).get("VIBHAGA_ADMIN_AUTH_DB_URL")
        if not url:
            return None, f"--auth-env {auth_env} has no VIBHAGA_ADMIN_AUTH_DB_URL line"
        return url, f"--auth-env {auth_env}"
    if os.environ.get("VIBHAGA_ADMIN_AUTH_DB_URL"):
        return os.environ["VIBHAGA_ADMIN_AUTH_DB_URL"], "VIBHAGA_ADMIN_AUTH_DB_URL env"
    ep = env_path or (Path(os.environ["VIBHAGA_ADMIN_ENV"]) if os.environ.get("VIBHAGA_ADMIN_ENV")
                      else _auth.ENV_PATH)
    url = cr.read_env(ep).get("VIBHAGA_ADMIN_AUTH_DB_URL") if ep.is_file() else None
    if url:
        return url, str(ep)
    return None, ("not in the environment, no --auth-env file, and no line in "
                  f"{ep} (the Admin Auth project URL lives in Vibhaga-Admin/.env.local or the environment)")


def resolve_auth_url(auth_env: str | None) -> str:
    """The CLI wrapper over find_auth_url — prints the SOURCE (never the value) or dies."""
    url, src = find_auth_url(auth_env)
    if url:
        print(f"{PROG}: auth DB URL from {src}", file=sys.stderr)
        return url
    die(src if auth_env else f"no VIBHAGA_ADMIN_AUTH_DB_URL — {src}")


# psql connection errors echo the server's host and resolved IP (`connection to server at
# "db.<ref>.example.co" (1.2.3.4) …`, `could not translate host name "…"`) — and these lines are
# printed into transcripts, so every echoed stderr line passes through redact() first.
DNS_RE = re.compile(r"(?<![\w.])(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")        # a dotted DNS name
IPV4_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
IPV6_RE = re.compile(r"\b(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:]*")
USER_RE = re.compile(r'user\s+"[^"]*"')


def redact(line: str, host: str | None = None) -> str:
    """Blank anything that could identify the DB before a psql stderr line is echoed: the URL's
    own host, any DNS name containing "supabase" (a dotted name like `auth.users` survives —
    identifiers are not hosts), IP literals, and `user "<name>"`. The error wording itself —
    ERROR:/FATAL:/permission denied — is what we keep."""
    if host:
        line = line.replace(host, "<host>")
    line = DNS_RE.sub(lambda m: "<host>" if "supabase" in m.group(0).lower() else m.group(0),
                      line)
    line = IPV4_RE.sub("<ip>", line)
    line = IPV6_RE.sub("<ip>", line)
    return USER_RE.sub('user "<user>"', line)


def run_proof(pg: dict[str, str], block: str, variables: list[tuple[str, str]], tag: str) -> dict:
    """One proof block through psql, read-only, SQL on stdin, PG* env only. Returns the row as
    {column: coerced value}; exits 1 on a psql failure or a header+row it cannot map."""
    argv = ["psql", "-X", "-q", "-w", "-A", "-F", "\t", "-P", "footer=off",
            "-v", "ON_ERROR_STOP=1"]
    for k, v in variables:
        argv += ["-v", f"{k}={v}"]
    argv += ["-f", "-"]
    try:
        proc = subprocess.run(argv, input=f"set default_transaction_read_only=on;\n{block}",
                              capture_output=True, text=True, env={**os.environ, **pg})
    except FileNotFoundError:
        die("psql is not on PATH")
    if proc.returncode != 0:
        # psql stderr carries no URL and no password, but a connection failure DOES carry the
        # host and its IP — every echoed line is redact()ed first. Lead with the ERROR:/FATAL:
        # line (psql prefixes it "psql: error:" so it may sit mid-line), then up to the last 3
        # stderr lines — the owner once saw only `^`, the caret under a psql position marker.
        err = [redact(l.strip(), pg.get("PGHOST"))
               for l in proc.stderr.splitlines() if l.strip()]
        flagged = next((l for l in err if re.search(r"(ERROR|FATAL):", l)), None)
        tail = err[-3:]
        shown = ([flagged] if flagged and flagged not in tail else []) + tail
        print(f"{PROG}: psql failed on {tag} (exit {proc.returncode})"
              + ("" if shown else " — no stderr"), file=sys.stderr)
        for l in shown:
            print(f"{PROG}:   {l}", file=sys.stderr)
        if any("permission denied for schema auth" in l for l in err):
            print(f"{PROG}: the Q3 role needs USAGE on schema auth — e.g. `grant anon to <role>`; "
                  "see skills/generate/SKILL.md step 11", file=sys.stderr)
        raise SystemExit(1)
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    if len(lines) != 2:
        die(f"{tag} returned {len(lines)} line(s) — expected a header plus exactly one row", 1)
    cols, vals = lines[0].split("\t"), lines[1].split("\t")
    if len(cols) != len(vals):
        die(f"{tag}: header has {len(cols)} column(s) but the row has {len(vals)}", 1)
    return {c: coerce(v) for c, v in zip(cols, vals)}


def coerce(v: str):
    if v in ("t", "f"):
        return v == "t"
    return int(v) if re.fullmatch(r"-?\d+", v) else v


def show(v) -> str:
    return ("t" if v else "f") if isinstance(v, bool) else str(v)


def failing_q2(counts: dict, expected: int) -> list[str]:
    """The same conditions the Q2 `ok` expression encodes — so a false ok says which broke."""
    bad = []
    if counts.get("session_exists") != 1:
        bad.append(f"session_exists={show(counts.get('session_exists'))}")
    if counts.get("questions") != expected:
        bad.append(f"questions={show(counts.get('questions'))} (expected {expected})")
    for k in ("not_flagged", "not_published", "papered", "scope_mismatch",
              "signed_answers", "signed_sub_answers", "unanswered_leaves"):
        if counts.get(k) != 0:
            bad.append(f"{k}={show(counts.get(k))}")
    return bad


def failing_q3(counts: dict) -> list[str]:
    """Q3's `ok`: the actor exists on the AUTH project, no session or live refresh token survives,
    and the database really is the auth project (public.question_batches absent)."""
    bad = []
    if counts.get("actor_exists") != 1:
        bad.append(f"actor_exists={show(counts.get('actor_exists'))}")
    for k in ("sessions", "active_refresh_tokens"):
        if counts.get(k) != 0:
            bad.append(f"{k}={show(counts.get(k))}")
    if counts.get("wrong_project") is not False:
        bad.append(f"wrong_project={show(counts.get('wrong_project'))}")
    return bad


def write_out(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                 encoding="utf-8")


def report(tag: str, row: dict, bad: list[str]) -> int:
    """Counts line + verdict; returns the exit code. `ok` missing from the row fails closed."""
    ok = row.get("ok")
    print(" ".join(f"{k}={show(v)}" for k, v in row.items()))
    if ok is True:
        print(f"{tag}: ok")
        return 0
    detail = ", ".join(bad) if bad else f"ok={show(ok)}"
    print(f"{tag}: NOT ok — {detail}")
    return 1


def out_payload(tag: str, id_key: str, id_val: str, counts: dict, ok: bool) -> dict:
    return {"query": tag.upper(), id_key: id_val, "counts": counts, "ok": ok,
            "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="sql-proof.py",
        description="queries.sql Q2 (content DB) and Q3 (Admin Auth project) read-only via psql; "
                    "exits on the ok column.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q2 = sub.add_parser("q2", help="post-publish proof for a playground session (content DB)")
    q2.add_argument("session_id", help="the question_batches uuid")
    q2.add_argument("--expected", type=int, required=True,
                    help="how many questions the batch must hold (positive int)")
    q2.add_argument("--db-env", help="a dotenv file to read DATABASE_URL from (wins over the env var)")
    q2.add_argument("--out", help="write the counts JSON to this path")
    q3 = sub.add_parser("q3", help="auth revocation proof for an actor (Admin Auth project)")
    q3.add_argument("--actor", required=True, help="the auth.users uuid the tool signed in as")
    q3.add_argument("--auth-env", help="a dotenv file to read VIBHAGA_ADMIN_AUTH_DB_URL from")
    q3.add_argument("--out", help="write the counts JSON to this path")
    a = ap.parse_args(argv)

    sql_text = QUERIES.read_text(encoding="utf-8")
    if a.cmd == "q2":
        if not UUID_RE.match(a.session_id):
            die(f"session_id {a.session_id!r} is not a uuid")
        if not isinstance(a.expected, int) or a.expected < 1:
            die("--expected must be a positive integer (how many questions you published)")
        block = slice_proof(sql_text, "Q2")
        pg = cr.pg_env_from_url(cr.resolve_db_url(a.db_env))
        row = run_proof(pg, block, [("batch_id", a.session_id), ("expected", str(a.expected))], "q2")
        counts = {k: v for k, v in row.items() if k != "ok"}
        bad = failing_q2(counts, a.expected)
        rc = report("q2", row, bad)
        if a.out:
            write_out(a.out, out_payload("q2", "session_id", a.session_id, counts,
                                         row.get("ok") is True))
        return rc

    # q3
    if not UUID_RE.match(a.actor):
        die(f"--actor {a.actor!r} is not a uuid")
    block = slice_proof(sql_text, "Q3")
    pg = cr.pg_env_from_url(resolve_auth_url(a.auth_env))
    row = run_proof(pg, block, [("actor_id", a.actor)], "q3")
    counts = {k: v for k, v in row.items() if k != "ok"}
    bad = failing_q3(counts)
    rc = report("q3", row, bad)
    if a.out:
        write_out(a.out, out_payload("q3", "actor_id", a.actor, counts,
                                     row.get("ok") is True))
    return rc


if __name__ == "__main__":
    sys.exit(main())
