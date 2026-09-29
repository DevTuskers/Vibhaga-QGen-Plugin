---
name: author-question-text
description: Author one generated question's student-facing stem — there is no source paper, so every stem is written from scratch inside the lesson's scope — write the `$…$` / `$$…$$` / backtick markers correctly, and gate the authored strings on `hasSwallowedMarkup` plus the markdown gate before they go anywhere near a staged doc. Emits `question_text` (with `question_text_sinhala` left null). Use when authoring, writing, correcting or reviewing the question text/stem of a generated maths question, or when a swallowed `$`, a stray backtick or a markdown table in a stem needs adjudicating before publish.
argument-hint: "[question number or staged item]"
---

# Author a question's text (S4)

> Moved from Vibhaga-Docs `.devin/skills/author-question-text` @08c09a9; paper-only sections removed
> (see docs/MIGRATION.md). What went: mapped-region transcription, the furniture-quarantine verdicts,
> page-regime verification channels, the parallel-shape chunk contract. What stays: §1a's authored-stem
> ruling, the whole of §3's markup law, and the §0 items that bind a generator as much as a transcriber.

> **The one failure this skill owns has a generation twin.** The paper side feared a wrong digit that
> reads fluently; the generator's version is a wrong digit that was *invented* — a number in the stem
> that the approach then faithfully computes on, self-consistent and wrong for the lesson. Every
> numeral you write is a choice: it must serve the skill being tested, survive the figure's measured
> geometry (the stem-ratio check), and not silently be the textbook's own exercise numbers.

**Emits:** `question_text` for `content.yaml` (`tools/build-staged.py` compiles it into the staged doc;
`question_text_sinhala` stays null — §0.6).

---

## 0. Non-negotiables (read first)

1. **A generated stem is self-contained.** Nothing it needs lives anywhere else: no "as shown above",
   no shared formula the student was told earlier, no figure the question does not carry. If a formula
   is load-bearing for this question, it is *in* this stem (a formula hoisted into the text is how the
   paper side solved the same problem).
2. **⚠️ `hasSwallowedMarkup` is a hard pre-publish gate, enforced SKILL-SIDE.** If it returns `true` for
   any string you authored, **you refuse to stage that question** and fix the text first. See §3.3 —
   including why this is *not* an Admin change and why making it one is a separate, ADR-worthy
   decision.
3. **Every numeral is authored deliberately and stays inside the lesson.** There is no regime channel to
   confirm against — the check is different: (a) the stem's numbers are the same ones the claim set's
   `stem:` header and the approach's arithmetic use; (b) they are not just the textbook exercise's
   numbers relabelled (dedup rule); (c) they are within what the lesson teaches.
4. **Never put Sinhala inside KaTeX `\text{}`** (`Vibhaga-Admin/AGENTS.md` §4, item 8 — D7;
   [content-text-syntax](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/technical/content-text-syntax.md) **rule 7**).
   Prose and maths are separate nodes. A Sinhala-headed `\begin{array}` table is illegal for the same
   reason.
5. **Trust > coverage.** A question you cannot author confidently inside the lesson is **not guessed** —
   drop it or put it to the owner. Wrong content that reads fluently is the worst thing this pipeline
   can produce (`0008` PD-3).
6. **The stem has no Sinhala box in the Admin UI.** `0003` PD-C removed the question-level Sinhala
   field; only *sub-questions* have `text_sinhala` (`Vibhaga-Admin/src/features/onboarding/QuestionCard.tsx:598-616`).
   The **column and the staged-doc field still exist** and a whole-doc `PUT` can write them
   (`Vibhaga-API/api/src/onboarding/validation.ts:72`, `publish.ts:352`) — but no human can then see or
   repair it through the workspace. `build-staged.py` writes it null; keep it null.
