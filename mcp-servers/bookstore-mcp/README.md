# bookstore-mcp

## 1. What this server is

A tiny bookstore with ten books in memory. Humans use the web page or the REST
API; AI agents use the same store through MCP. It exposes five tools
(`list_books`, `search_books`, `get_book`, `purchase_book`, `list_orders`) and
one resource (`bookstore://catalog`). Buying a book reduces stock, so you can
watch two different clients affect one shared state.

## 2. How it is built

```
 browser  ──► GET /            index.html (plain HTML + fetch)
 curl     ──► /api/books ...   FastAPI routes          ─┐
                                                         ├─► service.py ─► data.py
 agent    ──► POST /mcp        MCP app (Streamable HTTP)─┘
 Claude Desktop ──► python mcp_server.py   (stdio, same tools)
```

| File | Role |
|---|---|
| `data.py` | Seed list of books. Never changes at run time. |
| `service.py` | The only business logic: lookups, stock rule, order IDs, typed errors. |
| `app.py` | FastAPI: REST routes, the UI, and `app.mount("/", mcp.streamable_http_app())`. |
| `mcp_server.py` | MCP tools and the resource; each one calls `service.py`. Also the stdio entry point. |
| `static/index.html` | The UI. Talks to `/api` only. |

**Tools vs resources.** A tool *does* something when the agent decides to call
it (`purchase_book`). A resource is *content to read*, named by a URI
(`bookstore://catalog`), like opening a file for context. Tools can change
state; resources should not.

**Streamable HTTP vs stdio.** Over HTTP the client POSTs JSON-RPC messages to
`/mcp` and the server answers (as JSON or as a short event stream). A session
ID header ties the calls together. Any machine can connect, which is what you
want for testing remote agents. Over stdio the client launches
`python mcp_server.py` itself and talks through stdin/stdout. Only local, no
ports, which is how Claude Desktop runs servers.

**Errors.** `service.py` raises typed errors (`BookNotFound`, `OutOfStock`,
`InvalidQuantity`). REST maps them to 404/409/400 JSON; MCP maps them to a tool
result with `isError: true` and the message, so the agent can recover.

## 3. How to run it

```bash
cd mcp-servers
python3.12 -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r bookstore-mcp/requirements.txt
cd bookstore-mcp && python app.py                          # http://127.0.0.1:8001
```

Open http://localhost:8001 in a browser: search, click a book, place an order.

### Two ways to serve the same tools

| Transport | Command | When |
|---|---|---|
| Streamable HTTP | `python app.py` → MCP at `http://localhost:8001/mcp` (plus REST and the UI) | remote agents, ADK, Claude Code, Inspector by URL |
| stdio | `python mcp_server.py` (the client starts it; you never run it by hand) | Claude Desktop, Inspector by command, local scripts |

Both import the same `mcp` object from `mcp_server.py`, so a tool you add
appears in both at once. In stdio mode stdout *is* the protocol channel, which
is why nothing in the code uses `print()`.

## 4. How to test it (easy to hard)

### 4a. REST with curl

```bash
curl -s localhost:8001/api/health
curl -s "localhost:8001/api/books/search?q=kim"
curl -s -X POST localhost:8001/api/orders -H 'Content-Type: application/json' \
     -d '{"book_id":"b3","quantity":1,"customer_name":"Jazeer"}'
curl -s -i -X POST localhost:8001/api/orders -H 'Content-Type: application/json' \
     -d '{"book_id":"b5","quantity":1,"customer_name":"Jazeer"}' | head -1
```

Expected, in order:

```
{"status":"ok","service":"bookstore","mcp":"/mcp"}
[{"id":"b4","title":"The Phoenix Project",...},{"id":"b6","title":"Accelerate",...}]
{"order_id":"ord-0001","book_id":"b3","title":"Designing Data-Intensive Applications","quantity":1,"customer_name":"Jazeer","total":3299.0,"placed_at":"2026-..."}
HTTP/1.1 409 Conflict          <- b5 is out of stock on purpose; body says OUT_OF_STOCK
```

### 4b. MCP Inspector (a UI for any MCP server)

```bash
npx -y @modelcontextprotocol/inspector@0.15.0
```

A browser tab opens. Choose **Transport: Streamable HTTP**, URL
`http://localhost:8001/mcp`, click **Connect**, then **Tools > List Tools**.
Expected: five tools with their descriptions. Click `search_books`, enter
`query = dune`, **Run Tool**: a result with Dune, stock 7. Under
**Resources**, `bookstore://catalog` shows the text catalog.

CLI mode, no browser:

```bash
npx -y @modelcontextprotocol/inspector@0.15.0 --cli http://localhost:8001/mcp --transport http --method tools/list
npx -y @modelcontextprotocol/inspector@0.15.0 --cli http://localhost:8001/mcp --transport http \
    --method tools/call --tool-name purchase_book --tool-arg book_id=b9 --tool-arg quantity=2 --tool-arg customer_name=Inspector
```

Expected: `{"tools": [ {"name": "list_books", ...} ... ]}` and then a result
whose `text` contains `"order_id": "ord-0002"` (or the next number).

### 4c. Raw MCP over HTTP with curl

