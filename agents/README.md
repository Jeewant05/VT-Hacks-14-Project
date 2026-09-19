# Agent clients

This directory contains deterministic scripted clients for testing the coordinator's
public HTTP API. They are not autonomous agents and do not bypass the coordinator.

## Run the agent smoke test

Start a seeded server in another terminal:

```sh
npm run seed
npm run dev:server
```

Then run:

```sh
uv run python -m agents.test_agents
```

The test verifies that both fixture agents can join and claim work, incompatible
contracts open a conflict and reject a changeset with HTTP 409, and a compatible
re-declaration lets both changesets complete the objective. Use `--base-url` to
point at another API instance.
