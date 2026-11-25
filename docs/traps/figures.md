# Figures traps

[Trap index](../TRAPS.md).

<a name="t96"></a>

## T96 — A schema-legal field the renderer ignores is a figure that lies.

**Looked true:** the VDD schema accepts `label` on an `angleMark`, so labelling a right angle is supported.
**Actually:** for `variant: "right"` the renderer **never draws the label** (`VddRenderer.tsx:182-187`).
`safeParse` passes, the document is legal, the figure renders — **and the label is silently gone**. That is
S6's founding failure class (*"figure silently missing an element"*) arriving through the schema rather than
through the canvas.
**The check:** ⚠️ **Legal is not rendered.** For every element type and every variant, confirm the fields you
set actually appear in the output SVG — a `safeParse` pass proves the document is well-formed, not that it
draws what you wrote. ⇒ Step 2 also found **no italic on `text`** and **no per-segment stroke width**.

⚠️ **A pair-render sweep then found EIGHT MORE, two of them live in the shipped batch:** `arrow.headSize`
(**ignored, live ×3**), `defaults.fontFamily` (**ignored, live ×9**), `rotation` (**ignored on 11 of 15
element types**), `arc.sweep`, `z`, element `opacity` on fills, `defaults.opacity`, and `groupId`/`link`.
All schema-legal, all `safeParse`-clean, all silently dropped at render. ⇒ **The gap between "the schema
accepts it" and "the renderer draws it" is a SURFACE to sweep, not a bug to fix once.** Render each element
type twice — with and without the field — and diff the SVG. That is how all nine were found.

⚠️ **The "no way to say not to scale" complaint was WRONG, and the correction matters more.** The actor
reported drawing an angle at 41.6° and labelling it 20°. Measured off the printed figure's own
`get_drawings()`: **the paper prints x = 41.72°, y = 48.28° and a "110°" drawn at 131.58°** — **the source is
not to scale, and the VDD reproduced it to 0.15°.** Reproducing the paper's own scale error is correct
behaviour. And VDD *can* say it: four other figures in the same batch place free `text`. ⇒ **Before recording
a tool limitation, check that the tool actually lacks it — a self-accusation is as unreliable as a
self-verification (T25).**

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T96 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t98"></a>

## T98 — An `angleMark` label can render on the OPPOSITE SIDE of the vertex, and it is live in the spec's own golden fixture.

