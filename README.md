# Vibhaga-QGen-Plugin (`vibhaga-qgen`)

A [Devin plugin](https://docs.devin.ai/cli/extensibility/plugins) that turns a
Devin agent into a maths-question author for [vibhaga.lk](https://vibhaga.lk):
it reads the private lesson corpus, generates practice questions with verified
answers and VDD figures, stages them as a `staged.json` doc, and publishes them
to an Admin playground batch.

There is **no source paper** in this pipeline. Every quantity a question uses
comes from the corpus lesson and the stem the agent authors — the tools and
skills here exist to keep generated content honest (claim sets, drawn-vs-stem
numeric verification, markdown gates, structure checks).

## Install

```bash
devin plugins install DevTuskers/Vibhaga-QGen-Plugin
```

Local checkout (linked; edits are live):

```bash
devin plugins install --local ./Vibhaga-QGen-Plugin
```

## Configuration

The tools need a checkout of the private **Vibhaga-Admin** app (it bundles the
real diagram renderer and the credentials file). Resolution order — never an
absolute path baked into this repo:

| What | Resolution order |
|---|---|
| Vibhaga-Admin checkout | `--admin PATH` flag → `VIBHAGA_ADMIN` env → sibling `<plugin>/../Vibhaga-Admin` |
| Admin credentials | `Vibhaga-Admin/.env.local`, or `VIBHAGA_ADMIN_ENV` pointing elsewhere — read at runtime, never printed |
| Lesson corpus | `VIBHAGA_CORPUS` env → sibling `<plugin>/../Vibhaga-Maths-Corpus` |

Layout the defaults expect:

```
Vibhaga/
├── Vibhaga-QGen-Plugin/     ← this repo
├── Vibhaga-Admin/           ← private; credentials + node_modules
└── Vibhaga-Maths-Corpus/    ← private; lesson markdown + scope cards
```

## Offline tests

Everything runs offline — no session create, no publish, no network:

```bash
PYTHONDONTWRITEBYTECODE=1 VIBHAGA_ADMIN_ENV=/nonexistent/offline-test-only \
  python3 tools/check-suite.py
```

Individual tools also carry `--self-test` (`tools/audit-claim-set.py`,
`tools/playground-publish.py`, `tools/vdd-check.mjs`, `tools/markdown-gate.mjs`).

## Public-repo rule

This repo is **public**. Never commit production content: no real question or
corpus text, no real UUIDs, no email addresses, no Supabase / `workers.dev`
hostnames. Tests and fixtures use synthetic values only
(`00000000-0000-4000-8000-0000000000NN`, `auth.example.test`). `docs/MIGRATION.md`
records the hygiene scan and how it was run.

## Licence

No licence granted; all rights reserved.
