"""Lesson 2: give the agent real tools by connecting it to an MCP server.

Step 1's agent could only talk, so it invented abilities it did not have.
Here it is connected to mcp-servers/bookstore-mcp and may call the three
READ-ONLY tools. Buying stays blocked until lesson 3.

Start the bookstore first (other terminal):
    cd agent-playground/mcp-servers && ./run-all.sh

Run:
    python bookstore_assistant/step2_bookstore_tools.py
    python bookstore_assistant/step2_bookstore_tools.py "Do you have anything by Tagore?"
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

load_dotenv(Path(__file__).parent / ".env")

# Override with BOOKSTORE_MCP_URL when the server runs on another port.
BOOKSTORE_URL = os.environ.get("BOOKSTORE_MCP_URL", "http://localhost:8001/mcp")

SYSTEM_PROMPT = (
    "You are the assistant for a small bookstore. Use the bookstore tools to "
    "answer; never guess titles, prices or stock. Prices are in INR. "
    "You cannot place orders yet; say so if asked. Keep answers short."
)

# The key "bookstore" is OUR name for the server. It becomes the middle part
# of every tool name: mcp__<server key>__<tool name>.
MCP_SERVERS = {"bookstore": {"type": "http", "url": BOOKSTORE_URL}}

# Only the read-only tools are pre-approved. purchase_book and list_orders
# exist on the server but are not listed, so "dontAsk" denies them.
READ_ONLY_TOOLS = [
    "mcp__bookstore__list_books",
    "mcp__bookstore__search_books",
    "mcp__bookstore__get_book",
]


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers=MCP_SERVERS,
        allowed_tools=READ_ONLY_TOOLS,
        permission_mode="dontAsk",
        setting_sources=[],
        # Use only the servers above; ignore any .mcp.json lying around.
        strict_mcp_config=True,
        max_turns=6,
    )


def show(message) -> None:
    """Print one event from the agent loop in a readable form."""
    if isinstance(message, SystemMessage) and message.subtype == "init":
        # First message of every run. Tells us whether the MCP server connected.
        for server in message.data.get("mcp_servers", []):
            print(f"[mcp] {server.get('name')}: {server.get('status')}")
    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)
            elif isinstance(block, ToolUseBlock):
                # Claude decided to call a tool. The SDK runs it for us.
                print(f"[tool call] {block.name} {block.input}")
    elif isinstance(message, UserMessage) and isinstance(message.content, list):
        # Tool results travel back to Claude as a "user" message.
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                status = "error" if block.is_error else "ok"
                print(f"[tool result] {status}: {str(block.content)[:200]}")
    elif isinstance(message, ResultMessage):
        cost = message.total_cost_usd
        cost_text = f"${cost:.4f}" if cost is not None else "n/a"
        print(f"\n[{message.subtype}] turns={message.num_turns} cost~{cost_text}")


async def main(prompt: str) -> None:
    async for message in query(prompt=prompt, options=build_options()):
        show(message)


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Which books do you have under 400 rupees, and are they in stock?"
    asyncio.run(main(question))
