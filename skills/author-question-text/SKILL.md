---
name: author-question-text
description: >-
  Author a generated question's student-facing stem and part text from a lesson scope card.
  Use for bilingual English and Sinhala prose, maths markup and content.yaml.
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

**Emits:** `question_text` AND `question_text_sinhala` for `content.yaml` — `stem` + `stem_si`
(`tools/build-staged.py` compiles them into the staged doc and refuses a missing, a Sinhala-in-English,
or a copied side — §0.6).

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
6. **The stem is bilingual (0024).** Author `stem` in plain school English AND `stem_si` in natural
   everyday Sinhala — same numbers, same task. `build-staged.py` emits `question_text` +
   `question_text_sinhala` and refuses a missing `_si`, Sinhala in the English side, or an
   English-prose copy in the `_si` side (identical maths-only text like `$x = 4$` is allowed — the same
   string serves both media). The reviewer's `English | සිංහල` preview toggle in Admin reads both
   sides, so a copied or machine-stiff translation is visible in review.
   - **Bilingual diagram-stem coordination (language-neutral diagrams):** VDD diagrams (`diagram_dsl`)
     are shared bilingually between English and Sinhala student views. When a question features real-world
     scenarios or geometric figures, keep the diagram language-neutral with single English letters or
     mathematical tokens ($A, B, C, P, Q, H, F, T, S$), and introduce the entity mapping in both English
     and Sinhala stems (e.g. *"In the diagram, $H$ represents her home and $F$ represents her finish point..."*
     and *"රූපයේ, $H$ මඟින් ඇයගේ නිවසද $F$ මඟින් ඇය ගමන් අවසන් කළ ස්ථානයද දැක්වේ..."*). This avoids
     embedding English words/phrases inside the diagram which would appear unlocalized on the Sinhala side.
