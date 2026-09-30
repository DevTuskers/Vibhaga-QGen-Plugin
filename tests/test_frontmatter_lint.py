#!/usr/bin/env python3
"""test_frontmatter_lint.py — the A8 frontmatter lint in tools/check-suite.py.

T-QG-1: a skill whose frontmatter is not valid YAML is silently dropped by the CLI — an unquoted
`: ` inside a plain-scalar `description:` is the concrete failure this lint exists to catch.
"""
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load_suite():
    spec = importlib.util.spec_from_file_location("check_suite", ROOT / "tools" / "check-suite.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SUITE = load_suite()


GOOD = """\
---
name: draw-and-verify-question-vdd
description: >-
  Draw a VDD figure for a question — from the claim set the read-figure-claim-set skill emitted
  (constructed channel: the geometry is authored from the stem's stated values). Use when a figure
  must be created or corrected.
---

## 0. Body
"""

BAD = """\
---
name: draw-and-verify-question-vdd
description: Draw a VDD figure — from the claim set (constructed channel: the geometry is authored
  from the stem's stated values). Use when a figure must be created or corrected.
---

## 0. Body
"""


class FrontmatterLint(unittest.TestCase):
    def test_colon_space_in_plain_scalar_fails(self):
        errs = SUITE.frontmatter_errors("skills/x/SKILL.md", BAD, "x")
        self.assertTrue(errs, "plain-scalar description containing ': ' must fail the lint")
        self.assertIn("not valid YAML", errs[0])

    def test_folded_block_passes(self):
        self.assertEqual(
            SUITE.frontmatter_errors(
                "skills/draw-and-verify-question-vdd/SKILL.md", GOOD, "draw-and-verify-question-vdd"
            ),
            [],
        )

    def test_missing_frontmatter_fails(self):
        errs = SUITE.frontmatter_errors("agents/x.md", "# title\n\nno frontmatter\n")
        self.assertTrue(errs)
        self.assertIn("no `---` frontmatter", errs[0])

    def test_non_mapping_frontmatter_fails(self):
        errs = SUITE.frontmatter_errors("agents/x.md", "---\n- just\n- a\n- list\n---\n")
        self.assertTrue(errs)
        self.assertIn("not a mapping", errs[0])

    def test_missing_keys_fail(self):
        errs = SUITE.frontmatter_errors("agents/x.md", "---\nname: x\n---\n")
        self.assertTrue(errs)
        self.assertIn("`description`", errs[0])

    def test_name_must_equal_dir_for_skills(self):
        errs = SUITE.frontmatter_errors("skills/scope-cards/SKILL.md", GOOD, "scope-cards")
        self.assertTrue(errs)
        self.assertIn("!= directory name", errs[0])

    def test_agent_name_not_dir_checked(self):
        agent = "---\nname: qgen-critic\ndescription: reviews output\n---\n"
        self.assertEqual(SUITE.frontmatter_errors("agents/qgen-critic.md", agent), [])


if __name__ == "__main__":
    unittest.main()
