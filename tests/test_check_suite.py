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


class Units(unittest.TestCase):
    def test_empty_selection_imports_nothing(self):
        self.assertEqual(cs.unittest_units(set()), ([], []))

    def test_selection_keeps_only_its_module(self):
        units, broken = cs.unittest_units({"test_check_suite"})
        self.assertEqual(broken, [])
        self.assertTrue(units)
        self.assertTrue(all(i.startswith("test_check_suite.") for u in units for i in u["ids"]))


class TrapIndex(unittest.TestCase):
    def test_detail_links_must_match_the_indexed_trap_id(self):
        index = ROOT / "docs" / "TRAPS.md"
        area = index.parent / "traps" / "figures.md"
        docs = {
            index: "| [T-QG-2](traps/figures.md#t-qg-2) | Check stem values. |\n",
            area: '<a name="t-qg-2"></a>\n\n## T-QG-2 — Check stem values\n',
        }
        errors = len(cs.ERRORS)
        try:
            cs.check_trap_references(docs)
            self.assertEqual(cs.ERRORS[errors:], [])
            docs[index] = docs[index].replace("#t-qg-2", "#t-qg-3")
            cs.check_trap_references(docs)
            self.assertIn("T-QG-2 does not link to its detail", cs.ERRORS[errors])
            del cs.ERRORS[errors:]
            docs[area] += '\n## T-QG-3 — Another detail\n'
            cs.check_trap_references(docs)
            self.assertTrue(any("T-QG-3 missing" in error for error in cs.ERRORS[errors:]))
        finally:
            del cs.ERRORS[errors:]


if __name__ == "__main__":
    unittest.main()
