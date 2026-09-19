import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getLiveConfig, getLiveRun, startLiveRun, subscribeLiveRun,
  type LiveArtifact, type LiveConfig, type LiveEvent, type LiveSnapshot,
} from './liveAgents';

type Props = { onSimulation: () => void };
const initialObjective = 'Build a small task manager with a FastAPI backend, React frontend, and contract tests.';
const roleIds = ['backend', 'frontend', 'integration'] as const;

export function LiveDashboard({ onSimulation }: Props) {
  const [objective, setObjective] = useState(initialObjective);
  const [config, setConfig] = useState<LiveConfig | null>(null);
  const [run, setRun] = useState<LiveSnapshot | null>(null);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [selectedPath, setSelectedPath] = useState('shared/api-contract.json');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    void getLiveConfig().then(setConfig).catch(cause => {
      setError(cause instanceof Error ? cause.message : 'Could not load Gemini configuration.');
    });
    return () => sourceRef.current?.close();
  }, []);

  const artifacts = run?.artifacts ?? [];
  const selected = artifacts.find(item => item.path === selectedPath) ?? artifacts[0];
  const roleStatus = useMemo(() => Object.fromEntries(roleIds.map(role => {
    const roleEvents = events.filter(event => event.agent_id === role);
    const latest = roleEvents.at(-1)?.event_type;
    if (latest === 'file_committed') return [role, 'Committed'];
    if (latest === 'proposal_staged') return [role, 'Ready to commit'];
    if (latest === 'intention_ready') return [role, 'Intention ready'];
    if (latest === 'intention_started') return [role, 'Planning'];
    if (latest === 'agent_started' || latest === 'proposal_received') return [role, 'Building'];
    return [role, 'Waiting'];
  })), [events]);

  async function refresh(runId: string) {
    const snapshot = await getLiveRun(runId);
    setRun(snapshot);
    if (!selectedPath && snapshot.artifacts.length) setSelectedPath(snapshot.artifacts[0].path);
  }

  async function start() {
    setBusy(true); setError(''); setEvents([]); setRun(null); setSelectedPath('shared/api-contract.json');
    sourceRef.current?.close();
    try {
      const result = await startLiveRun(objective);
      await refresh(result.run_id);
      const source = subscribeLiveRun(result.run_id, event => {
        setEvents(current => [...current, event]);
        void refresh(result.run_id).catch(() => undefined);
        if (event.event_type === 'run_complete' || event.event_type === 'run_failed') source.close();
      });
      source.onerror = () => {
        source.close();
        void refresh(result.run_id).catch(() => undefined);
      };
      sourceRef.current = source;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start the Gemini agents.');
    } finally { setBusy(false); }
  }

  function reset() {
    sourceRef.current?.close(); setRun(null); setEvents([]); setError('');
    setSelectedPath('shared/api-contract.json');
  }

  return <main className="live-shell">
    <header className="live-header">
      <div><p className="eyebrow">SYNAPSE · GEMINI CODE LAB</p><h1>Three agents. One coordinated project.</h1><p>Frontend and backend build in parallel. The integration agent reviews both, then the coordinator validates every generated path before writing it.</p></div>
      <button className="secondary" onClick={onSimulation}>Open guided simulation</button>
    </header>

    <section className="prompt-card">
      <div className="prompt-heading"><div><label htmlFor="objective">Project objective</label><small>{config ? `${config.model} · ${config.configured ? 'ready' : 'setup required'}` : 'Checking configuration…'}</small></div>{run && <span className={`run-status status-${run.status}`}>{run.status}</span>}</div>
      <textarea id="objective" value={objective} maxLength={2000} onChange={event => setObjective(event.target.value)} disabled={busy || !!run} />
      <div className="prompt-actions"><button className="primary" onClick={start} disabled={busy || !!run || !config?.configured}>{busy ? 'Starting…' : 'Start three Gemini agents'}</button>{run && <button className="secondary" onClick={reset} disabled={run.status === 'planning' || run.status === 'building'}>New run</button>}<span>Generated code stays in an isolated local run directory.</span></div>
      {config && !config.configured && <div className="setup-note"><strong>Three Gemini APIs needed.</strong> Set <code>AGENT_PROVIDER=gemini</code> plus <code>GEMINI_BACKEND_API_KEY</code>, <code>GEMINI_FRONTEND_API_KEY</code>, and <code>GEMINI_INTEGRATION_API_KEY</code> in <code>.env</code>, then restart the API.</div>}
    </section>

    {error && <div className="error-card"><strong>Live run error</strong><pre>{error}</pre></div>}

    <section className="live-agent-grid">{roleIds.map(agent => {
      const details = config?.roles.find(role => role.id === agent);
      const count = artifacts.filter(item => item.agent_id === agent).length;
      return <article className={`agent-card-live state-${roleStatus[agent].toLowerCase().replaceAll(' ', '-')}`} key={agent}><div className="agent-dot" /><div><h2>{details?.title ?? agent}<span className={details?.configured ? 'api-ready' : 'api-missing'}>{details?.configured ? 'API ready' : 'API missing'}</span></h2><p>{details?.responsibility}</p>{run?.intentions[agent] && <blockquote className="agent-intention"><b>Intention</b>{run.intentions[agent]}</blockquote>}<small>{roleStatus[agent]}{count ? ` · ${count} file${count === 1 ? '' : 's'}` : ''}</small></div></article>;
    })}</section>

    <section className="live-workspace">
      <div className="panel artifact-panel"><div className="panel-title"><h2>Generated project</h2><span>{artifacts.length} files</span></div><div className="artifact-browser"><nav>{artifacts.map(artifact => <ArtifactButton key={artifact.path} artifact={artifact} active={artifact.path === selected?.path} onClick={() => setSelectedPath(artifact.path)} />)}{!artifacts.length && <p className="empty">Files will appear as the agents finish.</p>}</nav><div className="artifact-preview"><div><b>{selected?.path ?? 'No file selected'}</b>{selected && <span>{selected.agent_id}</span>}</div><pre>{selected?.content ?? 'Start a run to generate a project.'}</pre></div></div></div>
      <div className="panel activity-panel-live"><div className="panel-title"><h2>Coordinator timeline</h2><span>{events.length} events</span></div><ol className="event-list">{events.map((event, index) => <li key={`${event.timestamp}-${index}`}><b>{event.agent_id}</b><span>{event.event_type.replaceAll('_', ' ')}</span><p>{event.message}</p></li>)}{!events.length && <li className="empty">Agent activity will stream here in real time.</li>}</ol></div>
    </section>
  </main>;
}

function ArtifactButton({ artifact, active, onClick }: { artifact: LiveArtifact; active: boolean; onClick: () => void }) {
  return <button className={active ? 'active' : ''} onClick={onClick}><span>{artifact.path}</span><small>{artifact.agent_id}</small></button>;
}
