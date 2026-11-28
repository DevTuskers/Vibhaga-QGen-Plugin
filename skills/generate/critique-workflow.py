import asyncio
import json
import os
from functools import partial
from pathlib import Path


META = {
    "name": "Qgen critique",
    "description": "One independent critique round on the parent VM",
    "phases": [{"title": "critique", "detail": "Review the plan or published batch"}],
}
SCHEMA = {
    "verdict": {"type": "string", "enum": ["SATISFIED", "NOT SATISFIED"]},
    "blockers": {"type": "integer"},
    "majors": {"type": "integer"},
    "minors": {"type": "integer"},
    "report_path": {"type": "string"},
}


def plugin_root():
    override = os.environ.get("VIBHAGA_QGEN_ROOT")
    if override:
        root = Path(override).expanduser()
        if not root.is_absolute():
            raise ValueError("VIBHAGA_QGEN_ROOT must point to an absolute checkout path")
        return root.resolve()

    for parent in Path(__file__).resolve().parents:
        if (parent / "tools/run-gates.py").is_file():
            return parent
    return (Path.home() / "repos/Vibhaga-QGen-Plugin").resolve()


def previous_prompt(previous):
    return f" Previous report: {previous['report']}." if previous.get("report") else ""


def batch_prompt(cfg, chunk, kind):
    report = chunk["reports"][kind]
    if kind == "content":
        prompt = (
            f"Critique playground batch {cfg['batch_id']} per your profile. Paths: plugin {cfg['plugin']}; "
            f"corpus {cfg['corpus']}; content-DB env {cfg['db_env']}; visual-check output {cfg['vc']}; "
            f"write the report to {report}."
        )
        if "admin" in cfg or "web" in cfg:
            prompt += f" VIBHAGA_ADMIN={cfg['admin']} VIBHAGA_WEB={cfg['web']}."
    else:
        prompt = (
            f"Critique the diagrams of playground batch {cfg['batch_id']} per your profile. "
            f"Paths: plugin {cfg['plugin']}; content-DB env {cfg['db_env']}; "
            f"visual-check output {cfg['vc']}; write the report to {report}."
        )
    if "questions" in chunk:
        first, last = chunk["questions"]
        if not 1 <= first <= last <= first + 11:
            raise ValueError("A chunk must be a range of 1–12 positive question numbers")
        prompt += f" Chunk: questions {first}..{last}."
    previous = chunk.get("previous", {}).get(kind, {})
    prompt += previous_prompt(previous)
    if previous.get("rows"):
        prompt += f" Previous rows: {previous['rows']}."
    return prompt


def jobs_for(cfg):
    stage, round_number = cfg["stage"], cfg["round"]
    mode = cfg.get("mode", "quick")
    if stage not in ("plan", "batch", "blueprint", "sample") or type(round_number) is not int:
        raise ValueError("Expected plan, batch, blueprint or sample stage and an integer round")
    if mode not in ("quick", "families") or (stage in ("blueprint", "sample") and mode != "families"):
        raise ValueError("Expected quick or families mode; blueprint and sample require families mode")
    limit = {"plan": 4 if mode == "families" else 2, "batch": 3, "blueprint": 4, "sample": 3}
    if not 1 <= round_number <= limit[stage]:
        raise ValueError(f"{stage} critique round limit exceeded")
    if stage == "blueprint":
        report = cfg["reports"]["blueprint"]
        return [("blueprint", report, (
            f"Mode: lesson blueprint\nPaths: blueprint {cfg['blueprint']}; card {cfg['card']}; "
            f"write the report to {report}."
        ) + previous_prompt(cfg.get("previous", {}).get("blueprint", {})))]
    if stage == "sample":
        report = cfg["reports"]["sample"]
        return [("sample", report, (
            f"Mode: family sample\nPaths: content {cfg['content']}; "
            f"family specs {json.dumps(cfg['families'])}; ledgers {json.dumps(cfg['ledgers'])}; "
            f"card {cfg['card']}; visual evidence {cfg.get('visual', 'none')}; write the report to {report}."
        ) + previous_prompt(cfg.get("previous", {}).get("sample", {})))]
    if stage == "plan":
        report = cfg["reports"]["plan"]
        plan = cfg["plan"]
        prompt = (
            ("Mode: family plan\n" if mode == "families" else "Mode: plan\n")
            + f"Critique the plan per your profile. Paths: plan-items {plan['items']}; "
            f"similar-plan {plan['similar']}; dedup-sheet {plan['dedup']}; signals {plan['signals']}; "
            f"cards {json.dumps(plan['cards'], sort_keys=True)}; write the report to {report}."
        )
        if mode == "families":
            prompt += f" Approved lesson blueprint: {plan['blueprint']}; mapped live family index: {plan['families']}."
        prompt += previous_prompt(cfg.get("previous", {}).get("plan", {}))
        return [("plan", report, prompt)]

    if not isinstance(cfg["figures"], bool):
        raise ValueError("Expected a figures boolean")
    kinds = ("content", "diagram") if cfg["figures"] else ("content",)
    jobs = []
    for chunk in cfg["chunks"]:
        selected = chunk.get("critics", list(kinds))
        if (not isinstance(selected, list) or not selected
                or any(kind not in kinds for kind in selected)
                or len(set(selected)) != len(selected)):
            raise ValueError("Chunk critics must be a nonempty, unique list of applicable critic kinds")
        for kind in selected:
            jobs.append((kind, chunk["reports"][kind], batch_prompt(cfg, chunk, kind)))
    if not jobs or (len(cfg["chunks"]) > 1 and any("questions" not in c for c in cfg["chunks"])):
        raise ValueError("Supply one batch or explicit question ranges for multiple chunks")
    return jobs