**Looked true:** an `angleMark` with `label: "58°"` draws its arc at the vertex and its label beside that
arc. T96 already swept the fields the renderer *ignores*; a field it *honours* is fine.
**Actually:** the label position is `bis = ((from + to) / 2) % 360` (Admin `DiagramRenderer.tsx:176`, Web
`VddRenderer.tsx:181`) — the **arithmetic mean of two angles in `(-180, 180]`**, which points the wrong way
whenever the two rays differ by more than 180°. The arc is correct (`arcPath` normalises the sweep); only
the text moves. **Measured 2026-08-26 in real Chromium on `/diagtest`, on the DSL spec's own §7.1
`TRIANGLE` fixture** — the one the tests and the sandbox are built on: at vertex `B`,
`angleOf(A,B) = -98.75°`, `angleOf(C,B) = 172.69°`, difference **271.44°**, so `bis = 36.97°` and the
`58°` label renders **outside the triangle, below-right of B**, where the true bisector is **-143.03°**.
Reading order alone would attach it to the wrong angle on any busier figure. ⚠️ Swapping `from` and `to`
does not help — the mean is symmetric.
⚠️ **PROSPECTIVE, NOT LIVE — and the first write-up of this trap implied otherwise.** Measured 2026-08-28
over every stored `angleMark` in production: **6 of them, and 0 meet the condition.** The largest span is
**99.94°** (a live figure's `angB`, labelled 125°), and the three `variant: "right"` marks are exactly 90°.
⇒ **No student is looking at this defect today.** It is reproducible in the DSL spec's golden `TRIANGLE`
*fixture*, which is a test/sandbox artefact and not published content. The word *"live"* in the first
version of this entry would have been read as *"in production"*, and that was wrong.

```sql
WITH f AS (SELECT diagram_dsl d FROM questions WHERE diagram_dsl IS NOT NULL
    UNION ALL SELECT diagram_dsl FROM sub_questions WHERE diagram_dsl IS NOT NULL
    UNION ALL SELECT diagram_dsl FROM answers      WHERE diagram_dsl IS NOT NULL
    UNION ALL SELECT diagram_dsl FROM sub_answers  WHERE diagram_dsl IS NOT NULL)
SELECT count(*) AS angle_marks, max(span) AS max_span, count(*) FILTER (WHERE span > 180) AS t98_hits
FROM f, jsonb_array_elements(d->'elements') e, LATERAL (SELECT abs(
        degrees(atan2((e->'from'->>1)::float - (e->'vertex'->>1)::float,
                      (e->'from'->>0)::float - (e->'vertex'->>0)::float))
      - degrees(atan2((e->'to'->>1)::float   - (e->'vertex'->>1)::float,
                      (e->'to'->>0)::float   - (e->'vertex'->>0)::float))) AS span) x
WHERE e->>'type' = 'angleMark';        -- 2026-08-28: 6 · 99.94 · 0
```

⚠️ **Keep it anyway, and keep it prospective.** It costs one line in a render check, the condition is
mechanical, and the next figure with a reflex or a wide-span mark meets it. ⇒ **The general shape: a defect
with zero current instances is still worth a named check when the check is cheaper than the audit that
would find it later.** Say *"0 instances today"* rather than dropping it, and never say *"live"* about
something measured in a fixture.

⚠️ **A FIX WAS IN FLIGHT WHEN THIS WAS WRITTEN, AND THAT DOES NOT RETIRE THE CHECK.** Measured
2026-08-26: `origin/main` and `HEAD` carry the mean at **Admin `:176` / Web `:181`**, and both repos'
**working trees**, on a branch called `fix/vdd-renderer-silent-field-drops`, already carried
`const bis = bisectorDeg(from, to, el.reflex);` (Admin `:387`, Web `:395`) — **uncommitted**. ⇒ **Re-grep
before citing either line**, and treat the row as *"which of the two is deployed right now?"* rather than
as a fact. ⚠️ **And do not delete the check when the bug goes**: the bug is one instance of a class
(**T96**) whose surface has to be swept per element type and per field, and a label in the wrong *place* is
invisible to a sweep that only asks whether a field was *dropped*.

**The check:** ⚠️ **read the label's own `x`/`y` out of the SVG and confirm it lies inside the angle it
names** (S6b §4.2 has the `page.evaluate()` snippet). Condition to test for:
`abs(angleOf(from) - angleOf(to)) > 180`. The fix in a document you author is a separate **`text`**
element positioned on the true bisector (measured: the label moved into the angle when that was applied).
⇒ **T96 said "legal is not rendered"; this is its sibling — RENDERED IS NOT RENDERED WHERE YOU MEANT.** A
sweep for dropped fields cannot find a field that is honoured and misplaced, so both sweeps are needed.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T98 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t99"></a>

## T99 — Collapsing collinear strokes into one element is right; the side you drop while doing it is invisible to every check you have.

**Looked true:** a printed figure's strokes map to VDD elements, so drawing them and counting them against
your intent list is enough. Collapsing `AC` + `CE` into one `line A→E` through C is *better* than two
elements, because the renderer then cannot hinge them apart.
**Actually:** measured while S6b was being written, on the worked example in S6a §4 — six printed strokes
(`AB AC BC BF CD CE`) were collapsed into three `line` elements, and **`AB`, the vertical side of the
triangle, was simply never written.** `VddDocument.safeParse` passed. `checkDiagram()` returned `[]`. The
element count matched the intent list, because the intent list was written by the same reader who dropped
the side. The rendered figure was a *different, entirely plausible* figure — a triangle `BFC` instead of a
right-angled `ABC` with a ray `BF` — and it was found **only by looking at the render**.
⚠️ **And a second element was missing for a different reason, on the same figure.** The printed
**right-angle mark at B** is a `type: "fs"` white-filled rectangle, and the exploratory dump had filtered
`get_drawings()` to `type == "s"`, so the claim set asserted the angle was *"not marked on the page"* and the
drawing omitted the mark. ⇒ **Two mechanisms, one symptom:** an element you collapsed away, and an element
you never saw. Both pass `safeParse`; both change what the figure says.
**The check:** ⚠️ **count against the CLAIM SET, never against your intent** — and make sure the claim set
was written from a dump that filtered nothing (S6a §2.1). S6b §5.2: every `segments` entry in the claim set
must be *covered* by some element (an element whose endpoints are the two named points, or a
`line`/`polyline` on which both lie), every `labels` glyph must appear in exactly one element, every mark
claim must have an element, and no element may be unaccounted for. That check is text-only — claim set plus VDD JSON, no picture — so a
second agent can run it. ⇒ **This is T25 applied to drawing:** an inventory you wrote yourself is not an
independent check of your own work, and *"I counted my elements"* is exactly that.

⚠️ **AND THE SHAPE RECURRED INSIDE THE TOOL BUILT TO CATCH IT, WITHIN A DAY.**
`audit-claim-set.py`'s parser folded any line under `claims:` with no `|` into the *previous* claim's
`note`. Strip the separators from one claim and it **vanished** — 71 assertions, **0 failures, exit 0** —
and S12 §3.2 gates a handoff on exactly that exit code. Found by a critique, not by the self-test, because
every `F-CLAIM` mutation had been a *wrong* claim and none had been a *malformed* one. Now a claim-shaped
line without separators is a hard parse error, and the footer prints `claims parsed: N`.
⇒ ⚠️ **A silent-deletion defect will reappear in the checker you write for it, because the checker's input
is also a document that can lose a line.** Two rules that generalise: **count what you parsed and print
the count**, and **make one mutation MALFORMED, not merely wrong** — a validator that has only ever seen
well-formed bad input has not been tested on the failure mode it exists for.

⚠️⚠️ **AND THE FIX WAS ITSELF THE SAME BUG, ONE LEVEL DOWN — WHICH IS THE MOST USEFUL PART OF THIS ENTRY.**
The repair tested the *shape of the id*: `if the first token does not match [A-Z]\d+[a-z]? then this line
is a note continuation`. Measured the next day against the real worked example, injecting a pipe-less claim
line: **`k24` · `K24.` · `(K24)` · `KK24` · `K24ab` · `K-24` · `24` · `k4b` — 8 of 8 silently swallowed**,
each producing a report **byte-identical to the clean one**. ⚠️ **So "count what you parsed" did not catch
it either: the count was unchanged**, because the smuggled line never became a claim to count.

⇒ ⭐ **THE RULE: A NEGATIVE TEST FAILS OPEN ON EVERY SHAPE YOU DID NOT ENUMERATE; A POSITIVE TEST FAILS
CLOSED.** *"If it does not look like X, treat it as Y"* is a promise about the infinite set of things that
are not X, and you cannot enumerate that set — every mis-typed, mis-cased, bracketed or punctuated id is a
new hole. Invert it: decide what a line **is** from something structural you control, then require the
rest. Here the structural fact is **where the line starts**: the first content line under `claims:` sets the
claim indent, every line at or left of it **is** a claim and must have its separators, and a note
continuation must be a real hanging indent (≥ 6 columns further in) — anything between is refused as
ambiguous rather than guessed. Re-measured across **20 id shapes × 5 indents (0, 2, 4, 6, tab) = 100
combinations: 0 escapes**, and a genuine wrapped note still parses.
⇒ And note *where* the class hides: the same shape is in **S1b's regime chain** (a first-match-wins `if`
ladder whose final `return "R2"` is a negative test — **T17**), in **T93's** OCR filters, and in this
checker's own `else` for unknown predicates, which is now a failure rather than a skip. **Whenever you
write "otherwise, assume", write down what you are assuming about the set you did not name.**

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T99 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t104"></a>

