import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "dedup-sheet.py"
SPEC = importlib.util.spec_from_file_location("dedup_sheet_test", TOOL)
dedup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dedup)


class DedupSheetTests(unittest.TestCase):
    def test_stubbed_psql_is_read_only_and_returns_json_rows(self):
        row = {"question_id": "00000000-0000-4000-8000-000000000011",
               "stem_english": "Synthetic stem", "stem_sinhala": "කෘතිම",
               "parts": [{"label": "a", "text_english": "Synthetic part",
                          "text_sinhala": "කෘතිම කොටස"}]}

        def runner(argv, **kwargs):
            self.assertIn("lesson_id=00000000-0000-4000-8000-000000000011", argv)
            self.assertIn("BEGIN TRANSACTION READ ONLY;", kwargs["input"])
            self.assertIn("ROLLBACK;", kwargs["input"])
            self.assertIn("jsonb_build_object", kwargs["input"])
            self.assertIn("text_english", kwargs["input"])
            return subprocess.CompletedProcess(argv, 0, json.dumps(row), "")

        rows = dedup.live_rows({}, "00000000-0000-4000-8000-000000000011", runner)
        self.assertEqual(rows, [row])

    def test_synthetic_card_items_and_question_text_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "26-synthetic.yaml"
            path.write_text(
                "lesson_id: 00000000-0000-4000-8000-000000000012\n"
                "generated:\n"
                "  sections: [{title: Synthetic section}]\n"
                "  worked_examples: [{id: 2, heading: Synthetic example, text: Work it}]\n"
                "  exercises: [{id: 26.1(1), heading: Synthetic exercise, text: Try it}]\n"
                "  activities: [{id: 1, heading: Synthetic activity, text: Make it}]\n"
                "curated:\n"
                "  difficulty_hooks: [Synthetic hook]\n", encoding="utf-8")
            card = dedup.load_card(path)
        row = {"question_id": "00000000-0000-4000-8000-000000000013",
               "question_number": 3, "status": "draft", "stem_english": "Synthetic stem",
               "stem_sinhala": "කෘතිම", "parts": [
                   {"label": "a", "text_english": "Synthetic part", "text_sinhala": "කෘතිම කොටස"}]}
        rendered = "\n".join(dedup.render_lesson("L26", 26, card, [row], None, None))
        for expected in ("live rows 1 · sections 1 · worked examples 1 · exercises 1 · "
                         "activities 1 · difficulty_hooks 1", "L26·WE2", "L26·EX26.1(1)",
                         "L26·ACT1", row["question_id"], "Synthetic stem", "කෘතිම කොටස"):
            self.assertIn(expected, rendered)

    def test_plan_lines_are_paired_with_similar_neighbours(self):
        plan = [{"key": "Q1", "stem": "Synthetic plan", "parts": ["First task"]}]
        similar = {"results": [{"key": "Q1", "neighbours": [
            {"question_id": "00000000-0000-4000-8000-000000000014", "score": 0.4,
             "stem": "Synthetic neighbour", "parts": ["Neighbour part"]}]}]}
        rendered = "\n".join(dedup.render_lesson(
            "L26", 26, {}, [], plan, similar))
        self.assertIn("Synthetic plan", rendered)
        self.assertIn("similar 0.4 · 00000000-0000-4000-8000-000000000014: Synthetic neighbour",
                      rendered)
        self.assertIn("Neighbour part", rendered)


if __name__ == "__main__":
    unittest.main()
