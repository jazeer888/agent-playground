"""Lesson 6 tests: the web layer, still without a model or a running server."""

from __future__ import annotations

import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

import web
from step3_permissions import PURCHASE_TOOL

ORDER = {"book_id": "b9", "quantity": 1, "customer_name": "Asha"}


class FakeRequest:
    def __init__(self, **headers: str):
        self.headers = headers


def test_messages_become_page_events():
    assert web.to_events(
        SystemMessage(subtype="init", data={"mcp_servers": [{"name": "bookstore", "status": "connected"}]})
    ) == [{"type": "mcp", "name": "bookstore", "status": "connected"}]

    assert web.to_events(
        AssistantMessage(
            content=[TextBlock(text="hi"), ToolUseBlock(id="t", name="mcp__bookstore__get_book", input={"book_id": "b1"})],
            model="m",
        )
    ) == [
        {"type": "text", "text": "hi"},
        {"type": "tool_call", "name": "mcp__bookstore__get_book", "input": {"book_id": "b1"}},
    ]

    assert web.to_events(UserMessage(content=[ToolResultBlock(tool_use_id="t", content="boom", is_error=True)])) == [
        {"type": "tool_result", "ok": False, "text": "boom"}
    ]

    result = ResultMessage(
        subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
        num_turns=2, session_id="s", total_cost_usd=0.5,
    )
    assert web.to_events(result) == [{"type": "done", "status": "success", "turns": 2, "cost": 0.5}]


def test_plain_user_text_produces_no_events():
    assert web.to_events(UserMessage(content="hello")) == []


def test_requests_from_other_sites_are_rejected():
    json_type = {"content-type": "application/json"}
    # Same page, or a non-browser client that sends no Origin: accepted.
    assert web.rejected(FakeRequest(**json_type)) is None
    assert web.rejected(FakeRequest(origin=f"http://127.0.0.1:{web.PORT}", **json_type)) is None
    # A form post (what a hostile page can send without a CORS preflight): refused.
    assert web.rejected(FakeRequest(**{"content-type": "text/plain"})).status_code == 415
    # Another site: refused.
    assert web.rejected(FakeRequest(origin="https://evil.example", **json_type)).status_code == 403


def run_purchase_with_browser_answer(answer: bool | None, tool_input=ORDER, timeout=120):
    """Drive web.can_use_tool; 'click' the approval card as soon as it appears."""

    async def scenario():
        web.state.events = asyncio.Queue()
        web.state.pending.clear()
        web.APPROVAL_TIMEOUT_SECONDS = timeout
        call = asyncio.create_task(web.can_use_tool(PURCHASE_TOOL, tool_input, ToolPermissionContext()))
        seen = []
        while not call.done():
            try:
                event = await asyncio.wait_for(web.state.events.get(), 0.05)
            except asyncio.TimeoutError:
                continue
            seen.append(event)
            if event["type"] == "approval" and answer is not None:
                web.state.pending[event["id"]].set_result(answer)
        while not web.state.events.empty():
            seen.append(web.state.events.get_nowait())
        return await call, seen

    try:
        return asyncio.run(scenario())
    finally:
        web.APPROVAL_TIMEOUT_SECONDS = 120


def test_browser_approve_allows_the_order():
    result, events = run_purchase_with_browser_answer(True)
    assert isinstance(result, PermissionResultAllow)
    assert [e["type"] for e in events] == ["approval", "permission"]
    assert events[0]["summary"] == "Order 1 x book b9 for Asha"


def test_browser_decline_denies_the_order():
    result, _ = run_purchase_with_browser_answer(False)
    assert isinstance(result, PermissionResultDeny)


def test_no_answer_in_time_counts_as_no():
    result, events = run_purchase_with_browser_answer(None, timeout=0.1)
    assert isinstance(result, PermissionResultDeny)
    assert web.state.pending == {}  # nothing left to click later


def test_over_limit_never_shows_an_approval_card():
    result, events = run_purchase_with_browser_answer(True, tool_input={**ORDER, "quantity": 5})
    assert isinstance(result, PermissionResultDeny)
    assert [e["type"] for e in events] == ["permission"]


def test_web_agent_keeps_the_same_guardrails():
    options = web.web_options()
    assert PURCHASE_TOOL not in options.allowed_tools
    assert options.permission_mode == "default"
    assert options.can_use_tool is web.can_use_tool
