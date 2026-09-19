"""Source of truth for the shared demo contracts; no coordinator behavior yet."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiContract(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    role: Literal["provides", "consumes"]
    request_fields: dict[str, str] = Field(default_factory=dict)
    response_fields: dict[str, str] = Field(default_factory=dict)


class TestResult(BaseModel):
    name: str
    status: Literal["passed", "failed", "not_run"]
    source: Literal["agent_reported", "synapse_executed"] = "agent_reported"


class ChangeSet(BaseModel):
    id: str
    workstream_id: str
    agent_id: str
    commit_sha: str | None = None
    files: list[str]
    contract: ApiContract
    tests: list[TestResult] = Field(default_factory=list)


class Objective(BaseModel):
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    status: Literal["active", "complete"] = "active"


class Workstream(BaseModel):
    id: str
    objective_id: str
    title: str
    agent_id: str
    owned_paths: list[str]
    depends_on: list[str] = Field(default_factory=list)
    contract: ApiContract
    status: Literal["pending", "active", "blocked", "complete"] = "pending"
    latest_changeset: ChangeSet | None = None


class AgentPrincipal(BaseModel):
    id: str
    # Canonical ANSName: ans://v<major.minor.patch>.<agentHost>. In mock mode this is
    # a placeholder label; in ANS mode it must resolve. See server/app/ans/names.py.
    ans_name: str
    role: str
    verified: bool = False
    # Populated by ANS registration; absent in mock mode.
    ans_agent_id: str | None = None
    identity_cert_fingerprint: str | None = None
    ans_status: str | None = None


class Conflict(BaseModel):
    id: str
    type: Literal["file", "contract"]
    workstream_ids: list[str]
    explanation: str
    conflicting_field: str
    decision_id: str | None = None
    recommendation: str
    status: Literal["open", "resolved"] = "open"


class Decision(BaseModel):
    decision_id: str
    title: str
    content: str
    affected_component: str
    created_at: str


class Event(BaseModel):
    event_id: str
    objective_id: str
    workstream_id: str | None = None
    agent_id: str | None = None
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str


class VerificationResult(BaseModel):
    agent_id: str
    verified: bool
    source: Literal["ans", "mock"]
    evidence: str
    checked_at: str
    # ANS-6 verification tier actually performed, and the badge state it saw.
    tier: Literal["badge", "scitt", "none"] = "none"
    badge_status: str | None = None


class WriteReceipt(BaseModel):
    event_id: str
    source: Literal["databricks", "cache"]
    status: Literal["written", "pending", "failed"]


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    identity_mode: str
    memory_mode: str
    live_integrations: bool = False
    # ANS mode only: what the coordinator actually verifies, for the integrations panel.
    identity_tier: Literal["badge", "scitt", "none"] = "none"
    dpop_required: bool = False


class WorkspaceState(BaseModel):
    phase: Literal["foundation"] = "foundation"
    objective: Objective | None = None
    workstreams: list[Workstream] = Field(default_factory=list)
    agents: list[AgentPrincipal] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
