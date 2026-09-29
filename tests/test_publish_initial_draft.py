import contextlib
import copy
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import publish as tool


JOB = "99999999-9999-4999-8999-999999999999"
PAPER = "22222222-2222-4222-8222-222222222222"
ACTOR = "11111111-2222-4333-8444-555555555555"
SCOPE = {"grade": 8, "subject": "Mathematics", "medium": "sinhala"}
STAMP = "2026-09-09T04:51:00Z"


def fixtures():
    staged = {"paper": {"paper_id": PAPER, "source_pdf_sha256": "a" * 64,
                        "paper_metadata": dict(SCOPE)},
              "questions": [{"question_id": tool.UUID0, "question_number": 1,
                             "question_text": "First draft", "sort_order": 0,
                             "ingestion_metadata": {"needs_human_review": True}}]}
    proof = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
             "job_id": JOB, "paper_id": PAPER, "source_pdf_sha256": "a" * 64,
             "actor_id": ACTOR, "raw_status": "uploaded", "question_count": 0,
             "paper_rows": 0, "live_question_rows": 0, "r2_bucket": "qbank-blobs",
             "r2_key": f"onboarding/{JOB}/questions.json", "staged_object_absent": True,
             "exclusive_writer_confirmed": True, "created_at": STAMP, "updated_at": STAMP,
             "scope": dict(SCOPE)}
    job = {"id": JOB, "status": "uploaded", "paper_id": PAPER, "filename": "paper-I.pdf",
           "question_count": 0, "error": None, "created_at": STAMP, "updated_at": STAMP}
    return staged, proof, job


class InitialTransport(tool.FakeAdmin):
    def __init__(self, staged, job):
        super().__init__({"paper": staged["paper"], "questions": [], "stats": {"questions": 0, "flagged": 0}})
        self.job = job
        self.initial = (200, {"ready": False, "questions": []})
        self.job_status = 200
        self.put_bodies = []
        self.after_questions = None

    def __call__(self, method, url, headers, body):
        path = tool.urllib.parse.urlparse(url).path
        if method == "GET" and path == f"/v1/admin/extractions/{JOB}":
            self.calls.append((method, path))
            return self.job_status, json.dumps(self.job).encode()
        if method == "GET" and path.endswith("/questions") and not self.put_bodies:
            self.calls.append((method, path))
            if self.after_questions:
                self.after_questions()
            status, response = self.initial
            return status, json.dumps(response).encode()
        if method == "PUT":
            self.put_bodies.append(json.loads(body))
        return super().__call__(method, url, headers, body)


class InitialDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.staged, self.proof, self.job = fixtures()
        self.staged_path = self.root / "staged.json"
        self.proof_path = self.root / "proof.json"
        self.logs = []
        self.fake = InitialTransport(self.staged, self.job)

    def invoke(self, metadata=None, drop=False, allow=False):
        self.staged_path.write_text(json.dumps(self.staged))
        self.proof_path.write_text(json.dumps(self.proof))
        api = tool.Api(tool.FAKE_ENV, transport=self.fake, log=self.logs.append)
        try:
            return tool.cmd_put(api, JOB, self.staged_path, metadata, drop, allow,
                                log=self.logs.append, initialize_empty_proof=self.proof_path)
        finally:
            tool.finish(api, log=self.logs.append)

    def refuse(self, **kwargs):
        with self.assertRaises(tool.Refuse):
            self.invoke(**kwargs)
        self.assertEqual(self.fake.put_bodies, [])
        if self.fake.grants:
            self.assertEqual(self.fake.logouts, 1)
            self.assertEqual(self.fake.calls[-1], ("POST", "/auth/v1/logout?scope=global"))

    def test_initial_put_exact_payload_and_order(self):
        self.assertEqual(self.invoke(), 0)
        self.assertEqual(self.fake.put_bodies, [{"questions": self.staged["questions"], "paper_metadata": SCOPE}])
        self.assertEqual(self.fake.calls[1:4], [
            ("GET", f"/v1/admin/extractions/{JOB}"),
            ("GET", f"/v1/admin/extractions/{JOB}/questions"),
            ("PUT", f"/v1/admin/extractions/{JOB}/questions")])
        self.assertTrue(any(JOB in line and PAPER in line and "scope" in line for line in self.logs))
        self.assertTrue(any("not atomic" in line for line in self.logs))
        self.assertEqual(self.fake.logouts, 1)

    def test_every_proof_field_required(self):
        for key in list(self.proof):
            with self.subTest(key=key):
                saved = self.proof.pop(key)
                self.refuse()
                self.proof[key] = saved

    def test_negative_or_mismatched_evidence(self):
        cases = {"job_id": PAPER, "paper_id": JOB, "source_pdf_sha256": "b" * 64,
                 "actor_id": PAPER, "raw_status": "extracting", "question_count": 1,
                 "paper_rows": 1, "live_question_rows": 1, "r2_bucket": "other",
                 "r2_key": f"onboarding/{PAPER}/questions.json", "staged_object_absent": False,
                 "exclusive_writer_confirmed": False, "updated_at": "2026-09-09T04:52:00Z"}
        for key, value in cases.items():
            with self.subTest(key=key):
                saved = self.proof[key]
                self.proof[key] = value
                self.refuse()
                self.proof[key] = saved

    def test_evidence_types_not_truthiness(self):
        for key, value in [("question_count", False), ("paper_rows", "0"),
                           ("live_question_rows", None), ("staged_object_absent", 1),
                           ("exclusive_writer_confirmed", "true")]:
            with self.subTest(key=key):
                saved = self.proof[key]
                self.proof[key] = value
                self.refuse()
                self.proof[key] = saved

    def test_stale_future_and_malformed_time(self):
        now = dt.datetime.now(dt.timezone.utc)
        for value in [(now - dt.timedelta(seconds=301)).isoformat(),
                      (now + dt.timedelta(seconds=30)).isoformat(), "bad", "2026-09-09T04:51:00", None]:
            with self.subTest(value=value):
                self.proof["checked_at"] = value
                self.refuse()

    def test_get_questions_must_be_exact_absence_response(self):
        for status, response in [(200, {"ready": True, **self.staged}),
                                 (200, {"ready": False}), (200, {"questions": []}),
                                 (200, {"ready": 0, "questions": []}),
                                 (200, {"ready": False, "questions": [], "error": "bad"}),
                                 (200, {"ready": False, "questions": [self.staged["questions"][0]]}),
                                 (200, None), (200, []), (500, {"ready": False, "questions": []}),
                                 (404, {"error": "not_found"})]:
            with self.subTest(status=status, response=response):
                self.fake = InitialTransport(self.staged, self.job)
                self.fake.initial = status, response
                self.refuse()

    def test_job_get_identity_status_count_error_and_timestamps(self):
        for key, value in [("id", PAPER), ("paper_id", JOB), ("status", "published"),
                           ("question_count", 1), ("question_count", False), ("error", "failed"),
                           ("created_at", "bad"), ("updated_at", "2026-09-09T05:00:00Z")]:
            with self.subTest(key=key, value=value):
                job = {**self.job, key: value}
                self.fake = InitialTransport(self.staged, job)
                self.refuse()
        for key in self.job:
            with self.subTest(missing=key):
                job = dict(self.job)
                del job[key]
                self.fake = InitialTransport(self.staged, job)
                self.refuse()
        self.fake = InitialTransport(self.staged, self.job)
        self.fake.job_status = 503
        self.refuse()

    def test_partial_invalid_or_mismatched_scope(self):
        for scope in [{}, {"grade": 8}, {**SCOPE, "medium": "xx"}, {**SCOPE, "grade": True},
                      {**SCOPE, "grade": 12}, {**SCOPE, "subject": ""}, {**SCOPE, "exam": "ol"},
                      {**SCOPE, "year": 2024}]:
            with self.subTest(scope=scope):
                self.staged["paper"]["paper_metadata"] = scope
                self.proof["scope"] = scope
                self.refuse()
        self.staged["paper"]["paper_metadata"] = dict(SCOPE)
        self.proof["scope"] = {**SCOPE, "grade": 7}
        self.refuse()
        self.proof["scope"] = dict(SCOPE)
        self.refuse(metadata={**SCOPE, "grade": 7})

    def test_malformed_local_identity_and_questions(self):
        original = copy.deepcopy(self.staged)
        for paper in [None, {}, {**original["paper"], "paper_id": "bad"},
                      {**original["paper"], "source_pdf_sha256": "bad"}]:
            with self.subTest(paper=paper):
                self.staged = {**original, "paper": paper}
                self.refuse()
        for questions in [None, [], [{}], [original["questions"][0]] * 2]:
            with self.subTest(questions=questions):
                self.staged = {**original, "questions": questions}
                self.refuse()

    def test_proof_malformed_json_nonobject_and_unknown_fields(self):
        for content in ["{", "null", "[]", json.dumps({**self.proof, "extra": True})]:
            with self.subTest(content=content):
                self.proof_path.write_text(content)
                with self.assertRaises(tool.Refuse):
                    tool.load_initial_proof(self.proof_path, JOB, self.staged, None)
        with self.assertRaises(tool.Refuse):
            tool.load_initial_proof(self.root / "missing.json", JOB, self.staged, None)

    def test_expiration_rechecked_after_get_before_put(self):
        real_datetime = dt.datetime
        clock = [real_datetime.now(dt.timezone.utc)]

        class Clock(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return clock[0]

        self.fake.after_questions = lambda: clock.__setitem__(0, clock[0] + dt.timedelta(seconds=301))
        with mock.patch.object(tool.dt, "datetime", Clock):
            self.refuse()
        self.assertTrue(any(path.endswith("/questions") for _, path in self.fake.calls))

    def test_initialization_rejects_unflagged_or_published_local_content(self):
        original = copy.deepcopy(self.staged["questions"][0])
        for patch in [{"ingestion_metadata": None}, {"ingestion_metadata": {"needs_human_review": False}},
                      {"published": True}, {"published": 0}, {"published_at": STAMP}]:
            with self.subTest(patch=patch):
                self.staged["questions"] = [{**original, **patch}]
                self.refuse()

    def test_main_wires_proof_and_always_logs_out_after_grant(self):
        real_api = tool.Api
        for mode in ("success", "refused", "exception"):
            with self.subTest(mode=mode):
                self.fake = InitialTransport(self.staged, self.job)
                if mode == "refused":
                    self.fake.initial = 200, {"ready": True, **self.staged}
                if mode == "exception":
                    def fail():
                        raise RuntimeError("fake transport interruption")
                    self.fake.after_questions = fail
                self.staged_path.write_text(json.dumps(self.staged))
                self.proof_path.write_text(json.dumps(self.proof))
                argv = ["publish.py", "put", JOB, "--staged", str(self.staged_path),
                        "--initialize-empty-proof", str(self.proof_path), "--env", str(self.proof_path)]
                with mock.patch("sys.argv", argv), mock.patch.object(tool, "read_env", return_value=tool.FAKE_ENV), mock.patch.object(tool, "Api", side_effect=lambda *a, **kw: real_api(*a, **kw, transport=self.fake)), contextlib.redirect_stdout(io.StringIO()):
                    if mode == "exception":
                        with self.assertRaises(RuntimeError):
                            tool.main()
                    else:
                        self.assertEqual(tool.main(), 0 if mode == "success" else 3)
                self.assertEqual(self.fake.logouts, 1)
                self.assertEqual(self.fake.calls[-1], ("POST", "/auth/v1/logout?scope=global"))
                self.assertEqual(len(self.fake.put_bodies), int(mode == "success"))

    def test_after_initialization_publish_keeps_signature_ids_flagged_and_t77_guards(self):
        self.assertEqual(self.invoke(), 0)
        for accept, dry, t77_rc, expected in [(None, False, 0, 4), (1, False, 0, 4),
                                             (0, True, 0, 0), (0, False, 1, 1), (0, False, 0, 0)]:
            with self.subTest(accept=accept, dry=dry, t77=t77_rc):
                fake = tool.FakeAdmin(self.fake.doc)
                ids_out = self.root / "ids.json"
                if ids_out.exists():
                    ids_out.unlink()
                checked = []
                def record_check():
                    self.assertEqual(json.loads(ids_out.read_text())["question_ids"], [tool.UUID0])
                def transport(method, url, headers, body):
                    if url.endswith("/publish"):
                        record_check()
                    return fake(method, url, headers, body)
                api = tool.Api(tool.FAKE_ENV, transport=transport, log=self.logs.append)
                try:
                    result = tool.run_publish(api, JOB, self.staged_path, SCOPE, accept, None, None,
                                              ids_out, dry, lambda *args: checked.append(args) or t77_rc,
                                              log=self.logs.append)
                except tool.Refuse as exc:
                    result = exc.code
                finally:
                    tool.finish(api, log=self.logs.append)
                self.assertEqual(result, expected)
                self.assertEqual(len(fake.publishes), int(accept == 0 and not dry))
                self.assertEqual(len(checked), int(accept == 0 and not dry))
                self.assertEqual(fake.logouts, 1)
        for change in ("flag", "scope", "text"):
            with self.subTest(change=change):
                server = copy.deepcopy(self.fake.doc)
                if change == "flag":
                    server["questions"][0]["ingestion_metadata"]["needs_human_review"] = False
                elif change == "scope":
                    server["paper"]["paper_metadata"]["grade"] = 7
                else:
                    server["questions"][0]["question_text"] = "different"
                fake = tool.FakeAdmin(server)
                api = tool.Api(tool.FAKE_ENV, transport=fake, log=self.logs.append)
                with self.assertRaises(tool.Refuse):
                    tool.run_publish(api, JOB, self.staged_path, SCOPE, 0, None, None,
                                     self.root / "ids-refused.json", False, lambda *_: self.fail("unexpected T77"),
                                     log=self.logs.append)
                self.assertFalse(fake.publishes)

    def test_read_and_publish_still_refuse_unready(self):
        self.staged_path.write_text(json.dumps(self.staged))
        for mode in ("get", "publish"):
            api = tool.Api(tool.FAKE_ENV, transport=self.fake, log=self.logs.append)
            with self.subTest(mode=mode), self.assertRaises(tool.Refuse):
                if mode == "get":
                    tool.cmd_get(api, JOB, self.root / "out.json", log=self.logs.append)
                else:
                    tool.run_publish(api, JOB, self.staged_path, SCOPE, 0, None, None,
                                     self.root / "ids-refused.json", False, lambda *_: self.fail("unexpected T77"),
                                     log=self.logs.append)
            tool.finish(api, log=self.logs.append)
        self.assertFalse((self.root / "out.json").exists())
        self.assertFalse((self.root / "ids-refused.json").exists())
        self.assertFalse(self.fake.publishes)

    def test_drop_flags_incompatible(self):
        self.refuse(drop=True)
        self.refuse(allow=True)

    def test_normal_put_still_merges_and_unready_still_refused(self):
        self.staged_path.write_text(json.dumps(self.staged))
        server = copy.deepcopy(self.staged)
        server["questions"][0]["question_id"] = PAPER
        server["questions"][0]["published"] = True
        fake = tool.FakeAdmin(server)
        api = tool.Api(tool.FAKE_ENV, transport=fake, log=self.logs.append)
        self.assertEqual(tool.cmd_put(api, JOB, self.staged_path, None, False, False, log=self.logs.append), 0)
        self.assertEqual(len(fake.doc["questions"]), 2)
        self.assertTrue(fake.doc["questions"][0]["published"])
        api = tool.Api(tool.FAKE_ENV, transport=self.fake, log=self.logs.append)
        with self.assertRaises(tool.Refuse):
            tool.cmd_put(api, JOB, self.staged_path, None, False, False, log=self.logs.append)
        self.assertEqual(self.fake.put_bodies, [])

    def test_flag_rejected_on_read_and_publish_before_env(self):
        for argv in [["publish.py", "get", JOB, "--out", "out.json"],
                     ["publish.py", "publish", JOB, "--staged", "s.json", "--scope", "grade=8"]]:
            with self.subTest(argv=argv), mock.patch("sys.argv", argv + ["--initialize-empty-proof", "proof.json"]), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    tool.main()
                self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
