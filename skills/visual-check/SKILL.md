---
name: visual-check
description: >-
  Render VDD figures and whole student-preview questions through the REAL Admin app and MEASURE
  them — labels vs canvas edge/stroke/the geometry they name, angle numerals vs their arcs,
  claimed shaded cells vs painted fill, serif-vs-sans label mixes — then LOOK at the contact
  sheet it writes. Mode 1 batches staged docs / VDD files through /diagtest headlessly; mode 2
  (`--session <id>`) drives a headed browser through the playground student preview, signs out,
  and proves the revocation. Use after authoring or templating a figure (before `validate`), and
  after `doc put` when you need rendered evidence — not for authoring, that is the tools' job.
argument-hint: "[staged.json | figure dir | figure.json …]  or  --session <playground-session-id>"
---

# visual-check — render it like a student sees it, then measure + look

Two modes, one tool — `tools/visual-check.mjs` + the pure rules module `tools/visual-metrics.mjs`
(unit-tested offline in `tests/test_visual_metrics.mjs`).

## Mode 1 — batch render + measure (the command to run)

```bash
node tools/visual-check.mjs <staged.json | dir | figure.json …> \
    [--out DIR] [--widths 320,375,768] [--themes light,dark] \
    [--base-url http://localhost:<port>] [--claims-dir DIR] [--admin PATH] [--headed]
```

- **Inputs** — any mix of: a staged doc JSON (collects every `diagram_dsl` at question /
  sub-question / answer level as `Q<n>[.<label>][.ans<k>]`), a single VDD `.json`, or a directory
  of them. Claim sets are optional: `<base>.claims.txt`, `<base>-claims.txt`, or
  `--claims-dir/<id>.claims.txt` / `--claims-dir/<id>-claims.txt` (the name `vdd_templates.py`
  emits for a figure id — `Q3` → `Q3-claims.txt`). With `--claims-dir`, a figure that resolves no
  claim set gets a `WARN` line and a count in the summary — and a staged doc's figure id is
  `Q<n>[.<label>][.ans<k>]`, so a template's `figure_id` must equal that id for its claims to be
  found.
- **What it renders** — the real Admin `/diagtest` page (real `globals.css`, real next/font
  Inter + Noto Sans Sinhala, real `html[data-theme]` light/dark via `localStorage
  vibhaga_admin_theme`) with an esbuild bundle of the real `DiagramRenderer` injected — same
  bundle discipline as `vdd-check.mjs`. The figure sits in the StudentPreview figure-plate
  classes minus `max-w-md`, so 768 px really is 768. KaTeX `math` overlays are measured too —
  they are HTML, not `<text>` (T-QG-3).
- **Server** — `--base-url` to reuse a running Admin dev server, or it spawns
  `next dev` itself (needs an env file — `VIBHAGA_ADMIN_ENV` or `.env.local` — to EXIST;
  this mode never reads it; `src/lib/env.ts` throws at module load without `NEXT_PUBLIC_*`, so
  a 500 after spawn means the env file is incomplete). `--admin` = the Admin CHECKOUT
  (`--admin` > `VIBHAGA_ADMIN` > `<plugin>/../Vibhaga-Admin`).
- **Output** — one line per figure, then a summary; `<out>/<id>/<theme>-<w>.png` (default
  `$TMPDIR/visual-check-out`), `<out>/report.json` (the measured label↔edge / label↔stroke
  distances — the W4 deliverable) and `<out>/contact-light-375.png` — every figure's
  light-375 render at native size, captioned, for the step-6b look. Each verdict line ends
  with the light-375 PNG's pixel size (`375×131`). Exit `1` any FAIL · `2` usage/env · `0` clean.

```
Q7  FAIL  font: KaTeX math ×1 + text ×4 · labels 5 (min edge 4.7px, min stroke -2.5px) ·
    target ok · arc — · shaded — · aspect ok · 375×131  → <out>/Q7/
9 figures · 2 pass · 7 fail · PNGs: 54 · report: <out>/report.json · contact: <out>/contact-light-375.png 384×800
```

### The six rules (visual-metrics.mjs — every width, rendered px)

| rule | fails when | claim-set downgrade |
|---|---|---|
| `edge` | label bbox < **8 px** from the canvas edge | `allow: label:"<text>"` → warn |
| `stroke` | label bbox < **6 px** from a stroke's EDGE | same |
| `target` | label sits > **1.5 × fontSize** from what it names (a `point` label → its own point, always; else the nearest paint). One target result per label, measured at the least-quantised width, governs the per-width rows AND the finding. **Word labels (≥3-letter run, any script — pictograph rows, headers) are exempt.** | `allow: label:"<text>"` → warn |
| `arc` | each angle numeral (`1`, `2`°, `x°`, `θ°`) resolves to its **owner arc** — the candidate whose drawn curve (sampled along the real span) is nearest among arcs whose span contains the label's polar angle — and fails if no near arc covers its direction, or if ≥2 numerals share one owner (`arc <id> carries N numerals`). Labelled angleMarks are candidates too (only their own renderer-placed label is exempt). ⚠️ a **bare side-length number near a wedge** (e.g. `60` next to an arc) can trip this — move the label or declare `allow: label:"60"` | `allow: label:"<text>"` → warn |
| `shaded` | only with a `shaded N of M cells` claim + `grid R by C` anchors: painted fill inside the grid vs claimed N + 0.5×halves, tolerance 0.1 cell | — |
| `font` | KaTeX `math` and `<text>` labels coexist, or two text fontFamilies | — |
| `aspect` | the 375 render's figure height > **2.0 ×** its width — taller than a phone screen; re-lay the figure out (a 1×10 shaded grid as 5×2). `vdd_templates finish` and `vdd-check` refuse the same canvas, so a built figure can only trip this from a hand-drawn spec | — |