7. **You do not decide the batch's scope.** `grade` XOR `exam`, subject and medium are session-level;
   a per-question `exam` is accepted by the save schema and then **ignored**
   (`validation.ts:73-78` → `publish.ts:356` takes the batch's). `build-staged.py` emits no `exam` key.
   Don't try to smuggle scope into a stem.

---

## 1a. Where an item has NO printed stem, AUTHOR one — and here, nothing is ever printed

The paper-side owner ruling (2026-08-26) answered "some printed items open straight at `(a)` with no stem
of their own": the author writes a short, neutral instruction in the paper's language. For generation the
rule generalises to **everything**: there is no printed item at all, so the stem is always authored.

⚠️ **Authored is not the same as lifted, and the difference is the whole point.** The paper side's failure
was giving stemless items the paper's own Part-level rubric — *real text in a role it does not have* —
which is worse than authoring because it silently claims a provenance it lacks. The generation twin:
lifting the **textbook's exercise instruction** or the lesson file's worked-example wording as your stem.
An authored stem is honestly authored; a copied instruction is a dedup violation wearing a uniform.

⇒ **Author it, and note it** in the run ledger as *"stem authored"* — trivially true of every generated
question, which is exactly why the dedup comparison in `generate` §2 step 2 has to happen *before*
authoring, not after.

---

## 3. The format — **markdown**, plus `$…$`, `$$…$$`, `` `…` ``

⚠️ **Since [`decisions/0010`](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/decisions/0010-markdown-as-the-content-format.md) the field you
are authoring is MARKDOWN** (CommonMark + GFM tables, curated element policy) around the three markers
below. It renders to students in `Vibhaga-Web` and previews for the author in `Vibhaga-Admin` through
**one shared component**. That buys you real tables and lists — and it means **markdown deletes the
marker characters it acts on**, so a line that merely *looks* like markup becomes markup and the
character disappears. §3.4 is that list; do not skip it.

The canonical spec is
[content-text-syntax](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/technical/content-text-syntax.md) — it is on
`main` now, read it rather than re-deriving. The three rules that bite an author:

1. **First opener wins**, scanning left to right; the only tie (`$$` vs `$` at the same index) goes to
   `$$` (`grep -n "firstOpener\|startsWith(\"\$\$\")" Vibhaga-Admin/src/lib/mathSegments.ts`).
2. **No nesting.** In `` `a $x$ b` `` the whole thing is literal English; in ``$a `x` b$`` the backticks
   are handed to KaTeX, which draws `` ` `` as a `'` quote.
3. **An unterminated opener degrades to literal text** and never throws — which is precisely the damage
   §3.3 gates on.

### 3.1 When to use which

| You are writing | Use | Example |
|---|---|---|
| A symbol, variable or number inside prose | `$…$` | `Find the value of $x$.` |
| A formula that deserves its own line | `$$…$$` ⚠️ **with the fences on their OWN lines, at column 0, after a blank line** | rare in a stem; common in an `approach`. ⚠️ **`$$\frac{3}{4}$$` on ONE line is now INLINE**, and `$$\frac{3}{4}` ⏎ `$$` (content on the opener line) **DELETES the formula** — everything after `$$` on that line is eaten as the fence's info-string. Inside a list item it detonates the item and the **raw LaTeX reaches the student** |
| English words inside Sinhala prose that Singlish must not transliterate | `` `…` `` | **0 live rows used it when last measured.** You are likely the first — test the render |
| A unit | inside the maths: `$10\text{ cm}$` | |
| Sinhala | **plain text, outside every marker** | |

⚠️ **`\text{}` is for Latin only.** `$30\text{ kg } 350\text{ g}$` is fine; a Sinhala word inside
`\text{}` is forbidden and will render as tofu or garbage.

### 3.2 The exact predicate

```ts
// Vibhaga-Admin/src/lib/mathSegments.ts — re-derived 2026-08-22.
// grep -n "export function hasSwallowedMarkup" Vibhaga-Admin/src/lib/mathSegments.ts
export function hasSwallowedMarkup(input: string): boolean {
  return splitMathSegments(input).some((seg) => {
    if (seg.unterminated !== true) return false;
    // A backtick opener eats nothing — see the block comment above it in the source.
    if (!seg.value.startsWith("$")) return false;          // ⚠️ ADDED — no backtick shape fires now
    const afterOpener = seg.value.slice(seg.value.startsWith("$$") ? 2 : 1);
    return afterOpener.includes("$");                      // ⚠️ the `|| includes("`")` clause is GONE
  });
}
```

It is **narrow on purpose**: an unclosed opener only matters when it is **eating a later delimiter**.
Verified vectors (run against the compiled function, §3.3 — not copied from memory):

| String | `hasSwallowedMarkup` | Why |
|---|---|---|
| `Find $x$ if $x+2=5$.` | `false` | balanced |
| ``The `pH of the solution is $7$`` | **`false`** | the predicate returns early on any opener that is not `$` — `` `a and `b` here `` (a real loss) and `` `pH` and `x `` (an author mid-word) are **character-for-character the same shape**, so no source predicate can separate them. Backticks are owned by the construct-level checks — `codeSpanBlankLine`, `codeSpanEmpty`, `codeFenceLiteral` — which the markdown gate runs |
| `Rs. $500 profit` | `false` | a lone `$` is legitimate prose; nothing is hidden |
| `Evaluate $$\frac{3}{4}` | `false` | half-typed display run, nothing after it |
| ``Evaluate $$\frac{3}{4} and `pH` too`` | **`false`** | same change: nothing after the unterminated `$$` is a `$`. ✅ **The markdown gate blocks it anyway**, as `M2-displayMathUnpaired` |
| `$$x$` | **`true`** | accepted rough edge — a true positive |
| `$$ x $ y $` | **`true`** | ⚠️ **even number of `$` and still swallowed** — so parity is not a *substitute* for `hasSwallowedMarkup` |
| `Take $\pi as 22/7. Find $x$.` | **`false`** | ⚠️ **odd `$`, and it passes** — the instruction line then renders as maths. Parity is a **separate, mandatory** gate (the gate's `G4` check, TRAPS **T14** in Vibhaga-Docs); run **both** |
| ``` `a $x b` ``` | `false` | the `$` is literal inside the raw span (no nesting) |

### 3.3 The gate, and the in-code decision it reverses

**Run it, don't eyeball it.** Compile the real predicate with the Admin checkout's own `esbuild` into a
throwaway directory and feed it your authored strings (run from the umbrella root — `Vibhaga-Admin`
resolves as `--admin`/env/sibling, same as the tools):

```bash
mkdir -p /tmp/vibhaga-gate
git -C Vibhaga-Admin log --oneline -1        # confirm the checkout is at or after markdown Phase 1
Vibhaga-Admin/node_modules/.bin/esbuild Vibhaga-Admin/src/lib/mathSegments.ts \
  --bundle --format=esm --platform=node --outfile=/tmp/vibhaga-gate/mathSegments.mjs
node -e 'import("/tmp/vibhaga-gate/mathSegments.mjs").then(m=>{
  const fields = JSON.parse(process.argv[1]);
  const bad = fields.filter(f => m.hasSwallowedMarkup(f));
  console.log(JSON.stringify({checked: fields.length, swallowed: bad.length, bad}));
})' "$(cat /tmp/vibhaga-gate/authored.json)"
```

A hand-written regex is still **not** a substitute: it gets `$$ x $ y $` and `` `a $x b` `` wrong in
opposite directions. ⚠️ **And `hasSwallowedMarkup` is no longer the whole markup gate** — it never sees
a bullet list eating a minus sign. Run `node tools/markdown-gate.mjs`, which runs this predicate's
successor as one of three layers (`run-gate.sh` runs it over a staged doc).

**If it returns `true`: do not stage.** Fix the string, re-run, then continue. Record the
refusal in the ledger (`refused: swallowed markup`, plus the offending substring).

⚠️ **This reverses an explicit, reasoned in-code decision — know exactly what you are and are not
doing.** The rationale lives in `mathSegments.ts` (`grep -n "Never a publish blocker" Vibhaga-Admin/src -r`):

> *"`hasSwallowedMarkup`, not 'any unterminated opener': a lone `$` (`Rs. $500`) and a half-typed
> `` `pH `` are both harmless and both extremely common, and warning on them would train the author to
> ignore amber. **Never a publish blocker.**"*

