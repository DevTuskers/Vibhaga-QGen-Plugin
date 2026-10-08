#!/usr/bin/env python3
"""playground-publish.py — P6.1: the agent question-playground client as ONE committed tool
(plan 2026-09-25-agent-question-playground §P6.1; decision 0018 OD-2/OD-4/PD-6; decision 0014 PD-1
guard-rails; TRAPS T9, T77, T5).

A playground "session" is a `question_batches` row — scoped grade XOR exam, plus subject/medium and
lesson intent — holding a staged questions doc in R2 (`playground/<id>/questions.json`), exactly the
row+doc split of an onboarding job. Publish writes live rows with `source_batch_id` = the session and
`source_paper_id` NULL, and every row lands FLAGGED (`needs_human_review` forced true — 0018 OD-2).
This is publish.py's sibling (`import publish as _pub`): same transport, a FRESH password-grant token
per stage, and the same guard-rail shape, adapted to the playground routes:

  1. the session's stored scope is echoed and must EQUAL `--scope` — publish refuses on mismatch
  2. `--ledger` records the publish set BEFORE the first publish request (T9) — merged by session id,
     never overwritten, written atomically (temp file + os.replace)
  3. the dry-run's `signatures_at_risk` is printed and the run refuses unless `--accept-signatures N`
     equals it (0 must be typed)
  4. every chosen question must carry `ingestion_metadata.needs_human_review: true`; `doc put` refuses
     a staged question that lacks the flag or carries an `exam` key (0018 PD-6 — scope lives on the
     session, never on a question)
  5. after EACH publish the tool writes the OD-2 flag + `published`/`published_at` back into the staged
     doc itself — the playground publish response does NOT mirror it (Admin's `persistPublishOutcome`
     does this in the UI; the API leaves it to the client) — then two read-backs: the staged doc again,
     and the LIVE ROWS by direct SELECT, never the API (Hyperdrive's cache is ~75 s stale, T5): the T77
     staged-vs-published diff plus a per-id provenance query
  6. `POST /auth/v1/logout?scope=global` is the last act of every network subcommand. After a WRITE
     subcommand (session create/archive, doc put, publish, unpublish, flag-review) the revocation is
     then PROVEN: queries.sql Q3 runs on the merged (content) project via sql-proof's own resolver +
     psql runner when a DB URL resolves (the transition-era VIBHAGA_ADMIN_AUTH_DB_URL sources, else
     the content-DB chain), the counts land in the ledger under the
     session, and a NOT-ok after a successful write exits 5. With no URL source one `q3: PENDING`
     line stands in for the proof. Read-only subcommands print nothing past the logout line.

`clear-review` / `unflag-review` are REFUSED with zero network calls and no env read: lowering a review
flag is a human act (decision 0014 PD-1 guard-rail 4 / PD-2, 0009, 0020) — use 'Go live' / 'Remove flag'
on the Admin /generate page.

Usage (from anywhere; credentials + URLs are read at run time from Vibhaga-Admin/.env.local — never printed):
  playground-publish.py session create --name N --scope grade=6,subject=Mathematics,medium=sinhala --lessons uuid,uuid --ledger L.json
  playground-publish.py session show <sid> · session list [--status active|archived] [--limit N] · session archive <sid> --ledger L.json
  playground-publish.py doc get <sid> --out staged.json
  playground-publish.py doc put <sid> --staged Q.json --ledger L.json [--drop-missing [--allow-drop]]
  playground-publish.py validate <sid> --staged Q.json
  playground-publish.py publish <sid> --staged Q.json --scope grade=6,subject=Mathematics,medium=sinhala --ids-file ids.json
                            --ledger L.json --accept-signatures N [--dry-run]
  playground-publish.py unpublish <sid> --ids-file ids.json --ledger L.json
  playground-publish.py flag-review <sid> --ids-file ids.json --ledger L.json
  playground-publish.py lessons [--grade N] [--exam SLUG] [--subject S]
  playground-publish.py questions list [--lesson-id UUID[,UUID]] [--status draft|published] [--needs-human-review true|false]
                            [--grade N] [--exam S] [--subject S] [--medium M] [--batch-id UUID] [--q TEXT] [--limit N] [--all] [--out F]
  playground-publish.py questions show <question_id> [--out F]
  playground-publish.py --self-test                                        # NO network: runs test_playground_publish.py

  every network subcommand: --env PATH (default: Vibhaga-Admin/.env.local, found by walking up) · --cred-prefix VIBHAGA_ADMIN
  `--scope` is parse_kv format: grade=<int>|exam=<slug> (XOR), subject as catalogued, medium ∈ sinhala|english|tamil.
  publish always sends question_ids (omitting them would publish ALL); --ids-file is therefore required.
  Read-back 2 needs DATABASE_URL (or Vibhaga-DB/.env beside Vibhaga-Admin) and the `psql` binary; publish
  makes FOUR grants per run: publish:get, publish:dry-run, publish:loop, publish:readback.

Ledger shape (--ledger, merged by session id, never dropping a key):
  {"sessions": {"<sid>": {"name", "scope", "lesson_ids", "created_at", "status",
    "published":  {question_ids, questions:[ids_of…], written_at, updated_at, last_publish_ids},
    "unpublished": [ids…], "flag_raised": [ids…]}}}

Exit codes: 0 ok · 1 read-back mismatch / staged doc stale / self-test failure · 2 usage / missing input
            · 3 refused (scope, archived, unflagged, exam-keyed, drop, staged≠server, validate errors)
            · 4 refused at the dry-run (signatures) · 5 a network call or write failed mid-run,
            or the post-write Q3 proof ran and was NOT ok · 6 auth failed.
"""
from __future__ import annotations

import argparse, datetime as dt, importlib.util, json, os, re, sys, tempfile, time, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _admin_auth as _auth  # noqa: E402  (shared env + transport — a bare urllib UA gets Cloudflare 1010)
import publish as _pub      # noqa: E402  (the sibling tool — reuse, don't copy)

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("sql_proof", HERE / "sql-proof.py")
sqlp = importlib.util.module_from_spec(_spec)  # noqa: E402  (Q3's URL resolution + psql runner — reused, not copied)
_spec.loader.exec_module(sqlp)

Refuse = _pub.Refuse
ARCHIVED_MSG = "session is archived — re-open it in the Admin /generate page first; the API would 409 batch_archived"
MEDIUMS = ("sinhala", "english", "tamil")

PROVENANCE_SQL = """SELECT COALESCE(json_agg(json_build_object(
  'question_id', q.question_id, 'status', q.status, 'needs_human_review', q.needs_human_review,
  'source_batch_id', q.source_batch_id, 'source_paper_id', q.source_paper_id,
  'signed_answers', (SELECT count(*) FROM answers a WHERE a.question_id = q.question_id AND a.verified_by IS NOT NULL),
  'signed_sub_answers', (SELECT count(*) FROM sub_answers sa JOIN sub_questions s ON s.sub_question_id = sa.sub_question_id
                         WHERE s.question_id = q.question_id AND sa.verified_by IS NOT NULL))), '[]'::json)
FROM questions q WHERE q.question_id::text IN (__IDS__);"""


