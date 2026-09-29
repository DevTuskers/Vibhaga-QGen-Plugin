import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
GATE = HERE.parent / "tools" / "run-gate.sh"
ASSET = {"version": 1, "canvas": {"width": 200, "height": 100}, "elements": []}
OTHER = {**ASSET, "elements": [{"type": "point", "x": 20, "y": 30}]}


class FigureCoverageTests(unittest.TestCase):
    def run_check(self, diagrams, assets, extra=None, via_gate=False):
        source = GATE.read_text()
        functions = source[source.index("N=0; F=0"):source.index("self_test()")]
        command = '\nfigure_check "$1" II "$2"\nexit "$F"'
        if via_gate:
            command = '\ns8_s5_checks() { :; }; text_gates() { :; }\ngate "$2"\nexit "$F"'
        with tempfile.TemporaryDirectory(prefix="run-gate-figures-") as tmp:
            root = Path(tmp)
            (root / "figures").mkdir()
            for name, asset in assets.items():
                (root / "figures" / name).write_text(json.dumps(asset))
            staged = {"questions": [{"question_id": "q1", "sub_questions": [
                {"label": label, "diagram_dsl": diagram}
                for label, diagram in zip(("v", "vi", "vii"), diagrams)
            ]}]}
            if extra:
                staged.update(extra)
            (root / "questions-II.json").write_text(json.dumps(staged))
            return subprocess.run(
                ["bash", "-c", functions + command,
                 "fixture", str(root / "questions-II.json"), str(root)],
                capture_output=True, text=True, check=False,
                env={"PATH": os.environ["PATH"],
                     "PYTHONDONTWRITEBYTECODE": "1", "VIBHAGA_ADMIN_ENV": "/nonexistent/offline-test-only"},
            )

    def assert_gate(self, diagrams, assets, passes, extra=None):
        result = self.run_check(diagrams, assets, extra)
        self.assertEqual(result.returncode, 0 if passes else 1, result.stdout + result.stderr)
        self.assertIn("[II/figures]", result.stdout)
        return result.stdout

    def test_same_asset_attached_twice(self):
        self.assert_gate([ASSET, copy.deepcopy(ASSET)], {"q1v.json": ASSET}, True)

    def test_normal_unique_assets(self):
        self.assert_gate([ASSET, OTHER], {"q1v.json": ASSET, "q1vi.json": OTHER}, True)

    def test_wrong_asset_at_equal_count(self):
        self.assert_gate([OTHER], {"q1v.json": ASSET}, False)

    def test_extraneous_occurrence(self):
        self.assert_gate([ASSET, OTHER], {"q1v.json": ASSET}, False)

    def test_unused_asset_at_equal_count(self):
        self.assert_gate([ASSET, ASSET], {"q1v.json": ASSET, "q1vi.json": OTHER}, False)

    def test_missing_asset_file(self):
        self.assert_gate([ASSET], {}, False)

    def test_missing_attachment(self):
        self.assert_gate([None], {"q1v.json": ASSET}, False)

    def test_empty_assets_and_attachments(self):
        self.assert_gate([None], {}, True)

    def test_anchor_files_ignored(self):
        # anchors sidecars are not figure assets; every other *.json in figures/ is one
        self.assert_gate([ASSET], {"q1v.json": ASSET, "q1v.anchors.json": OTHER}, True)

    def test_object_key_order_is_irrelevant(self):
        reordered = dict(reversed(list(ASSET.items())))
        self.assert_gate([reordered], {"q1v.json": ASSET}, True)

    def test_array_order_is_significant(self):
        asset = {**ASSET, "elements": [1, 2]}
        self.assert_gate([{**asset, "elements": [2, 1]}], {"q1v.json": asset}, False)

    def test_null_asset_is_unused(self):
        self.assert_gate([None], {"q1v.json": None}, False)

    def test_non_json_numbers_fail_closed(self):
        self.assert_gate([ASSET], {"q1v.json": {"x": float("nan")}}, False)

    def test_integral_float_matches_integer(self):
        self.assert_gate([{"points": [[58, 0]]}], {"q1v.json": {"points": [[58.0, -0.0]]}}, True)

    def test_boolean_does_not_match_number(self):
        self.assert_gate([{"x": True}], {"q1v.json": {"x": 1}}, False)

    def test_per_level_counts(self):
        part = {"diagram_dsl": ASSET, "answers": [{"diagram_dsl": ASSET}],
                "sub_answer": {"sub_answer_id": "s", "diagram_dsl": ASSET}}
        question = {**copy.deepcopy(part), "sub_questions": [
            {**copy.deepcopy(part), "sub_questions": [copy.deepcopy(part)]}
        ]}
        out = self.assert_gate([], {"q1v.json": ASSET}, True, {"questions": [question]})
        report = json.loads(out.split("canonical JSON content equality (whole staged document): ", 1)[1])
        self.assertEqual(report["placements"], 9)
        self.assertEqual(report["files"], 1)
        self.assertEqual(report["by_level"], {"q": 1, "sq": 1, "sq2": 1,
                                              "a": 2, "sa": 2, "sa2": 2, "other": 0})

    def test_equivalent_aliases_warn_but_pass_with_one_placement(self):
        asset = {"points": [[58, 0]]}
        out = self.assert_gate([asset], {"q1v.json": asset,
                                       "q1vi.json": {"points": [[58.0, -0.0]]}}, True)
        warning = next(line for line in out.splitlines() if "[II/figures#aliases]" in line)
        self.assertTrue(warning.endswith("WARN"))
        self.assertIn('["q1v.json","q1vi.json"]', warning)
        self.assertIn("content equality only; unique file use not proven", warning)

    def test_alias_warning_does_not_hide_unused_different_content(self):
        out = self.assert_gate([ASSET], {"q1v.json": ASSET, "q1vi.json": ASSET,
                                       "q2.json": OTHER}, False)
        self.assertIn("[II/figures#aliases]", out)
        self.assertIn('"unused": ["q2.json"]', out)
        self.assertTrue(out.rstrip().endswith("FAIL"))

    def test_all_staged_occurrences_are_checked_through_gate(self):
        # figure coverage is over the WHOLE staged doc — no publish-set scoping in qgen
        questions = [{"question_id": "q1"}, {"question_id": "q2", "diagram_dsl": ASSET}]
        for assets, code in (({}, 1), ({"q2.json": ASSET}, 0)):
            with self.subTest(assets=assets):
                result = self.run_check([], assets, {"questions": questions}, via_gate=True)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertIn("content equality (whole staged document)", result.stdout)
                if code:
                    self.assertIn('"unmatched": ["questions/1/diagram_dsl"]', result.stdout)

    def test_extra_placement_outside_questions_fails(self):
        self.assert_gate([ASSET], {"q1v.json": ASSET}, False,
                         {"extra": {"diagram_dsl": OTHER}})


if __name__ == "__main__":
    unittest.main()
