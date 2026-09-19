# Demo runbook

## Foundation smoke check (available now)

1. Copy `.env.example` to `.env` and run `npm run setup`.
2. Start `npm run dev` and open http://127.0.0.1:5173.
3. Confirm backend connectivity, the OAuth objective, two pending workstreams, and the local-fixture notice.
4. In another terminal run `npm run rehearse` and `npm run check`.
5. Run `npm run reset` to restore the local fixtures; the dashboard polls once per second.

## Final product rehearsal (not implemented yet)

Create objective → verify agents → request scoped context → declare incompatible contracts → block convergence → retrieve Databricks decision → accept frontend correction → redeclare and submit → show combined review and successful event delivery.

Target: under three minutes, five clean runs, no manual database edits. Report scripted clients honestly. Show fresh ANS evidence and real Databricks reads/writes. Distinguish agent-reported tests from executed tests. Record a successful backup and tag the tested commit `demo-stable` only after the complete flow works.

The pasted deadline is provisional: confirm this year's submission time and video requirements. Reserve relocation and sleep time. Submit ahead of the deadline; do not make code changes after the last clean rehearsal.