That decision is about a **human typing in a textarea**, where mid-keystroke states are the normal
happy path and a modal block would be hostile. An agent is not mid-keystroke: it submits a finished
string, so the same predicate that must stay advisory for a human is free to be terminal for a machine.

| | Skill-side enforcement (**this skill**) | Admin-side block (**not this skill**) |
|---|---|---|
| What changes | the agent declines to stage/publish | `publishDisabledReason` gains a third clause |
| Code change | **none** | `Vibhaga-Admin` PR |
| Who it affects | agent runs only | **every human author, on every card** |
| Reverses `QuestionCard.tsx`? | no — the warning stays advisory in the UI | **yes** |
| Process | just do it | an **ADR** (`Vibhaga-Docs/decisions/NNNN-*`), because it overrides a documented decision |

So: **enforce it, and do not touch `QuestionCard.tsx`.** If a future run decides the Admin should
block too, that is a separate proposal with its own decision record — not a line snuck into a plugin PR.

⚠️ **The warning you are standing in for is invisible where it matters.** `MarkupWarning`
(`QuestionCard.tsx` — `grep -n "function MarkupWarning"`) renders only inside the **expanded** card, so
on a collapsed list of 30 questions a swallowed `$` is not on screen at all. Nobody is going to catch
this for you.

### 3.4 ⚠️ Markdown — the eight rules that decide whether a stem survives

