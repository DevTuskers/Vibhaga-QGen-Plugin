#!/usr/bin/env python3
"""publish.py — W7: the admin-API publish loop as ONE committed tool (plan 2026-09-08-onboarding-under-90-minutes §2 W7,
§7 step 1; decision 0014 PD-1 guard-rails 1–6; S10 §3/§6/§7.1/§8/§9; TRAPS T9, T77).

Every run since run 6 rewrote this as a curl loop (GET → PUT with paper_metadata → dry-run → one publish per question →
T77), and run 10's token expired mid-run. This is that loop, with a FRESH password-grant token at the start of every
stage, and the six 0014 guard-rails built in:
  1. the staged `paper_metadata` is echoed from the GET and must EQUAL `--scope` (the API-side paper-bar confirm)
  2. `published-ids.json` is written BEFORE the first publish request (T9) — question, part and answer ids
  3. the dry-run's `signatures_at_risk` is printed and the tool refuses unless `--accept-signatures N` equals it (0 must be typed)
  4. every question in the set must carry `ingestion_metadata.needs_human_review: true` (flagged-only; the tool never clears)
  5. `t77-staged-vs-published.py` runs after the last publish (reused, not reimplemented) — a mismatch is a failed run
  6. `POST /auth/v1/logout?scope=global` is the last act, and the two SQL statements the orchestrator must run are printed

Usage (from anywhere; credentials + URLs are read at run time from Vibhaga-Admin/.env.local — never printed):
  publish.py get      <job> --out staged.json
  publish.py put      <job> --staged questions.json [--paper-metadata grade=8,subject=Mathematics,medium=sinhala]
                            [--drop-missing [--allow-drop]]          # S10 §8: GET → merge into the SERVER array → PUT
  publish.py publish  <job> --staged questions.json --scope grade=8,subject=Mathematics,medium=sinhala
                            --accept-signatures N [--ids ids.json] [--sub I] [--ids-out published-ids.json] [--dry-run]
  publish.py manifest <run-dir> [--out-dir DIR] [--date YYYY-MM-DD]  # S7 §3 coverage manifest .md + .json per sub-paper
  publish.py --self-test                                               # NO network: fake transport + fake psql

  get/put/publish: --env PATH (default: Vibhaga-Admin/.env.local, found by walking up from this file) · --cred-prefix VIBHAGA_ADMIN
          (→ VIBHAGA_ADMIN_EMAIL / VIBHAGA_ADMIN_PASSWORD; another actor: --cred-prefix VIBHAGA_ADMIN_WATHSALA)
  `--scope` values are compared EXACTLY against the API's PaperMetadataSchema shape (validation.ts): grade int,
  subject as catalogued ("Mathematics"), medium ∈ sinhala|english|tamil, optional exam slug.
  T77 needs DATABASE_URL (or Vibhaga-DB/.env beside Vibhaga-Admin) and the `psql` binary.

Exit codes: 0 ok · 1 T77 mismatch or self-test failure · 2 usage / missing input · 3 refused (scope, unflagged, drop,
            staged≠server) · 4 refused at the dry-run (signatures) · 5 a publish request failed (stopped; ids file stands)
            · 6 auth failed.
"""
from __future__ import annotations

import argparse, datetime as dt, json, os, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _admin_auth as _auth  # noqa: E402  (shared env + transport with paper-prep.py, W1)

HERE = Path(__file__).resolve().parent
UUID0 = "00000000-0000-4000-8000-000000000000"


class Refuse(Exception):
    def __init__(self, msg: str, code: int = 3):
        super().__init__(msg); self.code = code


# ----------------------------------------------------------------------------------------------- env / transport
def find_up(name: str, start: Path = HERE) -> Path | None:
    for d in [start, *start.parents]:
        if (d / name).exists(): return d / name
    return None


def read_env(path: Path) -> dict[str, str]:
    """Delegates to `_admin_auth.read_env` (one parser for the five `.env.local` keys — no drift between W1 and W7); returns
    every key present so `--cred-prefix` can pick another credential pair."""
    return _auth.read_env_all(path)


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    """(status, body); status 0 = connection-level failure (curl's `000`). The same urllib call as `_admin_auth`, minus headers."""
    st, _h, out = _auth.urllib_transport(method, url, headers, body)
    return st, out


class Api:
    """The admin plane: Supabase password grant + the qbank-admin-api Worker. `transport` is injectable (self-test)."""

    def __init__(self, env: dict[str, str], transport=urllib_transport, cred_prefix="VIBHAGA_ADMIN", log=print):
        need = ["NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", f"{cred_prefix}_EMAIL", f"{cred_prefix}_PASSWORD"]
        missing = [k for k in need if not env.get(k)]
        if missing: raise Refuse(f"env is missing {', '.join(missing)}", 2)
        try:
            self.cf = _auth.access_headers(env)
            self.base, self.sb = _auth.distinct_origins(env["NEXT_PUBLIC_API_BASE_URL"], env["NEXT_PUBLIC_SUPABASE_URL"])
        except SystemExit as e:
            raise Refuse(str(e), 2) from None
        self.anon = env["NEXT_PUBLIC_SUPABASE_ANON_KEY"]; self._email = env[f"{cred_prefix}_EMAIL"]; self._pw = env[f"{cred_prefix}_PASSWORD"]
        self.t = transport; self.log = log; self.token: str | None = None; self.user_id: str | None = None; self.grants = 0

    def _json(self, method, url, headers, body=None, *, scope):
        data = json.dumps(body).encode() if body is not None else None
        try:
            h = _auth.scoped_headers(url, {"content-type": "application/json", **headers}, scope, self.base, self.sb, self.cf)
        except SystemExit as e:
            raise Refuse(str(e), 2) from None
        st, raw = self.t(method, url, h, data)
        if scope == "admin" and st == 0 and raw in (_auth.TLS_CONFIG, _auth.TLS_VERIFY):
            raise Refuse(_auth.response_error(st, raw), 5)
        js = _auth.response_json(st, raw)
        return st, js if isinstance(js, dict) else {"error": "invalid JSON response (body withheld)"}

    def fresh_token(self, stage: str) -> str:
        """A new password grant per stage (run 10's token expired mid-run). The token stays in memory; never logged."""
        st, js = self._json("POST", f"{self.sb}/auth/v1/token?grant_type=password", {"apikey": self.anon}, {"email": self._email, "password": self._pw}, scope="supabase")
        if st != 200:
            diagnostic = _auth.response_error(st, js)
            raise Refuse(f"auth failed for stage {stage}: {diagnostic}", 6)
        if not isinstance(js.get("access_token"), str) or not _auth.re.fullmatch(r"[!-~]+", js["access_token"]):
            raise Refuse(f"auth failed for stage {stage}: HTTP {st} (response body withheld)", 6)
        user = js.get("user"); uid = user.get("id") if isinstance(user, dict) else None
        self.token = js["access_token"]; self.user_id = uid if isinstance(uid, str) and _auth.re.fullmatch(r"[0-9a-fA-F-]{36}", uid) else None; self.grants += 1
        self.log(f"auth: fresh token for stage '{stage}' (grant #{self.grants}, user {self.user_id})")
        return self.token

    def _auth(self): return {"authorization": f"Bearer {self.token}", "apikey": self.anon}

    def get_doc(self, job: str) -> dict:
        st, js = self._json("GET", f"{self.base}/v1/admin/extractions/{job}/questions", self._auth(), scope="admin")
        if st != 200: raise Refuse(f"GET questions → {_auth.response_error(st, js)}", 5)
        if not js.get("ready"): raise Refuse("GET questions → ready:false (no staged doc yet)", 3)
        checked_doc(js)
        return js

    def get_initial_doc(self, job: str, proof: dict) -> dict:
        if self.user_id != proof["actor_id"]:
            raise Refuse("initialization proof actor_id != fresh grant user", 3)
        st, js = self._json("GET", f"{self.base}/v1/admin/extractions/{job}", self._auth(), scope="admin")
        if st != 200: raise Refuse(f"GET job → {_auth.response_error(st, js)}", 5)
        required = {"id", "status", "paper_id", "filename", "question_count", "error", "created_at", "updated_at"}
        if not required <= js.keys() or js["id"] != job or js["paper_id"] != proof["paper_id"] or js["status"] != "uploaded" or js["error"] is not None:
            raise Refuse("initialization GET job identity/status/error does not match proof", 3)
        if type(js["question_count"]) is not int or js["question_count"] != 0:
            raise Refuse("initialization GET job question_count must be integer zero", 3)
        if js["filename"] is not None and not isinstance(js["filename"], str):
            raise Refuse("malformed initialization GET job filename", 5)
        if any(proof_time(js[k]) != proof_time(proof[k]) for k in ("created_at", "updated_at")):
            raise Refuse("initialization GET job timestamps changed from proof", 3)
        st, js = self._json("GET", f"{self.base}/v1/admin/extractions/{job}/questions", self._auth(), scope="admin")
        if st != 200: raise Refuse(f"GET questions → {_auth.response_error(st, js)}", 5)
        if set(js) != {"ready", "questions"} or js["ready"] is not False or js["questions"] != []:
            raise Refuse("initialization requires exactly ready:false and questions:[]; existing/malformed draft refused", 3)
        return {"questions": []}

    def put_doc(self, job: str, questions: list, paper_metadata: dict | None) -> dict:
        body: dict = {"questions": questions}
        if paper_metadata: body["paper_metadata"] = paper_metadata
        st, js = self._json("PUT", f"{self.base}/v1/admin/extractions/{job}/questions", self._auth(), body, scope="admin")
        if st != 200: raise Refuse(f"PUT questions → {_auth.response_error(st, js)}", 5)
        checked_doc(js)
        return js

    def publish(self, job: str, ids: list[str], dry_run=False) -> tuple[int, dict]:
        body: dict = {"question_ids": ids}
        if dry_run: body["dry_run"] = True
        return self._json("POST", f"{self.base}/v1/admin/extractions/{job}/publish", self._auth(), body, scope="admin")

    def logout_global(self) -> int:
        if not self.token: return -1
        st, _ = self._json("POST", f"{self.sb}/auth/v1/logout?scope=global", self._auth(), scope="supabase")
        self.token = None
        return st


