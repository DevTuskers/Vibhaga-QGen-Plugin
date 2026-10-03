#!/usr/bin/env python3
"""test_blueprint.py — offline suite for tools/blueprint.py (W10d).

Synthetic fixture tests/fixtures/blueprint.yaml only (English filler — public repo). The tool is
run as a subprocess for CLI/exit-code behaviour; the module is also imported in-process for the
cheap sweeps (50 seeds, determinism) so the suite does not rebuild the figure 50 times.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL = ROOT / "tools" / "blueprint.py"
BUILD_STAGED = ROOT / "tools" / "build-staged.py"
CHECK_ANSWERS = ROOT / "tools" / "check-answers.py"
VDD_TEMPLATES = ROOT / "tools" / "vdd_templates.py"
FIXTURE = HERE / "fixtures" / "blueprint.yaml"
CONTENT_FIXTURE = HERE / "fixtures" / "content.yaml"

_spec = importlib.util.spec_from_file_location("blueprint", TOOL)
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)


def run_tool(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


def instantiate_fixture(seed=7, n=3, tmp=None, *extra):
    """CLI instantiate against the fixture; `tmp` gives the run a scratch dir for --spec-out."""
    args = ["instantiate", str(FIXTURE), "--seed", str(seed), "--n", str(n)]
    return run_tool(*args, *extra)


def write_variant(tmp: Path, mutate) -> Path:
    """The fixture with `mutate(doc['blueprint'])` applied — each test needs a near-copy."""
    doc = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    mutate(doc["blueprint"])
    p = Path(tmp) / "variant.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return p


def instantiate_variant(tmp: Path, mutate, seed=7, n=3):
    p = write_variant(Path(tmp), mutate)
    return run_tool("instantiate", str(p), "--seed", str(seed), "--n", str(n))


class BlueprintTest(unittest.TestCase):
    # ---- sampling + determinism --------------------------------------------
    def test_same_seed_byte_identical(self):
        r1 = instantiate_fixture(seed=7)
        r2 = instantiate_fixture(seed=7)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertEqual(r1.stdout, r2.stdout)

    def test_two_seeds_differ(self):
        outs = {instantiate_fixture(seed=s).stdout for s in range(1, 8)}
        self.assertGreater(len(outs), 1)

    def test_fifty_seeds_all_satisfy_where(self):
        spec = bp.load_blueprint(str(FIXTURE))
        for seed in range(50):
            _q, fig = bp.instantiate(spec, seed, 3)
            self.assertGreater(fig["length"], fig["width"] + 1, f"seed {seed}")

    def test_impossible_where_gives_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b.__setitem__("where", ["ln < 0"]))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("2000", r.stderr)

    # ---- slot rules ---------------------------------------------------------
    def test_slot_inside_text_group_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(
                tmp, lambda b: b["question"].__setitem__(
                    "stem", "A rectangle $\\text{ln}$ by ${wd}$."))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("ambiguous", r.stderr)

    def test_other_brace_groups_untouched(self):
        r = instantiate_fixture(seed=7)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("\\text{cm}", r.stdout)           # {cm} is not a declared name

    def test_whole_slot_becomes_typed_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_out = Path(tmp) / "specs" / "figures.json"
            r = run_tool("instantiate", str(FIXTURE), "--seed", "7", "--n", "3",
                         "--spec-out", str(spec_out))
            self.assertEqual(r.returncode, 0, r.stderr)
            spec = json.loads(spec_out.read_text(encoding="utf-8"))[0]
            self.assertIsInstance(spec["length"], int)          # "{ln}" → typed, not "16"
            self.assertIsInstance(spec["width"], int)
            self.assertEqual(spec["figure_id"], "Q3")
            self.assertIn("16", spec["stem"])

    def test_whole_slot_in_question_tree_stays_a_string(self):
        """`final: "{per}"` must emit the formatted STRING — typed values are a figure-spec
        rule; a non-string final would fail build-staged's leaf validation."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            def mutate(b):
                b["question"]["parts"][0]["final"] = "{per}"
                b.pop("figure")                     # no figure → no figures: entry needed
            p = write_variant(tmp, mutate)
            r = run_tool("instantiate", str(p), "--seed", "7", "--n", "1")
            self.assertEqual(r.returncode, 0, r.stderr)
            item = yaml.safe_load(r.stdout)[0]
            self.assertIsInstance(item["parts"][0]["final"], str)
            self.assertRegex(item["parts"][0]["final"], r"^\d+$")
            spec = {"id_seed": "w10d-test",
                    "lessons": {"L07": "00000000-0000-4000-8000-000000000007"},
                    "questions": [item]}
            c = tmp / "content.json"
            c.write_text(json.dumps(spec), encoding="utf-8")
            rb = subprocess.run([sys.executable, str(BUILD_STAGED), str(c),
                                 "--out", str(tmp / "staged.json")],
                                capture_output=True, text=True)
            self.assertEqual(rb.returncode, 0, rb.stderr)

    def test_undeclared_slot_refused_but_latex_groups_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b["question"].__setitem__(
                "stem", "perimeter {perx}."))         # perx is not declared — a typo
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("undeclared slot {perx}", r.stderr)
            # slot-shaped LaTeX groups are not slots: \command{, x^{…}, a_{…}, after }
            r = instantiate_variant(tmp, lambda b: b["question"].__setitem__(
                "stem", "A {ln} by {wd} rect: $x^{ab}$ $a_{bc}$ $\\frac{cd}{ef}$ $\\text{cm}$."))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("x^{ab}", r.stdout)          # untouched

    def test_short_and_capital_slots_refused(self):
        """`{l}`/`{L}`/`{Ln}` are slot-shaped (any case, 1+ chars) — undeclared in plain text
        they are refused, not passed verbatim into the stem."""
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("{l}", "{L}", "{Ln}"):
                r = instantiate_variant(tmp, lambda b, s=bad: b["question"].__setitem__(
                    "stem", f"A {{ln}} by {{wd}} rect, side {s}."))
                self.assertEqual(r.returncode, 2, f"{bad}: {r.stdout} {r.stderr}")
                self.assertIn("undeclared slot", r.stderr)
            # but the same shape inside LaTeX grouping is not a slot at all
            r = instantiate_variant(tmp, lambda b: b["question"].__setitem__(
                "stem", "A {ln} by {wd} rect; $x^{n}$ and $\\mathbf{A}$."))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("x^{n}", r.stdout)

    def test_non_mapping_part_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b["question"]["parts"].append("oops"))
            self.assertEqual(r.returncode, 2)
            self.assertIn("not a mapping", r.stderr)

    def test_declared_slot_keeps_braces_after_super_subscript(self):
        """`x^{ln}` must emit `x^{12}` — the braces are LaTeX grouping, not slot syntax."""
        with tempfile.TemporaryDirectory() as tmp:
            def mutate(b):
                b["params"]["ln"] = {"choices": [12]}        # fixed 2-digit draw
                b["question"]["stem"] = "A {ln} by {wd} rect; $x^{ln}$ and $a_{wd}$."
            r = instantiate_variant(tmp, mutate)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("x^{12}", r.stdout)
            self.assertNotIn("x^12", r.stdout)

    def test_parts_deeper_than_two_refused_at_load(self):
        """build-staged's depth rule, mirrored: a part's part cannot itself have parts."""
        with tempfile.TemporaryDirectory() as tmp:
            def mutate(b):
                b["question"]["parts"][0] = {
                    "label": "a", "text": "t",
                    "parts": [{"label": "i", "text": "t",
                               "parts": [{"label": "x", "text": "t", "approach": "x",
                                          "final": "1", "check": "1 == 1"}]}]}
            r = instantiate_variant(tmp, mutate)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("2 levels", r.stderr)

    def test_forged_question_keys_refused(self):
        """`n`, `blueprint_id`, `blueprint_seed`, `figure` inside question: — provenance and
        numbering are emitted by the tool, never authored."""
        with tempfile.TemporaryDirectory() as tmp:
            for key, val in [("n", 9), ("blueprint_id", "other-bp"),
                             ("blueprint_seed", 9), ("figure", "fx")]:
                r = instantiate_variant(tmp, lambda b, k=key, v=val:
                                        b["question"].__setitem__(k, v))
                self.assertEqual(r.returncode, 2, f"{key}: {r.stdout} {r.stderr}")

    # ---- expressions --------------------------------------------------------
    def test_unknown_name_in_where_and_derived_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b.__setitem__("where", ["xx > 0"]))
            self.assertEqual(r.returncode, 2)
            self.assertIn("unknown name", r.stderr)
            r = instantiate_variant(tmp, lambda b: b["derived"].__setitem__("per", "zz * 2"))
            self.assertEqual(r.returncode, 2)
            self.assertIn("unknown name", r.stderr)

    def test_whitelist_not_loosened(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(
                tmp, lambda b: b["derived"].__setitem__("per", "__import__('os')"))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            r = instantiate_variant(
                tmp, lambda b: b["derived"].__setitem__("per", "ln . real if False else 1"))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            r = instantiate_variant(
                tmp, lambda b: b["derived"].__setitem__("per", "(ln).__class__"))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_non_exact_derived_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(
                tmp, lambda b: b["derived"].__setitem__("per", "ln / 3 + wd"))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("is not exact", r.stderr)
            self.assertIn("tighten the constraints", r.stderr)

    def test_non_finite_choice_and_derived_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b["params"]["wd"].__setitem__(
                "choices", [3, float("inf")]))
            self.assertEqual(r.returncode, 2)
            self.assertIn("finite", r.stderr)
            r = instantiate_variant(tmp, lambda b: b["derived"].__setitem__(
                "per", "1e400"))                       # evaluates to inf — non-finite
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_derived_forward_reference_refused(self):
        """derived names resolve in order — a forward reference is an unknown name."""
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b.__setitem__(
                "derived", {"fwd": "per + 1", "per": "2 * (ln + wd)"}))
            self.assertEqual(r.returncode, 2)
            self.assertIn("unknown name", r.stderr)

    def test_non_bool_where_refused_fast(self):
        """A `where` that is not a comparison refuses on the first draw — no 2000-draw loop."""
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b.__setitem__("where", ["ln + wd"]))
            self.assertEqual(r.returncode, 2)
            self.assertIn("True/False", r.stderr)
            self.assertNotIn("2000", r.stderr)

    # ---- leaf checks --------------------------------------------------------
    def test_no_check_leaf_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(
                tmp, lambda b: b["question"]["parts"][0].__delitem__("check"))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("check", r.stderr)

    def test_false_check_exits_1_naming_seed_and_leaf(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(
                tmp, lambda b: b["question"]["parts"][0].__setitem__(
                    "check", "{per} + 1 == {per}"), seed=11)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("seed 11", r.stderr)
            self.assertIn("'a'", r.stderr)                      # the leaf label

    # ---- --spec-out -----------------------------------------------------------
    def test_spec_out_merge_and_duplicate_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_out = Path(tmp) / "specs" / "figures.json"
            existing = Path(tmp) / "specs2.json"
            existing.write_text(json.dumps(
                [{"template": "number_line", "figure_id": "Q1", "stem": "s",
                  "v0": 0, "v1": 3, "parts_per_unit": 10, "points": {"P": 0.4}}]),
                encoding="utf-8")
            r = run_tool("instantiate", str(FIXTURE), "--seed", "7", "--n", "3",
                         "--spec-out", str(existing))
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = json.loads(existing.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]["figure_id"], "Q3")
            # same figure_id again → refused
            r = run_tool("instantiate", str(FIXTURE), "--seed", "7", "--n", "3",
                         "--spec-out", str(existing))
            self.assertEqual(r.returncode, 2)
            self.assertIn("duplicate", r.stderr)

    def test_template_error_is_a_refusal(self):
        """A figure spec the template refuses (a length the stem never states) → exit 2,
        carrying the TemplateError message — caught here, not at run-gates."""
        with tempfile.TemporaryDirectory() as tmp:
            r = instantiate_variant(tmp, lambda b: b["figure"].__setitem__("length", 999))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("999", r.stderr)

    def test_n_must_be_positive(self):
        r = run_tool("instantiate", str(FIXTURE), "--seed", "7", "--n", "0")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--n", r.stderr)

    # ---- the emitted item is a real content.yaml question --------------------
    def test_emitted_item_passes_build_staged_and_check_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copytree(HERE / "fixtures" / "figures", tmp / "figures")   # F1 → q3.json
            # instantiate with --spec-out, then build that spec into figures/Q4.json
            r = run_tool("instantiate", str(FIXTURE), "--seed", "7", "--n", "4",
                         "--spec-out", str(tmp / "specs" / "figures.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("# figures: add  Q4: figures/Q4.json"))
            rb = subprocess.run(
                [sys.executable, str(VDD_TEMPLATES), "build",
                 str(tmp / "specs" / "figures.json"), "--out", str(tmp / "figures")],
                capture_output=True, text=True)
            self.assertEqual(rb.returncode, 0, rb.stdout + rb.stderr)
            # paste the item under the fixture's questions, with the figures: entry it names
            content = yaml.safe_load(CONTENT_FIXTURE.read_text(encoding="utf-8"))
            item_text = r.stdout.splitlines(keepends=True)
            item_text = "".join(l for l in item_text if not l.startswith("#"))
            item = yaml.safe_load(item_text)[0]
            self.assertEqual(item["n"], 4)
            self.assertEqual(item["blueprint_id"], "rect-perimeter")
            self.assertEqual(item["blueprint_seed"], 7)
            self.assertEqual(item["figure"], "Q4")
            content["questions"].append(item)
            content["figures"]["Q4"] = "figures/Q4.json"
            (tmp / "content.yaml").write_text(
                yaml.safe_dump(content, sort_keys=False, allow_unicode=True), encoding="utf-8")
            # build-staged + check-answers over the appended spec
            staged = tmp / "staged.json"
            r = subprocess.run([sys.executable, str(BUILD_STAGED), str(tmp / "content.yaml"),
                                "--out", str(staged)], capture_output=True, text=True,
                               cwd=tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            doc = json.loads(staged.read_text(encoding="utf-8"))
            self.assertNotIn("blueprint", json.dumps(doc))      # actor-only, never emitted
            r = subprocess.run([sys.executable, str(CHECK_ANSWERS), str(tmp / "content.yaml")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
