export type LiveEvent = {
  agent_id: string;
  event_type: string;
  message: string;
  timestamp: string;
  path?: string;
};

export type LiveArtifact = { path: string; agent_id: string; content: string };
export type LiveSnapshot = {
  run_id: string;
  objective: string;
  status: 'queued' | 'planning' | 'building' | 'complete' | 'failed';
  artifacts: LiveArtifact[];
  intentions: Record<string, string>;
  reports: Record<string, string>;
};
export type LiveConfig = {
  configured: boolean;
  model: string;
  roles: { id: string; title: string; responsibility: string; configured: boolean }[];
};

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export async function getLiveConfig(): Promise<LiveConfig> {
  return json(await fetch('/api/live/config'));
}

export async function startLiveRun(objective: string): Promise<{ run_id: string; status: string }> {
  return json(await fetch('/api/live/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ objective }),
  }));
}

export async function getLiveRun(runId: string): Promise<LiveSnapshot> {
  return json(await fetch(`/api/live/runs/${runId}`));
}

export function subscribeLiveRun(runId: string, onEvent: (event: LiveEvent) => void): EventSource {
  const source = new EventSource(`/api/live/runs/${runId}/events`);
  source.onmessage = event => onEvent(JSON.parse(event.data) as LiveEvent);
  return source;
}