7. **You do not decide the batch's scope.** `grade` XOR `exam`, subject and medium are session-level;
   a per-question `exam` is accepted by the save schema and then **ignored**
   (`validation.ts:73-78` → `publish.ts:356` takes the batch's). `build-staged.py` emits no `exam` key.
   Don't try to smuggle scope into a stem.
8. **Respect student cognitive load and spatial imagination limits (CDS Index).** Before staging,
   evaluate the stem's Cognitive Decoding & Spatial Imagery score ([`assess-spatial-imagination`](../assess-spatial-imagination/SKILL.md)). If
   the stem requires visualizing multi-point coordinate grids, complex 2D shapes, folding, or
   spatial transformations exceeding the grade benchmark (e.g. CDS > 4 for Grades 7–8), **you MUST NOT
   rely on pure text**. You must either provide a visual VDD diagram ([`figure-templates`](../figure-templates/SKILL.md),
   [`draw-and-verify-question-vdd`](../draw-and-verify-question-vdd/SKILL.md)) or chunk the description into clear, simple single-relation steps
   so that students are tested on the underlying mathematics rather than spatial working-memory overload.
9. **IT & technical terms in Sinhala (English terms in brackets rule):**
   When authoring questions related to Information Technology (IT/ICT), computing hardware/peripherals,
   data storage/systems, or calculator/device interfaces in Sinhala:
   - **Include the English technical term in brackets:** Whenever technical terms are translated into Sinhala
     (even when using correct/standard curriculum terminology), always include the English technical term
     within parentheses immediately following the Sinhala term
     (e.g. `අධිවේගී ෆ්ලෑෂ් ආචයන (High-Speed Flash Storage)`, `වෙන්කිරීම් කුට්ටි (allocation blocks)`,
     `දර්ශක වාර්තාවක් (index record)`, `ගොනු පද්ධතිය (file system)`, `දෘඪ තැටිය (hard disk drive)`).
     *Rationale:* Most Sinhala-medium students are unfamiliar with coined or formal Sinhala technical terms,
     whereas they are already familiar with the English technical terms from practical computer use, syllabi,
     and everyday life. Providing the English term in brackets eliminates ambiguity and cognitive friction.
   - **Everyday IT peripherals and hardware terms:** Use standard English technical terms (either in English
     or natural transliteration, e.g. "mouse" / "මවුසය", "keyboard", "monitor", "RAM", "CPU", "software",
     "storage", "bytes") even within the Sinhala version. Do NOT use awkward, artificial, or antiquated
     direct Sinhala translations alone (e.g. for mouse, never use "මූසිකය"; for software, hardware, cursor,
     RAM, CPU, file, folder, button, key, etc., use the English terms that students actually learn and use
     in IT practice and standard exam convention).
10. **Sinhala mathematical terminology and translation calque traps:**
   When translating or authoring Sinhala question stems and parts, you must strictly follow Sri Lankan school curriculum terminology (`terms/si-maths-terms.yaml`). Non-frontier or generic machine translation models frequently produce catastrophic calques and mistranslations:
   - **Intersection / crossing:** "crossing point" in compass construction / loci is strictly `ඡේදන ලක්ෂ්‍යය`, NEVER `කුරුසු ලක්ෂ්‍යය` ("crucifix point"). "Arcs cross/intersect" is `චාප ඡේදනය වේ`, NEVER `කුරුසු වේ`.
   - **Angles & circles:** "central angle" / "centre angle" is `කේන්ද්‍රික කෝණය` (Grades 6–8) or `කේන්ද්‍ර කෝණය` (Grades 9–11). "Sector" is `කේන්ද්‍රික ඛණ්ඩය` (NEVER `අංශ`). "Spoke" of a wheel is `ගරාදිය` (NEVER `කොටස`).
   - **Congruence vs coincidence:** geometric figures that are "congruent" are `අංගසම` (NEVER `සම්පාත`, which means coincident/overlapping).
   - **Independence:** "independent" steps or events are `එකිනෙකින් ස්වායත්ත වේ` / `ස්වාධීන වේ` (NEVER literal calques like `එකිනෙකාට බඳිනු නැත`).
   - **Real-world entities:** Ferris wheel is `රස්සියානු රෝදය (Ferris wheel)` (NEVER `රුස්සාවි රෝදය`). Vesak pandal is `වෙසක් තොරණක්` (NEVER `වෙසක් කූඩුවක්` which is a lantern).
   - **Statistics:** "median" is the noun `මධ්‍යස්ථය` (NEVER the adjective `මධ්‍යස්ථ`).
   - **Bearings & units:** Quadrant bearings in Sinhala text must be formatted as `උ 30° නැ` or `ද 45° බ` using plain degree symbols `°` in text (do NOT bury the degree symbol inside `$…$` LaTeX math mode in Sinhala text, or markup strippers will strip the angle).

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
| A number and unit | English symbol after the number in both languages: `$4$ cm` (or `$10\text{ cm}$` inside maths); never a Sinhala unit word or abbreviation immediately before or after it | `mm`, `cm`, `m`, `km`, `mg`, `g`, `kg`, `ml`, `l` |
| Sinhala | **plain text, outside every marker** | |

⚠️ **`\text{}` is for Latin only.** `$30\text{ kg } 350\text{ g}$` is fine; a Sinhala word inside
`\text{}` is forbidden and will render as tofu or garbage.

Units stay in English symbols beside numbers in Sinhala text as well as English text. The blocking
`unit-notation.py` gate refuses Sinhala unit words/abbreviations immediately before or after a number
and Singlish transliterations of unit symbols.

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

Enforce the predicate before staging. Do not change the Admin warning into a publish block;
that would be a separate Admin proposal and ADR. See the [gate rationale](reference.md#gate-rationale).

### 3.4 ⚠️ Markdown — the eight rules that decide whether a stem survives

**Run `node tools/markdown-gate.mjs` over every string.** Apply these rules; see the
[worked Markdown examples](reference.md#markdown-examples) for table recipes and troubleshooting.

- **R0/R7:** Put edge pipes on both sides of every row, use a delimiter row, and use the first
  row as the header. Separate tables from prose with blank lines. Hard cap: 8 columns or 30 rows.
- **R1:** Use `\vert` or `\mid` for a bar in maths inside a table, not a literal or escaped pipe
  (the escaped pipe produces `\parallel` in TeX). Escape a literal pipe outside maths in a cell.
- **R2:** At most two Sinhala columns or four English columns; split wider tables or use VDD.
- **R3:** Use empty body cells for blanks, not dots. Never leave a header cell empty.
- **R4:** Use real sub-questions or escape leading `1)` and `1.` (including year labels).
- **R5:** Write `$>5$` or `\>` instead of a bare line-initial `>`.
- **R6:** Remove four-space indents at the start of a paragraph or field; they turn maths into code.
  An indented continuation without a blank line is not a code block.

---

## 5. Writing the stem

- ⭐ **Lay the stem and every part out for a phone.** A single newline is a line break; a blank
  line is a paragraph break (`remark-breaks`). One idea or step per paragraph:

  | Where | Layout |
  |---|---|
  | Stem | Givens/setup paragraph, blank line, then the task in its own paragraph |
  | Part text | One instruction or question per paragraph |
  | Follow-up | A separate “why / explain” question gets its own paragraph |
  | Points/data | One per line or as a list, not packed into a sentence |
  | STEM/PART cap | WARN above 180 characters or at 2 sentences; FAIL above 240 characters or at 3 or more sentences in one paragraph |

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

## Writing natural Sinhala

The Sinhala side is not a translation of the English. Write it as a Sinhala maths teacher would write it in the textbook.
1. **Write from the lesson, not from the English.** Before writing, grep the lesson's exercises for their sentence endings and verbs (`grep -oE '[^ ]+ න්න|[^ ]+න්න[ .?]' <lesson>.md | sort | uniq -c | sort -rn | head`). Use the same instruction verbs (සොයන්න, ගණනය කරන්න, ලියන්න, හේතු දක්වන්න, අඳින්න …) and the lesson's own words for objects (the lesson says ඉරටු කැබලි, so do not write බට කෑලි).
   **Terminology is looked up, never guessed.** Before writing a `*_si` field, look each maths term up in [`terms/si-maths-terms.yaml`](../../terms/si-maths-terms.yaml) and use its rendering for the question's grade (e.g. compass → `කවකටුව`, never `කාරණදාර`; bearing → the `උ 30° නැ` format, never a single word). The `phrases:` section carries taught phrasing patterns (bearing format, the G7/G8 event-class spellings — no certain/likely/unlikely word scale) and `banned:` lists known MT artifacts. If a term is absent from the dictionary, find it in the corpus lesson first and add a cited entry in the same change; if the corpus has no rendering either, it belongs on the dictionary's `needs_review` list for a human ruling — do not invent it. `tools/check-si-terms.py` blocks the build on a missed lookup.
   * *Common MT solid geometry traps:* cone is `කේතුව` (never `කෝනය` / `කෝණය` — "කෝණය" is an angle, while "කෝනය" is a machine-transliteration artifact); slant height is `ඇල උස` (never `ලම්බ උස` — perpendicular height); curved surface area is `වක්‍ර පෘෂ්ඨ වර්ගඵලය` (not `වක්‍ර වර්ගඵලය`); total surface area is `මුළු පෘෂ්ඨ වර්ගඵලය`; sphere is `ගෝලය`; hemisphere is `අර්ධ ගෝලය`; cylinder is `සිලින්ඩරය`; prism is `ප්‍රිස්මය`.
   * *Bearings:* Grade 10 & 11 use three-figure bearing `දිගංශය` (e.g. `220° ක දිගංශයකින්`, `දිගංශය`), while Grade 8 uses quadrant bearing format (`උ 30° නැ`). NEVER use calque `දිශාංකය`.
   * *Due directions (never `නිව් ...`):* English "due north / due east / due south / due west" must NEVER be phonetically calqued as "නිව් උතුරට", "නිව් නැගෙනහිරින්", etc. Translate as "කෙළින්ම නැගෙනහිරින්" / "නැගෙනහිර දෙසින්" / "කෙළින්ම දකුණින්" / "කෙළින්ම උතුරට".
   * *Circle theorems & chords:* In Sri Lankan school geometry, chord is `ජ්‍යාය` (accusative `ජ්‍යාව`, indefinite `ජ්‍යායක්`), NEVER `ජ්‍යා රේඛාව`. Alternate segment theorem is `ඒකාන්තර වෘත්ත ඛණ්ඩ ප්‍රමේයය` (or `ඒකාන්තර වෘත්ත ඛණ්ඩයේ කෝණ ආශ්‍රිත ප්‍රමේයය`). Subtending an angle is `ආපාතනය කරන` or `යටත් කරන` (e.g. `කේන්ද්‍රයේ ආපාතනය කරන කෝණය`), NEVER mistranslated as earning income `උපයන`. Mid-point theorem is `මධ්‍ය ලක්ෂ්‍ය ප්‍රමේයය`.
   * *Contextual personas, objects & MT hallucinations:*
     - Groundsman is `ක්‍රීඩා පිටි භාරකරු` or `භූමි භාරකරු` (never pejorative calque `භූමිකාරයා`).
     - Observation deck/platform is `නිරීක්ෂණ කුටිය`, `නිරීක්ෂණ මැදිරිය` or `නිරීක්ෂණ තට්ටුව` (never phonetic calque `දෙකොළය` / `දෙකොළයක`).
     - Land plots are `බිම් කොටස්` or `ඉඩම් කොටස` (never colloquial slang `කෑලි` / `කෑලිය` / `භූමි කෑලි`).
     - Examiner/marker (e.g. "A marker states...", "An observer claims...") is a person: `නිරීක්ෂකයෙකු ප්‍රකාශ කරයි` / `පරීක්ෂකයෙකු පවසයි` (never inanimate mark `සලකුණක් පවසයි` / `සලකුණක් ප්‍රකාශ කරයි`).
     - Altitude/height in real-world contexts (e.g. drone, airplane, tower) is `උස` or `ලම්බ උස` (never `උච්චය`, which is strictly the geometric altitude of a triangle or parallelogram relative to a base).
     - Metal/cardboard sheet is `තහඩුව` or `කොළය` (never `ලෙඛනය` which means a written document); dashed lines are `කඩ ඉරි` (never hallucination `තිඹිරි ඉරි`); matchsticks are `ගිනිකූරු` / `ගිනිකූරු කැබලි` (never hallucination `තීන්සිලි`); roof rafters are `පරාල` (never `පරෙක`); paving stones/tiles are `ඇතුරුම් ගල්` / `ගෙබිම් ඇතුරුම්` (never `පාත්තුම්`); cable/wire is `කේබලය` or `කම්බිය` (never `කැබලය`).
   * *Geometry & polygon terminology:* angle bisector is `කෝණ සමච්ඡේදකය` (never `කෝණ සමභාජකය` / `සමභාජක`); bisecting an angle is `කෝණ සමච්ඡේදනය` (never `කෝණ සමභාජනය`); sum of interior angles is `අභ්‍යන්තර කෝණවල ඓක්‍යය`; regular polygon is `සවිධි බහු අස්‍රය` (never typographic missing letter `බහුස්‍රය`); central angle is `කේන්ද්‍රික කෝණය` (never calque `කේන්ද්‍රීය`); right angle is `ඍජු කෝණය` (or `සෘජු කෝණය`); rectangle is `ඍජුකෝණාස්‍රය` (or `සෘජුකෝණාස්‍රය`).
   * *Converse of theorems:* always `විලෝමය` (e.g. `මධ්‍ය ලක්ෂ්‍ය ප්‍රමේයයේ විලෝමය`), never `ප්‍රතිලෝමය` (which means inverse).
   * *Contextual meaning of "base":* for cones and pyramids in the syllabus, the base is `ආධාරකය` (or `ආධාරක වෘත්තය`); for plane figures and prisms, it is `පාදය`; for containers/tanks/vessels, it is `පතුල` (never translate a container's bottom as `ආධාරකය`).
   * *Formal register:* Always use formal written Sinhala (`නැත`, not spoken `නැහැ`). Never open an approach with announcement prefixes (`පිළිතුර:`, `Answer:`).
   * *Never Sinhala inside KaTeX `\text{}`:* prose and maths are separate nodes (D7, S4 §0.4, S8 §0.8); KaTeX cannot render Sinhala script reliably and it breaks accessibility. `precritic-lint.py` blocks any field with Sinhala in `\text{}`.
2. **Short sentences.** One idea per sentence. Split "… වන අතර එය …" into two sentences: `$3 + 4 = 7$ වේ.` / `$7$, $8$ ට වඩා කුඩා ය.`
3. **Active verbs.** Prefer active phrasing (`බෙදා දෙයි` / `බෙදා දුන්නේ ය`, `සාදයි` / `සාදා ඇත`, `ගනී`, `නමයි` / `නමා ඇත`) to mechanical passive constructions (`බෙදා දෙනු ලැබේ`, `සාදනු ලැබේ`, `ගනු ලැබේ`, `නමනු ලැබේ`), unless the syllabus or context naturally requires the passive.
4. **Sinhala word order.** Write the count after the noun with ක්: `පවුල් $3$ක්`, not `$3$ පවුල්`. Put the verb last. Ask questions with ද: `… කීය ද?`, `… කුමක් ද?`.
5. **No calques.** Avoid "හි" chains copied from English "of" (`AC හි දිග හි අගය`). Write `AC පාදයේ දිග`. Do not open with කරුණාකර.
6. **Read it alone.** Cover the English and read the Sinhala aloud. If a student would read a sentence twice, rewrite it.
7. `tools/si-style.py` (run by `run-gates build`) warns on the mechanical signs of these. A warning is a prompt to reread, not proof of a defect.

## 6. Traps — stories with the catch

<a name="t-s4-1--the--parity-check-that-passes-a-swallowed-run"></a>
<a name="t-s4-2--the-warning-that-is-on-screen-and-invisible"></a>
<a name="t-s4-5a--the-copy-that-explains-a-backtick-written-in-backticks"></a>
<a name="t-s4-5--the-backtick-nobody-has-ever-used"></a>

Cross-cutting traps live in [TRAPS](../../docs/TRAPS.md); see the [S4 cases](reference.md#6-traps--stories-with-the-catch) for markup false negatives and renderer checks.

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
- [ ] `tools/check-layout.py` reports 0 FAIL for stems and part texts; read every WARN.
- [ ] No Sinhala inside `\text{}` — this returns nothing (ripgrep `\p{Sinhala}` or Python
      `re.search(r'\\\\text\{[^}]*[\u0D80-\u0DFF]', s)`):
      `python3 -c "import re,sys,json; [print(s) for s in json.load(open('authored.json')) if re.search(r'\\\\text\{[^}]*[\u0D80-\u0DFF]', s)]"`
- [ ] The stem carries no question number and no mark allocation.
- [ ] Both sides authored: `stem` plain school English, `stem_si` natural everyday Sinhala — same
      numbers, same task (build-staged's `bilingual_problem` is the machine check).
- [ ] After publish: `SELECT COALESCE(question_text_english, question_text_sinhala) FROM questions WHERE question_id = '<id>';` returns your
      string **byte-for-byte** (⚠️ a direct `SELECT` — the API read goes through Hyperdrive, whose query
      cache is not write-invalidated for ~75 s; `docs/TRAPS.md` T5).

---

## 8. Keep this skill alive

If a line number, a predicate, a count or a rendered behaviour above no longer matches reality —
**stop, re-verify against the live system, then update this file in the same PR**. Cross-cutting
traps go to [`docs/TRAPS.md`](../../docs/TRAPS.md); S4-specific ones go in §6
above, written as a story with the catch.
