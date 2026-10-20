# weather-mcp

## 1. What this server is

A weather information service for ten cities with **mock, deterministic**
data: no API key, works offline, and the same question always gets the same
answer (useful when you are testing an agent and want repeatable results). It
exposes three tools: `get_current_weather`, `get_forecast` and
`list_supported_cities`.

## 2. How it is built

```
 curl / apps ──► /api/cities, /api/weather/{city}   FastAPI routes ─┐
                                                                    ├─► service.py ─► data.py
 agent       ──► POST /mcp   MCP app (Streamable HTTP)             ─┘
 Claude Desktop ──► python mcp_server.py   (stdio)
```

| File | Role |
|---|---|
| `data.py` | Today's reading per city, plus a fixed 7-day pattern used to derive forecasts. |
| `service.py` | Lookup (case-insensitive), forecast maths, typed errors `UnknownCity`, `InvalidDays`. |
| `app.py` | FastAPI routes and `app.mount("/", mcp.streamable_http_app())`. |
| `mcp_server.py` | The three MCP tools; each calls `service.py`. Also the stdio entry point. |

Same shape as `bookstore-mcp`, with no UI and no state that changes. Read the
bookstore README for the longer explanation of tools vs resources and HTTP vs
stdio; the short version: **tools** are actions the agent calls, **resources**
are content it reads; **Streamable HTTP** means POST JSON-RPC to `/mcp` with a
session-id header (remote clients), **stdio** means the client runs
`python mcp_server.py` as a child process (local clients like Claude Desktop).

**Errors.** An unknown city returns `UNKNOWN_CITY` with the list of supported
cities in the message, so an agent can correct itself without a second
lookup. `days` outside 1..7 returns `INVALID_DAYS`.

## 3. How to run it

```bash
cd mcp-servers
python3.12 -m venv .venv && source .venv/bin/activate     # Python 3.11+ (skip if done for bookstore)
pip install -r weather-mcp/requirements.txt
cd weather-mcp && python app.py                            # http://127.0.0.1:8002
```

### Two ways to serve the same tools

| Transport | Command | When |
|---|---|---|
| Streamable HTTP | `python app.py` → MCP at `http://localhost:8002/mcp` (plus REST) | remote agents, ADK, Claude Code, Inspector by URL |
| stdio | `python mcp_server.py` (the client starts it; you never run it by hand) | Claude Desktop, Inspector by command, local scripts |

Both use the one `mcp` object in `mcp_server.py`. No `print()` anywhere: in
stdio mode stdout belongs to the protocol.

## 4. How to test it (easy to hard)

### 4a. REST with curl

```bash
curl -s localhost:8002/api/health
curl -s localhost:8002/api/cities
curl -s localhost:8002/api/weather/kochi
curl -s "localhost:8002/api/weather/New%20York?days=2"
curl -s -i localhost:8002/api/weather/atlantis | head -1
```

Expected, in order:

```
{"status":"ok","service":"weather","mcp":"/mcp"}
["Kochi","Bengaluru","Mumbai","Delhi","Dubai","London","Berlin","New York","Singapore","Sydney"]
{"city":"Kochi","country":"IN","temp_c":29,"condition":"Humid and cloudy","humidity":84,"wind_kph":14}
{"city":"New York","country":"US","days":2,"forecast":[{"day":1,"temp_c":22,"condition":"Partly cloudy","humidity":52},{"day":2,"temp_c":19,"condition":"Light rain","humidity":63}]}
HTTP/1.1 404 Not Found         <- body: {"error":"UNKNOWN_CITY","message":"'atlantis' is not a supported city. Try one of: Kochi, ..."}
```

### 4b. MCP Inspector

```bash
npx -y @modelcontextprotocol/inspector@0.15.0
```

Transport **Streamable HTTP**, URL `http://localhost:8002/mcp`, **Connect**,
**Tools > List Tools**. Expected: three tools. Run `get_forecast` with
`city = sydney`, `days = 3`: day 1 is 20 °C "Partly cloudy". Run
`get_current_weather` with `city = Atlantis`: a red error result naming the
supported cities. CLI mode:

```bash
npx -y @modelcontextprotocol/inspector@0.15.0 --cli http://localhost:8002/mcp --transport http --method tools/list
npx -y @modelcontextprotocol/inspector@0.15.0 --cli http://localhost:8002/mcp --transport http \
    --method tools/call --tool-name get_current_weather --tool-arg city=london
```

