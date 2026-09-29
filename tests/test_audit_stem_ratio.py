"""Subprocess coverage for tools/audit-claim-set.py's stem-justification check (2d):
the planted-bad fixture — anchors and claim agree at the DRAWN ratio (1.5) while the
stem states 5:2 — must FAIL, and the corrected fixture must pass."""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "tools" / "audit-claim-set.py"
FIXTURES = HERE / "fixtures"


class StemRatioCheckTests(unittest.TestCase):
    def run_tool(self, fixture):
        return subprocess.run([sys.executable, str(TOOL), str(FIXTURES / fixture)],
                              capture_output=True, text=True)

    def test_bad_fixture_fails_and_cites_the_claim(self):
        r = self.run_tool("stem-ratio-bad.txt")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("K2", r.stdout)
        self.assertIn("stem", r.stdout)

    def test_good_fixture_passes(self):
        r = self.run_tool("stem-ratio-good.txt")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unbacked_derive_fails_and_names_the_literal(self):
        # the claim cites `derive K9` (= 3/2 = 1.5, matching the drawn value) but the stem
        # never mentions 3 — an invented derive must not rescue a copied ratio.
        r = self.run_tool("stem-ratio-unbacked-derive.txt")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("K2", r.stdout)
        self.assertIn("not backed", r.stdout)
        self.assertIn("3", r.stdout)

    def test_self_test_passes(self):
        r = subprocess.run([sys.executable, str(TOOL), "--self-test"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
