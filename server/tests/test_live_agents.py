import asyncio
import json

from fastapi.testclient import TestClient

from server.app.config import Settings
from server.app.live_agents import LiveRun
from server.app.main import create_app


class FakeGemini:
    def __init__(self, invalid_frontend: bool = False):
        self.invalid_frontend = invalid_frontend
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if "Backend agent" in prompt:
            return json.dumps(
                {
                    "report": "Built the item API.",
                    "files": [{"path": "backend/app.py", "content": "def items(): return []\n"}],
                }
            )
        if "Frontend agent" in prompt:
            path = "backend/stolen.py" if self.invalid_frontend else "frontend/App.tsx"
            return json.dumps(
                {
                    "report": "Built the task list.",
                    "files": [{"path": path, "content": "export function App() { return null }\n"}],
                }
            )
        return json.dumps(
            {
                "report": "Added the contract handoff.",
                "files": [{"path": "integration/README.md", "content": "# Integration\n"}],
            }
        )


def test_three_agents_generate_scoped_project(tmp_path):
    provider = FakeGemini()
    run = LiveRun("run-test", "Build tasks", tmp_path / "run-test", provider)

    asyncio.run(run.execute())

    assert run.status == "complete"
    assert len(provider.prompts) == 3
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


def test_agent_cannot_escape_its_owned_directory(tmp_path):
    run = LiveRun(
        "run-invalid", "Build tasks", tmp_path / "run-invalid", FakeGemini(invalid_frontend=True)
    )

    asyncio.run(run.execute())

    assert run.status == "failed"
    assert run.events[-1]["event_type"] == "run_failed"
    assert "outside frontend/" in run.events[-1]["message"]
    assert not (run.root / "backend/stolen.py").exists()


def test_live_config_is_available_without_a_gemini_key(tmp_path):
    client = TestClient(create_app(Settings(database_path=tmp_path / "state.db")))

    config = client.get("/live/config")
    start = client.post("/live/runs", json={"objective": "Build tasks"})

    assert config.status_code == 200
    assert config.json()["configured"] is False
    assert [role["id"] for role in config.json()["roles"]] == ["backend", "frontend", "integration"]
    assert start.status_code == 503
