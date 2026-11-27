# MIGRATION — what came over from Vibhaga-Docs, and what happened to it

## Current

This plugin generates questions from the lesson corpus, not from source papers. Start with
[generate](../skills/generate/SKILL.md) for the current workflow and [TRAPS](TRAPS.md) for specific pitfalls.

2026-11-25: Split long trap and skill references out of the run instructions and archived
the migration tables and generation history. No workflow or validation rules changed.

2026-11-26: Grade 11 mixed run — 20 bilingual Medium questions (41 answer parts; 10 diagrams), published flagged; Q2/Q2b/Q3 passed; two plan rounds and three batch rounds, final critics satisfied. Added optional per-chunk critic selection and precritic wording, scaffold, and figure-description checks.

2026-11-27: Grade 9 mixed run — 20 bilingual Medium questions (60 answer parts; 10 diagrams: L13 Loci, L25 Angles of Polygons, L08 Straight Lines and Parallel Lines; 10 figureless: L24 Probability, L03 Number Patterns, L10 Direct Proportion, L07 Factors of Algebraic Expressions), published flagged to session 476bf97a-41ba-452c-9f1f-8648bad9cef4. Q2/Q2b/Q3/T77 passed, visual 6-rule standard verified (10/10 PASS), batch content critic satisfied (20/20 clean). Description length rule strictly enforced with <= 240 char paragraphs.

2026-11-27: Grade 10 mixed run — 20 bilingual Medium questions (40 answer parts; 8 diagrams: L27 Constructions, L16 Parallelograms II, L28 Surface Area and Volume, L31 Scale Diagrams; 12 figureless: L02 Square Root, L04 Binomial Expressions, L11 LCM of Algebraic Expressions, L24 Algebraic Inequalities, L21 Rate, L22 Formulae), published flagged to session 1b394519-84c4-4733-8a70-6b39530be574. Q2/Q2b/Q3/T77 passed, visual 6-rule standard verified (8/8 PASS), batch content critic satisfied (20/20 clean). Grade 10 length directives strictly enforced (practical/real-world context, structured paragraphs <= 240 chars, approaches <= 180 chars).

2026-11-27: Grade 11 mixed run — 20 bilingual Medium questions (60 answer parts; 8 diagrams: L11 Mid-point Theorem, L21 Tangents, L18 Surface Area and Volume of Solids, L24 Sets; 12 figureless: L01 Real Numbers, L03 Quadratic Equations, L07 Algebraic Fractions, L12 Graphs, L14 Inequalities, L15 Frequency Distributions), published flagged to session ed360eed-9e86-4ab8-8223-e37f2d4e640b. Q2/Q2b/Q3/T77 passed, visual 6-rule standard verified (8/8 PASS across 320/375/768 px light/dark), independent diagram critic satisfied (0 Blocker, 0 Major), independent content critic satisfied (20/20 clean, 0 Blocker, 0 Major). Grade 11 comprehensive O/L exam-length scenarios strictly enforced with chunked paragraphs <= 240 chars, approaches <= 180 chars, and 0 banned MT terms.

## Archive — not required before a generation run

- <a name="tools"></a>[Tools](migration/archive/history.md#tools)
- <a name="tests--fixtures"></a>[Tests & fixtures](migration/archive/history.md#tests--fixtures)
- <a name="skills--agents"></a>[Skills & agents](migration/archive/history.md#skills--agents)
- <a name="deliberately-kept-paper-era-mentions"></a>[Deliberately kept paper-era mentions](migration/archive/history.md#deliberately-kept-paper-era-mentions)
- <a name="hygiene-scan--commands-and-results-re-run-2026-09-29-raw-output-wtqgen-w0hygienetxt"></a>[Hygiene scan — commands and results (re-run 2026-09-29; raw output `wt/qgen-w0/hygiene.txt`)](migration/archive/history.md#hygiene-scan--commands-and-results-re-run-2026-09-29-raw-output-wtqgen-w0hygienetxt)
- <a name="generate-skill-history-2026-10-21"></a>[generate skill history 2026-10-21](migration/archive/history.md#generate-skill-history-2026-10-21)
