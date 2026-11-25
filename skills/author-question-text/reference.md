# author-question-text — examples and troubleshooting

[Operational rules](SKILL.md). Open this reference for examples or to diagnose a failure.

## Gate rationale

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

## Markdown examples

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