class PlaygroundApi(_pub.Api):
    """The playground plane: same password grant + transport as publish.py's Api, one method per route."""

    def _pg(self, method, path, body=None, ok=(200,)):
        st, js = self._json(method, f"{self.base}{path}", self._auth(), body, scope="admin")
        if st not in ok:
            raise Refuse(f"{method} {path} → {_auth.response_error(st, js)}", 5)
        return js

    def create_session(self, meta: dict) -> dict:
        return checked_session(self._pg("POST", "/v1/admin/playground/sessions", meta, ok=(201,)))

    def get_session(self, sid: str) -> dict:
        return checked_session(self._pg("GET", f"/v1/admin/playground/sessions/{sid}"))

    def list_sessions(self, params: dict) -> dict:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        js = self._pg("GET", f"/v1/admin/playground/sessions{'?' + qs if qs else ''}")
        if not isinstance(js.get("data"), list) or (js.get("next_cursor") is not None and not isinstance(js["next_cursor"], str)):
            raise Refuse("malformed session list response (body withheld)", 5)
        for s in js["data"]: checked_session(s)
        return js

    def patch_session(self, sid: str, patch: dict) -> dict:
        return checked_session(self._pg("PATCH", f"/v1/admin/playground/sessions/{sid}", patch))

    def get_doc(self, sid: str) -> dict:
        """The PlaygroundDoc. ready:false (empty questions/stats placeholders) is NOT an error here —
        `doc get` may show it; `publish` requires ready."""
        return checked_pg_doc(self._pg("GET", f"/v1/admin/playground/sessions/{sid}/questions"))

    def put_doc(self, sid: str, questions: list) -> dict:
        js = checked_pg_doc(self._pg("PUT", f"/v1/admin/playground/sessions/{sid}/questions", {"questions": questions}))
        if js.get("ready") is not True:
            raise Refuse("PUT questions returned ready:false (body withheld)", 5)
        return js

    def validate(self, sid: str, questions: list) -> tuple[int, dict]:
        return self._json("POST", f"{self.base}/v1/admin/playground/validate", self._auth(), {"session_id": sid, "questions": questions}, scope="admin")

    def publish(self, sid: str, ids: list[str], dry_run=False) -> tuple[int, dict]:
        body: dict = {"question_ids": ids}  # ALWAYS sent — omitting it would publish ALL
        if dry_run: body["dry_run"] = True
        return self._json("POST", f"{self.base}/v1/admin/playground/sessions/{sid}/publish", self._auth(), body, scope="admin")

    def unpublish(self, sid: str, ids: list[str]) -> tuple[int, dict]:
        return self._json("POST", f"{self.base}/v1/admin/playground/sessions/{sid}/unpublish", self._auth(), {"question_ids": ids}, scope="admin")

    def flag_review(self, sid: str, ids: list[str]) -> tuple[int, dict]:
        return self._json("POST", f"{self.base}/v1/admin/playground/sessions/{sid}/flag-review", self._auth(), {"question_ids": ids}, scope="admin")

    def list_lessons(self) -> dict:
        return self._pg("GET", "/v1/admin/lessons")

    def list_questions(self, params: dict) -> dict:
        qs = urllib.parse.urlencode(params)
        return self._pg("GET", f"/v1/admin/playground/questions{'?' + qs if qs else ''}")

    def get_question(self, qid: str) -> dict:
        return self._pg("GET", f"/v1/admin/playground/questions/{qid}")


# ----------------------------------------------------------------------------------------------- response shapes (openapi.admin.yaml)
def checked_session(js) -> dict:
    req = {"id", "name", "grade", "exam", "subject", "medium", "lesson_ids", "r2_key", "status", "question_count", "created_by_admin_id", "created_at", "updated_at"}
    ok = isinstance(js, dict) and req <= js.keys() and _auth.valid_uuid(js["id"]) and isinstance(js["name"], str) \
        and (js["grade"] is None or type(js["grade"]) is int) and (js["exam"] is None or isinstance(js["exam"], str)) \
        and (js["subject"] is None or isinstance(js["subject"], str)) and (js["medium"] is None or js["medium"] in MEDIUMS) \
        and isinstance(js["lesson_ids"], list) and all(_auth.valid_uuid(i) for i in js["lesson_ids"]) \
        and isinstance(js["r2_key"], str) and js["status"] in ("active", "archived") and type(js["question_count"]) is int \
        and (js["created_by_admin_id"] is None or _auth.valid_uuid(js["created_by_admin_id"])) \
        and isinstance(js["created_at"], str) and isinstance(js["updated_at"], str)
    if not ok:
        raise Refuse("malformed session response (body withheld)", 5)
    return js


def checked_pg_doc(js) -> dict:
    if not isinstance(js, dict) or type(js.get("ready")) is not bool or not isinstance(js.get("questions"), list) \
            or not isinstance(js.get("stats"), dict) or not isinstance(js.get("session"), dict):
        raise Refuse("malformed staged doc response (body withheld)", 5)
    for q in js["questions"]:
        if not isinstance(q, dict) or not isinstance(q.get("question_id"), str) or not 1 <= len(q["question_id"]) <= 64:
            raise Refuse("malformed staged doc response (body withheld)", 5)
    if any(type(js["stats"].get(k)) is not int or js["stats"][k] < 0 for k in ("questions", "flagged")):
        raise Refuse("malformed staged doc response (body withheld)", 5)
    checked_session(js["session"])
    return js


def checked_validate_report(js) -> dict:
    if not isinstance(js, dict) or type(js.get("ok")) is not bool or not isinstance(js.get("results"), list):
        raise Refuse("malformed validate response (body withheld)", 5)
    for r in js["results"]:
        if not isinstance(r, dict) or type(r.get("index")) is not int or not isinstance(r.get("errors"), list) \
                or not isinstance(r.get("warnings"), list) or any(not isinstance(x, str) for x in r["errors"] + r["warnings"]) \
                or (r.get("question_id") is not None and not _auth.valid_uuid(r["question_id"])):
            raise Refuse("malformed validate response (body withheld)", 5)
    return js


def checked_dry_run(js) -> dict:
    per = {"question_id", "first_publish", "unchanged", "changed_field", "signed_count", "would_destroy_signatures"}
    if not isinstance(js, dict) or js.get("dry_run") is not True or type(js.get("signatures_at_risk")) is not int \
            or type(js.get("unchanged_count")) is not int or not isinstance(js.get("questions"), list):
        raise Refuse("malformed dry-run response (body withheld)", 4)
    for q in js["questions"]:
        if not isinstance(q, dict) or not per <= q.keys() or not _auth.valid_uuid(q["question_id"]) \
                or type(q["signed_count"]) is not int or not all(type(q[k]) is bool for k in ("first_publish", "unchanged", "would_destroy_signatures")) \
                or (q["changed_field"] is not None and not isinstance(q["changed_field"], str)):
            raise Refuse("malformed dry-run response (body withheld)", 4)
    return js


def checked_publish_result(js) -> dict:
    if not isinstance(js, dict) or any(type(js.get(k)) is not int or js[k] < 0 for k in ("published", "sub_questions", "answers", "sub_answers")) \
            or any(not isinstance(js.get(k), list) for k in ("question_ids", "reflagged")):
        raise Refuse("malformed publish response (body withheld)", 5)
    for k in ("unchanged", "reraised", "signatures_destroyed", "signatures_preserved"):
        if k in js and not isinstance(js[k], list):
            raise Refuse("malformed publish response (body withheld)", 5)
        js.setdefault(k, [])
    if any(not _auth.valid_uuid(i) for k in ("question_ids", "reflagged", "unchanged", "reraised", "signatures_destroyed", "signatures_preserved") for i in js[k]):
        raise Refuse("malformed publish response (body withheld)", 5)
    return js


def checked_unpublish(js) -> dict:
    if not isinstance(js, dict) or type(js.get("unpublished")) is not int or js["unpublished"] < 0 \
            or any(not isinstance(js.get(k), list) or not all(_auth.valid_uuid(i) for i in js[k]) for k in ("question_ids", "not_in_session")):
        raise Refuse("malformed unpublish response (body withheld)", 5)
    return js


def checked_flag_response(js) -> dict:
    if not isinstance(js, dict) or type(js.get("flagged")) is not int or js["flagged"] < 0 \
            or any(not isinstance(js.get(k), list) or not all(_auth.valid_uuid(i) for i in js[k]) for k in ("question_ids", "no_live_row")) \
            or ("staged_doc_updated" in js and type(js["staged_doc_updated"]) is not bool):
        raise Refuse("malformed flag-review response (body withheld)", 5)
    return js


def checked_summary(js) -> dict:
    if not isinstance(js, dict) or not _auth.valid_uuid(js.get("question_id")) or js.get("status") not in ("draft", "published") \
            or type(js.get("needs_human_review")) is not bool or type(js.get("question_number")) is not int or not isinstance(js.get("stem_excerpt"), str):
        raise Refuse("malformed questions list response (body withheld)", 5)
    return js


