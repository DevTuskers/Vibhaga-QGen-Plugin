#!/usr/bin/env python3
"""tests/test_precritic_lint.py — offline tests for tools/precritic-lint.py (W9 item G).

Synthetic fixtures only: a hand-written scope card (English filler, no real lesson text) under
<tmp>/cards/, a content.yaml with toy stems, and a synthetic claims file. --cards-dir keeps the
corpus out of the loop entirely.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "tools" / "precritic-lint.py"

CARD = """\
schema_version: 1
grade: 6
subject: Mathematics
medium: si
lesson_number: 7
title_en: Fractions
title_si: Fractions (si)
syllabus_refs: ["1.1"]
term: 1
periods: 2
source: {file: "lessons/07-Fractions.md", sha256: "0000000000000000000000000000000000000000000000000000000000000001"}
generated:
  sections:
    - {number: "1.1", title: "Naming fractions"}
    - {number: "1.2", title: "Equivalent fractions"}
  vocabulary: ["fraction", "numerator", "denominator"]
  worked_examples: []
  exercises: []
  activities: []
  figure_kinds: []
  figures: 0
  tables: 0
  summary: []
curated:
  status: drafted
  not_taught:
    - {concept: "improper fractions", why: "unit fractions only here", probes: ["improper", "top-heavy"]}
    - {concept: "decimals", why: "next lesson", probes: ["decimal point"]}
  prerequisites: []
  difficulty_hooks:
    - {level: "M", hook: "equal parts vs equal count"}
    - {level: "H", hook: "a folded-strip proof"}
"""

CLAIMS = """\
claims:
  K1  shaded 3 of 5 cells | inferred | the fully shaded cells
"""

CLAIMS_LINE = """\
claims:
  K1  axis AB from 730 to 750 | stem | endpoints
  K2  at 745 @P | inferred | the marked point
"""

# the same `at` claim in the written-file dialect — @anchor resolved to coordinates
CLAIMS_LINE_COORDS = """\
claims:
  K1  axis AB from 730 to 750 | stem | endpoints
  K2  at 745 380.00 62.94 | inferred | the marked point
"""

CLAIMS_PICTO = """\
claims:
  K1  describe "row Mon shows 2 symbols — 4 items at 2 per symbol" | inferred | reads off
