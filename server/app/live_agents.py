"""Bounded three-agent Gemini coding runs.

Gemini may propose files, but only this coordinator validates and writes them.
Generated projects live under ``.local/live-runs`` and never touch this repository.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Protocol


class TextProvider(Protocol):
    async def generate(self, prompt: str) -> str: ...


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
    provider: TextProvider
    events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
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
            "reports": self.reports,
        }

    async def execute(self) -> None:
        self.status = "running"
        self.root.mkdir(parents=True, exist_ok=False)
        self.emit("coordinator", "run_started", "Created an isolated project workspace")
        contract = self._contract()
        self._write(
            Artifact(
                path="shared/api-contract.json",
                agent_id="coordinator",
                content=json.dumps(contract, indent=2) + "\n",
            )
        )
        self.emit("coordinator", "contract_published", "Published the shared API contract")

        try:
            backend, frontend = await asyncio.gather(
                self._ask(ROLES[0], contract), self._ask(ROLES[1], contract)
            )
            self._apply(ROLES[0], backend)
            self._apply(ROLES[1], frontend)
            integration_context = {
                "contract": contract,
                "generated_files": [
                    {"path": item.path, "content": item.content[:8_000]}
                    for item in self.artifacts
                    if item.agent_id in {"backend", "frontend"}
                ],
            }
            integration = await self._ask(ROLES[2], integration_context)
            self._apply(ROLES[2], integration)
            self._validate_run()
        except Exception as exc:  # noqa: BLE001 - failures belong in the live timeline
            self.status = "failed"
            self.emit("coordinator", "run_failed", str(exc)[:1_000])
            return

        self.status = "complete"
        self.emit(
            "coordinator",
            "run_complete",
            f"Validated {len(self.artifacts)} generated files across three agents",
        )

    async def _ask(self, role: AgentRole, context: dict[str, Any]) -> dict[str, Any]:
        self.emit(role.id, "agent_started", f"{role.title} is generating its scoped changes")
        prompt = f"""You are the {role.title} in a coordinated coding demo.
Objective: {self.objective}
Responsibility: {role.responsibility}
You may create files only inside the `{role.allowed_root}/` directory.

Shared project context:
{json.dumps(context, indent=2)}

Return JSON only, without markdown fences, using this exact shape:
{{
  "report": "short explanation of the implementation",
  "files": [{{"path": "{role.allowed_root}/relative-name", "content": "complete file contents"}}]
}}
Create a small, coherent, runnable implementation. Do not include secrets, shell commands,
absolute paths, parent-directory traversal, or files outside your assigned directory.
"""
        raw = await self.provider.generate(prompt)
        proposal = self._parse(raw)
        self.emit(role.id, "proposal_received", proposal["report"][:1_000])
        return proposal

    def _apply(self, role: AgentRole, proposal: dict[str, Any]) -> None:
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
            if any(item.path == normalized.as_posix() for item in self.artifacts + pending):
                raise ValueError(f"duplicate generated path: {normalized.as_posix()}")
            pending.append(Artifact(normalized.as_posix(), role.id, content))

        if sum(len(item.content) for item in self.artifacts + pending) > MAX_TOTAL_CHARS:
            raise ValueError("generated project exceeds the run size limit")
        for artifact in pending:
            self._write(artifact)
            self.emit(role.id, "file_written", artifact.path, path=artifact.path)
        self.reports[role.id] = proposal["report"][:2_000]
        self.emit(role.id, "agent_complete", f"Created {len(pending)} scoped files")

    def _write(self, artifact: Artifact) -> None:
        destination = self.root.joinpath(*PurePosixPath(artifact.path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.content, encoding="utf-8")
        self.artifacts.append(artifact)

    def _validate_run(self) -> None:
        owners = {item.agent_id for item in self.artifacts}
        missing = {role.id for role in ROLES} - owners
        if missing:
            raise ValueError(f"missing deliverables from: {', '.join(sorted(missing))}")
        paths = [item.path for item in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("two agents proposed the same path")
        self.emit(
            "coordinator", "validation_passed", "Ownership, path, duplicate, and size checks passed"
        )

    @staticmethod
    def _contract() -> dict[str, Any]:
        return {
            "endpoint": "GET /api/items",
            "response": {"items": [{"id": "string", "title": "string", "done": "boolean"}]},
            "ownership": {role.id: f"{role.allowed_root}/**" for role in ROLES},
        }

    @staticmethod
    def _parse(raw: str) -> dict[str, Any]:
        value = raw.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(value)
        if not isinstance(data, dict):
            raise TypeError("Gemini response must be a JSON object")
        if not isinstance(data.get("report"), str) or not isinstance(data.get("files"), list):
            raise TypeError("Gemini response must contain report and files")
        return data


class LiveRuns:
    def __init__(self, provider: TextProvider | None, root: Path):
        self.provider, self.root = provider, root
        self.runs: dict[str, LiveRun] = {}

    @property
    def configured(self) -> bool:
        return self.provider is not None

    def start(self, objective: str) -> LiveRun:
        if self.provider is None:
            raise RuntimeError(
                "Gemini is not configured. Set AGENT_PROVIDER=gemini and GEMINI_API_KEY."
            )
        objective = objective.strip()
        if not objective:
            raise ValueError("objective cannot be empty")
        if len(objective) > MAX_OBJECTIVE_CHARS:
            raise ValueError(f"objective must be at most {MAX_OBJECTIVE_CHARS} characters")
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        run = LiveRun(run_id, objective, self.root / run_id, self.provider)
        self.runs[run_id] = run
        run.task = asyncio.create_task(run.execute())
        return run

    def get(self, run_id: str) -> LiveRun:
        if run_id not in self.runs:
            raise KeyError(run_id)
        return self.runs[run_id]
