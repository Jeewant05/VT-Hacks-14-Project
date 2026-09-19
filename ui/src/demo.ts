export type Phase = 'ready' | 'verifying' | 'context' | 'conflict' | 'correcting' | 'aligned' | 'submitting' | 'complete';
export type DemoEvent = { id: string; title: string; detail: string; time: string; tone: 'neutral' | 'success' | 'warning'; evidence?: 'identity' | 'decision' | 'contract' | 'tests' };
export type DemoState = { phase: Phase; events: DemoEvent[] };
export type DemoAction = { type: 'start' | 'verified' | 'declared' | 'accept' | 'redeclared' | 'submit' | 'completed' | 'reset' };

const initialEvent: DemoEvent = { id: 'objective', title: 'Objective created', detail: 'Two workstreams assigned to a shared objective.', time: '00:00', tone: 'neutral' };
export const initialDemo: DemoState = { phase: 'ready', events: [initialEvent] };

export function demoReducer(state: DemoState, action: DemoAction): DemoState {
  const append = (phase: Phase, events: DemoEvent[]): DemoState => ({ phase, events: [...state.events, ...events] });
  switch (action.type) {
    case 'reset': return initialDemo;
    case 'start':
      return state.phase === 'ready' ? append('verifying', [{ id: 'joining', title: 'Agents joining', detail: 'Checking the two demo identity fixtures.', time: '00:02', tone: 'neutral' }]) : state;
    case 'verified':
      return state.phase === 'verifying' ? append('context', [
        { id: 'identity', title: 'Demo identities checked', detail: 'Backend and frontend accepted by the local fixture.', time: '00:04', tone: 'success', evidence: 'identity' },
        { id: 'context', title: 'Scoped context delivered', detail: 'Each agent receives its assignment and dependencies.', time: '00:06', tone: 'neutral' },
      ]) : state;
    case 'declared':
      return state.phase === 'context' ? append('conflict', [
        { id: 'declared', title: 'Plans declared', detail: 'Both agents declared POST /api/oauth.', time: '00:09', tone: 'neutral', evidence: 'contract' },
        { id: 'conflict', title: 'Contract mismatch detected', detail: 'Two response fields disagree. Convergence is blocked.', time: '00:10', tone: 'warning', evidence: 'contract' },
        { id: 'memory', title: 'Project decision found', detail: 'Local copy of ADR-001 establishes token + user.', time: '00:11', tone: 'neutral', evidence: 'decision' },
      ]) : state;
    case 'accept':
      return state.phase === 'conflict' ? append('correcting', [{ id: 'accepted', title: 'Correction accepted', detail: 'Frontend asked to adopt the approved response.', time: '00:18', tone: 'neutral', evidence: 'decision' }]) : state;
    case 'redeclared':
      return state.phase === 'correcting' ? append('aligned', [{ id: 'aligned', title: 'Frontend contract redeclared', detail: 'Both workstreams now agree on token + user.', time: '00:21', tone: 'success', evidence: 'contract' }]) : state;
    case 'submit':
      return state.phase === 'aligned' ? append('submitting', [{ id: 'submit', title: 'Submitting demo ChangeSets', detail: 'Collecting sample manifests and reported tests.', time: '00:25', tone: 'neutral' }]) : state;
    case 'completed':
      return state.phase === 'submitting' ? append('complete', [{ id: 'complete', title: 'Ready for Convergence review', detail: 'Two compatible manifests. No open conflicts.', time: '00:28', tone: 'success', evidence: 'tests' }]) : state;
    default: return state;
  }
}

export const hasIdentity = (phase: Phase) => !['ready', 'verifying'].includes(phase);
export const isAligned = (phase: Phase) => ['aligned', 'submitting', 'complete'].includes(phase);
export const hasDeclarations = (phase: Phase) => !['ready', 'verifying', 'context'].includes(phase);

