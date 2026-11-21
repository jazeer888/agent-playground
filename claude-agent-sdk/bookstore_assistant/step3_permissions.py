"""Lesson 3: a human approves every purchase, enforced in code.

Step 2 blocked buying completely. Here the agent MAY call purchase_book, but
each call first passes through `can_use_tool`, a Python function we own:

    Claude wants a tool
        ├─ in allowed_tools?          -> runs, we are never asked   (the 3 read-only tools)
        └─ otherwise -> can_use_tool  -> our code returns Allow or Deny

The rule lives in `decide()`, a plain function with no SDK or network in it,
so lesson 5 can test it without a model.

Run (bookstore must be up on :8001):
    python bookstore_assistant/step3_permissions.py
    python bookstore_assistant/step3_permissions.py "Buy 5 copies of Dune for Asha"
"""

from __future__ import annotations

import asyncio
import sys
import warnings
from typing import Any, Callable

from claude_agent_sdk import (
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
    query,
)
from claude_agent_sdk.types import CanUseToolShadowedWarning

# Reuse lesson 2's connection, tool list and printer. (Importing it also loads .env.)
from step2_bookstore_tools import MCP_SERVERS, READ_ONLY_TOOLS, show

# The SDK warns that can_use_tool is never asked about tools in allowed_tools.
# That is exactly the design here (reads skip approval), so silence it.
warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)

PURCHASE_TOOL = "mcp__bookstore__purchase_book"
MAX_QUANTITY = 3  # a hard limit no prompt and no human "yes" can raise

SYSTEM_PROMPT = (
    "You are the assistant for a small bookstore. Use the bookstore tools to "
    "answer; never guess titles, prices or stock. Prices are in INR. "
    "To place an order call purchase_book; the shop owner approves each order. "
    "If an order is refused, tell the customer why and do not retry. Keep answers short."
)

PermissionResult = PermissionResultAllow | PermissionResultDeny


def decide(
    tool_name: str,
    tool_input: dict[str, Any],
    approve: Callable[[str], bool],
) -> PermissionResult:
    """The whole purchase policy. `approve` asks a human and returns True/False."""
    if tool_name != PURCHASE_TOOL:
        # Default deny: anything we did not plan for is refused.
        return PermissionResultDeny(message=f"{tool_name} is not permitted for this assistant.")

    quantity = tool_input.get("quantity")
    if not isinstance(quantity, int) or quantity < 1:
        return PermissionResultDeny(message="Quantity must be a whole number, 1 or more.")
    if quantity > MAX_QUANTITY:
        # Checked BEFORE asking the human: a hard rule should not depend on a tired owner.
        return PermissionResultDeny(
            message=f"Orders are limited to {MAX_QUANTITY} copies; {quantity} requested."
        )

    summary = (
        f"Order {quantity} x book {tool_input.get('book_id')} "
        f"for {tool_input.get('customer_name')}"
    )
    if approve(summary):
        return PermissionResultAllow()
    # The message goes back to Claude as the tool result, so it can explain.
    return PermissionResultDeny(message="The shop owner declined this order.")


def ask_in_terminal(summary: str) -> bool:
    answer = input(f"\n[approval needed] {summary}. Approve? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


async def can_use_tool(
    tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext
) -> PermissionResult:
    """The SDK calls this for every tool call that is not already approved."""
    # input() blocks, so run the decision in a thread to keep the event loop free.
    result = await asyncio.to_thread(decide, tool_name, tool_input, ask_in_terminal)
    print(f"[permission] {tool_name} -> {result.behavior}")
    return result


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers=MCP_SERVERS,
        allowed_tools=READ_ONLY_TOOLS,
        # "default", not "dontAsk": unapproved calls must reach can_use_tool
        # instead of being denied before our code sees them.
        permission_mode="default",
        can_use_tool=can_use_tool,
        setting_sources=[],
        strict_mcp_config=True,
        max_turns=8,
    )


async def main(prompt: str) -> None:
    async for message in query(prompt=prompt, options=build_options()):
        show(message)


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Buy 1 copy of Dune for Asha."
    asyncio.run(main(question))
