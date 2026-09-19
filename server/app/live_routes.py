import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.app.live_agents import ROLES, LiveRuns


class LiveStartRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=2_000)


class LiveRunResponse(BaseModel):
    run_id: str
    status: str


def build_live_router(runs: LiveRuns, model: str, guard=None) -> APIRouter:
    router = APIRouter(prefix="/api/live", tags=["live-agents"])
    # Only starting a run spends provider credit, so only that is gated.
    # Reading config or following an existing run stays open, or the
    # dashboard cannot even report which providers are configured.
    billable = [Depends(guard)] if guard else []

    @router.get("/config")
    async def config():
        return {
            "configured": runs.configured,
            "model": model,
            "roles": [
                {
                    "id": role.id,
                    "title": role.title,
                    "responsibility": role.responsibility,
                    "configured": role.id in runs.configured_roles,
                }
                for role in ROLES
            ],
        }

    @router.post("/runs", response_model=LiveRunResponse, dependencies=billable)
    async def start(body: LiveStartRequest):
        try:
            run = runs.start(body.objective)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return LiveRunResponse(run_id=run.run_id, status=run.status)

    @router.get("/runs/{run_id}")
    async def snapshot(run_id: str):
        try:
            return runs.get(run_id).snapshot()
        except KeyError as exc:
            raise HTTPException(404, "live run not found") from exc

    @router.get("/runs/{run_id}/events")
    async def events(run_id: str):
        try:
            run = runs.get(run_id)
        except KeyError as exc:
            raise HTTPException(404, "live run not found") from exc

        async def stream():
            sent = 0
            while True:
                while sent < len(run.events):
                    event = run.events[sent]
                    sent += 1
                    yield f"data: {json.dumps(event)}\n\n"
                if run.task is not None and run.task.done():
                    break
                await asyncio.sleep(0.2)

        return StreamingResponse(stream(), media_type="text/event-stream")

    return router
