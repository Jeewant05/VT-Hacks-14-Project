import { useEffect, useMemo, useState } from 'react';
import { approveLiveRun, getLiveFile, startLiveRun, subscribeLiveRun, type LiveEvent } from './liveAgents';

type Props = { onSimulation: () => void };
const initialObjective = 'Build a task-management application with a shared API contract.';

export function LiveDashboard({ onSimulation }: Props) {
  const [objective, setObjective] = useState(initialObjective);
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [file, setFile] = useState({ version: 0, content: '', conflict_pending: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const status = useMemo(() => {
    const result: Record<string, string> = { backend: 'Waiting', frontend: 'Waiting', qa: 'Waiting' };
    for (const event of events) {
      if (event.event_type === 'agent_started') result[event.agent_id] = 'Working';
      if (event.event_type === 'conflict_detected') result[event.agent_id] = 'Blocked';
      if (event.event_type === 'tests_passed') result[event.agent_id] = 'Tests passed';
      if (event.event_type === 'shared_file_updated') result[event.agent_id] = 'Updated shared file';
    }
    return result;
  }, [events]);

  async function start() {
    setBusy(true); setError(''); setEvents([]); setFile({ version: 0, content: '', conflict_pending: false });
    try {
      const result = await startLiveRun(objective);
      setRunId(result.run_id);
      const source = subscribeLiveRun(result.run_id, event => {
        setEvents(current => [...current, event]);
        void getLiveFile(result.run_id).then(setFile).catch(() => undefined);
      });
      source.onerror = () => source.close();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start live run.');
    } finally { setBusy(false); }
  }

  async function approve() {
    if (!runId) return;
    try { await approveLiveRun(runId); setFile(await getLiveFile(runId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not approve correction.'); }
  }

  return <main className="live-shell">
    <header className="live-header"><div><p className="eyebrow">SYNAPSE · LIVE MODE</p><h1>Three agents. One shared file.</h1><p>Gemini agents propose real changes while the coordinator serializes edits and exposes conflicts.</p></div><button className="secondary" onClick={onSimulation}>Open simulation</button></header>
    <section className="prompt-card"><label htmlFor="objective">Project prompt</label><textarea id="objective" value={objective} onChange={event => setObjective(event.target.value)} disabled={busy || !!runId} /><button className="primary" onClick={start} disabled={busy || !!runId}>{busy ? 'Starting…' : 'Start Gemini agents'}</button></section>
    {error && <div className="error-card"><strong>Live run error</strong><pre>{error}</pre><span>Check that the API is running and GEMINI_API_KEY is configured on the server.</span></div>}
    <section className="agent-grid">{(['backend', 'frontend', 'qa'] as const).map(agent => <article className={`agent-card-live ${status[agent] === 'Blocked' ? 'blocked' : ''}`} key={agent}><div className="agent-dot" /><div><h2>{agent === 'qa' ? 'QA / Integration' : `${agent[0].toUpperCase()}${agent.slice(1)} agent`}</h2><p>{status[agent]}</p></div></article>)}</section>
    <section className="live-grid"><div className="panel"><div className="panel-title"><h2>Shared file</h2><span>api-contract.json · v{file.version}</span></div><pre className="shared-file">{file.content || 'Start a run to create the shared contract.'}</pre>{file.conflict_pending && <div className="conflict-card"><strong>Conflict requires approval</strong><p>The frontend proposal is based on the latest shared file. Review the event timeline, then approve the correction.</p><button className="primary" onClick={approve}>Approve correction</button></div>}</div><div className="panel"><div className="panel-title"><h2>Live activity</h2><span>{events.length} events</span></div><ol className="event-list">{events.map((event, index) => <li key={`${event.timestamp}-${index}`}><b>{event.agent_id}</b><span>{event.event_type}</span><p>{event.message}</p><small>shared version {event.version}</small></li>)}{!events.length && <li className="empty">Agent activity will appear here in real time.</li>}</ol></div></section>
  </main>;
}
