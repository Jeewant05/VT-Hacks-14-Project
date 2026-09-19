"""The full demo scene, end to end, in mock/cache mode. If this passes, the curl demo works."""

from fastapi.testclient import TestClient

from scripts.database import demo_state
from server.app.config import Settings
from server.app.main import create_app
from server.app.store import write_state

APPROVED = {"token": "string", "user": "object"}


def _client(tmp_path):
    path = tmp_path / "scenario.db"
    write_state(path, demo_state())
    return TestClient(create_app(Settings(database_path=path)))


def _contract(role, fields):
    return {"method": "POST", "path": "/api/oauth", "role": role, "response_fields": fields}


def _changeset(ws, agent, fields, files):
    return {
        "id": f"cs-{ws}",
        "workstream_id": ws,
        "agent_id": agent,
        "files": files,
        "contract": _contract("provides" if ws == "backend" else "consumes", fields),
        "tests": [{"name": "t1", "status": "passed"}],
    }


def _types(state):
    return [e["event_type"] for e in state["events"]]


def test_full_scene(tmp_path):
    c = _client(tmp_path)

    # 1. join
    s = c.post("/agents/backend-agent/join").json()
    assert s["agents"][0]["verified"] is True
    s = c.post("/agents/frontend-agent/join").json()
    assert all(a["verified"] for a in s["agents"])

    # revoked / unknown identity is refused
    assert c.post("/agents/rogue-agent/join").status_code == 404

    # 2. claim
    c.post("/workstreams/backend/claim", json={"agent_id": "backend-agent"})
    s = c.post("/workstreams/frontend/claim", json={"agent_id": "frontend-agent"}).json()
    assert {w["status"] for w in s["workstreams"]} == {"active"}

    # wrong agent cannot claim
    r = c.post("/workstreams/backend/claim", json={"agent_id": "frontend-agent"})
    assert r.status_code == 403

    # 3. declare -> conflict opens, decision attached
    c.post("/workstreams/backend/declare",
           json={"agent_id": "backend-agent", "contract": _contract("provides", APPROVED)})
    wrong = {"accessToken": "string", "profile": "object"}
    s = c.post("/workstreams/frontend/declare",
               json={"agent_id": "frontend-agent", "contract": _contract("consumes", wrong)}).json()
    open_conflicts = [x for x in s["conflicts"] if x["status"] == "open"]
    assert len(open_conflicts) == 1
    assert open_conflicts[0]["conflicting_field"] == "accessToken"
    assert open_conflicts[0]["decision_id"] == "auth-response"
    assert {w["status"] for w in s["workstreams"]} == {"blocked"}
    assert "conflict_opened" in _types(s)

    # submit while blocked -> 409
    r = c.post("/workstreams/frontend/submit",
               json=_changeset("frontend", "frontend-agent", wrong, ["src/components/login/x.tsx"]))
    assert r.status_code == 409

    # 4. redeclare -> conflict resolves
    body = {"agent_id": "frontend-agent", "contract": _contract("consumes", APPROVED)}
    s = c.post("/workstreams/frontend/declare", json=body).json()
    assert all(x["status"] == "resolved" for x in s["conflicts"])
    assert {w["status"] for w in s["workstreams"]} == {"active"}
    assert "conflict_resolved" in _types(s)

    # 5. submit both -> complete
    c.post("/workstreams/backend/submit",
           json=_changeset("backend", "backend-agent", APPROVED, ["src/api/auth/oauth.ts"]))
    cs = _changeset("frontend", "frontend-agent", APPROVED, ["src/components/login/x.tsx"])
    s = c.post("/workstreams/frontend/submit", json=cs).json()
    assert {w["status"] for w in s["workstreams"]} == {"complete"}
    assert s["objective"]["status"] == "complete"
    assert _types(s)[-1] == "objective_completed"

    # 6. reset
    s = c.post("/reset").json()
    assert s["events"] == [] and s["conflicts"] == []


def test_state_persists_across_requests(tmp_path):
    c = _client(tmp_path)
    c.post("/agents/backend-agent/join")
    assert c.get("/state").json()["agents"][0]["verified"] is True
