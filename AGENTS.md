# Synapse (VT Hacks 14)

MCP server that gives coding agents tools for reading repo state and commits. Hackathon prototype, Sep 2026. Deployed on Fly.io from the Dockerfile. Not production; expect rough edges.

## Layout

- `server/` - MCP server code. Entry point: `server/mcp_server.py`.
- `Dockerfile` - runtime image (python 3.13-slim, uv, git).
- `fly.live.toml` - deploy config, gitignored, do not commit.
- `.codex/` - local Codex project config, gitignored.

## Run

    uv sync
    uv run python -m server.mcp_server

Server listens on http://127.0.0.1:8000.

## Hard rules for this repo

- Never commit `.env`, `fly.live.toml`, tokens, or anything under `.codex/`.
- Don't change MCP tool names or signatures in `server/` without asking; other configs depend on them.
- Don't edit the Dockerfile base image or the Fly config without asking.
- All changes go through a PR to `main`. Never push to `main` directly.

## Current focus

Hackathon is over. Repo is in maintenance mode. Only cleanup, docs, and small fixes unless told otherwise.

## Known gotchas

- Runtime image needs `git` installed or commit tools fail (already in Dockerfile).
- Codex may start the MCP server from `.codex/config.toml` when this project opens; that's expected.