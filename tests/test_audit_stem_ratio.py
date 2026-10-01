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

    def test_real_shape_stem_justified_but_labels_refuse(self):
        # THE REAL INCIDENT'S NUMBERS: the stem states 5, 3 and 2 — so the copied 1.5 = 3/2
        # is stem-justified AND the cited derive is backed. Only the figure's own labels
        # (5 cm on AB, 2 cm on BC) prove the drawn ratio wrong — check 2e-ii.
        r = self.run_tool("stem-ratio-real-shape-bad.txt")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("K2", r.stdout)
        self.assertIn("'5 cm'", r.stdout)
        self.assertIn("must be 2.5", r.stdout)
        self.assertNotIn("not justified by the stem", r.stdout)   # stem can't refuse it here

    def test_parallel_edge_forge_fails_on_drawn_vs_label_pairs(self):
        # The critic's forge: the copied 1.5 is claimed on AB/BC while the labels live on the
        # PARALLEL edges DC ("5 cm")/DA ("2 cm") — neither stem check nor claim-level label
        # check sees it. The anchor-based pair check does: drawn DC/DA = 1.5 ≠ printed 2.5.
        r = self.run_tool("stem-ratio-parallel-forge.txt")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("K20", r.stdout)
        self.assertIn("K21", r.stdout)
        self.assertIn("disagrees with its own labels", r.stdout)
        self.assertNotIn("not justified by the stem", r.stdout)   # stem canNOT refuse it here

    def test_numeric_label_on_undeclared_segment_fails(self):
        # The label rides AC — the face DIAGONAL, never declared in `segments:` — so the
        # drawn-vs-label pair check cannot measure it. The binding itself must fail.
        r = self.run_tool("stem-ratio-undeclared-label.txt")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("undeclared segment AC", r.stdout)
        self.assertIn("K7", r.stdout)

    def test_self_test_passes(self):
        r = subprocess.run([sys.executable, str(TOOL), "--self-test"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
