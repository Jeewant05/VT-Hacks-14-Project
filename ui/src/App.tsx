import { useState } from 'react';
import { LiveDashboard } from './LiveDashboard';
import { SimulationWorkspace } from './SimulationWorkspace';

export function App() {
  const [live, setLive] = useState(true);
  return live
    ? <LiveDashboard onSimulation={() => setLive(false)} />
    : <SimulationWorkspace onLive={() => setLive(true)} />;
}
