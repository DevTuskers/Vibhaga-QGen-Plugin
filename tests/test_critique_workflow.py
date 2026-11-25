import asyncio
import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/generate/critique-workflow.py"


class WorkflowAgentError(Exception):
    pass


class CritiqueWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.critic = self.root / "wt/test/critic"
        self.config = self.root / "wt/current-critique.json"
        self.config.parent.mkdir()
        self.script = self.root / "skills/generate/critique-workflow.py"
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.script)
        self.events = []
        self.logs = []
        self.fails = None

    def run_round(self, config):
        self.config.write_text(json.dumps({"plugin": str(self.root), **config}), encoding="utf-8")

        async def register(meta):
            self.events.append("register")

        async def agent(prompt, **kwargs):
            self.events.append((prompt, kwargs))
            if self.fails and kwargs["label"].startswith(self.fails):
                raise WorkflowAgentError("critic timed out")
            props = kwargs["schema"]["properties"]
            return {key: {"string": "", "integer": 0, "array": []}[spec["type"]]
                    for key, spec in props.items()} | {"verdict": "SATISFIED"}

        async def parallel(calls):
            self.events.append("parallel")
            return await asyncio.gather(*(call() for call in calls))

        runpy.run_path(str(self.script), init_globals={
            "register_workflow": register, "agent": agent, "parallel": parallel,
            "log": self.logs.append, "WorkflowAgentError": WorkflowAgentError,
        })

    def batch(self, figures):
        return {
            "stage": "batch", "round": 2, "batch_id": "example",
            "corpus": "/test/corpus", "db_env": "/test/db.env", "vc": "/test/vc", "figures": figures,
            "chunks": [{
                "questions": [13, 24],
                "reports": {kind: str(self.critic / f"{kind}/r2.md") for kind in ("content", "diagram")},
                "previous": {"diagram": {"report": "/test/previous.md", "rows": "/test/hashes.txt"}},
            }],
        }

    def test_plan_uses_one_shared_agent_with_plan_inputs(self):
        self.run_round({
            "stage": "plan", "round": 1, "reports": {"plan": str(self.critic / "plan-r1.md")},
            "plan": {"items": "/test/plan.yaml", "similar": "/test/similar.json",
                     "dedup": "/test/dedup.md", "signals": "/test/signals.md", "cards": ["/test/card.yaml"]},
        })
        registered, (prompt, kwargs) = self.events
        self.assertEqual(registered, "register")
        self.assertIn('Mode: plan\n', prompt)
        self.assertIn('cards ["/test/card.yaml"]', prompt)
        self.assertIn("replace", kwargs["schema"]["required"])
        self.assertEqual(kwargs["vm_mode"], "shared")
        self.assertNotIn("mode", kwargs)

    def test_figures_dispatch_both_critics_in_parallel(self):
        self.run_round(self.batch(figures=True))
        registered, parallel, (content, content_args), (diagram, diagram_args) = self.events
        self.assertEqual((registered, parallel), ("register", "parallel"))
        self.assertIn("qgen-critic.md", content)
        self.assertIn("qgen-diagram-critic.md", diagram)
        self.assertIn("Chunk: questions 13..24. Previous report: /test/previous.md. "
                      "Previous rows: /test/hashes.txt.", diagram)
        self.assertEqual((content_args["vm_mode"], diagram_args["vm_mode"]), ("shared", "shared"))

    def test_figureless_batch_dispatches_only_content(self):
        self.run_round(self.batch(figures=False))
        self.assertEqual(len(self.events), 2)
        self.assertIn("qgen-critic.md", self.events[1][0])

    def test_agent_error_logged_and_fails_round(self):
        self.fails = "diagram"
        with self.assertRaisesRegex(RuntimeError, "Critique agent failed"):
            self.run_round(self.batch(figures=True))
        content, diagram = json.loads(self.logs[-1])["results"]
        self.assertEqual(content["verdict"], "SATISFIED")
        self.assertEqual(diagram["error"], "critic timed out")

    def test_round_cap_prevents_agent_calls(self):
        with self.assertRaisesRegex(ValueError, "plan critique round limit exceeded"):
            self.run_round({"stage": "plan", "round": 3})
        self.assertEqual(self.events, ["register"])
