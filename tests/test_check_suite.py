"""check-suite.py --quick: changed paths → the tests they reach."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_suite", ROOT / "tools" / "check-suite.py")
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)


class Keys(unittest.TestCase):
    def test_code_file_has_both_spellings(self):
        self.assertEqual(cs.keys_of("tools/check-si-terms.py"),
                         {"check-si-terms", "check_si_terms"})

    def test_data_file_is_its_name(self):
        self.assertEqual(cs.keys_of("queries.sql"), {"queries.sql"})


class Depends(unittest.TestCase):
    def test_import_is_an_edge(self):
        self.assertTrue(cs.depends("import os\nfrom fake_tool import x\n", {"fake_tool"}))
        self.assertTrue(cs.depends("import os, fake_tool\n", {"fake_tool"}))

    def test_quoted_path_is_an_edge(self):
        self.assertTrue(cs.depends('argv = ["tools/fake-tool.py", "-x"]', {"fake-tool"}))
        self.assertTrue(cs.depends("open(ROOT / 'fake.yaml')", {"fake.yaml"}))

    def test_prose_mention_is_not(self):
        self.assertFalse(cs.depends("# see fake_tool for the rule\n", {"fake_tool"}))
        self.assertFalse(cs.depends('"""Like fake-tool.py, but faster."""', {"fake-tool"}))


class QuickSelection(unittest.TestCase):
    def setUp(self):
        self._warns = list(cs.WARNS)

    def tearDown(self):
        cs.WARNS[:] = self._warns

    def test_doc_only_change_reaches_no_tests(self):
        self.assertEqual(cs.quick_selection(["docs/TRAPS.md", "skills/generate/SKILL.md"]), (set(), set()))

    def test_changed_test_selects_itself(self):
        tests, _ = cs.quick_selection(["tests/test_check_suite.py"])
        self.assertIn("tests/test_check_suite.py", tests)

    def test_tool_change_selects_its_tests_and_importers(self):
        tests, reached = cs.quick_selection(["tools/check-si-terms.py"])
        self.assertIn("tests/test_check_si_terms.py", tests)
        self.assertIn("check-si-terms", reached)
        self.assertIn("run-gates", reached)          # run-gates invokes check-si-terms.py
        self.assertNotIn("tests/test_vdd_templates.py", tests)

    def test_missing_path_is_ignored(self):
        self.assertEqual(cs.quick_selection(["tools/deleted-tool.py"]), (set(), set()))


if __name__ == "__main__":
    unittest.main()