This is what every MCP client does under the hood. Three steps: `initialize`,
tell the server you are ready, then use tools. The server gives you a session
ID in the `mcp-session-id` response header; send it back on every later call.
Two headers are required on every request. The server must be running
(`python app.py`, or `./run-all.sh`); `curl -s` prints nothing at all when
nothing is listening, so the block starts with a health check.

First, `initialize` on its own, with `-i` so you can see the headers:

```bash
curl -sf localhost:8001/api/health >/dev/null && echo "server up" || echo "NOT RUNNING: start it with  cd bookstore-mcp && python app.py"

H='Content-Type: application/json'
A='Accept: application/json, text/event-stream'

curl -s -i -X POST localhost:8001/mcp -H "$H" -H "$A" -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
  "params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

Expected: `server up`, then `HTTP/1.1 200 OK`, a header `mcp-session-id: 0845ed5f...`,
then `data: {"jsonrpc":"2.0","id":1,"result":{"capabilities":{...},"instructions":"A small bookstore...","serverInfo":{"name":"bookstore"...}}}`.

Now the whole conversation. The first command repeats `initialize` but keeps
only the session id in `$SID` (a literal placeholder such as `SID=<paste>` is
a shell syntax error, since `<` and `>` are redirections). Then: the
`notifications/initialized` notification (no `id`, so only a status line),
`tools/list`, a `tools/call`, and `resources/read`.

```bash
SID=$(curl -s -i -X POST localhost:8001/mcp -H "$H" -H "$A" -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
  "params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  | grep -i '^mcp-session-id:' | awk '{print $2}' | tr -d '\r')
[ -n "$SID" ] && echo "session: $SID" || echo "NO SESSION ID: the server did not answer (is it running on 8001?)"

curl -s -i -X POST localhost:8001/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' | head -1

curl -s -X POST localhost:8001/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

curl -s -X POST localhost:8001/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_books","arguments":{"query":"dune"}}}'

curl -s -X POST localhost:8001/mcp -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","id":4,"method":"resources/read","params":{"uri":"bookstore://catalog"}}'
```

Or run the same flow as one script, with checks: `./test-http.sh` (in this folder).

Expected: `session: <32 hex characters>`, then `HTTP/1.1 202 Accepted` for the notification; step 3 `data: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"list_books",...` (5 tools);
step 4 a result with `"isError":false` and `"structuredContent":{"result":[{"id":"b9","title":"Dune",...}]}`;
step 5 `"contents":[{"mimeType":"text/plain","text":"Bookstore catalog ...`.
Forget the session header and you get `400 Bad Request: Missing session ID`.
Call `purchase_book` for `b5` and you get `"isError":true` with `OUT_OF_STOCK: Only 0 copies ...`.

### 4d. stdio: the Inspector CLI, then a raw pipe

Nothing needs to be running for this. Run from `bookstore-mcp/`.

```bash
npx -y @modelcontextprotocol/inspector@0.15.0 --cli ../.venv/bin/python mcp_server.py --method tools/list
npx -y @modelcontextprotocol/inspector@0.15.0 --cli ../.venv/bin/python mcp_server.py \
    --method tools/call --tool-name get_book --tool-arg book_id=b9
```

Expected: the same five tools as over HTTP, then a result whose `text` starts
`{\n  \"id\": \"b9\",\n  \"title\": \"Dune\"` with `"isError": false`.

Raw stdio is one JSON-RPC message per line on stdin, one reply per line on
stdout. No session header: the process is the session. The `sleep 1` keeps
stdin open long enough for the last reply to arrive before the process exits.

```bash
( echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stdio-test","version":"0"}}}'
  echo '{"jsonrpc":"2.0","method":"notifications/initialized"}'
  echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
  echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get_book","arguments":{"book_id":"b9"}}}'
  sleep 1 ) | ../.venv/bin/python mcp_server.py
```

Expected: three lines, one per request id, each starting `{"jsonrpc":"2.0","id":N,"result":...`:
id 1 has `"serverInfo":{"name":"bookstore"`, id 2 lists the tools, id 3 has
`"title\": \"Dune\"` and `"isError":false`. The notification gets no reply.

### 4e. Claude Desktop and Claude Code

**Claude Code** (HTTP, server must be running):

```bash
claude mcp add --transport http bookstore http://localhost:8001/mcp
```

Then in a session: "search the bookstore for dune and buy one copy for Jazeer".

**Claude Desktop** (stdio: Desktop launches the server itself). Add to
`claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`),
using absolute paths, then restart Desktop:

```json
{"mcpServers": {"bookstore": {
  "command": "/ABS/PATH/mcp-servers/.venv/bin/python",
  "args": ["/ABS/PATH/mcp-servers/bookstore-mcp/mcp_server.py"]}}}
```

Expected: a tools icon in the chat input listing the five bookstore tools.

## 5. What to try next

- **Add a tool** in three steps: a function in `service.py`, a `@mcp.tool()`
  wrapper in `mcp_server.py`, a route in `app.py`. Try `cancel_order(order_id)`.
- **Add auth**: today anyone who can reach `/mcp` can buy. Require a verified
  identity per agent (HelixID) before `purchase_book` runs.
- **Connect your own agent**: ADK's `McpToolset` with
  `StreamableHTTPConnectionParams(url="http://localhost:8001/mcp")`.