# ----------------------------------------------------------------------------------------------- local inputs / ledger
def need_uuid(v, what="id") -> str:
    """Validate + case-normalise: Postgres renders uuids lower-case, so every id we keep/compare
    or interpolate into SQL must be lowered at the input boundary."""
    if not _auth.valid_uuid(v):
        raise Refuse(f"bad {what} {v!r} — want a uuid", 2)
    return v.lower()


def scope_from_kv(s) -> dict:
    """`--scope` → the session-scope shape; local rules (exit 2): medium enum, grade XOR exam."""
    try:
        kv = s if isinstance(s, dict) else _pub.parse_kv(s)
    except ValueError:
        raise Refuse("bad --scope (grade must be an integer)", 2) from None
    scope = _pub.norm_scope(kv)
    if scope["medium"] not in MEDIUMS:
        raise Refuse("--scope needs medium=sinhala|english|tamil", 2)
    if (scope["grade"] is None) == (scope["exam"] is None):
        raise Refuse("--scope needs grade XOR exam (0006: a question is a grade question OR an exam question, never both)", 2)
    return scope


def parse_uuid_list(s, what="--lessons") -> list[str]:
    ids = [p.strip().lower() for p in (s or "").split(",") if p.strip()]
    if any(not _auth.valid_uuid(i) for i in ids):
        raise Refuse(f"bad {what} — want comma-separated uuids", 2)
    return ids


def load_questions_file(path: Path) -> list:
    """{questions:[…]} or a bare list of questions."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise Refuse(f"cannot read staged JSON {path} (contents withheld)", 2) from None
    qs = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(qs, list) or any(not isinstance(q, dict) or not q.get("question_id") for q in qs):
        raise Refuse("staged file must be {questions:[…]} or a bare list of questions with question_id", 2)
    return qs


def load_ids_file(path: Path) -> list[str]:
    """The publish set. There is no 'publish everything' default — the file must exist and hold a
    non-empty list of unique uuids (otherwise omitting question_ids would publish ALL)."""
    try:
        ids = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise Refuse(f"--ids-file {path} is not readable JSON", 3) from None
    if not isinstance(ids, list) or not ids or any(not _auth.valid_uuid(i) for i in ids):
        raise Refuse("--ids-file must be a non-empty JSON list of unique UUID question ids", 3)
    lowered = [i.lower() for i in ids]
    if len(set(lowered)) != len(lowered):
        raise Refuse("--ids-file must be a non-empty JSON list of unique UUID question ids", 3)
    return lowered


def load_ledger(path: Path) -> dict:
    if not path.exists():
        return {"sessions": {}}
    try:
        led = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise Refuse(f"cannot read ledger {path} (contents withheld)", 2) from None
    if not isinstance(led, dict) or not isinstance(led.get("sessions"), dict):
        raise Refuse(f"malformed ledger {path} — want {{\"sessions\": {{…}}}}", 2)
    return led


def save_ledger(path: Path, led: dict) -> None:
    """Atomic: temp file in the same directory, then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(_pub.dump(led))
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def ledger_entry(path: Path, sid: str) -> tuple[dict, dict]:
    led = load_ledger(path)
    return led, led["sessions"].setdefault(sid, {})


def upsert_meta(ent: dict, sess: dict) -> None:
    """Refresh the session-meta mirror from the row we just read. Never touches published/unpublished/flag_raised."""
    ent.update({"name": sess.get("name"), "scope": _pub.norm_scope(sess), "lesson_ids": sess.get("lesson_ids") or [], "status": sess.get("status")})
    ent.setdefault("created_at", sess.get("created_at"))


def union_ids(prev, new) -> list:
    out = list(prev or [])
    return out + [i for i in (new or []) if i not in set(out)]


def refuse_archived(sess: dict) -> None:
    if sess.get("status") == "archived":
        raise Refuse(ARCHIVED_MSG, 3)


def q3_after_logout(api: PlaygroundApi, *, sid: str | None, ledger: Path | None,
                    env_path: Path | None, log=print) -> int:
    """Guard-rail 6b — after a WRITE subcommand's global logout, prove the revocation on the
    merged project: queries.sql Q3 run through sql-proof's own resolver + runner (imported,
    never copied). Returns 0 when the proof is ok or cannot run here (PENDING); 5 when it ran
    and failed — psql error included, that is a NOT-ok not a skip. A write refused BEFORE any
    grant was obtained (no actor id) prints nothing — there is no session to revoke; a write
    refused AFTER a grant still gets its proof."""
    uid = api.user_id
    if not uid or not sqlp.UUID_RE.match(uid):
        return 0                                    # never completed a grant — nothing to prove
    url, src = sqlp.find_auth_url(None, env_path)
    if not url:
        log(f"q3: PENDING — no DB URL source; run tools/sql-proof.py q3 --actor {uid}")
        return 0
    print(f"{sqlp.PROG}: auth DB URL from {src}", file=sys.stderr)
    block = sqlp.slice_proof(sqlp.QUERIES.read_text(encoding="utf-8"), "Q3")
    try:
        row = sqlp.run_proof(sqlp.cr.pg_env_from_url(url), block, [("actor_id", uid)], "q3")
    except SystemExit as e:
        row = None                                      # run_proof printed the psql error above
        q3_why = "psql failed (its error is above)" if e.code == 1 \
            else f"the proof could not run (exit {e.code})"   # e.g. psql not on PATH
    ok = bool(row) and row.get("ok") is True
    counts = {k: v for k, v in (row or {}).items() if k != "ok"}
    if row is None:
        log(f"q3: NOT ok — {q3_why}")
    else:
        log(" ".join(f"{k}={sqlp.show(v)}" for k, v in row.items()))
        bad = sqlp.failing_q3(counts)
        log("q3: ok" if ok else f"q3: NOT ok — {', '.join(bad) if bad else 'ok=f'}")
    if ledger is not None and sid:
        try:                                        # a ledger write failure must not mask the
            led, ent = ledger_entry(ledger, sid)    # proof's exit code (warn, never raise)
            ent["q3"] = {"counts": counts, "ok": ok,
                         "checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "actor": uid}
            save_ledger(ledger, led)
        except Exception as e:
            log(f"q3: ledger write failed ({e}) — the proof result above stands")
    return 0 if ok else 5


def finish(api: PlaygroundApi, *, write: bool, sid: str | None = None, ledger: Path | None = None,
           env_path: Path | None = None, log=print) -> int:
    """Guard-rail 6: logout is the last act of every network subcommand. After a WRITE command the
    revocation is then PROVEN (Q3) or one PENDING line stands in for the old SQL hint; read-only
    commands print nothing past the logout line."""
    st = api.logout_global()
    log(f"logout?scope=global → HTTP {st} (a 204 is NOT the proof — agent-identities §3)")
    if not write:
        return 0
    return q3_after_logout(api, sid=sid, ledger=ledger, env_path=env_path, log=log)


# ----------------------------------------------------------------------------------------------- subcommands
def cmd_session_create(api: PlaygroundApi, name: str, scope_kv, lessons_csv: str, ledger_path: Path, log=print, sid_out: dict | None = None) -> int:
    scope = scope_from_kv(scope_kv)                       # local rules BEFORE the first call
    lessons = parse_uuid_list(lessons_csv, "--lessons")
    if not lessons:
        raise Refuse("--lessons must name at least one lesson uuid (the session's lesson intent)", 2)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
        raise Refuse("--name required (1–200 chars)", 2)
    body = {"name": name, "medium": scope["medium"], "lesson_ids": lessons}
    for k in ("grade", "exam", "subject"):                # send each scope key only when set
        if scope.get(k) is not None: body[k] = scope[k]
    api.fresh_token("session-create")
    sess = api.create_session(body)
    led, ent = ledger_entry(ledger_path, sess["id"]); upsert_meta(ent, sess); save_ledger(ledger_path, led)
    if sid_out is not None: sid_out["sid"] = sess["id"]   # main records the Q3 proof under the new sid
    log(sess["id"])                                       # the new session id, alone on its line
    return 0


def cmd_session_show(api: PlaygroundApi, sid: str, log=print) -> int:
    sid = need_uuid(sid, "session id")
    api.fresh_token("session-show")
    log(_pub.dump(api.get_session(sid)).rstrip("\n"))
    return 0


def cmd_session_list(api: PlaygroundApi, status, limit, log=print) -> int:
    api.fresh_token("session-list")
    log(_pub.dump(api.list_sessions({"status": status, "limit": limit})).rstrip("\n"))
    return 0


def cmd_session_archive(api: PlaygroundApi, sid: str, ledger_path: Path, log=print) -> int:
    sid = need_uuid(sid, "session id")
    api.fresh_token("session-archive")
    sess = api.patch_session(sid, {"status": "archived"})
    led, ent = ledger_entry(ledger_path, sid); upsert_meta(ent, sess); save_ledger(ledger_path, led)
    log(f"session archive: {sid} → archived (re-open via 'Unarchive' on the Admin /generate page — there is no reopen subcommand)")
    return 0


def cmd_doc_get(api: PlaygroundApi, sid: str, out_path: Path, log=print) -> int:
    sid = need_uuid(sid, "session id")
    api.fresh_token("doc-get")
    doc = api.get_doc(sid)
    out = {k: doc[k] for k in ("session", "questions", "stats")}   # ready is a transport detail, dropped
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_pub.dump(out), encoding="utf-8")
    log(f"doc get: {'ready' if doc['ready'] else 'NOT ready — empty doc'} · {len(out['questions'])} question(s) → {out_path}")
    return 0


