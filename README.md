# agent-playground

Small sample agents built with different agent frameworks, for learning and
trying things out. Each sample is deliberately minimal: one agent, one clear
job, a few hundred lines you can read in one sitting.

There are two kinds of thing here: **agents** (built with a framework) and
**MCP servers** (tools for agents to call). The servers exist so the agents
have something real to connect to while you learn tool discovery, tool calls
and, later, authentication.

### Agents

| Framework | Sample | What it teaches |
|---|---|---|
| [Google ADK](adk/) | `customer_support_agent` | Agent + instruction + one tool, guardrails in callbacks, basic data leak protection, tests without a model |

### MCP servers

| Server | Port | What it teaches |
|---|---|---|
| [`mcp-servers/bookstore-mcp`](mcp-servers/bookstore-mcp/) | 8001 | One service layer behind REST **and** MCP, tools vs resources, stateful tools (stock, orders), error handling, a small UI |
| [`mcp-servers/weather-mcp`](mcp-servers/weather-mcp/) | 8002 | The same pattern with deterministic mock data, so agent tests are repeatable |

Both are FastAPI + the official `mcp` Python SDK, in-memory data, no auth, no
keys. `mcp-servers/README.md` explains MCP in under 150 words and how to run
both with one command; each server README walks through curl, MCP Inspector,
raw JSON-RPC and Claude Desktop, with the output to expect.

## Layout

```
agent-playground/
  README.md            this file
  adk/                 Google ADK agents (one folder per agent)
  mcp-servers/         MCP servers agents can connect to (one folder per server)
  <framework>/         one folder per framework, each with its own README,
                       requirements.txt and tests
```

Each top-level folder is self-contained: its own virtual environment,
dependencies and run instructions. Nothing is shared between folders on
purpose, so you can read one without knowing the others.

## How the pieces fit

```
  adk/customer_support_agent ──(MCP over HTTP)──►  mcp-servers/bookstore-mcp :8001/mcp
  Claude Desktop / Claude Code / MCP Inspector ──►  mcp-servers/weather-mcp   :8002/mcp
```

Today the agent sample uses only `google_search`. The next step is to point an
agent at these servers through `McpToolset`, then put identity and
authorisation (HelixID) in front of `/mcp`.

## Ground rules for every sample

- **Secrets never enter the repo.** Keys live in a git-ignored `.env`; each
  sample ships an `.env.example` with placeholders.
- **Rules that must hold go in code, not only in the prompt.** A prompt is a
  suggestion to the model; a callback or a check is a guarantee.
- **Tests run without a model.** A scripted fake stands in for the LLM, so
  `pytest` is fast, free and deterministic.
