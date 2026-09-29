---
name: structure-question-parts
description: Turn one authored question into the staged doc's structural fields — `question_number` as a real JSON number, an explicit `is_multipart`, and a 2-level `sub_questions` tree with non-empty labels, text and `sort_order`. Owns the silent-coercion failures in the publish mapper (`question_number → 0`, `is_multipart` never computed server-side, empty labels and empty sub-question text accepted). `tools/build-staged.py` emits most of this from your `content.yaml` — this skill is the rules it implements and the checks that catch what it cannot. Use when splitting a question into (a)/(b)/(i)/(ii) parts, when setting or checking question numbers or multipart flags, or when a published question's structure came out wrong.
argument-hint: "[question number or staged item]"
---

# Structure a question's parts (S5)

> Moved from Vibhaga-Docs `.devin/skills/structure-question-parts` @08c09a9; paper-only sections removed
> (see docs/MIGRATION.md). The paper-side wrapper (the S12 contract, the printed-label rulings,
> restart-aware numbering) is gone; the field-corruption content below is unchanged because the publish
> mapper it describes is unchanged.

> **The one failure this skill owns: silent field corruption.** Not a rejection — an *acceptance*. The
> publish mapper takes a JSON string `"1"` and writes `0`; takes a missing `is_multipart` and writes
> `false` next to three sub-questions; takes an empty label and an empty sub-question and publishes
> both. Nothing errors, nothing warns, and the row looks fine in the API response.
>
> ⚠️ **And this write path has almost no production history.** `sub_questions` and `sub_answers` were
> **0 rows** when last measured (2026-08-10). Everything below is read off the code, not off precedent.
> Treat a session's first multipart question as the highest-risk artefact in the batch and verify it by
> direct `SELECT`, question by question.

**Emits:** `question_number`, `is_multipart`, and the `sub_questions` tree with labels — via the
`parts:` tree of `content.yaml`, which `tools/build-staged.py` compiles into the staged doc.

---

## 0. Non-negotiables (read first)

1. **`question_number` must be a JSON `number`.** `num()` accepts only `typeof v === "number"`
   (`Vibhaga-API/api/src/onboarding/publish.ts:139`), so `"1"` → `null` → **`?? 0`**
   (`publish.ts:349`). It is silent, it is not validated (the field is **not declared** in
   `EditableQuestionSchema` — it survives only via `.passthrough()`), and there is **no unique
   constraint** on `(batch, question_number)`, so two questions both land on `0` and nothing
   complains. `build-staged.py` refuses a non-integer `n:`.
2. **Set `is_multipart` explicitly, every time.** The mapper is `q.is_multipart === true`
   (`publish.ts:350`) — it is **never computed from the presence of sub-questions**. The Admin *client*
   computes it on save (`Vibhaga-Admin/src/lib/api/onboarding.ts:402`), so the UI path is safe; a
   whole-doc `PUT` written by an agent bypasses that entirely (§2.2). `build-staged.py` writes it.
3. **Never emit an empty `label` or empty sub-question `text`.** Both publish:
   `label: str(node.label) ?? ""` (`publish.ts:380`, `:401`) and
   `text: typeof node.text === "string" ? node.text : ""` (`:382`, `:403`). Only the **whole-question**
   text is checked non-empty (`:342-344`). §3.3 shows what the student actually gets — and it is worse
   than blank. The builder refuses both.
4. **Depth 2. Not 3.** A grandchild throws
   `Question <id>: sub-questions may nest at most 2 levels deep.` (`publish.ts:395`) → `400`.
   ⚠️ **Blast radius depends on the path**: the Admin UI publishes **one question per request**
   (`Vibhaga-Admin/src/app/(admin)/onboard/[id]/page.tsx:136`), so through the UI a depth-3 error costs
   **exactly one question** — it is a per-question rejection, *not* a batch-wide abort. Batch a publish
   through the API with several ids and the same throw loses the whole call. Do not quote the
   batch-wide radius for UI work.
