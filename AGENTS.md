# vibhaga-qgen — always-on rules

This plugin generates maths practice questions for vibhaga.lk and publishes them to an Admin
playground session. There is **no source paper**: every number comes from the lesson corpus and the
stem you author. These rules hold in every session that loads the plugin.

## Generation rules
1. **Flagged-only.** Every generated row lands FLAGGED (`needs_human_review = true`) with
   `verified_by` NULL on every answer and sub-answer. Only a human clicking "Go live" in Admin
   clears it. No tool, query or agent lowers a flag or writes `verified_by`.
2. **Lesson content comes only from the corpus checkout**, never from an API. Resolve it as
   `VIBHAGA_CORPUS` env → sibling `<plugin>/../Vibhaga-Maths-Corpus`. No published lesson (or no scope
   card) for the grade → refuse. Never hand-edit the corpus.
3. **Two or more lessons tagged ⇒ each one is used.** At least one part's solution needs a concept
   from each tagged lesson. A tag the working never touches is a defect, not a bonus.
4. **Stay inside the scope card.** Nothing on its `not_taught` list, no later-grade notation.
5. **Prove by SQL, not by the API.** Use `queries.sql` (Q2 post-publish proof, Q3 Auth revocation —
   same merged project, actor asserted to exist AND to be an admin first). Never select token
   values.
6. **Drawn diagram text is simple English on every medium** (ADR 0021 —
   `Vibhaga-Docs/decisions/0021-english-only-diagram-text.md`). Point letters, labels, text
   elements, math latex, axis/category/series/value titles, units — never Sinhala, whatever the
   question's `medium` (the old T-S6b-6 medium condition is superseded; TRAPS T-QG-12). The a11y
   `title`/`description` are not drawn and keep the question's medium.

## Session discipline
- **One image per `read` call.** An image is seen only if the result shows it. Log what you saw at
  once; never re-read an image already confirmed. A read that came back without the image may be
  retried once, alone; after that, change approach.
- **30-ACU cap per session.** When you reach it, or the rest cannot fit, stop: commit clean work,
  write a hand-off prompt under `wt/<topic>/`, and report what is done and what is left.

## Public repo — never commit production content
- No real question text, corpus or scope-card text, real UUIDs, email addresses, or anything that
  identifies the Supabase projects (hosts, refs) or workers.dev hosts. Fixtures use synthetic
  placeholders (`00000000-0000-4000-8000-0000000000NN`, `auth.example.test`).

## Configuration — resolution order, never absolute paths
- `Vibhaga-Admin` checkout: `--admin PATH` flag → `VIBHAGA_ADMIN` env → sibling
  `<plugin>/../Vibhaga-Admin`.
- Admin credentials: `Vibhaga-Admin/.env.local` (or `VIBHAGA_ADMIN_ENV`), read at runtime, never
  printed.
- Lesson corpus: `VIBHAGA_CORPUS` env → sibling `<plugin>/../Vibhaga-Maths-Corpus`.

## Offline test command (run before every commit)
```
PYTHONDONTWRITEBYTECODE=1 VIBHAGA_ADMIN_ENV=/nonexistent/offline-test-only \
  python3 tools/check-suite.py
```

## Layout
`tools/` scripts · `tests/` unittest + node --test suites · `tests/fixtures/` synthetic fixtures ·
`skills/` slash-command skills · `agents/` subagents · `queries.sql` · `docs/MIGRATION.md`,
`docs/TRAPS.md`.
