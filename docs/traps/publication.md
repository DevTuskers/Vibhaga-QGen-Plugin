# Publication traps

[Trap index](../TRAPS.md).

<a name="t4"></a>

## T4 — A `204` from `/auth/v1/logout` is not proof of revocation

**Looked true:** signed out, got a `204`, session gone.
**Actually:** sessions survive. A 12-day-old admin session with `not_after = NULL` was found live on
2026-07-27's credentials, on an admin plane with **no network gate**.
**The check:** re-query `auth.sessions` **and** `auth.refresh_tokens` for the user and confirm **zero
rows**. This check paid for itself: it found a stale session from an unrelated incident.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T4 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t5"></a>

## T5 — Hyperdrive's query cache is not invalidated by writes (~75 s)

**Looked true:** the sign-off failed — the question is still hidden from students right after clearing it.
**Actually:** the read was cached. The same question published unflagged returned `200` at t+0 s.
**The check:** verify a write with a **direct `SELECT`**, not through the API. ⚠️ And warn the operator:
someone who clears a flag, sees nothing, and reaches for **Publish changes** to force it will trigger the
*destructive* verb — which re-raises the flag and silently undoes their own sign-off.

⚠️ **Addendum 2026-09-27 — the same cache stales a server-side GATE, not only a verification read.** The playground's archived rule (`409 batch_archived`) read its guard row with a plain `SELECT` through Hyperdrive, so a tab opened before archiving saved **and published** on the archived session for ~30–90 s, and a just-reopened session still read as archived. Any read that decides whether a write is allowed must bypass the cache: include a STABLE function (Vibhaga-API#56: `AND now() IS NOT NULL`) or use a cache-disabled Hyperdrive binding. *(Phase 5 critique, Vibhaga-Admin#87.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T5 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t9"></a>

## T9 — The publish response is not load-bearing, but recording ids first is

**Looked true:** you can recover a bad publish from the response.
**Actually:** ids are **client-generated**, so they exist before the request. If the response is lost, the
ids are still recoverable four other ways — but only if you wrote them down.
**The check:** record `question_id`s **before** publishing. See the rollback runbook.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T9 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t77"></a>

## T77 — A migration that writes the published row but not the STAGED DOC reverts itself on the next publish.

**Looked true:** the content is migrated. `SELECT` shows the new markdown in `sub_questions.text` and
`questions.question_text`, a gate passed the bytes read back out of the database, and the row rendered
correctly in a real browser. Phase 6 checked all of that and was right about all of it.
**Actually:** an onboarded question exists in **two stores** — the live content rows **and** the onboarding
job's **staged document**, which is what the Admin card renders and what `POST /publish` upserts *from*.
The migration wrote the first and not the second, so:

| | staged doc (what the reviewer sees) | published row |
|---|---|---|
| `sub_questions.text <id>` | `Square \| ................` — **no delimiter row** | `\| Square \|  \|` |
| `questions.question_text <id>` | no `---\|---` | has it |

Two consequences, and the second is the dangerous one. **(a)** The review card rendered the *old* text —
correctly, because without a delimiter row it is not a table — so the owner would have signed off dot-runs
while believing they were approving the migrated table. **(b)** ⚠️ **Pressing `Publish changes` would have
overwritten the migrated rows with the stale ones**, silently undoing the migration, with every gate still
green and no error anywhere.

**The check:** after **any** write that does not go through the Admin UI — a migration, a repair, a direct
`UPDATE` — **diff the staged doc against the published rows before a human is asked to review**
(S11 §4.7). And prefer to make the edit in the **staged doc** and re-publish, which is the path that keeps
both stores in step by construction; that is what runs 3 and 4 did for their `question_number` repairs.
⇒ **This is T35's family — the review surface disagreeing with what is stored — reached by a new
mechanism.** T35 said *enumerate every field the batch populated*; T77 adds *and every store that holds it*.

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T77 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t142"></a>