5. **Never put an answer in both `node.sub_answer` and `node.answers[]` on one part.** They are
   *merged* (`publish.ts:274-276`), so the same `sub_answer_id` is inserted twice → duplicate primary
   key → the whole publish transaction `ROLLBACK`s (`Vibhaga-API/api/src/db.ts:1613`, rollback at
   `:1638`). Pick one shape and stay with it: this plugin emits leaf-part answers as `sub_answer`
   objects inside the sub-question (§5a of author-question-answers), and `build-staged.py` never emits
   both.
6. **Verify the first multipart row directly.** Nothing about this path is proven by precedent.
   Verify the first multipart question with a direct `SELECT` **before** authoring the second (§5).
7. **Structure is not scope.** `grade`/`exam`/`subject`/`medium` are session-level; a per-question
   `exam` is accepted by the save schema and then ignored (`validation.ts:73-78` → `publish.ts:356`).

---

## 1. Stable facts — and how to re-verify them

⚠️ **If any row looks different, STOP and re-derive.** Measured 2026-08-09/10 against `origin/main` and
the live project.

| Fact | Value | Re-verification |
|---|---|---|
| `sub_questions` rows in prod | **0** | `SELECT count(*) FROM sub_questions;` |
| `sub_answers` rows in prod | **0** | `SELECT count(*) FROM sub_answers;` |
| Questions flagged `is_multipart` in prod | **0** of 22 | `SELECT count(*) FROM questions WHERE is_multipart;` |
| Questions with `question_number = 0` in prod | **0** | `SELECT count(*) FROM questions WHERE question_number = 0;` |
| `question_number` coercion | `num(q.question_number) ?? 0`, and `num` rejects non-`number` | `sed -n '139p;349p' Vibhaga-API/api/src/onboarding/publish.ts` |
| `question_number` **not declared** in the save schema | survives on `.passthrough()` only | `grep -n "question_number" Vibhaga-API/api/src/onboarding/validation.ts` → **no match** |
| `is_multipart` mapper | `q.is_multipart === true` | `sed -n '350p' Vibhaga-API/api/src/onboarding/publish.ts` |
| `is_multipart` computed client-side on save | `is_multipart: sub_questions.length > 0` | `grep -n "is_multipart: sub_questions.length" Vibhaga-Admin/src/lib/api/onboarding.ts` (`:402`) |
| Depth-3 rejection message | `Question ${qid}: sub-questions may nest at most 2 levels deep.` | `grep -n "nest at most" Vibhaga-API/api/src/onboarding/publish.ts` (`:395`) |
| Publish is one question per request (UI) | `publishQuestions(token, id, [qid])` | `sed -n '133,140p' 'Vibhaga-Admin/src/app/(admin)/onboard/[id]/page.tsx'` |
| The save endpoint is deliberately permissive | depth-2 children typed `z.array(z.record(z.unknown())).max(60)` | `sed -n '48,66p' Vibhaga-API/api/src/onboarding/validation.ts` |
| Admin default labels | roots `a, b, c…`; children `i, ii, iii…` | `sed -n '56,58p;568p;676p' Vibhaga-Admin/src/features/onboarding/QuestionCard.tsx` |
| ⚠️ **Web** fallback labels (when `label` is `""`) | roots `i, ii, iii…`; children `a, b, c…` — **the opposite scheme** | `sed -n '57,63p;123,129p' Vibhaga-Web/src/components/questions/SubParts.tsx` |
| Limits | ≤60 sub-questions per node, ≤20 answers per node, ≤50 000 chars per text field | `Vibhaga-API/api/src/onboarding/validation.ts` |
| A published question's structure survives a re-publish only by being re-sent | publish does `DELETE FROM sub_questions WHERE question_id = $1` then re-inserts | `sed -n '1593p' Vibhaga-API/api/src/db.ts` |

---

## 2. The shape you emit

### 2.1 The staged question

