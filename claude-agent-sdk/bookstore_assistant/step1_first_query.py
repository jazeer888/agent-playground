"""Lesson 1: the smallest possible Claude Agent SDK program.

One question in, a stream of messages out. No tools yet, on purpose: this
step only proves that the SDK is installed and your API key works.

Run:
    python bookstore_assistant/step1_first_query.py
    python bookstore_assistant/step1_first_query.py "your own question"
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

# The SDK reads ANTHROPIC_API_KEY from the process environment and does NOT
# load .env files itself, so we do it here, before the first query() call.
load_dotenv(Path(__file__).parent / ".env")

SYSTEM_PROMPT = (
    "You are the assistant for a small bookstore. "
    "Answer in two or three short sentences."
)


async def main(prompt: str) -> None:
    options = ClaudeAgentOptions(
        # A plain string replaces the default prompt entirely.
        system_prompt=SYSTEM_PROMPT,
        # allowed_tools = tools that run WITHOUT asking. Empty: nothing is pre-approved.
        allowed_tools=[],
        # "dontAsk" = deny anything that would otherwise need a permission prompt.
        # Together with the empty list above, this agent can only talk.
        permission_mode="dontAsk",
        # [] = ignore ~/.claude and project settings, so the script behaves the
        # same on every machine instead of inheriting your Claude Code setup.
        setting_sources=[],
        # Safety net: stop after a few model turns even if something loops.
        max_turns=3,
    )

    # query() is an async generator. Each `message` is one event in the agent
    # loop: what Claude said, which tool it called, and finally the result.
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            # Always the last message: status, turn count and estimated cost.
            cost = message.total_cost_usd
            cost_text = f"${cost:.4f}" if cost is not None else "n/a"
            print(
                f"\n[{message.subtype}] turns={message.num_turns} "
                f"cost~{cost_text} session={message.session_id}"
            )


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What can a bookstore assistant help me with?"
    asyncio.run(main(question))
