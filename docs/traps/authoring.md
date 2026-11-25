# Authoring traps

[Trap index](../TRAPS.md).

<a name="t14"></a>

## T14 — `hasSwallowedMarkup` is `false` on an odd number of `$`

**Looked true:** the swallowed-markup gate catches unbalanced maths delimiters.
**Actually:** `Take $\pi as 22/7. Find $x$.` returns **`false`** — so the *instruction line* silently
renders as maths with no warning.
**The check:** an even-`$`-parity check is a **separate, mandatory** gate. Do not treat
`hasSwallowedMarkup` as covering delimiter balance.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T14 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t30"></a>

## T30 — `$`-parity and `hasSwallowedMarkup` never look INSIDE the delimiters.

**Looked true:** the two mandatory markup gates (**T14**) cover authored maths.
**Actually:** both only inspect delimiter *structure*. `Find $\fract{1}{2}$ now.` has balanced `$`, is
swallowing nothing, and **passes both** — then KaTeX throws and the child sees red error text. Measured
with the repo's own `katex@0.17.0`.
**The check:** compile every `math` segment with the repo's own KaTeX at `throwOnError: true` as a
**third** gate. It is three lines, and it is the only one of the three that can see a mistyped macro.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T30 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t143"></a>

## T143 — A familiar word is not the lesson's word

A Sinhala answer used a near-synonym for a named object. It was grammatical, but the lesson and its exercises used a different term, so the student's vocabulary did not match the source. Grep the lesson Markdown for the term before writing it (`grep -o '<root>[^ ]*' <lesson>.md | sort | uniq -c`); a close word is still wrong (a fold line was written `නැවුම් රේඛාව` for the lesson's `නැමුම් රේඛාව`; a floor tile `උළු කැටය` — a roof tile — for `ටයිල්`).

<a name="t144"></a>

## T144 — The stem gave away the part

A part asked the student to name a region, while the stem had already named it. Calling ∠AOB's region "the smaller sector" answered (a) "what is this region called?". Give the data (`$\angle AOB = 75^\circ$`), not the vocabulary.

<a name="t145"></a>

## T145 — New numbers do not make a worked example new

Do not lift the lesson's own worked example or activity as a part, and vary the part pattern across questions of one lesson — the critic flags both, and neither is a one-line fix after publish.

<a name="t146"></a>

## T146 — The answer check did not use the question

`check:` must compute from the question's numbers. A constant-only comparison (`12 > 11`, `60 != 120`) is refused; a classification or "which one" leaf gets `check: none — <reason>`.

<a name="t147"></a>

## T147 — A point name was swallowed by maths markup

Keep names outside the maths span: `OP $= 4.5$` cm, not `$OP = 4.5$ cm` (the markdown gate blocks the latter as swallowed prose).

<a name="t148"></a>

## T148 — Shared maths is not a Sinhala translation defect

A maths-only `final_si` identical to English is stored once, in `_english` (the Sinhala column is NULL by design, 0024). If a Sinhala reader should see a Sinhala word, write one around the maths (`කෝණවල එකතුව: $…$`).

<a name="t149"></a>

## T149 — The yes/no answer and its reason need separate paragraphs

A yes/no final gets its own paragraph. `No.` / `නැත.` first, the reason after a blank line. The Sinhala side splits into more sentences than the English and trips check-layout's 3-sentences-in-one-paragraph FAIL first.

<a name="t150"></a>

## T150 — A unit outside maths is prose

A unit outside the maths span is English prose. `final_si: "$22$ cm"` is refused as a copy of English; write `$22\ \text{cm}$` (shared maths-only) or put a Sinhala word around it.

The blocking unit-notation gate also refuses a Sinhala unit word immediately before a number or maths span (for example, `සෙන්ටිමීටර් $4$`), as well as after one. Keep the unit as an English symbol after the number: `$4$ cm`.

<a name="t151"></a>

## T151 — Sinhala inside a math span is not rendered as prose

No Sinhala words inside `$…$` (markdown gate M2). Name the quantity with a letter (`$w$`) and keep the words outside the span.

<a name="t154"></a>

## T154 — Similarity score is not a copy verdict