def cmd_doc_put(api: PlaygroundApi, sid: str, staged_path: Path, ledger_path: Path, drop_missing: bool, allow_drop: bool, log=print) -> int:
    sid = need_uuid(sid, "session id")
    staged = load_questions_file(staged_path)
    api.fresh_token("doc-put")
    sess = api.get_session(sid)
    refuse_archived(sess)                                  # before ANY write
    unflagged = [q.get("question_number") for q in staged if (q.get("ingestion_metadata") or {}).get("needs_human_review") is not True]
    if unflagged:
        raise Refuse(f"REFUSED: {len(unflagged)} staged question(s) lack needs_human_review:true — Q{unflagged} (0014 guard-rail 4 / 0018 OD-2: staged questions are saved flagged)", 3)
    with_exam = [q.get("question_number") for q in staged if "exam" in q]
    if with_exam:
        raise Refuse(f"REFUSED: {len(with_exam)} staged question(s) carry an `exam` key — Q{with_exam} (0018 PD-6: scope lives on the session, never on a question)", 3)
    doc = api.get_doc(sid)
    merged, stats = _pub.merge_questions(doc.get("questions") or [], staged, drop_missing, allow_drop)
    log(f"doc put: merge {json.dumps(stats)}")
    res = api.put_doc(sid, merged)
    got = res.get("questions") or []
    log(f"doc put: server now holds {len(got)} question(s) · stats {json.dumps(res.get('stats'))}")
    if len(got) != len(merged):
        raise Refuse(f"PUT echoed {len(got)} questions, sent {len(merged)}", 5)
    lowered = sum(1 for q, s in zip(got, merged) if (s.get("ingestion_metadata") or {}).get("needs_human_review") is True and (q.get("ingestion_metadata") or {}).get("needs_human_review") is not True)
    if lowered:
        raise Refuse(f"server lowered the review flag on {lowered} question(s) — should be impossible (the save clamps raise-only)", 5)
    led, ent = ledger_entry(ledger_path, sid); upsert_meta(ent, sess); save_ledger(ledger_path, led)
    return 0


def cmd_validate(api: PlaygroundApi, sid: str, staged_path: Path, log=print) -> int:
    sid = need_uuid(sid, "session id")
    staged = load_questions_file(staged_path)
    api.fresh_token("validate")
    st, js = api.validate(sid, staged)
    if st != 200:
        raise Refuse(f"validate → {_auth.response_error(st, js)}", 5)
    checked_validate_report(js)
    for r in js["results"]:
        q = staged[r["index"]] if 0 <= r["index"] < len(staged) else {}
        log(f"Q{q.get('question_number')} ({q.get('question_id') or r.get('question_id')})")
        for e in r["errors"]: log(f"  error: {e}")
        for w in r["warnings"]: log(f"  warn: {w}")
    errors = sum(len(r["errors"]) for r in js["results"]); warnings = sum(len(r["warnings"]) for r in js["results"])
    log(f"validate: {'ok' if js['ok'] else 'NOT ok'} — {errors} error(s), {warnings} warning(s) (warnings never block)")
    return 0 if js["ok"] else 3


def writeback_after_publish(api: PlaygroundApi, sid: str, result: dict, log=print) -> None:
    """The OD-2 write-back — Admin's persistPublishOutcome. The playground publish response does NOT
    write the flag into the R2 staged doc: a follow-up PUT is the client's job. question_ids ∪ reflagged
    ∪ reraised get needs_human_review:true; question_ids get published/published_at."""
    doc = api.get_doc(sid)
    if doc.get("ready") is not True:
        raise Refuse("write-back GET returned ready:false — refusing to PUT an empty doc over a live publish", 5)
    qs = doc["questions"]
    flagged = {str(i).lower() for i in (result.get("question_ids") or []) + (result.get("reflagged") or []) + (result.get("reraised") or [])}
    published = {str(i).lower() for i in (result.get("question_ids") or [])}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for q in qs:
        qid = str(q.get("question_id")).lower()
        if qid in flagged:
            q["ingestion_metadata"] = {**(q.get("ingestion_metadata") or {}), "needs_human_review": True}
        if qid in published:
            q["published"] = True; q["published_at"] = now
    try:
        api.put_doc(sid, qs)
    except Refuse as e:
        log(f"  write-back PUT failed: {e}")
        raise Refuse("published but the staged doc was NOT updated — re-run `doc put` (the OD-2 flag lives only on the live row until the doc catches up)", 5) from None


def provenance_check(sql_runner, sid: str, order: list[str], log=print) -> bool:
    """Read-back 2b: the live rows by direct SELECT (never the API — T5). Every published id must be
    exactly one row, batch-owned, paperless, flagged, status published. A signed count >0 is a WARN
    (a human signature the publish preserved, OD-D), not a failure."""
    ids = [need_uuid(i, "question id") for i in order]          # re-validated before SQL interpolation
    sql = PROVENANCE_SQL.replace("__IDS__", ",".join(f"'{i}'" for i in ids))
    rows = sql_runner(sql)
    if rows is None:
        log("provenance: could not run (no DATABASE_URL / psql failure) — counts as a FAILURE")
        return False
    sid = str(sid).lower()
    by: dict[str, list] = {}
    for r in rows if isinstance(rows, list) else []:
        by.setdefault(str(r.get("question_id")).lower(), []).append(r)
    ok = True
    for i in ids:
        rs = by.get(i) or []
        if len(rs) != 1:
            log(f"  {i}: FAIL expected exactly 1 live row, got {len(rs)}"); ok = False; continue
        r = rs[0]
        probs = []
        if str(r.get("source_batch_id")).lower() != sid: probs.append(f"source_batch_id {r.get('source_batch_id')} != session {sid}")
        if r.get("source_paper_id") is not None: probs.append("source_paper_id is not NULL (playground rows are paperless)")
        if r.get("needs_human_review") is not True: probs.append("needs_human_review is not true")
        if r.get("status") != "published": probs.append(f"status {r.get('status')!r} != 'published'")
        signed = (r.get("signed_answers") or 0) + (r.get("signed_sub_answers") or 0)
        warn = " · WARN human signature present (OD-D preserved)" if signed else ""
        if probs:
            log(f"  {i}: FAIL {'; '.join(probs)}"); ok = False
        else:
            log(f"  {i}: ok — published, flagged, batch-owned{warn}")
    log(f"provenance: {len(ids)} id(s) · {'OK' if ok else 'FAILED'}")
    return ok


