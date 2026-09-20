import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.app.config import Settings
from server.app.live_agents import Artifact, LiveRun, LiveRuns
from server.app.live_preview import render_agent_preview
from server.app.live_routes import build_live_router
from server.app.main import create_app


class FakeProvider:
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
                    },
                    {
                        "path": "frontend/preview.json",
                        "content": json.dumps({
                            "title": "Task Flow",
                            "subtitle": "A focused task manager built by the agent team.",
                            "accent": "#6d5dfc",
                            "primary_action": "Add task",
                            "metrics": [{"value": "3", "label": "Open tasks"}],
                            "cards": [{
                                "title": "Ship demo",
                                "description": "Validate the finished preview.",
                                "badge": "In progress",
                            }],
                        }),
                    },
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
        "backend": FakeProvider("backend"),
        "frontend": FakeProvider("frontend", invalid_frontend),
        "integration": FakeProvider("integration"),
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
    assert (run.root / "frontend/preview.json").exists()
    assert (run.root / "integration/README.md").exists()
    assert run.preview_html is not None
    assert "Task Flow" in run.preview_html
    assert run.snapshot()["preview_url"] == "/api/live/runs/run-test/preview"
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


def test_preview_escapes_agent_content_and_is_served_with_a_sandbox(tmp_path):
    spec = {
        "title": "<script>alert('no')</script>",
        "subtitle": "A safe generated app.",
        "accent": "#123456",
        "primary_action": "Launch",
        "metrics": [],
        "cards": [{"title": "Card", "description": "Details", "badge": "Ready"}],
    }
    html = render_agent_preview(
        "Build safely", [Artifact("frontend/preview.json", "frontend", json.dumps(spec))]
    )
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html

    runs = LiveRuns({}, tmp_path, None)  # type: ignore[arg-type]
    run = LiveRun("run-preview", "Build safely", tmp_path / "run-preview", {})
    run.status = "complete"
    run.preview_html = html
    runs.runs[run.run_id] = run
    app = FastAPI()
    app.include_router(build_live_router(runs))

    response = TestClient(app).get("/api/live/runs/run-preview/preview")
    assert response.status_code == 200
    assert response.headers["content-security-policy"].startswith("sandbox;")
    assert response.headers["x-content-type-options"] == "nosniff"


def test_live_config_reports_each_missing_api(tmp_path):
    client = TestClient(create_app(Settings(demo_token=None, 
        database_path=tmp_path / "state.db", trace_mode="cache", backend_provider="none",
        frontend_provider="none", qa_provider="none",
    )))

    config = client.get("/api/live/config")
    start = client.post("/api/live/runs", json={"objective": "Build tasks"})

    assert config.status_code == 200
    assert config.json()["configured"] is False
    assert [role["configured"] for role in config.json()["roles"]] == [False, False, False]
    assert start.status_code == 503
    assert "backend, frontend, integration" in start.json()["detail"]


# --- Why a run failed ---------------------------------------------------------


class RejectingProvider:
    """A provider whose upstream refuses every request, as with a spent account."""

    name = "huggingface"
    model = "openai/gpt-oss-120b:fastest"

    def __init__(self, message: str):
        self.message = message

    async def generate(self, prompt: str) -> str:
        raise RuntimeError(self.message)


CREDITS = 'huggingface 402: {"error":"You have depleted your monthly included credits."}'


def test_a_provider_rejection_is_not_reported_as_a_validation_failure(tmp_path):
    """No code is generated when the provider refuses, so there is nothing to validate.

    This surfaced as "The build did not pass validation" on the live site while
    the real cause was an out-of-credits account, which sent the operator to
    debug generated code that never existed.
    """
    rejecting = {role: RejectingProvider(CREDITS) for role in ("backend", "frontend", "integration")}
    run = LiveRun("run-402", "Build tasks", tmp_path / "run-402", rejecting)

    asyncio.run(run.execute())

    snapshot = run.snapshot()
    assert snapshot["status"] == "failed"
    assert "402" in snapshot["error"]
    assert snapshot["failure_title"] == "huggingface rejected the request: the account is out of credits."
    assert "validation" not in snapshot["failure_title"]


def test_a_successful_run_reports_no_failure(tmp_path):
    run = LiveRun("run-ok", "Build tasks", tmp_path / "run-ok", providers())
    asyncio.run(run.execute())
    snapshot = run.snapshot()
    assert snapshot["status"] == "complete"
    assert snapshot["error"] is None and snapshot["failure_title"] is None


def test_genuine_validation_failures_keep_the_validation_wording(tmp_path):
    run = LiveRun("run-bad", "Build tasks", tmp_path / "run-bad", providers(invalid_frontend=True))
    asyncio.run(run.execute())
    assert run.status == "failed"
    assert run.snapshot()["failure_title"] == "The agent build failed validation."


def test_failure_headlines_name_the_actual_cause():
    from server.app.live_agents import explain_failure

    assert "out of credits" in explain_failure(CREDITS)
    assert "rejected the API key" in explain_failure("huggingface 401: bad token")
    assert "rate limiting" in explain_failure("groq 429: rate limit exceeded")
    assert "not configured" in explain_failure("HUGGINGFACE_API_KEY is not set")
    assert "could not be reached" in explain_failure("huggingface request timed out")