## T104 — The wrong answer that agrees with its own figure. No gate this suite owns could have caught it, INCLUDING the one nobody has built yet.

**Looked true:** the stored answer follows from the stored diagram, the diagram's `a11y.description`
describes the diagram, and the `approach` states facts that are all individually correct — so the question
is internally coherent and **every gate passes**.

**Actually:** a published grade-10 question drew a heavy segment
**between** an open −2 and a filled 2 and answered `$-2 < x \le 2$`, while the paper prints two
**outward** rays and means **`x < −2` or `x ≥ 2`** — *the exact complement*. It had been live and
**human-signed** (`verified_at 2026-07-04T13:07:23Z`) for eight weeks.

⭐ **THE FINDING IS THE GATE TABLE, NOT THE DEFECT.** Every gate this suite owns was **run against the
defective document** and each one passed it. Measured 2026-08-30, not asserted:

| gate | what it said about the WRONG Q15 | why it is blind |
|---|---|---|
| `VddDocument.safeParse` | ✅ **valid**, 24 elements | it validates *shape*. A heavy line from −2 to +2 and a heavy line from −2 to −∞ are the same schema |
| `checkDiagram()` | **`[]` — not one advisory** | ⚠️ **it has TWO checks, and BOTH are gated on the same thing** — a labelled-vs-drawn angle comparison per `angleMark` (`Vibhaga-Admin/src/components/diagram/validate.ts:34-47`) and a triangle angle sum over exactly three numeric `angleMark` labels (`:49-57`). Both need an `angleMark` carrying a numeric label. **A number line has no `angleMark` at all**, so the only semantic gate in the codebase **cannot fire on this class of figure by construction** — 60 lines, one element type |
| `markdown-gate.mjs --fields` | **0 BLOCKED** | it checks markdown deletion and delimiter hazards. `$-2 < x \le 2$` is perfectly well-formed markdown — and perfectly wrong |
| KaTeX compile (**T30**) · S9 `G4` `$`-parity · `hasSwallowedMarkup` | all pass | `-2 < x \le 2` is valid LaTeX with even `$` and no swallowed markup |
| S11 (structural audit) | would **reconcile perfectly** | it asks *did it land*, never *is it true* |
| `stagedQuestionSignature` / **T77** drift | **no drift** | equality between two stores says nothing about either being right |
| ⭐ **an answer-vs-figure self-consistency check** — *the obvious thing to build* | ⛔ **WOULD HAVE PASSED IT TOO** | the figure drew `-2 < x ≤ 2`, the answer said `-2 < x ≤ 2`, the `a11y.description` said *"the segment **between them** highlighted"*, and the `approach` named exactly the two facts that were right. **Four artefacts, mutually consistent, all four wrong.** |