### `--self-test` — the live check after editing the tool

`node tools/visual-check.mjs --self-test` renders two synthetic figures through `/diagtest`
end-to-end (clean PASS; a defective one FAILs font+edge). **Not part of `check-suite.py`** — the
offline suite runs with `VIBHAGA_ADMIN_ENV=/nonexistent` so nothing touches credentials; run this
live check by hand after changing visual-check/visual-metrics. SKIPs cleanly when the checkout has
no env file.

## LOOK — the rule the metrics cannot replace

**Open `contact-light-375.png` once — every figure at native 375 px, captioned — and log one line
per figure.** Open a single figure's `light-375.png` only when the sheet shows a problem or is too
small to judge. A PASS is "no rule
fired", not "looks right". ⚠️ **The look is the lead's job, never the critic's:** the `qgen-critic`
subagent is image-blind (probed 2026-10-02 — a PNG read returns a placeholder), so it consumes
`report.json` only and lists every visual conclusion as could-not-check. Point it at the output
directory, not at a PNG. What the five rules **cannot** catch:

- a label that clears every stroke but **names the wrong or an ambiguous edge** (e.g. a cuboid
  depth label at a corner);
- whether a marked arc **is the angle the stem means** (reflex vs interior choice);
- **legibility** — size, contrast, cramped-but-clear spacing are judgements, not distances;
- whether a pictograph icon **reads as the thing** it stands for;
- label↔label collisions and anything else that is two elements *both* in tolerance.

## Mode 2 — `--session <playground-session-id>` (headed, after `doc put`)

```bash
node tools/visual-check.mjs --session <id> [--admin PATH] [--out DIR]
```

Always headed Chromium (1440×900). **Credentials** come from `Vibhaga-Admin/.env.local`
(`VIBHAGA_ADMIN_EMAIL`/`VIBHAGA_ADMIN_PASSWORD`, or `VIBHAGA_ADMIN_ENV`) — read at runtime, never
printed, never on a command line, a log or a screenshot. (`--session` replaced the plan's
`--admin <session>` — `--admin` is the plugin-wide checkout flag.)

The drive: **sign in** (fields `Email`/`Password`, button `Sign in`; failure = `role=alert`
*"Incorrect email or password."*) → `/generate/<id>` → per question click
**`Preview as a student — question N`**, wait for the `Preview — question N, as a student reads it`
region and its fonts/svg, **unclamp** the scrollport + ancestors (`max-height:none; height:auto;
overflow:visible`) and grow the viewport to fit (an element shot captures only the visible box —
a clipped figure + black band WAS shipped once), element-screenshot `[data-student-scrollport]` →
`<out>/session/<theme>-Q<n>.png` — a shot that still leaves scrollable content or an svg outside
the port is a **`CLIPPED` = FAIL** verdict — and run the same in-page label measurement + `assess` on every
`<svg>` inside it (no claim set) — light AND dark. **Answer figures are already covered**: Web
reveals answers behind `RevealAnswer`, but Admin's preview expands everything — there is no
Reveal control to click, and the measurement walks every `<svg>` in the scrollport, answer
figures included. Then read the actor's `user.id` out of the Supabase session **immediately
after sign-in** (cookies — never a token), and whatever happens, **Sign out** runs under
`finally` (a failed click is reported loudly and the session cookies are expired in-page).
Prove the revocation: queries.sql **Q3** on the **Admin Auth** project — `VIBHAGA_ADMIN_AUTH_DB_URL`
is parsed into `PG*` env vars for psql (never on argv; `-f -` on stdin so `:'actor_id'`
interpolates, `-c` does NOT), read-only — or the printed `revocation: PENDING` line when the
env is unset. Never select token values.

### The rules that survive from the manual drive

- **A screenshot is not a rendered string** — read the SVG/text in the DOM too, not only the
  pixels.
- **A 403 after a successful sign-in is a permissions fact**, not a bad password — the `admins`
  allowlist is server-side.
- **A 204 from `/auth/v1/logout` is not proof (T4)** — only the re-query counts.
- ⚠️ **The ~75-second rule** — a flag clear/withhold is not student-visible for up to ~75 s
  (Hyperdrive's read cache is not write-invalidated). Never confirm through the student app inside
  the first minute; verify by `SELECT`, or wait. Never force it with **Publish changes** — that
  destroys the answer sub-tree and re-raises the flag (T-S8-2/T-S8-6).
- **One job, one tab, one actor** — no lock on the staged doc; a stale second tab's save
  overwrites everything (`last-write-wins` by design). Watching is safe; intervening from a stale
  tab is not.
