# TRAPS — cross-cutting traps the vibhaga-qgen plugin inherits

The subset of Vibhaga-Docs `_maths-onboarding/TRAPS.md` that the moved skills and tools still cite,
plus the traps this plan mandated (T5, T9, T77, T125, T136, T142). Skill-local traps (T-S4-*, T-S5-*,
T-S6a-*, T-S6b-*, T-S8-*) are linked from their own skills' §Traps sections. Use the rule in the index; open only the
case you need. The paper-era cases are [archived](traps/archive.md).

| Trap | Rule |
|---|---|
| <a name="t4--a-204-from-authv1logout-is-not-proof-of-revocation"></a><a name="t4"></a>[T4](traps/publication.md#t4) | a `204` from `/auth/v1/logout` is not proof of revocation |
| <a name="t5--hyperdrives-query-cache-is-not-invalidated-by-writes-75-s"></a><a name="t5"></a>[T5](traps/publication.md#t5) | Hyperdrive's query cache is not invalidated by writes (~75 s) |
| <a name="t9--the-publish-response-is-not-load-bearing-but-recording-ids-first-is"></a><a name="t9"></a>[T9](traps/publication.md#t9) | record generated ids BEFORE you publish — the response merely echoes them |
| <a name="t13--the-r2-mechanical-gate-catches-ocr-confusables-not-a-wrong-digit"></a><a name="t13"></a>[T13](traps/archive.md#t13) | watch a check fire on a deliberately broken fixture before you trust it |
| <a name="t14--hasswallowedmarkup-is-false-on-an-odd-number-of-"></a><a name="t14"></a>[T14](traps/authoring.md#t14) | `hasSwallowedMarkup` is `false` on an odd number of `$` |
| <a name="t25--a-separate-agent-turn-is-not-something-one-agent-can-do-to-itself"></a><a name="t25"></a>[T25](traps/archive.md#t25) | a separate agent turn is not something one agent can do to itself |
| <a name="t30---parity-and-hasswallowedmarkup-never-look-inside-the-delimiters"></a><a name="t30"></a>[T30](traps/authoring.md#t30) | `$`-parity and `hasSwallowedMarkup` never look INSIDE the delimiters |
| <a name="t34--paper-faithful-part-labels-are-a-defect-when-you-onboard-a-subset"></a><a name="t34"></a>[T34](traps/archive.md#t34) | faithful part labels are a defect when you ship a subset |
| <a name="t56--a-checksum-detects-drift-within-a-repo-nothing-was-comparing-the-two-repos"></a><a name="t56"></a>[T56](traps/verification.md#t56) | a checksum detects drift WITHIN a repo — nothing compared the two repos |
| <a name="t61--a-security-fix-that-makes-two-surfaces-disagree-and-the-review-surface-stated-the-opposite-of-what-a-student-gets"></a><a name="t61"></a>[T61](traps/verification.md#t61) | a security fix made two surfaces disagree, and the review surface stated the opposite |
| <a name="t70--a-settle-by-sample-equality-is-a-race-and-a-gate-that-reds-at-random-is-a-gate-people-re-run"></a><a name="t70"></a>[T70](traps/verification.md#t70) | a "settle" by sample-equality is a race — a gate that reds at random gets re-run |
| <a name="t74--a-gate-whose-coverage-and-whose-false-positives-are-measured-at-different-severities-is-green-when-it-blocks-nothing"></a><a name="t74"></a>[T74](traps/verification.md#t74) | coverage and false positives measured at different severities = a gate green while blocking nothing |
| <a name="t77--a-migration-that-writes-the-published-row-but-not-the-staged-doc-reverts-itself-on-the-next-publish"></a><a name="t77"></a>[T77](traps/publication.md#t77) | a write to the published row but not the staged doc reverts itself on the next publish |
| <a name="t96--a-schema-legal-field-the-renderer-ignores-is-a-figure-that-lies"></a><a name="t96"></a>[T96](traps/figures.md#t96) | a schema-legal field the renderer ignores is a figure that lies |
| <a name="t98--an-anglemark-label-can-render-on-the-opposite-side-of-the-vertex-and-it-is-live-in-the-specs-own-golden-fixture"></a><a name="t98"></a>[T98](traps/figures.md#t98) | an `angleMark` label can render on the OPPOSITE side of the vertex |
| <a name="t99--collapsing-collinear-strokes-into-one-element-is-right-the-side-you-drop-while-doing-it-is-invisible-to-every-check-you-have"></a><a name="t99"></a>[T99](traps/figures.md#t99) | a collapsed segment is invisible to every check that counts elements |
| <a name="t104--the-wrong-answer-that-agrees-with-its-own-figure-no-gate-this-suite-owns-could-have-caught-it-including-the-one-nobody-has-built-yet"></a><a name="t104"></a>[T104](traps/figures.md#t104) | the wrong answer that agrees with its own figure — no structural gate can see it |
| <a name="t114--a-gates-summary-line-that-is-computed-after-a-display-filter-cannot-fail-and-looked-exactly-like-one-that-can"></a><a name="t114"></a>[T114](traps/verification.md#t114) | a summary line computed AFTER a display filter cannot fail |
| <a name="t125--a-question-figures-a11ydescription-can-state-the-answer-the-item-asks-for"></a><a name="t125"></a>[T125](traps/figures.md#t125) | a figure's `a11y.description` can state the answer the item asks for |
| <a name="t128--a-correct-never-rule-applied-beyond-its-real-constraint-manufactures-its-own-defect"></a><a name="t128"></a>[T128](traps/figures.md#t128) | a correct "never" rule applied beyond its real constraint manufactures its own defect |
| <a name="t136--a-constructed-claim-set-that-passes-audit-a-because-you-read-its-footer-not-its-exit-code"></a><a name="t136"></a>[T136](traps/figures.md#t136) | a constructed claim set that "passes" because you read the footer, not the exit code |
| <a name="t142--the-playground-publish-raises-the-flag-on-the-row-not-in-the-staged-doc"></a><a name="t142"></a>[T142](traps/publication.md#t142) | the playground publish raises the flag on the ROW, not in the staged doc |
| <a name="t143--a-familiar-word-is-not-the-lessons-word"></a><a name="t143"></a>[T143](traps/authoring.md#t143) | Use the lesson’s own terminology. |
| <a name="t144--the-stem-gave-away-the-part"></a><a name="t144"></a>[T144](traps/authoring.md#t144) | Do not give away the part in the stem. |
| <a name="t145--new-numbers-do-not-make-a-worked-example-new"></a><a name="t145"></a>[T145](traps/authoring.md#t145) | New numbers do not make a worked example new. |
| <a name="t146--the-answer-check-did-not-use-the-question"></a><a name="t146"></a>[T146](traps/authoring.md#t146) | Check the answer against the actual question. |
| <a name="t147--a-point-name-was-swallowed-by-maths-markup"></a><a name="t147"></a>[T147](traps/authoring.md#t147) | Check that maths markup does not swallow point names. |
| <a name="t148--shared-maths-is-not-a-sinhala-translation-defect"></a><a name="t148"></a>[T148](traps/authoring.md#t148) | Shared mathematics is not a Sinhala translation defect. |
| <a name="t149--the-yesno-answer-and-its-reason-need-separate-paragraphs"></a><a name="t149"></a>[T149](traps/authoring.md#t149) | Separate a yes/no result and its reason into paragraphs. |
| <a name="t150--a-unit-outside-maths-is-prose"></a><a name="t150"></a>[T150](traps/authoring.md#t150) | A unit outside maths is prose. |
| <a name="t151--sinhala-inside-a-math-span-is-not-rendered-as-prose"></a><a name="t151"></a>[T151](traps/authoring.md#t151) | Keep Sinhala prose outside maths spans. |
| <a name="t152--default-figure-descriptions-can-reveal-answers"></a><a name="t152"></a>[T152](traps/figures.md#t152) | Check default figure descriptions for answer leaks. |
| <a name="t153--the-requested-figure-change-did-not-fit"></a><a name="t153"></a>[T153](traps/figures.md#t153) | Refuse or report a requested figure change that does not fit. |
| <a name="t154--similarity-score-is-not-a-copy-verdict"></a><a name="t154"></a>[T154](traps/authoring.md#t154) | Similarity score is not a copy verdict. |
| <a name="t155--a-real-world-number-in-a-stem-must-be-true-or-framed-as-suppose"></a><a name="t155"></a>[T155](traps/authoring.md#t155) | Use true real-world numbers or frame them as hypothetical. |
| <a name="t-qg-1--the-skill-that-never-loaded-frontmatter-that-is-not-valid-yaml-is-dropped-silently"></a><a name="t-qg-1"></a>[T-QG-1](traps/verification.md#t-qg-1) | a skill whose frontmatter is not valid YAML is silently dropped by the CLI — `devin plugins info` + the frontmatter lint are the check |
| <a name="t-qg-2--the-claim-set-agreed-with-itself-the-audit-cant-see-a-figure-built-to-its-own-record"></a><a name="t-qg-2"></a>[T-QG-2](traps/figures.md#t-qg-2) | a claim set that records the DRAWN ratio passes every audit line — the stem's own numbers must drive the figure, and the value be justified by them |
| <a name="t-qg-3--the-label-metric-that-never-saw-the-math-label-katex-overlays-are-html-not-text"></a><a name="t-qg-3"></a>[T-QG-3](traps/figures.md#t-qg-3) | Inspect KaTeX HTML overlays as well as SVG text. |
| <a name="t-qg-4--the-drift-check-that-never-saw-the-answer-the-read-side-knew-a-narrower-shape-than-the-write-path"></a><a name="t-qg-4"></a>[T-QG-4](traps/publication.md#t-qg-4) | a drift check whose READ side knows a narrower shape than the write path reports a clean publish as failed |
| <a name="t-qg-5--the-label-row-that-disagreed-with-the-verdict-one-rule-three-measurements"></a><a name="t-qg-5"></a>[T-QG-5](traps/figures.md#t-qg-5) | a width-invariant rule measured per width can straddle its own threshold — a label row says `ok:false` while the figure verdict says PASS |
| <a name="t-qg-6--the-revocation-check-that-saw-zero-rows-policy-less-rls-hides-auth-entirely"></a><a name="t-qg-6"></a>[T-QG-6](traps/publication.md#t-qg-6) | a reader role with SELECT on `auth.*` sees ZERO rows under policy-less RLS — a revocation count reads "revoked" while sessions are live |
| <a name="t-qg-7--the-gate-chain-that-never-ran-the-markdown-gate"></a><a name="t-qg-7"></a>[T-QG-7](traps/authoring.md#t-qg-7) | a gate that is never wired into the chain cannot fail it — a `$$…$$` on one line passed build, validate, publish and both visual checks; only the critic's standalone markdown-gate saw it |
| <a name="t-qg-8--two-variants-of-one-blueprint-read-as-one-question-to-a-student"></a><a name="t-qg-8"></a>[T-QG-8](traps/authoring.md#t-qg-8) | two variants of one blueprint in a batch read as ONE question to a student — build-staged refuses a second question carrying a batch-mate's `blueprint_id` (across sessions variants count as distinct) |
| <a name="t-qg-9--the-floater-sweep-that-can-never-land-in-the-pocket-it-was-given"></a><a name="t-qg-9"></a>[T-QG-9](traps/figures.md#t-qg-9) | Check placement on the final fitted canvas. |
| <a name="t-qg-10--clearance-scales-up-in-units-the-target-rule-does-not"></a><a name="t-qg-10"></a>[T-QG-10](traps/figures.md#t-qg-10) | Scale clearance, not the rendered target threshold. |
| <a name="t-qg-11---inferred-unhooks-a-value-from-the-stem-with-no-trace"></a><a name="t-qg-11"></a>[T-QG-11](traps/figures.md#t-qg-11) | Use inferred evidence only for values the student actually reads. |
| <a name="t-qg-12--the-medium-conditional-label-rule-that-shipped-a-figure-a-second-medium-cannot-render"></a><a name="t-qg-12"></a>[T-QG-12](traps/figures.md#t-qg-12) | a medium-conditional label rule ships figures that can never render on the other medium — drawn diagram text is simple English on EVERY medium (ADR 0021) |
| <a name="t-qg-13--the-wide-frame-that-starved-the-overlap-and-the-region-label-far-from-its-target"></a><a name="t-qg-13"></a>[T-QG-13](traps/figures.md#t-qg-13) | Keep overlap and region labels legible in the fitted frame. |
| <a name="t-qg-14--the-readability-rule-that-lived-only-in-a-checklist"></a><a name="t-qg-14"></a>[T-QG-14](traps/authoring.md#t-qg-14) | a readability rule enforced only by a hand-run checklist lets run-on approaches through while stems and parts have no layout rule |
| <a name="t-qg-15--singlish-can-corrupt-unit-symbols-and-point-labels"></a><a name="t-qg-15"></a>[T-QG-15](traps/authoring.md#t-qg-15) | Keep units and point labels out of Singlish transliteration. |