**Run `node tools/markdown-gate.mjs` over every string you author.** It is
generative, so it catches shapes this list does not name. **R0** is the positive template; **R1–R6**
are the shapes you will actually hit writing a Sri Lankan maths stem. Every one is measured.
⚠️ **R6 deletes the most, and it is late in the list only because it is not about a single
character** — read it. **R7** closes with the shape that is not about a character either.

**R0 · The shape of a table, because the rest of this section is prohibitions.** Copy this:

```
| Shape | Order |
|---|---|
| square | 4 |
| triangle | 3 |
```

Four facts an author does not guess, each measured:
- **The delimiter row `|---|---|` is what makes it a table.** Omit it and you have written prose.
- ⚠️ **The FIRST row is ALWAYS a header.** There is no headerless GFM table, so a table with
  no header gets its first *data* row styled as one — decide what the header should be.
- **Write the edge pipes.** `A | B` over `---|---` is also a table, and it is **textually identical to
  prose that became one by accident**; the gate can only advise on it.
- **Caps:** the gate blocks above **8 columns** or **30 rows**, and advises above **2** columns for
  Sinhala (4 for English) — see R2.

**R1 · A bar inside maths inside a table cell must be `\vert` (or `\mid`).** GFM splits a row on the
pipe character *before* inline parsing, so a bar typed as the pipe character becomes a cell boundary.
⚠️ **This rule is written out in words rather than shown, because a table cannot contain an unescaped
example of its own delimiter** — every "never" below names the characters instead.

| you want | write | ⚠️ never |
|---|---|---|
| "5 divides 8", inside a cell | `$5 \vert 8$` · `$5 \mid 8$` — both render **∣** (U+2223) | the **pipe character** inside `$…$`: measured, it splits the cell, the header/delimiter counts stop matching and **the table does not form at all** |
| a **literal pipe** in a cell, outside maths | **backslash + pipe** — ✅ the correct escape *here*, and only here | — |
| ⚠️ **backslash + pipe INSIDE `$…$`** | — | ⚠️ **the wrong fix, and it is silent.** In TeX that sequence is `\parallel`: measured, it renders **∥** (U+2225, *parallel*) where **∣** (*divides*) was meant. A wrong symbol, no error, no warning |
| a bare pipe in prose **below a table** | fine — **but put a blank line between them** | without the blank line the sentence is absorbed as one more table row and the pipe becomes a cell boundary |

**R2 · Two columns for Sinhala, four for English.** A sub-question's content box is **265 px at 375 px**
wide and **210 px at 320 px**, and a 2-column Sinhala table already measures **305 px** max-content —
⚠️ *those three pixel figures are **inherited** from the paper-side analysis §10.3, which measured them in real
Chromium with the real Sinhala font; they are cited, not re-claimed.* The
hard cap is 8 columns and the gate blocks there; above 2 (Sinhala) / 4 (English) it advises, and you should
treat the advice as the rule. If the table you want is wider, **split it or use a VDD** — do not ship a
5-column table because nothing refused it.

**R3 · An empty cell, never a row of dots.** A fill-in-the-blank is `|  |`, not `| ........ |`: dots are
content a student can mistake for an answer, and an empty cell keeps its size, so the affordance is
already there. ⇒ **never leave a HEADER cell blank** (the gate blocks on it); a blank *body* cell under a
filled header is the correct shape.

⚠️ **The reason is NOT that a blank header collapses the column — that was measured and is false under
what actually ships.** With `ContentMarkdown`'s own `min-w-10`/`h-8` declarations, a blank header cell
measures the same as its filled sibling and nothing collapses. The rule stands on the reason that
survives: **an unnamed column is unreadable and unannounceable** — a screen-reader user gets a `<th>`
with no name.

**R4 · `1)` and `1.` at line start are list markers, and Sri Lankan items label parts that way.**

