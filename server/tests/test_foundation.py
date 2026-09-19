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
    assert client.get("/health").json()["live_integrations"] is False
    state = client.get("/state").json()
    assert len(state["workstreams"]) == 2
    assert not any(agent["verified"] for agent in state["agents"])
    assert state["workstreams"][0]["contract"] != state["workstreams"][1]["contract"]


def test_unknown_agent_is_not_mock_verified():
    result = asyncio.run(
        MockIdentity().verify(AgentPrincipal(id="unknown", ans_name="unknown.demo", role="unknown"))
    )
    assert not result.verified
    assert result.source == "mock"