"""


def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def make_run(tmp: Path, stem: str = "Shade the strip.", parts=None, approach=None,
             final=None, lessons=None) -> Path:
    run = tmp / "run"
    run.mkdir(parents=True, exist_ok=True)
    q = {"n": 1, "lessons": lessons if lessons is not None else ["L07"], "stem": stem}
    if approach is not None:
        q["approach"] = approach
    if final is not None:
        q["final"] = final
    if parts is not None:
        q["parts"] = parts
    import yaml
    write(run / "content.yaml",
          yaml.safe_dump({"id_seed": "synthetic", "lessons": {"L07": "placeholder"},
                          "questions": [q]}, allow_unicode=True, sort_keys=False))
    cards = tmp / "cards"
    write(cards / "07-Fractions.yaml", CARD)
    return run


def lint(run: Path, tmp: Path, *extra):
    return subprocess.run(
        [sys.executable, str(TOOL), str(run), "--card", "L07=7", "--grade", "6",
         "--cards-dir", str(tmp / "cards"), *extra],
        capture_output=True, text=True)


class PrecriticLintTest(unittest.TestCase):
    # ---- (a) not_taught probes ----------------------------------------------
    def test_probe_in_stem_fails(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td), stem="Write the improper fraction shown.")
            r = lint(run, Path(td))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("FAIL Q1", r.stdout)
            self.assertIn("improper", r.stdout)
            self.assertIn("1 fail(s)", r.stdout)

    def test_probe_in_part_approach_fails_and_names_the_part(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td), parts=[
                {"label": "a", "text": "Name the fraction.",
                 "approach": "A top-heavy fraction, so …", "final": "5/3"},
            ])
            r = lint(run, Path(td))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("FAIL Q1.a", r.stdout)
            self.assertIn("top-heavy", r.stdout)

    def test_probe_case_insensitive_and_absent_is_clean(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td), stem="IMPROPER behaviour is off-topic only in prose.")
            r = lint(run, Path(td))
            self.assertEqual(r.returncode, 1)  # substring, ASCII-folded — still fires
            run2 = make_run(Path(td) / "clean", stem="Shade the strip.", lessons=["L07"])
            r2 = lint(run2, Path(td))
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

    # ---- (b) a11y description must not hand over the readable value ---------
    def test_description_digit_matching_a_claim_value_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            write(run / "specs" / "figures.json",
                  '[{"template": "shaded_grid", "figure_id": "Q1", '
                  '"description": "A strip with 3 shaded cells."}]')
            write(run / "figures" / "Q1-claims.txt", CLAIMS)
            r = lint(run, tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)   # warn never blocks
            self.assertIn("WARN Q1", r.stdout)
            self.assertIn("'3'", r.stdout)
            self.assertIn("T125", r.stdout)

    def test_description_digit_not_carried_by_the_figure_is_quiet(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            write(run / "specs" / "figures.json",
                  '[{"template": "shaded_grid", "figure_id": "Q1", '
                  '"description": "A strip of equal squares; 2 halves make a whole."}]')
            write(run / "figures" / "Q1-claims.txt", CLAIMS)
            r = lint(run, tmp)
            self.assertNotIn("WARN Q1 description", r.stdout)

    def test_number_line_at_and_pictograph_counts_warn(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            write(run / "specs" / "figures.json",
                  '[{"template": "number_line", "figure_id": "Q1", '
                  '"description": "A line marked from 730 to 750 with P at 745."},'
                  ' {"template": "pictograph", "figure_id": "Q2", '
                  '"description": "Rows of books; Monday has 4."}]')
            write(run / "figures" / "Q1-claims.txt", CLAIMS_LINE)
            write(run / "figures" / "Q2-claims.txt", CLAIMS_PICTO)
            r = lint(run, tmp)
            self.assertIn("'745'", r.stdout)          # the `at` value
            self.assertNotIn("'730'", r.stdout)       # axis endpoints are not `at` values
            self.assertIn("'4'", r.stdout)            # the pictograph row's item count

    def test_at_claim_in_the_coordinate_dialect_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            write(run / "specs" / "figures.json",
                  '[{"template": "number_line", "figure_id": "Q1", '
                  '"description": "A line marked from 730 to 750 with P at 745."}]')
            write(run / "figures" / "Q1-claims.txt", CLAIMS_LINE_COORDS)
            r = lint(run, tmp)
            self.assertIn("'745'", r.stdout)
            self.assertNotIn("'730'", r.stdout)

    def test_pictograph_prose_at_does_not_read_as_a_point(self):
        # "… items at 2 per symbol" prose must NOT register 2 as a readable `at` value
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            write(run / "specs" / "figures.json",
                  '[{"template": "pictograph", "figure_id": "Q1", '
                  '"description": "A pictograph with a key of 2."}]')
            write(run / "figures" / "Q1-claims.txt",
                  'claims:\n  K1  describe "pens at 2 per box" | inferred | prose\n')
            r = lint(run, tmp)
            self.assertNotIn("WARN Q1 description", r.stdout)

    def test_missing_specs_file_skips_check_b(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            r = lint(run, tmp)
            self.assertIn("check (b) skipped", r.stdout)

    # ---- (c) tagged but none of the card's words appear ---------------------
    def test_tagged_question_with_no_card_vocabulary_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[
                {"label": "a", "text": "Count the cells.", "approach": "There are 5."},
            ])
            r = lint(run, tmp)
            self.assertEqual(r.returncode, 0)
            self.assertIn("heuristic", r.stdout)
            self.assertIn("WARN Q1 tags L07", r.stdout)

    def test_vocabulary_term_in_a_part_is_quiet(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[
                {"label": "a", "text": "Write the fraction.", "approach": "count over total"},
            ])
            r = lint(run, tmp)
            self.assertNotIn("WARN Q1 tags", r.stdout)

    def test_partless_question_uses_its_own_fields(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, stem="Colour the numerator.", approach=None, final="2")
            r = lint(run, tmp)
            self.assertNotIn("WARN Q1 tags", r.stdout)   # stem carries "numerator"

    # ---- usage ---------------------------------------------------------------
    def test_bad_card_spec_and_missing_card_die(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            r = subprocess.run([sys.executable, str(TOOL), str(run), "--card", "BAD", "--grade", "6",
                                "--cards-dir", str(tmp / "cards")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("KEY=NN", r.stderr)
            r = subprocess.run([sys.executable, str(TOOL), str(run), "--card", "L07=99", "--grade", "6",
                                "--cards-dir", str(tmp / "cards")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("0 card(s) match", r.stderr)


if __name__ == "__main__":
    unittest.main()