# ----------------------------------------------------------------------------------------------- helpers
def checked_doc(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get("questions"), list):
        raise Refuse("malformed staged response (body withheld)", 5)
    for q in doc["questions"]:
        if not isinstance(q, dict) or not isinstance(q.get("question_id"), str) or not 1 <= len(q["question_id"]) <= 64:
            raise Refuse("malformed staged response (body withheld)", 5)
    paper = {} if doc.get("paper") is None else doc["paper"]; stats = {} if doc.get("stats") is None else doc["stats"]
    if not isinstance(paper, dict) or (paper.get("paper_metadata") is not None and not isinstance(paper["paper_metadata"], dict)) or not isinstance(stats, dict):
        raise Refuse("malformed staged response (body withheld)", 5)
    summary = {k: stats[k] for k in ("questions", "flagged") if k in stats}
    if any(type(v) is not int or v < 0 for v in summary.values()):
        raise Refuse("malformed staged response (body withheld)", 5)
    return summary


def checked_publish_result(js, dry):
    counts = ("signatures_at_risk", "unchanged_count") if dry else ("published", "sub_questions", "answers", "sub_answers")
    lists = ("questions",) if dry else ("reflagged", "unchanged")
    if not isinstance(js, dict) or any(type(js.get(k)) is not int or js[k] < 0 for k in counts) or any(not isinstance(js.get(k), list) for k in lists):
        raise Refuse("malformed publish response (body withheld)", 4 if dry else 5)
    if (dry and any(not isinstance(q, dict) for q in js["questions"])) or (not dry and any(not _auth.valid_uuid(i) for k in lists for i in js[k])):
        raise Refuse("malformed publish response (body withheld)", 4 if dry else 5)


def parse_kv(s: str | None) -> dict:
    """grade=8,subject=Mathematics,medium=sinhala[,exam=ol] → the PaperMetadataSchema shape (grade int; empty/null → None)."""
    out: dict = {}
    for part in filter(None, (s or "").split(",")):
        if "=" not in part: raise Refuse(f"bad scope item {part!r} (want key=value)", 2)
        k, v = part.split("=", 1); k = k.strip(); v = v.strip()
        if k not in ("grade", "subject", "medium", "exam"): raise Refuse(f"unknown scope key {k!r}", 2)
        out[k] = None if v in ("", "null", "None") else (int(v) if k == "grade" else v)
    return out


def norm_scope(m: dict | None) -> dict:
    m = m or {}
    return {k: m.get(k) for k in ("grade", "subject", "medium", "exam")}


def merge_ids(prev: dict | None, rec: dict) -> dict:
    """Same job, a later (partial) publish — e.g. stage 8's fix round: UNION the id records, keep the first `written_at`, never drop an id (T9)."""
    if not prev:
        return rec
    out = dict(prev)
    prev_ids = list(prev.get("question_ids") or [])
    out["question_ids"] = prev_ids + [i for i in rec["question_ids"] if i not in set(prev_ids)]
    if "written_at" not in out:
        out["written_at"] = rec["written_at"]  # runs 10/11 recorded {job, question_ids} only
    by_id = {q["question_id"]: dict(q) for q in (prev.get("questions") or [])}
    for q in rec["questions"]:  # per question: union every id list, so an answer/part added in a fix round is in the T9 record too
        cur = by_id.setdefault(q["question_id"], {"question_id": q["question_id"]})
        for k, v in q.items():
            if isinstance(v, list):
                cur[k] = list(cur.get(k) or []) + [x for x in v if x not in set(cur.get(k) or [])]
            elif k not in cur:
                cur[k] = v
    out["questions"] = list(by_id.values())
    out["updated_at"] = rec["written_at"]; out["last_publish_ids"] = rec["question_ids"]
    return out


def num_norm(x):
    """Numbers compare by value (`100.0 == 100` — Postgres/JSON round-trips drop the `.0`); dict/list recursively."""
    if isinstance(x, dict): return {k: num_norm(v) for k, v in x.items()}
    if isinstance(x, list): return [num_norm(v) for v in x]
    if isinstance(x, float) and x == int(x): return int(x)
    return x


def strip_server_hints(q: dict) -> dict:
    return {k: v for k, v in q.items() if k not in ("published", "published_at")}


def ids_of(q: dict) -> dict:
    """Every client-generated id in a question's tree — the record T9 says must exist before the first publish."""
    rec = {"question_id": q["question_id"], "question_number": q.get("question_number"), "answer_ids": [a.get("answer_id") for a in q.get("answers") or []], "sub_question_ids": [], "sub_answer_ids": []}
    def walk(parts):
        for p in parts or []:
            rec["sub_question_ids"].append(p.get("sub_question_id")); rec["sub_answer_ids"] += [a.get("sub_answer_id") for a in p.get("answers") or []]; walk(p.get("sub_questions"))
    walk(q.get("sub_questions")); return rec


def dump(o) -> str: return json.dumps(o, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def load_db_url(env_path: Path | None) -> str | None:
    if os.environ.get("DATABASE_URL"): return os.environ["DATABASE_URL"]
    if env_path:
        cand = env_path.parent.parent / "Vibhaga-DB" / ".env"
        if cand.exists(): return read_env(cand).get("DATABASE_URL")
    return None


# ----------------------------------------------------------------------------------------------- stages
def cmd_get(api: Api, job: str, out: Path, log=print) -> int:
    api.fresh_token("get"); doc = api.get_doc(job); doc.pop("ready", None)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump(doc), encoding="utf-8")
    log(f"get: {len(doc['questions'])} question(s) · stats {json.dumps(checked_doc(doc))} · paper_metadata saved → {out}")
    return 0