⚠️ **The last row is the entry.** The natural response to a wrong answer beside a wrong figure is *"add a
check that the answer follows from the figure"* — and that check was **already satisfied** by the defect.
**A self-consistency check is not a correctness check.** S8 §0.5 already says this about two *derivations*
of one answer; this is the same failure one level up, across four *artefacts*, and it is worse, because the
four look like independent evidence.

⭐ **AND THE DECISIVE EVIDENCE WAS A DIRECTION, WHICH NO DATABASE COLUMN RECORDS.** What settled it was
`page.get_drawings()` on the source page: path **#31** is a **1.4173 pt** stroke running x **78.01 →
161.80** (i.e. −4.883 → **−2.000**, *leftwards*, into the arrowhead), and path **#33** is `type:"s"` with
`fill=None`. Nothing in `questions`, `answers`, `diagram_dsl` or the staged doc stores *which way the
printed ray ran*. ⇒ **A defect whose evidence exists only outside the system cannot be gated from inside
it.** The only thing that caught this was S13 — an independent read of the source page.

⇒ **The checks:**

1. ⭐ **Before building a gate, ask what the defect's evidence IS and whether the gate can see it.** Write
   down the single datum that settles the case; if it is not a column, a file or an HTTP response the gate
   can reach, the gate cannot fire and building it buys a false assurance. **This is the question that
   would have stopped "answer-vs-figure consistency" being proposed as the fix.**
2. **The gate that WOULD work, and it is cheap:** for a figure carrying an S6a **`axis` / `interval`**
   claim set, **sample points** — parse the answer's inequality and test the claim set's `interval`
   membership at each labelled tick. It runs off the *stored* VDD plus the *stored*
   `final_answer_latex`, needs no page, and **it fires here on one point: 0 is on no heavy part and
   `-2 < x ≤ 2` contains 0.** (This is S8 §3's "second method" as a machine check —
   [S6a](../../skills/read-figure-claim-set/SKILL.md) §3.2 owns the `interval` predicate.)
3. ⛔ **ITS PRECONDITION IS THE WHOLE POINT: an S6a CLAIM SET MUST EXIST.** The claim set is the only
   artefact that says *what the printed figure means*, independently of the drawing. **Without it the
   check degenerates into comparing the drawing with itself** — which is exactly the passing
   self-consistency check above, wearing a different name. ⇒ **"We will add the sampling gate" is not a
   plan unless S6a ran.** A figure with no claim set is not gateable for correctness, and that fact should
   be reported as a limit rather than left to be discovered by a student.
4. ⚠️ **State a semantic gate's SCOPE, or an operator reads `[]` as "the figure is fine".**
   `checkDiagram()` is **two** checks, and both are gated on an `angleMark` with a numeric label
   (`validate.ts:34-47`, `:49-57`) — so it is silent on
   number lines, sectors, grids, patterns and area models: **9 of the 20** figures live when
   [S6a](../../skills/read-figure-claim-set/SKILL.md) §3.5 took its census (2026-08-26; **22** live today) fall in
   classes it cannot reach at all. An undocumented scope makes an empty
   result look like a clean bill of health (**T102**, one level up: there the gate had no *input*; here it
   has no *jurisdiction*).
5. **Read the page.** Every other row of that table was cheap and green; the one thing that worked cost a
   `get_drawings()` call on the PDF.

