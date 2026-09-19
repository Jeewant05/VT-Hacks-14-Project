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
    return TestClient(create_app(Settings(demo_token=None, database_path=tmp_path / "web.db", ans_domain=DOMAIN)))


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


def test_every_api_route_lives_under_api(tmp_path):
    """No server route may sit outside /api.

    The dashboard calls /api/* and the dev proxy no longer rewrites the prefix,
    so a router mounted anywhere else 404s in the browser while every server-side
    test still passes. That is exactly how /live and /traces shipped broken.

    Read from the OpenAPI schema, not app.routes: included routers appear there
    as opaque objects with no .path, so walking app.routes silently inspects
    almost nothing and the check passes no matter what is mounted.
    """
    app = create_app(Settings(demo_token=None, database_path=tmp_path / "routes.db", ans_domain=DOMAIN))
    allowed = {"/.well-known/agent-card.json"}
    stray = [
        path
        for path in app.openapi()["paths"]
        if not path.startswith("/api") and path not in allowed
    ]
    assert not stray, f"routes outside /api will 404 from the dashboard: {stray}"


def test_the_paths_the_dashboard_actually_calls_exist(tmp_path):
    """Pin the exact paths ui/src calls, so a prefix change cannot silently break them."""
    c = client(tmp_path)
    for path in ["/api/health", "/api/state", "/api/traces?limit=12", "/api/live/config"]:
        assert c.get(path).status_code != 404, path


def test_the_declared_ans_endpoint_answers(tmp_path):
    """Registration seals https://<host>/api, so that URL must not 404."""
    c = client(tmp_path)
    for host in HOSTS.values():
        r = c.get("/api", headers={"Host": host})
        assert r.status_code == 200, host
        assert r.json()["ansName"] == f"ans://v{ANS_VERSION}.{host}"
