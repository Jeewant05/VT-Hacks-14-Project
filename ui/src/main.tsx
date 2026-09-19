import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { components } from "./api.generated";
import "./style.css";

type Health = components["schemas"]["Health"];
type WorkspaceState = components["schemas"]["WorkspaceState"];

async function get<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, { signal });
  if (!response.ok) throw new Error(`Server returned ${response.status}`);
  return response.json();
}

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [state, setState] = useState<WorkspaceState | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const [nextHealth, nextState] = await Promise.all([
          get<Health>("/health", controller.signal), get<WorkspaceState>("/state", controller.signal),
        ]);
        setHealth(nextHealth); setState(nextState); setError(null);
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Connection failed");
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(refresh, 1000);
      }
    }
    void refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  return <main>
    <header><div><span className="eyebrow">SYNAPSE / WORKSPACE</span><h1>Shared intent.<br />Coordinated work.</h1></div>
      <span className={`badge ${error ? "error" : ""}`} role="status">{error ? "Backend offline" : health ? "Backend connected" : "Connecting…"}</span>
    </header>
    <p className="notice">Foundation preview · Local fixtures · Live ANS and Databricks integrations are not connected.</p>
    {error && <p role="alert" className="error">{error}. Start the API with <code>npm run dev:server</code>. {state && "Showing the last received state."}</p>}
    <section><span className="eyebrow">01 / OBJECTIVE</span><h2>{state?.objective?.title ?? "Your workspace is ready"}</h2>
      <p>{state?.objective?.description ?? "Run npm run seed to load the prepared demo objective."}</p>
      <ul>{state?.objective?.acceptance_criteria.map(item => <li key={item}>{item}</li>)}</ul>
    </section>
    <section><span className="eyebrow">02 / WORKSTREAMS</span><div className="workstreams">{state?.workstreams?.map(workstream => <article key={workstream.id}>
      <span className="badge">{workstream.status}</span><h2>{workstream.title}</h2><p>{workstream.agent_id} · Not verified</p>
      <code>{workstream.owned_paths.join(", ")}</code><p>{workstream.depends_on?.length ? `Depends on ${workstream.depends_on.join(", ")}` : "Provides the authentication API"}</p>
    </article>)}</div></section>
    <div className="bottom"><section><span className="eyebrow">03 / COORDINATION FEED</span><h2>Ready for agent activity</h2><p>Identity checks, context requests, and conflict evidence will appear here.</p></section>
      <section><span className="eyebrow">04 / CONVERGENCE</span><h2>Review awaits completion</h2><p>The combined review will become available when both workstreams finish.</p></section></div>
    <footer>Identity: {health?.identity_mode ?? "—"} · Memory: {health?.memory_mode ?? "—"} · Foundation milestone</footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
