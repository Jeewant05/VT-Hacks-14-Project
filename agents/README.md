# Gemini live-agent mode

The repository now includes a server-side Gemini foundation. It is intentionally
opt-in and does not expose the API key to the browser.

## Configure locally

Copy `.env.example` to `.env`, then set:

```dotenv
AGENT_PROVIDER=gemini
GEMINI_API_KEY=your_key_from_aistudio
GEMINI_MODEL=gemini-2.5-flash
```

Do not commit `.env` or the API key. Gemini API usage may have quotas or charges
separate from a Google One/Pro subscription.

The provider is in `server/app/gemini.py`, and the coordinated three-role runner
is in `server/app/live_agents.py`. The runner uses one shared
`shared/api-contract.json` file and records versioned events rather than allowing
agents to overwrite one another. The next UI integration should stream those
`AgentEvent` objects over Server-Sent Events or WebSockets.

The existing `npm run agent-test` remains the offline coordinator smoke test. It
does not call Gemini and does not incur API usage.