A high `similar` score on the finished batch usually means the same task chain. A tank question (capacity → water used → height of what is left) scored 0.83 against an existing row with the same three steps; new numbers would not fix it, so the question became "compare two containers → repeated pours, when does it overflow" (0.74, different steps).

<a name="t155"></a>

## T155 — A real-world number in a stem must be true, or framed as "suppose"

A signal-anchored stem (creative-signals) reads as fact to a student and a teacher. A rounded or invented figure stated as a real statistic ("Sri Lanka exported 500 kg of tea last year") is a false claim even when the arithmetic is right. Use the sourced value or "about" + a clearly rounded one; when the maths needs other numbers, change the framing ("Suppose a factory …"), never the fact.

<a name="t-qg-7"></a>

## T-QG-7 — The gate chain that never ran the markdown gate

**Looked true:** build green, validate clean, `--session` previews clean, published — the doc
was fine.
**Actually:** a display-math run written `$$…$$` on ONE line mid-paragraph round-trips to
`$…$` under the renderer's parser and flags `displayMathInline` — and NONE of build, validate,
publish, or either visual-check ever ran `markdown-gate.mjs`. Only the critic's standalone
`--fields` invocation caught it, one round in.
**The check:** run-gates `build` now runs the gate itself — it writes `<run>/fields.json` (the
same field set `run-gate.sh`'s `fields_py` produces: stems + sinhala, part texts, every
approach/final) and any `BLOCKED` field stops the chain before publish ever sees it. Shape that
passes: `$$` and `$$` on their OWN lines around the math. A gate that lives only in the critic's
hands is a story for TRAPS, not a safeguard.

*Source: this plugin — W9 run, 2026-10-03.*

<a name="t-qg-8"></a>

## T-QG-8 — Two variants of one blueprint read as one question to a student

**Looked true:** a blueprint is a parameterised question — instantiate it twice with different
seeds and the batch has two different questions.
**Actually:** same stem, same parts, same figure kind — only the numbers differ. On the page a
student sees the same question twice. (Owner ruling 2026-10-03.)
**The check:** `build-staged` refuses a batch where two questions carry the same `blueprint_id`
— at most one variant per blueprint per batch. Instantiate the second variant in a LATER run:
across sessions variants count as distinct, so `precritic-lint --existing` may still WARN a
fresh variant against a row from another session — expected, read the WARN and move on.

*Source: this plugin — W10d, owner ruling 2026-10-03.*

<a name="t-qg-14"></a>

## T-QG-14 — The readability rule that lived only in a checklist

**Looked true:** `author-question-answers` §4.1c described readable approach paragraphs, and its
hand-run jq check looked for paragraphs over 180 characters.
**Actually:** `run-gates build` never ran that check, so it could not stop a build; stems and part
texts had no layout rule at all. A published batch shipped single-paragraph approaches the owner
rejected as cluttered.
**The check:** `tools/check-layout.py` now checks stems, parts, approaches and finals, and
`run-gates build` runs it after markdown-gate. Blank lines separate prose paragraphs; any FAIL
stops the build and every WARN must be read. Dotted abbreviations (ප.ව., පෙ.ව., a.m.), currency
markers (රු./Rs.), spaced time abbreviations (ප. ව./පෙ. ව.), dot-run blanks and line-start
Roman-numeral list markers are not sentence ends for the gate. The authoring rules live in
`author-question-answers` §4.1c and `generate` step 4.

*Source: this plugin — owner ruling, 2026-10-13.*

<a name="t-qg-15"></a>

## T-QG-15 — Singlish can corrupt unit symbols and point labels

**Looked true:** a Sinhala-field sentence can keep unit symbols and point labels in English while
Singlish mode is enabled.
**Actually:** Admin Singlish mode used to transliterate `cm` as `ක්ම්` and the point label `AB` as
`ඇඹ්`, changing standard notation into Sinhala text.
**The check:** keep units beside numbers in English symbols in both languages (`$4$ cm`), and keep
point labels in English. The blocking `unit-notation.py` gate refuses Sinhala unit words or
abbreviations immediately before or after numbers.

*Source: this plugin — unit-notation gate and blind-planning work.*
