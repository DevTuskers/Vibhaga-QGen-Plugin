---
name: visual-check
description: Drive Vibhaga-Admin in a headed browser to *see* a generated question the way a student and a reviewer will — sign in, open the playground batch's card and its student preview, take an element screenshot at 375 px, then SIGN OUT and prove the session is gone. Use after a `/generate` run has been uploaded to a playground job, when you need rendered evidence of a stem, a figure or an answer — not for authoring (that is the tools' job).
argument-hint: "[playground job id or URL]"
---

# Visual check — look at the generated question before anyone signs off

> **Replaces `drive-admin-onboarding-ui` for the generation pipeline** — extracted from
> Vibhaga-Docs `.devin/skills/drive-admin-onboarding-ui` @08c09a9 (see docs/MIGRATION.md). There is no
> paper to upload and no per-question authoring loop; what remains is *"render it and look"*. **W4
> adds a one-command renderer** — until then this is the manual version.

## The rules that survive, in one breath

- **Credentials come from `Vibhaga-Admin/.env.local`** (or `VIBHAGA_ADMIN_ENV`), read at runtime,
  **never printed** — not in a command line, a log, a screenshot or a chat reply.
- **Headed Chromium**, so the evidence is pixels a human can check — and light + dark where it
  matters.
- **A screenshot is not a rendered string.** Read the SVG/text in the DOM, not only the pixels.

## The drive

1. **Sign in.** Email + password only — the Google button cannot be automated. A valid sign-in still
   has to pass the `admins` allowlist server-side, so a `403` after a *successful* sign-in is a
   permissions fact, not a bad password. Fields: `Email` / `Password`; submit reads **`Sign in`**;
   failure is a `role="alert"` reading *"Incorrect email or password."*
2. **Open the playground job** — `/onboard/<job-id>`. The cards are `role="group"` named
   `Question N` (use `{ exact: true }` — non-exact matches several cards on one page).
3. **Check what the card renders before trusting the preview.** A human cannot attest what the
   screen does not display — confirm the read-only card shows every field the batch populated:
   question text, **sub-part text and sub-part diagrams at every depth**, answers, lesson tags.
   Screenshots of any dialog/overlay too — assert it renders in the right place, not just that it
   opened.
4. **Student preview at 375 px.** Open the question's student preview (the card's preview panel or
   the student page `/q/<id>`) sized to a **375 px** phone viewport and take an **element
   screenshot** of the question card — not a full-page shot: the element shot is what a reviewer
   diffs. Read it: label collisions, clipped inline maths (`$…$` never wraps — see
   `author-question-answers` §4.1c), a figure that renders as *"Diagram coming soon"*
   (T-S6b-4 — it is not a loading state; the document failed `parseVdd`), Sinhala inside `\text{}`.
   ⚠️ **On an answer figure, Reveal first** — the worked answer is behind the reveal, so a collapsed
   card shows no answer `<svg>` and a check that stops at page load passes on a figure that never
   renders.
5. ⚠️ **The ~75-second rule.** A flag clear or a withhold is not student-visible for up to ~75 s
   (Hyperdrive's read cache is not write-invalidated). Never confirm visibility through the student
   app inside the first minute — verify with a direct `SELECT`, or wait. And never "force" it with
   **Publish changes**: that destroys the answer sub-tree and re-raises the flag (T-S8-2/T-S8-6).
6. **SIGN OUT — and prove it.** A `204` from `/auth/v1/logout` is **not** proof (**T4**). Re-query
   `auth.sessions` and `auth.refresh_tokens` on the **Admin Auth project** (not the content DB) for
   the actor's sessions and confirm zero remain, or revoke `scope=global` and re-query. Never print
   token values while doing it.
7. **Leave the browser.** One job, one tab, one actor — there is no lock or ETag on the staged doc;
   a stale second tab's next save overwrites everything (`last-write-wins` by design). Watching is
   safe; intervening from a stale tab is not.

## Which verb do I want — the only line you need

Wrong content live → **Unpublish** · your own unchecked content, not yet live → **Flag for review**
then publish · unchecked content already live → **Withhold from students** · already flagged →
**leave it, it is withheld** · a human checked it → **Mark reviewed** · wrong card flagged →
**Remove flag** / **Clear flag** · the content itself must change → and only then → **re-publish**.

⚠️ **Never use `Mark reviewed` to undo a flag** — it stamps `verified_by`/`verified_at` and files a
permanent audit row under your admin id. **Remove flag** exists precisely so you never have to.
