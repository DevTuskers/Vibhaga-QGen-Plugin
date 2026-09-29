# vibhaga-qgen — always-on rules

This plugin generates maths practice questions for vibhaga.lk and publishes them
to an Admin playground batch. There is **no source paper** — every number in a
question comes from the lesson corpus and the stem you author.

## Public repo — never commit production content
- No real question text, corpus text, real UUIDs, email addresses, or
  Supabase/workers.dev hostnames. Fixtures use synthetic placeholders
  (`00000000-0000-4000-8000-0000000000NN`, `auth.example.test`).

## Configuration — resolution order, never absolute paths
- `Vibhaga-Admin` checkout: `--admin PATH` flag → `VIBHAGA_ADMIN` env → sibling
  `<plugin>/../Vibhaga-Admin`.
- Admin credentials: `Vibhaga-Admin/.env.local` (or `VIBHAGA_ADMIN_ENV`), read at
  runtime, never printed.
- Lesson corpus: `VIBHAGA_CORPUS` env → sibling `<plugin>/../Vibhaga-Maths-Corpus`.

## Offline test command (run before every commit)
```
PYTHONDONTWRITEBYTECODE=1 VIBHAGA_ADMIN_ENV=/nonexistent/offline-test-only \
  python3 tools/check-suite.py
```

## Layout
`tools/` runnable scripts · `tests/` unittest + node --test suites ·
`tests/fixtures/` synthetic fixtures · `skills/` slash-command skills ·
`agents/` custom subagents · `docs/MIGRATION.md`, `docs/TRAPS.md`.

<!-- W1's always-on generation rule arrives in session 2 — placeholder. -->
