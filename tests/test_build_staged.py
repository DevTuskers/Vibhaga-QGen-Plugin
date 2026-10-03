#!/usr/bin/env python3
"""test_build_staged.py — content.yaml → staged.json builder (golden output, determinism, refusals).

Every fixture is synthetic: English text, 00000000-…-4000-8000-… placeholder lesson uuids. The golden
run is byte-compared against tests/fixtures/staged-golden.json (regenerate with
`python3 tools/build-staged.py tests/fixtures/content.yaml --out tests/fixtures/staged-golden.json`).
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "build-staged.py"
FIXTURE = HERE / "fixtures" / "content.yaml"
GOLDEN = HERE / "fixtures" / "staged-golden.json"
FIG = HERE / "fixtures" / "figures" / "q3.json"

L07 = "00000000-0000-4000-8000-000000000007"
L09 = "00000000-0000-4000-8000-000000000009"
UUID_RE = __import__("re").compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

BASE = {
    "id_seed": "w0-selftest",
    "lessons": {"L07": L07, "L09": L09},
    "figures": {"F1": "figures/q3.json"},
    "questions": [{
        "n": 1, "lessons": ["L07"], "stem": "A cuboid face measures 5 cm by 2 cm.",
        "approach": "length x width", "final": "10 cm^2",
    }],
}


def run_tool(spec_path, out_path):
    return subprocess.run([sys.executable, str(TOOL), str(spec_path), "--out", str(out_path)],
                          capture_output=True, text=True)


class BuildStagedTest(unittest.TestCase):
    def write_spec(self, spec, tmp, name="content.json"):
        p = Path(tmp) / name
        p.write_text(json.dumps(spec), encoding="utf-8")
        return p

    def build(self, spec, tmp):
        spec_path = self.write_spec(spec, tmp)
        out = Path(tmp) / "staged.json"
        return spec_path, out, run_tool(spec_path, out)

    def assert_refuses(self, spec, tmp, needle):
        _, out, r = self.build(spec, tmp)
        self.assertEqual(r.returncode, 2, f"{needle}: expected refusal, got {r.returncode}: {r.stdout} {r.stderr}")
        self.assertIn(needle, r.stderr, f"stderr was: {r.stderr}")
        self.assertFalse(out.exists(), "refused run must not write the doc")

    # ---- happy path -------------------------------------------------------

    def test_golden(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "staged.json"
            r = run_tool(FIXTURE, out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(out.read_bytes(), GOLDEN.read_bytes())

    def test_determinism(self):
        with tempfile.TemporaryDirectory() as tmp:
            one, two = Path(tmp) / "a.json", Path(tmp) / "b.json"
            self.assertEqual(run_tool(FIXTURE, one).returncode, 0)
            self.assertEqual(run_tool(FIXTURE, two).returncode, 0)
            self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_output_passes_publish_local_rules(self):
        """Every staged question flagged, no exam key anywhere, ids are uuids, multipart shape right."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "staged.json"
            self.assertEqual(run_tool(FIXTURE, out).returncode, 0)
            doc = json.loads(out.read_text())
            self.assertEqual(set(doc), {"questions"})
            for q in doc["questions"]:
                self.assertTrue(UUID_RE.match(q["question_id"]))
                self.assertIs(type(q["question_number"]), int)
                self.assertEqual(q.get("ingestion_metadata", {}).get("needs_human_review"), True)
                self.assertNotIn("exam", q)
                self.assertIsNone(q["question_text_sinhala"])
                self.assertTrue(q["lesson_ids"])
                for lid in q["lesson_ids"]:
                    self.assertTrue(UUID_RE.match(lid))
                if q["is_multipart"]:
                    self.assertEqual(q["answers"], [])
                    stack = list(q["sub_questions"])
                    while stack:
                        s = stack.pop()
                        self.assertTrue(UUID_RE.match(s["sub_question_id"]))
                        self.assertTrue(__import__("re").match(r"^[0-9A-Za-z]+$", s["label"]))
                        self.assertNotIn("exam", s)
                        stack += s["sub_questions"]
                        if not s["sub_questions"]:
                            a = s["sub_answer"]
                            self.assertTrue(UUID_RE.match(a["sub_answer_id"]))
                            self.assertTrue(a["approach"] and a["final_answer_latex"])
                else:
                    self.assertNotIn("sub_questions", q)
                    a = q["answers"][0]
                    self.assertTrue(UUID_RE.match(a["answer_id"]))
            # figure key F1 resolved into question 3's diagram_dsl
            self.assertEqual(doc["questions"][2]["diagram_dsl"], json.loads(FIG.read_text()))

    def test_ids_out_round_trips_through_publish_ids_loader(self):
        """--ids-out writes the question_ids in question order, in exactly the shape
        playground-publish.py's load_ids_file accepts (a non-empty list of unique uuids)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "playground_publish", ROOT / "tools" / "playground-publish.py")
        pp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pp)
        with tempfile.TemporaryDirectory() as tmp:
            out, ids = Path(tmp) / "staged.json", Path(tmp) / "ids.json"
            r = subprocess.run([sys.executable, str(TOOL), str(FIXTURE),
                                "--out", str(out), "--ids-out", str(ids)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            want = [q["question_id"] for q in json.loads(out.read_text())["questions"]]
            self.assertTrue(want)
            self.assertEqual(json.loads(ids.read_text()), want)  # raw file: same order
            self.assertEqual(pp.load_ids_file(ids), want)         # and it loads as a publish set

    # ---- refusals (exit 2) ------------------------------------------------

    def test_refuse_duplicate_n(self):
        spec = copy.deepcopy(BASE)
        spec["questions"].append(copy.deepcopy(spec["questions"][0]))
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "duplicate question number")

    def test_refuse_unknown_lesson(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0]["lessons"] = ["L42"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "unknown lesson key")

    def test_refuse_non_uuid_lesson(self):
        spec = copy.deepcopy(BASE)
        spec["lessons"]["L07"] = "lesson-7"
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "not a uuid")

    def test_refuse_unknown_figure_key(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0]["figure"] = "F9"
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "unknown figure key")

    def test_refuse_missing_figure_file(self):
        spec = copy.deepcopy(BASE)
        spec["figures"]["F1"] = "figures/nope.json"
        spec["questions"][0]["figure"] = "F1"
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "not found")

    def test_refuse_depth_3(self):
        spec = copy.deepcopy(BASE)
        leaf = {"label": "i", "text": "…", "approach": "…", "final": "…"}
        deep = {"label": "i", "text": "…", "approach": "…", "final": "…",
                "parts": [{"label": "x", "text": "…", "approach": "…", "final": "…", "parts": [leaf]}]}
        spec["questions"][0] = {"n": 1, "lessons": ["L07"], "stem": "…",
                                "parts": [{"label": "a", "text": "…", "parts": [deep]}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "at most 2 levels")

    def test_refuse_duplicate_sibling_label(self):
        # two parts labelled `a` under one parent collide on the same uuid5 label path —
        # the builder must refuse rather than emit duplicate sub_question_ids.
        spec = copy.deepcopy(BASE)
        spec["questions"][0] = {"n": 1, "lessons": ["L07"], "stem": "…",
                                "parts": [
                                    {"label": "a", "text": "…", "approach": "…", "final": "…"},
                                    {"label": "a", "text": "…", "approach": "…", "final": "…"},
                                ]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "duplicate part label")

    def test_refuse_duplicate_nested_label(self):
        # same collision one level down — grandchildren of `a`.
        spec = copy.deepcopy(BASE)
        spec["questions"][0] = {"n": 1, "lessons": ["L07"], "stem": "…",
                                "parts": [{"label": "a", "text": "…", "parts": [
                                    {"label": "i", "text": "…", "approach": "…", "final": "…"},
                                    {"label": "i", "text": "…", "approach": "…", "final": "…"},
                                ]}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "duplicate part label")

    def test_same_label_under_different_parents_is_fine(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0] = {"n": 1, "lessons": ["L07"], "stem": "…",
                                "parts": [
                                    {"label": "a", "text": "…", "parts": [
                                        {"label": "i", "text": "…", "approach": "…", "final": "…"}]},
                                    {"label": "b", "text": "…", "parts": [
                                        {"label": "i", "text": "…", "approach": "…", "final": "…"}]},
                                ]}
        with tempfile.TemporaryDirectory() as tmp:
            _, out, r = self.build(spec, tmp)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_refuse_leaf_without_answer(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0] = {"n": 1, "lessons": ["L07"], "stem": "…",
                                "parts": [{"label": "a", "text": "…"}]}
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "leaf part needs")

    def test_refuse_parts_plus_whole_answer(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0]["parts"] = [{"label": "a", "text": "…", "approach": "…", "final": "…"}]
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "either parts OR a whole answer")

    def test_refuse_non_bare_labels(self):
        for label in ["(a)", "a)", "a.", "(i)", "a :"]:
            spec = copy.deepcopy(BASE)
            spec["questions"][0] = {"n": 1, "lessons": ["L07"], "stem": "…",
                                    "parts": [{"label": label, "text": "…", "approach": "…", "final": "…"}]}
            with tempfile.TemporaryDirectory() as tmp:
                self.assert_refuses(spec, tmp, "BARE")

    def test_refuse_missing_id_seed(self):
        spec = copy.deepcopy(BASE)
        del spec["id_seed"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "id_seed")

    def test_refuse_empty_questions(self):
        spec = copy.deepcopy(BASE)
        spec["questions"] = []
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "nonempty")

    def test_refuse_unknown_keys(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0]["stemp"] = "typo"
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "unknown question keys")

    def test_refuse_lone_approach(self):
        spec = copy.deepcopy(BASE)
        del spec["questions"][0]["final"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "as a pair")

    # ---- actor-only leaf keys: check / level (W10) --------------------------

    def test_check_and_level_keys_never_reach_staged(self):
        """Golden: staged output is byte-identical whether or not the leaves carry
        `check:`/`level:` — the keys are actor-only, never emitted."""
        import yaml
        spec = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
        spec["questions"][0]["check"] = "5 * 2 == 10"
        spec["questions"][0]["level"] = "R"
        nested = spec["questions"][1]["parts"][1]["parts"][0]
        nested["check"] = "10 / 2 == 5"
        nested["level"] = "M"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "figures").mkdir()          # figure paths resolve beside the spec
            (Path(tmp) / "figures" / "q3.json").write_bytes(FIG.read_bytes())
            spec_path = Path(tmp) / "content.yaml"
            spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
                                 encoding="utf-8")
            a, b = Path(tmp) / "plain.json", Path(tmp) / "with-keys.json"
            self.assertEqual(run_tool(FIXTURE, a).returncode, 0)
            self.assertEqual(run_tool(spec_path, b).returncode, 0)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_bad_level_refused(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0]["level"] = "X"
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "one of R, M, H")

    def test_nonstring_check_refused(self):
        spec = copy.deepcopy(BASE)
        spec["questions"][0]["check"] = ["40 * 23 == 920"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "string expression")

    def test_meta_keys_on_a_container_are_refused(self):
        """`check:`/`level:` on a node WITH parts would be silently ignored — the walkers
        only visit leaves — so build-staged refuses instead of letting it look checked."""
        spec = copy.deepcopy(BASE)
        spec["questions"][0]["parts"] = [
            {"label": "a", "text": "t", "approach": "x", "final": "1"}]
        del spec["questions"][0]["approach"], spec["questions"][0]["final"]
        spec["questions"][0]["check"] = "1 == 1"
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec, tmp, "leaf-only")
        spec2 = copy.deepcopy(BASE)
        spec2["questions"][0]["parts"] = [
            {"label": "a", "text": "t", "level": "M", "parts": [
                {"label": "i", "text": "t", "approach": "x", "final": "1"}]}]
        del spec2["questions"][0]["approach"], spec2["questions"][0]["final"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refuses(spec2, tmp, "leaf-only")


if __name__ == "__main__":
    unittest.main()
