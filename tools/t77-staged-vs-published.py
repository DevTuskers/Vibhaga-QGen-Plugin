#!/usr/bin/env python3
"""T77 — the staged doc against the PUBLISHED rows, field by field, by direct SELECT (S10 §9 / S11).

    cd Vibhaga-DB && set -a && . ./.env && set +a && cd ..
    python3 Vibhaga-Docs/.devin/skills/_maths-onboarding/t77-staged-vs-published.py staged.json --ids ids.json
    python3 …/t77-staged-vs-published.py staged.json --ids '["<uuid>", …]'
    python3 …/t77-staged-vs-published.py questions-I.json --ids published-ids.json --sub I   # publish.py's nested id map

For every question in the publish set it compares, against `questions` / `sub_questions` / `answers` /
`sub_answers`: the stem (both languages), `question_number`, `needs_human_review`, every part's label /
text / text_sinhala / sort_order / parent, every answer's approach / final_answer_latex, and `diagram_dsl`
at all four levels (JSON equality). Prints one line per mismatch and a totals line; exit 1 on any mismatch.
Every previous run did this ad hoc (TRAPS T77: a migration that wrote the rows and not the staged doc
reverted itself on the next publish; the runs ledger quotes "N comparisons, 0 mismatches" from a script
that was never committed). Needs `DATABASE_URL` in the environment (read-only queries only) and psycopg
OR the `psql` binary — it uses `psql -At` with JSON output so no driver is required.
"""
import json, os, re, subprocess, sys, urllib.parse

def psql_json(sql: str):
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("t77: DATABASE_URL not set (cd Vibhaga-DB && set -a && . ./.env && set +a)")
    # never put the URL on psql's argv — the password would show in `ps`; split it into -h/-p/-U/-d + PGPASSWORD/PGSSLMODE
    env = dict(os.environ)
    u = urllib.parse.urlsplit(url)
    if u.password:
        env["PGPASSWORD"] = u.password
    args = ["psql", "-At", "-v", "ON_ERROR_STOP=1", "-c", sql]
    if u.hostname: args += ["-h", u.hostname]
    if u.port: args += ["-p", str(u.port)]
    if u.username: args += ["-U", u.username]
    if u.path and u.path != "/": args += ["-d", u.path.lstrip("/")]
    for k, v in urllib.parse.parse_qsl(u.query):
        if k == "sslmode": env["PGSSLMODE"] = v
    out = subprocess.run(args, capture_output=True, text=True, check=True, env=env).stdout.strip()
    return json.loads(out) if out else []

def norm(o):
    """JSONB stores 74.0 as 74 — compare numbers by value, not by spelling."""
    if isinstance(o, float) and o == int(o): return int(o)
    if isinstance(o, dict): return {k: norm(v) for k, v in o.items()}
    if isinstance(o, list): return [norm(v) for v in o]
    return o

