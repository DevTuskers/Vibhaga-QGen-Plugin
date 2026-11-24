#!/usr/bin/env python3
"""note-proof.py — prove a lesson-short-notes upload is a hidden DRAFT, as ONE command.

    note-proof.py --lesson <uuid> WORK [--student-env FILE] [--out FILE.json]

WORK holds the reviewed `en.md`, `si.md` and `diagrams.json`. In order, failing closed:

  1. admin sign-in (`_admin_auth.Admin`, Admin's .env.local or VIBHAGA_ADMIN_ENV) and
     `GET /v1/admin/lessons/{lesson}/note`: both bodies byte-equal to WORK, diagrams JSON-equal,
     `status` draft, `verified_by` / `verified_at` null;
  2. queries.sql Q5 (read-only psql, content DB): the row is draft at that version with no
     verifier, and an audit event by THIS admin exists for that version;
  3. a STUDENT password grant (DEV_LOGIN_EMAIL / DEV_LOGIN_PASSWORD from --student-env, default
     VIBHAGA_WEB env or <plugin>/../Vibhaga-Web/.env.local) whose JWT is not an admin and not the admin's uid, then
     `GET /v1/lessons/{lesson}/note` must be HTTP 404 with error code `not_found`;
  4. global sign-out of both identities, then queries.sql Q3 for the admin (revocation).

Prints one `key=value` line per proof and `note-proof: ok` or `note-proof: NOT ok — …`; `--out`
writes the same as JSON. Never prints a credential, a token, an email or a note body.
Exit: 0 ok · 1 a proof failed · 2 usage · 3 a DB URL or student identity could not be found.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _admin_auth as _auth  # noqa: E402


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = _load("sql_proof", "sql-proof.py")
cr = sp.cr
PROG = "note-proof"
STUDENT_KEYS = ("NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY")


def die(msg: str, code: int = 2):
    print(f"{PROG}: {msg}", file=sys.stderr)
    raise SystemExit(code)


def jwt_claims(token: str) -> dict:
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except (IndexError, ValueError):
        return {}


def compare_stored(note: dict, en: str, si: str, diagrams: list) -> list[str]:
    bad = []
    if note.get("content_english") != en:
        bad.append("content_english differs from en.md")
    if note.get("content_sinhala") != si:
        bad.append("content_sinhala differs from si.md")
    if json.dumps(note.get("diagrams"), sort_keys=True) != json.dumps(diagrams, sort_keys=True):
        bad.append("diagrams differ from diagrams.json")
    if note.get("status") != "draft":
        bad.append(f"status={note.get('status')!r}")
    for k in ("verified_by", "verified_at"):
        if note.get(k) is not None:
            bad.append(f"{k} is set")
    return bad


def student_env(path: Path, admin_env: dict) -> dict | None:
    if not path.is_file():
        return None
    web = _auth.read_env_all(path)
    if not web.get("DEV_LOGIN_EMAIL") or not web.get("DEV_LOGIN_PASSWORD"):
        return None
    env = {k: v for k, v in admin_env.items() if k not in ("VIBHAGA_ADMIN_EMAIL", "VIBHAGA_ADMIN_PASSWORD")}
    env.update(VIBHAGA_ADMIN_EMAIL=web["DEV_LOGIN_EMAIL"], VIBHAGA_ADMIN_PASSWORD=web["DEV_LOGIN_PASSWORD"])
    # The student must hit the student API (Admin's API base serves only /v1/admin/** and 404s "No route").
    env.update({k: web[k] for k in STUDENT_KEYS if web.get(k)})
    return env


def body_404_transport(method, url, headers, body):
    """The shared transport withholds every error body; the student route's 404 envelope
    (`{"error": {"code", "message", "request_id"}}`) is the proof, so read it — 404 only, 4 KB cap."""
    import urllib.error
    import urllib.request
    context = _auth.checked_tls_context()
    req = urllib.request.Request(url, data=body, method=method, headers={**headers, "User-Agent": _auth.USER_AGENT})
    try:
        with urllib.request.build_opener(_auth.NoRedirect(), urllib.request.HTTPSHandler(context=context)).open(req, timeout=60) as r:
            return r.status, {}, b""
    except urllib.error.HTTPError as e:
        with e:
            return e.code, {}, (e.read(4096) if e.code == 404 else b"")


def error_envelope(st: int, raw: bytes) -> dict:
    try:
        err = json.loads(raw).get("error") if raw else None
    except (ValueError, AttributeError):
        err = None
    return err if isinstance(err, dict) else {}


def student_check(stu: "_auth.Admin", lesson: str, admin_uid: str | None, get=body_404_transport) -> tuple[list[str], dict]:
    token = stu.token()
    claims = jwt_claims(token)
    role = (claims.get("app_metadata") or {}).get("vibhaga_role")
    bad = []
    if role == "admin" or not stu.user_id or stu.user_id == admin_uid:
        bad.append("the student identity is an admin or the same account — not withholding evidence")
    url = f"{stu.api}/v1/lessons/{lesson}/note"
    st, _, raw = get("GET", url, {"Authorization": f"Bearer {token}", **stu.cf}, None)
    err = error_envelope(st, raw)
    if st != 404 or err.get("code") != "not_found" or str(err.get("message", "")).startswith("No route"):
        bad.append(f"student GET returned {st} {err.get('code')!r} — need 404 not_found")
    return bad, {"student_status": st, "student_code": err.get("code"), "student_message": err.get("message"),
                 "student_request_id": err.get("request_id")}


def main(argv: list[str] | None = None, transport=None, student_get=body_404_transport) -> int:
    ap = argparse.ArgumentParser(prog="note-proof.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("work", type=Path)
    ap.add_argument("--lesson", required=True)
    ap.add_argument("--student-env", type=Path)
    ap.add_argument("--db-env")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if not cr.UUID_RE.fullmatch(a.lesson):
        die("--lesson must be a uuid")
    work = a.work.resolve()
    en = (work / "en.md").read_text(encoding="utf-8")
    si = (work / "si.md").read_text(encoding="utf-8")
    diagrams = json.loads((work / "diagrams.json").read_text(encoding="utf-8"))
    try:
        admin_path = (Path(os.environ["VIBHAGA_ADMIN_ENV"]) if os.environ.get("VIBHAGA_ADMIN_ENV")
                      else Path(os.environ["VIBHAGA_ADMIN"]) / ".env.local" if os.environ.get("VIBHAGA_ADMIN")
                      else _auth.ENV_PATH)
        admin_env = _auth.read_env(admin_path)
    except SystemExit as e:
        die(f"admin credentials unavailable ({e.code})", 3)
    stu_path = a.student_env or Path(os.environ.get("VIBHAGA_WEB") or HERE.parent.parent / "Vibhaga-Web") / ".env.local"
    stu_env = student_env(stu_path, admin_env)
    if stu_env is None:
        die(f"no DEV_LOGIN_EMAIL/DEV_LOGIN_PASSWORD student identity in {stu_path}", 3)
    url = cr.resolve_db_url(a.db_env)
    pg = cr.pg_env_from_url(url)
    kw = {} if transport is None else {"transport": transport}
    adm, stu = _auth.Admin(env=admin_env, **kw), _auth.Admin(env=stu_env, **kw)
    result, bad = {"lesson_id": a.lesson}, []
    try:
        adm.token()
        st, note = adm.call("GET", f"/v1/admin/lessons/{a.lesson}/note")
        if st != 200 or not isinstance(note, dict):
            bad.append(f"admin GET returned {st}")
            note = {}
        note = note.get("data", note) if isinstance(note.get("data"), dict) else note
        bad += compare_stored(note, en, si, diagrams)
        result.update(note_id=note.get("note_id"), version=note.get("version"), status=note.get("status"))
        if note.get("note_id") and isinstance(note.get("version"), int) and adm.user_id:
            q5 = sp.run_proof(pg, sp.slice_proof(sp.QUERIES.read_text(), "Q5"),
                              [("lesson_id", a.lesson), ("note_id", note["note_id"]),
                               ("version", str(note["version"])), ("actor_id", adm.user_id)], "Q5")
            result["q5"] = q5
            if q5.get("ok") is not True:
                bad.append("Q5 not ok")
        else:
            bad.append("Q5 skipped — no note_id/version/admin uid")
        sbad, sres = student_check(stu, a.lesson, adm.user_id, student_get)
        bad += sbad
        result.update(sres)
    finally:
        for who in (stu, adm):
            if who.access:
                who.logout()
    if adm.user_id:
        q3 = sp.run_proof(pg, sp.slice_proof(sp.QUERIES.read_text(), "Q3"), [("actor_id", adm.user_id)], "Q3")
        result["q3"] = q3
        if q3.get("ok") is not True:
            bad += [f"Q3 {b}" for b in sp.failing_q3(q3)] or ["Q3 not ok"]
    result["actor_id"] = adm.user_id
    result["ok"] = not bad
    result["checked_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for k, v in result.items():
        print(f"{k}={json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v}")
    print("note-proof: ok" if not bad else f"note-proof: NOT ok — {'; '.join(bad)}")
    if a.out:
        sp.write_out(a.out, result)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
