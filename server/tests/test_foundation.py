import asyncio

from fastapi.testclient import TestClient

from scripts.database import demo_state
from server.app.adapters import MockIdentity
from server.app.config import Settings
from server.app.main import create_app
from server.app.models import AgentPrincipal
from server.app.store import write_state


def test_health_and_seeded_state(tmp_path):
    path = tmp_path / "test.db"
    write_state(path, demo_state())
    client = TestClient(create_app(Settings(database_path=path)))
    health = client.get("/health").json()
    assert health["live_integrations"] is False
    assert health["trace_mode"] == "cache"
    state = client.get("/state").json()
    assert len(state["workstreams"]) == 3
    assert not any(agent["verified"] for agent in state["agents"])
    assert state["workstreams"][0]["contract"] != state["workstreams"][1]["contract"]


def test_coordinator_events_are_available_from_trace_api(tmp_path):
    path = tmp_path / "test.db"
    write_state(path, demo_state())
    client = TestClient(create_app(Settings(database_path=path)))

    assert client.post("/agents/backend-agent/join").status_code == 200
    traces = client.get("/traces").json()

    assert len(traces) == 1
    assert traces[0]["source"] == "coordinator"
    assert traces[0]["event_type"] == "agent_joined"
    assert traces[0]["agent_id"] == "backend-agent"


def test_unknown_agent_is_not_mock_verified():
    result = asyncio.run(
        MockIdentity().verify(AgentPrincipal(id="unknown", ans_name="unknown.demo", role="unknown"))
    )
    assert not result.verified
    assert result.source == "mock"
