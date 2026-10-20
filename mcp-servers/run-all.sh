#!/usr/bin/env bash
# Starts both MCP servers in one terminal. Ctrl-C stops both.
#
#   ./run-all.sh            uses ./.venv if present, else whatever `python` is on PATH
#
# Bookstore -> http://localhost:8001  (UI at /, REST at /api, MCP at /mcp)
# Weather   -> http://localhost:8002  (REST at /api, MCP at /mcp)

set -euo pipefail
cd "$(dirname "$0")"

PY="python"
[ -x ".venv/bin/python" ] && PY="$(pwd)/.venv/bin/python"

( cd bookstore-mcp && exec "$PY" app.py ) &
BOOK=$!
( cd weather-mcp && exec "$PY" app.py ) &
WEATHER=$!

trap 'echo; echo "Stopping..."; kill $BOOK $WEATHER 2>/dev/null; wait $BOOK $WEATHER 2>/dev/null || true' INT TERM EXIT

echo "bookstore pid=$BOOK  http://localhost:8001"
echo "weather   pid=$WEATHER  http://localhost:8002"
echo "Press Ctrl-C to stop both."
wait
