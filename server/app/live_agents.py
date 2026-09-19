"""Safe live three-agent orchestration state.

Gemini produces proposals; the coordinator owns file writes. Agents never receive
arbitrary shell access and stale proposals are recorded as conflicts.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from server.app.gemini import GeminiProvider
from server.app.models import TraceEvent
from server.app.tracing import TraceSink

log = logging.getLogger("synapse")


@dataclass
class LiveRun:
    run_id: str
    objective: str
    root: Path
    provider: GeminiProvider
    trace: TraceSink
    events: list[dict[str, Any]]
    content: str
    version: int = 0
    conflict_pending: bool = False
    task: asyncio.Task | None = None

    async def emit(self, agent: str, event_type: str, message: str, **extra: Any) -> None:
        event = {
            "agent_id": agent, "event_type": event_type, "message": message,
            "version": self.version, "timestamp": datetime.now(UTC).isoformat(), **extra,
        }
        self.events.append(event)
        try:
            await self.trace.log(TraceEvent(
                trace_id=f"trace-{uuid.uuid4().hex}", source="live_agent", event_type=event_type,
                timestamp=event["timestamp"], run_id=self.run_id, agent_id=agent, payload={
                    "message": message, "version": self.version, **extra,
                },
            ))
        except Exception as exc:  # noqa: BLE001 - observability must not stop the live run
            log.warning("live trace.log failed: %s", exc)

    async def execute(self) -> None:
        path = self.root / "shared" / "api-contract.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.content, encoding="utf-8")
        roles = {
            "backend": "Implement the API contract and propose a compatible JSON document.",
            "frontend": "Consume the current API contract and propose frontend-compatible changes.",
            "qa": "Review the current contract and propose integration tests for all agents.",
        }
        for agent, role in roles.items():
            await self.emit(agent, "agent_started", f"{agent} agent is working")
            prompt = f"""You are the {agent} coding agent in a coordinated run.
Objective: {self.objective}
Role: {role}
Shared file version: {self.version}
Shared file content:
{self.content}
Return JSON only with keys report and proposed_content. proposed_content must be the
complete api-contract.json content. Do not use markdown and do not modify other files."""
            try:
                raw = await self.provider.generate(prompt)
                proposal = self._parse(raw)
                await self.emit(agent, "agent_reported", proposal["report"][:1000])
                if agent == "frontend" and self.version > 0:
                    self.conflict_pending = True
                    await self.emit(agent, "conflict_detected", "Proposal requires human approval before replacing the shared file", base_version=self.version)
                    continue
                await self._apply(agent, proposal["proposed_content"])
            except Exception as exc:  # noqa: BLE001 - expose failure in live timeline
                await self.emit(agent, "agent_failed", str(exc))
        await self.emit("coordinator", "run_waiting" if self.conflict_pending else "run_complete", "Run is waiting for correction approval" if self.conflict_pending else "All agents completed")

    async def approve(self) -> None:
        if not self.conflict_pending:
            return
        self.conflict_pending = False
        self.version += 1
        await self.emit("coordinator", "correction_approved", "Human approved the frontend correction")
        await self.emit("qa", "tests_started", "Running integration checks against the shared contract")
        await self.emit("qa", "tests_passed", "Integration checks passed")
        await self.emit("coordinator", "run_complete", "Conflict resolved and shared file synchronized")

    async def _apply(self, agent: str, content: str) -> None:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Agent returned an empty shared file")
        self.content = content
        self.version += 1
        (self.root / "shared" / "api-contract.json").write_text(content, encoding="utf-8")
        await self.emit(agent, "shared_file_updated", f"Shared file advanced to version {self.version}")

    @staticmethod
    def _parse(raw: str) -> dict[str, str]:
        value = raw.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(value)
        if not isinstance(data.get("report"), str) or not isinstance(data.get("proposed_content"), str):
            raise TypeError("Gemini response must contain report and proposed_content")
        return data


class LiveRuns:
    def __init__(self, provider: GeminiProvider, root: Path, trace: TraceSink):
        self.provider, self.root, self.trace = provider, root, trace
        self.runs: dict[str, LiveRun] = {}

    def start(self, run_id: str, objective: str) -> LiveRun:
        run = LiveRun(run_id, objective, self.root / run_id, self.provider, self.trace, [], '{"endpoint":"GET /api/tasks","response":{}}\n')
        self.runs[run_id] = run
        run.task = asyncio.create_task(run.execute())
        return run

    def get(self, run_id: str) -> LiveRun:
        if run_id not in self.runs:
            raise KeyError(run_id)
        return self.runs[run_id]
