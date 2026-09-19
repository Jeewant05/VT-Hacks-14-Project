import asyncio
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.app.live_agents import LiveRuns


class LiveStartRequest(BaseModel):
    objective: str


class LiveRunResponse(BaseModel):
    run_id: str
    status: str


def build_live_router(runs: LiveRuns) -> APIRouter:
    router = APIRouter(prefix="/live", tags=["live-agents"])

    @router.post("/runs", response_model=LiveRunResponse)
    async def start(body: LiveStartRequest):
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        runs.start(run_id, body.objective)
        return LiveRunResponse(run_id=run_id, status="started")

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
                    yield f"data: {__import__('json').dumps(event)}\n\n"
                done = run.task is not None and run.task.done() and not run.conflict_pending
                if done:
                    break
                await asyncio.sleep(0.25)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.post("/runs/{run_id}/approve", response_model=LiveRunResponse)
    async def approve(run_id: str):
        try:
            run = runs.get(run_id)
        except KeyError as exc:
            raise HTTPException(404, "live run not found") from exc
        run.approve()
        return LiveRunResponse(run_id=run_id, status="approved")

    @router.get("/runs/{run_id}/file")
    async def file(run_id: str):
        try:
            run = runs.get(run_id)
        except KeyError as exc:
            raise HTTPException(404, "live run not found") from exc
        return {"version": run.version, "content": run.content, "conflict_pending": run.conflict_pending}

    return router
