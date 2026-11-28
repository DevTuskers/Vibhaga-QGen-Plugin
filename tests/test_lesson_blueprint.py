import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools/lesson-blueprint.py"


class LessonBlueprintTests(unittest.TestCase):
    def test_draft_and_coverage(self):
        import yaml

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            card, blueprint, rows, marked = (work / name for name in ("card", "grid", "rows", "marked"))
            card.write_text(json.dumps({
                "schema_version": 1, "grade": 10, "lesson_number": 1,
                "generated": {"sections": [{"number": "1.1", "title": "Synthetic section"}],
                              "vocabulary": ["synthetic term"]},
                "curated": {"difficulty_hooks": [{"level": "M", "hook": "synthetic hook"}]},
            }))
            subprocess.run([sys.executable, SCRIPT, "build", card, "--out", blueprint], check=True)
            draft = yaml.safe_load(blueprint.read_text())
            self.assertEqual(draft["cells"], [])
            self.assertEqual(draft["difficulty_hooks"][0]["level"], "M")
            self.assertEqual(draft["vocabulary"], ["synthetic term"])
            item = {"id": "first-cell", "section": "s1", "skill": "estimate", "task_chain": "compare gaps",
                    "representation": "table", "unknown_direction": "forward", "band": "medium", "format": "short"}
            draft["cells"] = [item, dict(item, id="second-cell", unknown_direction="decide")]
            blueprint.write_text(json.dumps(draft))
            rows.write_text(json.dumps({"questions": [
                {"question_id": "test-row-1", "cell_id": "first-cell", "difficulty_band": "medium"},
                {"question_id": "test-row-2", "cell_id": "second-cell", "needs_human_review": True},
                {"question_id": "test-row-3"},
            ]}))
            result = subprocess.run([sys.executable, SCRIPT, "check", blueprint, "--coverage", rows,
                                     "--out", marked], capture_output=True, text=True, check=True)
            self.assertIn("Covered cells: 1/2; unmapped live rows: 1", result.stdout)
            self.assertIn("medium: 1 uncovered (second-cell)", result.stdout)
            self.assertEqual([cell["covered"] for cell in yaml.safe_load(marked.read_text())["cells"]], [True, False])
            draft["cells"][1]["unknown_direction"] = "forward"
            blueprint.write_text(json.dumps(draft))
            result = subprocess.run([sys.executable, SCRIPT, "check", blueprint], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("duplicate cell coordinates", result.stderr)
