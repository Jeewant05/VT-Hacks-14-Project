import { useEffect, useState } from 'react';
import { LiveDashboard } from './LiveDashboard';
import { SimulationWorkspace } from './SimulationWorkspace';
import { getLiveConfig } from './liveAgents';

type View = 'live' | 'guided';

function requestedView(): View | null {
  const value = new URLSearchParams(window.location.search).get('view');
  return value === 'live' || value === 'guided' ? value : null;
}

/** Keep the view in the URL so a refresh stays where the reader was. */
function rememberView(view: View) {
  const url = new URL(window.location.href);
  url.searchParams.set('view', view);
  window.history.replaceState(null, '', url);
}

export function App() {
  const [view, setView] = useState<View | null>(requestedView);

  // No ?view= in the URL: land on the live panel only when the agents are
  // actually configured, so a fresh clone opens on the guided walkthrough.
  useEffect(() => {
    if (view) return;
    let active = true;
    void getLiveConfig()
      .then(config => { if (active) setView(config.configured ? 'live' : 'guided'); })
      .catch(() => { if (active) setView('guided'); });
    return () => { active = false; };
  }, [view]);

  if (!view) return null;
  const show = (next: View) => { setView(next); rememberView(next); };
  return view === 'live'
    ? <LiveDashboard onSimulation={() => show('guided')} />
    : <SimulationWorkspace onLive={() => show('live')} />;
}
