"""Bounded three-agent coding runs with plan-before-write coordination."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from server.app.providers import Provider


@dataclass(frozen=True)
class AgentRole:
    id: str
    title: str
    responsibility: str
    allowed_root: str


ROLES = (
    AgentRole(
        "backend",
        "Backend agent",
        "Build the API, data model, and server-side behavior.",
        "backend",
    ),
    AgentRole(
        "frontend",
        "Frontend agent",
        "Build the UI that consumes the shared API contract.",
        "frontend",
    ),
    AgentRole(
        "integration",
        "Integration agent",
        "Review both implementations and add contract tests, setup, and handoff docs.",
        "integration",
    ),
)
ROLE_BY_ID = {role.id: role for role in ROLES}
MAX_OBJECTIVE_CHARS = 2_000
MAX_FILES_PER_AGENT = 6
MAX_FILE_CHARS = 50_000
MAX_TOTAL_CHARS = 180_000


@dataclass
class Artifact:
    path: str
    agent_id: str
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "agent_id": self.agent_id, "content": self.content}


@dataclass
class LiveRun:
    run_id: str
    objective: str
    root: Path
    providers: dict[str, Provider]
    events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    intentions: dict[str, str] = field(default_factory=dict)
    reports: dict[str, str] = field(default_factory=dict)
    status: str = "queued"
    task: asyncio.Task[None] | None = None

    def emit(self, agent: str, event_type: str, message: str, **extra: Any) -> None:
        self.events.append(
            {
                "agent_id": agent,
                "event_type": event_type,
                "message": message,
                "timestamp": datetime.now(UTC).isoformat(),
                **extra,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "status": self.status,
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "intentions": self.intentions,
            "reports": self.reports,
        }

    async def execute(self) -> None:
        self.status = "planning"
        self.root.mkdir(parents=True, exist_ok=False)
        self.emit("coordinator", "run_started", "Created an isolated project workspace")
        contract = self._contract()

        try:
            plans = await asyncio.gather(*(self._plan(role, contract) for role in ROLES))
            self.intentions = {role.id: plan for role, plan in zip(ROLES, plans, strict=True)}
            self.emit(
                "coordinator", "intentions_shared", "Shared all three intentions with every agent"
            )

            self.status = "building"
            backend, frontend = await asyncio.gather(
                self._build(ROLES[0], {"contract": contract}),
                self._build(ROLES[1], {"contract": contract}),
            )
            staged = self._stage(ROLES[0], backend, [])
            staged += self._stage(ROLES[1], frontend, staged)

            integration = await self._build(
                ROLES[2],
                {
                    "contract": contract,
                    "generated_files": [
                        {"path": item.path, "content": item.content[:8_000]} for item in staged
                    ],
                },
            )
            staged += self._stage(ROLES[2], integration, staged)
            self._validate_staged(staged)
            self._commit(contract, staged)
        except Exception as exc:  # noqa: BLE001 - failures belong in the live timeline
            self.status = "failed"
            self.emit("coordinator", "run_failed", str(exc)[:1_000])
            return

        self.status = "complete"
        self.emit(
            "coordinator",
            "run_complete",
            f"Committed {len(staged)} agent files after intention and scope validation",
        )

    async def _plan(self, role: AgentRole, contract: dict[str, Any]) -> str:
        self.emit(role.id, "intention_started", f"{role.title} is planning before coding")
        prompt = f"""You are the {role.title} planning your work before any files are written.
Objective: {self.objective}
Responsibility: {role.responsibility}
Owned directory: {role.allowed_root}/
Shared API contract: {json.dumps(contract)}

Return JSON only: {{"intention":"a concise plan covering approach, files, dependencies, and validation"}}.
Do not write code yet. Your intention will be shared with the other two agents.
"""
        raw = await self.providers[role.id].generate(prompt)
        data = self._json(raw)
        intention = data.get("intention")
        if not isinstance(intention, str) or not intention.strip():
            raise TypeError(f"{role.id} intention response is invalid")
        intention = intention.strip()[:3_000]
        self.emit(role.id, "intention_ready", intention)
        return intention

    async def _build(self, role: AgentRole, context: dict[str, Any]) -> dict[str, Any]:
        self.emit(role.id, "agent_started", f"{role.title} is implementing its intention")
        prompt = f"""You are the {role.title} in a coordinated coding demo.
Objective: {self.objective}
Responsibility: {role.responsibility}
You may create files only inside the `{role.allowed_root}/` directory.

Intentions agreed before implementation (use these to avoid conflicts):
{json.dumps(self.intentions, indent=2)}

Shared project context:
{json.dumps(context, indent=2)}

