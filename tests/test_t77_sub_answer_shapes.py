#!/usr/bin/env python3
"""T-QG-4: t77 must collect a part's staged sub-answers from BOTH `sub_answer` (the singular
object build-staged emits) and `answers` (the canonical list) — publish.ts collectSubAnswers
accepts either, so a live sub_answers row can legitimately come from the singular form.
Reading only `answers[]` reported every published sub_answer as "live row not in staged".

All uuids are the synthetic 00000000-0000-4000-8000-0000000000NN family.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent.parent / "tools"
spec = importlib.util.spec_from_file_location("t77_mod", TOOLS / "t77-staged-vs-published.py")
t77 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t77)

Q1 = "00000000-0000-4000-8000-000000000001"
SQ_A = "00000000-0000-4000-8000-000000000011"
SQ_B = "00000000-0000-4000-8000-000000000012"
SA_A = "00000000-0000-4000-8000-000000000021"
SA_B = "00000000-0000-4000-8000-000000000022"

# Staged doc in the shape build-staged emits: part a carries the SINGULAR `sub_answer`,
# part b the `answers` LIST — publish.ts collects both into the same sub_answers table.
STAGED = {
    "questions": [{
        "question_id": Q1,
        "question_number": 1,
        "question_text": "synthetic stem",
        "question_text_sinhala": None,
        "ingestion_metadata": {"needs_human_review": True},
        "diagram_dsl": None,
        "sub_questions": [
            {"sub_question_id": SQ_A, "label": "a", "sort_order": 0, "text": "part a",
             "text_sinhala": None, "diagram_dsl": None,
             "sub_answer": {"sub_answer_id": SA_A, "approach": "do the sum",
                            "final_answer_latex": "$1 + 1 = 2$"},
             "sub_questions": []},
            {"sub_question_id": SQ_B, "label": "b", "sort_order": 1, "text": "part b",
             "text_sinhala": None, "diagram_dsl": None,
             "answers": [{"sub_answer_id": SA_B, "approach": "halve it",
                          "final_answer_latex": "$4 / 2 = 2$"}],
             "sub_questions": []},
        ],
    }]
}


def live_rows():
    return [{
        "question_id": Q1, "question_number": 1, "question_text": "synthetic stem",
        "question_text_sinhala": None, "needs_human_review": True, "diagram_dsl": None,
        "answers": None,
        "parts": [
            {"sub_question_id": SQ_A, "label": "a", "text": "part a", "text_sinhala": None,
             "sort_order": 0, "parent": None, "diagram_dsl": None,
             "answers": [{"sub_answer_id": SA_A, "approach": "do the sum",
                          "final_answer_latex": "$1 + 1 = 2$", "diagram_dsl": None}]},
            {"sub_question_id": SQ_B, "label": "b", "text": "part b", "text_sinhala": None,
             "sort_order": 1, "parent": None, "diagram_dsl": None,
             "answers": [{"sub_answer_id": SA_B, "approach": "halve it",
                          "final_answer_latex": "$4 / 2 = 2$", "diagram_dsl": None}]},
        ],
    }]


def run_t77(staged_doc, rows):
    """Drive t77.main() in-process: staged via patched open, live rows via a fake psql."""
    out = io.StringIO()
    with patch.dict(os.environ, {"DATABASE_URL": "postgres://fake.invalid/fake"}), \
         patch.object(sys, "argv", ["t77", "staged.json", "--ids", json.dumps([Q1])]), \
         patch.object(t77.subprocess, "run",
                      return_value=subprocess.CompletedProcess([], 0, json.dumps(rows), "")), \
         patch.object(t77, "open", return_value=io.StringIO(json.dumps(staged_doc)), create=True), \
         contextlib.redirect_stdout(out):
        with unittest.TestCase().assertRaises(SystemExit) as exited:
            t77.main()
    return exited.exception.code, out.getvalue()


class T77SubAnswerShapes(unittest.TestCase):
    def test_singular_sub_answer_matches_live(self):
        rc, out = run_t77(STAGED, live_rows())
        self.assertEqual(rc, 0, out)
        self.assertIn("0 mismatch(es)", out)
        self.assertNotIn("live row not in staged", out)

    def test_wrong_field_still_mismatches(self):
        rows = live_rows()
        rows[0]["parts"][0]["answers"][0]["final_answer_latex"] = "$1 + 1 = 3$"
        rc, out = run_t77(STAGED, rows)
        self.assertEqual(rc, 1)
        self.assertIn("MISMATCH", out)
        self.assertIn("1 mismatch(es)", out)


if __name__ == "__main__":
    unittest.main()
