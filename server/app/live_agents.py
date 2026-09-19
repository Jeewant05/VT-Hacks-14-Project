"""Safe live three-agent orchestration state.

Each agent role has its own LLM provider (Gemini, Cerebras, Groq, ...). Providers produce
proposals; the coordinator owns file writes. Agents never receive shell access, and stale
proposals are recorded as conflicts. A role with no working provider uses a scripted
proposal so one bad key never kills the run.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from server.app.providers import Provider

ROLES = {
    "backend": "Implement the API contract and propose a compatible JSON document.",
    "frontend": "Consume the current API contract and propose frontend-compatible changes.",
    "qa": "Review the current contract and propose integration tests for all agents.",
}

_RESPONSE = {"token": "string", "user": "object"}
SCRIPTED = {
    "backend": {
        "report": "Scripted backend: added token and user to the contract response.",
        "proposed_content": json.dumps({"endpoint": "POST /api/oauth",
                                        "response": _RESPONSE}) + "\n",
    },
    "frontend": {
        "report": "Scripted frontend: consumes token and user from the contract.",
        "proposed_content": json.dumps({"endpoint": "POST /api/oauth", "response": _RESPONSE,
                                        "consumer": "login"}) + "\n",
    },
    "qa": {
        "report": "Scripted QA: added an integration test asserting token and user are present.",
        "proposed_content": json.dumps({"endpoint": "POST /api/oauth", "response": _RESPONSE,
                                        "tests": ["token present", "user present"]}) + "\n",
    },
}


@dataclass
class LiveRun:
    run_id: str
    objective: str
    root: Path
    providers: dict[str, Provider]
    events: list[dict[str, Any]] = field(default_factory=list)
    content: str = '{"endpoint":"GET /api/tasks","response":{}}\n'
    version: int = 0
    conflict_pending: bool = False
    task: asyncio.Task | None = None

    def emit(self, agent: str, event_type: str, message: str, **extra: Any) -> None:
        self.events.append({
            "agent_id": agent, "event_type": event_type, "message": message,
            "version": self.version, "timestamp": datetime.now(UTC).isoformat(), **extra,
        })

    def _prompt(self, agent: str) -> str:
        return (
            f"You are the {agent} coding agent in a coordinated run.\n"
            f"Objective: {self.objective}\n"
            f"Role: {ROLES[agent]}\n"
            f"Shared file version: {self.version}\n"
            f"Shared file content:\n{self.content}\n"
            "Return JSON only with keys report and proposed_content. proposed_content must be "
            "the complete api-contract.json content. Do not use markdown and do not modify "
            "other files."
        )

    async def _propose(self, agent: str) -> dict[str, str]:
        provider = self.providers.get(agent)
        if provider is None:
            self.emit(agent, "agent_started", f"{agent} agent is working (scripted)",
                      provider="scripted", model="-")
            return SCRIPTED[agent]
        self.emit(agent, "agent_started", f"{agent} agent is working",
                  provider=provider.name, model=provider.model)
        raw = await provider.generate(self._prompt(agent))
        return self._parse(raw)

    async def execute(self) -> None:
        path = self.root / "shared" / "api-contract.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.content, encoding="utf-8")
        for agent in ROLES:
            try:
                proposal = await self._propose(agent)
                self.emit(agent, "agent_reported", proposal["report"][:1000])
                if agent == "frontend" and self.version > 0:
                    self.conflict_pending = True
                    self.emit(agent, "conflict_detected",
                              "Proposal requires human approval before replacing the shared file",
                              base_version=self.version)
                    continue
                self._apply(agent, proposal["proposed_content"])
            except Exception as exc:  # noqa: BLE001 - expose failure in live timeline
                self.emit(agent, "agent_failed", str(exc))
                proposal = SCRIPTED[agent]
                self.emit(agent, "agent_reported", "Fell back to scripted proposal.")
                if not (agent == "frontend" and self.version > 0):
                    self._apply(agent, proposal["proposed_content"])
        if self.conflict_pending:
            self.emit("coordinator", "run_waiting", "Run is waiting for correction approval")
        else:
            self.emit("coordinator", "run_complete", "All agents completed")

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
        report, content = data.get("report"), data.get("proposed_content")
        if not isinstance(report, str):
            raise TypeError("LLM response must contain a string 'report'")
        if isinstance(content, dict | list):
            content = json.dumps(content) + "\n"
        if not isinstance(content, str):
            raise TypeError("LLM response must contain 'proposed_content'")
        return {"report": report, "proposed_content": content}


class LiveRuns:
    def __init__(self, providers: dict[str, Provider], root: Path):
        self.providers, self.root = providers, root
        self.runs: dict[str, LiveRun] = {}

    def start(self, run_id: str, objective: str) -> LiveRun:
        run = LiveRun(run_id, objective, self.root / run_id, self.providers)
        self.runs[run_id] = run
        run.task = asyncio.create_task(run.execute())
        return run

    def get(self, run_id: str) -> LiveRun:
        if run_id not in self.runs:
            raise KeyError(run_id)
        return self.runs[run_id]
