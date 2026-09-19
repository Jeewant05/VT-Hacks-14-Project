"""Server-side demo runner for ANS mode.

The dashboard drives the whole coordination flow, but in ANS mode every
privileged call needs a proof signed by an agent's identity key. A browser must
never hold those keys, so the run happens here instead and the dashboard just
asks for it.

The proofs are real, not bypassed. Each scripted agent signs with
`ANS_PUBLIC_BASE_URL` -- the public origin -- while the request travels over
loopback. That works because an ANS-6 verifier compares `htu` against its
configured authority and never reads the `Host` header, so a proof signed for
the public URL verifies on a local hop. The gate is the same one an external
caller would face.

Guarded by a shared secret: it mutates the workspace and costs real verification
work, so it is not something a stranger should be able to trigger.
"""

import asyncio
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from agents.clients import APPROVED_CONTRACT, CONSUMER_CONTRACT, PASSED_TEST, AgentClient
from server.app.ans.material import load as load_material
from server.app.ans.signer import DpopSigner
from server.app.config import Settings

log = logging.getLogger("synapse.demo")

# Matches the seeded workstreams in scripts/database.py.
PLAN = [
    ("backend-agent", "backend", APPROVED_CONTRACT,
     ["src/api/auth/oauth.ts", "src/auth/session.ts"]),
    ("frontend-agent", "frontend", CONSUMER_CONTRACT,
     ["src/components/login/OrganizationLogin.tsx"]),
    ("telemetry-agent", "telemetry", CONSUMER_CONTRACT,
     ["src/lib/analytics/authEvents.ts"]),
]


class DemoRunResponse(BaseModel):
    status: str
    agents: list[str]
    detail: str | None = None


def _run(settings: Settings, local_base: str) -> DemoRunResponse:
    """Drive the three scripted agents with real DPoP proofs.

    Phased, not agent-by-agent. The seeded workstreams all claim
    `src/auth/session.ts`, which is the collision the demo exists to show, and
    the coordinator refuses a ChangeSet while any conflict is open. So every
    agent must be re-scoped before the first submit -- the same order the
    dashboard used to drive by hand.
    """
    clients = {}
    for agent_id, _workstream, _contract, _files in PLAN:
        # Signed against the public origin, sent over loopback: an ANS-6 verifier
        # compares htu to its configured authority and never reads the Host
        # header, so the proof is the same one an external caller would present.
        certificate_pem, key_pem = load_material(agent_id, settings.ans_agent_identities)
        signer = DpopSigner.from_pem(certificate_pem, key_pem, settings.ans_public_base_url)
        clients[agent_id] = AgentClient(base_url=local_base, agent_id=agent_id, signer=signer)

    for agent_id, _ws, _contract, _files in PLAN:
        clients[agent_id].join()
    for agent_id, workstream, _contract, _files in PLAN:
        clients[agent_id].claim(workstream)
    for agent_id, workstream, contract, _files in PLAN:
        clients[agent_id].declare(workstream, contract)
    # Resolve every overlap before anything is submitted.
    for agent_id, workstream, _contract, files in PLAN:
        clients[agent_id].scope(workstream, files)
    for agent_id, workstream, contract, files in PLAN:
        clients[agent_id].submit(workstream, contract, files, PASSED_TEST)

    return DemoRunResponse(status="complete", agents=[a for a, *_ in PLAN])


def build_demo_guard(demo_token: str | None):
    """Dependency requiring the shared demo secret.

    Used for the runner, `/reset` and the live-agent routes -- all of which are
    destructive or cost money, and none of which a stranger who finds the URL
    should be able to trigger.
    """

    def guard(x_demo_token: str | None = Header(default=None)) -> None:
        if not demo_token:
            # Local development: no token configured, nothing to check. A public
            # deployment cannot reach here -- require_demo_token_for_public()
            # refuses to build the app without one.
            return
        # Constant-time: a timing oracle on a demo token is still a timing oracle.
        if not x_demo_token or not secrets.compare_digest(x_demo_token, demo_token):
            raise HTTPException(401, "invalid or missing X-Demo-Token")

    return guard


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0", "testserver"}


def require_demo_token_for_public(settings: Settings) -> None:
    """Refuse to start a public deployment with destructive endpoints open.

    Checked at startup rather than per request so the failure is loud and happens
    before the first visitor, not after.
    """
    from urllib.parse import urlsplit

    host = (urlsplit(settings.ans_public_base_url).hostname or "").lower()
    if host in LOCAL_HOSTS or settings.demo_token:
        return
    raise RuntimeError(
        f"ANS_PUBLIC_BASE_URL is public ({host}) but DEMO_TOKEN is unset. "
        "/api/reset, /api/demo/run and the live-agent routes would be open to "
        "anyone. Set DEMO_TOKEN."
    )


def build_demo_router(settings: Settings, demo_token: str | None, local_base: str) -> APIRouter:
    router = APIRouter(prefix="/api/demo", tags=["demo"],
                       dependencies=[Depends(build_demo_guard(demo_token))])

    @router.post("/run", response_model=DemoRunResponse)
    async def run() -> DemoRunResponse:
        try:
            # The scripted clients are blocking httpx; keep the event loop free.
            return await asyncio.to_thread(_run, settings, local_base)
        except Exception as exc:  # noqa: BLE001 - surface the failure to the dashboard
            log.warning("demo run failed: %s", exc)
            return DemoRunResponse(status="failed", agents=[], detail=str(exc)[:400])

    return router