Return JSON only, without markdown fences, using this exact shape:
{{"report":"short implementation summary","files":[{{"path":"{role.allowed_root}/relative-name","content":"complete file contents"}}]}}
Create a small, coherent implementation aligned with all three intentions. Do not include secrets,
absolute paths, parent-directory traversal, or files outside your assigned directory.
"""
        raw = await self.providers[role.id].generate(prompt)
        proposal = self._json(raw)
        if not isinstance(proposal.get("report"), str) or not isinstance(
            proposal.get("files"), list
        ):
            raise TypeError(f"{role.id} response must contain report and files")
        self.emit(role.id, "proposal_received", proposal["report"][:1_000])
        return proposal

    def _stage(
        self, role: AgentRole, proposal: dict[str, Any], existing: list[Artifact]
    ) -> list[Artifact]:
        files = proposal["files"]
        if not files or len(files) > MAX_FILES_PER_AGENT:
            raise ValueError(f"{role.id} must return 1-{MAX_FILES_PER_AGENT} files")
        pending: list[Artifact] = []
        for value in files:
            if not isinstance(value, dict):
                raise TypeError(f"{role.id} returned an invalid file entry")
            path, content = value.get("path"), value.get("content")
            if not isinstance(path, str) or not isinstance(content, str) or not content.strip():
                raise TypeError(f"{role.id} returned a file without a path or content")
            normalized = PurePosixPath(path)
            if (
                normalized.is_absolute()
                or ".." in normalized.parts
                or not normalized.parts
                or normalized.parts[0] != role.allowed_root
            ):
                raise ValueError(f"{role.id} attempted to write outside {role.allowed_root}/")
            if len(content) > MAX_FILE_CHARS:
                raise ValueError(f"{path} exceeds the per-file size limit")
            if any(item.path == normalized.as_posix() for item in existing + pending):
                raise ValueError(f"duplicate generated path: {normalized.as_posix()}")
            pending.append(Artifact(normalized.as_posix(), role.id, content))
        self.reports[role.id] = proposal["report"][:2_000]
        self.emit(role.id, "proposal_staged", f"Staged {len(pending)} files; nothing written yet")
        return pending

    def _validate_staged(self, staged: list[Artifact]) -> None:
        missing = {role.id for role in ROLES} - {item.agent_id for item in staged}
        if missing:
            raise ValueError(f"missing deliverables from: {', '.join(sorted(missing))}")
        if sum(len(item.content) for item in staged) > MAX_TOTAL_CHARS:
            raise ValueError("generated project exceeds the run size limit")
        self.emit(
            "coordinator",
            "validation_passed",
            "Intentions, ownership, paths, duplicates, and size checks passed",
        )

    def _commit(self, contract: dict[str, Any], staged: list[Artifact]) -> None:
        self._write(
            Artifact(
                "shared/api-contract.json", "coordinator", json.dumps(contract, indent=2) + "\n"
            )
        )
        self.emit(
            "coordinator", "contract_committed", "Committed the coordinator-owned API contract"
        )
        for artifact in staged:
            self._write(artifact)
            self.emit(artifact.agent_id, "file_committed", artifact.path, path=artifact.path)

    def _write(self, artifact: Artifact) -> None:
        destination = self.root.joinpath(*PurePosixPath(artifact.path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.content, encoding="utf-8")
        self.artifacts.append(artifact)

    @staticmethod
    def _contract() -> dict[str, Any]:
        return {
            "endpoint": "GET /api/items",
            "response": {"items": [{"id": "string", "title": "string", "done": "boolean"}]},
            "ownership": {role.id: f"{role.allowed_root}/**" for role in ROLES},
        }

    @staticmethod
    def _json(raw: str) -> dict[str, Any]:
        value = raw.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(value)
        if not isinstance(data, dict):
            raise TypeError("Agent response must be a JSON object")
        return data


class LiveRuns:
    def __init__(self, providers: dict[str, Provider], root: Path):
        self.providers, self.root = providers, root
        self.runs: dict[str, LiveRun] = {}

    @property
    def configured(self) -> bool:
        return all(role.id in self.providers for role in ROLES)

    @property
    def configured_roles(self) -> set[str]:
        return set(self.providers)

    def start(self, objective: str) -> LiveRun:
        missing = [role.id for role in ROLES if role.id not in self.providers]
        if missing:
            raise RuntimeError(f"Missing agent provider configuration for: {', '.join(missing)}")
        objective = objective.strip()
        if not objective:
            raise ValueError("objective cannot be empty")
        if len(objective) > MAX_OBJECTIVE_CHARS:
            raise ValueError(f"objective must be at most {MAX_OBJECTIVE_CHARS} characters")
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        run = LiveRun(run_id, objective, self.root / run_id, self.providers)
        self.runs[run_id] = run
        run.task = asyncio.create_task(run.execute())
        return run

    def get(self, run_id: str) -> LiveRun:
        if run_id not in self.runs:
            raise KeyError(run_id)
        return self.runs[run_id]