## T142 — The playground publish raises the flag on the ROW, not in the staged doc

**Looked true:** every playground publish forces `needs_human_review = true` (0018 OD-2), so after a publish "the question is flagged" everywhere. The onboarding flag verbs mirror into the staged doc and say so (`staged_doc_updated`).
**Actually:** the publish response has no `staged_doc_updated` field, and the server does not write the forced flag back into `playground/<id>/questions.json`. A doc saved with the flag down stays down in R2 while the live row is up. The Phase 5 page then showed a flagged, withheld question as green "Published" after a reload. It was fixed client-side by `persistPublishOutcome` (Vibhaga-Admin#87), and any other client (curl, script, agent) reopens the hole.
**The check:** after every real publish, PUT the doc back with `published: true` and the flag `true` on every id in `question_ids ∪ reflagged ∪ reraised`. Then GET it and assert both fields per id. `playground-publish.py publish` does this (read-back 1) before its SQL read-back. Cited by `generate` §1/§4. *(Phase 5 critique finding; tool guard added in Phase 6, 2026-09-27.)*

*Source: Vibhaga-Docs `.devin/skills/_maths-onboarding/TRAPS.md` T142 @08c09a9 — production ids scrubbed; paper-era references kept as history where the lesson is pipeline-neutral.*

---

<a name="t-qg-4"></a>

## T-QG-4 — The drift check that never saw the answer: the read side knew a narrower shape than the write path

**Looked true:** a playground publish loop ended `published 4/4`, `read-back 1: staged doc confirms
4 published + flagged`, `provenance: 4 id(s) · OK` — then `t77: 4 question(s) · 92 comparisons ·
12 mismatch(es)`, every line `Q<n>.<part>.sa[<id>]: live row not in staged`. The run read as FAILED.
**Actually:** those live `sub_answers` rows WERE the staged ones — the printed ids matched the staged
doc's uuid5 `sub_answer_id`s exactly. `build-staged.py` emits a part's answer as the singular
`sub_answer` object (the shape `publish.ts collectSubAnswers` accepts beside `answers[]`), but
`t77-staged-vs-published.py` collected staged sub-answers only from `s.answers` — so every
sub-answer the publish wrote looked unclaimed, and none of their approach/final/diagram_dsl fields
were ever compared (92 vs the correct 128 comparisons). Question level needed no fix: build-staged
emits only `answers[]` there and the API reads only that.
**The check:** t77 now folds `s.sub_answer` ahead of `s.answers[]` — `collectSubAnswers`' own order —
before comparing. A staged doc carrying BOTH keys for one answer still flags (the duplicate pops the
live row once, then reports `missing live`), which is the double-insert refusal the staged schema
warns about. Pinned by `tests/test_t77_sub_answer_shapes.py`.

*Source: this plugin — W6, 2026-10-02; found on the first publish of a batch whose parts all carried
the singular form.*

<a name="t-qg-6"></a>

## T-QG-6 — The revocation check that saw zero rows: policy-less RLS hides `auth.*` entirely

**Looked true:** Q3's direct `count(*)` over `auth.sessions`/`auth.refresh_tokens` returned 0 —
"a clean logout".
**Actually:** RLS is enabled on `auth.users`, `auth.sessions` and `auth.refresh_tokens` with **no
policies**, so any role that is not BYPASSRLS sees zero rows — sessions or no sessions. A plain
reader role cannot observe revocation at all.
**The check:** Q3's `actor_exists = 1` guard is what caught it — the same reader saw zero users
too, so `ok` went false instead of silently passing. The fix is `qgen.q3(actor uuid)`, a
counts-only SECURITY DEFINER function owned by postgres (one-time setup: generate step 11); the
reader gets USAGE on schema `qgen` + EXECUTE, never a grant on `auth.*` — and never BYPASSRLS.

*Source: this plugin — W9, 2026-10-03.*
