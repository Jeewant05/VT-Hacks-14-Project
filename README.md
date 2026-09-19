# Synapse

A hackathon demo of pre-merge coordination between three coding agents. Each agent publishes its intended file touches before implementation; the coordinator detects overlap, applies exclusive ownership, and accepts only conflict-free ChangeSets.

## Quick start

Prerequisites: Git, Python 3.13, [uv](https://docs.astral.sh/uv/), and Node 22.12+ (22.x) with npm. `.python-version` and `.nvmrc` record the development runtimes.

```sh
git clone https://github.com/Jeewant05/VT-Hacks-14-Project.git
cd VT-Hacks-14-Project
cp .env.example .env
npm run setup
npm run dev
```

Open http://127.0.0.1:5173. The dashboard should show **Coordinator connected**, the prepared OAuth objective, and three pending workstreams. API documentation is at http://127.0.0.1:8000/docs. Stop both services with Ctrl+C.

No sponsor credentials are required for setup. The default `IDENTITY_MODE=mock` uses a local allowlist: mock identity results are fixtures, not ANS verification.

`IDENTITY_MODE=ans` performs real Agent Name Service verification — transparency-log badge for identity and liveness, plus an ANS-6 Method B proof of possession on every privileged call. It needs registered agents and credentials; see [docs/ANS.md](docs/ANS.md). In that mode the dashboard's guided buttons are read-only by design, because a browser cannot hold agent identity keys.

`MEMORY_MODE=cache` remains the only memory mode. The memory adapter is an in-process development fixture, not durable Databricks delivery. Seeded decisions are local fixtures.

## Commands

| Command | Purpose |
| --- | --- |
| `npm run setup` | Install locked Python/npm dependencies, export contracts, seed SQLite |
| `npm run dev` | Start API on 8000 and UI on 5173 |
| `npm run dev:server` / `npm run dev:ui` | Start one service |
| `npm run contracts` | Export Python schemas/OpenAPI and generate UI API types |
| `npm run seed` | Seed fixtures if no objective exists; preserve existing state |
| `npm run reset` | Replace local workspace state with initial fixtures |
| `npm run check` | Python lint, foundation smoke tests, TypeScript check, UI build |
| `npm run rehearse` | Check a running, seeded API; not the final product rehearsal |
| `npm run ans -- <step>` | Drive ANS registration (`generate`, `register`, `records`, `acme`, `dns`, `status`, `certs`) |
| `npm run ans:check` | Resolve the seeded ANSNames and report what a verifier would decide |

The database defaults to `.local/synapse.db`. Reset touches only local workspace state; it does not contact sponsor services. Do not use the local reset command against any future shared or production store.

## Layout and ownership

| Directory | Purpose | Owner |
| --- | --- | --- |
| `server/` | API, models, SQLite, coordinator and integration interfaces | P1; P3/P4 implement their adapters |
| `ui/` | React/TypeScript dashboard | P2 |
| `agents/` | Future scripted clients and coding-agent instructions | P2 with P1 |
| `demo-repo/` | Future small OAuth application and prepared changes | P2 |
| `contracts/` | Generated schemas and sample state | P1 approves interface changes |
| `scripts/` | Setup support, contracts, seed/reset, smoke check | P1 |
| `docs/` | Scope, ownership, demo instructions | All |

Pydantic models in `server/app/models.py` are the source of truth. Run `npm run contracts` after model or endpoint changes, and commit all generated files. Do not edit `ui/src/api.generated.ts` manually. Exact dependency resolutions are committed in `uv.lock` and `package-lock.json`; use `uv sync --locked` and `npm ci` for repeatable installs.

The coordinator exposes health/state reads plus agent join, workstream claim, contract declaration, scope reassignment, ChangeSet submission, and local reset endpoints. The guided UI calls these endpoints through the Vite `/api` proxy. The official Python MCP SDK is installed, but no MCP transport or tools are exposed yet. Production hosting/proxy configuration remains outside this milestone.

See [scope and team handoff](docs/SETUP.md) and [demo runbook](docs/DEMO.md). Keep secrets in ignored `.env`; never commit credentials, keys, or local database files.