Expected: `{"tools": [{"name": "get_current_weather", ...}, {"name": "get_forecast", ...}, {"name": "list_supported_cities", ...}]}` and then
`"text": "{\n  \"city\": \"London\",\n  \"country\": \"GB\",\n  \"temp_c\": 14, ...` with `"isError": false`.

### 4c. Raw MCP over HTTP with curl

Same dance as the bookstore: `initialize` (grab the `mcp-session-id` header),
`notifications/initialized`, then calls. Both headers are required every time.

The server must be running (`python app.py` in another terminal, or
`./run-all.sh`). `curl -s` prints nothing at all when nothing is listening, so
the first line below checks that before anything else. Step 1 is `initialize`;
the session id is read from the response headers into `$SID`. Step 2 is the
`notifications/initialized` notification (no `id`, so no reply body, just
`202 Accepted`). Steps 3 to 5 are ordinary requests.

```bash
curl -sf localhost:8002/api/health >/dev/null && echo "server up" || echo "NOT RUNNING: start it with  cd weather-mcp && python app.py"

H='Content-Type: application/json'
A='Accept: application/json, text/event-stream'

SID=$(curl -s -i -X POST localhost:8002/mcp -H "$H" -H "$A" -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
  "params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  | grep -i '^mcp-session-id:' | awk '{print $2}' | tr -d '\r')
[ -n "$SID" ] && echo "session: $SID" || echo "NO SESSION ID: the server did not answer (is it running on 8002?)"

curl -s -i -X POST localhost:8002/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' | head -1

curl -s -X POST localhost:8002/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

curl -s -X POST localhost:8002/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_forecast","arguments":{"city":"kochi","days":2}}}'

curl -s -X POST localhost:8002/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_current_weather","arguments":{"city":"Atlantis"}}}'
```

Or run the same flow as one script, with checks: `./test-http.sh` (in this folder).

Expected: `server up`, then `session: f261d380...` (a 32-character hex id; run
the initialize curl without the `SID=$(...)` wrapper to see the full `200 OK`
response with `"serverInfo":{"name":"weather"...}`); the notification returns
`HTTP/1.1 202 Accepted`;
`tools/list` returns the three tools; the forecast call returns
`"isError":false` with `"temp_c": 30` for day 1 and `27` for day 2; the Atlantis
call returns `"isError":true` and `UNKNOWN_CITY: 'Atlantis' is not a supported city. Try one of: Kochi, ...`.

### 4d. stdio: the Inspector CLI, then a raw pipe

Nothing needs to be running. Run from `weather-mcp/`.

```bash
npx -y @modelcontextprotocol/inspector@0.15.0 --cli ../.venv/bin/python mcp_server.py --method tools/list
npx -y @modelcontextprotocol/inspector@0.15.0 --cli ../.venv/bin/python mcp_server.py \
    --method tools/call --tool-name get_current_weather --tool-arg city=dubai
```

Expected: the three tools, then a result with `"temp_c\": 38,\n  \"condition\": \"Clear\"` and `"isError": false`.

Raw stdio, one JSON-RPC message per line (the `sleep 1` keeps stdin open until
the last reply has been written):

```bash
( echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stdio-test","version":"0"}}}'
  echo '{"jsonrpc":"2.0","method":"notifications/initialized"}'
  echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_current_weather","arguments":{"city":"dubai"}}}'
  sleep 1 ) | ../.venv/bin/python mcp_server.py
```

Expected: two lines. id 1 with `"serverInfo":{"name":"weather"`, id 2 with
`"city\": \"Dubai\"`, `"temp_c\": 38` and `"isError":false`.

### 4e. Claude Desktop and Claude Code

```bash
claude mcp add --transport http weather http://localhost:8002/mcp     # Claude Code, HTTP
```

Claude Desktop (stdio), in `claude_desktop_config.json` with absolute paths:

```json
{"mcpServers": {"weather": {
  "command": "/ABS/PATH/mcp-servers/.venv/bin/python",
  "args": ["/ABS/PATH/mcp-servers/weather-mcp/mcp_server.py"]}}}
```

Expected: ask "what's the weather in Kochi tomorrow?" and the assistant calls
`get_forecast` and answers 30 °C, partly cloudy.

## 5. What to try next

- **Add a tool**: `compare_cities(a, b)` in `service.py`, then wrap it in
  `mcp_server.py` and `app.py`.
- **Add a resource**: `weather://cities` returning the city list as text, to
  see how a client treats resources differently from tools.
- **Swap the data for a real API** behind `service.py` only; the tools and
  routes should not need to change. That is the payoff of the shared layer.
