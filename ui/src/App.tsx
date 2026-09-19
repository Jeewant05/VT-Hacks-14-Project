import { useState } from 'react';
import { LiveDashboard } from './LiveDashboard';

export function App() {
  const [live, setLive] = useState(true);
  return live ? <LiveDashboard onSimulation={() => setLive(false)} /> : (
    <main style={{ padding: 40, fontFamily: 'system-ui' }}>
      <h1>Synapse</h1>
      <p>The deterministic simulation is still available in the previous workspace build.</p>
      <button onClick={() => setLive(true)}>Open live Gemini agents</button>
    </main>
  );
}
