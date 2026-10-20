#!/usr/bin/env bash
# The raw MCP-over-HTTP conversation from README section 4c, as one script.
# Needs the server running:  python app.py   (or ../run-all.sh)
#
#   ./test-http.sh            talks to http://localhost:8001/mcp
set -euo pipefail
URL="http://localhost:${PORT:-8001}/mcp"
H='Content-Type: application/json'
A='Accept: application/json, text/event-stream'      # both headers are required by the protocol

curl -sf "${URL%/mcp}/api/health" >/dev/null || { echo "Server not running at $URL. Start it: python app.py"; exit 1; }

echo "== 1. initialize (session id comes back in the mcp-session-id header)"
SID=$(curl -s -i -X POST "$URL" -H "$H" -H "$A" -d '{"jsonrpc":"2.0","id":1,"method":"initialize",
  "params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test-http.sh","version":"0"}}}' \
  | grep -i '^mcp-session-id:' | awk '{print $2}' | tr -d '\r')
[ -n "$SID" ] || { echo "No session id in the response"; exit 1; }
echo "session: $SID"

echo "== 2. notifications/initialized (a notification: expect 202, no body)"
curl -s -i -X POST "$URL" -H "$H" -H "$A" -H "mcp-session-id: $SID" \
     -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' | head -1

rpc() {  # rpc <id> <method> [params-json]   -> prints the JSON-RPC reply (the data: line)
  local params=${3:-null}
  curl -s -X POST "$URL" -H "$H" -H "$A" -H "mcp-session-id: $SID" \
       -d "{\"jsonrpc\":\"2.0\",\"id\":$1,\"method\":\"$2\",\"params\":$params}" | sed -n 's/^data: //p'
}

echo "== 3. tools/list";       rpc 2 tools/list | cut -c1-200; echo "..."
echo "== 4. tools/call search_books dune"
rpc 3 tools/call '{"name":"search_books","arguments":{"query":"dune"}}'
echo "== 5. resources/read bookstore://catalog"
rpc 4 resources/read '{"uri":"bookstore://catalog"}' | cut -c1-200; echo "..."
echo "== 6. an expected error: purchase_book b5 (out of stock) -> isError true"
rpc 5 tools/call '{"name":"purchase_book","arguments":{"book_id":"b5","quantity":1,"customer_name":"test"}}'
echo "== done"
