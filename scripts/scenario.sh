#!/usr/bin/env bash
# The full demo scene against a running API (npm run dev:server). Fail-safe level 2.
# Usage: bash scripts/scenario.sh [base_url]
set -euo pipefail
B="${1:-http://127.0.0.1:8000}"
J='Content-Type: application/json'
step() { echo; echo "== $1"; }
post() { curl -sS -X POST "$B$1" -H "$J" ${2:+-d "$2"} | python3 -c "
import sys,json; s=json.load(sys.stdin)
if 'detail' in s: print('  ->', s['detail']); sys.exit(0)
print('  workstreams:', {w['id']: w['status'] for w in s['workstreams']})
print('  open conflicts:', [(c['id'], c['conflicting_field'], c['decision_id']) for c in s['conflicts'] if c['status']=='open'])
print('  last event:', s['events'][-1]['event_type'] if s['events'] else None)"; }

APPROVED='{"token":"string","user":"object"}'
WRONG='{"accessToken":"string","profile":"object"}'

step "reset";              post /reset
step "backend joins";      post /agents/backend-agent/join
step "frontend joins";     post /agents/frontend-agent/join
step "rogue agent refused"; post /agents/rogue-agent/join
step "claim both"
post /workstreams/backend/claim  '{"agent_id":"backend-agent"}'
post /workstreams/frontend/claim '{"agent_id":"frontend-agent"}'
step "backend declares provides {token,user}"
post /workstreams/backend/declare "{\"agent_id\":\"backend-agent\",\"contract\":{\"method\":\"POST\",\"path\":\"/api/oauth\",\"role\":\"provides\",\"response_fields\":$APPROVED}}"
step "frontend declares consumes {accessToken,profile}  -> CONFLICT"
post /workstreams/frontend/declare "{\"agent_id\":\"frontend-agent\",\"contract\":{\"method\":\"POST\",\"path\":\"/api/oauth\",\"role\":\"consumes\",\"response_fields\":$WRONG}}"
step "frontend tries to submit while blocked -> 409"
post /workstreams/frontend/submit "{\"id\":\"cs-f0\",\"workstream_id\":\"frontend\",\"agent_id\":\"frontend-agent\",\"files\":[\"src/components/login/x.tsx\"],\"contract\":{\"method\":\"POST\",\"path\":\"/api/oauth\",\"role\":\"consumes\",\"response_fields\":$WRONG}}"
step "frontend redeclares {token,user} -> RESOLVED"
post /workstreams/frontend/declare "{\"agent_id\":\"frontend-agent\",\"contract\":{\"method\":\"POST\",\"path\":\"/api/oauth\",\"role\":\"consumes\",\"response_fields\":$APPROVED}}"
step "both submit"
post /workstreams/backend/submit "{\"id\":\"cs-b1\",\"workstream_id\":\"backend\",\"agent_id\":\"backend-agent\",\"files\":[\"src/api/auth/oauth.ts\"],\"contract\":{\"method\":\"POST\",\"path\":\"/api/oauth\",\"role\":\"provides\",\"response_fields\":$APPROVED},\"tests\":[{\"name\":\"oauth returns token+user\",\"status\":\"passed\"}]}"
post /workstreams/frontend/submit "{\"id\":\"cs-f1\",\"workstream_id\":\"frontend\",\"agent_id\":\"frontend-agent\",\"files\":[\"src/components/login/x.tsx\"],\"contract\":{\"method\":\"POST\",\"path\":\"/api/oauth\",\"role\":\"consumes\",\"response_fields\":$APPROVED},\"tests\":[{\"name\":\"login consumes token+user\",\"status\":\"passed\"}]}"
echo; echo "== done. GET $B/state for the review page."