| you write | what markdown does | write instead |
|---|---|---|
| `1) Find x` ⏎ `2) Find y` | ⚠️ an ordered list — **both part labels are DELETED** | `1\) Find x` — or, better, make them real sub-questions ([structure-question-parts](../structure-question-parts/SKILL.md)) |
| `1. Find x` ⏎ `3. Find y` | ⚠️ only the first number survives; **part 3 is shown to the student as 2** | `1\.` / `3\.` |
| `1988. In that year…` | ⚠️ a **year** at line start is a list marker. The `<ol start="1988">` marker still *prints* `1988.`, so the screen looks close — but the number is **gone from the text node**, so `plainText()` drops it from the share title and the paragraph is now an indented list item | `1988\.` |

**R5 · `>` at line start is deleted — and it is the exception to the "no space is safe" rule.**
`-5` and `#5` are safe with no space after the marker; **`>5 is bigger` still loses the `>`**.
⭐ Write `$>5$`, which also gives a properly typeset `>`; `\>` also works.

**R6 · ⚠️ FOUR SPACES AT THE START OF A LINE IS A CODE BLOCK, AND IT KILLS EVERY `$…$` ON THAT LINE.**
This deletes more than any other rule here. Measured:

| you write | what the student gets |
|---|---|
| `Answer:` ⏎ ⏎ `····$x = 5$ <word>` (blank line, then 4 spaces) | ⚠️ a code block — **the maths never renders and the `$` markers reach the student** |
| an **indented first line**, nothing above it | ⚠️ the same, **and there is no blank line to blame** — one pasted, indented line is enough |
| `Answer:` ⏎ `····$x = 5$ <word>` (**no** blank line) | ✅ **the maths still renders** — the indent only bites where the line is not continuing a paragraph directly above it |

⇒ **remove the indent.** ⚠️ And do not "fix" the third row: the gate passes it deliberately, so an agent that
rewrites it is editing content for no reason.

**R7 · Write the edge pipes — the one rule the gate cannot enforce for you.** R0 says to; this is *why*.
A table written without them is a real table, and it is **textually identical to prose that became one
by accident**, so `L3-table-no-edge-pipes` can only ever be `advice`: a live migrated row
is exactly this shape, and blocking it would refuse published content. ⇒ **the discipline is the only
thing that separates the deliberate case from the accident**, and nothing downstream can recover the
difference once it is lost.

---

## 5. Writing the stem

- ⭐ **A data list in the stem wraps only where YOU break it.** Inline `$…$` never wraps (`.katex` is
  `whitespace-nowrap`), so a row of ten values in one `$…$` is cut off at the right edge of a 375 px
  phone — measured: such a row reached x = 391. Put **at most six numbers** on a
  `$…$` line (single newline between lines), or use a table. `tools/check-inline-math-width.py`
  measures every stem too.
- **Fix your own language before you write it.** The paper side's rule was "correct the paper's
  grammar, declare it"; the generator's version is simpler: there is no source, so a spelling or
  grammar mistake in the stem is *your* mistake — fix it before staging, and let the critic catch what
  you missed. **Never "correct" a number, symbol, operator, unit, name, label or variable** — a "typo"
  there may be the maths; if the maths is wrong the *question* is wrong, not the spelling.
- **Strip the question number from the prose.** `question_number` is its own integer field.
- **No mark allocation.** There is nowhere to put it — do not write "(5 marks)" into a stem.
- **No inter-part references that break standalone reading.** *"Using the value you found in (a)"* is
  legal between parts of one question; *"using the graph above"* pointing at an earlier *question's*
  figure is unanswerable — every question stands alone.
- **Whitespace is preserved verbatim in the DATABASE** end to end (`str()` in `publish.ts` does not trim
  the interior). ⚠️ **But `whitespace-pre-wrap` is GONE** — markdown Phase 1 dropped it from the render
  wrapper, and Web now *asserts its absence*. What renders a newline is `remark-breaks`: **a single
  newline is a line break, a blank line is a paragraph break**, and a run of spaces collapses. So
  "newlines you type are newlines the student sees" still holds; **"spaces you type are spaces the
  student sees" does not** — and four spaces at the start of a line is a **code block** that stops every
  `$…$` on it from rendering at all: **§3.4 R6**, which also names the one case where it does not bite.
- **Limits:** 50 000 chars per text field; ≤400 questions per doc (`validation.ts`). Not a real
  constraint for a stem — if you are near it, something is wrong.

---

## 6. Traps — stories with the catch

Cross-cutting traps live in [`docs/TRAPS.md`](../../docs/TRAPS.md); these are
S4's own.