def run_publish(api: PlaygroundApi, sid: str, staged_path: Path, scope_kv, ids_path: Path, ledger_path: Path,
                accept: int | None, dry_run_only: bool, t77_runner, sql_runner, log=print) -> int:
    sid = need_uuid(sid, "session id")
    want = scope_from_kv(scope_kv)
    # ---- stage 1: session + archived + scope echo (guard-rail 1)
    api.fresh_token("publish:get"); sess = api.get_session(sid)
    refuse_archived(sess)
    pm = _pub.norm_scope(sess)
    if pm != want:
        raise Refuse(f"REFUSED: session scope {json.dumps(pm)} != --scope {json.dumps(want)} — fix --scope, or re-scope the session in the Admin /generate page", 3)
    log(f"scope: session = {json.dumps(pm)} · --scope = {json.dumps(want)}")
    # ---- stage 2: the ids file — non-empty, unique, uuids (no 'publish everything')
    want_ids = load_ids_file(ids_path)
    # ---- stage 3: the staged doc, then the publish set's guards
    doc = api.get_doc(sid)
    if doc.get("ready") is not True:
        raise Refuse("staged doc is not ready (ready:false) — `doc put` first", 3)
    server_q = {str(q["question_id"]).lower(): q for q in doc["questions"]}
    missing = [i for i in want_ids if i not in server_q]
    if missing:
        raise Refuse(f"REFUSED: {len(missing)} id(s) not in the session's staged doc: {missing[:3]}", 3)
    if any(type(server_q[i].get("question_number")) is not int for i in want_ids):
        raise Refuse("REFUSED: publish set requires integer question numbers (values withheld)", 3)
    staged_q = {str(q.get("question_id")).lower(): q for q in load_questions_file(staged_path)}
    differ = [server_q[i].get("question_number") for i in want_ids
              if i not in staged_q or _pub.num_norm(_pub.strip_server_hints(staged_q[i])) != _pub.num_norm(_pub.strip_server_hints(server_q[i]))]
    if differ:
        raise Refuse(f"REFUSED: staged file differs from the server doc on Q{differ} — publish reads the SERVER doc; run `doc put` first (T77)", 3)
    unflagged = [server_q[i].get("question_number") for i in want_ids if (server_q[i].get("ingestion_metadata") or {}).get("needs_human_review") is not True]
    if unflagged:
        raise Refuse(f"REFUSED: unflagged in publish set: Q{unflagged} (0014 guard-rail 4 / 0018 OD-2 — set ingestion_metadata.needs_human_review: true)", 3)
    order = sorted(want_ids, key=lambda i: (server_q[i].get("sort_order", 0), server_q[i].get("question_number")))
    log(f"publish set: {len(order)} question(s), all flagged, in order: {[server_q[i].get('question_number') for i in order]}")
    # ---- stage 4: server-side validate of the WHOLE server doc (session mode); errors on a CHOSEN question refuse
    server_list = doc["questions"]
    st, js = api.validate(sid, server_list)
    if st != 200:
        raise Refuse(f"validate → {_auth.response_error(st, js)}", 5)
    checked_validate_report(js)
    chosen = set(order); errs = []
    for r in js["results"]:
        rid = r.get("question_id")
        if rid is None and 0 <= r["index"] < len(server_list):
            rid = server_list[r["index"]].get("question_id")
        rid = str(rid).lower() if rid else None
        if rid not in chosen:
            continue
        for w in r["warnings"]: log(f"  validate warn Q{server_q[rid].get('question_number')}: {w}")
        errs += [f"Q{server_q[rid].get('question_number')} ({rid}): {e}" for e in r["errors"]]
    if errs:
        for e in errs: log(f"  validate error: {e}")
        raise Refuse(f"REFUSED: server-side validate reported {len(errs)} error(s) on chosen questions — fix the doc (`doc put`) before publish", 3)
    # ---- stage 5 (guard-rail 2 / T9): the ledger records the publish set BEFORE the first publish request
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = {"question_ids": order, "questions": [_pub.ids_of(server_q[i]) for i in order], "written_at": now}
    led, ent = ledger_entry(ledger_path, sid); upsert_meta(ent, sess)
    ent["published"] = _pub.merge_ids(ent.get("published"), rec)
    ent["published"].setdefault("updated_at", now); ent["published"].setdefault("last_publish_ids", order)
    save_ledger(ledger_path, led)
    log(f"ledger: {len(order)} question id(s) recorded in {ledger_path} BEFORE the first publish request (T9)")
    # ---- stage 6 (guard-rail 3): dry-run → signatures_at_risk must be accepted explicitly
    api.fresh_token("publish:dry-run"); st, js = api.publish(sid, order, dry_run=True)
    if st != 200:
        raise Refuse(f"dry-run → {_auth.response_error(st, js)}", 4)
    checked_dry_run(js)
    risk, unchanged = js["signatures_at_risk"], js["unchanged_count"]
    log(f"dry-run: signatures_at_risk = {risk} · unchanged_count = {unchanged} · questions previewed = {len(js['questions'])}")
    if accept is None:
        raise Refuse(f"REFUSED: pass --accept-signatures {risk} to proceed (the number must be typed, including 0)", 4)
    if accept != risk:
        raise Refuse(f"REFUSED: --accept-signatures {accept} != signatures_at_risk {risk}", 4)
    if dry_run_only:
        log("--dry-run: stopping after the dry-run; nothing published")
        return 0
    # ---- stage 7: one publish per question, in order; write the outcome back into the doc after EACH
    api.fresh_token("publish:loop"); done = 0
    for i in order:
        q = server_q[i]
        st, res = api.publish(sid, [i])
        if st == 0:
            log(f"  Q{q.get('question_number')} {i} → 000 (connection) — retrying once"); time.sleep(2); st, res = api.publish(sid, [i])
        if not (200 <= st < 300):
            log(f"  Q{q.get('question_number')} {i} → {_auth.response_error(st, res)}")
            raise Refuse(f"STOPPED after {done}/{len(order)}: publish of Q{q.get('question_number')} failed with HTTP {st}. The ledger {ledger_path} stands; fix and re-run.", 5)
        checked_publish_result(res)
        log(f"  Q{q.get('question_number')} {i} → {st} published={res['published']} sub_q={res['sub_questions']} answers={res['answers']}+{res['sub_answers']} reflagged={len(res['reflagged'])} unchanged={len(res['unchanged'])}")
        writeback_after_publish(api, sid, res, log)
        done += 1
    log(f"published {done}/{len(order)}")
    # ---- stage 8, read-back 1: the staged doc must now show every published id flagged + published
    api.fresh_token("publish:readback"); doc2 = api.get_doc(sid)
    after = {str(q["question_id"]).lower(): q for q in doc2.get("questions") or []}
    bad = [i for i in order if after.get(i, {}).get("published") is not True or (after.get(i, {}).get("ingestion_metadata") or {}).get("needs_human_review") is not True]
    if bad:
        raise Refuse(f"MISMATCH doc: {[server_q[i].get('question_number') for i in bad]} lack published:true or the flag in the staged doc after write-back", 1)
    log(f"read-back 1: staged doc confirms {len(order)} published + flagged")
    # ---- stage 9, read-back 2: the LIVE ROWS, by direct SELECT — never the API (Hyperdrive ~75 s stale, T5)
    rc = t77_runner(staged_path, order)
    log(f"t77: exit {rc}" + ("" if rc == 0 else " — MISMATCH: the run is FAILED until staged and live agree (T77)"))
    prov = provenance_check(sql_runner, sid, order, log)
    return 0 if rc == 0 and prov else 1


def cmd_unpublish(api: PlaygroundApi, sid: str, ids_path: Path, ledger_path: Path, log=print) -> int:
    sid = need_uuid(sid, "session id")
    ids = load_ids_file(ids_path)
    api.fresh_token("unpublish")
    sess = api.get_session(sid); refuse_archived(sess)
    st, js = api.unpublish(sid, ids)
    if st != 200:
        raise Refuse(f"unpublish → {_auth.response_error(st, js)}", 5)
    checked_unpublish(js)
    led, ent = ledger_entry(ledger_path, sid); upsert_meta(ent, sess)
    ent["unpublished"] = union_ids(ent.get("unpublished"), js["question_ids"]); save_ledger(ledger_path, led)
    log(f"unpublish: {js['unpublished']} question(s) set back to draft")
    if js["not_in_session"]:
        log(f"not_in_session: {js['not_in_session']} — requested ids with no live row in this session (never silently skipped)")
        return 3
    doc = api.get_doc(sid); after = {q["question_id"]: q for q in doc.get("questions") or []}
    still = [i for i in js["question_ids"] if after.get(i, {}).get("published") is True]
    if still:
        log(f"WARN: {len(still)} moved id(s) still show published:true in the staged doc — the mirror lagged; re-run `doc put`")
    return 0