def merge_questions(server: list, staged: list, drop_missing: bool, allow_drop: bool) -> tuple[list, dict]:
    """S10 §8: merge INTO the server's array by question_id (replace in place, append new). With drop_missing the staged
    list is authoritative and server questions absent from it are dropped — refused if any of them is live."""
    by_id = {q["question_id"]: q for q in staged}
    merged = [strip_server_hints(by_id.pop(q["question_id"])) if q["question_id"] in by_id else q for q in server] if not drop_missing else []
    kept = [q for q in server if q["question_id"] not in {s["question_id"] for s in staged}]
    if drop_missing:
        live = [q for q in kept if q.get("published") is True]
        if live and not allow_drop: raise Refuse(f"merge would DROP {len(live)} live question(s) — pass --allow-drop only if that is intended (the staged doc has no undo)", 3)
        merged = [strip_server_hints(q) for q in staged]; by_id = {}
    merged += [strip_server_hints(q) for q in staged if q["question_id"] in by_id]
    # published/published_at are the SERVER's hints (routes.ts publish mirror) — keep the server's copy on replaced questions
    server_hint = {q["question_id"]: {k: q[k] for k in ("published", "published_at") if k in q} for q in server}
    for q in merged: q.update(server_hint.get(q["question_id"], {}))
    renorm = sum(1 for i, q in enumerate(merged) if q.get("sort_order") != i)
    for i, q in enumerate(merged): q["sort_order"] = i
    stats = {"server": len(server), "staged": len(staged), "replaced": sum(1 for q in staged if q["question_id"] in {s["question_id"] for s in server}),
             "added": sum(1 for q in staged if q["question_id"] not in {s["question_id"] for s in server}), "kept_unlisted": 0 if drop_missing else len(kept), "dropped": len(kept) if drop_missing else 0, "sort_order_renormalised": renorm}
    return merged, stats


def proof_time(value) -> dt.datetime:
    try:
        if not isinstance(value, str): raise ValueError
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None: raise ValueError
        return stamp.astimezone(dt.timezone.utc)
    except (ValueError, OverflowError):
        raise Refuse("initialization proof requires valid timezone-aware timestamps", 3) from None


def fresh_initial_proof(proof: dict) -> None:
    age = (dt.datetime.now(dt.timezone.utc) - proof_time(proof["checked_at"])).total_seconds()
    if not 0 <= age <= 300:
        raise Refuse("initialization proof is future-dated or older than 5 minutes; refresh independent SQL + R2 evidence", 3)


def initial_scope(value) -> dict:
    if not isinstance(value, dict) or set(value) - {"grade", "subject", "medium", "exam"}:
        raise Refuse("initialization requires complete paper scope with no unknown keys", 3)
    scope = norm_scope(value)
    grade, subject, medium, exam = (scope[k] for k in ("grade", "subject", "medium", "exam"))
    if medium not in ("sinhala", "english", "tamil") or (grade is None) == (exam is None):
        raise Refuse("initialization scope needs medium and grade XOR exam", 3)
    if grade is not None and (type(grade) is not int or not 6 <= grade <= 11):
        raise Refuse("initialization school scope requires grade 6–11", 3)
    if exam is not None and (not isinstance(exam, str) or not _auth.re.fullmatch(r"[a-z0-9_]{1,50}", exam)):
        raise Refuse("initialization scope has invalid exam slug", 3)
    if grade is not None or exam in ("ol", "al"):
        if not isinstance(subject, str) or not 1 <= len(subject) <= 120 or subject != subject.strip() or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in subject):
            raise Refuse("initialization scope requires a nonempty subject (max 120 chars)", 3)
    elif subject is not None:
        raise Refuse("initialization government-exam scope must not have a subject", 3)
    return scope


def load_initial_proof(path: Path, job: str, staged: dict, paper_metadata: dict | None) -> dict:
    try:
        proof = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise Refuse("cannot read initialization proof JSON (contents withheld)", 2) from None
    required = {"checked_at", "job_id", "paper_id", "source_pdf_sha256", "actor_id", "raw_status",
                "question_count", "paper_rows", "live_question_rows", "r2_bucket", "r2_key",
                "staged_object_absent", "exclusive_writer_confirmed", "created_at", "updated_at", "scope"}
    if not isinstance(proof, dict) or set(proof) != required:
        raise Refuse("initialization proof fields missing or unknown (see put --help)", 3)
    if not _auth.valid_uuid(job) or any(not _auth.valid_uuid(proof[k]) for k in ("job_id", "paper_id", "actor_id")) or proof["job_id"] != job:
        raise Refuse("initialization proof requires matching UUID job/paper/actor identities", 3)
    sha = proof["source_pdf_sha256"]
    if not isinstance(sha, str) or not _auth.re.fullmatch(r"[a-f0-9]{64}", sha):
        raise Refuse("initialization proof requires lowercase source_pdf_sha256", 3)
    if proof["raw_status"] != "uploaded" or any(type(proof[k]) is not int or proof[k] != 0 for k in ("question_count", "paper_rows", "live_question_rows")):
        raise Refuse("initialization proof must attest raw uploaded status and zero job/paper/live-question counts", 3)
    if proof["r2_bucket"] != "qbank-blobs" or proof["r2_key"] != f"onboarding/{job}/questions.json" or proof["staged_object_absent"] is not True or proof["exclusive_writer_confirmed"] is not True:
        raise Refuse("initialization proof requires exact R2 object absence and exclusive-writer attestation", 3)
    if proof_time(proof["created_at"]) != proof_time(proof["updated_at"]) or proof_time(proof["updated_at"]) > proof_time(proof["checked_at"]):
        raise Refuse("initialization proof requires unchanged original job timestamps before evidence check", 3)
    fresh_initial_proof(proof)
    checked_doc(staged)
    paper = staged.get("paper")
    if not isinstance(paper, dict) or paper.get("paper_id") != proof["paper_id"] or paper.get("source_pdf_sha256") != sha:
        raise Refuse("initialization staged paper identity/hash does not match proof", 3)
    scope = initial_scope(proof["scope"])
    if initial_scope(paper.get("paper_metadata")) != scope or (paper_metadata is not None and initial_scope(paper_metadata) != scope):
        raise Refuse("initialization proof scope != local paper metadata / --paper-metadata", 3)
    questions = staged["questions"]
    if not 1 <= len(questions) <= 400 or len({q["question_id"] for q in questions}) != len(questions):
        raise Refuse("initialization requires 1–400 questions with unique IDs", 3)
    for q in questions:
        if not _auth.valid_uuid(q["question_id"]) or not isinstance(q.get("question_text"), str) or len(q["question_text"]) > 50000:
            raise Refuse("initialization requires UUID questions with valid question_text", 3)
        if not isinstance(q.get("ingestion_metadata"), dict) or q["ingestion_metadata"].get("needs_human_review") is not True or (q.get("published") is not None and q.get("published") is not False) or q.get("published_at") is not None:
            raise Refuse("initialization requires flagged-only, unpublished local questions", 3)
    return proof