*(Found 2026-08-30 by S13 `critique-onboarded-content` auditing three grade-10 questions from the retired
`Vibhaga-Ingestion` pipeline. The corrected answer, figure and `a11y` are live today; the wording of S8 **§4.1b** is the worked `approach` half of this entry.
⚠️ **The signature was destroyed by the fix, and that was the point, not the cost** — it attested to the
complement. Companion to **T94/T100** — a defect no check was looking for — and to **T13**: three of the
gates in that table had never been watched fail on *this class* of figure, so "they pass" was a claim.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T104 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t125"></a>

## T125 — A question figure's `a11y.description` can state the answer the item asks for

**Looked true (run 13, S13 chunk I-11-20, 2026-09-10):** the a11y checks (S6b §0.3/§3.3, vdd-check item 2, S13 C4)
verify the title is real and the description non-empty — i.e. *the figure is honestly described*.
**Actually:** the stored concave-octagon figure on a "count the acute and reflex angles" item described itself as
*"the four tips are acute (about 72 degrees each), the left and right points are obtuse (about 106 degrees), and the
two notches are reflex (about 290 degrees)"* — a screen-reader student is **read the classified answer** that a
sighted student must still work out vertex by vertex. Every green a11y gate passes it because the text is accurate;
the failure is that it is accurate *about the answer*, not the apparatus.
**The check:** for a **question** figure, read `a11y.title` + `description` against the item's own ask — if the item
asks for a count/classification/measure, the description must carry shape and direction without naming the classes
or stating the counts (the asymmetry with §3.2's answer-figure rule — *"the title must state the answer"* — is the
point: question describes the apparatus, answer states the result). Report as MINOR (pedagogical leak, not a wrong
answer) unless the item is otherwise unusable without the leak.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T125 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t128"></a>

## T128 — A correct "never" rule applied beyond its real constraint manufactures its own defect

**Looked true (run 13, S6b ii01a/ii01b, 2026-09-11):** T-S6b-6 says a figure cannot be bilingual (one
`diagram_dsl`, one `text.value`), so the claim-set labels and drawings removed every Sinhala word — the
tally table's 3 column headers + 5 row names, the pictograph's 5 day names — and declared stem prose bound
them by position instead.
**Actually:** the constraint is *bilingual*, not *Sinhala*. These questions are mono-medium Sinhala — no
second-medium sibling will ever render the figure — so stripping structural labels left a printed table's
header row and label column EMPTY on the student's page: a figure that no longer matched the paper and
needed a prose paragraph to stand in for ink. The owner saw it instantly. The paper's own
`සෙවසතුවක්`-as-`ඝනවස්තුවක්` ruling the same day is the text-side twin: fidelity governs *content*, not
misspellings — a printed non-word resolves to the standard textbook term (declared), while a real variant
(`ගණත`, `හාවිත`) stays as printed.
**The check:** before applying a `never`/`always` rule, name the constraint it protects and test whether
this case trips *the constraint* (here: a second medium consuming the DSL — impossible), not just the
literal wording. vdd-check's hygiene rule is now medium-aware (`--medium sinhala`) — ⚠️ *superseded
by ADR 0021 (T-QG-12): drawn text is simple English on every medium, the flag no longer widens it* —
and claim sets carry
`budget:`/`allow:` so build-staged can run the whole suite without per-figure flag juggling.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T128 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t136"></a>

## T136 — A constructed claim set that "passes" Audit A because you read its footer, not its exit code

**Looked true:** ten constructed answer-figure claim sets, each run through `audit-claim-set.py` in a shell loop with
`| tail -4` — every footer read *"recognised, NOT verifiable here: …"* and the loop's own exit code was 0.
**Actually:** every one of the ten had **exited 1**. `tail` swallowed the failures, and a `for` loop's exit status is
its last command's (the `tail`). The failures were format, not content, and all three are specific to a `constructed`
set written from run 1's template: (1) a `labels:` inventory with no `label "<glyph>" names <target>` claim per glyph
(the tool checks glyph → claim closure — run 1's sets bound every declared label); (2) `points:`/`segments:` declared
with an empty `anchors:` block — a constructed figure has no PAGE anchors, so the **canvas** coordinates go in
`anchors:`, exactly as the tool's own `SELF_TEST_CONSTRUCTED` fixture does, and Audit A then verifies the `equal` /
`right` / `parallel` / `on` / `ratio` / `angle` claims against them instead of skipping them; (3) `derive` values must
be exact to 1e-9 (`80 / 60 = 1.3333` fails; `80 * 3 = 240` or `216 * 216 / 3 = 15552` passes — pick an expression whose
value is exact).
**The check:** never pipe a gate through `tail`/`grep` without capturing `${PIPESTATUS[0]}` (or run it once per file
and print `exit=$?`); and for a constructed set, fill `anchors:` with the canvas coordinates you will draw at — it turns
Audit A from a parser into a geometry check (62–97 assertions per figure on the run below).

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T136 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t152"></a>

## T152 — Default figure descriptions can reveal answers

Give every template spec its own `title` + `description` in the question's medium. The default a11y text is English and states counts ("15 equal squares … 6 fully shaded", even "0 cut by a diagonal") that answer part (a) (T125); a Sinhala-medium run needs Sinhala a11y (rule 6).

<a name="t153"></a>

## T153 — The requested figure change did not fit

A "how many more" part must fit the cells actually drawn. "Cut more squares in half" needed 4 empty squares on a grid with 3 left — count the free cells on the spec before fixing the target fraction.

<a name="t-qg-2"></a>

## T-QG-2 — The claim set agreed with itself: the audit can't see a figure built to its own record

**Looked true:** the generated cuboid's claim set recorded `ratio len AB / len BC = 1.5`, the anchors
agreed, `audit-claim-set.py` reported a pass — so the figure was right.
**Actually:** the stem said **5:2**. The claim set had been written down from the *drawing*, not from
the stem — Audit A then recomputed every numeric claim against the very anchors that carried the same
wrong value and found self-consistency, so the render it gate-kept passed too. A claim set authored
from its own figure is a tautology: every check inside the loop agrees, and the only witness that could
disagree — the stem's own numbers — was never consulted. That is why `audit-claim-set.py` now REQUIRES
a `stem:` header on every `constructed` set and refuses a `ratio`/`angle` claim whose value the stem's
numbers (or a transitively backed `derive`) do not justify.
⚠️ **The stem-pair check alone has a hole: the incident stem itself stated 5, 3 AND 2 — and
`3 / 2 = 1.5` IS stem-justified.** Three further checks close it (review R1 + critique R3):
**LABEL-RATIO** — a ratio claimed on segments carrying numeric labels (`label "5 cm" names DC`)
must equal the *labelled* numbers' ratio; **MIS-CITATION** — a `derive Kn` cited in the note must
exist *and* match the claimed value; and the **DRAWN-VS-LABEL pair check** — every *pair* of
segments carrying numeric labels must have a drawn anchor ratio equal to the printed ratio, so the
forge that claims 1.5 on the *unlabelled parallel* edge while "5 cm"/"2 cm" print on the other face
still fails (the labels are ground truth the claim cannot route around). A deliberately
foreshortened edge — an oblique-projection depth edge — is declared by naming its *label claim's*
id in `ambiguous:`. (And the dodge that binds the numeric labels to names `segments:` never
declared — a face diagonal `AC` — fails outright: a two-capital label target must be a declared
segment, so the pair check can always measure it.) This is why `cuboid` (and
`house_pentagon`/`rectangle_points` where labels exist) claim the ratio on the
**labelled** segments. And it is why `tools/vdd_templates.py`
exists at all: a template takes the stem's numbers, refuses any parameter the stem never states
(`require_stem`), computes the geometry FROM them, and emits the claim set itself — there is no hand
step where the drawn ratio can be copied into the claims.
**The check:** for any figure a template can build, build it — the numbers come from the stem by
construction. For a hand-built claim set, write every `ratio`/`angle` value from the STEM text first,
then draw to it; if the drawing you have in mind doesn't match the stem's numbers, the drawing is
wrong, not the stem. Never read a value off the canvas back into a claim (that is the draw→claim→audit
loop that passed 1.5 vs 5:2). Cited by `figure-templates` and `generate` §4.

*Source: this plugin — the 2026-09-29 cuboid incident; the audit change landed in W0 (`audit-claim-set.py`
check 2d) and the templates in W3.*

---

<a name="t-qg-3"></a>

## T-QG-3 — The label metric that never saw the math label: KaTeX overlays are HTML, not `<text>`

**Looked true:** a five-sided figure with four `<text>` side labels and one `math` label passed
every gate — `vdd-check` reported its label metrics clean, the render audit passed, so the figure
was signed off.
**Actually:** two independent blind spots hid the same defect. (1) DiagramRenderer draws a `math`
element as a **KaTeX HTML overlay** inside the figure's `[role="img"]` container — not an SVG
`<text>`, not a `<foreignObject>` — so vdd-check's label metric (a `svg.querySelectorAll("text")`
walk) never measured it at all. (2) vdd-check renders in a bare harness with no `--font-sans`
variable, while DiagramRenderer's text stack is `var(--font-sans, …)` — so a **serif KaTeX face
sitting among sans `<text>` labels**, and a math label drawn **−2.5 px into a stroke**, both
passed every gate. Measured on the 2026-09-29 house-pentagon figure (described synthetically —
no stem text, no ids): `font mix: KaTeX math ×1 + text ×4` plus the math label's centre inside a
slant edge. The same render also showed text labels clipped to 4.7 px from the canvas edge and
sitting 1.3 px off strokes — invisible to every check that ran.
**The check:** `tools/visual-check.mjs` renders through the real Admin `/diagtest` page — real
`globals.css`, real next/font (Inter + Noto Sans Sinhala resolve `--font-sans`), real
`html[data-theme]` — and its in-page measurement collects *both* `<text>` runs and `.katex`
overlays, converting overlay client-rects through `svg.getScreenCTM().inverse()`. Rules:
`font` (any math+text mix or two text faces → FAIL), `stroke` (a math label's bbox is measured
against strokes like any other label). Cited by `visual-check`.

*Source: this plugin — W4, 2026-09-30; the stored production figure failed on first real render
through `/diagtest`.*

---

<a name="t-qg-5"></a>

## T-QG-5 — The label row that disagreed with the verdict: one rule, three measurements

**Looked true:** visual-check reported a number-line figure `verdict: PASS` with `findings: []` —
while its own per-width label rows said `ok:false` at 375 and 768 for every point label.
**Actually:** the `target` rule is a canvas-unit invariant (a point label >1.5×fontSize from its
own point), but the DOM box was re-measured at every render width and px quantisation moved the
distance across the bound — 26.8u at 320, 27.5u at 375. Rows folded each width's measurement; the
finding sampled only width[0], so the same label both failed and passed.
**The check:** one target result per label, computed on the least-quantised width, now governs the
rows and the finding alike (`visual-metrics.mjs`); `build_number_line`'s point-label lift was
retuned to the measured DOM box reach (~0.5·fontSize, not the text-run bound) — pinned by
`tests/test_visual_metrics.mjs` and `tests/test_vdd_templates.py`.

*Source: this plugin — W8 dogfood, 2026-10-02.*

<a name="t-qg-9"></a>

## T-QG-9 — The floater sweep that can never land in the pocket it was given

**Looked true:** `finish()`'s `_near` floater search tries 16 directions × fixed 6-unit steps
around the anchor — if a clear spot exists near the dot, the sweep finds it.
**Actually:** it only finds spots its fixed-step grid happens to hit. A coordinate-plane point
surrounded by grid lines leaves a clear pocket that is a thin SLIVER — (cell − label − 2×
clearance) ≈ 1–6 units tall centred mid-cell — and the sweep steps past it at every distance.
`stroke-clearance rule rejected 112 of 112` meant "your sweep granularity never sampled the
pocket", not "no pocket exists". Same trap for labels that must sit between a segment and a
neighbouring anchor (`own-anchor` eats everything outside a narrow band).
**The check:** labels whose legal positions are pockets between strokes — grid-cell letters on
`coordinate_plane`, the `MN` foot letters and `"3 cm"` value on `parallel_lines` — are placed as
FIXED texts by `_pick_label_spot`, which evaluates candidate centres against exactly the rules
`finish()` will apply (stroke gap, label gap, own-anchor) and picks the best. `_near` floaters
stay for spots with real freedom (endpoints, axis letters) — the origin's `O` and `0` are
pocket-seated too, because a floater's sweep stacked `O` on top of `0` (W11 review).

*Update 2026-10-04 (owner ruling):* a point letter may sit **over** the faint ruling lines when
the pockets run out — "if they are visible, that is fine". `coordinate_plane` keeps the
clear-pocket search as pass 1; only when a letter (or the `O`) seats nowhere at any size does a
fallback pass treat the `gv*`/`gh*` ruling lines as non-obstacles (axes, ticks, joins, dots,
labels and the edge still count), and then ALL the figure's letters draw in the accent colour
`#1d4ed8` — one ink per figure — with a `describe` claim recording it. `vdd-check` and
`visual-check` exempt exactly those ids (the structural marker — never colour or width) from the
label↔stroke rule, and `finish()`'s pre-flight does the same. The old measured-limit refusal
(`x_max ≥ 7` refuses with `grid`+letters) is gone: the whole 10×10 envelope builds; a refusal now
means even the fallback found no seat.

*Source: this plugin — W11, 2026-10-04.*

<a name="t-qg-10"></a>

## T-QG-10 — Clearance scales UP in units, the target rule does NOT

**Looked true:** a label placed `clearance + padding` units from a stroke is safe — the padding
is tiny and the stroke rule is the tightest one anyway.
**Actually:** `_clearance_units(px, span)` converts rendered px to canvas units at ~`px/s`
(s = 294/span once the figure outgrows the plate), so on a wide canvas "8 px clear of the axis"
becomes a ~19-unit gap. visual-check's **target** rule measures a short label's distance to the
nearest painted geometry in CANVAS units and fails past `1.5 × fontSize` — it does not scale.
The two rules squeeze from opposite ends: `bar_chart` category labels sat ~23u under the
baseline (fail >21u) and the coordinate plane's `"0"` at the numeral-column corner sat ~29u
from the origin (fail >22.5u — the diagonal seat multiplies the required gap by √2).
**The check:** any fixed label 1–2 glyphs long must be seated with BOTH constraints in the
score: stroke/label gaps ≥ the scaled clearance AND box-to-nearest-paint ≤ `1.5·size`. The
"0" shares the point-letter pocket search for exactly this reason; corner seats that must
clear two perpendicular strokes can be unreachable — seat it hugging ONE axis instead.

*Source: this plugin — W11, 2026-10-04.*

<a name="t-qg-11"></a>

## T-QG-11 — `| inferred` unhooks a value from the stem with no trace

**Looked true:** a `reads P v on XY` claim's evidence word is bookkeeping — `stem` means the
stem states it, `inferred` means it doesn't — and either way the VALUE is still checked.
**Actually:** the stem-justification check only bites on `ev stem`. Flipping `reads A 4 on OY`
from `| stem` to `| inferred` in a stem-mode claim set passed the whole audit — the value was
then justified by NOTHING (measured and verified on a W11 stem-mode coordinate plane).
**The check:** in a `constructed` set a `reads` claim whose evidence is not `stem` FAILS unless
the set carries the read-the-figure declaration — a `describe` claim whose text says the values
are "figure content". Both W11 figure modes emit that line word for word; a set in stem mode
never does, so a flipped evidence word dies. (Same round: a `parallelMark`'s chevrons are real
strokes — the transversal crosses every line AT ITS CENTRE, so a mark's default `at` = 0.5 sits
on the crossing; the builder probes `at` positions until the marks clear it and MN by 8 px.)

*Source: this plugin — W11 review round 1, 2026-10-04.*

<a name="t-qg-12"></a>

## T-QG-12 — The medium-conditional label rule that shipped a figure a second medium cannot render

**Looked true (first G7 run, session f040ebb5, 2026-10-04):** T-S6b-6 as rescoped made drawn label
language a function of the question's `medium` — so on a sinhala-medium run the Q5/Q6 bar charts
shipped with Sinhala category names and axis titles, and every gate (`medium='sinhala'` builder
check, `vdd-check --medium sinhala` rule 3) passed them as correct.
**Actually:** a figure is one `diagram_dsl` consumed by whichever medium renders it — a chart whose
categories are Sinhala can never be reused or previewed on an English surface without redrawing, and
the Sinhala-shaping/KaTeX risks stayed live in review surfaces that render it regardless of scope.
The rule that was meant to protect the mono-medium case also *blessed* the content that defeats
re-use. ADR 0021 closes it: **every piece of text drawn in a figure is simple English on every
medium** — point letters, labels, axis/category/series/value titles, units, card/ring texts. The
a11y `title`/`description` are not drawn and keep the question's medium.
**The check:** `_check_label_texts` (vdd_templates.py) and `vdd-check.mjs` rule 3 refuse any
codepoint U+0D80–U+0DFF in drawn text unconditionally — the message names the label and cites
`diagram text must be simple English (ADR 0021)`. `--medium` is still accepted (other checks and
the flag's callers keep working); it no longer widens the label rule.

*Source: this plugin — W12, 2026-10-04 (session f040ebb5, Q5/Q6 bar charts).*

<a name="t-qg-13"></a>

## T-QG-13 — The wide frame that starved the overlap, and the region label "far from its target"

**What happened (W14, `venn_sets`).** Two traps in one template. (1) Two five-letter words in A∩B
refused at every radius up to 150 units although the lens holds them at 130 standalone: the
universal rectangle carried the full label-band padding on its LEFT and RIGHT too, the canvas grew,
the clearance in units grew with it (T-QG-10), and the lens lost more than the bigger circle gave.
Side padding only has to keep the frame off the outlines — the label bands are top and bottom.
(2) A one-token count seated at its region's roomiest point is ~30 units from every outline, so
visual-check's `target` rule (a label within 1.5 × fontSize of what it names) failed every Venn
count: the rule assumes a label names a STROKE, and a region item names an AREA.
**The check:** the venn frame's side pad is `clr + 6`; region tokens bind `label "g" names
region_<key>[_j]`, and `visual-metrics.mjs` skips the `target` rule for exactly those `region_…`
targets — edge and stroke still measure them, no `allow:` line is involved, so nothing else is
waived. A trefoil's overlap regions hold about one short token each at a readable size; the
template says so when it refuses.

*Source: this plugin — W14, 2026-10-05.*
