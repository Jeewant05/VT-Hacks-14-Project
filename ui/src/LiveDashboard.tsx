import { useEffect, useMemo, useRef, useState } from 'react';
import {
  getLiveConfig, getLiveRun, startLiveRun, subscribeLiveRun,
  type LiveArtifact, type LiveConfig, type LiveEvent, type LiveSnapshot,
} from './liveAgents';
import { Logo } from './components';

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
  const [previewNotice, setPreviewNotice] = useState('');
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    void getLiveConfig().then(setConfig).catch(cause => {
      setError(cause instanceof Error ? cause.message : 'Could not load agent configuration.');
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
    return snapshot;
  }

  function preparePreviewTab() {
    const tab = window.open('', '_blank');
    if (!tab) {
      setPreviewNotice('Your browser blocked the preview tab. You can open it after the run finishes.');
      return null;
    }
    tab.opener = null;
    tab.document.title = 'Agents are building…';
    tab.document.body.style.cssText = 'margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f8f5;color:#20362b;font-family:system-ui,sans-serif';
    const panel = tab.document.createElement('div');
    panel.style.cssText = 'width:min(520px,calc(100% - 48px));padding:36px;border:1px solid #dbe7dc;border-radius:18px;background:white;box-shadow:0 18px 60px #23452b18';
    const label = tab.document.createElement('p');
    label.textContent = 'SYNAPSE · LIVE BUILD';
    label.style.cssText = 'color:#247457;font-size:12px;font-weight:800;letter-spacing:.14em';
    const heading = tab.document.createElement('h1');
    heading.textContent = 'Three agents are building your app.';
    const copy = tab.document.createElement('p');
    copy.textContent = 'This tab will automatically switch to the finished work after intentions, code, and the preview are validated.';
    copy.style.cssText = 'color:#65776b;line-height:1.6';
    panel.append(label, heading, copy);
    tab.document.body.append(panel);
    return tab;
  }

  function finishPreview(snapshot: LiveSnapshot, tab: Window | null) {
    if (snapshot.status === 'complete' && snapshot.preview_url) {
      if (tab && !tab.closed) tab.location.replace(snapshot.preview_url);
      setPreviewNotice(tab ? 'Finished app opened in the preview tab.' : 'Finished app is ready to open.');
    } else if (snapshot.status === 'failed') {
      if (tab && !tab.closed) {
        tab.document.title = 'Agent build failed';
        const heading = tab.document.querySelector('h1');
        const copy = tab.document.querySelector('div > p:last-child');
        if (heading) heading.textContent = 'The build did not pass validation.';
        if (copy) copy.textContent = 'Return to the Synapse dashboard to inspect the coordinator timeline.';
      }
      setPreviewNotice('The preview was not published because the agent build failed validation.');
    }
  }

  async function start() {
    setPreviewNotice('');
    const previewTab = preparePreviewTab();
    setBusy(true); setError(''); setEvents([]); setRun(null); setSelectedPath('shared/api-contract.json');
    sourceRef.current?.close();
    try {
      const result = await startLiveRun(objective);
      await refresh(result.run_id);
      const source = subscribeLiveRun(result.run_id, event => {
        setEvents(current => [...current, event]);
        void refresh(result.run_id).catch(() => undefined);
        if (event.event_type === 'run_complete' || event.event_type === 'run_failed') {
          source.close();
          void refresh(result.run_id).then(snapshot => finishPreview(snapshot, previewTab)).catch(() => undefined);
        }
      });
      source.onerror = () => {
        source.close();
        void refresh(result.run_id).then(snapshot => finishPreview(snapshot, previewTab)).catch(() => undefined);
      };
      sourceRef.current = source;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not start the coding agents.');
      if (previewTab && !previewTab.closed) previewTab.close();
    } finally { setBusy(false); }
  }

  function reset() {
    sourceRef.current?.close(); setRun(null); setEvents([]); setError(''); setPreviewNotice('');
    setSelectedPath('shared/api-contract.json');
  }

  function openFinishedPreview() {
    if (run?.preview_url) window.open(run.preview_url, '_blank', 'noopener,noreferrer');
  }

  return <main className="live-shell">
    <header className="live-header">
      <div><Logo /><p className="eyebrow">SYNAPSE · OPEN MODEL CODE LAB</p><h1>Three agents. One coordinated project.</h1><p>Frontend and backend build in parallel. The integration agent reviews both, then the coordinator validates every generated path before writing it.</p></div>
      <button className="secondary" onClick={onSimulation}>Open guided simulation</button>
    </header>

    <section className="prompt-card">
      <div className="prompt-heading"><div><label htmlFor="objective">Project objective</label><small>{config ? `3 role providers · ${config.configured ? 'ready' : 'setup required'}` : 'Checking configuration…'}</small></div>{run && <span className={`run-status status-${run.status}`}>{run.status}</span>}</div>
      <textarea id="objective" value={objective} maxLength={2000} onChange={event => setObjective(event.target.value)} disabled={busy || !!run} />
      <div className="prompt-actions"><button className="primary" onClick={start} disabled={busy || !!run || !config?.configured}>{busy ? 'Starting…' : 'Start three coding agents'}</button>{run?.preview_url && <button className="secondary" onClick={openFinishedPreview}>Open finished app</button>}{run && <button className="secondary" onClick={reset} disabled={run.status === 'planning' || run.status === 'building'}>New run</button>}<span>Generated code stays in an isolated local run directory.</span></div>
      {previewNotice && <p className="preview-notice">{previewNotice}</p>}
      {config && !config.configured && <div className="setup-note"><strong>Three agent APIs needed.</strong> Set <code>BACKEND_PROVIDER</code>, <code>FRONTEND_PROVIDER</code>, and <code>QA_PROVIDER</code>, plus the matching API keys in <code>.env</code>, then restart the API.</div>}
    </section>

    {error && <div className="error-card"><strong>Live run error</strong><pre>{error}</pre></div>}

    <section className="live-agent-grid">{roleIds.map(agent => {
      const details = config?.roles.find(role => role.id === agent);
      const count = artifacts.filter(item => item.agent_id === agent).length;
      return <article className={`agent-card-live state-${roleStatus[agent].toLowerCase().replaceAll(' ', '-')}`} key={agent}><div className="agent-dot" /><div><h2>{details?.title ?? agent}<span className={details?.configured ? 'api-ready' : 'api-missing'}>{details?.configured ? 'API ready' : 'API missing'}</span></h2><p>{details?.responsibility}</p>{details?.configured && <p className="agent-provider">{details.provider} · {details.model}</p>}{run?.intentions[agent] && <blockquote className="agent-intention"><b>Intention</b>{run.intentions[agent]}</blockquote>}<small>{roleStatus[agent]}{count ? ` · ${count} file${count === 1 ? '' : 's'}` : ''}</small></div></article>;
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
