import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
GATE = HERE.parent / "tools" / "run-gate.sh"
U = lambda n: f"00000000-0000-4000-8000-0000000000{n:02d}"
QUESTION = {"question_id": U(1), "question_number": 1, "sort_order": 0, "is_multipart": False,
            "question_text": "A synthetic stem.", "lesson_ids": [U(11)],
            "answers": [{"answer_id": U(2), "approach": "a", "final_answer_latex": "b"}],
            "ingestion_metadata": {"needs_human_review": True}}
STAGED = {"questions": [QUESTION]}


class GateFormatTests(unittest.TestCase):
    def run_gate(self, files, stubs='\ns8_s5_checks() { :; }; text_gates() { :; }; figure_check() { :; }'):
        """Run `gate` on a temp run dir with all heavy checks stubbed, return the CompletedProcess."""
        source = GATE.read_text()
        functions = source[source.index("N=0; F=0"):source.index("self_test()")]
        with tempfile.TemporaryDirectory(prefix="run-gate-formats-") as tmp:
            root = Path(tmp)
            for name, data in files.items():
                (root / name).write_text(data if isinstance(data, str) else json.dumps(data))
            return subprocess.run(["bash", "-c", functions + stubs + '\ngate "$1"\nexit "$F"', "fixture", tmp],
                                  text=True, capture_output=True, check=False,
                                  env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1",
                                       "VIBHAGA_ADMIN_ENV": "/nonexistent/offline-test-only"})

    def s8(self, staged):
        """Run only s8_s5_checks on the given staged doc."""
        source = GATE.read_text()
        functions = source[source.index("N=0; F=0"):source.index("self_test()")]
        with tempfile.TemporaryDirectory(prefix="run-gate-s8-") as tmp:
            f = Path(tmp) / "s.json"
            f.write_text(staged if isinstance(staged, str) else json.dumps(staged))
            return subprocess.run(["bash", "-c", functions + '\ns8_s5_checks "$1" II\nexit "$F"', "fixture", str(f)],
                                  text=True, capture_output=True, check=False,
                                  env={"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1",
                                       "VIBHAGA_ADMIN_ENV": "/nonexistent/offline-test-only"})

    # ── staged-doc discovery ────────────────────────────────────────────────────
    def test_staged_json_is_discovered(self):
        result = self.run_gate({"staged.json": STAGED})
        self.assertIn("===== Staged doc staged", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_questions_json_and_sub_files_are_discovered(self):
        result = self.run_gate({"questions.json": STAGED})
        self.assertIn("===== Staged doc _", result.stdout)
        result = self.run_gate({"questions-I.json": STAGED, "questions-II.json": STAGED})
        self.assertIn("===== Staged doc I", result.stdout)
        self.assertIn("===== Staged doc II", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_no_staged_doc_is_usage_error(self):
        result = self.run_gate({"unrelated.json": {}})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("no staged doc", result.stderr)

    def test_malformed_staged_doc_fails_closed(self):
        result = self.run_gate({"questions-I.json": "{not json"})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not valid JSON", result.stdout)

    # ── lesson_ids: ≥1 uuid per question (mixed-lesson questions may carry several) ──
    def lessons(self, lesson_ids, passes=True):
        staged = copy.deepcopy(STAGED)
        staged["questions"][0]["lesson_ids"] = lesson_ids
        result = self.s8(staged)
        self.assertEqual(result.returncode == 0, passes, result.stdout + result.stderr)
        self.assertIn("[II/lessons]", result.stdout)
        return result

    def test_lesson_uuid_required(self):
        self.lessons([U(11)])
        self.lessons([U(11), U(12), U(13)])  # mixed-lesson questions carry more than two

    def test_lesson_rejections(self):
        for bad in ([], None, "l1", ["not-a-uuid"], [U(11), "also-bad"], [None], [42]):
            with self.subTest(bad=bad):
                self.lessons(bad, False)

    # ── exam key — playground items carry none (decision 0018 PD-6) ─────────────
    def test_exam_key_anywhere_fails(self):
        staged = copy.deepcopy(STAGED)
        staged["questions"][0]["exam"] = "ol"
        result = self.s8(staged)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("[II/exam]", result.stdout)

    def test_nested_exam_key_fails(self):
        staged = copy.deepcopy(STAGED)
        staged["questions"][0]["ingestion_metadata"]["exam"] = "ol"
        result = self.s8(staged)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    # ── needs_human_review flag on every question ────────────────────────────────
    def test_unflagged_question_fails(self):
        for flag in (False, None, 0, "false"):
            with self.subTest(flag=flag):
                staged = copy.deepcopy(STAGED)
                staged["questions"][0]["ingestion_metadata"]["needs_human_review"] = flag
                result = self.s8(staged)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_missing_ingestion_metadata_fails(self):
        staged = copy.deepcopy(STAGED)
        del staged["questions"][0]["ingestion_metadata"]
        result = self.s8(staged)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    # ── sub_answer object is a first-class answer node (Vibhaga-API collectSubAnswers) ──
    def test_sub_answer_object_satisfies_answer_checks(self):
        staged = copy.deepcopy(STAGED)
        staged["questions"][0].update(is_multipart=True, sub_questions=[
            {"sub_question_id": U(3), "label": "a", "sort_order": 0, "text": "t",
             "sub_answer": {"sub_answer_id": U(4), "approach": "x", "final_answer_latex": "y"}}])
        result = self.s8(staged)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sub_answer_missing_id_fails(self):
        for node in ({"sub_answer": {"answer_id": U(4), "approach": "x"}},
                     {"sub_answer": {"approach": "x"}},
                     {"sub_answer": "not-an-object"},
                     {"answers": [{"answer_id": U(4)}]}):
            with self.subTest(node=node):
                staged = copy.deepcopy(STAGED)
                staged["questions"][0].update(is_multipart=True, sub_questions=[
                    {"sub_question_id": U(3), "label": "a", "sort_order": 0, "text": "t", **node}])
                result = self.s8(staged)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_answer_in_answers_array_at_sub_level_needs_sub_answer_id(self):
        staged = copy.deepcopy(STAGED)
        staged["questions"][0].update(is_multipart=True, sub_questions=[
            {"sub_question_id": U(3), "label": "a", "sort_order": 0, "text": "t",
             "answers": [{"sub_answer_id": U(4), "approach": "x", "final_answer_latex": "y"}]}])
        result = self.s8(staged)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
