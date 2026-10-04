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


class CircleThroughGrammarTests(unittest.TestCase):
    """`circle centre X through` takes one to three on-outline anchors — the
    spelling vdd-check evaluates from two up (the W10c builders emit it). A lone
    through-point parses but is recognised-not-verifiable: nothing to compare."""

    BASE = """figure:   t — t
source:   constructed; frame is the figure's own canvas, 80 x 80, y down
channel:  constructed
stem:     A circle with 2 anchors on its outline.
ask:      a  the circle
points:   Z A B C D
segments:
anchors:
  Z 40 40
  A 40 10
  B 40 70
  C 10 40
  D 70 40
claims:
{claims}  K8  derive 1 + 1 = 2 | inferred | the anchor count
  K9  none tickMark parallelMark angleMark arrow dashed shaded | inferred | t
load-bearing:
  a -> K1
unreadable: (none)
ambiguous:  (none)
"""

    def run_claims(self, claims):
        import tempfile
        body = "".join(f"  K{i + 1}  {c} | inferred | t\n"
                       for i, c in enumerate(claims))
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(self.BASE.format(claims=body))
            name = f.name
        return subprocess.run([sys.executable, str(TOOL), name],
                              capture_output=True, text=True)

    def test_one_through_is_recognised_not_verifiable(self):
        # one through-point has nothing to compare — parsed, anchors checked,
        # but it lands in the footer's not-verifiable list, not anchor-checked
        r = self.run_claims(["circle centre Z through A"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"NOT verifiable here: \d+ \([^)]*K1")

    def test_two_and_three_throughs_are_anchor_checked(self):
        for claim in ("circle centre Z through A B",
                      "circle centre Z through A B C"):
            r = self.run_claims([claim])
            self.assertEqual(r.returncode, 0, claim + "\n" + r.stdout + r.stderr)
            self.assertNotRegex(r.stdout, r"NOT verifiable here: \d+ \([^)]*K1")

    def test_four_throughs_and_repeats_fail(self):
        r = self.run_claims(["circle centre Z through A B C D"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.run_claims(["circle centre Z through A A"])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)


class ReadsNonparallelTests(unittest.TestCase):
    """W11's two new anchor predicates: `reads P v on XY` (a point reads a value off a
    declared axis — bar-chart bar tops, coordinate-plane projections) and `nonparallel AB CD`
    (two segments drawn >=5 deg apart — the crossing line's honesty claim). The fixture also
    exercises the printed-numerals exclusion: "2008" is printed, but bound to `cat0`, so it is
    a category name, not a scale numeral. OY runs 180 units for a 0..5 scale, so T1 at 0.6 of
    the way reads 3; AB lies parallel to OX, CD tilts away."""

    BASE = """figure:   t — t
source:   constructed; frame is the figure's own canvas, 240 x 240, y down
channel:  constructed
stem:     The chart shows 3 units and 2008 widgets.
ask:      a  the figure
labels:   0 1 2 3 4 5 2008
points:   O X Y T1 A B C D
segments: OX OY AB CD
anchors:
  O 40 200
  X 220 200
  Y 40 20
  T1 90 92
  A 40 150
  B 220 150
  C 90 60
  D 130 200
claims:
  K1  axis OY from 0 to 5     | stem     | the value axis
  K2  tick OY step 1          | stem     |
  K10 label "0" names 0       | stem     |
  K11 label "1" names 1       | stem     |
  K12 label "2" names 2       | stem     |
  K13 label "3" names 3       | stem     |
  K14 label "4" names 4       | stem     |
  K15 label "5" names 5       | stem     |
  K16 label "2008" names cat0 | stem     | a year category — not a scale numeral
  K90 derive 3 * 1 = 3        | inferred | t
  K99 none tickMark parallelMark angleMark angleArc dashed shaded | inferred | t
{claims}load-bearing:
  a -> K3
unreadable: (none)
ambiguous:  (none)
"""

    def run_claims(self, claims, replace=None):
        """claims: list of (predicate, evidence) tuples, numbered from K3."""
        import tempfile
        body = "".join(f"  K{i + 3}  {pred} | {ev} | t\n" for i, (pred, ev) in enumerate(claims))
        text = self.BASE.format(claims=body)
        for old, new in (replace or []):
            assert old in text, f"{old!r} not in fixture"
            text = text.replace(old, new, 1)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(text)
            name = f.name
        return subprocess.run([sys.executable, str(TOOL), name],
                              capture_output=True, text=True)

    def test_reads_happy_path_anchor_checked(self):
        r = self.run_claims([("reads T1 3 on OY", "stem")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_reads_wrong_value_fails(self):
        r = self.run_claims([("reads T1 4 on OY", "stem")])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("reads T1 4 on OY", r.stdout)

    def test_reads_outside_axis_range_fails(self):
        r = self.run_claims([("reads T1 9 on OY", "stem")])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_reads_with_no_axis_fails(self):
        r = self.run_claims([("reads T1 3 on OY", "stem")],
                            replace=[("K1  axis OY from 0 to 5     | stem     | the value axis",
                                      "K1  paint OY solid          | stem     |")])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_reads_ev_stem_value_not_in_stem_fails(self):
        r = self.run_claims([("reads T1 3 on OY", "stem")],
                            replace=[("The chart shows 3 units", "The chart shows three units")])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("not justified by the stem", r.stdout)

    def test_reads_resolves_the_axis_either_way(self):
        r = self.run_claims([("reads T1 3 on YO", "stem")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_reads_undeclared_digit_point_fails_closure(self):
        # T9 parses under the [A-Z]\d* point grammar but is not declared in `points:`
        r = self.run_claims([("reads T9 3 on OY", "stem")])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_nonparallel_axes_sharing_the_origin_passes(self):
        # OX and OY share O — the common case for this claim — and sit 90 deg apart
        r = self.run_claims([("nonparallel OX OY", "inferred")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_nonparallel_on_parallel_anchors_fails(self):
        r = self.run_claims([("nonparallel OX AB", "inferred")])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("nonparallel OX AB", r.stdout)

    def test_nonparallel_tilted_pair_passes(self):
        r = self.run_claims([("nonparallel AB CD", "inferred")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_nonparallel_degenerate_pair_fails(self):
        r = self.run_claims([("nonparallel OX XO", "inferred")])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_numeric_label_on_nonnumeric_target_stays_out_of_the_numeral_set(self):
        # the baseline binds "2008" to cat0 — the printed-numerals check still passes.
        # Rebind it to a numeric name and the strict numeral equality fails instead.
        r = self.run_claims([("nonparallel OX OY", "inferred")],
                            replace=[('K16 label "2008" names cat0', 'K16 label "2008" names 2008')])
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("numeric labels", r.stdout)


if __name__ == "__main__":
    unittest.main()
