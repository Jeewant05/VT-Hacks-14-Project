# Synapse

A hackathon demo of pre-merge coordination between two coding agents. This repository currently contains the **foundation milestone**, not a working conflict-prevention product.

## Quick start

Prerequisites: Git, Python 3.13, [uv](https://docs.astral.sh/uv/), and Node 22.12+ (22.x) with npm. `.python-version` and `.nvmrc` record the development runtimes.

```sh
git clone https://github.com/Jeewant05/VT-Hacks-14-Project.git
cd VT-Hacks-14-Project
cp .env.example .env
npm run setup
npm run dev
```

Open http://127.0.0.1:5173. The dashboard should show **Backend connected**, the prepared OAuth objective, and two pending workstreams. API documentation is at http://127.0.0.1:8000/docs. Stop both services with Ctrl+C.

No sponsor credentials are required for setup. `IDENTITY_MODE=mock` and `MEMORY_MODE=cache` are the only implemented modes. Mock identity results are fixtures, not ANS verification. The memory adapter is an in-process development fixture, not durable Databricks delivery. Seeded decisions are local fixtures.

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

Only `GET /health` and `GET /state` exist today. The official Python MCP SDK is installed for the next milestone; no MCP transport or tools are exposed yet. The UI uses a Vite development proxy for `/api`. Its production build is verified, but production hosting/proxy configuration is outside this milestone.

See [scope and team handoff](docs/SETUP.md) and [demo runbook](docs/DEMO.md). Keep secrets in ignored `.env`; never commit credentials, keys, or local database files.