```jsonc
{
  "question_id": "…uuid…",
  "question_number": 7,          // ⚠️ a NUMBER. "7" silently becomes 0.
  "is_multipart": true,          // ⚠️ set explicitly — publish never derives it
  "question_text": "…S4's stem…",
  "question_text_sinhala": null,
  "lesson_ids": ["…uuid…"],
  "diagram_dsl": null,           // the constructed figure, drawn from its claim set
  "sub_questions": [
    {
      "sub_question_id": "…uuid…",
      "label": "a",
      "sort_order": 0,
      "text": "Find the length of $AB$.",
      "text_sinhala": null,
      "diagram_dsl": null,
      "sub_answer": { "sub_answer_id": "…uuid…", "approach": "…", "final_answer_latex": "…" },
      "sub_questions": [         // depth 2 — and no deeper
        { "sub_question_id": "…", "label": "i", "sort_order": 0, "text": "…", "sub_answer": {…}, "sub_questions": [] }
      ]
    }
  ],
  "answers": [],                 // whole-question answers[] — only when there are NO parts
  "ingestion_metadata": { "needs_human_review": true }
}
```

Every `*_id` must be a **UUID** or publish throws (`publish.ts:339`, `:374`, `:391`). `build-staged.py`
mints them as `uuid5(NAMESPACE, "<id_seed>/<path>")` — deterministic, recorded in the committed output
(`TRAPS.md` T9's "record ids before publishing" falls out of the ledger plus the spec).

### 2.2 ⚠️ Which path are you on? The two behave differently

| | Admin UI (a human drives it) | Agent path (`content.yaml` → `build-staged.py` → `playground-publish doc put`) |
|---|---|---|
| `is_multipart` | **computed for you** on every save (`onboarding.ts:402`) | the builder writes it |
| `sort_order` | renormalised to array index on save (`onboarding.ts:389-397`) | the builder writes it (array index) |
| legacy `kind`/`steps` keys | stripped on save (`onboarding.ts:380-386`) | the builder never emits them; unknown spec keys are refused |
| depth-3 | **unreachable** — the child node renders no "add nested" control (`QuestionCard.tsx:629`) | **refused by the builder** — it cannot reach the staged doc |
| whole-doc replace | same | same — `doc put` is a whole-doc `PUT`; the tool `GET`s, merges, `PUT`s — never blind |

### 2.3 What you type — the `parts:` tree in `content.yaml`

§2.1 is the shape that reaches the API; it is **not what you type**. `content.yaml` carries
`label` (bare, contiguous, §3.4), `text`, optional `figure`, optional `approach`+`final`, optional
nested `parts` — and `python3 tools/build-staged.py content.yaml` derives the rest:

| the structural jobs | Who does it |
|---|---|
| `is_multipart` | the builder — `true` iff `parts` is non-empty |
| `sort_order` | the builder — array index |
| `question_number` as a NUMBER (§3.1) | `n:` must be an integer or the spec is refused |
| the empty label (§3.3) | refused by the builder |
| non-bare or punctuated labels (§3.4) | refused — write `a`, never `(a)`/`a)`/`a.` |
| depth 3 | refused — the depth-3 blast radius of T-S5-4 cannot reach publish |
| whole-answer **and** parts on one item | refused |
| leaf part without `approach`+`final` | refused |
| ids | `uuid5(NAMESPACE, "<id_seed>/q<n>/<label-path>")`, "+answer" for answers — deterministic across runs |

---

## 3. Labels, numbering and the three silent corruptions

### 3.1 `question_number → 0`

The item is number **7**; you send `"7"`; the row says **0**. Then:

- the Admin card header reads `Question {q.question_number ?? index + 1}` (`QuestionCard.tsx:1025`) —
  `0` is not `null`, so it renders **"Question 0"**, not a helpful fallback;
- the bulk-publish confirm strip lists `Q0` (`onboard/[id]/page.tsx:425`);
- there is **no unique constraint** on `(batch, question_number)`, so every
  string-numbered question collapses onto `0` together and nothing errors.

**The catch:** it is a *type* bug, and the only cheap defence is a type assertion before you `PUT`:

```bash
jq '[.questions[] | select((.question_number|type) != "number")] | length' staged.json   # must be 0
```

⚠️ **`question_number` is not authorable in the Admin UI at all** — it appears only in display strings
and `aria-label`s (`QuestionCard.tsx:1025`, `:1108`, `:1116`, `:1272`); the only writer is
`blankQuestion(n)` (`onboarding.ts:517-528`). So a human cannot repair a wrong number through the
workspace.

### 3.2 `is_multipart` never computed server-side

`publish.ts:350` is `q.is_multipart === true` — a strict identity check, so `1`, `"true"` and `undefined`
all become `false`. A question with three sub-questions and no flag publishes as **not multipart**, and
the sub-question rows still get written. The row is internally contradictory and no reader complains.

**The catch:** assert the two agree, both before publish and after:

```bash
jq '[.questions[] | select((.is_multipart == true) != ((.sub_questions|length) > 0))] | length' staged.json  # 0
```

```sql
-- after publish: must return 0 rows
SELECT q.question_id, q.is_multipart, count(s.sub_question_id) AS subs
FROM questions q LEFT JOIN sub_questions s ON s.question_id = q.question_id
WHERE q.source_batch_id = '<session_id>'
GROUP BY q.question_id, q.is_multipart
HAVING q.is_multipart <> (count(s.sub_question_id) > 0);
```

### 3.3 The empty label is worse than blank — it silently **renumbers**

An empty `label` publishes (`publish.ts:380`). The student app then does
`{node.label || fallbackLabel(depth, i)}` (`Vibhaga-Web/src/components/questions/SubParts.tsx:62`), and
`fallbackLabel` (`:126-129`) numbers **roots `i, ii, iii…` and children `a, b, c…`** — which is the
**exact opposite** of the Admin's own defaults (roots `a, b, c`, children `i, ii, iii`;
`QuestionCard.tsx:57-58`, `:568`, `:676`).