### T-S4-1 — The `$`-parity check that passes a swallowed run
**Looked true:** counting `$` characters is a cheap stand-in for the real predicate — an even count
means every run is closed.
**Actually:** `$$ x $ y $` has four `$` and **is** swallowed (`$$` opens, never closes, and eats the
two later `$`). And `` `pH `` has zero `$` and swallows a following `$x$`. Parity is wrong in both
directions.
**The check:** run the compiled `hasSwallowedMarkup` (§3.3). It is eight lines; there is no excuse for
an approximation.

### T-S4-2 — The warning that is on screen and invisible
**Looked true:** the author warning fires, so a swallowed marker cannot reach production.
**Actually:** `MarkupWarning` renders **inside the expanded card only** (`QuestionCard.tsx`), and
`publishDisabledReason` checks only blank text and paper-bar completeness.
On a collapsed 30-question list the amber is nowhere, and Publish is enabled.
**The check:** the gate is yours, not the UI's (§3.3). Assert it over every authored field before the
publish loop starts, not per card as you go.

### T-S4-5a — The copy that explains a backtick, written in backticks
**Looked true:** the wrapper is documented, so an author knows how to use it. **Actually:** a splitter
cannot express its own delimiter — copy explaining `` `…` `` rendered with whitespace-only `<code>`
elements and stray backticks leaking into the prose, so the one paragraph teaching the feature was the
one that displayed wrong. **The check:** render every author-facing string through the real component
and assert no backtick survives — in a browser, not in a unit test.

### T-S4-5 — The backtick nobody has ever used
**Looked true:** the `` `…` `` wrapper is well-tested, so English-inside-Sinhala is a solved case.
**Actually:** when last measured, **0 of 60** non-empty live content fields contained a backtick. Every
backtick you author is the feature's first production use, and VDD diagram labels are explicitly **not**
covered by any strip — a backtick in a figure label reaches the student verbatim
([content-text-syntax](https://github.com/DevTuskers/Vibhaga-Docs/blob/main/technical/content-text-syntax.md) §"Not covered
by any strip"; the VDD skills own that surface).
**The check:** after authoring a backtick field, read it back from the **rendered student page**, not
from the editor preview — and remember `plainText()` strips markers differently for `<title>`/OG, so
check the share preview too if the question is likely to be shared.

---

## 6a. What you emit — the `content.yaml` spec, not staged JSON

`content.yaml` is the authoring surface: `stem` / part `text` fields in the §3 format, lesson keys, bare
part labels — and **nothing in the staged shape**: no uuid, no `sort_order`, no `question_number` as a
string, no `ingestion_metadata`. `tools/build-staged.py` derives those; its refusals name the rule you
broke. Every rule in §3–§5 applies unchanged to the text you write.

## 7. Verify (definition of done for S4, per question)

- [ ] A part whose **answer is a drawing** (a shaded region, a construction) was not authored — there is
      no channel for a student-drawn response; the `approach`/`final` fields cannot carry it.
- [ ] **`G4` even-`$`-parity** run in addition to `hasSwallowedMarkup` (the latter is `false` on odd `$`)
- [ ] `hasSwallowedMarkup` is `false` for `question_text`, measured with the
      compiled predicate (§3.3) or `tools/markdown-gate.mjs` over the staged doc.
- [ ] No Sinhala inside `\text{}` — this returns nothing (ripgrep `\p{Sinhala}` or Python
      `re.search(r'\\\\text\{[^}]*[\u0D80-\u0DFF]', s)`):
      `python3 -c "import re,sys,json; [print(s) for s in json.load(open('authored.json')) if re.search(r'\\\\text\{[^}]*[\u0D80-\u0DFF]', s)]"`
- [ ] The stem carries no question number and no mark allocation.
- [ ] After publish: `SELECT question_text FROM questions WHERE question_id = '<id>';` returns your
      string **byte-for-byte** (⚠️ a direct `SELECT` — the API read goes through Hyperdrive, whose query
      cache is not write-invalidated for ~75 s; `docs/TRAPS.md` T5).

---

## 8. Keep this skill alive

If a line number, a predicate, a count or a rendered behaviour above no longer matches reality —
**stop, re-verify against the live system, then update this file in the same PR**. Cross-cutting
traps go to [`docs/TRAPS.md`](../../docs/TRAPS.md); S4-specific ones go in §6
above, written as a story with the catch.
