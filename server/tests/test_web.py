"""The production web surface: agent cards and static serving.

The card's ANSName must equal the registered name for the host it is served on.
A mismatch publishes a claim the registry does not back, which is the failure
mode an external verifier looks for -- so it is worth a test rather than a
convention.
"""

from fastapi.testclient import TestClient

from scripts.database import ANS_VERSION, ans_name_for
from server.app.config import Settings
from server.app.main import create_app

DOMAIN = "synapse-vt.us"

# agent id -> the host it is registered on.
HOSTS = {
    "backend-agent": f"backend.{DOMAIN}",
    "frontend-agent": f"frontend.{DOMAIN}",
    "telemetry-agent": f"telemetry.{DOMAIN}",
    "coordinator": DOMAIN,  # the apex, not coordinator.<domain>
}


def client(tmp_path):
    return TestClient(create_app(Settings(database_path=tmp_path / "web.db", ans_domain=DOMAIN)))


def test_agent_card_ansname_matches_the_host_it_is_served_on(tmp_path):
    c = client(tmp_path)
    for host in HOSTS.values():
        card = c.get("/.well-known/agent-card.json", headers={"Host": host}).json()
        assert card["ansName"] == f"ans://v{ANS_VERSION}.{host}", host
        assert card["host"] == host


def test_agent_card_matches_what_registration_would_seal(tmp_path):
    """The card and scripts/ans_register.py must agree on every host."""
    c = client(tmp_path)
    for agent_id, host in HOSTS.items():
        card = c.get("/.well-known/agent-card.json", headers={"Host": host}).json()
        assert card["ansName"] == ans_name_for(agent_id, DOMAIN), agent_id


def test_each_subdomain_serves_its_own_identity(tmp_path):
    c = client(tmp_path)
    names = {
        h: c.get("/.well-known/agent-card.json", headers={"Host": h}).json()["name"]
        for h in HOSTS.values()
    }
    assert len(set(names.values())) == len(names), names


def test_api_still_wins_over_the_static_mount(tmp_path):
    assert client(tmp_path).get("/api/health").status_code == 200