So your `(a)` does not go missing. It comes back as **`(i)`**, confidently, in a numbering scheme
you never used — and a student sees a different question structure. Two further consequences:

- the label chip is `aria-hidden` (`SubParts.tsx:58-63`), so a screen-reader user hears **no part label
  at all**, real or fallen-back;
- an empty **`text`** renders `<BilingualText text="">` — an empty block with a label chip beside it, i.e.
  a visible, numbered, contentless part.

**The catch:** never rely on a renderer's fallback for a value you are supposed to author.

```bash
jq '[.. | objects | select(has("sub_question_id")) | select((.label // "" | length) == 0 or (.text // "" | length) == 0)] | length' staged.json  # 0
```

### 3.4 Labels are STUDENT-FACING and must be CONTIGUOUS — they are not provenance (TRAPS **T34** in Vibhaga-Docs)

⚠️ **Owner ruling, 2026-08-14, made for the paper side and binding here even harder.** The paper side
learned that faithfully copying printed part labels (`III, IV` with no `I`, a `b) I` group with no `a)`)
produces a question that simply looks broken. The ruling: ***"students never see the paper — they are
the customer."*** For generation there is no paper at all, so:

1. **Use the house scheme: roots `a, b, c…`; children `i, ii, iii…`** — the Admin defaults. There is no
   page to override it with.
2. ⚠️ **Number CONTIGUOUSLY from the start.** If a planned part is dropped, its siblings are relabelled —
   never leave a gap at the start, in the middle, or from a dropped group.
3. ⚠️ **No delimiter inside the label.** Both surfaces add their own shape: Web's chip
   (`SubParts.tsx:58-63`) and Admin's read-only card (`QuestionCard.tsx`, via `partLabel`). So
   `label: "a"` — not `"(a)"`, and **not `"a)"`**, which once rendered as **`(a))`** on a review screen.
   `build-staged.py` refuses non-bare labels outright.
4. **No compound labels for a flat list.** `"a) I" … "a) V"` is a tree flattened by hand — emit the tree
   (`a` with children `i…v`) so the parent's stem renders once and the group can be separated visually.

⇒ **Consequence for the critic:** check the labels a student actually sees, contiguous and gapless, and
treat a gap as a finding.

`sort_order` is the display order and defaults to the array index at publish (`publish.ts:381`, `:402`).
The builder writes it explicitly — the two must not disagree.

---

## 4. Traps — stories with the catch

Cross-cutting traps: [`docs/TRAPS.md`](../../docs/TRAPS.md). These are S5's.

