"""HTTP surface for the strict three-agent orchestration flow."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.app.models import (
    IntentionDocument,
    Objective,
    OrchestrationChangeSet,
    OrchestrationState,
    ResolutionProposal,
)
from server.app.orchestration import OrchestrationError, OrchestrationKernel


class ObjectiveRequest(BaseModel):
    id: str = "objective-oauth"
    title: str = "Add organization-level OAuth login"
    description: str = "Coordinate three agents before overlapping changes are written."
    acceptance_criteria: list[str] = Field(default_factory=lambda: [
        "Every agent declares a structured intention before execution.",
        "Contract and dependency conflicts resolve before code changes begin.",
        "Every submitted ChangeSet matches its approved intention.",
    ])


class ResolutionApproval(BaseModel):
    approved_by: str


def build_orchestration_router(kernel: OrchestrationKernel) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["orchestration"])

    def fail(error: OrchestrationError) -> HTTPException:
        return HTTPException(status_code=409, detail=str(error))

    @router.post("/objectives", response_model=OrchestrationState)
    async def create_objective(body: ObjectiveRequest | None = None):
        body = body or ObjectiveRequest()
        return await kernel.create_objective(Objective(
            id=body.id, title=body.title, description=body.description,
            acceptance_criteria=body.acceptance_criteria,
        ))

    @router.get("/objectives/{objective_id}/status", response_model=OrchestrationState)
    async def status(objective_id: str):
        try:
            return kernel.state(objective_id)
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/agents/{agent_id}/plan", response_model=OrchestrationState)
    async def plan(agent_id: str, intention: IntentionDocument | None = None):
        try:
            return await kernel.plan(agent_id, intention)
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/intentions/validate", response_model=OrchestrationState)
    async def validate_intention(intention: IntentionDocument):
        try:
            return await kernel.plan(intention.agent_id, intention)
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/conflicts/detect", response_model=OrchestrationState)
    async def detect_conflicts(objective_id: str):
        try:
            state = kernel.state(objective_id)
            await kernel._validate_and_detect(state)  # kernel owns the state transition
            from server.app.store import write_orchestration_state
            write_orchestration_state(kernel.db_path, state)
            return state
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/conflicts/{conflict_id}/resolve", response_model=ResolutionProposal)
    async def resolve_conflict(conflict_id: str):
        try:
            return await kernel.propose_resolution(conflict_id)
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/conflicts/{conflict_id}/approve", response_model=OrchestrationState)
    async def approve_conflict(conflict_id: str, body: ResolutionApproval):
        try:
            return await kernel.approve_resolution(conflict_id, body.approved_by)
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/agents/{agent_id}/execute", response_model=OrchestrationState)
    async def execute(agent_id: str):
        try:
            return await kernel.execute(agent_id)
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/changesets/submit", response_model=OrchestrationState)
    async def submit_changeset(changeset: OrchestrationChangeSet):
        try:
            return await kernel.submit_changeset(changeset)
        except OrchestrationError as error:
            raise fail(error) from error

    @router.post("/objectives/{objective_id}/converge", response_model=OrchestrationState)
    async def converge(objective_id: str):
        try:
            return await kernel.converge(objective_id)
        except OrchestrationError as error:
            raise fail(error) from error

    return router
