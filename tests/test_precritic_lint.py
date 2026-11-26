#!/usr/bin/env python3
"""tests/test_precritic_lint.py — offline tests for tools/precritic-lint.py (W9 item G).

Synthetic fixtures only: a hand-written scope card (English filler, no real lesson text) under
<tmp>/cards/, a content.yaml with toy stems, and a synthetic claims file. --cards-dir keeps the
corpus out of the loop entirely.
"""
import json
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
  phrases: ["equal parts", "of", "unit fraction"]
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

CARD8 = """\
schema_version: 1
grade: 6
subject: Mathematics
medium: si
lesson_number: 8
title_en: Perimeter
title_si: Perimeter (si)
syllabus_refs: ["2.1"]
term: 1
periods: 2
source: {file: "lessons/08-Perimeter.md", sha256: "0000000000000000000000000000000000000000000000000000000000000002"}
generated:
  sections:
    - {number: "2.1", title: "Measuring around a shape"}
  vocabulary: ["perimeter"]
  phrases: ["around the edge"]
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
    - {concept: "circle circumference", why: "grade 7", probes: ["circumference"]}
  prerequisites: []
  difficulty_hooks: []
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


SI = {"stem": "stem_si", "text": "text_si", "approach": "approach_si", "final": "final_si"}


def with_si(node):
    """0024: every student field in a fixture carries its *_si twin (synthetic Sinhala) —
    mirrors build-staged's requirement so a fixture testing another check stays legal."""
    for en, si in SI.items():
        if node.get(en) is not None and node.get(si) is None:
            node[si] = "සිංහල අන්තර්ගතය"
    for p in node.get("parts") or []:
        if isinstance(p, dict):
            with_si(p)
    return node


def write(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def make_run(tmp: Path, stem: str = "Shade the strip.", parts=None, approach=None,
             final=None, lessons=None, figure=None, figures=None) -> Path:
    run = tmp / "run"
    run.mkdir(parents=True, exist_ok=True)
    q = {"n": 1, "lessons": lessons if lessons is not None else ["L07"], "stem": stem}
    if approach is not None:
        q["approach"] = approach
    if final is not None:
        q["final"] = final
    if parts is not None:
        q["parts"] = parts
    if figure is not None:
        q["figure"] = figure
    import yaml
    write(run / "content.yaml",
          yaml.safe_dump({"id_seed": "synthetic", "lessons": {"L07": "placeholder"},
                          "figures": figures or {},
                          "questions": [with_si(q)]}, allow_unicode=True, sort_keys=False))
    cards = tmp / "cards"
    write(cards / "07-Fractions.yaml", CARD)
    return run


def make_run_two_cards(tmp: Path, questions: list) -> Path:
    """A run with cards 07 (probe 'improper') AND 08 (probe 'circumference') on disk —
    each question's `lessons:` decides which probes it answers to (W12)."""
    run = tmp / "run"
    run.mkdir(parents=True, exist_ok=True)
    import yaml
    write(run / "content.yaml",
          yaml.safe_dump({"id_seed": "synthetic",
                          "lessons": {"L07": "placeholder", "L08": "placeholder2"},
                          "questions": [with_si(q) for q in questions]},
                         allow_unicode=True, sort_keys=False))
    write(tmp / "cards" / "07-Fractions.yaml", CARD)
    write(tmp / "cards" / "08-Perimeter.yaml", CARD8)
    return run


def lint_two_cards(run: Path, tmp: Path, *extra):
    return subprocess.run(
        [sys.executable, str(TOOL), str(run), "--card", "L07=7", "--card", "L08=8",
         "--grade", "6", "--cards-dir", str(tmp / "cards"), *extra],
        capture_output=True, text=True)


def lint(run: Path, tmp: Path, *extra):
    return subprocess.run(
        [sys.executable, str(TOOL), str(run), "--card", "L07=7", "--grade", "6",
         "--cards-dir", str(tmp / "cards"), *extra],
        capture_output=True, text=True)


def lint_plain(run: Path, *extra):
    """No cards bound — for the rubric (d) and dedup (e) checks, which need no corpus."""
    return subprocess.run([sys.executable, str(TOOL), str(run), *extra],
                          capture_output=True, text=True)


PART = ('      - label: {label}\n        text: "t"\n        text_si: "සිංහල"\n'
        '        approach: "x"\n        approach_si: "සිංහල"\n        final: "1"\n'
        '        final_si: "සිංහල"{lvl}\n')


def write_levels_run(tmp: Path, *question_levels) -> Path:
    """question_levels = [R,M,H]-style lists of level strings (None → the key is absent)."""
    qs = []
    for i, levels in enumerate(question_levels, 1):
        parts = "".join(PART.format(label=chr(96 + k), lvl=f"\n        level: {l}" if l else "")
                        for k, l in enumerate(levels, 1))
        qs.append(f'  - n: {i}\n    lessons: [L07]\n    stem: "s"\n    stem_si: "සිංහල"\n    parts:\n{parts}')
    run = tmp / "run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "content.yaml").write_text(
        'id_seed: "synthetic"\nlessons:\n  L07: placeholder\nquestions:\n' + "".join(qs),
        encoding="utf-8")
    return run


