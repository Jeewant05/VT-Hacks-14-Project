"""Utilities for connecting the live-agent UI to the coordinator."""

export type LiveEvent = {
  agent_id: string;
  event_type: string;
  message: string;
  version: number;
  timestamp: string;
  base_version?: number;
};

export type LiveFile = { version: number; content: string; conflict_pending: boolean };

export async function startLiveRun(objective: string): Promise<{ run_id: string; status: string }> {
  const response = await fetch('/api/live/runs', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ objective }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export function subscribeLiveRun(runId: string, onEvent: (event: LiveEvent) => void): EventSource {
  const source = new EventSource(`/api/live/runs/${runId}/events`);
  source.onmessage = event => onEvent(JSON.parse(event.data) as LiveEvent);
  return source;
}

export async function approveLiveRun(runId: string): Promise<void> {
  const response = await fetch(`/api/live/runs/${runId}/approve`, { method: 'POST' });
  if (!response.ok) throw new Error(await response.text());
}

export async function getLiveFile(runId: string): Promise<LiveFile> {
  const response = await fetch(`/api/live/runs/${runId}/file`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
