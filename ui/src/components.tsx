import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { ArrowUpRight, Check, ChevronRight, Circle, FileCode2, GitBranch, LoaderCircle, ShieldCheck, X } from 'lucide-react';
import { demoFiles, demoTests, decisions, hasIdentity, isAligned, type DemoState, type Phase } from './demo';

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'green' | 'amber' | 'red' | 'blue' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Button({ children, variant = 'secondary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'quiet' }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>;
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return <span className="brand"><svg viewBox="0 0 32 32" aria-hidden="true" className="brand-mark"><path d="M7 8h12l6 8-6 8H7l6-8Z" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" /><path d="m7 8 12 16M19 8 7 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" /></svg>{!compact && <span>synapse<span className="brand-period">.</span></span>}</span>;
}

export type Inspector = { kind: 'identity' | 'decision' | 'contract' | 'tests' | 'scope' | 'guide'; id?: string } | null;

export function AgentCard({ role, phase, inspect }: { role: 'backend' | 'frontend'; phase: Phase; inspect: (value: Inspector) => void }) {
  const frontend = role === 'frontend';
  const known = hasIdentity(phase);
  const aligned = isAligned(phase);
  const blocked = frontend && ['conflict', 'correcting'].includes(phase);
  const status = phase === 'complete' ? 'Complete' : phase === 'ready' ? 'Waiting' : blocked ? 'Blocked' : phase === 'verifying' ? 'Joining' : 'Active';
  return <article className={`agent-card ${blocked ? 'agent-blocked' : ''}`}>
    <div className="agent-top"><div className={`agent-avatar ${frontend ? 'avatar-blue' : ''}`}><span>{frontend ? 'FE' : 'BE'}</span></div><div className="agent-name"><h3>{frontend ? 'Frontend agent' : 'Backend agent'}</h3><span>{frontend ? 'Organization login' : 'OAuth API'}</span></div><Badge tone={blocked ? 'amber' : phase === 'complete' ? 'green' : 'neutral'}><span className={`status-dot ${status.toLowerCase()}`} />{status}</Badge></div>
    <button className="identity-link" onClick={() => inspect({ kind: 'identity', id: role })}><ShieldCheck size={14} />{known ? 'Identity checked' : 'Identity pending'}<span className="source-tag">Demo</span><ChevronRight size={13} /></button>
    <div className="agent-details"><div><span className="field-label">Owned scope</span><button className="code-link" onClick={() => inspect({ kind: 'scope', id: role })}>{frontend ? 'src/components/login/**' : 'src/api/auth/**'}<ArrowUpRight size={13} /></button></div>
    <div><span className="field-label">{frontend ? 'Consumes' : 'Provides'}</span><code className="endpoint"><span>POST</span> /api/oauth</code></div>
    <div><span className="field-label">Response fields</span><div className={`field-chips ${blocked ? 'fields-conflict' : ''}`}><code>{frontend && !aligned ? 'accessToken' : 'token'}</code><code>{frontend && !aligned ? 'profile' : 'user'}</code>{aligned && <Check size={14} className="success-ink" />}</div></div></div>
    <footer className="agent-footer"><GitBranch size={13} /><span>{frontend ? 'Depends on Backend agent' : 'No upstream dependencies'}</span></footer>
  </article>;
}

export function FileList({ onSelect, selected, submitted = false }: { onSelect: (index: number) => void; selected?: number; submitted?: boolean }) {
  return <div className="file-list">{demoFiles.map((file, index) => <button key={file.path} className={`file-row ${selected === index ? 'selected' : ''}`} onClick={() => onSelect(index)}><FileCode2 size={17} /><span className="file-label"><strong>{file.path.split('/').at(-1)}</strong><span>{file.path.split('/').slice(0, -1).join('/')}</span></span><span className="file-owner">{file.owner}</span><Badge>{submitted ? 'Submitted' : 'Sample'}</Badge><ChevronRight size={14} /></button>)}</div>;
}

export function Diff({ index }: { index: number }) {
  const file = demoFiles[index];
  return <div className="diff-view"><div className="diff-header"><FileCode2 size={16} /><strong>{file.path}</strong></div><div className="diff-caption">Illustrative excerpt · Not a Git diff from your repository</div><pre className="diff-code" aria-label={`Illustrative changes for ${file.path}`}>{file.lines.map((line, index) => <span className={`diff-line diff-${line.kind}`} key={index}><span className="line-number">{index + 1}</span><span className="line-sign">{line.kind === 'add' ? '+' : line.kind === 'remove' ? '−' : ' '}</span><code>{line.text || ' '}</code></span>)}</pre><p className="diff-description">{file.description}</p></div>;
}

export function TestRows({ completed }: { completed: boolean }) {
  return <div className="test-list">{demoTests.map(test => <div className="test-row" key={test.name}>{completed ? <Check size={16} className="success-ink" /> : <Circle size={14} />}<span>{test.name}<small>{test.owner} · {completed ? 'Simulated agent report' : 'Not submitted'}</small></span><span className={completed ? 'success-ink' : 'muted'}>{completed ? 'Pass' : 'Pending'}</span></div>)}</div>;
}

export function InspectorDrawer({ value, onClose, demo }: { value: Inspector; onClose: () => void; demo: DemoState }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (value) dialog.current?.showModal();
    else dialog.current?.close();
  }, [value]);
  const decision = decisions.find(item => item.id === value?.id) ?? decisions[0];
  const title = value?.kind === 'identity' ? 'Agent identity' : value?.kind === 'decision' ? decision.title : value?.kind === 'scope' ? 'Scoped assignment' : value?.kind === 'tests' ? 'Validation results' : value?.kind === 'guide' ? 'The three-minute walkthrough' : 'Interface contract';
  return <dialog ref={dialog} className="inspector" onClose={onClose} onClick={event => { if (event.target === event.currentTarget) onClose(); }} aria-labelledby="inspector-title"><div className="drawer-body"><header className="drawer-header"><div><h2 id="inspector-title">{title}</h2></div><button className="icon-button" aria-label="Close evidence panel" onClick={onClose}><X size={20} /></button></header>
    <div className="drawer-notice"><Badge tone="amber">Demo evidence</Badge><p>These fixtures explain the flow. No live provider operation was performed.</p></div>
    {value?.kind === 'identity' && <><div className="evidence-icon"><ShieldCheck size={26} /></div><h3>{value.id === 'frontend' ? 'Frontend agent' : value.id === 'backend' ? 'Backend agent' : 'Backend & frontend agents'}</h3><dl className="detail-list"><div><dt>Verification state</dt><dd>{hasIdentity(demo.phase) ? 'Checked by demo fixture' : 'Awaiting demo check'}</dd></div><div><dt>Identity source</dt><dd>Local allowlist</dd></div><div><dt>Planned provider</dt><dd>GoDaddy ANS</dd></div><div><dt>Live ANS evidence</dt><dd>Not available</dd></div><div><dt>Payload signing</dt><dd>Outside MVP scope</dd></div></dl><p className="body-note">The live integration will resolve the registered identity and retain the response with its verification timestamp. Unknown identities must be blocked from submitting a ChangeSet.</p></>}
    {value?.kind === 'decision' && <><div className="section-heading"><Badge>{decision.id}</Badge><span className="muted">{decision.component}</span></div><p>{decision.content}</p><pre className="code-block">{decision.code}</pre><dl className="detail-list"><div><dt>Current source</dt><dd>Local demo fixture</dd></div><div><dt>Planned source</dt><dd>Databricks · synapse_decisions</dd></div><div><dt>Delivery</dt><dd>Shared with both workstreams</dd></div></dl><p className="body-note">In the live flow, this panel will show the retrieved decision and query evidence. The demo does not claim that a Databricks query succeeded.</p></>}
    {value?.kind === 'contract' && <><code className="endpoint large"><span>POST</span> /api/oauth</code><p>Backend owns the response. Frontend consumes the same interface.</p><div className="contract-detail"><h3>Approved response</h3><pre className="code-block">{'{\n  "token": "string",\n  "user": "object"\n}'}</pre><h3>Frontend declaration</h3><pre className={`code-block ${isAligned(demo.phase) ? '' : 'code-warning'}`}>{isAligned(demo.phase) ? '{\n  "token": "string",\n  "user": "object"\n}' : '{\n  "accessToken": "string",\n  "profile": "object"\n}'}</pre></div><p className="body-note">{isAligned(demo.phase) ? 'The demo frontend has redeclared the approved response.' : 'The field names are incompatible. Accept the correction, then wait for the frontend to redeclare.'}</p></>}
    {value?.kind === 'scope' && <><h3>{value.id === 'frontend' ? 'Frontend assignment' : 'Backend assignment'}</h3><dl className="detail-list"><div><dt>Objective</dt><dd>Organization-level OAuth login</dd></div><div><dt>Owned paths</dt><dd><code>{value.id === 'frontend' ? 'src/components/login/**' : 'src/api/auth/**'}</code></dd></div><div><dt>Restricted paths</dt><dd><code>{value.id === 'frontend' ? 'src/api/auth/**' : 'src/components/login/**'}</code></dd></div><div><dt>Dependency</dt><dd>{value.id === 'frontend' ? 'Backend response contract' : 'None'}</dd></div><div><dt>Relevant decision</dt><dd>ADR-001 · Authentication response</dd></div></dl><p className="body-note">An agent receives its assignment, permitted paths, dependencies, contract, and relevant project decisions.</p></>}
    {value?.kind === 'tests' && <><p>Sample test reports attached to the two demo manifests. These tests were not executed by Synapse.</p><TestRows completed={demo.phase === 'complete'} /></>}
    {value?.kind === 'guide' && <><p>One objective. Two agents. One incompatible assumption caught before merge.</p><ol className="guide-list"><li><strong>Start the agents</strong><p>Show assigned scopes and the labeled identity checks.</p></li><li><strong>Inspect the mismatch</strong><p>Backend provides token + user. Frontend expects accessToken + profile.</p></li><li><strong>Accept the correction</strong><p>Use the approved project decision and wait for redeclaration.</p></li><li><strong>Review the combined result</strong><p>Submit the demo ChangeSets, inspect files and reported tests, then export the review.</p></li></ol><p className="body-note">The interactive demo works offline. Use Backend view to inspect the actual API state. Real sponsor integrations are a separate implementation milestone.</p></>}
    <Button className="drawer-done" onClick={onClose}>Back to workspace</Button>
  </div></dialog>;
}

export function Busy({ children }: { children: ReactNode }) { return <span className="busy"><LoaderCircle size={15} className="spin" />{children}</span>; }
