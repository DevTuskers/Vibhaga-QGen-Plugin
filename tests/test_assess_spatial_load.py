#!/usr/bin/env python3
"""test_assess_spatial_load.py — Unit tests for Cognitive Decoding & Spatial Imagery Index (CDS)."""
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

spec = importlib.util.spec_from_file_location("asl", ROOT / "tools" / "assess-spatial-load.py")
asl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(asl)


class TestAssessSpatialLoad(unittest.TestCase):
    def test_low_load_passes(self):
        text = "රේඛාවක දිග $10$ cm වේ. එහි මැද ලක්ෂ්‍යය $M$ නම්, එක් කෙළවරක සිට $M$ ට දුර සොයන්න."
        res = asl.assess_question_text(text, grade=7)
        self.assertLessEqual(res["raw_cds"], 3)
        self.assertEqual(res["status"], "PASS")

    def test_high_load_coordinate_grid_fails_grade_7(self):
        text = (
            "වෙසක් කූඩුවක සිරස් සමමිති අක්ෂයක් ඇත.\n"
            "A, අක්ෂයට 6 cm වමින් සහ 10 cm පහළින්.\n"
            "B, අක්ෂයට 6 cm දකුණින් සහ 10 cm පහළින්.\n"
            "C, අක්ෂයට 4 cm වමින් සහ 12 cm පහළින්.\n"
            "D, අක්ෂයට 4 cm දකුණින් සහ 12 cm පහළින්.\n"
            "E, අක්ෂයට 6 cm දකුණින් සහ 12 cm පහළින්."
        )
        res = asl.assess_question_text(text, grade=7, has_diagram=False)
        self.assertGreaterEqual(res["raw_cds"], 7)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("exceeds Grade 7 benchmark", res["recommendations"][0])

    def test_diagram_reduces_effective_load(self):
        text = (
            "වෙසක් කූඩුවක සිරස් සමමිති අක්ෂයක් ඇත.\n"
            "A, අක්ෂයට 6 cm වමින් සහ 10 cm පහළින්.\n"
            "B, අක්ෂයට 6 cm දකුණින් සහ 10 cm පහළින්.\n"
            "C, අක්ෂයට 4 cm වමින් සහ 12 cm පහළින්.\n"
            "D, අක්ෂයට 4 cm දකුණින් සහ 12 cm පහළින්."
        )
        res_no_diag = asl.assess_question_text(text, grade=7, has_diagram=False)
        res_diag = asl.assess_question_text(text, grade=7, has_diagram=True)
        self.assertLess(res_diag["effective_cds"], res_no_diag["effective_cds"])
        self.assertEqual(res_diag["status"], "PASS")

    def test_benchmarks_monotonic_progression(self):
        benchmarks = asl.GRADE_BENCHMARKS
        for g in range(6, 13):
            self.assertLessEqual(
                benchmarks[g]["max_text_cds"],
                benchmarks[g + 1]["max_text_cds"],
                f"Benchmark for Grade {g} should not exceed Grade {g+1}",
            )


if __name__ == "__main__":
    unittest.main()
