import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import vdd_templates as vt
import vdd_g9_apparatus as apparatus


class ApparatusTests(unittest.TestCase):
    def vessel(self, **kwargs):
        spec = dict(figure_id="synthetic-1-vessel", stem="A scale holds 80 ml with 20 ml divisions and a reading of 30 ml.",
                    capacity=80, step=20, reading=30)
        return apparatus.build_graduated_vessel(**dict(spec, **kwargs))

    def audit(self, built):
        with tempfile.TemporaryDirectory() as tmp:
            paths = built.write(tmp)
            result = subprocess.run([sys.executable, str(TOOLS / "audit-claim-set.py"), str(paths["claims"])],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_audit_modes_and_extremes(self):
        for reading in (0, 10, 30, 80):
            with self.subTest(reading=reading):
                self.audit(self.vessel(reading=reading, values="figure"))
        self.audit(self.vessel())
        self.audit(self.vessel(values="figure", stem="The scale holds 80 ml in steps of 20 ml."))
        with self.assertRaises(vt.TemplateError):
            self.vessel(stem="The scale holds 80 ml in steps of 20 ml.")
        for operand in (0, 7, 17, 999):
            self.audit(apparatus.build_calculator_square(figure_id="synthetic-1-keys",
                       stem=f"Square {operand} using the keys.", operand=operand))

    def test_key_families_and_results(self):
        examples = [([0, "x²"], 0), ([1, "x²"], 1), ([12, "+", 8], 20), ([19, "−", 7], 12),
                    ([2.4, "×", 1.5], 3.6), ([18, "÷", 4], 4.5),
                    ([60, "+", 8, "÷", 4], 62),
                    ([320, "×", 15, "SHIFT", "="], 48),
                    ([3, "÷", 12, "SHIFT", "="], 25),
                    ([45, "×", 20, "%"], 9),
                    (["√", 2.56], 1.6), (["√", "(", 6, "x²", "+", 8, "x²", ")"], 10),
                    ([4.2, "x²", "+", 3, "x²"], 26.64)]
        for expression, expected in examples:
            stem = "Operands " + " ".join(str(x) for x in expression if isinstance(x, (int, float))) + "."
            with self.subTest(expression=expression):
                built = apparatus.build_calculator_keys(figure_id="synthetic-1-flow", stem=stem,
                           keys=["AC", *expression, "="], result=expected)
                self.audit(built)
                self.assertNotIn(str(expected), built.doc["a11y"]["description"])
        self.audit(apparatus.build_calculator_keys(figure_id="synthetic-1-immediate", stem="Operands 60 8 4.",
                   keys=["ON", 60, "+", 8, "÷", 4, "="], result=17, evaluation="immediate"))
        self.audit(self.vessel(capacity=100, step=10, reading=35, values="figure",
                              stem="Scale capacity 100 ml with step 10 ml."))

    def test_key_refusals(self):
        bad_expressions = [[True, "+", 2], ["12", "+", 2], [float("nan")], [float("inf")],
                           [10**1000], [0.0000001], [2, "**", 4], ["__import__"],
                           [2, "SHIFT", "+", 4], [2, "=", 4], [2, "÷", 0],
                           ["√", "(", 2, "−", 4, ")"], ["(", 2, "+", 4],
                           [2, 4], [2, ")"], [2, "+"], [2, "ON", 4]]
        for expression in bad_expressions:
            with self.subTest(expression=repr(expression)[:60]), self.assertRaises(vt.TemplateError):
                apparatus.build_calculator_keys(figure_id="synthetic-1-bad", stem="Operands 0 2 4 12.",
                                                keys=["ON", *expression, "="])
        for kwargs in (dict(result=5), dict(result=True), dict(result="6"), dict(evaluation="unknown"),
                       dict(stem="No numbers.")):
            spec = dict(figure_id="synthetic-1-bad", stem="Operands 2 4.", keys=["ON", 2, "+", 4, "="])
            with self.assertRaises(vt.TemplateError):
                apparatus.build_calculator_keys(**dict(spec, **kwargs))
        with self.assertRaises(vt.TemplateError):
            self.vessel(unit="gal")

    def test_bad_numbers_before_conversion(self):
        for name in ("capacity", "step", "reading"):
            for bad in (True, "20", None, float("nan"), float("inf"), -1, 10**1000):
                with self.subTest(name=name, bad=repr(bad)[:20]), self.assertRaises(vt.TemplateError):
                    self.vessel(**{name: bad})
        for bad in (True, "7", None, float("nan"), float("inf"), -1, 1000, 2.5, 10**1000):
            with self.assertRaises(vt.TemplateError):
                apparatus.build_calculator_square(figure_id="synthetic-1-bad", stem="Square 7.", operand=bad)

    def test_missing_givens_and_lattice(self):
        for kwargs in (dict(stem="Read it."), dict(reading=31), dict(capacity=81),
                       dict(step=1), dict(values="other"), dict(reading=90)):
            with self.assertRaises(vt.TemplateError):
                self.vessel(**kwargs)
        with self.assertRaises(vt.TemplateError):
            apparatus.build_calculator_square(figure_id="synthetic-1-bad", stem="Square a number.", operand=7)

    def test_computed_geometry_and_no_answer_leak(self):
        captured = None
        with patch.object(vt, "finish", side_effect=lambda **kw: kw):
            captured = self.vessel(values="figure")
        self.assertEqual(captured["anchors"]["P"], (110, 150))
        self.assertIn(("reads P 30 on OY", "inferred", "horizontal liquid surface meets the calibrated scale"), captured["claims"])
        self.assertNotIn("30", captured["description"])
        built = apparatus.build_calculator_square(figure_id="synthetic-1-square", stem="Square 17.", operand=17)
        self.assertNotIn("289", built.doc["a11y"]["description"])
        self.assertFalse(any(e.get("value") == "289" for e in built.doc["elements"]))

    def test_percent_restrictions(self):
        refused = ([200, "+", 15, "%"], [2, "−", 10, "%"], ["√", 16, "%"],
                   [16, "×", "√", 16, "%"], [4, "×", "(", 2, "+", 3, ")", "%"],
                   [10, "×", 25, "%", "%"], [200, "+", 15, "SHIFT", "=", "="])
        for expression in refused:
            with self.subTest(expression=repr(expression)), self.assertRaises(vt.TemplateError):
                apparatus.build_calculator_keys(figure_id="synthetic-1-pct", stem="Operands 200 15 2 10 4 16 3 25.",
                                                keys=["ON", *expression, "="])
        self.audit(apparatus.build_calculator_keys(figure_id="synthetic-1-pctok",
                   stem="Operands 480 and 25.", keys=["ON", 480, "×", 25, "SHIFT", "=", "="], result=120))

    def test_immediate_mode_is_ordinary_calculator(self):
        for key in ("x²", "√", "(", ")", "%", "SHIFT"):
            with self.subTest(key=key), self.assertRaises(vt.TemplateError):
                apparatus.build_calculator_keys(figure_id="synthetic-1-imm", stem="Operands 60 8 4.",
                                                keys=["ON", 60, "+", key, 4, "="], evaluation="immediate")
        with self.assertRaises(vt.TemplateError):
            apparatus.build_calculator_keys(figure_id="synthetic-1-imm", stem="Operands 60 8 4.",
                                            keys=["ON", 60, "+", "(", 8, "÷", 4, ")", "="],
                                            evaluation="immediate")

    def test_figure_mode_provenance(self):
        built = apparatus.build_calculator_keys(figure_id="synthetic-1-fig", stem="Press the keys in order.",
                                                keys=["AC", 42, "+", 8, "="], values="figure")
        self.audit(built)
        self.assertIn("figure content", built.claims)
        with self.assertRaises(vt.TemplateError):
            apparatus.build_calculator_keys(figure_id="synthetic-1-fig", stem="Press the keys in order.",
                                            keys=["AC", 42, "+", 8, "="])
        built = self.vessel(stem="Read the scale.", values="figure")
        self.audit(built)
        self.assertIn("figure content", built.claims)

    def test_half_step_and_units(self):
        built = self.vessel(capacity=100, step=50, reading=75, values="figure",
                            stem="A scale is marked in divisions.")
        self.assertTrue(any(e.get("id", "").startswith("minor") for e in built.doc["elements"]))
        self.assertIn("half-step", built.claims)
        for unit in ("ml", "cm³", "l"):
            with self.subTest(unit=unit):
                self.audit(self.vessel(unit=unit, values="figure", stem="Read the scale."))
        with self.assertRaises(TypeError):
            self.vessel(profile="cylinder")

    def test_exact_decimal_labels(self):
        built = self.vessel(capacity=0.7, step=0.1, reading=0.35, values="figure", stem="Read the scale.")
        texts = [e.get("value") for e in built.doc["elements"] if e.get("type") == "text"]
        for expected in ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7"):
            self.assertIn(expected, texts)
        self.assertNotIn("0.30000000000000004", texts)
        self.assertIn('label "0.3" names 0.3', built.claims)
        self.audit(built)
        built = self.vessel(capacity=0.5, step=0.05, reading=0.25, values="figure", stem="Read the scale.")
        self.assertIn('label "0.35" names 0.35', built.claims)
        self.audit(built)
        for bad in (dict(capacity=1, step=1 / 6), dict(capacity=0.1, step=0.03),
                    dict(capacity=1, step=0.33333333)):
            with self.subTest(bad=bad), self.assertRaises(vt.TemplateError):
                self.vessel(values="figure", stem="Read.", **bad)

    def test_key_claim_targets_are_real_ids(self):
        built = apparatus.build_calculator_square(figure_id="synthetic-1-keys",
                                                  stem="Square 122.", operand=122)
        element_ids = {e.get("id") for e in built.doc["elements"]}
        for line in built.claims.splitlines():
            if " names " in line:
                target = line.split(" names ")[1].split(" |")[0].strip()
                self.assertIn(target, element_ids, f"label target {target} is not a drawn element")

    def test_sequence_must_compute(self):
        with self.assertRaises(vt.TemplateError):
            apparatus.build_calculator_keys(figure_id="synthetic-1-noop", stem="Operand 42.",
                                            keys=["ON", 42, "="])


if __name__ == "__main__":
    unittest.main()
