# Demo runbook

## Live three-agent Gemini demo

1. Copy `.env.example` to `.env`, set `AGENT_PROVIDER=gemini` and the three role-specific Gemini keys, then run `npm run setup` and `npm run dev`.
2. Open the live dashboard, enter a small full-stack objective, and start the agents.
3. Watch all three agents publish an intention. Explain that these plans are injected into every implementation prompt before any file is written.
4. Point out that backend and frontend then build concurrently using separate APIs, exclusive directory ownership, and one shared contract.
5. The integration agent reviews their staged output; after validation, all files are committed to the run sandbox together.
6. Open generated files in the project browser and finish on the coordinator's validation event.

Be precise in the presentation: the displayed files are genuinely returned by Gemini and written to an isolated local run directory. Synapse validates boundaries, but it does not execute or commit generated code. Use the guided simulation when a Gemini key or network connection is unavailable.

## Foundation smoke check (available now)

1. Copy `.env.example` to `.env` and run `npm run setup`.
2. Start `npm run dev` and open http://127.0.0.1:5173.
3. Confirm coordinator connectivity, the OAuth objective, three pending workstreams, and the local-fixture notice.
4. In another terminal run `npm run rehearse` and `npm run check`.
5. Run `npm run reset` to restore the local fixtures; the dashboard polls once per second.

## Guided three-agent rehearsal

Reset the workspace → connect your coding agent and two teammate agents → publish planned file touches → show that all three selected `src/auth/session.ts` → inspect the three server-side file conflicts → apply the ownership plan → show exclusive scopes → submit three ChangeSets → open the combined review.

The key proof happens before implementation: the coordinator blocks the three plans while their intended files overlap. The approved plan leaves `src/auth/session.ts` with the API agent, moves UI work to `OrganizationLogin.tsx`, and moves telemetry work to `authEvents.ts`. The final review shows three manifests with one owner per file.

Target: under three minutes, five clean runs, no manual database edits. Report the guided clients honestly. The current identity and memory adapters are local fixtures; do not present them as live ANS or Databricks operations. Distinguish agent-reported tests from executed tests. Record a successful backup and tag the tested commit `demo-stable` only after the complete flow works.

The pasted deadline is provisional: confirm this year's submission time and video requirements. Reserve relocation and sleep time. Submit ahead of the deadline; do not make code changes after the last clean rehearsal.