def cmd_flag_review(api: PlaygroundApi, sid: str, ids_path: Path, ledger_path: Path, log=print) -> int:
    sid = need_uuid(sid, "session id")
    ids = load_ids_file(ids_path)
    api.fresh_token("flag-review")
    sess = api.get_session(sid); refuse_archived(sess)
    st, js = api.flag_review(sid, ids)
    if st != 200:
        raise Refuse(f"flag-review → {_auth.response_error(st, js)}", 5)
    checked_flag_response(js)
    led, ent = ledger_entry(ledger_path, sid); upsert_meta(ent, sess)
    ent["flag_raised"] = union_ids(ent.get("flag_raised"), js["question_ids"]); save_ledger(ledger_path, led)
    log(f"flag-review: flagged={js['flagged']} · no_live_row={js['no_live_row']} · staged_doc_updated={js.get('staged_doc_updated')}")
    if js.get("staged_doc_updated") is False:
        log("flag applied, staged doc stale — re-PUT")
        return 1
    return 0


def cmd_lessons(api: PlaygroundApi, grade, exam, subject, log=print) -> int:
    if grade is not None and exam:
        raise Refuse("--grade and --exam are mutually exclusive (0006)", 2)
    api.fresh_token("lessons")
    js = api.list_lessons()
    data = js.get("data") if isinstance(js, dict) else None
    if not isinstance(data, list):
        raise Refuse("malformed lessons response (body withheld)", 5)
    for it in data:
        if not isinstance(it, dict) or not _auth.valid_uuid(it.get("lesson_id")) or not isinstance(it.get("name"), str) or type(it.get("sort_order")) is not int:
            raise Refuse("malformed lessons response (body withheld)", 5)
    rows = [it for it in data if (grade is None or it.get("grade") == grade) and (exam is None or it.get("exam") == exam) and (subject is None or it.get("subject") == subject)]
    rows.sort(key=lambda it: (it["sort_order"], it["name"]))
    for it in rows:
        log(f"{it['lesson_id']}  {it['sort_order']}  {it['name']}  |  {it.get('name_sinhala')}")
    log(f"lessons: {len(rows)} of {len(data)}")
    return 0


def cmd_questions_list(api: PlaygroundApi, params: dict, fetch_all: bool, out_path: Path | None, log=print) -> int:
    if params.get("grade") is not None and params.get("exam"):
        raise Refuse("--grade and --exam are mutually exclusive (0006)", 2)
    if params.get("batch_id"):
        params["batch_id"] = need_uuid(params["batch_id"], "--batch-id")
    if params.get("lesson_id"):
        params["lesson_id"] = ",".join(parse_uuid_list(params["lesson_id"], "--lesson-id"))
    api.fresh_token("questions-list")
    got: list = []; cursor = None; pages = 0
    while True:
        p = dict(params)
        if cursor: p["cursor"] = cursor
        js = api.list_questions(p)
        data, nxt = js.get("data"), js.get("next_cursor")
        if not isinstance(data, list) or (nxt is not None and not isinstance(nxt, str)):
            raise Refuse("malformed questions list response (body withheld)", 5)
        for it in data: checked_summary(it)
        got += data; pages += 1
        if not fetch_all or not nxt:
            break
        if pages >= 20:
            log("WARN: stopped at the 20-page cap — more pages remain (narrow the filters)")
            break
        cursor = nxt
    for it in got:
        src = "paper" if it.get("source_paper_id") else ("batch" if it.get("source_batch_id") else "none")
        flag = "flagged" if it.get("needs_human_review") is True else "clear"
        log(f"{it['question_id']}  {it.get('status')}  {flag}  {src}  Q{it.get('question_number')}  {(it.get('stem_excerpt') or '')[:80]}")
    log(f"questions: {len(got)} row(s) · {pages} page(s)")
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_pub.dump(got), encoding="utf-8")
        log(f"→ {out_path}")
    return 0


def cmd_question_show(api: PlaygroundApi, qid: str, out_path: Path | None, log=print) -> int:
    qid = need_uuid(qid, "question id")
    api.fresh_token("question-show")
    js = api.get_question(qid)
    if not isinstance(js, dict) or not isinstance(js.get("question"), dict) or any(not isinstance(js.get(k), list) for k in ("sub_questions", "sub_answers", "answers")):
        raise Refuse("malformed question response (body withheld)", 5)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_pub.dump(js), encoding="utf-8")
        log(f"→ {out_path}")
    else:
        log(_pub.dump(js).rstrip("\n"))
    return 0


# ----------------------------------------------------------------------------------------------- runners (injectable for tests)
def t77_runner(env_path: Path | None, log=print):
    return _pub.t77_subprocess(env_path, log=log)


def provenance_sql_runner(env_path: Path | None, log=print):
    """sql -> list[dict] | None (None = could not run; counts as a failure). Loads psql_json out of
    t77-staged-vs-published.py; DATABASE_URL from _pub.load_db_url (env first, then Vibhaga-DB/.env)."""
    def run(sql: str):
        url = _pub.load_db_url(env_path)
        if not url:
            log("provenance: DATABASE_URL not set and no Vibhaga-DB/.env found — could NOT run (counts as a failure)")
            return None
        try:
            spec = importlib.util.spec_from_file_location("t77_staged_vs_published", HERE / "t77-staged-vs-published.py")
            t77 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t77)
        except (OSError, ValueError, ImportError):
            log("provenance: cannot load t77-staged-vs-published.py — counts as a failure")
            return None
        old = os.environ.get("DATABASE_URL"); os.environ["DATABASE_URL"] = url
        try:
            return t77.psql_json(sql)
        except Exception as e:  # noqa: BLE001 — psql non-zero / bad JSON: a failed proof, not a crash
            log(f"provenance: psql failed ({type(e).__name__}) — counts as a failure")
            return None
        finally:
            if old is None: os.environ.pop("DATABASE_URL", None)
            else: os.environ["DATABASE_URL"] = old
    return run


# ----------------------------------------------------------------------------------------------- self-test (no network)
def self_test() -> int:
    """Run the committed unittest module — no network, fakes only."""
    import unittest
    path = HERE / "test_playground_publish.py"
    if not path.exists():
        path = HERE.parent / "tests" / "test_playground_publish.py"   # plugin layout: tests/ beside tools/
    if not path.exists():
        print("test_playground_publish.py not found beside the tool or in ../tests"); return 2
    spec = importlib.util.spec_from_file_location("test_playground_publish", path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    res = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(mod))
    return 0 if res.wasSuccessful() else 1