async def critique(cfg, kind, report, prompt):
    profile = "qgen-diagram-critic" if kind == "diagram" else "qgen-critic"
    instructions = (
        f"Read and follow {cfg['plugin']}/agents/{profile}.md. "
        f"Read-only critique: write only reports and supporting outputs inside {Path(report).parent}; "
        "do not switch branches, restart shells, or run qgen-setup."
    )
    if kind in ("content", "diagram"):
        instructions += " If needed, set VIBHAGA_ADMIN_ENV=/dev/shm/qgen-admin.env; do not read or print secrets."
    properties = dict(SCHEMA)
    if kind == "plan":
        properties["replace"] = {"type": "array", "items": {"type": "string"}}
        instructions += " Return REPLACE keys as Q<n>; use zero for counts not applicable to the plan."
    try:
        return await agent(
            f"{instructions}\n\n{prompt}",
            phase="critique",
            label=f"{kind}-r{cfg['round']} {report}",
            schema={"type": "object", "properties": properties, "required": list(properties)},
            # "when Devin uses that plugin in a cloud session, I need it to use the shared_vm.
            # I.e all the sub-agents should run in the parents machines. Also there it should use dynamic workflows."
            vm_mode="shared",
            soft_time_limit_minutes=15 if kind in ("plan", "blueprint") else 25,
        )
    except WorkflowAgentError as exc:
        return {"report_path": report, "error": str(exc)}


async def main():
    await register_workflow(META)
    root = plugin_root()
    config = root / "wt/current-critique.json"
    if not config.is_file():
        raise FileNotFoundError(
            f"No critique config at {config}; set VIBHAGA_QGEN_ROOT to the parent checkout "
            "and write wt/current-critique.json there"
        )
    cfg = json.loads(config.read_text(encoding="utf-8"))
    if Path(cfg["plugin"]).resolve() != root:
        raise ValueError("Critique config plugin path must match the selected checkout")
    jobs = jobs_for(cfg)
    wt = (root / "wt").resolve()
    dirs = set()
    for _, report, _ in jobs:
        path = Path(report).resolve().relative_to(wt)
        if len(path.parts) < 3 or path.parts[1] != "critic" or path.parent in dirs:
            raise ValueError("Reports must have separate directories under wt/<topic>/critic")
        dirs.add(path.parent)
    calls = [partial(critique, cfg, *job) for job in jobs]
    results = await parallel(calls) if len(calls) > 1 else [await calls[0]()]
    log(json.dumps({"stage": cfg["stage"], "round": cfg["round"], "results": results}, sort_keys=True))
    if any("error" in result for result in results):
        raise RuntimeError("Critique agent failed; see round results")


asyncio.run(main())