class PrecriticLintTest(unittest.TestCase):
    def test_mechanical_wording_advisories(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            run = make_run(
                tmp, stem="The loan has principal and interest. The repayment stays the same.",
                parts=[{
                    "label": "a",
                    "text": "Use $P$ and $Q$ from 3 to 7. Explain why Q is larger.",
                    "text_si": "$P$ හා $Q$ සඳහා 3 සිට 8 දක්වා සලකන්න.",
                    "approach": "Compare the endpoints at x = 7.",
                    "final": "$Q > P$",
                }],
            )
            result = lint(run, tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for message in (
                "specify whether principal, interest, or the total payment stays unchanged",
                "consistent notation: use inline math for Q",
                "bare variable assignment",
                "explicit numeric range endpoints disagree",
                "prompt asks for a reason, but the final is math only",
            ):
                self.assertIn(message, result.stdout)

    def test_qualified_aligned_wording_is_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            run = make_run(
                tmp, stem="The loan has principal and interest. The principal repayment stays the same.",
                parts=[{
                    "label": "a",
                    "text": "Use $P$ and $Q$ from 3 to 7. Explain why $Q$ is larger.",
                    "text_si": "$P$ හා $Q$ සඳහා 3 සිට 7 දක්වා සලකන්න.",
                    "approach": "Compare the fraction endpoints at $x = 7$.",
                    "final": "$Q > P$ because $Q$ is farther right.",
                }],
            )
            result = lint(run, tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("precritic-lint: 0 fail(s) · 0 warn(s)", result.stdout)

    def test_existing_scaffold_warns_but_unbound_a11y_markers_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            run = make_run(tmp, figure="curve", figures={"curve": "figures/curve.json", "marked": "figures/marked.json"},
                           parts=[{"label": "a", "text": "Expand $(t + 13)^4$.",
                                   "figure": "marked", "approach": "Use repeated multiplication.", "final": "Done."}])
            existing = write(tmp / "existing.json", '[{"id":"synthetic","stem_excerpt":"Verify the polynomial expansion of $(t+13)^{4}$ before substituting any values."}]')
            write(run / "figures" / "curve.json", '{"a11y":{"description":"The curve has marked plot endpoints."},"elements":[{"type":"polyline"}]}')
            write(run / "figures" / "marked.json", '{"a11y":{"description":"The curve has marked plot endpoints."},"elements":[{"type":"point","r":3}]}')
            result = lint(run, tmp, "--existing", str(existing))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("exact algebra scaffold also appears in existing.json:synthetic", result.stdout)
            self.assertIn("FAIL curve: a11y describes marked plot bounds", result.stdout)
            self.assertIn("FAIL marked: a11y describes marked plot bounds", result.stdout)

    def test_lints_only_figure_paths_referenced_by_questions_or_nested_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            run = make_run(tmp, lessons=[], figure="main", figures={"main": "figures/main.json",
                           "nested": "diagrams/endpoints.json", "unused": "figures/unused.json"},
                           parts=[{"label": "a", "text": "Read the plot.", "parts": [
                               {"label": "i", "text": "Name the endpoints.", "figure": "nested",
                                "approach": "Read the axis.", "final": "Done."}]}])
            figure = '{"a11y":{"description":"Marked plot endpoints."},"elements":[]}'
            write(run / "figures" / "main.json", figure)
            write(run / "diagrams" / "endpoints.json", figure)
            write(run / "figures" / "unused.json", "{")
            write(run / "figures" / "abandoned.json", "{")
            result = lint_plain(run)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("FAIL main: a11y describes marked plot bounds", result.stdout)
            self.assertIn("FAIL endpoints: a11y describes marked plot bounds", result.stdout)
            self.assertIn("precritic-lint: 2 fail(s) · 0 warn(s)", result.stdout)

    def test_bound_marker_must_bind_the_named_element_at_the_declared_value(self):
        line = {"id": "end", "type": "line", "points": [[0, 0], [0, 20]]}
        point = {"id": "end", "type": "point", "at": [0, 0]}
        fixtures = [
            ({**line, "stroke": {"style": "dashed"}}, {}, False),
            (line, {"strokeStyle": "dashed"}, False),
            (point, {}, False),
            ({**line, "points": [[10, 0], [10, 20]]}, {}, True),
            ({**point, "r": 0}, {}, True),
        ]
        for marker, defaults, fails in fixtures:
            with self.subTest(marker=marker, defaults=defaults), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                run = make_run(tmp, lessons=[], figure="bounds", figures={"bounds": "figures/bounds.json"})
                import yaml
                content = run / "content.yaml"
                data = yaml.safe_load(content.read_text())
                data["figure_features"] = {"bounds": [
                    {"kind": "bound-marker", "id": "left", "axis": "x", "value": 0, "element": "end"}]}
                content.write_text(yaml.safe_dump(data))
                write(run / "figures" / "bounds-claims.txt",
                      "anchors:\n  L 0 0\n  R 40 0\nclaims:\n  K1 axis LR from 0 to 4 | inferred |")
                write(run / "figures" / "bounds.json", json.dumps({
                    "a11y": {"description": "Marked plot endpoints."},
                    "defaults": defaults,
                    "elements": [marker],
                }))
                result = lint_plain(run)
                self.assertEqual(result.returncode, int(fails), result.stdout + result.stderr)
                self.assertEqual("FAIL bounds: a11y describes marked plot bounds" in result.stdout,
                                 fails, result.stdout)

    def test_question_a11y_and_bilingual_figure_refs_bind_emitted_figure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            en = {"figure": "curve", "kind": "point", "id": "P"}
            si = {**en, "id": "Z"}
            run = make_run(tmp, lessons=[], figure="curve", figures={"curve": "figures/curve.json"},
                           parts=[{"label": "a", "text": "Read the vertex at P.", "final": "$(-2, 7)$",
                                   "figure_refs": {"english": [en], "sinhala": [si]}}])
            write(run / "figures" / "curve.json", json.dumps({
                "a11y": {"description": "The vertex is at (-2, 7)."},
                "elements": [{"id": "p", "type": "point", "label": "P", "r": 2},
                             {"id": "q", "type": "point", "label": "Q", "r": 2}]}))
            result = lint_plain(run)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("sinhala: no visible point Z", result.stdout)
            self.assertIn("a11y reveals the asked vertex answer", result.stdout)
            self.assertIn("unused named point Q", result.stdout)

    def test_figure_a11y_does_not_treat_an_already_given_vertex_as_a_spoiler(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, lessons=[], figure="curve", figures={"curve": "figures/curve.json"},
                           stem="The vertex is at (2, 7).",
                           parts=[{"label": "a", "text": "Use the vertex to explain symmetry.", "final": "$(2,7)$"}])
            write(run / "figures" / "curve.json",
                  '{"a11y":{"description":"Vertex (2, 7)."},"elements":[]}')
            result = lint_plain(run)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bilingual_refs_bind_labels_on_zero_radius_points(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td), lessons=[], figure="corner",
                           figures={"corner": "figures/corner.json"},
                           parts=[{"label": "a", "text": "Name corner A.",
                                   "figure_refs": {lang: [{"figure": "corner", "kind": "point", "id": "A"}]
                                                   for lang in ("english", "sinhala")}}])
            write(run / "figures" / "corner.json",
                  '{"elements":[{"id":"a","type":"point","label":"A","at":[30,30],"r":0}]}')
            result = lint_plain(run)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wording_advisories_use_paired_fields_and_part_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            run = make_run(Path(td), stem="Count the pages printed by then.", parts=[{
                "label": "a", "text": "Write the area as a product of two binomials. Expand it.",
                "text_si": "වර්ගඵලය සඳහා ප්‍රකාශනයක් ලියන්න.",
                "approach": "The gradient in metres per hour is 4.",
                "approach_si": "පැයකට මීටර ලෙස ගත් විට අනුක්‍රමණය හතරකි.",
            }])
            content = run / "content.yaml"
            import yaml
            doc = yaml.safe_load(content.read_text(encoding="utf-8"))
            doc["questions"][0]["stem_si"] = "ඒ වන විට මුද්‍රණය වන පිටු ගණන."
            content.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
            result = subprocess.run([sys.executable, str(TOOL), str(run)], capture_output=True, text=True)
            self.assertIn("completed vs ongoing", result.stdout)
            self.assertIn("gradient directly", result.stdout)
            self.assertIn("multiple method steps", result.stdout)

    def test_wording_advises_on_prepartitioned_figure_for_symbolic_area(self):
        with tempfile.TemporaryDirectory() as td:
            stem = "The diagram shows how the sides of the rectangle are split."
            parts = [{"label": "a", "text": "Give the area as a simplified expression."}]
            run = make_run(Path(td), stem=stem, parts=parts, figure="Q1")
            result = subprocess.run([sys.executable, str(TOOL), str(run)], capture_output=True, text=True)
            self.assertIn("pre-partitioned figure gives away the area method", result.stdout)
            make_run(Path(td), stem="The diagram labels the full side lengths.", parts=parts, figure="Q1")
            result = subprocess.run([sys.executable, str(TOOL), str(run)], capture_output=True, text=True)
            self.assertNotIn("pre-partitioned figure", result.stdout)

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

    def test_card_key_must_be_a_content_lessons_key(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, stem="Shade the strip.")
            for extra in ((), ("--all-probes",)):
                unknown = subprocess.run(
                    [sys.executable, str(TOOL), str(run), "--card", "bs=7",
                     "--grade", "6", "--cards-dir", str(tmp / "cards"), *extra],
                    capture_output=True, text=True)
                self.assertEqual(unknown.returncode, 2, unknown.stdout + unknown.stderr)
                self.assertIn(
                    "--card bs=7: 'bs' is not a content.yaml lessons key (have: L07)",
                    unknown.stderr)

            correct = lint(run, tmp)
            self.assertEqual(correct.returncode, 0, correct.stdout + correct.stderr)

    # ---- (a) W12: probes are per-question, keyed off the question's lessons: ----
    def test_probe_of_an_untagged_card_is_not_checked(self):
        """Card 07's probe 'improper' in a question tagging only L08 → clean."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run_two_cards(tmp, [
                {"n": 1, "lessons": ["L08"], "stem": "Write the improper fraction."},
            ])
            r = lint_two_cards(run, tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("0 fail(s)", r.stdout)

    def test_probe_of_the_tagged_card_fails(self):
        """The same word in a question tagging L07 → FAIL (default is per-question)."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run_two_cards(tmp, [
                {"n": 1, "lessons": ["L07"], "stem": "Write the improper fraction."},
            ])
            r = lint_two_cards(run, tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("FAIL Q1", r.stdout)
            self.assertIn("improper", r.stdout)

    def test_question_tagging_both_gets_both_probe_sets(self):
        """A question tagging L07+L08 answers to both cards' probes."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run_two_cards(tmp, [
                {"n": 1, "lessons": ["L07", "L08"],
                 "stem": "Measure the circumference of the rim."},
            ])
            r = lint_two_cards(run, tmp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("circumference", r.stdout)
            self.assertIn("08-Perimeter", r.stdout)

    def test_all_probes_restores_the_run_wide_check(self):
        """--all-probes: card 07's probe fires even on a question tagging only L08."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run_two_cards(tmp, [
                {"n": 1, "lessons": ["L08"], "stem": "Write the improper fraction."},
            ])
            r = lint_two_cards(run, tmp, "--all-probes")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("improper", r.stdout)

    def test_unbound_lesson_key_warns_per_question(self):
        """A `lessons:` key no --card binds → one WARN per (question, key): its not_taught
        probes were not checked. Bound keys on the same question still lint normally."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run_two_cards(tmp, [
                {"n": 1, "lessons": ["L07", "L08"], "stem": "Shade the fraction strip."},
                {"n": 2, "lessons": ["L08"], "stem": "Measure the rim."},
            ])
            r = subprocess.run(                     # bind ONLY L07 — L08 has no card
                [sys.executable, str(TOOL), str(run), "--card", "L07=7",
                 "--grade", "6", "--cards-dir", str(tmp / "cards")],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("WARN Q1: lesson key 'L08' has no bound --card", r.stdout)
            self.assertIn("WARN Q2: lesson key 'L08' has no bound --card", r.stdout)
            self.assertIn("2 warn(s)", r.stdout)    # one per (question, key), not per probe
            # --all-probes is the run-wide mode — no per-key binding WARN there
            r2 = lint_two_cards(run, tmp, "--all-probes")
            self.assertNotIn("has no bound --card", r2.stdout)

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

    def test_phrase_term_in_a_part_is_quiet(self):
        # phrases (not just vocabulary) count toward the card-terms match
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[
                {"label": "a", "text": "Split the strip into equal parts.",
                 "approach": "x", "final": "4"},
            ])
            r = lint(run, tmp)
            self.assertNotIn("WARN Q1 tags", r.stdout)

    def test_short_phrase_term_does_not_silence_the_warn(self):
        # 'of' is on the phrases list but under 3 letter codepoints — dropped, so a
        # question whose only card-word is 'of' still warns
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[
                {"label": "a", "text": "Count the cells of the strip.",
                 "approach": "x", "final": "5"},
            ])
            r = lint(run, tmp)
            self.assertIn("WARN Q1 tags", r.stdout)

    # ---- (d) --rubric medium-hard reads the leaf `level:` keys ---------------
    def test_rubric_passes_a_clean_set(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "M", "H"], ["M", "H", "H"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("0 fail(s)", r.stdout)

    def test_rubric_by_band_checks_each_question_against_its_own_band(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "M"], ["M", "M", "H"])
            c = run / "content.yaml"
            t = c.read_text(encoding="utf-8").replace('id_seed: "synthetic"\n',
                                                      'id_seed: "synthetic"\ndifficulty: medium\n')
            c.write_text(t.replace("  - n: 2\n", "  - n: 2\n    difficulty: hard\n"), encoding="utf-8")
            r = lint_plain(run, "--rubric", "by-band")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("rubric medium: Q1", r.stdout)
            self.assertIn("rubric medium-hard: Q2", r.stdout)
            r2 = lint_plain(run, "--rubric", "medium")
            self.assertEqual(r2.returncode, 1)
            self.assertIn("level H — medium does not allow H", r2.stdout)

    def test_rubric_fails_under_3_parts(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["M", "H"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL Q1: 2 leaf part(s)", r.stdout)

    def test_rubric_fails_two_r_parts_and_r_not_first(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "R", "M", "M", "H"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 1)
            self.assertIn("2 R parts", r.stdout)
            run2 = write_levels_run(Path(td) / "b", ["M", "R", "H"])
            r2 = lint_plain(run2, "--rubric", "medium-hard")
            self.assertEqual(r2.returncode, 1)
            self.assertIn("the R part is Q1.b — medium-hard allows it only as part (a)",
                          r2.stdout)

    def test_rubric_fails_last_not_h(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "M", "M", "H", "M"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 1)
            self.assertIn("ends on H", r.stdout)

    def test_rubric_mh_fraction_is_set_wide(self):
        # Q1 alone is 1/3 M/H among its rated leaves — under a per-question rule it
        # failed; the set rules read ≥60% over ALL rated leaves, so the set passes
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "M", None],
                                   ["M", "H", "H"], ["M", "H", "H"], ["M", "H", "H"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("WARN Q1.c: no level", r.stdout)

    def test_rubric_fails_under_60_percent_mh(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "R", "M"])   # rated M/H 1/3 — and 2 Rs
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 1)
            self.assertIn("medium-hard wants ≥60%", r.stdout)

    def test_rubric_fails_under_30_percent_h_overall(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "M", "M", "M", "H"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 1)
            self.assertIn("medium-hard wants ≥30% H overall", r.stdout)

    def test_rubric_missing_level_is_a_warn_not_a_fail(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", None, "M", "H"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertIn("WARN Q1.b: no level", r.stdout)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # a set with NO rated leaves at all cannot fail either — every leaf warned
            run2 = write_levels_run(Path(td) / "b", [None, None, None])
            r2 = lint_plain(run2, "--rubric", "medium-hard")
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
            self.assertIn("0 fail(s)", r2.stdout)

    def test_rubric_unrated_last_leaf_warns_cannot_check_h(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "M", None], ["M", "H", "H"])
            r = lint_plain(run, "--rubric", "medium-hard")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("WARN Q1: last part has no level — cannot check it is H",
                          r.stdout)

    def test_easy_rubric_requires_r_and_at_most_three_leaves(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", "R", "R"])
            passed = lint_plain(run, "--rubric", "easy")
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            run = write_levels_run(Path(td) / "b", ["R", "M"])
            wrong_level = lint_plain(run, "--rubric", "easy")
            self.assertEqual(wrong_level.returncode, 1)
            self.assertIn("easy requires R", wrong_level.stdout)
            run = write_levels_run(Path(td) / "c", ["R", "R", "R", "R"])
            too_many = lint_plain(run, "--rubric", "easy")
            self.assertEqual(too_many.returncode, 1)
            self.assertIn("easy allows at most 3", too_many.stdout)

    def test_easy_and_medium_missing_levels_warn(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["R", None])
            easy = lint_plain(run, "--rubric", "easy")
            self.assertEqual(easy.returncode, 0, easy.stdout + easy.stderr)
            self.assertIn("WARN Q1.b: no level", easy.stdout)
            run = write_levels_run(Path(td) / "m", ["M", None])
            medium = lint_plain(run, "--rubric", "medium")
            self.assertEqual(medium.returncode, 0, medium.stdout + medium.stderr)
            self.assertIn("WARN Q1.b: no level", medium.stdout)

    def test_medium_requires_m_no_h_and_two_to_four_leaves(self):
        with tempfile.TemporaryDirectory() as td:
            run = write_levels_run(Path(td), ["M", "R", "R", "R"])
            good = lint_plain(run, "--rubric", "medium")
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            run = write_levels_run(Path(td) / "b", ["R", "R"])
            no_m = lint_plain(run, "--rubric", "medium")
            self.assertEqual(no_m.returncode, 1)
            self.assertIn("no M leaf", no_m.stdout)
            run = write_levels_run(Path(td) / "c", ["M", "H"])
            has_h = lint_plain(run, "--rubric", "medium")
            self.assertEqual(has_h.returncode, 1)
            self.assertIn("medium does not allow H", has_h.stdout)
            run = write_levels_run(Path(td) / "d", ["M"])
            too_few = lint_plain(run, "--rubric", "medium")
            self.assertEqual(too_few.returncode, 1)
            self.assertIn("medium wants 2–4", too_few.stdout)

    # ---- (e) --existing: digits-masked Jaccard duplicate warn ----------------
    def test_existing_duplicate_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, stem="Shade 3 of 5 cells in the strip.")
            ex = write(tmp / "existing.json",
                       '[{"question_id": "qqq-1", "stem_excerpt": '
                       '"Shade 9 of 12 cells in the strip."}]')
            r = lint_plain(run, "--existing", str(ex))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("WARN Q1 ≈ existing.json:qqq-1", r.stdout)
            self.assertIn("digits masked", r.stdout)

    def test_existing_unrelated_stem_is_quiet(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, stem="Compute the perimeter of the rectangle.")
            ex = write(tmp / "existing.json",
                       '[{"question_id": "qqq-1", "stem_excerpt": '
                       '"Shade 9 of 12 cells in the strip."}]')
            r = lint_plain(run, "--existing", str(ex))
            self.assertNotIn("≈", r.stdout)

    def test_card_example_and_exercise_fingerprints_warn_without_item_text(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, stem="Shade 3 of 5 cells in the strip.")
            import yaml
            card_path = tmp / "cards" / "07-Fractions.yaml"
            card = yaml.safe_load(card_path.read_text(encoding="utf-8"))
            card["generated"]["worked_examples"] = [{
                "heading": "Synthetic example heading",
                "excerpt": "Shade 3 of 5 cells in the strip.",
            }]
            card["generated"]["exercises"] = [{
                "heading": "Synthetic exercise heading",
                "items": ["Shade 8 of 9 cells in the strip."],
            }]
            card_path.write_text(
                yaml.safe_dump(card, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            r = lint(run, tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("worked example 1 (Synthetic example heading)", r.stdout)
            self.assertIn("exercise Synthetic exercise heading item 1", r.stdout)
            self.assertIn("Jaccard 1.00, digits masked", r.stdout)
            self.assertNotIn("Shade 8 of 9 cells", r.stdout)
            self.assertNotIn("Shade 3 of 5 cells", r.stdout)

    def test_same_algebra_scaffold_in_an_exercise_blocks_but_a_given_does_not(self):
        import yaml
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[{"label": "a", "text": "Expand $(t + 13)^4$."}])
            path = tmp / "cards" / "07-Fractions.yaml"
            card = yaml.safe_load(path.read_text())
            card["generated"]["exercises"] = [{"heading": "Synthetic", "items": [
                "Find the expansion of $(t+13)^{4}$.",
                "Compare $28$ to the answer from the first part.",
            ]}]
            path.write_text(yaml.safe_dump(card))
            result = lint(run, tmp)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("FAIL Q1.a.text: exact algebra scaffold", result.stdout)
            content = run / "content.yaml"
            doc = yaml.safe_load(content.read_text())
            doc["questions"][0]["parts"][0]["text"] = "Find the degree of $(t+13)^4$."
            content.write_text(yaml.safe_dump(doc))
            result = lint(run, tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # ---- usage ---------------------------------------------------------------
    def test_sinhala_scaffold_operation_matches_english(self):
        import yaml
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[{"label": "a", "text": "Factor $t^2-169$."}])
            path = tmp / "cards" / "07-Fractions.yaml"
            card = yaml.safe_load(path.read_text())
            for exercise in ("සාධක වලට වෙන් කරන්න $t^2-169$.", "$t^2-169$ සාධකවලට වෙන් කරන්න."):
                with self.subTest(exercise=exercise):
                    card["generated"]["exercises"] = [{"items": [exercise]}]
                    path.write_text(yaml.safe_dump(card, allow_unicode=True))
                    result = lint(run, tmp)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("FAIL Q1.a.text: exact algebra scaffold", result.stdout)

    def test_sinhala_instruction_does_not_bind_the_next_sentence(self):
        import yaml
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[{"label": "a", "text": "Factor $t^2-169$."}])
            path = tmp / "cards" / "07-Fractions.yaml"
            card = yaml.safe_load(path.read_text())
            card["generated"]["exercises"] = [{"items": [
                "$x^2-49$ සාධකවලට වෙන් කරන්න. $t^2-169$ සඳහා අගය සොයන්න.",
            ]}]
            path.write_text(yaml.safe_dump(card, allow_unicode=True))
            result = lint(run, tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("exact algebra scaffold", result.stdout)

    def test_same_expression_in_a_different_exercise_task_does_not_block(self):
        import yaml
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, parts=[{"label": "a", "text": "Factor $t^2-169$."}])
            path = tmp / "cards" / "07-Fractions.yaml"
            card = yaml.safe_load(path.read_text())
            card["generated"]["exercises"] = [{"items": ["Evaluate $t^2-169$ at $t=5$."]}]
            path.write_text(yaml.safe_dump(card))
            result = lint(run, tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("exact algebra scaffold", result.stdout)

    def test_sinhala_in_text_command_fails(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp)
            # Inject Sinhala inside \text{} in content.yaml
            content_path = run / "content.yaml"
            import yaml
            data = yaml.safe_load(content_path.read_text(encoding="utf-8"))
            data["questions"][0]["stem_si"] = r"වර්ගඵලය $\text{වර්ගඵලය} = 10\text{ cm}^2$ වේ."
            content_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            r = lint(run, tmp, "--card", "L07=07")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(r"Sinhala text inside KaTeX \text{}", r.stdout)

    def test_approach_announcement_prefix_fails(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run = make_run(tmp, approach="The method is to divide.", final="$5$")
            content_path = run / "content.yaml"
            import yaml
            data = yaml.safe_load(content_path.read_text(encoding="utf-8"))
            # Sinhala approach starting with announcement prefix
            data["questions"][0]["approach_si"] = "පිළිතුර: $x = 5$"
            content_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            r = lint(run, tmp, "--card", "L07=07")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("approach opens with an announcement prefix", r.stdout)

            # English approach starting with announcement prefix
            data["questions"][0]["approach_si"] = "බෙදීමෙන් පිළිතුර ලැබේ."
            data["questions"][0]["approach"] = "Answer: $x = 5$"
            content_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            r = lint(run, tmp, "--card", "L07=07")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("approach opens with an announcement prefix", r.stdout)

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