### T-S5-1 — The write path with no witnesses
**Looked true:** multipart publishing works — the mapper handles roots and children, the FK ordering is
right (roots before children, `db.ts:1595-1600`), and there are unit tests.
**Actually:** `sub_questions` and `sub_answers` had **0 rows in production** when last measured. Unit
tests cover `buildContentRows`; they cannot cover Hyperdrive, the transaction, the renderer or the
operator.
**The check:** publish **one** multipart question first, then `SELECT` the tree back (§5) and open the
student page, **before** authoring the rest of the session. Discovering the shape is wrong after 30
questions costs 30 whole-document replaces.

### T-S5-2 — "It saved, so it will publish"
**Looked true:** the save returned `200`, so the structure is valid.
**Actually:** the save schema is **deliberately permissive** — the sub-question node is
`.passthrough()` and its children are `z.array(z.record(z.unknown()))` (`validation.ts:51-66`), so
depth-3 saves happily and fails only at publish (`publish.ts:395`). `question_number` is not even
declared. **The save endpoint validates almost nothing you care about.**
**The check:** run your own assertions on the staged JSON before the `PUT` (§3.1–§3.3), and treat a
publish `400` as a bug in your emitter, not as the gate working.

### T-S5-3 — The duplicate answer that rolls back the whole batch
**Looked true:** putting the answer in both `sub_answer` and `answers[]` is belt-and-braces — the mapper
will take whichever it finds.
**Actually:** it takes **both** (`publish.ts:274-276` pushes both sources into one list), inserts the
same `sub_answer_id` twice (`db.ts:1613`), hits the primary key, and the `catch` rolls the **entire
transaction** back (`db.ts:1636-1640`). On the UI path that is one question; on a batched API publish it
is every question in the call.
**The check:** one shape only — `sub_answer` per leaf part (this plugin's convention). Assert uniqueness
before publishing:
`jq '[.. | objects | select(has("sub_answer_id")) | .sub_answer_id] | (length) - (unique | length)'` → `0`.

### T-S5-4 — The depth-3 blast radius you quoted from the wrong doc
**Looked true:** a depth-3 node aborts the publish, so it costs the batch.
**Actually:** it costs the batch **only on the API path**. The Admin UI publishes one question per
request — `publishOne` → `publishQuestions(token, id, [qid])` (`onboard/[id]/page.tsx:133-138`), and the bulk
re-publish deliberately iterates one id per request *"so one invalid question can't sink the batch"*
(`onboard/[id]/page.tsx:218 (loop `:240-250`)`). Through the UI the error costs **exactly one question**.
**The check:** know which path you are on before you quote a radius — and note the other side of the
same coin: 30 questions = 30 publish requests.

### T-S5-5 — The Sinhala that has nowhere to live at the stem
**Looked true:** a bilingual multipart question can be authored bilingually throughout.
**Actually:** `0003` PD-C removed the **question-level** Sinhala field from the UI; only sub-questions
have `text_sinhala` (`QuestionCard.tsx:598-616`). A multipart question is therefore **monolingual at the
stem and bilingual in its parts** through the workspace. (The column exists and a `PUT` can write it —
but then no human can see or repair it. author-question-text §0.6.)
**The check:** `build-staged.py` writes every Sinhala field null — keep them null, and record in the
ledger if you ever deliberately override.

---

## 5. Verify (definition of done for S5, per question)

Run all seven over `staged.json` — the doc `build-staged.py` wrote and you are about to `doc put`.
**Every one must print `0`.** They are §3's three silent corruptions, plus the four things publish
decides for you by rejecting, defaulting or rolling back:

```bash
# 1. question_number is a JSON number — §3.1. "7" publishes as 0, silently, on every question at once.
jq '[.questions[] | select((.question_number|type) != "number")] | length' staged.json

# 2. is_multipart agrees with the tree — §3.2. publish.ts:350 never derives it.
jq '[.questions[] | select((.is_multipart == true) != ((.sub_questions // [] | length) > 0))] | length' staged.json

# 3. No empty label, no empty part text — §3.3. Neither is rejected (publish.ts:380, :382), and an
#    empty label does not blank: Web renumbers your (a) to (i).
jq '[.. | objects | select(has("sub_question_id"))
     | select(((.label // "")|gsub("^\\s+|\\s+$";"")|length) == 0
           or ((.text  // "")|gsub("^\\s+|\\s+$";"")|length) == 0)] | length' staged.json

# 4. Depth 2, never 3 — §0.4. A grandchild is a publish-time 400 (publish.ts:395); catching it here
#    costs nothing, catching it there costs the question (or, on a batched API publish, the call).
jq '[.questions[].sub_questions[]?.sub_questions[]?.sub_questions[]?] | length' staged.json

# 5. sort_order == array index — §3.4.
jq '[.. | objects | select((.sub_questions|type) == "array") | .sub_questions
     | to_entries[] | select(.value.sort_order != .key)] | length' staged.json

# 6. Every id is a UUID — the exact shape publish enforces,
#    UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
#    (`Vibhaga-API/api/src/onboarding/publish.ts:21`; **not** v4-specific). A bad question or
#    sub-question id throws; a bad answer id is skipped in SILENCE (`:279`, `:415`) and the question
#    publishes with no servable answer.
jq '[.. | objects | to_entries[]
     | select(.key | test("^(question|sub_question|answer|sub_answer)_id$"))
     | select((.value|type) != "string"
           or ((.value|test("^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$";"i")) | not))] | length' staged.json

# 7. No id reused — T-S5-3. One duplicated sub_answer_id ROLLBACKs the whole transaction (db.ts:1613).
jq '[.. | objects | to_entries[]
     | select(.key | test("^(question|sub_question|answer|sub_answer)_id$")) | .value]
    | (length) - (unique | length)' staged.json
```

⚠️ **Run them once against a deliberately corrupted copy** before you trust them. Seven assertions nobody
has watched fire are not a gate.

- [ ] All seven assertions print `0`, **on the doc as it now is** — re-read them out of the file rather
      than out of the values you meant to write.
- [ ] Labels follow the house scheme (roots `a, b, c`; children `i, ii, iii`), contiguous and bare — §3.4,
      and never left to Web's fallback, which numbers roots `i, ii, iii` — the opposite scheme (§3.3).
- [ ] `is_multipart` was **written explicitly** on every question, including the single-part ones
      (`false` is a value; `undefined` is the bug — §0.2). `build-staged.py` does this for you.
- [ ] Every `sub_question_id` / `sub_answer_id` is recorded **before** publishing (`TRAPS.md` T9) — the
      builder's uuid5s are deterministic, so the spec plus the ledger reconstructs the whole id set.
- [ ] ⚠️ If this is the session's **first** multipart question, route **that one alone** through
      validate → save → publish and have §5.1's read-back run on it before you author the second.
      T-S5-1: this write path has almost no precedent.

### 5.1 Deferred to after publish — the post-publish read-back

These need rows that do not exist yet, so they are **not** S5's definition of done. They are still real:

| Deferred check | Owner |
|---|---|
| The tree as a student will see it — labels, `sort_order`, parent links | the `qgen-critic` agent's read-back, re-scoped to the session's `source_batch_id` |
| `is_multipart` still agrees with the row's sub-question count after the write | same — the §3.2 SQL above |
| No empty `label` / empty sub-question `text` survived the write | same |
| No `question_number = 0` collapse in the batch | same |
| The student page renders the parts in order, with the authored labels | `skills/visual-check` in a headed browser — a fix verified at the mechanism is not verified, and the fallback-renumbering in §3.3 is only visible at the surface |

⚠️ **When they do run, they run as direct `SELECT`s — not through the API.** Hyperdrive's query cache is
not write-invalidated for ~75 s (`docs/TRAPS.md` **T5**), so a read-back through the API can show you the
previous state and send you chasing a bug that does not exist.

---

## 6. Keep this skill alive

Every number and line reference above was measured on 2026-08-09/10. **Once multipart rows exist in
production, this file is out of date in the most important way** — update §0.6, §1 and T-S5-1 in that
same PR, and record what actually broke. Cross-cutting traps go to [`docs/TRAPS.md`](../../docs/TRAPS.md).
