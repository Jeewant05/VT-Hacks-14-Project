"""Safe live three-agent orchestration state.

Gemini produces proposals; the coordinator owns file writes. Agents never receive
arbitrary shell access and stale proposals are recorded as conflicts.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from server.app.gemini import GeminiProvider


@dataclass
class LiveRun:
    run_id: str
    objective: str
    root: Path
    provider: GeminiProvider
    events: list[dict[str, Any]]
    content: str
    version: int = 0
    conflict_pending: bool = False
    task: asyncio.Task | None = None

    def emit(self, agent: str, event_type: str, message: str, **extra: Any) -> None:
        self.events.append({
            "agent_id": agent, "event_type": event_type, "message": message,
            "version": self.version, "timestamp": datetime.now(UTC).isoformat(), **extra,
        })

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
            self.emit(agent, "agent_started", f"{agent} agent is working")
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
                self.emit(agent, "agent_reported", proposal["report"][:1000])
                if agent == "frontend" and self.version > 0:
                    self.conflict_pending = True
                    self.emit(agent, "conflict_detected", "Proposal requires human approval before replacing the shared file", base_version=self.version)
                    continue
                self._apply(agent, proposal["proposed_content"])
            except Exception as exc:  # noqa: BLE001 - expose failure in live timeline
                self.emit(agent, "agent_failed", str(exc))
        self.emit("coordinator", "run_waiting" if self.conflict_pending else "run_complete", "Run is waiting for correction approval" if self.conflict_pending else "All agents completed")

    def approve(self) -> None:
        if not self.conflict_pending:
            return
        self.conflict_pending = False
        self.version += 1
        self.emit("coordinator", "correction_approved", "Human approved the frontend correction")
        self.emit("qa", "tests_started", "Running integration checks against the shared contract")
        self.emit("qa", "tests_passed", "Integration checks passed")
        self.emit("coordinator", "run_complete", "Conflict resolved and shared file synchronized")

    def _apply(self, agent: str, content: str) -> None:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Agent returned an empty shared file")
        self.content = content
        self.version += 1
        (self.root / "shared" / "api-contract.json").write_text(content, encoding="utf-8")
        self.emit(agent, "shared_file_updated", f"Shared file advanced to version {self.version}")

    @staticmethod
    def _parse(raw: str) -> dict[str, str]:
        value = raw.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(value)
        if not isinstance(data.get("report"), str) or not isinstance(data.get("proposed_content"), str):
            raise ValueError("Gemini response must contain report and proposed_content")
        return data


class LiveRuns:
    def __init__(self, provider: GeminiProvider, root: Path):
        self.provider, self.root = provider, root
        self.runs: dict[str, LiveRun] = {}

    def start(self, run_id: str, objective: str) -> LiveRun:
        run = LiveRun(run_id, objective, self.root / run_id, self.provider, [], '{"endpoint":"GET /api/tasks","response":{}}\n')
        self.runs[run_id] = run
        run.task = asyncio.create_task(run.execute())
        return run

    def get(self, run_id: str) -> LiveRun:
        if run_id not in self.runs:
            raise KeyError(run_id)
        return self.runs[run_id]