export const decisions = [
  { id: 'ADR-001', title: 'Authentication response contract', component: 'Authentication', summary: 'All authentication responses use token and user.', content: 'POST /api/oauth returns a token string and a user object. Consumers must use these field names to keep the login experience consistent.', code: '{\n  "token": "string",\n  "user": { "id": "string", "name": "string" }\n}', relevant: true },
  { id: 'ADR-002', title: 'Workstream ownership', component: 'Coordination', summary: 'Separate API ownership from login component ownership.', content: 'The backend workstream owns src/api/auth/**. The frontend workstream owns src/components/login/**. Neither agent may claim files outside its assignment.', code: 'backend   src/api/auth/**\nfrontend  src/components/login/**', relevant: false },
  { id: 'ADR-003', title: 'Review before convergence', component: 'Review', summary: 'Resolve incompatible declarations before final review.', content: 'Both workstreams must submit compatible ChangeSets before the objective can be marked complete. Convergence produces a review summary; it does not merge code.', code: 'open conflicts = 0\ncompatible manifests = 2', relevant: false },
];

export type DemoFile = { path: string; owner: 'Backend' | 'Frontend'; added: number; removed: number; description: string; lines: { kind: 'context' | 'add' | 'remove'; text: string }[] };
export const demoFiles: DemoFile[] = [
  { path: 'src/api/auth/oauth.ts', owner: 'Backend', added: 8, removed: 2, description: 'Provide the approved OAuth response.', lines: [
    { kind: 'context', text: 'export async function oauth(request: Request) {' },
    { kind: 'add', text: '  const organization = await resolveOrganization(request);' },
    { kind: 'add', text: '  const session = await authenticate(request, organization);' },
    { kind: 'remove', text: '  return Response.json({ session });' },
    { kind: 'add', text: '  return Response.json({' },
    { kind: 'add', text: '    token: session.token,' },
    { kind: 'add', text: '    user: session.user,' },
    { kind: 'add', text: '  });' },
    { kind: 'context', text: '}' },
  ] },
  { path: 'src/api/auth/oauth.test.ts', owner: 'Backend', added: 12, removed: 0, description: 'Describe the expected response contract.', lines: [
    { kind: 'add', text: 'it("returns the approved auth contract", async () => {' },
    { kind: 'add', text: '  const result = await requestOAuth(demoOrganization);' },
    { kind: 'add', text: '  expect(result).toHaveProperty("token");' },
    { kind: 'add', text: '  expect(result).toHaveProperty("user");' },
    { kind: 'add', text: '});' },
  ] },
  { path: 'src/components/login/OrganizationLogin.tsx', owner: 'Frontend', added: 5, removed: 3, description: 'Consume token and user after the correction.', lines: [
    { kind: 'context', text: 'async function handleLogin() {' },
    { kind: 'context', text: '  const response = await fetch("/api/oauth", { method: "POST" });' },
    { kind: 'remove', text: '  const { accessToken, profile } = await response.json();' },
    { kind: 'remove', text: '  setSession(accessToken, profile);' },
    { kind: 'add', text: '  const { token, user } = await response.json();' },
    { kind: 'add', text: '  setSession(token, user);' },
    { kind: 'context', text: '}' },
  ] },
  { path: 'src/components/login/OrganizationLogin.test.tsx', owner: 'Frontend', added: 10, removed: 0, description: 'Describe the corrected consumer behavior.', lines: [
    { kind: 'add', text: 'it("opens a session from the approved response", async () => {' },
    { kind: 'add', text: '  mockOAuth({ token: "demo-token", user: demoUser });' },
    { kind: 'add', text: '  await clickOrganizationLogin();' },
    { kind: 'add', text: '  expect(session.user).toEqual(demoUser);' },
    { kind: 'add', text: '});' },
  ] },
];

export const demoTests = [
  { name: 'OAuth returns token and user', owner: 'Backend' },
  { name: 'Organization context is required', owner: 'Backend' },
  { name: 'Login consumes the approved response', owner: 'Frontend' },
  { name: 'Authenticated user is displayed', owner: 'Frontend' },
];
