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
  preview_url: string | null;
};
export type LiveConfig = {
  configured: boolean;
  model: string;
  roles: {
    id: string;
    title: string;
    responsibility: string;
    configured: boolean;
    provider: string | null;
    model: string | null;
  }[];
};

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export async function getLiveConfig(): Promise<LiveConfig> {
  return json(await fetch('/api/live/config'));
}

/** Operator secret for billable endpoints, shared with the coordinator hooks. */
function demoToken(): string | null {
  try {
    const held = sessionStorage.getItem('synapse-demo-token');
    if (held) return held;
    const entered = window.prompt('Demo token (set as DEMO_TOKEN on the server)');
    if (entered) sessionStorage.setItem('synapse-demo-token', entered);
    return entered;
  } catch {
    return null; // Blocked storage: let the server reject it instead.
  }
}

export async function startLiveRun(objective: string): Promise<{ run_id: string; status: string }> {
  // Starting a run spends provider credit, so the server requires the token.
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = demoToken();
  if (token) headers['X-Demo-Token'] = token;
  return json(await fetch('/api/live/runs', {
    method: 'POST',
    headers,
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
