import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
SPEC = importlib.util.spec_from_file_location("playground_publish", TOOLS / "playground-publish.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)

SID = "33333333-3333-4333-8333-333333333333"
SID2 = "44444444-4444-4444-8444-444444444444"
ID1 = "11111111-1111-4111-8111-111111111111"
ID2 = "22222222-2222-4222-8222-222222222222"
ID3 = "55555555-5555-4555-8555-555555555555"
ID4 = "66666666-6666-4666-8666-666666666666"
LESSON = "77777777-7777-4777-8777-777777777777"
ACTOR = tool.FakePlayground.ACTOR
STAMP = tool.FakePlayground.STAMP
SCOPE = {"grade": 6, "subject": "Mathematics", "medium": "sinhala"}
SCOPE_KV = "grade=6,subject=Mathematics,medium=sinhala"
FAKE_ENV = dict(tool._pub.FAKE_ENV)  # password "pw" — what FakePlayground's grant accepts
ORDER = [ID2, ID3, ID1]             # sort_order 0,1,2 — deliberately not the fixture's list order


def question(qid, n, so, flag=True, **kw):
    return {"question_id": qid, "question_number": n, "sort_order": so,
            "question_text": f"Question {n} text", "question_text_sinhala": None,
            "answers": [{"answer_id": f"aaaaaaaa-0000-4000-8000-{n:012d}", "approach": "a", "final_answer_latex": "$1$"}],
            "ingestion_metadata": {"needs_human_review": flag}, **kw}


def questions3(flag=True):
    return [question(ID1, 1, 2, flag), question(ID2, 2, 0, flag), question(ID3, 3, 1, flag)]


def session_row(sid=SID, **kw):
    return {"id": sid, "name": "test session", "grade": 6, "exam": None, "subject": "Mathematics",
            "medium": "sinhala", "lesson_ids": [LESSON], "r2_key": f"playground/{sid}/questions.json",
            "status": "active", "question_count": 3, "created_by_admin_id": ACTOR,
            "created_at": STAMP, "updated_at": STAMP, **kw}


def good_rows(sid, ids):
    return [{"question_id": i, "status": "published", "needs_human_review": True,
             "source_batch_id": sid, "source_paper_id": None, "signed_answers": 0, "signed_sub_answers": 0}
            for i in ids]


def summary(qid, n, **kw):
    return {"question_id": qid, "question_number": n, "status": "published", "needs_human_review": True,
            "source_paper_id": None, "source_batch_id": SID, "lesson_ids": [], "grade": 6, "exam": None,
            "subject": "Mathematics", "medium": "sinhala", "stem_excerpt": f"Q{n} stem excerpt",
            "has_diagram": False, "created_at": STAMP, **kw}


class PlaygroundTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.logs = []
        self.staged_path = self.root / "staged.json"
        self.staged_path.write_text(json.dumps({"questions": questions3()}))
        self.ids_path = self.root / "ids.json"
        self.ids_path.write_text(json.dumps([ID1, ID2, ID3]))
        self.ledger_path = self.root / "ledger.json"

    # ---------- helpers ----------
    def fake(self, qs=None, sess=None, **kw):
        return tool.FakePlayground({SID: sess or session_row()}, {SID: qs if qs is not None else questions3()}, **kw)

    def api(self, fake):
        return tool.PlaygroundApi(FAKE_ENV, transport=fake, log=self.logs.append)

    def call(self, fn, *args):
        self.logs.clear()
        api = self.api(self.fake_obj)
        try:
            return fn(api, *args, log=self.logs.append)
        except tool.Refuse as e:
            self.logs.append(str(e))
            return e.code
        finally:
            tool.finish(api, log=self.logs.append)

    def run_pub(self, fake=None, accept=0, dry=False, scope=SCOPE, t77=None, sql=None,
                staged=None, ids=None, ledger=None, sid=SID):
        if fake is not None:
            self.fake_obj = fake
        elif getattr(self, "fake_obj", None) is None:
            self.fake_obj = self.fake()
        staged = staged or self.staged_path
        ids = ids or self.ids_path
        ledger = ledger or self.ledger_path
        t77 = t77 if t77 is not None else lambda *a: 0
        sql = sql if sql is not None else (lambda s: good_rows(SID, ORDER))
        return self.call(tool.run_publish, sid, staged, scope, ids, ledger, accept, dry, t77, sql)

    def new_fake(self, **kw):
        self.fake_obj = self.fake(**kw)
        return self.fake_obj

    def admin_writes(self, fake):
        return [c for c in fake.calls if c[0] in ("PUT", "POST") and c[1].startswith("/v1/admin")]

    # ---------- 1. scope mismatch refuses before any publish ----------
    def test_scope_mismatch_refuses_before_publish(self):
        fake = self.new_fake()
        rc = self.run_pub(scope={"grade": 7, "subject": "Mathematics", "medium": "sinhala"})
        self.assertEqual(rc, 3)
        self.assertFalse(fake.publishes)
        self.assertFalse(any(m == "POST" and p.endswith("/publish") for m, p in fake.calls))
        self.assertTrue(any("--scope" in l for l in self.logs))

    # ---------- 2. --ids-file is argparse-required and validated ----------
    def test_ids_file_required_and_validated(self):
        argv = ["playground-publish.py", "publish", SID, "--staged", str(self.staged_path),
                "--scope", SCOPE_KV, "--ledger", str(self.ledger_path)]
        with mock.patch("sys.argv", argv), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                tool.main()
        self.assertEqual(caught.exception.code, 2)
        for content in ("[]", json.dumps(["not-a-uuid"]), json.dumps([ID1, ID1]), "not json"):
            with self.subTest(content=content):
                self.ids_path.write_text(content)
                fake = self.new_fake()
                self.assertEqual(self.run_pub(), 3)
                self.assertFalse(fake.publishes)
        self.ids_path.write_text(json.dumps([ID1, ID2, ID3]))

    # ---------- 3. the signature guard ----------
    def test_signature_guard(self):
        for risk, accept, expected in [(2, None, 4), (2, 1, 4), (0, None, 4)]:
            with self.subTest(risk=risk, accept=accept):
                fake = self.new_fake(risk=risk)
                self.assertEqual(self.run_pub(accept=accept), expected)
                self.assertFalse(fake.publishes)
        fake = self.new_fake(risk=2)
        rc = self.run_pub(accept=2, dry=True)
        self.assertEqual(rc, 0)
        self.assertFalse(fake.publishes)
        self.assertTrue(any("nothing published" in l for l in self.logs))

    # ---------- 4. an archived session refuses every writing verb ----------
    def test_archived_session_refuses_writes(self):
        self.assertEqual(self.run_pub(fake=self.new_fake(archived={SID})), 3)
        self.assertFalse(self.admin_writes(self.fake_obj))
        self.assertTrue(any("batch_archived" in l for l in self.logs))
        self.assertEqual(self.call(tool.cmd_doc_put, SID, self.staged_path, self.ledger_path, False, False), 3)
        self.assertFalse(self.admin_writes(self.fake_obj))
        self.assertEqual(self.call(tool.cmd_unpublish, SID, self.ids_path, self.ledger_path), 3)
        self.assertFalse(self.admin_writes(self.fake_obj))
        self.assertEqual(self.call(tool.cmd_flag_review, SID, self.ids_path, self.ledger_path), 3)
        self.assertFalse(self.admin_writes(self.fake_obj))

    # ---------- 5. staged file != server doc → refused (T77 pre-check) ----------
    def test_stale_doc_refuses(self):
        qs = questions3(); qs[1]["question_text"] += " (edited on the server)"
        fake = self.new_fake(qs=qs)
        self.assertEqual(self.run_pub(), 3)
        self.assertFalse(fake.publishes)
        self.assertFalse(any(p.endswith("/publish") for _, p in fake.calls))
        self.assertTrue(any("doc put" in l for l in self.logs))

    # ---------- 6. unflagged chosen / id not in the doc ----------
    def test_unflagged_and_missing_id_refuse(self):
        qs = questions3(flag=False)                       # staged file == server doc, so the flag check fires
        self.staged_path.write_text(json.dumps({"questions": qs}))
        fake = self.new_fake(qs=qs)
        self.assertEqual(self.run_pub(), 3)
        self.assertFalse(fake.publishes)
        self.assertTrue(any("unflagged" in l for l in self.logs))
        self.staged_path.write_text(json.dumps({"questions": questions3()}))
        self.ids_path.write_text(json.dumps([ID1, ID4]))
        fake = self.new_fake()
        self.assertEqual(self.run_pub(), 3)
        self.assertFalse(fake.publishes)
        self.assertTrue(any("not in the session" in l for l in self.logs))
        self.ids_path.write_text(json.dumps([ID1, ID2, ID3]))

    # ---------- 7. server-side validate gates the publish ----------
    def test_validate_gates_chosen_only(self):
        fake = self.new_fake(validate_errors={ID2: ["sub_questions[0].text is blank"]})
        self.assertEqual(self.run_pub(), 3)
        self.assertFalse(fake.publishes)
        qs = questions3() + [question(ID4, 4, 3)]
        fake = self.new_fake(qs=qs, validate_errors={ID4: ["unrelated error"]})
        self.assertEqual(self.run_pub(), 0)
        self.assertEqual(fake.publishes, [[i] for i in ORDER])

    # ---------- 8. the ledger holds the ids BEFORE the first publish request (T9) ----------
    def test_ledger_before_first_publish(self):
        fake = self.new_fake()
        seen = {}
        def check(_n):
            led = json.loads(self.ledger_path.read_text())
            seen["ids"] = led["sessions"][SID]["published"]["question_ids"]
        fake.on_publish = check
        self.assertEqual(self.run_pub(), 0)
        self.assertEqual(seen["ids"], ORDER)

    # ---------- 9. a clean run of 3 ----------
    def test_clean_run_order_writeback_readbacks_finish(self):
        t77_calls = []
        fake = self.new_fake(flake_first=True)
        rc = self.run_pub(t77=lambda *a: t77_calls.append(a) or 0)
        self.assertEqual(rc, 0)
        self.assertEqual(fake.publishes, [[ID2], [ID3], [ID1]])           # sort_order order, one id per request
        self.assertTrue(any("retrying once" in l for l in self.logs))      # the 000 retried once
        self.assertEqual(len(fake.put_bodies), 3)                          # a write-back PUT after EACH publish
        last = {q["question_id"]: q for q in fake.put_bodies[-1]}
        for i in ORDER:
            self.assertIs(last[i]["published"], True)
            self.assertIs((last[i]["ingestion_metadata"] or {}).get("needs_human_review"), True)
        self.assertEqual(fake.grants, 4)                                    # get, dry-run, loop, readback
        self.assertEqual(fake.logouts, 1)
        self.assertEqual(fake.calls[-1], ("POST", "/auth/v1/logout?scope=global"))
        self.assertEqual(sum(1 for l in self.logs if f"FROM auth.sessions WHERE user_id = '{ACTOR}'" in l
                             or f"FROM auth.refresh_tokens WHERE user_id = '{ACTOR}'" in l), 2)
        secret_words = {"pw", "tok1", "tok2", "tok3", "tok4", FAKE_ENV["VIBHAGA_ADMIN_EMAIL"]}
        self.assertFalse(secret_words & {w for l in self.logs for w in l.replace("'", " ").replace('"', " ").split()})
        self.assertEqual(len(t77_calls), 1)
        led = json.loads(self.ledger_path.read_text())
        self.assertEqual(led["sessions"][SID]["published"]["question_ids"], ORDER)
        self.assertEqual(led["sessions"][SID]["status"], "active")

    # ---------- 10. a server that does NOT mirror the flag → read-back 1 fails ----------
    def test_writeback_missing_fails_readback(self):
        self.assertEqual(self.run_pub(fake=self.new_fake(put_drops_published=True)), 1)
        self.assertTrue(any("MISMATCH doc" in l for l in self.logs))

    # ---------- 11. a 500 mid-loop stops the run; the ledger stands ----------
    def test_publish_500_stops_mid_loop(self):
        fake = self.new_fake(fail_publish_at=2)
        self.assertEqual(self.run_pub(), 5)
        self.assertEqual(fake.publishes, [[ID2], [ID3]])
        self.assertEqual(len(fake.put_bodies), 1)                          # question 1's write-back landed
        self.assertTrue(any("STOPPED after 1/3" in l for l in self.logs))
        led = json.loads(self.ledger_path.read_text())
        self.assertEqual(led["sessions"][SID]["published"]["question_ids"], ORDER)

    # ---------- 12. the provenance read-back ----------
    def test_provenance_failures_and_signature_warn(self):
        base = good_rows(SID, ORDER)
        cases = {
            "papered": [{**r, "source_paper_id": ID4} for r in base],
            "other_batch": [{**r, "source_batch_id": SID2} for r in base],
            "unflagged": [{**r, "needs_human_review": False} for r in base],
            "draft": [{**r, "status": "draft"} for r in base],
            "missing": base[:2],
            "dup": base + [base[0]],
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.run_pub(fake=self.new_fake(), sql=lambda s, r=rows: r), 1)
        signed = [dict(r, signed_answers=2) if r["question_id"] == ID2 else r for r in base]
        self.assertEqual(self.run_pub(fake=self.new_fake(), sql=lambda s: signed), 0)
        self.assertTrue(any("WARN human signature present (OD-D preserved)" in l for l in self.logs))

    # ---------- 13. clear-review / unflag-review: refused, zero network, no env read ----------
    def test_clear_and_unflag_review_refused_offline(self):
        for verb in ("clear-review", "unflag-review"):
            with self.subTest(verb=verb):
                argv = ["playground-publish.py", verb, SID, "--ids-file", str(self.ids_path), "--env", "/nonexistent"]
                with mock.patch("sys.argv", argv), mock.patch.object(tool, "PlaygroundApi") as apimock, \
                        contextlib.redirect_stdout(io.StringIO()) as out:
                    rc = tool.main()
                self.assertEqual(rc, 3)
                apimock.assert_not_called()
                self.assertIn("human act", out.getvalue())
                self.assertIn("/generate", out.getvalue())

    # ---------- 14. doc put's staged-doc guards ----------
    def test_doc_put_refusals(self):
        qs = questions3(); qs[0]["ingestion_metadata"] = {"needs_human_review": False}
        self.staged_path.write_text(json.dumps({"questions": qs}))
        fake = self.new_fake()
        self.assertEqual(self.call(tool.cmd_doc_put, SID, self.staged_path, self.ledger_path, False, False), 3)
        self.assertFalse(fake.put_bodies)
        qs = questions3(); qs[1]["exam"] = "ol"
        self.staged_path.write_text(json.dumps({"questions": qs}))
        fake = self.new_fake()
        self.assertEqual(self.call(tool.cmd_doc_put, SID, self.staged_path, self.ledger_path, False, False), 3)
        self.assertFalse(fake.put_bodies)
        self.staged_path.write_text(json.dumps({"questions": questions3()[:2]}))
        live = questions3(); live[2]["published"] = True; live[2]["published_at"] = STAMP
        fake = self.new_fake(qs=live)
        self.assertEqual(self.call(tool.cmd_doc_put, SID, self.staged_path, self.ledger_path, True, False), 3)
        self.assertFalse(fake.put_bodies)
        self.staged_path.write_text(json.dumps({"questions": questions3()}))

    # ---------- 15. unpublish not_in_session / flag-review stale doc ----------
    def test_unpublish_not_in_session_and_stale_flag(self):
        self.ids_path.write_text(json.dumps([ID1, ID4]))
        fake = self.new_fake()
        self.assertEqual(self.call(tool.cmd_unpublish, SID, self.ids_path, self.ledger_path), 3)
        self.assertTrue(any(ID4 in l and "not_in_session" in l for l in self.logs))
        led = json.loads(self.ledger_path.read_text())
        self.assertEqual(led["sessions"][SID]["unpublished"], [ID1])
        self.ids_path.write_text(json.dumps([ID1]))
        fake = self.new_fake(flag_stale_doc=True)
        self.assertEqual(self.call(tool.cmd_flag_review, SID, self.ids_path, self.ledger_path), 1)
        self.assertTrue(any("stale" in l for l in self.logs))
        self.ids_path.write_text(json.dumps([ID1, ID2, ID3]))

    # ---------- 16. session create records the ledger; grade+exam refuses before any call ----------
    def test_session_create_ledger_and_scope_rules(self):
        fake = self.new_fake()
        self.assertEqual(self.call(tool.cmd_session_create, "run 1", SCOPE_KV, LESSON, self.ledger_path), 0)
        new_sid = fake.created and f"00000000-0000-4000-8000-{fake.created:012d}"
        led = json.loads(self.ledger_path.read_text())
        ent = led["sessions"][new_sid]
        self.assertEqual(ent["name"], "run 1")
        self.assertEqual(ent["scope"], {"grade": 6, "subject": "Mathematics", "medium": "sinhala", "exam": None})
        self.assertEqual(ent["lesson_ids"], [LESSON])
        self.assertEqual(ent["status"], "active")
        self.assertIn(new_sid, self.logs)
        for bad in ("grade=6,exam=ol,medium=sinhala", "medium=klingon,grade=6", "grade=6"):
            with self.subTest(scope=bad):
                fake = self.new_fake()
                self.assertEqual(self.call(tool.cmd_session_create, "x", bad, "", self.ledger_path), 2)
                self.assertFalse(fake.calls)          # refused BEFORE the password grant

    # ---------- 17. a bad session id exits 2 with zero calls ----------
    def test_bad_session_id_zero_calls(self):
        env_file = self.root / "env.local"
        env_file.write_text("\n".join(f"{k}={v}" for k, v in FAKE_ENV.items()))
        for argv in (["x", "session", "show", "not-a-uuid", "--env", str(env_file)],
                     ["x", "doc", "get", "bad", "--out", str(self.root / "o.json"), "--env", str(env_file)],
                     ["x", "publish", "!!", "--staged", "s", "--scope", "g", "--ids-file", "i", "--ledger", "l", "--env", str(env_file)]):
            with self.subTest(argv=argv):
                with mock.patch("sys.argv", argv), mock.patch.object(tool, "PlaygroundApi") as apimock, \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(tool.main(), 2)
                apimock.assert_not_called()

    # ---------- F1: upper-cased ids normalise against the lower-case server ----------
    def test_uppercase_ids_normalise(self):
        self.ids_path.write_text(json.dumps([i.upper() for i in [ID1, ID2, ID3]]))
        fake = self.new_fake()                                          # doc + session ids are lower-case
        rc = self.run_pub(sid=SID.upper(), sql=lambda s: good_rows(SID, ORDER))  # Postgres renders lower-case
        self.assertEqual(rc, 0)
        self.assertEqual(fake.publishes, [[i] for i in ORDER])
        led = json.loads(self.ledger_path.read_text())
        self.assertEqual(led["sessions"][SID]["published"]["question_ids"], ORDER)
        self.ids_path.write_text(json.dumps([ID1, ID2, ID3]))

    # ---------- 18. the ledger merge never drops another session's key ----------
    def test_ledger_merge_keeps_other_sessions(self):
        other = {"name": "other", "scope": SCOPE, "status": "active", "published": {"question_ids": [ID4], "written_at": STAMP}}
        self.ledger_path.write_text(json.dumps({"sessions": {SID2: other, "deadbeef-0000-4000-8000-000000000000": {"status": "archived", "custom": 1}}}))
        self.assertEqual(self.run_pub(fake=self.new_fake()), 0)
        led = json.loads(self.ledger_path.read_text())
        self.assertEqual(led["sessions"][SID2], other)
        self.assertEqual(led["sessions"]["deadbeef-0000-4000-8000-000000000000"], {"status": "archived", "custom": 1})
        self.assertIn(SID, led["sessions"])

    # ---------- the three read-only additions ----------
    def test_lessons_filter(self):
        lessons = [
            {"lesson_id": LESSON, "grade": 6, "exam": None, "subject": "Mathematics", "name": "Fractions", "name_sinhala": "භාග", "sort_order": 2},
            {"lesson_id": ID4, "grade": 6, "exam": None, "subject": "Mathematics", "name": "Numbers", "name_sinhala": None, "sort_order": 1},
            {"lesson_id": ID1, "grade": None, "exam": "ol", "subject": "Mathematics", "name": "Algebra", "name_sinhala": None, "sort_order": 3},
        ]
        self.fake_obj = tool.FakePlayground({}, {}, lessons=lessons)
        self.assertEqual(self.call(tool.cmd_lessons, 6, None, None), 0)
        lines = [l for l in self.logs if "|" in l]
        self.assertEqual(len(lines), 2)
        self.assertIn("Numbers", lines[0]) and self.assertIn("Fractions", lines[1])   # sort_order order
        self.assertEqual(self.call(tool.cmd_lessons, 6, "ol", None), 2)              # grade+exam → 2
        bad = [dict(lessons[0], sort_order="x")]
        self.fake_obj = tool.FakePlayground({}, {}, lessons=bad)
        self.assertEqual(self.call(tool.cmd_lessons, None, None, None), 5)

    def test_questions_list_params_and_cursor(self):
        corpus = [summary(ID1, 1), summary(ID2, 2), summary(ID3, 3)]
        self.fake_obj = tool.FakePlayground({}, {}, corpus=corpus, page_size=2)
        params = {"status": "published", "needs_human_review": "true", "grade": 6, "subject": "Mathematics",
                  "medium": "sinhala", "lesson_id": LESSON, "batch_id": SID, "q": "fraction", "limit": 2}
        out = self.root / "q.json"
        self.assertEqual(self.call(tool.cmd_questions_list, params, True, out), 0)
        list_calls = [p for m, p in self.fake_obj.calls if m == "GET" and "playground/questions?" in p]
        self.assertEqual(len(list_calls), 2)                                          # --all followed the cursor
        self.assertIn("cursor=2", list_calls[1])
        for frag in ("status=published", "needs_human_review=true", "grade=6", "subject=Mathematics",
                     "medium=sinhala", f"lesson_id={LESSON}", f"batch_id={SID}", "q=fraction", "limit=2"):
            self.assertIn(frag, list_calls[0])
        self.assertEqual(len(json.loads(out.read_text())), 3)
        self.assertTrue(any("flagged" in l and "batch" in l and "Q1" in l for l in self.logs))
        self.assertEqual(self.call(tool.cmd_questions_list, {"grade": 6, "exam": "ol"}, False, None), 2)
        self.assertEqual(self.call(tool.cmd_questions_list, {"batch_id": "nope"}, False, None), 2)

    def test_question_show(self):
        detail = {"question": {"question_id": ID1, "question_number": 1}, "sub_questions": [], "sub_answers": [], "answers": []}
        self.fake_obj = tool.FakePlayground({}, {}, question_detail=detail)
        self.assertEqual(self.call(tool.cmd_question_show, ID1, None), 0)
        self.assertIn(ID1, "".join(self.logs))
        out = self.root / "one.json"
        self.assertEqual(self.call(tool.cmd_question_show, ID1, out), 0)
        self.assertEqual(json.loads(out.read_text()), detail)
        self.assertTrue(any(p.endswith(f"/playground/questions/{ID1}") for _, p in self.fake_obj.calls))

    # ---------- supporting surfaces used by the flows above ----------
    def test_session_show_list_archive(self):
        fake = self.new_fake()
        self.assertEqual(self.call(tool.cmd_session_show, SID), 0)
        self.assertIn(SID, "".join(self.logs))
        self.assertEqual(self.call(tool.cmd_session_list, "active", 10), 0)
        self.assertIn(SID, "".join(self.logs))
        self.assertEqual(self.call(tool.cmd_session_archive, SID, self.ledger_path), 0)
        self.assertEqual(fake.sessions[SID]["status"], "archived")
        self.assertEqual(json.loads(self.ledger_path.read_text())["sessions"][SID]["status"], "archived")

    def test_doc_get_and_put_happy_path(self):
        fake = self.new_fake()
        out = self.root / "doc.json"
        self.assertEqual(self.call(tool.cmd_doc_get, SID, out), 0)
        got = json.loads(out.read_text())
        self.assertEqual(set(got), {"session", "questions", "stats"})                # ready dropped
        self.assertEqual(len(got["questions"]), 3)
        qs = questions3() + [question(ID4, 4, 3)]
        self.staged_path.write_text(json.dumps(qs))                                  # a bare list also loads
        self.assertEqual(self.call(tool.cmd_doc_put, SID, self.staged_path, self.ledger_path, False, False), 0)
        self.assertEqual(len(fake.docs[SID]), 4)

    def test_validate_subcommand(self):
        self.fake_obj = self.new_fake(validate_errors={ID1: ["bad label"]}, validate_warnings={ID2: ["no a11y description"]})
        self.assertEqual(self.call(tool.cmd_validate, SID, self.staged_path), 3)
        self.assertTrue(any("Q1" in l for l in self.logs))
        self.assertTrue(any("error: bad label" in l for l in self.logs))
        self.assertTrue(any("warn: no a11y description" in l for l in self.logs))
        self.fake_obj = self.new_fake()
        self.assertEqual(self.call(tool.cmd_validate, SID, self.staged_path), 0)

    def test_doc_put_archived_before_guard_order(self):
        # archived is checked on the GET session even when the staged file itself is clean
        fake = self.new_fake(archived={SID})
        self.assertEqual(self.call(tool.cmd_doc_put, SID, self.staged_path, self.ledger_path, False, False), 3)
        self.assertFalse(fake.put_bodies)


if __name__ == "__main__":
    unittest.main()
