# mcp-servers: two small MCP servers for learning and agent testing

## What MCP is, in under 150 words

The Model Context Protocol (MCP) is a standard way for an AI agent to use
tools that live in some other program. The program is an **MCP server**; the
agent (or the app hosting it, such as Claude Desktop or an ADK agent) is the
**MCP client**. The client asks the server "what can you do?" (`tools/list`),
gets back tool names, descriptions and input schemas, and then calls tools by
name with JSON arguments (`tools/call`). Besides tools, a server can offer
**resources** (read-only content with a URI, like a file) and **prompts**.
Messages are JSON-RPC 2.0, carried over one of two transports: **stdio**
(client starts the server as a child process) or **Streamable HTTP** (client
POSTs to a URL such as `http://localhost:8001/mcp`, so remote agents can
connect). Any MCP client can use any MCP server: that interoperability is the
whole point.

## The two servers

| Server | Port | REST | MCP tools | Extra |
|---|---|---|---|---|
| [`bookstore-mcp`](bookstore-mcp/) | 8001 | `/api/books`, `/api/orders`, UI at `/` | `list_books`, `search_books`, `get_book`, `purchase_book`, `list_orders` | resource `bookstore://catalog` |
| [`weather-mcp`](weather-mcp/) | 8002 | `/api/cities`, `/api/weather/{city}` | `get_current_weather`, `get_forecast`, `list_supported_cities` | deterministic mock data |

Both use the same structure, so once you have read one you know the other.

## Architecture (same for both)

```
  browser (UI)  ─┐
  curl / apps   ─┼─► FastAPI routes  /api/...  ─┐
                 │                               ├─► service.py  (ALL business logic)
  AI agent      ─┴─► MCP app        /mcp       ─┘        ▲
  (Claude, ADK, Inspector)   Streamable HTTP             │
                                                 data.py (in-memory seed data)
  Claude Desktop ──► python mcp_server.py  (stdio)  ─────┘
```

One process, two doors into the same logic. `service.py` never knows whether a
human or an agent is calling. Change a rule there and REST and MCP change
together. Buy a book in the browser, then read the MCP catalog resource: the
stock has gone down, because there is only one store.

## Run both

```bash
cd mcp-servers
python3.12 -m venv .venv && source .venv/bin/activate   # any Python 3.11+
pip install -r bookstore-mcp/requirements.txt           # same deps for both servers
./run-all.sh                                            # Ctrl-C stops both
```

Then open http://localhost:8001 for the bookstore UI. Each server can also run
alone: `cd bookstore-mcp && python app.py`.

## Two transports, same tools

Every server here speaks MCP two ways. Same `mcp_server.py`, same tools; only
the wire changes.

| | Streamable HTTP | stdio |
|---|---|---|
| Start | `python app.py` (REST + MCP in one process) | nothing to start: the client runs `python mcp_server.py` itself |
| Address | `http://localhost:800X/mcp` | stdin/stdout of the child process |
| Who uses it | remote agents, ADK `McpToolset`, Claude Code, MCP Inspector (URL) | Claude Desktop, MCP Inspector (command), any local client |
| Sessions | `mcp-session-id` header on every request | one process = one session |
| Good for | testing agents over a network, several clients at once | local tools, no ports, no network |

## Test both transports in one go

```bash
# HTTP (servers must be running: ./run-all.sh)
curl -s localhost:8001/api/health; echo; curl -s localhost:8002/api/health; echo
npx -y @modelcontextprotocol/inspector@0.15.0 --cli http://localhost:8001/mcp --transport http --method tools/list
npx -y @modelcontextprotocol/inspector@0.15.0 --cli http://localhost:8002/mcp --transport http --method tools/list

# stdio (nothing running: the Inspector launches each server as a child process)
(cd bookstore-mcp && npx -y @modelcontextprotocol/inspector@0.15.0 --cli ../.venv/bin/python mcp_server.py --method tools/list)
(cd weather-mcp   && npx -y @modelcontextprotocol/inspector@0.15.0 --cli ../.venv/bin/python mcp_server.py --method tools/list)
```

Expected: two `{"status":"ok",...}` lines, then a JSON list of 5 tools, then 3
tools; the two stdio commands print the same two tool lists. The server READMEs
walk through curl, the Inspector UI, raw JSON-RPC over HTTP, raw JSON-RPC over
stdio and Claude Desktop step by step, with the exact output to expect.

## SDK note

Code is pinned to `mcp==2.3.0`. In the 2.x SDK the server class is
`MCPServer` (`from mcp.server.mcpserver import MCPServer`); tutorials written
for 1.x call the same thing `FastMCP`. The decorators (`@mcp.tool()`,
`@mcp.resource(...)`) and the ideas are unchanged.

## What to try next

- Add a tool to either server (see the server READMEs for the 3-step recipe).
- Point an agent at them: an ADK `McpToolset` with the HTTP URL, or Claude Code
  with `claude mcp add --transport http bookstore http://localhost:8001/mcp`.
- Add authentication to `/mcp` so only identified agents can buy books. 
