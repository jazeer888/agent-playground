"""Lesson 6: the same agent behind a small web page instead of the terminal.

Nothing about the agent changes. Two things move from the terminal to HTTP:

    terminal (agent.py)                 browser (this file)
    ───────────────────                 ───────────────────
    print(message)             ->       one JSON line per event, streamed to the page
    input("Approve? [y/N]")    ->       an "approval" event, answered by POST /api/approve

The purchase rule is still `decide()` from lesson 3. Only the "ask a human"
function is different, which is why it was an argument in the first place.

One server process holds ONE conversation (one ClaudeSDKClient). That is right
for a local learning tool and wrong for a multi-user app.

Run (bookstore must be up on :8001):
    python bookstore_assistant/web.py        then open http://127.0.0.1:8003
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import uvicorn
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from step3_permissions import SYSTEM_PROMPT, PermissionResult, build_options, decide

HOST = "127.0.0.1"  # this machine only; there is no login on this page
PORT = 8003
APPROVAL_TIMEOUT_SECONDS = 120  # no answer in time counts as "no"
PAGE = Path(__file__).parent / "static" / "index.html"
ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


class Conversation:
    """Everything the server remembers: one client, one turn at a time."""

    def __init__(self) -> None:
        self.client: ClaudeSDKClient | None = None
        self.turn_lock = asyncio.Lock()
        self.events: asyncio.Queue[dict[str, Any] | None] | None = None  # current turn's stream
        self.pending: dict[str, asyncio.Future[bool]] = {}  # approvals awaiting a click


state = Conversation()


async def emit(event: dict[str, Any]) -> None:
    if state.events is not None:
        await state.events.put(event)


# --- messages -> events ----------------------------------------------------------------


def to_events(message: Any) -> list[dict[str, Any]]:
    """Turn one SDK message into plain dicts the page can draw. Pure function."""
    events: list[dict[str, Any]] = []
    if isinstance(message, SystemMessage) and message.subtype == "init":
        for server in message.data.get("mcp_servers", []):
            events.append({"type": "mcp", "name": server.get("name"), "status": server.get("status")})
    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                events.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolUseBlock):
                events.append({"type": "tool_call", "name": block.name, "input": block.input})
    elif isinstance(message, UserMessage) and isinstance(message.content, list):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                events.append(
                    {"type": "tool_result", "ok": not block.is_error, "text": str(block.content)[:400]}
                )
    elif isinstance(message, ResultMessage):
        events.append(
            {
                "type": "done",
                "status": message.subtype,
                "turns": message.num_turns,
                "cost": message.total_cost_usd,
            }
        )
    return events


# --- approval: the browser is the human ----------------------------------------------


async def ask_browser(summary: str) -> bool:
    """Show an approval card on the page and wait for Approve / Decline."""
    approval_id = uuid.uuid4().hex
    answer: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    state.pending[approval_id] = answer
    await emit({"type": "approval", "id": approval_id, "summary": summary})
    try:
        return await asyncio.wait_for(answer, APPROVAL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return False
    finally:
        state.pending.pop(approval_id, None)


async def can_use_tool(
    tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
) -> PermissionResult:
    loop = asyncio.get_running_loop()

    def approve(summary: str) -> bool:
        # decide() is synchronous and runs in a worker thread; hop back to the
        # event loop to talk to the browser, and block the thread until it answers.
        return asyncio.run_coroutine_threadsafe(ask_browser(summary), loop).result()

    result = await asyncio.to_thread(decide, tool_name, tool_input, approve)
    await emit(
        {
            "type": "permission",
            "tool": tool_name,
            "behavior": result.behavior,
            "message": getattr(result, "message", ""),
        }
    )
    return result


def web_options():
    return replace(
        build_options(),
        can_use_tool=can_use_tool,
        system_prompt=SYSTEM_PROMPT + " Reply in plain text, without Markdown.",
    )


# --- one turn ---------------------------------------------------------------------------


async def run_turn(text: str, events: asyncio.Queue) -> None:
    """Send one user message and forward everything the agent does.

    Runs as its own task so the SDK's response is always read to the end, even
    if the browser tab closes halfway through.
    """
    async with state.turn_lock:
        try:
            await state.client.query(text)
            async for message in state.client.receive_response():
                for event in to_events(message):
                    await events.put(event)
        except Exception as error:  # show it on the page instead of a dead stream
            await events.put({"type": "error", "text": f"{type(error).__name__}: {error}"})
        finally:
            await events.put(None)  # end of this turn's stream


# --- HTTP --------------------------------------------------------------------------------


def rejected(request: Request) -> JSONResponse | None:
    """Refuse requests a web page on another site could make this browser send.

    Without this, any site you visit could POST to localhost and chat with, or
    approve purchases for, your agent.
    """
    if not request.headers.get("content-type", "").startswith("application/json"):
        return JSONResponse({"error": "JSON only"}, status_code=415)
    origin = request.headers.get("origin")
    if origin is not None and origin not in ALLOWED_ORIGINS:
        return JSONResponse({"error": "wrong origin"}, status_code=403)
    return None


async def index(request: Request) -> FileResponse:
    return FileResponse(PAGE)


async def chat(request: Request):
    if (problem := rejected(request)) is not None:
        return problem
    text = str((await request.json()).get("text", "")).strip()
    if not text:
        return JSONResponse({"error": "empty message"}, status_code=400)
    if state.turn_lock.locked():
        return JSONResponse({"error": "the assistant is still answering"}, status_code=409)

    events: asyncio.Queue = asyncio.Queue()
    state.events = events
    turn = asyncio.create_task(run_turn(text, events))

    async def stream():
        while (event := await events.get()) is not None:
            yield json.dumps(event) + "\n"  # one JSON object per line
        await turn

    return StreamingResponse(stream(), media_type="application/x-ndjson")


async def approve(request: Request) -> JSONResponse:
    if (problem := rejected(request)) is not None:
        return problem
    body = await request.json()
    answer = state.pending.get(str(body.get("id")))
    if answer is None or answer.done():
        return JSONResponse({"error": "no such pending approval"}, status_code=404)
    answer.set_result(body.get("approve") is True)  # anything but true means no
    return JSONResponse({"ok": True})


@asynccontextmanager
async def lifespan(app: Starlette):
    # Connect once when the server starts; disconnect when it stops.
    async with ClaudeSDKClient(options=web_options()) as client:
        state.client = client
        yield
    state.client = None


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/", index),
        Route("/api/chat", chat, methods=["POST"]),
        Route("/api/approve", approve, methods=["POST"]),
    ],
)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