# ----------------------------------------------------------------------------------------------- FakePlayground (offline tests)
class FakePlayground:
    """In-memory playground plane: password grant, logout, session GET/POST/PATCH (409 batch_archived on
    writes to archived sessions), the staged-doc GET/PUT with the raise-never-lower flag clamp, validate,
    publish (dry-run returns `risk`; a real publish returns PublishResult but does NOT touch the doc —
    the worst case, matching live), unpublish, flag-review, the corpus list and the lessons table.
    Records every (method, path) call. Knobs: fail_publish_at (HTTP fail_status on the Nth real publish),
    flake_first (first real publish → status 0), validate_errors {question_id: [errors]},
    put_drops_published (the PUT ignores published/published_at — breaks read-back 1),
    flag_stale_doc (flag-review returns staged_doc_updated:false), mirror_publish_flag (a nicer-than-live
    server that DOES mirror the flag), page_size (corpus cursor pages)."""

    ACTOR = "11111111-2222-4333-8444-555555555555"
    STAMP = "2026-09-27T00:00:00Z"

    def __init__(self, sessions, docs, risk=0, fail_publish_at=None, flake_first=False, validate_errors=None,
                 validate_warnings=None, archived=(), mirror_publish_flag=False, put_drops_published=False,
                 flag_stale_doc=False, lessons=None, corpus=None, page_size=2, question_detail=None, fail_status=500):
        self.sessions = json.loads(json.dumps(sessions))
        for sid in archived:
            if sid in self.sessions: self.sessions[sid]["status"] = "archived"
        self.docs = {k: json.loads(json.dumps(v)) for k, v in docs.items()}
        self.risk = risk; self.fail_at = fail_publish_at; self.fail_status = fail_status; self.flake = flake_first
        self.validate_errors = validate_errors or {}; self.validate_warnings = validate_warnings or {}
        self.mirror = mirror_publish_flag; self.drop_pub = put_drops_published; self.flag_stale = flag_stale_doc
        self.lessons = lessons or []; self.corpus = corpus or []; self.page_size = page_size; self.detail = question_detail
        self.calls: list[tuple[str, str]] = []; self.publishes: list[list[str]] = []; self.put_bodies: list[list] = []
        self.on_publish = None; self.grants = 0; self.logouts = 0; self.created = 0

    def _doc(self, sid):
        qs = self.docs.get(sid)
        return {"ready": qs is not None, "session": self.sessions[sid], "questions": qs or [],
                "stats": {"questions": len(qs or []), "flagged": sum(1 for q in (qs or []) if (q.get("ingestion_metadata") or {}).get("needs_human_review") is True)}}

    def __call__(self, method, url, headers, body):
        u = urllib.parse.urlparse(url); path = u.path
        self.calls.append((method, path + ("?" + u.query if u.query else "")))
        js = json.loads(body) if body else {}
        if path.startswith("/auth/v1/token"):
            self.grants += 1
            if js.get("password") != "pw": return 400, b'{"error":"invalid_grant"}'
            return 200, json.dumps({"access_token": f"tok{self.grants}", "user": {"id": self.ACTOR}}).encode()
        if path.startswith("/auth/v1/logout"):
            self.logouts += 1; return 204, b""
        if not headers.get("authorization", "").startswith("Bearer tok"):
            return 401, b'{"error":"unauthorized"}'
        if path == "/v1/admin/lessons" and method == "GET":
            return 200, json.dumps({"data": self.lessons}).encode()
        if path == "/v1/admin/playground/questions" and method == "GET":
            qs = urllib.parse.parse_qs(u.query)
            start = int((qs.get("cursor") or ["0"])[0]); end = start + self.page_size
            return 200, json.dumps({"data": self.corpus[start:end], "next_cursor": str(end) if end < len(self.corpus) else None}).encode()
        m = re.fullmatch(r"/v1/admin/playground/questions/([0-9a-fA-F-]+)", path)
        if m and method == "GET":
            d = self.detail if self.detail is not None else {"question": {"question_id": m.group(1)}, "sub_questions": [], "sub_answers": [], "answers": []}
            return 200, json.dumps(d).encode()
        if path == "/v1/admin/playground/validate" and method == "POST":
            results = [{"index": i, "question_id": q.get("question_id"),
                        "errors": list(self.validate_errors.get(q.get("question_id"), [])),
                        "warnings": list(self.validate_warnings.get(q.get("question_id"), []))}
                       for i, q in enumerate(js.get("questions") or [])]
            return 200, json.dumps({"ok": not any(r["errors"] for r in results), "results": results}).encode()
        if path == "/v1/admin/playground/sessions":
            if method == "POST":
                if js.get("grade") is not None and js.get("exam") is not None: return 400, b'{"error":"invalid_scope"}'
                if not js.get("medium") or not js.get("name"): return 400, b'{"error":"invalid_request"}'
                self.created += 1
                sid = f"00000000-0000-4000-8000-{self.created:012d}"
                row = {"id": sid, "name": js["name"], "grade": js.get("grade"), "exam": js.get("exam"), "subject": js.get("subject"),
                       "medium": js["medium"], "lesson_ids": js.get("lesson_ids") or [], "r2_key": f"playground/{sid}/questions.json",
                       "status": "active", "question_count": 0, "created_by_admin_id": self.ACTOR, "created_at": self.STAMP, "updated_at": self.STAMP}
                self.sessions[sid] = row
                return 201, json.dumps(row).encode()
            if method == "GET":
                qs = urllib.parse.parse_qs(u.query)
                status = (qs.get("status") or ["active"])[0]; limit = int((qs.get("limit") or ["100"])[0])
                rows = [s for s in self.sessions.values() if s["status"] == status][::-1]  # newest first
                return 200, json.dumps({"data": rows[:limit], "next_cursor": None}).encode()
        m = re.fullmatch(r"/v1/admin/playground/sessions/([0-9a-fA-F-]{36})(/.*)?", path)
        if not m:
            return 404, b'{"error":"not_found"}'
        sid, tail = m.group(1).lower(), m.group(2) or ""          # Postgres uuid compare is case-insensitive
        sess = self.sessions.get(sid)
        if not sess:
            return 404, b'{"error":"not_found"}'
        if tail == "" and method == "GET":
            return 200, json.dumps(sess).encode()
        if tail == "" and method == "PATCH":
            if sess["status"] == "archived" and js != {"status": "active"}:
                return 409, b'{"error":"batch_archived"}'
            sess.update(js)
            return 200, json.dumps(sess).encode()
        if sess["status"] == "archived" and method in ("PUT", "POST"):
            return 409, b'{"error":"batch_archived"}'
        if tail == "/questions":
            if method == "GET":
                return 200, json.dumps(self._doc(sid)).encode()
            if method == "PUT":
                incoming = [json.loads(json.dumps(q)) for q in (js.get("questions") or [])]
                prev_flag = {q["question_id"] for q in self.docs.get(sid, []) if (q.get("ingestion_metadata") or {}).get("needs_human_review") is True}
                for q in incoming:
                    if self.drop_pub:
                        q.pop("published", None); q.pop("published_at", None)
                    if q.get("question_id") in prev_flag:
                        q["ingestion_metadata"] = {**(q.get("ingestion_metadata") or {}), "needs_human_review": True}
                self.docs[sid] = incoming; self.put_bodies.append(incoming); sess["question_count"] = len(incoming)
                return 200, json.dumps({"ready": True, **self._doc(sid)}).encode()
        if tail == "/publish" and method == "POST":
            ids = list(js.get("question_ids") or [])
            if js.get("dry_run"):
                return 200, json.dumps({"dry_run": True, "signatures_at_risk": self.risk, "unchanged_count": 0,
                                        "questions": [{"question_id": i, "first_publish": True, "unchanged": False, "changed_field": None,
                                                       "signed_count": self.risk, "would_destroy_signatures": self.risk > 0} for i in ids]}).encode()
            if self.on_publish: self.on_publish(len(self.publishes))
            if self.flake and not self.publishes:
                self.flake = False; return 0, b"connection reset"
            self.publishes.append(ids)
            if self.fail_at is not None and len(self.publishes) == self.fail_at:
                return self.fail_status, b'{"error":"boom"}'
            if self.mirror:
                for q in self.docs.get(sid, []):
                    if q.get("question_id") in ids:
                        q["published"] = True; q["published_at"] = self.STAMP
                        q["ingestion_metadata"] = {**(q.get("ingestion_metadata") or {}), "needs_human_review": True}
            return 200, json.dumps({"published": len(ids), "sub_questions": 0, "sub_answers": 0, "answers": len(ids),
                                    "question_ids": ids, "reflagged": [], "unchanged": [], "reraised": [],
                                    "signatures_destroyed": [], "signatures_preserved": []}).encode()
        if tail == "/unpublish" and method == "POST":
            have = {q["question_id"] for q in self.docs.get(sid, [])}
            ids = list(js.get("question_ids") or [])
            moved = [i for i in ids if i in have]; outside = [i for i in ids if i not in have]
            for q in self.docs.get(sid, []):
                if q["question_id"] in moved:
                    q["published"] = False; q["published_at"] = None
            return 200, json.dumps({"unpublished": len(moved), "question_ids": moved, "not_in_session": outside}).encode()
        if tail == "/flag-review" and method == "POST":
            have = {q["question_id"] for q in self.docs.get(sid, [])}
            ids = list(js.get("question_ids") or [])
            inside = [i for i in ids if i in have]; outside = [i for i in ids if i not in have]
            if not self.flag_stale:
                for q in self.docs.get(sid, []):
                    if q["question_id"] in inside:
                        q["ingestion_metadata"] = {**(q.get("ingestion_metadata") or {}), "needs_human_review": True}
            return 200, json.dumps({"flagged": len(inside), "question_ids": inside, "no_live_row": outside,
                                    "staged_doc_updated": not self.flag_stale}).encode()
        return 404, b'{"error":"not_found"}'


