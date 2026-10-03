#!/usr/bin/env python3
"""test_scope_cards.py — offline suite for tools/scope-cards.py.

Fixture corpus: tests/fixtures/scope-corpus/maths/grade-06 — two synthetic lessons (English filler,
structural Sinhala heading keywords only; this is a public repo, no real corpus text may appear).
Every test copies the fixture into a temp dir so the tree can be drafted into.
"""
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
TOOL = ROOT / "tools" / "scope-cards.py"
FIXTURE = HERE / "fixtures" / "scope-corpus"

CURATED = {
    "status": "drafted",
    "not_taught": [{"concept": "quokka-counting", "why": "not part of this lesson",
                    "probes": ["qq-not-a-word"]},
                   {"concept": "wombat-weighing", "why": "also not part of this lesson",
                    "probes": ["ww-not-a-word"]}],
    "prerequisites": [],
    "difficulty_hooks": [{"level": "M", "hook": "a routine-then-twist hook"},
                         {"level": "H", "hook": "a non-routine hook"}],
}


def run_tool(args):
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True, cwd=ROOT)


class ScopeCardsTest(unittest.TestCase):
    def make_corpus(self, tmp) -> Path:
        work = Path(tmp) / "corpus"
        shutil.copytree(FIXTURE, work)
        return work

    def draft(self, corpus, *extra):
        return run_tool(["draft", "--grade", "6", "--corpus", str(corpus), *extra])

    def check(self, corpus, *extra):
        return run_tool(["check", "--grade", "6", "--corpus", str(corpus), *extra])

    def cards_dir(self, corpus) -> Path:
        return corpus / "maths" / "grade-06" / "scope-cards"

    def load_card(self, corpus, stem):
        return yaml.safe_load((self.cards_dir(corpus) / f"{stem}.yaml").read_text(encoding="utf-8"))

    def curate(self, corpus, stem, curated):
        p = self.cards_dir(corpus) / f"{stem}.yaml"
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        doc["curated"] = curated
        p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1_000_000),
                     encoding="utf-8")

    def curate_all(self, corpus, curated=None):
        for stem in ("01-Alpha", "02-Beta"):
            self.curate(corpus, stem, dict(curated or CURATED))

    # ---- draft ---------------------------------------------------------------

    def test_draft_output_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            r = self.draft(corpus)
            self.assertEqual(r.returncode, 0, r.stderr)
            card = self.load_card(corpus, "01-Alpha")
            self.assertEqual(card["schema_version"], 1)
            self.assertEqual(card["grade"], 6)
            self.assertEqual(card["subject"], "Mathematics")
            self.assertEqual(card["medium"], "si")
            self.assertEqual(card["lesson_number"], 1)
            self.assertEqual(card["title_en"], "Alpha")
            self.assertEqual(card["term"], 1)
            self.assertEqual(card["periods"], 2)
            self.assertEqual(card["syllabus_refs"], ["1.1"])
            self.assertEqual(card["source"]["file"], "lessons/01-Alpha.md")
            self.assertEqual(len(card["source"]["sha256"]), 64)
            g = card["generated"]
            self.assertEqual(set(g), {"sections", "vocabulary", "worked_examples", "exercises",
                                      "activities", "figure_kinds", "figures", "tables", "summary"})
            self.assertIn({"number": "1.1", "title": "First topic"}, g["sections"])
            self.assertIn({"number": None, "title": "සාරාංශය"}, g["sections"])
            self.assertIn("alpha term", g["vocabulary"])
            self.assertIn("beta term", g["vocabulary"])
            self.assertIn("shared term", g["vocabulary"])
            self.assertNotIn("Source:", g["vocabulary"])
            self.assertNotIn("පියවර 1", g["vocabulary"])   # step labels are dropped
            wex = g["worked_examples"]
            self.assertEqual(len(wex), 1)
            self.assertEqual(wex[0]["heading"], "නිදසුන 1")
            self.assertEqual(wex[0]["section"], "1.1")
            self.assertEqual(wex[0]["anchor"], "fx-01-p001-u006")
            self.assertIn("zebra", wex[0]["excerpt"])
            ex = g["exercises"]
            self.assertEqual(len(ex), 1)
            self.assertEqual(ex[0]["section"], "1.1")
            self.assertEqual(ex[0]["items"], ["(1) Do the first drill.", "(2) Do the second drill."])
            acts = g["activities"]
            self.assertEqual(len(acts), 1)
            self.assertIn("Fold the paper strip", acts[0]["excerpt"])
            self.assertEqual(g["figure_kinds"], [{"concept": "alpha", "count": 1},
                                                 {"concept": "drawing", "count": 1}])
            self.assertEqual(g["figures"], 1)
            self.assertEqual(g["tables"], 0)
            self.assertEqual(g["summary"], ["First summary bullet.", "Second summary bullet."])
            self.assertEqual(card["curated"]["status"], "todo")
            # lesson 2 — a Table block and a මිශ්‍ර අභ්‍යාසය with both item styles
            card2 = self.load_card(corpus, "02-Beta")
            g2 = card2["generated"]
            self.assertEqual(g2["tables"], 1)
            self.assertEqual(g2["figures"], 0)
            self.assertEqual(len(g2["exercises"]), 1)
            self.assertEqual(g2["exercises"][0]["items"],
                             ["(1) First mixed drill.", "(2) Second mixed drill as a numbered paragraph."])

    def test_draft_rerun_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.assertEqual(self.draft(corpus).returncode, 0)
            snap = {p.name: p.read_bytes() for p in self.cards_dir(corpus).glob("*.yaml")}
            r = self.draft(corpus)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("unchanged", r.stdout)
            for p in self.cards_dir(corpus).glob("*.yaml"):
                self.assertEqual(p.read_bytes(), snap[p.name])

    def test_draft_preserves_curated(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            curated = dict(CURATED)
            curated["not_taught"] = [{"concept": "hand written", "why": "w", "probes": ["qq1", "qq2"]}]
            self.curate(corpus, "01-Alpha", curated)
            r = self.draft(corpus)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.load_card(corpus, "01-Alpha")["curated"], curated)

    def test_draft_lessons_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            r = self.draft(corpus, "--lessons", "1")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((self.cards_dir(corpus) / "01-Alpha.yaml").is_file())
            self.assertFalse((self.cards_dir(corpus) / "02-Beta.yaml").exists())
            r = self.draft(corpus, "--lessons", "9")
            self.assertEqual(r.returncode, 2)
            self.assertIn("not published", r.stderr)

    # ---- check ---------------------------------------------------------------

    def test_check_passes_on_curated_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            r = self.check(corpus)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("2 card(s) · 2 passed · 0 failed", r.stdout)

    def test_check_fails_status_todo(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("todo", r.stdout)

    def test_check_fails_missing_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus, "--lessons", "1")
            self.curate(corpus, "01-Alpha", CURATED)
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("no scope card", r.stdout)

    def test_check_fails_stale_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            lesson = corpus / "maths" / "grade-06" / "lessons" / "01-Alpha.md"
            lesson.write_text(lesson.read_text(encoding="utf-8") + "\nextra line\n",
                              encoding="utf-8")
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("stale", r.stdout)

    def test_check_fails_hand_edited_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            p = self.cards_dir(corpus) / "01-Alpha.yaml"
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            doc["generated"]["figures"] += 1
            p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("generated differs", r.stdout)

    def test_check_fails_probe_present_in_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            self.curate(corpus, "01-Alpha", {
                **CURATED,
                "not_taught": [{"concept": "zebra-crossing", "why": "wrong guess",
                                "probes": ["zebra"]}],   # 'zebra' IS in the lesson
            })
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("OCCURS", r.stdout)

    def test_probe_nfc_and_ascii_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            # an NFD probe still matches the NFC 'café' in the lesson; 'ZEBRA' case-folds
            self.curate(corpus, "01-Alpha", {
                **CURATED,
                "not_taught": [{"concept": "a", "why": "w", "probes": ["café"]},
                               {"concept": "b", "why": "w", "probes": ["ZEBRA"]}]})
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout.count("OCCURS"), 2, r.stdout)

    def test_probe_ascii_word_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            # 'erm' is only a substring of 'term', never a standalone word — OK
            self.curate(corpus, "01-Alpha", {
                **CURATED,
                "not_taught": [{"concept": "a", "why": "w", "probes": ["erm"]},
                               {"concept": "b", "why": "w", "probes": ["qq-x"]}]})
            r = self.check(corpus)
            self.assertEqual(r.returncode, 0, r.stdout)
            # 'term' IS a whole word in the lesson ('alpha term')
            self.curate(corpus, "01-Alpha", {
                **CURATED,
                "not_taught": [{"concept": "a", "why": "w", "probes": ["term"]},
                               {"concept": "b", "why": "w", "probes": ["qq-x"]}]})
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("OCCURS", r.stdout)

    def test_check_fails_wrong_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            p = self.cards_dir(corpus) / "01-Alpha.yaml"
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            doc["source"]["file"] = "lessons/02-Beta.md"
            p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("source.file must be", r.stdout)

    def test_check_fails_missing_generated_and_curated(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            p = self.cards_dir(corpus) / "01-Alpha.yaml"
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            del doc["generated"], doc["curated"]
            p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("generated must be a mapping", r.stdout)
            self.assertIn("curated must be a mapping", r.stdout)

    def test_check_fails_orphan_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            (self.cards_dir(corpus) / "99-Gamma.yaml").write_text(
                "schema_version: 1\n", encoding="utf-8")
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("99-Gamma.yaml FAIL: card has no published lesson", r.stdout)

    def test_check_fails_not_taught_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            for n in (1, 6):
                nt = [{"concept": f"c{i}", "why": "w", "probes": ["qq-x"]} for i in range(n)]
                self.curate(corpus, "02-Beta", {**CURATED, "not_taught": nt})
                r = self.check(corpus)
                self.assertEqual(r.returncode, 1, f"n={n}: {r.stdout}")
                self.assertIn("2-5", r.stdout)

    def test_check_fails_bad_prerequisites(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            for ref, needle in [("grade-06/03", "lower-numbered"),
                                ("grade-06/02", "lower-numbered"),
                                ("grade-07/01", "this grade"),
                                ("grade-06:free text", "grade < 6"),
                                ("grade-08:free text", "grade < 6"),
                                ("lesson-01", "unrecognised")]:
                self.curate(corpus, "02-Beta", {
                    **CURATED, "prerequisites": [{"lesson": ref, "why": "w"}]})
                r = self.check(corpus)
                self.assertEqual(r.returncode, 1, f"{ref}: {r.stdout}")
                self.assertIn(needle, r.stdout, f"{ref}: {r.stdout}")
            # a lower-numbered lesson that has no card at all
            self.curate(corpus, "01-Alpha", {
                **CURATED, "prerequisites": [{"lesson": "grade-06/00", "why": "w"}]})
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("no scope card", r.stdout)
            # and the good forms pass
            self.curate(corpus, "01-Alpha", CURATED)
            self.curate(corpus, "02-Beta", {
                **CURATED,
                "prerequisites": [{"lesson": "grade-06/01", "why": "alpha terms reused"},
                                  {"lesson": "grade-05:counting within 100", "why": "earlier grade"}]})
            r = self.check(corpus)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_check_fails_hook_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            self.draft(corpus)
            self.curate_all(corpus)
            for n in (1, 5):
                hooks = [{"level": "M", "hook": f"h{i}"} for i in range(n)]
                self.curate(corpus, "02-Beta", {**CURATED, "difficulty_hooks": hooks})
                r = self.check(corpus)
                self.assertEqual(r.returncode, 1, f"hooks={n}: {r.stdout}")
                self.assertIn("2-4", r.stdout)
            # bad level
            self.curate(corpus, "02-Beta", {
                **CURATED, "difficulty_hooks": [{"level": "R", "hook": "x"}, {"level": "M", "hook": "y"}]})
            r = self.check(corpus)
            self.assertEqual(r.returncode, 1)
            self.assertIn("level", r.stdout)

    # ---- refusals (exit 2) ---------------------------------------------------

    def test_refuse_grade_with_no_corpus_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            for cmd in ("draft", "check"):
                r = run_tool([cmd, "--grade", "7", "--corpus", str(corpus)])
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("grade 7", r.stderr)

    def test_refuse_exam_ol(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            for cmd in ("draft", "check"):
                r = run_tool([cmd, "--exam", "ol", "--corpus", str(corpus)])
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("grade-10", r.stderr)

    def test_refuse_manifest_lesson_without_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.make_corpus(tmp)
            mf = corpus / "maths" / "grade-06" / "manifest.yaml"
            mf.write_text(mf.read_text(encoding="utf-8") + "- 3\n", encoding="utf-8")
            r = self.draft(corpus)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("no lesson file", r.stderr)

    def test_refuse_no_corpus_at_all(self):
        r = run_tool(["check", "--grade", "6", "--corpus", "/nonexistent/no-corpus-here"])
        self.assertEqual(r.returncode, 2)
        self.assertIn("no corpus", r.stderr)


class BriefTest(unittest.TestCase):
    """`brief` (W9-D): a ~80-line reading brief per card — path or NN+--grade, pure read."""

    def draft(self, corpus):
        r = run_tool(["draft", "--grade", "6", "--corpus", str(corpus)])
        assert r.returncode == 0, r.stderr

    def curate(self, corpus, stem):
        p = corpus / "maths" / "grade-06" / "scope-cards" / f"{stem}.yaml"
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        doc["curated"] = {
            **CURATED,
            "prerequisites": [{"lesson": "grade-06/00", "why": "synthetic prereq"}],
        }
        p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1_000_000),
                     encoding="utf-8")
        return p

    def corpus_with_cards(self, tmp) -> Path:
        corpus = Path(tmp) / "corpus"
        shutil.copytree(FIXTURE, corpus)
        self.draft(corpus)
        self.curate(corpus, "01-Alpha")
        self.curate(corpus, "02-Beta")
        return corpus

    def test_brief_by_lesson_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.corpus_with_cards(tmp)
            r = run_tool(["brief", "1", "--grade", "6", "--corpus", str(corpus)])
            self.assertEqual(r.returncode, 0, r.stderr)
            out = r.stdout
            card = yaml.safe_load((corpus / "maths" / "grade-06" / "scope-cards"
                                   / "01-Alpha.yaml").read_text(encoding="utf-8"))
            self.assertIn("01-Alpha.yaml", out)
            self.assertIn("Alpha", out)                       # title_en
            import hashlib
            card_sha = hashlib.sha256(
                (corpus / "maths" / "grade-06" / "scope-cards" / "01-Alpha.yaml")
                .read_bytes()).hexdigest()[:8]
            self.assertIn(f"card {card_sha}", out)
            self.assertIn(f"lesson {card['source']['sha256'][:8]}", out)
            self.assertIn("sections (", out)
            self.assertIn("1.1 First topic", out)
            self.assertIn("vocabulary", out)
            self.assertIn("alpha term", out)
            self.assertIn("worked examples:", out)
            self.assertIn("නිදසුන 1", out)
            self.assertIn("zebra", out[:20000])
            self.assertIn("exercises:", out)
            self.assertIn("item(s)", out)
            self.assertIn("Do the first drill.", out)
            self.assertIn("activities:", out)
            self.assertIn("ක්‍රියාකාරකම", out)
            self.assertIn("figure_kinds:", out)
            self.assertIn("not_taught[0] quokka-counting — not part of this lesson", out)
            self.assertIn("probes: qq-not-a-word", out)
            self.assertIn("prerequisite grade-06/00 — synthetic prereq", out)
            self.assertIn("hook M: a routine-then-twist hook", out)
            self.assertIn("status: drafted", out)
            # aim: ~80 lines per card
            self.assertLessEqual(len(out.strip().splitlines()), 100, out)

    def test_brief_by_path_and_multiple_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = self.corpus_with_cards(tmp)
            p1 = corpus / "maths" / "grade-06" / "scope-cards" / "01-Alpha.yaml"
            p2 = corpus / "maths" / "grade-06" / "scope-cards" / "02-Beta.yaml"
            r = run_tool(["brief", str(p1), str(p2)])          # no --grade needed for paths
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.count("== "), 2)
            self.assertIn("01-Alpha.yaml", r.stdout)
            self.assertIn("02-Beta.yaml", r.stdout)

    def test_brief_vocab_cap_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            shutil.copytree(FIXTURE, corpus)
            self.draft(corpus)
            p = corpus / "maths" / "grade-06" / "scope-cards" / "01-Alpha.yaml"
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            doc["generated"]["vocabulary"] = \
                [f"term{i}" for i in range(25)] + ["term0", "**•** bullet-term"]
            doc["curated"] = CURATED
            p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False,
                                        width=1_000_000), encoding="utf-8")
            r = run_tool(["brief", str(p)])
            self.assertEqual(r.returncode, 0, r.stderr)
            vline = next(l for l in r.stdout.splitlines() if l.startswith("vocabulary"))
            self.assertIn("+6", vline)                       # 26 unique → 20 shown, 6 hidden
            self.assertEqual(vline.count("term0"), 1)        # deduped
            self.assertNotIn("**•**", vline)                 # glyph bullets stripped

    def test_brief_refusals(self):
        r = run_tool(["brief"])                              # no card args at all
        self.assertEqual(r.returncode, 2)
        self.assertIn("needs at least one card", r.stderr)
        r = run_tool(["brief", "7"])                         # bare number without --grade
        self.assertEqual(r.returncode, 2)
        self.assertIn("pass --grade", r.stderr)
        r = run_tool(["brief", "/nonexistent/nope.yaml"])    # a path that is not a file
        self.assertEqual(r.returncode, 2)
        self.assertIn("no such card file", r.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            shutil.copytree(FIXTURE, corpus)
            run_tool(["draft", "--grade", "6", "--corpus", str(corpus)])
            r = run_tool(["brief", "9", "--grade", "6", "--corpus", str(corpus)])
            self.assertEqual(r.returncode, 2)
            self.assertIn("0 card(s) match", r.stderr)


if __name__ == "__main__":
    unittest.main()
