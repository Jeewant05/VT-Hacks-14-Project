import { useEffect, useState } from 'react';
import type { components } from './api.generated';

export type BackendState = components['schemas']['WorkspaceState'];
export type BackendHealth = components['schemas']['Health'];

export function useBackend() {
  const [data, setData] = useState<{ health: BackendHealth; state: BackendState } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let active: AbortController | null = null;
    async function poll() {
      active = new AbortController();
      const timeout = setTimeout(() => active?.abort(), 4500);
      try {
        const responses = await Promise.all(['/health', '/state'].map(path => fetch(`/api${path}`, { signal: active!.signal })));
        if (responses.some(response => !response.ok)) throw new Error('The backend did not return a valid workspace.');
        const [health, state] = await Promise.all(responses.map(response => response.json())) as [BackendHealth, BackendState];
        if (health.status !== 'ok' || !Array.isArray(state.workstreams)) throw new Error('Unexpected workspace response.');
        if (!disposed) { setData({ health, state }); setError(null); setUpdatedAt(new Date()); }
      } catch {
        if (!disposed) setError('The local backend is unavailable. The interactive demo still works.');
      } finally {
        clearTimeout(timeout);
        if (!disposed) timer = setTimeout(poll, 5000);
      }
    }
    void poll();
    return () => { disposed = true; active?.abort(); clearTimeout(timer); };
  }, [attempt]);

  return { data, error, updatedAt, retry: () => setAttempt(value => value + 1) };
}