# ----------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--env", help="path to Vibhaga-Admin/.env.local"); common.add_argument("--cred-prefix", default="VIBHAGA_ADMIN")
    sub = ap.add_subparsers(dest="cmd")
    sess = sub.add_parser("session"); ssub = sess.add_subparsers(dest="sub")
    c = ssub.add_parser("create", parents=[common]); c.add_argument("--name", required=True); c.add_argument("--scope", required=True); c.add_argument("--lessons", required=True); c.add_argument("--ledger", required=True)
    sh = ssub.add_parser("show", parents=[common]); sh.add_argument("sid")
    li = ssub.add_parser("list", parents=[common]); li.add_argument("--status", choices=["active", "archived"]); li.add_argument("--limit", type=int)
    ar = ssub.add_parser("archive", parents=[common]); ar.add_argument("sid"); ar.add_argument("--ledger", required=True)
    doc = sub.add_parser("doc"); dsub = doc.add_subparsers(dest="sub")
    dg = dsub.add_parser("get", parents=[common]); dg.add_argument("sid"); dg.add_argument("--out", required=True)
    dp = dsub.add_parser("put", parents=[common]); dp.add_argument("sid"); dp.add_argument("--staged", required=True); dp.add_argument("--ledger", required=True); dp.add_argument("--drop-missing", action="store_true"); dp.add_argument("--allow-drop", action="store_true")
    v = sub.add_parser("validate", parents=[common]); v.add_argument("sid"); v.add_argument("--staged", required=True)
    pb = sub.add_parser("publish", parents=[common]); pb.add_argument("sid"); pb.add_argument("--staged", required=True); pb.add_argument("--scope", required=True)
    pb.add_argument("--ids-file", required=True); pb.add_argument("--ledger", required=True); pb.add_argument("--accept-signatures", type=int); pb.add_argument("--dry-run", action="store_true")
    un = sub.add_parser("unpublish", parents=[common]); un.add_argument("sid"); un.add_argument("--ids-file", required=True); un.add_argument("--ledger", required=True)
    fr = sub.add_parser("flag-review", parents=[common]); fr.add_argument("sid"); fr.add_argument("--ids-file", required=True); fr.add_argument("--ledger", required=True)
    for verb in ("clear-review", "unflag-review"):
        sub.add_parser(verb).add_argument("rest", nargs=argparse.REMAINDER)
    le = sub.add_parser("lessons", parents=[common]); le.add_argument("--grade", type=int); le.add_argument("--exam"); le.add_argument("--subject")
    q = sub.add_parser("questions"); qsub = q.add_subparsers(dest="sub")
    ql = qsub.add_parser("list", parents=[common]); ql.add_argument("--lesson-id"); ql.add_argument("--status", choices=["draft", "published"])
    ql.add_argument("--needs-human-review", choices=["true", "false"]); ql.add_argument("--grade", type=int); ql.add_argument("--exam")
    ql.add_argument("--subject"); ql.add_argument("--medium", choices=MEDIUMS); ql.add_argument("--batch-id"); ql.add_argument("--q"); ql.add_argument("--limit", type=int)
    ql.add_argument("--all", action="store_true", dest="fetch_all"); ql.add_argument("--out")
    qs = qsub.add_parser("show", parents=[common]); qs.add_argument("question_id"); qs.add_argument("--out")
    a = ap.parse_args(argv)
    if a.self_test: return self_test()
    if not a.cmd: ap.print_help(); return 2
    try:
        if a.cmd in ("clear-review", "unflag-review"):
            raise Refuse("refused: lowering a review flag is a human act (decision 0014 PD-1 guard-rail 4 / PD-2, 0009) — use 'Go live' / 'Remove flag' on the Admin /generate page", 3)
        if a.cmd in ("session", "doc", "questions") and not getattr(a, "sub", None):
            return 2
        # every id is validated AND lowered BEFORE the env file is read or any network call
        for attr, what in (("sid", "session id"), ("question_id", "question id"), ("batch_id", "--batch-id")):
            v = getattr(a, attr, None)
            if v is not None: setattr(a, attr, need_uuid(v, what))
        if getattr(a, "lesson_id", None): a.lesson_id = ",".join(parse_uuid_list(a.lesson_id, "--lesson-id"))
        env_path = Path(a.env) if getattr(a, "env", None) else (Path(os.environ["VIBHAGA_ADMIN_ENV"]) if os.environ.get("VIBHAGA_ADMIN_ENV") else None) \
            or _pub.find_up("Vibhaga-Admin/.env.local", HERE) or _pub.find_up("Vibhaga-Admin/.env.local", Path.cwd())
        if not env_path or not env_path.exists():
            raise Refuse(f"admin env file not found: {env_path or 'Vibhaga-Admin/.env.local (walked up from ' + str(HERE) + ')'} (pass --env or VIBHAGA_ADMIN_ENV)", 2)
        api = PlaygroundApi(_pub.read_env(env_path), cred_prefix=getattr(a, "cred_prefix", "VIBHAGA_ADMIN"))
        # WRITE subcommands — the ones whose logout leaves a revocation to prove (B1/B2: reads
        # print no hint at all; writes get the auto-Q3 or the PENDING line).
        write = (a.cmd == "session" and a.sub in ("create", "archive")) or \
                (a.cmd == "doc" and a.sub == "put") or \
                a.cmd in ("publish", "unpublish", "flag-review")
        created: dict = {}

        def go() -> int:
            if a.cmd == "session":
                if a.sub == "create": return cmd_session_create(api, a.name, a.scope, a.lessons, Path(a.ledger), sid_out=created)
                if a.sub == "show": return cmd_session_show(api, a.sid)
                if a.sub == "list": return cmd_session_list(api, a.status, a.limit)
                if a.sub == "archive": return cmd_session_archive(api, a.sid, Path(a.ledger))
            if a.cmd == "doc":
                if a.sub == "get": return cmd_doc_get(api, a.sid, Path(a.out))
                if a.sub == "put": return cmd_doc_put(api, a.sid, Path(a.staged), Path(a.ledger), a.drop_missing, a.allow_drop)
            if a.cmd == "validate": return cmd_validate(api, a.sid, Path(a.staged))
            if a.cmd == "publish":
                return run_publish(api, a.sid, Path(a.staged), a.scope, Path(a.ids_file), Path(a.ledger), a.accept_signatures, a.dry_run, t77_runner(env_path), provenance_sql_runner(env_path))
            if a.cmd == "unpublish": return cmd_unpublish(api, a.sid, Path(a.ids_file), Path(a.ledger))
            if a.cmd == "flag-review": return cmd_flag_review(api, a.sid, Path(a.ids_file), Path(a.ledger))
            if a.cmd == "lessons": return cmd_lessons(api, a.grade, a.exam, a.subject)
            if a.cmd == "questions":
                if a.sub == "list":
                    params = {k: v for k, v in (("lesson_id", a.lesson_id), ("status", a.status), ("needs_human_review", a.needs_human_review),
                                                ("grade", a.grade), ("exam", a.exam), ("subject", a.subject), ("medium", a.medium),
                                                ("batch_id", a.batch_id), ("q", a.q), ("limit", a.limit)) if v is not None}
                    return cmd_questions_list(api, params, a.fetch_all, Path(a.out) if a.out else None)
                if a.sub == "show": return cmd_question_show(api, a.question_id, Path(a.out) if a.out else None)
            return 2
        rc = None
        try:
            rc = go()
        finally:
            sid = created.get("sid") or getattr(a, "sid", None)
            frc = finish(api, write=write, sid=sid,
                         ledger=Path(a.ledger) if getattr(a, "ledger", None) else None,
                         env_path=env_path)
            if rc == 0 and frc:
                rc = frc                     # a NOT-ok Q3 after a successful write → exit 5
        return 2 if rc is None else rc
    except Refuse as e:
        print(e); return e.code
    return 2


if __name__ == "__main__":
    sys.exit(main())
