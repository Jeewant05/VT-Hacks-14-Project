import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.app.config import Settings
from server.app.live_agents import Artifact, LiveRun, LiveRuns
from server.app.live_preview import render_agent_preview
from server.app.live_routes import build_live_router
from server.app.main import create_app
from server.app.tracing import CacheTraceSink


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


class MalformedProposalThenValidProvider(FakeProvider):
    def __init__(self, role: str):
        super().__init__(role)
        self.build_calls = 0

    async def generate(self, prompt: str) -> str:
        if "Do not write code yet" in prompt:
            return await super().generate(prompt)
        self.prompts.append(prompt)
        self.build_calls += 1
        if self.build_calls == 1:
            return json.dumps({
                "report": "I made the frontend.",
                "files": [{"path": "frontend/App.tsx"}],
            })
        return json.dumps({
            "report": "Built the task list.",
            "files": [
                {"path": "frontend/App.tsx", "content": "export function App() { return null }\n"},
                {
                    "path": "frontend/preview.json",
                    "content": json.dumps({
                        "title": "Task Flow", "subtitle": "Tasks stay in sync.",
                        "accent": "#6d5dfc", "primary_action": "Add task",
                        "metrics": [],
                        "cards": [{"title": "First task", "description": "Ready to ship.", "badge": "Open"}],
                    }),
                },
            ],
        })


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
    assert run.snapshot()["git_repository"] is True
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
    assert (run.root / ".git").is_dir()
    assert not [
        path for path in run.root.rglob("*")
        if ".git" not in path.parts and path.name != ".synapse-run.json"
    ]


def test_malformed_file_proposal_is_corrected_once_before_staging(tmp_path):
    agent_providers = providers()
    frontend = MalformedProposalThenValidProvider("frontend")
    agent_providers["frontend"] = frontend
    run = LiveRun("run-retry", "Build tasks", tmp_path / "run-retry", agent_providers)

    asyncio.run(run.execute())

    assert run.status == "complete"
    assert frontend.build_calls == 2
    assert "previous proposal was invalid" in frontend.prompts[-1]


def test_completed_run_flushes_its_trace_events(tmp_path):
    trace = CacheTraceSink()
    run = LiveRun("run-traced", "Build tasks", tmp_path / "run-traced", providers(), trace)

    asyncio.run(run.execute())
    events = asyncio.run(trace.recent(run_id="run-traced"))

    assert run.status == "complete"
    assert events[0].event_type == "run_complete"
    assert any(event.event_type == "validation_passed" for event in events)


def test_completed_run_can_be_restored_after_api_restart(tmp_path):
    root = tmp_path / "run-restored"
    run = LiveRun("run-restored", "Build tasks", root, providers())

    asyncio.run(run.execute())
    restored = LiveRun.load(root)

    assert restored is not None
    assert restored.status == "complete"
    assert restored.snapshot()["artifacts"] == run.snapshot()["artifacts"]


def test_legacy_workspace_can_be_recovered_for_dashboard(tmp_path):
    root = tmp_path / "run-legacy"
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "main.py").write_text("print('ready')\n", encoding="utf-8")

    recovered = LiveRun.recover(root)

    assert recovered is not None
    assert recovered.status == "complete"
    assert recovered.artifacts[0].agent_id == "backend"


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


# --- File-count limits: stated, counted, and retried once ---------------------


class OverproducingProvider(FakeProvider):
    """Returns too many files for its first `bad_answers` build answers, then behaves."""

    def __init__(self, role: str, bad_answers: int, too_many: int = 9):
        super().__init__(role)
        self.bad_answers, self.too_many, self.build_calls = bad_answers, too_many, 0

    async def generate(self, prompt: str) -> str:
        if "Do not write code yet" in prompt:
            return await super().generate(prompt)
        self.build_calls += 1
        if self.build_calls <= self.bad_answers:
            files = [{"path": f"backend/part{i}.py", "content": "x = 1\n"} for i in range(self.too_many)]
            return json.dumps({"report": "Split everything into many files.", "files": files})
        return await super().generate(prompt)


def swap_backend(provider):
    mixed = providers()
    mixed["backend"] = provider
    return mixed


def test_the_prompt_states_the_file_limit_the_validator_enforces(tmp_path):
    """The limit was enforced but never mentioned, so models exceeded it blindly."""
    backend = FakeProvider("backend")
    run = LiveRun("run-limits", "Build tasks", tmp_path / "run-limits", swap_backend(backend))
    asyncio.run(run.execute())

    build_prompt = next(p for p in backend.prompts if "Do not write code yet" not in p)
    assert "between 1 and 6 files" in build_prompt
    assert "characters" in build_prompt


def test_one_over_limit_answer_is_corrected_by_a_retry(tmp_path):
    flaky = OverproducingProvider("backend", bad_answers=1)
    run = LiveRun("run-retry", "Build tasks", tmp_path / "run-retry", swap_backend(flaky))

    asyncio.run(run.execute())

    assert run.status == "complete"
    assert flaky.build_calls == 2
    retry = next(e for e in run.events if e["event_type"] == "proposal_retry")
    assert "returned 9 files" in retry["message"]
    # The model is told what was wrong, so the second answer can fix it.
    assert "rejected: returned 9 files" in flaky.prompts[-1]


def test_a_persistent_over_limit_answer_fails_and_reports_the_count(tmp_path):
    stubborn = OverproducingProvider("backend", bad_answers=99, too_many=9)
    run = LiveRun("run-stubborn", "Build tasks", tmp_path / "run-stubborn", swap_backend(stubborn))

    asyncio.run(run.execute())

    assert run.status == "failed"
    assert stubborn.build_calls == 2  # one retry, not a loop
    assert "backend returned 9 files; it must return 1-6" in run.snapshot()["error"]
    assert run.snapshot()["failure_title"] == "The agent build failed validation."


def test_an_empty_answer_is_reported_as_empty_not_as_a_bad_count(tmp_path):
    class Empty(FakeProvider):
        async def generate(self, prompt: str) -> str:
            if "Do not write code yet" in prompt:
                return await super().generate(prompt)
            return json.dumps({"report": "Nothing to do.", "files": []})

    run = LiveRun("run-empty", "Build tasks", tmp_path / "run-empty", swap_backend(Empty("backend")))
    asyncio.run(run.execute())
    assert run.status == "failed"
    assert "returned no files" in run.snapshot()["error"]
