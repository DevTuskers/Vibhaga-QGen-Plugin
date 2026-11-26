# Devin cloud critique runtime

Devin cloud only; other hosts follow [Independent critics](../../AGENTS.md#generation-rules).

Owner ruling (2026-11-25):
> when Devin uses that plugin in a cloud session, I need it to use the shared_vm. I.e all the sub-agents should run in the parents machines. Also there it should use dynamic workflows.

Run each critique round with `run_workflow` on [critique-workflow.py](critique-workflow.py)
in this checkout. Every agent call uses `vm_mode="shared"`; omit mode so it inherits the
parent's mode. No `devin_session_create`, tar/attachments, or per-critic `qgen-setup`.
Critics reuse the parent's `wt/` and `/dev/shm/qgen-admin.env`; give paths, never secrets.
They are read-only except for reports and supporting outputs inside their assigned
`wt/<topic>/critic/` subtrees. They must not switch branches or restart shells. The lead still
authors and fixes; see [Who does what](SKILL.md#who-does-what).
For optional mechanical delegation, also use a dynamic workflow with `vm_mode="shared"` for
every agent; otherwise run the command in the parent.

Shared agents bill to the parent. For a lean ~10-question run, start the parent in Normal mode
and target 2–3 ACUs (owner ruling 2026-10-20). At the 30-ACU session cap, or if the rest cannot fit,
stop, commit clean work, write a handoff under `wt/<topic>/` and report what remains.

## One config per round

Write `wt/current-critique.json` in the **parent VM's plugin checkout**.
The workflow uses `VIBHAGA_QGEN_ROOT` from the workflow runtime environment when set, otherwise
the checkout containing the script, otherwise `~/repos/Vibhaga-QGen-Plugin` (for a script copied
outside the checkout, e.g. under `/tmp`). If using a non-default checkout with a copied script,
set `VIBHAGA_QGEN_ROOT` to that checkout's absolute path in the workflow environment before starting
the round. The config's `plugin` must name the selected checkout.
Use absolute paths. Never stage this file or include source text, credentials, or actor notes.
One checkout runs one critique round at a time. Keep the config unchanged while that run is
active; resume a workflow only with its original config. Archive the config in the private run
directory before replacing it if you may need to resume. The lead reads the reports and fixes
between rounds, then writes a new config and starts a **new** workflow run, not a resume.

Common keys: `stage` (`plan` or `batch`), `round` (integer starting at 1), `plugin`
(checkout path). Stage-specific keys:

| Stage | Required | Optional |
| --- | --- | --- |
| `plan` | `plan` object with `items`, `similar`, `dedup`, `signals` (paths) and `cards` (list of scope-card paths); `reports`: `{"plan": "<path>"}` | `previous`: `{"plan": {"report": "<path>"}}` |
| `batch` | `batch_id`, `corpus`, `db_env`, `vc`, `figures` (boolean), `chunks` (list of objects below) | `admin` and `web` together for non-sibling checkouts |

A typical batch has a single chunk. For each chunk set `reports.content` to its report file
path, plus `reports.diagram` when `figures` is true. For a split batch provide `questions` as
`[first, last]` (inclusive, ≤12 questions) for each chunk. On re-runs supply the same chunk's
prior critic outputs in `previous.content` and, when applicable, `previous.diagram` (each
`{"report": "<path>", "rows": "<rows dir or hashes.txt>" }`). Carry unchanged chunks per
[step 14](SKILL.md#batch-critique-and-fixes). When only some critic inputs changed in a chunk,
set its optional `critics` list (e.g. `["content"]`) and supply reports and previous inputs only
for those critics; otherwise the chunk runs all applicable critics. Assign different report directories per critic,
chunk and round: for example, `wt/<topic>/critic/r1/content/r1.md` and
`wt/<topic>/critic/r1/diagram/diagram-r1.md`. This isolates their SQL row caches and preserves
previous-round evidence.

A plan round starts one `Mode: plan` critic. A batch round starts content and diagram critics
concurrently when figures exist, otherwise only content. The workflow logs verdict/counts
and report paths (plus REPLACE keys for plan rounds). Read the actual reports before deciding
what to keep or fix. An agent error or missing/incomplete report is not SATISFIED; report it,
and never substitute a separate-VM child.