def cmd_put(api: Api, job: str, staged_path: Path, paper_metadata: dict | None, drop_missing: bool, allow_drop: bool, log=print,
            *, initialize_empty_proof: Path | None = None) -> int:
    try:
        staged = json.loads(staged_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise Refuse("cannot read staged JSON (contents withheld)", 2) from None
    proof = None
    if initialize_empty_proof is not None:
        if drop_missing or allow_drop: raise Refuse("initialization proof cannot be combined with drop flags", 3)
        proof = load_initial_proof(initialize_empty_proof, job, staged, paper_metadata)
    staged_qs = staged["questions"] if isinstance(staged, dict) else staged
    if paper_metadata is None and isinstance(staged, dict): paper_metadata = (staged.get("paper") or {}).get("paper_metadata") or None
    api.fresh_token("put"); server = api.get_initial_doc(job, proof) if proof is not None else api.get_doc(job)                      # GET immediately before the PUT (S10 §8 rule 2)
    merged, stats = merge_questions(server.get("questions") or [], staged_qs, drop_missing, allow_drop)
    log(f"put: merge {json.dumps(stats)} · paper_metadata {json.dumps(paper_metadata)}")
    if proof is not None:
        log("initialize-empty: operator-attested SQL + R2 evidence; not atomic — exclusive writer required; concurrent writes can race GET/PUT")
        log(f"initialize-empty: approved job_id={job} paper_id={proof['paper_id']} actor_id={proof['actor_id']} scope={json.dumps(initial_scope(proof['scope']))} checked_at={proof_time(proof['checked_at']).isoformat()}")
        fresh_initial_proof(proof)
    res = api.put_doc(job, merged, paper_metadata)
    if proof is not None:
        paper = res.get("paper") or {}
        if paper.get("paper_id") != proof["paper_id"] or paper.get("source_pdf_sha256") != proof["source_pdf_sha256"] or initial_scope(paper.get("paper_metadata")) != initial_scope(proof["scope"]):
            raise Refuse("initialization PUT returned different paper identity/hash/scope; draft was written, stop and inspect", 5)
    got = res.get("questions") or []
    log(f"put: server now holds {len(got)} question(s) · stats {json.dumps(checked_doc(res))} · paper_metadata received")
    if len(got) != len(merged): raise Refuse(f"PUT echoed {len(got)} questions, sent {len(merged)}", 5)
    lowered = sum(1 for q, s in zip(got, merged) if (s.get("ingestion_metadata") or {}).get("needs_human_review") is True and (q.get("ingestion_metadata") or {}).get("needs_human_review") is not True)
    if lowered: raise Refuse(f"server lowered the review flag on {lowered} question(s) — should be impossible (routes.ts clamps)", 5)
    return 0


def run_publish(api: Api, job: str, staged_path: Path, scope: dict, accept: int | None, ids_path: Path | None, sub: str | None,
                ids_out: Path, dry_run_only: bool, t77_runner, log=print) -> int:
    staged = json.loads(staged_path.read_text(encoding="utf-8"))
    want_ids = json.loads(ids_path.read_text()) if ids_path else [q["question_id"] for q in staged["questions"]]
    if not isinstance(want_ids, list) or any(not _auth.valid_uuid(i) for i in want_ids):
        raise Refuse("REFUSED: publish set requires UUID question ids (values withheld)", 3)
    # ---- stage: GET + guard-rail 1 (scope echo) + guard-rail 4 (flagged only) + staged == server
    api.fresh_token("publish:get"); doc = api.get_doc(job)
    pm = norm_scope((doc.get("paper") or {}).get("paper_metadata")); want = norm_scope(scope)
    if pm != want: raise Refuse("REFUSED: staged paper_metadata != --scope (fix the paper bar with `put --paper-metadata …`, or fix --scope)", 3)
    log(f"scope: staged paper_metadata = {json.dumps(pm)} · --scope = {json.dumps(want)}")
    server_q = {q["question_id"]: q for q in doc.get("questions") or []}
    missing = [i for i in want_ids if i not in server_q]
    if missing: raise Refuse(f"REFUSED: {len(missing)} id(s) not in the server's staged doc: {missing[:3]}…", 3)
    if any(type(server_q[i].get("question_number")) is not int for i in want_ids):
        raise Refuse("REFUSED: publish set requires integer question numbers (values withheld)", 3)
    staged_q = {q["question_id"]: q for q in staged["questions"]}
    differ = [server_q[i].get("question_number") for i in want_ids if i in staged_q and num_norm(strip_server_hints(staged_q[i])) != num_norm(strip_server_hints(server_q[i]))]
    if differ: raise Refuse(f"REFUSED: staged file differs from the server doc on Q{differ} — publish reads the SERVER doc; run `put` first (T77)", 3)
    unflagged = [server_q[i].get("question_number") for i in want_ids if (server_q[i].get("ingestion_metadata") or {}).get("needs_human_review") is not True]
    if unflagged: raise Refuse(f"REFUSED: unflagged in publish set: Q{unflagged} (0014 guard-rail 4 / 0008 PD-3 — set ingestion_metadata.needs_human_review: true)", 3)
    order = sorted(want_ids, key=lambda i: (server_q[i].get("sort_order", 0), str(server_q[i].get("question_number"))))
    log(f"publish set: {len(order)} question(s), all flagged, in order: {[server_q[i].get('question_number') for i in order]}")
    # ---- guard-rail 2: ids BEFORE the first publish (T9)
    rec = {"job": job, "paper_id": (doc.get("paper") or {}).get("paper_id"), "scope": pm, "written_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "question_ids": order, "questions": [ids_of(server_q[i]) for i in order]}
    existing = json.loads(ids_out.read_text()) if ids_out.exists() else {}
    flat = isinstance(existing, dict) and "question_ids" in existing
    if not sub:
        if flat and existing.get("job") != job:
            raise Refuse(f"REFUSED: {ids_out} already holds job {existing.get('job')} — pass --sub I/--sub II so each sub-paper's record is kept (T9: the id map is never overwritten)", 3)
        if existing and not flat:
            raise Refuse(f"REFUSED: {ids_out} is nested by sub-paper ({sorted(existing)}) — pass --sub", 3)
        ids_out.write_text(dump(merge_ids(existing if flat else None, rec)), encoding="utf-8")
    else:
        if flat:
            raise Refuse(f"REFUSED: {ids_out} holds a flat record for job {existing.get('job')} — it cannot be nested under --sub {sub} without losing it (T9); "
                         f"move it aside or re-run that sub-paper with --sub", 3)
        prev = existing.get(sub)
        if prev and prev.get("job") != job:
            raise Refuse(f"REFUSED: {ids_out}[{sub}] already holds job {prev.get('job')} (this is {job}) — the id map is never overwritten (T9)", 3)
        existing[sub] = merge_ids(prev, rec); ids_out.write_text(dump(existing), encoding="utf-8")
    log(f"ids: wrote {ids_out} ({len(order)} question ids, {sum(len(r['sub_question_ids']) for r in rec['questions'])} part ids, {sum(len(r['answer_ids']) + len(r['sub_answer_ids']) for r in rec['questions'])} answer ids) BEFORE the first publish")
    # ---- guard-rail 3: dry-run → signatures_at_risk must be accepted explicitly
    api.fresh_token("publish:dry-run"); st, js = api.publish(job, order, dry_run=True)
    if st != 200: raise Refuse(f"dry-run → {_auth.response_error(st, js)}", 4)
    checked_publish_result(js, True)
    risk = js["signatures_at_risk"]; unchanged = js["unchanged_count"]
    log(f"dry-run: signatures_at_risk = {risk} · unchanged_count = {unchanged} · questions previewed = {len(js['questions'])}")
    if accept is None: raise Refuse(f"REFUSED: pass --accept-signatures {risk} to proceed (the number must be typed, including 0)", 4)
    if accept != risk: raise Refuse(f"REFUSED: --accept-signatures {accept} != signatures_at_risk {risk}", 4)
    if dry_run_only: log("--dry-run: stopping after the dry-run; nothing published"); return 0
    # ---- the loop: one request per question, printed order, stop on first non-2xx, one retry on 000
    api.fresh_token("publish:loop"); done = 0
    for i in order:
        q = server_q[i]; st, js = api.publish(job, [i])
        if st == 0: log(f"  Q{q.get('question_number')} {i} → 000 (connection) — retrying once"); time.sleep(2); st, js = api.publish(job, [i])
        if 200 <= st < 300:
            checked_publish_result(js, False)
            done += 1; log(f"  Q{q.get('question_number')} {i} → {st} published={js['published']} sub_q={js['sub_questions']} answers={js['answers']}+{js['sub_answers']} reflagged={len(js['reflagged'])} unchanged={len(js['unchanged'])}")
        else:
            log(f"  Q{q.get('question_number')} {i} → {_auth.response_error(st, js)}"); raise Refuse(f"STOPPED after {done}/{len(order)}: publish of Q{q.get('question_number')} failed with HTTP {st}. Ids are in {ids_out}; fix and re-run with --ids for the rest.", 5)
    log(f"published {done}/{len(order)}")
    # ---- guard-rail 5: T77 read-back
    rc = t77_runner(staged_path, order)
    log(f"t77: exit {rc}" + ("" if rc == 0 else " — MISMATCH: the run is FAILED until staged and live agree (T77)"))
    return 1 if rc else 0


def t77_subprocess(env_path: Path | None, log=print):
    def run(staged_path: Path, ids: list[str]) -> int:
        url = load_db_url(env_path)
        if not url: log("t77: DATABASE_URL not set and no Vibhaga-DB/.env found — T77 could NOT run (counts as a failure)"); return 1
        env = {**os.environ, "DATABASE_URL": url}
        p = subprocess.run([sys.executable, str(HERE / "t77-staged-vs-published.py"), str(staged_path), "--ids", json.dumps(ids)], env=env, capture_output=True, text=True)
        for line in (p.stdout + p.stderr).strip().splitlines(): log("  " + line)
        return p.returncode
    return run


def finish(api: Api, log=print) -> None:
    """Guard-rail 6: logout everything, then print what the ORCHESTRATOR must run (the tool has no SQL access)."""
    st = api.logout_global(); uid = api.user_id or "<actor user_id>"
    log(f"logout?scope=global → HTTP {st} (a 204 is NOT the proof — agent-identities §3)")
    log("orchestrator: run these on the ADMIN Supabase project and write both counts to sessions.json (must be 0 / 0):")
    log(f"  SELECT count(*) FROM auth.sessions WHERE user_id = '{uid}';")
    log(f"  SELECT count(*) FROM auth.refresh_tokens WHERE user_id = '{uid}';")


# ----------------------------------------------------------------------------------------------- manifest
def coverage_md(sp: dict, sidecar: str, run_rel: str, published_line: str) -> str:
    sha = lambda s: (s or "")[:16] + "…"
    sc = sp.get("scope") or {}
    rows = [f"# Coverage manifest — {sp['paper_slug']}", "", f"Sidecar: `{sidecar}`. Run record: `{run_rel}`.", "", "| key | value |", "|---|---|",
            f"| paper_disposition | `{sp.get('paper_disposition')}` |",
            f"| source PDF | `{Path(sp.get('source_pdf') or '').name}` (combined sha `{sha(sp.get('source_pdf_sha256_combined') or sp.get('source_pdf_sha256'))}`), PDF pages {json.dumps(sp.get('pdf_pages'))} |",
            f"| uploaded split | `{sp.get('split_file')}` sha `{sha(sp.get('source_pdf_sha256'))}` |",
            f"| paper_id / job_id | `{sp.get('paper_id')}` / `{sp.get('job_id')}` |",
            f"| scope | grade {sc.get('grade')} · {sc.get('subject')} · {sc.get('medium')} · exam {sc.get('exam') or 'NULL'} |",
            f"| regime | {sp.get('regime')} |",
            f"| printed items / units | {sp.get('source_questions')} items · totals {json.dumps(sp.get('totals'))} |",
            f"| published | {published_line} |", "", "| printed # | part (printed → live) | page | disposition | reason |", "|---|---|---|---|---|"]
    cut = lambda s: (s[:177] + "…") if s and len(s) > 180 else (s or "")
    for q in sp.get("questions") or []:
        if q.get("parts"):
            for p in q["parts"]: rows.append(f"| {q['n']} | {p.get('printed')} → {p.get('label')} | {q.get('page')} | `{p.get('disposition')}` | {cut(p.get('reason') or q.get('reason'))} |")
        else: rows.append(f"| {q['n']} | — | {q.get('page')} | `{q.get('disposition')}` | {cut(q.get('reason'))} |")
    return "\n".join(rows) + "\n"


def cmd_manifest(run_dir: Path, out_dir: Path, date: str, log=print) -> int:
    man = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    subs = man.get("sub_papers") or [man]
    pub = json.loads((run_dir / "published-ids.json").read_text()) if (run_dir / "published-ids.json").exists() else {}
    out_dir.mkdir(parents=True, exist_ok=True); bad = 0
    for sp in subs:
        # reconcile (S7 §3.4) before writing anything
        qs = sp.get("questions") or []; tot = sp.get("totals") or {}
        by_kind: dict = {}
        for q in qs: by_kind[q["disposition"].split(":")[0]] = by_kind.get(q["disposition"].split(":")[0], 0) + 1
        probs = []
        if sp.get("source_questions") != len(qs): probs.append(f"declared {sp.get('source_questions')} != counted {len(qs)}")
        if {k: v for k, v in tot.items() if v} != by_kind: probs.append(f"totals {tot} != by_kind {by_kind}")
        probs += [f"Q{q['n']} {q['disposition']} without reason" for q in qs if q["disposition"] != "published" and not (q.get("reason") or "")]
        probs += [f"Q{q['n']} published without question_id" for q in qs if q["disposition"] == "published" and not q.get("question_id")]
        pub_ids = None
        for k, v in (pub.items() if isinstance(pub, dict) and "question_ids" not in pub else [("", pub)]):
            if isinstance(v, dict) and v.get("job") == sp.get("job_id"): pub_ids = set(v.get("question_ids") or [])
        if pub_ids is not None:
            probs += [f"Q{q['n']} published but its id is not in published-ids.json" for q in qs if q["disposition"] == "published" and q.get("question_id") not in pub_ids]
        else: log(f"manifest: WARN no published-ids entry for job {sp.get('job_id')} — id cross-check skipped")
        flagged = ""
        for sf in run_dir.glob("questions*.json"):
            st = json.loads(sf.read_text(encoding="utf-8")); ids = {q["question_id"] for q in st.get("questions") or []}
            if pub_ids and ids >= pub_ids: n = sum(1 for q in st["questions"] if (q.get("ingestion_metadata") or {}).get("needs_human_review") is True); flagged = f", {n}/{len(ids)} flagged"
        name = f"{date}-{sp['paper_slug']}"
        (out_dir / f"{name}.json").write_text(dump(sp), encoding="utf-8")
        (out_dir / f"{name}.md").write_text(coverage_md(sp, f"{name}.json", f"../runs/{run_dir.name}/", f"{date}{flagged}"), encoding="utf-8")
        log(f"manifest: {name}.md + .json — {len(qs)} rows, totals {json.dumps(tot)}" + (f" · PROBLEMS: {probs}" if probs else " · reconciled"))
        bad += bool(probs)
    return 1 if bad else 0


# ----------------------------------------------------------------------------------------------- self-test (no network)
class FakeAdmin:
    """In-memory admin plane: password grant, GET/PUT questions, publish (+dry_run), logout. Records every call."""

    def __init__(self, doc: dict, signatures_at_risk=0, fail_publish_at: int | None = None, fail_status=500, flake_first=False):
        self.doc = json.loads(json.dumps(doc)); self.risk = signatures_at_risk; self.fail_at = fail_publish_at; self.fail_status = fail_status
        self.flake = flake_first; self.calls: list[tuple[str, str]] = []; self.publishes: list[list[str]] = []; self.on_publish = None; self.grants = 0; self.logouts = 0

    def __call__(self, method, url, headers, body):
        path = urllib.parse.urlparse(url).path + ("?" + urllib.parse.urlparse(url).query if urllib.parse.urlparse(url).query else "")
        self.calls.append((method, path)); js = json.loads(body) if body else {}
        if path.startswith("/auth/v1/token"):
            self.grants += 1
            if js.get("password") != "pw": return 400, b'{"error":"invalid_grant"}'
            return 200, json.dumps({"access_token": f"tok{self.grants}", "user": {"id": "11111111-2222-4333-8444-555555555555"}}).encode()
        if path.startswith("/auth/v1/logout"): self.logouts += 1; return 204, b""
        if not headers.get("authorization", "").startswith("Bearer tok"): return 401, b'{"error":"unauthorized"}'
        if path.endswith("/questions") and method == "GET": return 200, json.dumps({"ready": True, **self.doc}).encode()
        if path.endswith("/questions") and method == "PUT":
            pm = {**((self.doc.get("paper") or {}).get("paper_metadata") or {}), **(js.get("paper_metadata") or {})}
            prev_flag = {q["question_id"] for q in self.doc["questions"] if (q.get("ingestion_metadata") or {}).get("needs_human_review") is True}
            for q in js["questions"]:
                if q["question_id"] in prev_flag: q["ingestion_metadata"] = {**(q.get("ingestion_metadata") or {}), "needs_human_review": True}
            self.doc = {"paper": {**(self.doc.get("paper") or {}), "paper_metadata": {k: v for k, v in pm.items() if v is not None}}, "questions": js["questions"], "stats": {"questions": len(js["questions"]), "flagged": sum(1 for q in js["questions"] if (q.get("ingestion_metadata") or {}).get("needs_human_review") is True)}}
            return 200, json.dumps({"ready": True, **self.doc}).encode()
        if path.endswith("/publish"):
            if js.get("dry_run"): return 200, json.dumps({"dry_run": True, "questions": [{"question_id": i} for i in js["question_ids"]], "signatures_at_risk": self.risk, "unchanged_count": 0}).encode()
            if self.on_publish: self.on_publish(len(self.publishes))
            if self.flake and not self.publishes: self.flake = False; return 0, b"connection reset"
            self.publishes.append(js["question_ids"])
            if self.fail_at is not None and len(self.publishes) == self.fail_at: return self.fail_status, b'{"error":"boom"}'
            for q in self.doc["questions"]:
                if q["question_id"] in js["question_ids"]: q["published"] = True; q["published_at"] = "2026-09-08T00:00:00Z"
            return 200, json.dumps({"published": len(js["question_ids"]), "sub_questions": 0, "sub_answers": 0, "answers": 1, "question_ids": js["question_ids"], "reflagged": [], "signatures_destroyed": [], "signatures_preserved": [], "unchanged": []}).encode()
        return 404, b'{"error":"not_found"}'


FAKE_ENV = {"NEXT_PUBLIC_API_BASE_URL": "https://admin-api.invalid", "NEXT_PUBLIC_SUPABASE_URL": "https://sb.invalid", "NEXT_PUBLIC_SUPABASE_ANON_KEY": "anon", "VIBHAGA_ADMIN_EMAIL": "actor@invalid", "VIBHAGA_ADMIN_PASSWORD": "pw"}
FAKE_PSQL = r'''#!/usr/bin/env python3
# fake psql for publish.py --self-test: ignores the SQL, prints the JSON rows built from $FAKE_LIVE (a staged doc)
import json, os, sys
doc = json.load(open(os.environ["FAKE_LIVE"])); rows = []
for q in doc["questions"]:
    parts = []
    def walk(lst, parent):
        for s in lst or []:
            parts.append({"sub_question_id": s["sub_question_id"], "label": s.get("label"), "text": s.get("text"), "text_sinhala": s.get("text_sinhala"), "sort_order": s.get("sort_order"), "parent": parent, "diagram_dsl": s.get("diagram_dsl"),
                          "answers": [{"sub_answer_id": a["sub_answer_id"], "approach": a.get("approach"), "final_answer_latex": a.get("final_answer_latex"), "diagram_dsl": a.get("diagram_dsl")} for a in s.get("answers") or []]})
            walk(s.get("sub_questions"), s["sub_question_id"])
    walk(q.get("sub_questions"), None)
    rows.append({"question_id": q["question_id"], "question_number": q["question_number"], "question_text": q.get("question_text"), "question_text_sinhala": q.get("question_text_sinhala"),
                 "needs_human_review": bool((q.get("ingestion_metadata") or {}).get("needs_human_review")), "diagram_dsl": q.get("diagram_dsl"),
                 "answers": [{"answer_id": a["answer_id"], "approach": a.get("approach"), "final_answer_latex": a.get("final_answer_latex"), "diagram_dsl": a.get("diagram_dsl")} for a in q.get("answers") or []], "parts": parts or None})
print(json.dumps(rows))
'''


def self_test() -> int:
    docs = HERE.parent.parent.parent
    staged_src = next((p for p in [Path(os.environ.get("RUN11_STAGED", "/nonexistent")), docs / "question-onboarding" / "runs" / "2026-09-07-run11-g8-nwp-2024" / "questions-I.json"] if p.exists()), None)
    if not staged_src: print("publish.py --self-test: need run 11's staged doc (the run record's questions-I.json, or RUN11_STAGED)"); return 2
    full = json.loads(staged_src.read_text(encoding="utf-8"))
    doc = {"paper": full["paper"], "questions": [strip_server_hints(q) for q in full["questions"][:5]], "stats": {"questions": 5, "flagged": 5}}
    T = Path(tempfile.mkdtemp(prefix="publish-selftest.")); results: list[tuple[str, bool, str]] = []
    quiet: list[str] = []; log = quiet.append
    def case(name, ok, detail=""): results.append((name, ok, detail)); print(f"  {'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")
    staged = T / "staged.json"; staged.write_text(dump(doc)); ids_out = T / "published-ids.json"
    scope_ok = {"grade": 8, "subject": "Mathematics", "medium": "sinhala"}
    t77_ok = lambda *_: 0
    def run(fake, scope=scope_ok, accept=0, dry=False, t77=t77_ok, sub=None, ids=None, out=ids_out, staged_override=None):
        quiet.clear(); api = Api(FAKE_ENV, transport=fake, log=log)
        try: rc = run_publish(api, "job-1", staged_override or staged, scope, accept, ids, sub, out, dry, t77, log=log)
        except Refuse as e: log(str(e)); rc = e.code
        finish(api, log=log); return rc
    # 1. scope mismatch → refused, no publish call
    f = FakeAdmin(doc); rc = run(f, scope={"grade": 7, "subject": "Mathematics", "medium": "sinhala"})
    case("refuses when --scope != staged paper_metadata", rc == 3 and not f.publishes and any("REFUSED: staged paper_metadata" in l for l in quiet), f"rc={rc} publishes={len(f.publishes)}")
    # 2. unflagged question → refused
    d2 = json.loads(json.dumps(doc)); d2["questions"][2]["ingestion_metadata"] = {"needs_human_review": False}
    f = FakeAdmin(d2); s2 = T / "s2.json"; s2.write_text(dump(d2)); quiet.clear(); api = Api(FAKE_ENV, transport=f, log=log)
    try: rc = run_publish(api, "job-1", s2, scope_ok, 0, None, None, ids_out, False, t77_ok, log=log)
    except Refuse as e: rc = e.code; log(str(e))
    case("refuses an unflagged question in the set", rc == 3 and not f.publishes and any("unflagged in publish set: Q[3]" in l for l in quiet), f"rc={rc}")
    if ids_out.exists(): ids_out.unlink()
    # 3. signatures: absent / mismatch / zero-must-be-typed
    f = FakeAdmin(doc, signatures_at_risk=2); rc = run(f, accept=None)
    case("refuses when --accept-signatures is absent (risk 2)", rc == 4 and not f.publishes, f"rc={rc}")
    f = FakeAdmin(doc, signatures_at_risk=2); rc = run(f, accept=1)
    case("refuses when --accept-signatures 1 != signatures_at_risk 2", rc == 4 and not f.publishes, f"rc={rc}")
    f = FakeAdmin(doc, signatures_at_risk=0); rc = run(f, accept=None)
    case("refuses when signatures_at_risk is 0 and --accept-signatures was not typed", rc == 4 and not f.publishes, f"rc={rc}")
    f = FakeAdmin(doc, signatures_at_risk=2); rc = run(f, accept=2, dry=True)
    case("--dry-run with the matching --accept-signatures 2 stops after the dry-run, publishes nothing", rc == 0 and not f.publishes and any("nothing published" in l for l in quiet), f"rc={rc}")
    # 4. ids file exists before the first publish; 5. full clean loop with fresh token per stage + logout + SQL
    if ids_out.exists(): ids_out.unlink()
    seen: dict = {}
    f = FakeAdmin(doc, flake_first=True); f.on_publish = lambda n: seen.setdefault("ids_at_first_publish", ids_out.exists() and len(json.loads(ids_out.read_text())["question_ids"]) == 5)
    rc = run(f, accept=0)
    case("published-ids.json (5 ids) exists BEFORE the first publish request (T9)", seen.get("ids_at_first_publish") is True)
    case("clean loop: 5 publish requests in order, one id each, 000 retried once, exit 0", rc == 0 and f.publishes == [[q["question_id"]] for q in doc["questions"]] and any("retrying once" in l for l in quiet), f"rc={rc} publishes={len(f.publishes)}")
    case("a fresh token per stage (get, dry-run, loop = 3 grants) and logout?scope=global last", f.grants == 3 and f.logouts == 1 and f.calls[-1][1].endswith("/auth/v1/logout?scope=global"), f"grants={f.grants} logouts={f.logouts}")
    case("prints the two revocation SQL statements for the actor's user_id", sum(1 for l in quiet if "FROM auth.sessions WHERE user_id = '11111111-2222-4333-8444-555555555555'" in l or "FROM auth.refresh_tokens WHERE user_id = '11111111-2222-4333-8444-555555555555'" in l) == 2)
    case("no secret in the log (password / token never printed)", not any(w in ("pw", "tok1", "tok2", "tok3", "actor@invalid") for l in quiet for w in l.replace("'", " ").replace('"', " ").split()))
    # 5b. the id map is never overwritten: a second sub-paper without --sub is refused; with --sub both records are kept
    ids_out.write_text(json.dumps({"job": "another-job", "question_ids": ["x"]}))
    f = FakeAdmin(doc); rc = run(f, accept=0)
    case("refuses to overwrite published-ids.json that holds another job (no --sub) — exit 3, no publish", rc == 3 and not f.publishes, f"rc={rc}")
    ids_out.unlink(); ids_out.write_text(json.dumps({"I": {"job": "job-I", "question_ids": ["x"]}}))
    f = FakeAdmin(doc); rc = run(f, accept=0, sub="II")
    kept = json.loads(ids_out.read_text())
    case("--sub II nests beside an existing I record (both kept)", rc == 0 and set(kept) == {"I", "II"} and kept["I"]["job"] == "job-I", f"rc={rc} keys={sorted(kept)}")
    f = FakeAdmin(doc); rc = run(f, accept=0, sub="I")
    case("--sub I over an I record of a different job is refused (T9)", rc == 3 and not f.publishes, f"rc={rc}")
    ids_out.unlink(); ids_out.write_text(json.dumps({"job": "another-job", "question_ids": ["x"], "questions": []}))
    f = FakeAdmin(doc); rc = run(f, accept=0, sub="II")
    case("a flat record of another job + --sub II is refused, not discarded (T9)", rc == 3 and json.loads(ids_out.read_text()).get("job") == "another-job", f"rc={rc}")
    ids_out.unlink()
    f = FakeAdmin(doc); rc = run(f, accept=0, sub="I")
    sub_ids = ids_out.with_name("subset-ids.json"); sub_ids.write_text(json.dumps([doc["questions"][2]["question_id"]]))
    f = FakeAdmin(doc); rc2 = run(f, accept=0, sub="I", ids=sub_ids)
    kept = json.loads(ids_out.read_text())["I"]
    case("same-job re-publish of a 1-question subset MERGES into the 5-question record (fix round keeps every id)", rc == 0 and rc2 == 0 and len(kept["question_ids"]) == 5 and len(kept["questions"]) == 5 and kept["last_publish_ids"] == [doc["questions"][2]["question_id"]], f"ids now {len(kept['question_ids'])}")
    ids_out.unlink(); ids_out.write_text(json.dumps({"I": {"job": "job-1", "question_ids": [doc["questions"][0]["question_id"]]}}))  # run 10/11's legacy shape
    f = FakeAdmin(doc); rcL = run(f, accept=0, sub="I", ids=sub_ids)
    keptL = json.loads(ids_out.read_text())["I"]
    case("legacy {job, question_ids} record (runs 10/11) merges without crashing; both ids kept", rcL == 0 and len(keptL["question_ids"]) == 2 and len(keptL["questions"]) == 1, f"rc={rcL}")
    ids_out.unlink()
    f = FakeAdmin(doc); rc = run(f, accept=0, sub="I")
    d8 = json.loads(json.dumps(doc)); d8["questions"][2].setdefault("answers", []).append({"answer_id": "aaaaaaaa-0000-4000-8000-00000000fix1", "approach": "x", "final_answer_latex": "$1$"})
    s8 = ids_out.with_name("staged-fix.json"); s8.write_text(json.dumps(d8))
    f = FakeAdmin(d8); rc3 = run(f, accept=0, sub="I", ids=sub_ids, staged_override=s8)
    q3 = [q for q in json.loads(ids_out.read_text())["I"]["questions"] if q["question_id"] == doc["questions"][2]["question_id"]][0]
    case("an answer added in a fix round lands in the T9 record (per-question id union)", rc3 == 0 and "aaaaaaaa-0000-4000-8000-00000000fix1" in q3.get("answer_ids", []), f"rc={rc3} answer_ids={q3.get('answer_ids')}")
    ids_out.unlink()
    # 6. stops on a 500
    f = FakeAdmin(doc, fail_publish_at=3); rc = run(f, accept=0)
    case("stops on the first non-2xx: 500 on request 3 → 3 requests, exit 5, ids file stands", rc == 5 and len(f.publishes) == 3 and ids_out.exists(), f"rc={rc} publishes={len(f.publishes)}")
    # 7. staged ≠ server → refused (T77 pre-check)
    d7 = json.loads(json.dumps(doc)); d7["questions"][1]["question_text"] += " (edited on the server)"
    f = FakeAdmin(d7); rc = run(f, accept=0)
    case("refuses when the staged file differs from the server doc (run `put` first)", rc == 3 and not f.publishes, f"rc={rc}")
    # 8. T77 via the real t77-staged-vs-published.py against a FAKE psql: clean, then a planted staged edit
    bindir = T / "bin"; bindir.mkdir(); (bindir / "psql").write_text(FAKE_PSQL); (bindir / "psql").chmod(0o755)
    live = T / "live.json"; live.write_text(dump(doc))
    def t77(staged_path, ids):
        env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "DATABASE_URL": "postgres://fake", "FAKE_LIVE": str(live)}
        p = subprocess.run([sys.executable, str(HERE / "t77-staged-vs-published.py"), str(staged_path), "--ids", json.dumps(ids)], env=env, capture_output=True, text=True)
        for l in p.stdout.strip().splitlines(): log("  " + l)
        return p.returncode
    f = FakeAdmin(doc); rc = run(f, accept=0, t77=t77)
    case("T77 (real script, fake psql) passes when staged == published", rc == 0 and any("0 mismatch(es)" in l for l in quiet), next((l.strip() for l in quiet if "t77:" in l and "comparisons" in l), ""))
    d8 = json.loads(json.dumps(doc)); d8["questions"][0]["answers"][0]["final_answer_latex"] = "$1, 5$"; s8 = T / "s8.json"; s8.write_text(dump(d8))
    f = FakeAdmin(d8); quiet.clear(); api = Api(FAKE_ENV, transport=f, log=log)
    try: rc = run_publish(api, "job-1", s8, scope_ok, 0, None, None, ids_out, False, t77, log=log)
    except Refuse as e: rc = e.code
    case("T77 FAILS on a planted staged edit (final_answer_latex) — exit 1, 1 mismatch", rc == 1 and any("1 mismatch(es)" in l for l in quiet) and any("MISMATCH Q1.a[" in l for l in quiet), next((l.strip() for l in quiet if "MISMATCH" in l), ""))
    # 9. put: merge into the server array; refuse dropping a live question
    server = json.loads(json.dumps(doc)); server["questions"][0]["published"] = True; server["questions"][0]["published_at"] = "x"
    f = FakeAdmin(server); part = {"paper": doc["paper"], "questions": [dict(doc["questions"][1], question_text="NEW TEXT"), {**doc["questions"][4], "question_id": UUID0, "question_number": 99}]}
    sp = T / "part.json"; sp.write_text(dump(part)); quiet.clear(); api = Api(FAKE_ENV, transport=f, log=log)
    rc = cmd_put(api, "job-1", sp, {"grade": 8, "subject": "Mathematics", "medium": "sinhala"}, False, False, log=log)
    got = f.doc["questions"]
    case("put merges INTO the server array (replace by id, append new, keep unlisted, sort_order renormalised)", rc == 0 and len(got) == 6 and got[1]["question_text"] == "NEW TEXT" and got[5]["question_id"] == UUID0 and [q["sort_order"] for q in got] == list(range(6)) and got[0].get("published") is True, f"n={len(got)}")
    f = FakeAdmin(server); quiet.clear(); api = Api(FAKE_ENV, transport=f, log=log)
    try: rc = cmd_put(api, "job-1", sp, None, True, False, log=log)
    except Refuse as e: rc = e.code; log(str(e))
    case("put --drop-missing refuses to drop a LIVE question without --allow-drop", rc == 3 and len(f.doc["questions"]) == 5 and any("would DROP 1 live" in l for l in quiet))
    f = FakeAdmin(server); quiet.clear(); api = Api(FAKE_ENV, transport=f, log=log); rc = cmd_put(api, "job-1", sp, None, True, True, log=log)
    case("put --drop-missing --allow-drop replaces the whole doc", rc == 0 and len(f.doc["questions"]) == 2)
    # 10. auth failure surfaces as exit 6
    f = FakeAdmin(doc); quiet.clear(); api = Api({**FAKE_ENV, "VIBHAGA_ADMIN_PASSWORD": "wrong"}, transport=f, log=log)
    try: run_publish(api, "job-1", staged, scope_ok, 0, None, None, ids_out, False, t77_ok, log=log); rc = 0
    except Refuse as e: rc = e.code
    case("a failed password grant is exit 6 and nothing is fetched", rc == 6 and len(f.calls) == 1)
    # 11. manifest from run 11's committed record — reconciles, and the sidecar equals the committed coverage json
    run11 = docs / "question-onboarding" / "runs" / "2026-09-07-run11-g8-nwp-2024"; out = T / "coverage"; quiet.clear()
    rc = cmd_manifest(run11, out, "2026-09-07", log=log)
    same = all(json.loads((out / f"2026-09-07-2024-nwp-g8-2nd-term-maths-paper-{s}-sinhala.json").read_text()) == json.loads((docs / "question-onboarding" / "coverage" / f"2026-09-07-2024-nwp-g8-2nd-term-maths-paper-{s}-sinhala.json").read_text()) for s in ("I", "II"))
    md = (out / "2026-09-07-2024-nwp-g8-2nd-term-maths-paper-II-sinhala.md").read_text()
    case("manifest: run 11 → 2 × (.md + .json), reconciled, sidecars equal the committed coverage json, 15 rows in II", rc == 0 and same and md.count("\n| ") - 2 == 15 + 8, f"rows={md.count(chr(10) + '| ')}")
    bad = json.loads(json.dumps(json.loads((run11 / "manifest.json").read_text()))); bad["sub_papers"][0]["source_questions"] = 21
    bd = T / "badrun"; bd.mkdir(); (bd / "manifest.json").write_text(dump(bad)); quiet.clear(); rc = cmd_manifest(bd, T / "cov2", "2026-09-08", log=log)
    case("manifest: a planted declared≠counted is reported and exits 1", rc == 1 and any("PROBLEMS" in l for l in quiet))
    n_ok = sum(1 for _, ok, _ in results if ok); print(f"self-test: {n_ok}/{len(results)} checks passed" + ("" if n_ok == len(results) else " — FAILED"))
    return 0 if n_ok == len(results) else 1


# ----------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    common = argparse.ArgumentParser(add_help=False); common.add_argument("--env", help="path to Vibhaga-Admin/.env.local"); common.add_argument("--cred-prefix", default="VIBHAGA_ADMIN")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("get", parents=[common]); g.add_argument("job"); g.add_argument("--out", required=True)
    p = sub.add_parser("put", parents=[common]); p.add_argument("job"); p.add_argument("--staged", required=True); p.add_argument("--paper-metadata"); p.add_argument("--drop-missing", action="store_true"); p.add_argument("--allow-drop", action="store_true")
    p.add_argument("--initialize-empty-proof", type=Path, metavar="PATH", help="initialize only the attested empty job using fresh independent SQL + R2 evidence JSON; not atomic: exclusive writer required, GET/PUT race remains")
    p.epilog = ("Proof is an operator attestation, not a trusted server claim. Required JSON fields (one job per file): "
                "checked_at (timezone-aware, age 0–300s; timestamp the oldest evidence read), job_id, paper_id, "
                "source_pdf_sha256 (match staged.paper), actor_id (fresh grant user), raw_status='uploaded', "
                "question_count=0, paper_rows=0, live_question_rows=0 (all content rows for this paper, including drafts), "
                "r2_bucket='qbank-blobs', r2_key='onboarding/<job_id>/questions.json', staged_object_absent=true, "
                "exclusive_writer_confirmed=true, created_at, updated_at (unchanged original DB timestamps), "
                "scope (complete grade/subject/medium or exam scope, matching staged.paper.paper_metadata). "
                "No extra fields. Independently refresh raw SQL and R2 absence evidence immediately before use; "
                "API normalizes legacy extracting statuses and ready:false alone does not prove R2 absence. "
                "Catalog membership remains enforced by the publish dry-run. Existing drafts require normal put WITHOUT this option. "
                "Never use with drop flags; never treat a failed write/echo check as permission to retry initialization blindly.")
    u = sub.add_parser("publish", parents=[common]); u.add_argument("job"); u.add_argument("--staged", required=True); u.add_argument("--scope", required=True); u.add_argument("--accept-signatures", type=int)
    u.add_argument("--ids", help="json array of question_ids (default: every question in --staged)"); u.add_argument("--sub", help="sub-paper key (I/II) — nests the record under it in --ids-out")
    u.add_argument("--ids-out", default="published-ids.json"); u.add_argument("--dry-run", action="store_true")
    m = sub.add_parser("manifest"); m.add_argument("run_dir"); m.add_argument("--out-dir"); m.add_argument("--date", default=dt.date.today().isoformat())
    a = ap.parse_args()
    if a.self_test: return self_test()
    if not a.cmd: ap.print_help(); return 2
    try:
        if a.cmd == "manifest":
            rd = Path(a.run_dir); return cmd_manifest(rd, Path(a.out_dir) if a.out_dir else rd / "coverage", a.date)
        env_path = Path(a.env) if a.env else (Path(os.environ["VIBHAGA_ADMIN_ENV"]) if os.environ.get("VIBHAGA_ADMIN_ENV") else None) \
            or find_up("Vibhaga-Admin/.env.local", HERE) or find_up("Vibhaga-Admin/.env.local", Path.cwd())
        if not env_path or not env_path.exists(): raise Refuse(f"admin env file not found: {env_path or 'Vibhaga-Admin/.env.local (walked up from ' + str(HERE) + ')'} (pass --env or VIBHAGA_ADMIN_ENV)", 2)
        api = Api(read_env(env_path), cred_prefix=a.cred_prefix)
        try:
            if a.cmd == "get": return cmd_get(api, a.job, Path(a.out))
            if a.cmd == "put": return cmd_put(api, a.job, Path(a.staged), parse_kv(a.paper_metadata) if a.paper_metadata else None, a.drop_missing, a.allow_drop, initialize_empty_proof=a.initialize_empty_proof)
            if a.cmd == "publish":
                return run_publish(api, a.job, Path(a.staged), parse_kv(a.scope), a.accept_signatures, Path(a.ids) if a.ids else None, a.sub, Path(a.ids_out), a.dry_run, t77_subprocess(env_path))
        finally:
            finish(api)
    except Refuse as e:
        print(e); return e.code
    return 2


if __name__ == "__main__":
    sys.exit(main())
