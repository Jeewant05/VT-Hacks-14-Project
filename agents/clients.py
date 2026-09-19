"""Small deterministic clients used to exercise the coordinator over HTTP.

These clients intentionally model scripted agents, not autonomous agents. They use
only the public coordinator API so the same flow can be run against a local server
or a deployed review environment.
"""

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class AgentClient:
    """HTTP client for one coordinator agent."""

    base_url: str
    agent_id: str

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = httpx.request(method, f"{self.base_url.rstrip('/')}{path}", timeout=5, **kwargs)
        response.raise_for_status()
        return response.json()

    def join(self) -> dict[str, Any]:
        return self._request("POST", f"/agents/{self.agent_id}/join")

    def claim(self, workstream_id: str) -> dict[str, Any]:
        return self._request(
            "POST", f"/workstreams/{workstream_id}/claim", json={"agent_id": self.agent_id}
        )

    def declare(self, workstream_id: str, contract: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/workstreams/{workstream_id}/declare",
            json={"agent_id": self.agent_id, "contract": contract},
        )

    def submit(
        self,
        workstream_id: str,
        contract: dict[str, Any],
        files: list[str],
        tests: list[dict[str, str]],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/workstreams/{workstream_id}/submit",
            json={
                "id": f"test-{workstream_id}",
                "workstream_id": workstream_id,
                "agent_id": self.agent_id,
                "files": files,
                "contract": contract,
                "tests": tests,
            },
        )


APPROVED_CONTRACT = {
    "method": "POST",
    "path": "/api/oauth",
    "role": "provides",
    "response_fields": {"token": "string", "user": "object"},
}

CONSUMER_CONTRACT = {
    "method": "POST",
    "path": "/api/oauth",
    "role": "consumes",
    "response_fields": {"token": "string", "user": "object"},
}

INCOMPATIBLE_CONTRACT = {
    "method": "POST",
    "path": "/api/oauth",
    "role": "consumes",
    "response_fields": {"accessToken": "string", "profile": "object"},
}

PASSED_TEST = [{"name": "agent smoke test", "status": "passed"}]
