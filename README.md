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

No sponsor credentials are required for setup. `IDENTITY_MODE=mock`, `MEMORY_MODE=cache`, and `TRACE_MODE=cache` keep the app local. Mock identity results and seeded decisions are fixtures. The cache trace store exists only for the running process.

## Databricks trace layer

Synapse can write coordinator and live-agent events to a Unity Catalog Delta table for debugging and verification. Create the table with [the trace schema](docs/databricks-trace-schema.sql), then set the following server-only values in `.env`:

```sh
TRACE_MODE=databricks
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=<personal-access-token-or-service-principal-token>
DATABRICKS_WAREHOUSE_ID=<sql-warehouse-id>
DATABRICKS_CATALOG=<catalog>
DATABRICKS_SCHEMA=<schema>
DATABRICKS_TRACE_TABLE=synapse_agent_traces
```

The principal needs `USE CATALOG`, `USE SCHEMA`, `INSERT`, and `SELECT` for that table. With complete configuration, `GET /traces` reads the newest persisted records and `GET /traces?run_id=run-…` filters a live run. If the Databricks settings are incomplete, Synapse keeps running with the in-process cache and reports `trace_mode: cache` from `/health`.

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

The stricter orchestration API lives under `/api`. It registers three codebase demo agents, requires a structured Intention Document before execution, blocks deterministic file/symbol/contract/dependency/permission conflicts, validates submitted ChangeSets against their approved intention, and records the workflow through the configured trace sink. See [the three-agent workflow](agents/README.md#three-agent-orchestration-demo).

The checked-in [orchestration v1 contract](/Users/amanjeetsahagal/Documents/VTHACKS/VT-Hacks-14-Project/contracts/orchestration-api-v1.json) is frozen for frontend work. The verification suite rejects changes to its `/api` operations or response schemas. Additive API work belongs in a new versioned endpoint or a deliberate v2 contract update.

See [scope and team handoff](docs/SETUP.md) and [demo runbook](docs/DEMO.md). Keep secrets in ignored `.env`; never commit credentials, keys, or local database files.
