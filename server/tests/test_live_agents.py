import asyncio
import json

from fastapi.testclient import TestClient

from server.app.config import Settings
from server.app.live_agents import LiveRun
from server.app.main import create_app


class FakeGemini:
    def __init__(self, role: str, invalid_path: bool = False):
        self.role = role
        self.invalid_path = invalid_path
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "Do not write code yet" in prompt:
            return json.dumps({"intention": f"{self.role} will implement its owned deliverable"})
        responses = {
            "backend": {
                "report": "Built the item API.",
                "files": [{"path": "backend/app.py", "content": "def items(): return []\n"}],
            },
            "frontend": {
                "report": "Built the task list.",
                "files": [
                    {
                        "path": "backend/stolen.py" if self.invalid_path else "frontend/App.tsx",
                        "content": "export function App() { return null }\n",
                    }
                ],
            },
            "integration": {
                "report": "Added the contract handoff.",
                "files": [{"path": "integration/README.md", "content": "# Integration\n"}],
            },
        }
        return json.dumps(responses[self.role])


def providers(invalid_frontend: bool = False):
    return {
        "backend": FakeGemini("backend"),
        "frontend": FakeGemini("frontend", invalid_frontend),
        "integration": FakeGemini("integration"),
    }


def test_three_apis_plan_then_generate_scoped_project(tmp_path):
    agent_providers = providers()
    run = LiveRun("run-test", "Build tasks", tmp_path / "run-test", agent_providers)

    asyncio.run(run.execute())

    assert run.status == "complete"
    assert all(len(provider.prompts) == 2 for provider in agent_providers.values())
    assert run.intentions == {
        "backend": "backend will implement its owned deliverable",
        "frontend": "frontend will implement its owned deliverable",
        "integration": "integration will implement its owned deliverable",
    }
    implementation_prompts = [provider.prompts[1] for provider in agent_providers.values()]
    assert all(
        all(intention in prompt for intention in run.intentions.values())
        for prompt in implementation_prompts
    )
    assert {item.agent_id for item in run.artifacts} == {
        "coordinator",
        "backend",
        "frontend",
        "integration",
    }
    assert (run.root / "backend/app.py").exists()
    assert (run.root / "frontend/App.tsx").exists()
    assert (run.root / "integration/README.md").exists()
    assert run.events[-1]["event_type"] == "run_complete"


def test_invalid_proposal_commits_no_files(tmp_path):
    run = LiveRun(
        "run-invalid", "Build tasks", tmp_path / "run-invalid", providers(invalid_frontend=True)
    )

    asyncio.run(run.execute())

    assert run.status == "failed"
    assert run.events[-1]["event_type"] == "run_failed"
    assert "outside frontend/" in run.events[-1]["message"]
    assert run.artifacts == []
    assert list(run.root.rglob("*")) == []


def test_live_config_reports_each_missing_api(tmp_path):
    client = TestClient(create_app(Settings(database_path=tmp_path / "state.db")))

    config = client.get("/live/config")
    start = client.post("/live/runs", json={"objective": "Build tasks"})

    assert config.status_code == 200
    assert config.json()["configured"] is False
    assert [role["configured"] for role in config.json()["roles"]] == [False, False, False]
    assert start.status_code == 503
    assert "backend, frontend, integration" in start.json()["detail"]
