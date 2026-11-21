"""Lesson 4: the finished agent, a multi-turn chat in the terminal.

query() (lessons 1-3) starts a NEW session on every call, so the agent forgets
everything between questions. ClaudeSDKClient keeps ONE session open:

    async with ClaudeSDKClient(options) as client:   # connect once
        await client.query("...")                    # send a turn
        async for message in client.receive_response():   # read until ResultMessage
            ...
        await client.query("and the second one?")    # same session, context kept

Everything else is reused: the MCP connection and printer from lesson 2, the
purchase policy from lesson 3.

Run (bookstore must be up on :8001):
    python bookstore_assistant/agent.py
"""

from __future__ import annotations

import asyncio

from claude_agent_sdk import ClaudeSDKClient

from step2_bookstore_tools import show
from step3_permissions import build_options

EXIT_WORDS = {"quit", "exit", "q"}


async def read_line(prompt: str) -> str | None:
    """Read one line without blocking the event loop. None means end of input."""
    try:
        return (await asyncio.to_thread(input, prompt)).strip()
    except EOFError:
        return None


async def chat() -> None:
    print("Bookstore assistant. Type 'quit' to leave.\n")
    # `async with` connects on entry and always disconnects on exit,
    # even if something below raises.
    async with ClaudeSDKClient(options=build_options()) as client:
        while True:
            user_text = await read_line("you> ")
            if user_text is None or user_text.lower() in EXIT_WORDS:
                break
            if not user_text:
                continue

            await client.query(user_text)
            # receive_response() yields this turn's messages and stops after
            # its ResultMessage. Let it finish; do not `break` out of it.
            async for message in client.receive_response():
                show(message)
            print()
    print("Bye.")


if __name__ == "__main__":
    try:
        asyncio.run(chat())
    except KeyboardInterrupt:
        print("\nBye.")
