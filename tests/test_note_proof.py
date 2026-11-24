#!/usr/bin/env python3
"""tools/note-proof.py — offline tests. No DB, no network, synthetic ids only
(00000000-0000-4000-8000-0000000000NN, *.invalid.test)."""
import base64
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
SPEC = importlib.util.spec_from_file_location("note_proof", TOOLS / "note-proof.py")
np_ = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(np_)

LESSON = "00000000-0000-4000-8000-0000000000f1"
ADMIN = "00000000-0000-4000-8000-0000000000f2"
STUDENT = "00000000-0000-4000-8000-0000000000f3"


def jwt(claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"x.{body}.y"


class FakeStudent:
    api, cf = "https://api.invalid.test", {}

    def __init__(self, uid=STUDENT, role=None):
        self.user_id, self.role = uid, role

    def token(self):
        return jwt({"sub": self.user_id, "app_metadata": {"vibhaga_role": self.role} if self.role else {}})


def get_returning(status, err):
    def get(method, url, headers, body):
        get.url = url
        return status, {}, json.dumps({"error": err}).encode() if err is not None else b""
    return get


class NoteProof(unittest.TestCase):
    NOTE = {"content_english": "en", "content_sinhala": "si", "diagrams": [], "status": "draft",
            "verified_by": None, "verified_at": None}

    def test_compare_stored(self):
        self.assertEqual(np_.compare_stored(self.NOTE, "en", "si", []), [])
        bad = np_.compare_stored({**self.NOTE, "content_sinhala": "si ", "status": "verified",
                                  "verified_by": ADMIN, "diagrams": [{}]}, "en", "si", [])
        self.assertEqual(len(bad), 4, bad)

    def test_student_check(self):
        nf = {"code": "not_found", "message": "Lesson note not found.", "request_id": "r"}
        get = get_returning(404, nf)
        bad, res = np_.student_check(FakeStudent(), LESSON, ADMIN, get)
        self.assertEqual(bad, [])
        self.assertEqual(get.url, f"https://api.invalid.test/v1/lessons/{LESSON}/note")
        self.assertEqual(res["student_code"], "not_found")
        for name, (stu, g) in {
            "router-404": (FakeStudent(), get_returning(404, {"code": "not_found", "message": "No route for GET /x"})),
            "visible": (FakeStudent(), get_returning(200, None)),
            "no-envelope": (FakeStudent(), get_returning(404, None)),
            "admin-role": (FakeStudent(role="admin"), get_returning(404, nf)),
            "same-account": (FakeStudent(uid=ADMIN), get_returning(404, nf)),
        }.items():
            with self.subTest(name):
                bad, _ = np_.student_check(stu, LESSON, ADMIN, g)
                self.assertTrue(bad)

    def test_error_envelope_tolerates_garbage(self):
        for raw in (b"", b"not json", b"[]", b'{"error": "x"}'):
            self.assertEqual(np_.error_envelope(404, raw), {})

    def test_student_env_overlays_student_api(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env.local"
            admin = {"VIBHAGA_ADMIN_EMAIL": "a@example.test", "VIBHAGA_ADMIN_PASSWORD": "p",
                     "NEXT_PUBLIC_API_BASE_URL": "https://admin-api.invalid.test",
                     "NEXT_PUBLIC_SUPABASE_URL": "https://auth.invalid.test"}
            self.assertIsNone(np_.student_env(p, admin))
            p.write_text("DEV_LOGIN_EMAIL=s@example.test\n", encoding="utf-8")
            self.assertIsNone(np_.student_env(p, admin))
            p.write_text("DEV_LOGIN_EMAIL=s@example.test\nDEV_LOGIN_PASSWORD=q\n"
                         "NEXT_PUBLIC_API_BASE_URL=https://api.invalid.test\n", encoding="utf-8")
            env = np_.student_env(p, admin)
        self.assertEqual(env["VIBHAGA_ADMIN_EMAIL"], "s@example.test")
        self.assertEqual(env["NEXT_PUBLIC_API_BASE_URL"], "https://api.invalid.test")
        self.assertEqual(env["NEXT_PUBLIC_SUPABASE_URL"], "https://auth.invalid.test")

    def test_q5_slices_to_one_guarded_statement(self):
        sql = np_.sp.slice_proof(np_.sp.QUERIES.read_text(), "Q5")
        self.assertIn("FROM lesson_notes", sql)
        for var in ("lesson_id", "note_id", "version", "actor_id"):
            self.assertIn(f":'{var}'", sql)
        self.assertNotIn("content_english", sql)
        self.assertNotIn("Q1", sql)

    def test_usage_and_missing_student(self):
        with tempfile.TemporaryDirectory() as d:
            w = Path(d)
            for f, s in (("en.md", "x"), ("si.md", "y"), ("diagrams.json", "[]")):
                (w / f).write_text(s, encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as e:
                np_.main([str(w), "--lesson", "nope"])
            self.assertEqual(e.exception.code, 2)
            for extra in ([], ["--student-env", str(w / "absent.env")]):
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as e:
                    np_.main([str(w), "--lesson", LESSON, *extra])
                self.assertEqual(e.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
