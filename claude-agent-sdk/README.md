# Claude Agent SDK samples (Python)

## bookstore_assistant

A terminal assistant for the bookstore in `mcp-servers/bookstore-mcp`. Built
in small steps, one concept per file, so each step can be run and read alone.

| Step | File | Concept | Status |
|---|---|---|---|
| 1 | `step1_first_query.py` | `query()`, `ClaudeAgentOptions`, the message stream | written |
| 2 | `step2_bookstore_tools.py` | Connect to the bookstore over MCP (HTTP), read-only tools | written |
| 3 | `step3_permissions.py` | `purchase_book` behind an approval check in code | written |
| 4 | `agent.py` | Multi-turn chat with `ClaudeSDKClient` | written |
| 5 | `tests/` | Test the permission logic without a model | written |
| 6 | `web.py` + `static/index.html` | The same agent behind a small web chat page | written |

### Run step 1

```bash
cd agent-playground/claude-agent-sdk
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
printf 'ANTHROPIC_API_KEY=your-api-key\n' > bookstore_assistant/.env   # then paste your real key
python bookstore_assistant/step1_first_query.py
```

The key comes from the Claude Console (https://platform.claude.com/). `.env`
is git-ignored. The SDK needs Python 3.10+. Its wheel bundles the Claude Code
binary, so nothing else has to be installed.

### What step 1 teaches

1. **The SDK is the Claude Code agent loop as a library.** You do not write
   the loop (call model, run tool, feed result back). You configure it and
   read what comes out.
2. **`query()` is a stream, not a return value.** It yields messages as the
   agent works. `AssistantMessage` carries content blocks (`TextBlock`,
   `ToolUseBlock`); `ResultMessage` is always last and carries status,
   turn count and estimated cost.
3. **`ClaudeAgentOptions` is the whole configuration.** System prompt, tools,
   permissions, MCP servers and limits all live in this one object.
4. **`allowed_tools` approves, it does not restrict.** It lists tools that run
   without asking. What happens to everything else is decided by
   `permission_mode`; `"dontAsk"` denies it.
5. **The SDK does not read `.env`.** It reads the process environment, so the
   script calls `load_dotenv` first.

### Run step 2

Start the bookstore from this repo in another terminal
(`cd ../mcp-servers && ./run-all.sh`), then:

```bash
python bookstore_assistant/step2_bookstore_tools.py
python bookstore_assistant/step2_bookstore_tools.py "Buy me the cheapest book"
```

If the server is on another port, set `BOOKSTORE_MCP_URL`, for example
`BOOKSTORE_MCP_URL=http://localhost:8011/mcp`.

### What step 2 teaches

1. **Your own tools reach the agent as MCP servers.** `mcp_servers` maps a
   name you choose to a connection: `{"type": "http", "url": ...}` here.
2. **Tool names are `mcp__<server key>__<tool name>`.** The key is the one in
   your `mcp_servers` dict, not the name the server gives itself.
3. **Least privilege is a list.** Only the three read-only tools are in
   `allowed_tools`. `purchase_book` is on the server but not approved, so
   `"dontAsk"` denies it. The prompt also says "you cannot order", but that
   line is a request; the list is the guarantee.
4. **The `init` message reports MCP health.** A `SystemMessage` with subtype
   `init` arrives first and lists each server as `connected` or `failed`.
5. **Tool results come back as a `UserMessage`.** The loop is: assistant
   asks for a tool, the SDK runs it, the result is fed back as user content.
6. **MCP tools are loaded on demand.** The first call you see is
   `ToolSearch`: the agent fetches the tool definitions it needs instead of
   carrying every tool in its context.

Seeing `Dynamic Client Registration rejected (HTTP 404)` means the server
answered a tool call with 401 and the SDK tried to start an OAuth login.
The server in this repo has no auth, so check which process owns the port:
`lsof -nP -iTCP:8001 -sTCP:LISTEN`.

### Run step 3

```bash
python bookstore_assistant/step3_permissions.py                                   # answer y, then try n
python bookstore_assistant/step3_permissions.py "Buy 5 copies of Dune for Asha"   # refused, no question asked
```

### What step 3 teaches

1. **`can_use_tool` is your code in the permission path.** The SDK calls it
   with the tool name and input for any call that is not already approved;
   you return `PermissionResultAllow()` or `PermissionResultDeny(message=...)`.
2. **The order of checks matters.** `allowed_tools` is consulted first, so
   the three read tools never reach the callback. `permission_mode` must be
   `"default"`: with `"dontAsk"` the call is denied before your code runs.
3. **A deny message is a tool result.** Claude receives it as an error and
   explains it to the customer, so write it for the model to read.
4. **Hard rules come before the human.** The quantity limit is checked
   first; no prompt and no "yes" can raise it.
5. **Keep the policy a pure function.** `decide()` knows nothing about the
   SDK's process or the network, which is what makes step 5 possible.

`can_use_tool` only sees calls that would otherwise prompt. To inspect every
call, including pre-approved ones, the SDK offers `PreToolUse` hooks instead.

### Run step 4

```bash
python bookstore_assistant/agent.py
```

Try: "Do you have anything by Frank Herbert?", then "How much would 2 copies
of that one cost?", then "Buy them for Meera." The second and third messages
only make sense if the agent remembers the first.

### What step 4 teaches

1. **`query()` forgets, `ClaudeSDKClient` remembers.** Each `query()` call is
   a new session. The client keeps one session open, so every turn sees the
   earlier ones.
2. **Send and receive are separate.** `await client.query(text)` sends a
   turn; `client.receive_response()` yields that turn's messages and stops
   after its `ResultMessage`.
3. **`async with` owns the connection.** It connects on entry and
   disconnects on exit, including when an error is raised.
4. **Do not `break` out of the message loop.** Let `receive_response()`
   finish; leaving early can cause asyncio clean-up problems.
5. **Options carry over unchanged.** The same `build_options()` from step 3
   drives the chat, so the purchase approval still applies on every turn.

### Run step 5

```bash
pip install -r requirements-dev.txt
pytest             # no network, no model calls, no bookstore server
```

### What step 5 teaches

1. **Test the decision, not the model.** `test_purchase_policy.py` calls
   `decide()` with a `FakeOwner` in place of the person at the terminal. It
   checks that a hard rule wins even when the owner would say yes.
2. **Configuration is data, so test it.** `test_agent_config.py` asserts that
   `purchase_book` is never in `allowed_tools`, that step 3 routes to our
   callback, and that settings files are ignored. A careless edit fails a
   test instead of quietly removing the approval step.
3. **Messages are dataclasses.** A fake conversation is built by hand to
   test the printer; nothing has to be mocked.
4. **Know what is not covered.** The agent loop itself runs inside the
   bundled Claude Code binary and is not exercised here: these tests do not
   prove the model calls the right tool. The ADK sample goes further by
   swapping in a scripted fake model. The SDK accepts a custom `transport`,
   which may allow the same; that is not tried here.

### Run step 6 (web chat)

```bash
python bookstore_assistant/web.py      # then open http://127.0.0.1:8003
```

Ask about a book, then ask to buy it: an approval card appears with
Approve and Decline buttons. Tool calls show as small expandable rows.

### What step 6 teaches

1. **The agent did not change, only its edges did.** `print()` became a
   stream of JSON lines (one event per line) and `input()` became an
   approval card. `decide()` is reused untouched, with the browser as the
   "human".
2. **Waiting for a click is a future.** The permission callback creates an
   `asyncio.Future`, sends an `approval` event, and waits. `POST
   /api/approve` resolves it. No answer in 120 seconds counts as no.
3. **Read the SDK's response to the end.** Each turn runs as its own task,
   so closing the tab mid-answer does not leave the session half-read.
4. **A local page still needs a guard.** Any website you visit can make
   your browser POST to `localhost`. The server accepts only JSON requests
   from its own origin, so another site cannot chat with, or approve
   purchases for, your agent.
5. **Treat tool output as data.** The page draws everything with
   `textContent`, so a book title containing HTML cannot become markup.

Limits, on purpose: one server process is one conversation (restart to
start over), there is no login, and it listens on `127.0.0.1` only. The
cost shown is the running total for the session, not per message.

### Compared with the ADK sample

| | Google ADK (`adk/`) | Claude Agent SDK |
|---|---|---|
| You define | An `LlmAgent` object | Options for a ready-made agent loop |
| Run it with | `adk web` / runner | `query()` or `ClaudeSDKClient` |
| Built-in tools | `google_search` | File, shell and web tools (off in this sample) |
| Your own tools | Python functions | MCP servers (in-process or remote) |
| Hard rules | Model callbacks | Permission modes, `can_use_tool`, hooks |
