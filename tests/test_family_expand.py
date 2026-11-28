import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/family-expand.py"
FIXTURE = ROOT / "tests/fixtures/scaled-family.yaml"


class FamilyExpandTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.content, self.ledger = self.work / "content.yaml", self.work / "ledger.yaml"

    def run_tool(self, spec=FIXTURE, count=8, extra=()):
        return subprocess.run(
            [sys.executable, SCRIPT, spec, "--count", str(count), "--seed", "123", "--out", self.content,
             "--ledger", self.ledger, *extra], capture_output=True, text=True)

    def test_exact_reproducible_variants_and_build_staged(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        content, ledger = self.content.read_bytes(), self.ledger.read_bytes()
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((content, ledger), (self.content.read_bytes(), self.ledger.read_bytes()))
        data = yaml.safe_load(ledger)
        self.assertEqual(len(set(data["sample"])), 3)
        self.assertEqual(len({tuple(row["number_key"]) for row in data["variants"]}), 8)
        for row in data["variants"]:
            self.assertEqual(row["family_id"], "block-span-synthetic")
            self.assertEqual(Fraction(row["answers"]["width"]), Fraction(row["params"]["span"], row["params"]["gaps"]))
        staged = self.work / "staged.json"
        subprocess_result = subprocess.run(
            [sys.executable, ROOT / "tools/build-staged.py", self.content, "--out", staged],
            capture_output=True, text=True)
        self.assertEqual(subprocess_result.returncode, 0, subprocess_result.stderr)
        staged_ids = [q["question_id"] for q in json.loads(staged.read_text())["questions"]]
        self.assertEqual(staged_ids, [row["question_id"] for row in data["variants"]])
        answer_result = subprocess.run([sys.executable, ROOT / "tools/check-answers.py", self.content],
                                       capture_output=True, text=True)
        self.assertEqual(answer_result.returncode, 0, answer_result.stdout + answer_result.stderr)
        self.assertIn("8 checked · 0 false · 0 warn", answer_result.stdout)

    def test_vdd_template_specs_use_typed_slots(self):
        spec = yaml.safe_load(FIXTURE.read_text())
        path, figures = self.work / "family.yaml", self.work / "figures.json"
        spec["figure"] = {"template": "rectangle_points", "length": "{span}", "width": "{gaps}"}
        path.write_text(yaml.safe_dump(spec))
        result = self.run_tool(path, count=1, extra=("--first", "9", "--figures-out", figures))
        self.assertEqual(result.returncode, 0, result.stderr)
        [figure] = json.loads(figures.read_text())
        self.assertEqual(figure["figure_id"], "Q9")
        self.assertIs(type(figure["length"]), int)
        result = subprocess.run([sys.executable, ROOT / "tools/vdd_templates.py", "build", figures,
                                 "--out", self.work / "figures"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.work / "figures/Q9.json").is_file())

    def test_history_excludes_previous_number_tuples_and_enforces_cap(self):
        result = self.run_tool(count=4)
        self.assertEqual(result.returncode, 0, result.stderr)
        prior = self.work / "prior.yaml"
        self.ledger.rename(prior)
        result = self.run_tool(count=4, extra=("--prior-ledger", prior, "--first", "5"))
        self.assertEqual(result.returncode, 0, result.stderr)
        keys = [{tuple(row["number_key"]) for row in yaml.safe_load(path.read_text())["variants"]}
                for path in (prior, self.ledger)]
        self.assertTrue(keys[0].isdisjoint(keys[1]))
        result = self.run_tool(count=27, extra=("--prior-ledger", prior))
        self.assertEqual(result.returncode, 2)
        self.assertIn("exceed limit 30", result.stderr)

    def test_rejects_invalid_or_failed_solver_check(self):
        spec = yaml.safe_load(FIXTURE.read_text())
        path = self.work / "family.yaml"
        spec["solver"]["width"] = "min(gaps, span)"
        path.write_text(yaml.safe_dump(spec))
        result = self.run_tool(spec=path, count=1)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown solver name 'min'", result.stderr)
        spec["solver"]["width"] = "span / gaps + 1"
        path.write_text(yaml.safe_dump(spec))
        result = self.run_tool(spec=path, count=1)
        self.assertEqual(result.returncode, 2)
        self.assertIn("independent check did not pass", result.stderr)
        self.assertFalse(self.content.exists())
