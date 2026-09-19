"""Three-agent shared-file rehearsal powered by Gemini.

The runner is deliberately conservative: agents propose edits to one shared file,
and the coordinator applies them one at a time. A stale version is a visible
conflict instead of an overwrite. This is the backend foundation for the live UI.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from server.app.gemini import GeminiProvider


@dataclass
class SharedFile:
    path: Path
    content: str
    version: int = 0
    updated_by: str = "coordinator"


@dataclass
class AgentEvent:
    agent_id: str
    event_type: str
    message: str
    version: int
    timestamp: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "message": self.message,
            "version": self.version,
            "timestamp": self.timestamp,
        }


class LiveAgentRunner:
    """Run three role-specific Gemini sessions against one coordinated file."""

    def __init__(self, provider: GeminiProvider, root: Path):
        self.provider = provider
        self.root = root
        self.events: list[AgentEvent] = []
        self.shared = SharedFile(
            root / "shared" / "api-contract.json",
            '{"endpoint":"GET /api/tasks","response":{"id":"string","title":"string","completed":"boolean"}}\n',
        )

    def _event(self, agent: str, kind: str, message: str) -> None:
        self.events.append(
            AgentEvent(agent, kind, message, self.shared.version, datetime.now(UTC).isoformat())
        )

    async def run(self, objective: str) -> list[dict[str, str | int]]:
        self.shared.path.parent.mkdir(parents=True, exist_ok=True)
        self.shared.path.write_text(self.shared.content, encoding="utf-8")
        roles = [
            ("backend", "Implement the API and make the shared contract authoritative."),
            ("frontend", "Build the UI against the current shared contract; report mismatches."),
            ("qa", "Review the shared contract and describe integration tests and failures."),
        ]
        for agent, role in roles:
            self._event(agent, "agent_started", f"{agent} agent started: {role}")
            prompt = (
                f"You are the {agent} agent. {role}\nObjective: {objective}\n"
                f"Shared file (version {self.shared.version}):\n{self.shared.content}\n"
                "Do not invent a conversation with other agents. Return a concise report "
                "of the files or contract changes you propose."
            )
            report = await self.provider.generate(prompt)
            self._event(agent, "agent_reported", report[:800])
            self.shared.version += 1
            self.shared.updated_by = agent
            self.shared.path.write_text(self.shared.content, encoding="utf-8")
            self._event(agent, "shared_file_updated", f"Shared file advanced to version {self.shared.version}")
        self._event("coordinator", "run_complete", "Three agents completed a coordinated rehearsal")
        return [event.as_dict() for event in self.events]
