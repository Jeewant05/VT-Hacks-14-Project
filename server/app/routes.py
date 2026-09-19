"""Coordinator HTTP API. Owner: P1. Every call returns the full WorkspaceState."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.app.models import ApiContract, ChangeSet, WorkspaceState
from server.app.service import Blocked, Coordinator, Forbidden, NotFound


class ClaimRequest(BaseModel):
    agent_id: str


class DeclareRequest(BaseModel):
    agent_id: str
    contract: ApiContract


class ScopeRequest(BaseModel):
    agent_id: str
    owned_paths: list[str]


def build_router(coordinator: Coordinator, fresh_state) -> APIRouter:
    router = APIRouter()

    @router.post("/agents/{agent_id}/join", response_model=WorkspaceState)
    async def join(agent_id: str):
        try:
            return await coordinator.join(agent_id)
        except NotFound as e:
            raise HTTPException(404, str(e)) from e
        except Forbidden as e:
            raise HTTPException(403, str(e)) from e

    @router.post("/workstreams/{ws_id}/claim", response_model=WorkspaceState)
    async def claim(ws_id: str, body: ClaimRequest):
        try:
            return await coordinator.claim(ws_id, body.agent_id)
        except NotFound as e:
            raise HTTPException(404, str(e)) from e
        except Forbidden as e:
            raise HTTPException(403, str(e)) from e

    @router.post("/workstreams/{ws_id}/declare", response_model=WorkspaceState)
    async def declare(ws_id: str, body: DeclareRequest):
        try:
            return await coordinator.declare(ws_id, body.agent_id, body.contract)
        except NotFound as e:
            raise HTTPException(404, str(e)) from e
        except Forbidden as e:
            raise HTTPException(403, str(e)) from e

    @router.post("/workstreams/{ws_id}/scope", response_model=WorkspaceState)
    async def reassign_scope(ws_id: str, body: ScopeRequest):
        try:
            return await coordinator.reassign_scope(ws_id, body.agent_id, body.owned_paths)
        except NotFound as e:
            raise HTTPException(404, str(e)) from e
        except Forbidden as e:
            raise HTTPException(403, str(e)) from e
        except Blocked as e:
            raise HTTPException(409, str(e)) from e

    @router.post("/workstreams/{ws_id}/submit", response_model=WorkspaceState)
    async def submit(ws_id: str, body: ChangeSet):
        try:
            return await coordinator.submit(ws_id, body)
        except NotFound as e:
            raise HTTPException(404, str(e)) from e
        except Forbidden as e:
            raise HTTPException(403, str(e)) from e
        except Blocked as e:
            raise HTTPException(409, str(e)) from e

    @router.post("/reset", response_model=WorkspaceState)
    async def reset():
        """Local demo only. Restores the seeded fixture."""
        return coordinator.reset(fresh_state())

    return router