def main():
    import argparse
    ap = argparse.ArgumentParser(description="T77 — staged doc vs the live rows, field by field (numbers by value).")
    ap.add_argument("staged", help="questions-<sub>.json")
    ap.add_argument("--ids", required=True, help="JSON array of question_ids, a file holding one, or publish.py's published-ids.json (with --sub)")
    ap.add_argument("--sub", help="sub-paper key when --ids is publish.py's nested published-ids.json")
    a = ap.parse_args()
    staged = json.load(open(a.staged))
    ids_arg = a.ids
    ids = json.load(open(ids_arg)) if os.path.exists(ids_arg) else json.loads(ids_arg)
    sub = a.sub
    if isinstance(ids, dict):  # publish.py's published-ids.json: {question_ids: [...]} or {I: {question_ids: [...]}, II: {...}}
        if "question_ids" in ids:
            ids = ids["question_ids"]
        elif sub and sub in ids:
            ids = ids[sub]["question_ids"]
        elif len(ids) == 1:
            ids = next(iter(ids.values()))["question_ids"]
        else:
            sys.exit(f"t77: --ids is nested by sub-paper {sorted(ids)} — pass --sub I/--sub II")
    bad_ids = [i for i in ids if not re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", str(i))]
    if bad_ids:
        sys.exit(f"t77: --ids must be UUIDs (they are interpolated into SQL): {bad_ids[:3]}")
    idlist = ",".join(f"'{i}'" for i in ids)
    rows = psql_json(f"""
      SELECT json_agg(json_build_object(
        'question_id', q.question_id, 'question_number', q.question_number, 'question_text', q.question_text,
        'question_text_sinhala', q.question_text_sinhala, 'needs_human_review', q.needs_human_review, 'diagram_dsl', q.diagram_dsl,
        'answers', (SELECT json_agg(json_build_object('answer_id', a.answer_id, 'approach', a.approach, 'final_answer_latex', a.final_answer_latex, 'diagram_dsl', a.diagram_dsl)) FROM answers a WHERE a.question_id = q.question_id),
        'parts', (SELECT json_agg(json_build_object('sub_question_id', s.sub_question_id, 'label', s.label, 'text', s.text, 'text_sinhala', s.text_sinhala,
                    'sort_order', s.sort_order, 'parent', s.parent_sub_question_id, 'diagram_dsl', s.diagram_dsl,
                    'answers', (SELECT json_agg(json_build_object('sub_answer_id', sa.sub_answer_id, 'approach', sa.approach, 'final_answer_latex', sa.final_answer_latex, 'diagram_dsl', sa.diagram_dsl)) FROM sub_answers sa WHERE sa.sub_question_id = s.sub_question_id)))
                  FROM sub_questions s WHERE s.question_id = q.question_id)))
      FROM questions q WHERE q.question_id::text IN ({idlist});""")
    live = {r["question_id"]: r for r in rows}
    n = 0; bad = []
    def cmp(path, a, b):
        nonlocal n
        n += 1
        if isinstance(a, dict) or isinstance(b, dict):
            if json.dumps(norm(a), sort_keys=True) != json.dumps(norm(b), sort_keys=True): bad.append(f"{path}: staged vs live differ (object)")
        elif (a or "") != (b or ""): bad.append(f"{path}: staged {str(a)[:60]!r} != live {str(b)[:60]!r}")
    for q in staged["questions"]:
        if q["question_id"] not in ids: continue
        L = live.get(q["question_id"])
        if not L: bad.append(f"Q{q['question_number']} {q['question_id']}: NOT PUBLISHED"); continue
        p = f"Q{q['question_number']}"
        cmp(p + ".question_number", q["question_number"], L["question_number"])
        cmp(p + ".question_text", q.get("question_text"), L["question_text"])
        cmp(p + ".question_text_sinhala", q.get("question_text_sinhala"), L["question_text_sinhala"])
        cmp(p + ".needs_human_review", bool((q.get("ingestion_metadata") or {}).get("needs_human_review")), L["needs_human_review"])
        cmp(p + ".diagram_dsl", q.get("diagram_dsl"), L["diagram_dsl"])
        la = {a["answer_id"]: a for a in (L["answers"] or [])}
        for a in q.get("answers") or []:
            x = la.pop(a["answer_id"], None)
            if not x: bad.append(f"{p}.answers[{a['answer_id'][:8]}]: missing live"); continue
            cmp(f"{p}.a[{a['answer_id'][:8]}].approach", a.get("approach"), x["approach"])
            cmp(f"{p}.a[{a['answer_id'][:8]}].final", a.get("final_answer_latex"), x["final_answer_latex"])
            cmp(f"{p}.a[{a['answer_id'][:8]}].diagram_dsl", a.get("diagram_dsl"), x["diagram_dsl"])
        for k in la: bad.append(f"{p}.answers[{k[:8]}]: live row not in staged")
        lp = {s["sub_question_id"]: s for s in (L["parts"] or [])}
        def parts(lst, parent, depth):
            for i, s in enumerate(lst or []):
                x = lp.pop(s["sub_question_id"], None); pp = f"{p}.{s.get('label')}"
                if not x: bad.append(f"{pp}: part missing live"); continue
                cmp(pp + ".label", s.get("label"), x["label"]); cmp(pp + ".text", s.get("text"), x["text"])
                cmp(pp + ".text_sinhala", s.get("text_sinhala"), x["text_sinhala"]); cmp(pp + ".sort_order", i, x["sort_order"])
                cmp(pp + ".parent", parent, x["parent"]); cmp(pp + ".diagram_dsl", s.get("diagram_dsl"), x["diagram_dsl"])
                lsa = {a["sub_answer_id"]: a for a in (x["answers"] or [])}
                # a part's staged sub-answers live in BOTH shapes publish.ts collectSubAnswers
                # accepts: the singular `sub_answer` object (what build-staged emits) and the
                # `answers` list (canonical). Reading only the list reported every published
                # sub_answer as "live row not in staged" (T-QG-4).
                staged_sa = ([s["sub_answer"]] if isinstance(s.get("sub_answer"), dict) else []) \
                    + [a for a in s.get("answers") or [] if isinstance(a, dict)]
                for a in staged_sa:
                    y = lsa.pop(a["sub_answer_id"], None)
                    if not y: bad.append(f"{pp}.sa[{a['sub_answer_id'][:8]}]: missing live"); continue
                    cmp(f"{pp}.sa.approach", a.get("approach"), y["approach"]); cmp(f"{pp}.sa.final", a.get("final_answer_latex"), y["final_answer_latex"])
                    cmp(f"{pp}.sa.diagram_dsl", a.get("diagram_dsl"), y["diagram_dsl"])
                for k in lsa: bad.append(f"{pp}.sa[{k[:8]}]: live row not in staged")
                parts(s.get("sub_questions"), s["sub_question_id"], depth + 1)
        parts(q.get("sub_questions"), None, 1)
        for k in lp: bad.append(f"{p}: live part {k[:8]} not in staged")
    for b in bad: print("  MISMATCH", b)
    print(f"t77: {len(ids)} question(s) · {n} comparisons · {len(bad)} mismatch(es)")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
