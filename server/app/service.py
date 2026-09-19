"""Coordinator transitions. Owner: P1.

Every public method: lock -> read_state -> mutate -> append Event -> write_state -> memory.log.
Fixed rules only. No LLM.
"""

import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from server.app.adapters import IdentityAdapter, MemoryAdapter
from server.app.coordinator import find_conflicts
from server.app.models import (
    ApiContract,
    ChangeSet,
    Conflict,
    Event,
    WorkspaceState,
    Workstream,
)
from server.app.store import read_state, write_state

# Event type strings. P2's UI and agents key off these. Do not rename after 2:30 PM.
AGENT_JOINED = "agent_joined"
AGENT_REJECTED = "agent_rejected"
WORKSTREAM_CLAIMED = "workstream_claimed"
CONTRACT_DECLARED = "contract_declared"
CONFLICT_OPENED = "conflict_opened"
CONFLICT_RESOLVED = "conflict_resolved"
CHANGESET_SUBMITTED = "changeset_submitted"
CHANGESET_REJECTED = "changeset_rejected"
WORKSTREAM_COMPLETED = "workstream_completed"
OBJECTIVE_COMPLETED = "objective_completed"


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


class Blocked(Exception):
    pass


log = logging.getLogger("synapse")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Coordinator:
    def __init__(self, db_path: Path, identity: IdentityAdapter, memory: MemoryAdapter):
        self.db_path = db_path
        self.identity = identity
        self.memory = memory
        self._lock = threading.Lock()

    # ---------- helpers ----------

    def _ws(self, state: WorkspaceState, ws_id: str) -> Workstream:
        for ws in state.workstreams:
            if ws.id == ws_id:
                return ws
        raise NotFound(f"workstream {ws_id}")

    async def _emit(self, state: WorkspaceState, event_type: str, ws_id: str | None,
                    agent_id: str | None, payload: dict | None = None) -> Event:
        event = Event(
            event_id=f"evt-{uuid.uuid4().hex[:8]}",
            objective_id=state.objective.id if state.objective else "none",
            workstream_id=ws_id,
            agent_id=agent_id,
            event_type=event_type,
            payload=payload or {},
            timestamp=_now(),
        )
        state.events.append(event)
        try:
            await self.memory.log(event)
        except Exception as exc:  # noqa: BLE001 - memory must never stall the demo
            log.warning("memory.log failed: %s", exc)
        return event

    def _open_conflicts_for(self, state: WorkspaceState, ws_id: str) -> list[Conflict]:
        return [c for c in state.conflicts if c.status == "open" and ws_id in c.workstream_ids]

    async def _recompute_conflicts(self, state: WorkspaceState, actor: str | None) -> None:
        """Diff current conflicts against the rules. Open new ones, resolve stale ones."""
        current = {c.id: c for c in find_conflicts(state.workstreams)}
        existing = {c.id: c for c in state.conflicts}

        for cid, conflict in current.items():
            if cid in existing and existing[cid].status == "open":
                continue
            if conflict.type == "contract":
                await self._attach_decision(conflict)
            state.conflicts = [c for c in state.conflicts if c.id != cid]
            state.conflicts.append(conflict)
            await self._emit(state, CONFLICT_OPENED, None, actor, {
                "conflict_id": cid, "type": conflict.type,
                "conflicting_field": conflict.conflicting_field,
                "decision_id": conflict.decision_id,
                "workstream_ids": conflict.workstream_ids,
            })

        for cid, conflict in existing.items():
            if conflict.status == "open" and cid not in current:
                conflict.status = "resolved"
                await self._emit(state, CONFLICT_RESOLVED, None, actor, {"conflict_id": cid})

        blocked = {wid for c in state.conflicts if c.status == "open" for wid in c.workstream_ids}
        for ws in state.workstreams:
            if ws.status == "complete":
                continue
            if ws.id in blocked:
                ws.status = "blocked"
            elif ws.status == "blocked":
                ws.status = "active"

    async def _attach_decision(self, conflict: Conflict) -> None:
        """Databricks hook. P3 replaces the adapter; this call stays the same."""
        try:
            hits = await self.memory.search(f"{conflict.explanation} {conflict.conflicting_field}")
        except Exception as exc:  # noqa: BLE001 - memory must never stall the demo
            log.warning("memory.search failed: %s", exc)
            hits = []
        if hits:
            d = hits[0]
            conflict.decision_id = d.decision_id
            conflict.recommendation = (
                f"Per decision {d.decision_id} ({d.title}): {d.content} "
                + conflict.recommendation
            )

    # ---------- transitions ----------

    async def join(self, agent_id: str) -> WorkspaceState:
        with self._lock:
            state = read_state(self.db_path)
            agent = next((a for a in state.agents if a.id == agent_id), None)
            if agent is None:
                raise NotFound(f"agent {agent_id}")
            result = await self.identity.verify(agent)
            agent.verified = result.verified
            if not result.verified:
                await self._emit(state, AGENT_REJECTED, None, agent_id,
                                 {"source": result.source, "evidence": result.evidence})
                write_state(self.db_path, state)
                raise Forbidden(result.evidence)
            await self._emit(state, AGENT_JOINED, None, agent_id,
                             {"source": result.source, "evidence": result.evidence,
                              "ans_name": agent.ans_name})
            write_state(self.db_path, state)
            return state

    async def claim(self, ws_id: str, agent_id: str) -> WorkspaceState:
        with self._lock:
            state = read_state(self.db_path)
            ws = self._ws(state, ws_id)
            agent = next((a for a in state.agents if a.id == agent_id), None)
            if agent is None or not agent.verified:
                raise Forbidden(f"{agent_id} is not a verified agent")
            if ws.agent_id != agent_id:
                raise Forbidden(f"{ws_id} is assigned to {ws.agent_id}")
            if ws.status == "pending":
                ws.status = "active"
            await self._emit(state, WORKSTREAM_CLAIMED, ws_id, agent_id,
                             {"owned_paths": ws.owned_paths, "depends_on": ws.depends_on})
            write_state(self.db_path, state)
            return state

    async def declare(self, ws_id: str, agent_id: str, contract: ApiContract) -> WorkspaceState:
        with self._lock:
            state = read_state(self.db_path)
            ws = self._ws(state, ws_id)
            if ws.agent_id != agent_id:
                raise Forbidden(f"{ws_id} is assigned to {ws.agent_id}")
            ws.contract = contract
            if ws.status == "pending":
                ws.status = "active"
            await self._emit(state, CONTRACT_DECLARED, ws_id, agent_id, contract.model_dump())
            await self._recompute_conflicts(state, agent_id)
            write_state(self.db_path, state)
            return state

    async def submit(self, ws_id: str, changeset: ChangeSet) -> WorkspaceState:
        with self._lock:
            state = read_state(self.db_path)
            ws = self._ws(state, ws_id)
            if changeset.agent_id != ws.agent_id:
                raise Forbidden(f"{ws_id} is assigned to {ws.agent_id}")
            open_conflicts = self._open_conflicts_for(state, ws_id)
            if open_conflicts:
                await self._emit(state, CHANGESET_REJECTED, ws_id, changeset.agent_id,
                                 {"changeset_id": changeset.id,
                                  "open_conflicts": [c.id for c in open_conflicts]})
                write_state(self.db_path, state)
                raise Blocked(f"open conflicts: {[c.id for c in open_conflicts]}")
            if changeset.contract != ws.contract:
                await self._emit(state, CHANGESET_REJECTED, ws_id, changeset.agent_id,
                                 {"changeset_id": changeset.id,
                                  "reason": "contract differs from declared"})
                write_state(self.db_path, state)
                raise Blocked("changeset contract differs from the declared contract")
            ws.latest_changeset = changeset
            ws.status = "complete"
            await self._emit(state, CHANGESET_SUBMITTED, ws_id, changeset.agent_id, {
                "changeset_id": changeset.id, "files": changeset.files,
                "tests": [t.model_dump() for t in changeset.tests],
            })
            await self._emit(state, WORKSTREAM_COMPLETED, ws_id, changeset.agent_id, {})
            if state.objective and all(w.status == "complete" for w in state.workstreams):
                state.objective.status = "complete"
                await self._emit(state, OBJECTIVE_COMPLETED, None, None,
                                 {"objective_id": state.objective.id})
            write_state(self.db_path, state)
            return state

    def reset(self, fresh: WorkspaceState) -> WorkspaceState:
        with self._lock:
            write_state(self.db_path, fresh)
            return fresh
