# Deployment reference — synapse-vt.us

Fly app `synapse-vt`, one machine in `iad`, a 1GB volume at `/data`. The API and
the built dashboard are served from one origin: everything under `/api`, static
UI at `/`, agent cards at `/.well-known/`.

## Configuration lives in two places

**`fly.toml` `[env]`** — plain config, versioned with the repo and redeployed
with it. Nothing secret belongs here.

| Variable | Value | Why |
| --- | --- | --- |
| `IDENTITY_MODE` | `ans` | Real ANS verification, not the fixture |
| `MEMORY_MODE` / `TRACE_MODE` | `cache` | Databricks is not wired up |
| `ANS_PUBLIC_BASE_URL` | `https://synapse-vt.us` | DPoP `htu` is compared to this, never to the `Host` header |
| `ANS_BASE_URL` | `https://api.godaddy.com` | The CLI and client default to OTE otherwise |
| `ANS_DOMAIN` | `synapse-vt.us` | Zone the agents are registered under |
| `ANS_TRUSTED_TL_HOSTS` | `transparency.ans.godaddy.com,api.godaddy.com` | Checked before a badge URL from DNS is fetched |
| `CORS_ORIGINS` | `https://synapse-vt.us` | |
| `DATABASE_PATH` | `/data/synapse.db` | On the volume, so it survives a redeploy |
| `LOCAL_BASE_URL` | `http://127.0.0.1:8080` | Where the runner posts while signing for the public origin |
| `BACKEND_PROVIDER` / `FRONTEND_PROVIDER` / `QA_PROVIDER` | `gemini` | Live coding agents |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Optional: equals the code default, pinned here so a change to the default cannot silently change production |

**Fly secrets** — `fly secrets set`, or the dashboard's batch import.

| Secret | What it is |
| --- | --- |
| `ANS_API_KEY` / `ANS_API_SECRET` | GoDaddy ANS credentials. Stored split; composed into `key:secret` on use |
| `DEMO_TOKEN` | Operator secret for `/api/reset` only. Everything else the dashboard does is open |
| `ANS_AGENT_IDENTITIES` | JSON of base64 PEM cert+key per agent, for the server-side runner |
| `GEMINI_API_KEY_BACKEND` / `_FRONTEND` / `_QA` | One Gemini key per live agent, so the three concurrent agents do not share a rate limit. `GEMINI_API_KEY` is accepted as a single shared fallback |
| `ACME_CHALLENGES` | HTTP-01 responses. Only needed while registering; safe to drop once every agent is ACTIVE |

## The app refuses to start misconfigured

`require_demo_token_for_public()` rejects a deployment whose
`ANS_PUBLIC_BASE_URL` is a public host while `DEMO_TOKEN` is unset — `/api/reset`
would let anyone who found the URL wipe the workspace. The failure is at startup,
before the first visitor, not at request time.

## What is open, and the cost

Only `/api/reset` needs the token, because it is the one endpoint that destroys
state. Live runs and the demo runner are open so the dashboard works without a
prompt. The cost of that is **provider quota, not data**: anyone who finds the
URL can start a live run on the three Gemini keys. Watch usage in Google AI Studio,
and rotate the keys if the URL travels further than intended.

The demo runner never resets, so a second run replays over the finished
workspace. Press Reset (which asks for the token) to start the scene fresh.

## Registering another agent or version

`force_https` must be **false** during ANS domain validation. HTTP-01 fetches
over plain HTTP and this RA does not follow the 301, so every challenge fails
otherwise. Set it false, deploy, validate, set it back, deploy. See docs/ANS.md.

## Unused here

`HUGGINGFACE_*`, `CEREBRAS_*`, `GROQ_*`, `GITHUB_*`, `OPENROUTER_*`, `OPENAI_*` are
supported vendors but not selected. A `HUGGINGFACE_API_KEY` secret may still be on the
app from the earlier Hugging Face setup; nothing reads it while the providers are
`gemini`.

`DATABRICKS_*` is unused while `MEMORY_MODE`/`TRACE_MODE` are `cache`. `PORKBUN_*` is
local tooling for publishing ANS DNS records and must not be deployed.
