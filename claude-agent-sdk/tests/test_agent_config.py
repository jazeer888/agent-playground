"""Lesson 5b: the agent's configuration, tested as data.

ClaudeAgentOptions is a dataclass. The security of this agent is mostly what
is in it, so a careless edit ("just add purchase_book to allowed_tools") should
fail a test, not be discovered in production.
"""

from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

import step2_bookstore_tools as step2
import step3_permissions as step3


def test_only_read_tools_are_pre_approved():
    assert set(step2.READ_ONLY_TOOLS) == {
        "mcp__bookstore__list_books",
        "mcp__bookstore__search_books",
        "mcp__bookstore__get_book",
    }


def test_purchase_is_never_pre_approved():
    # If it were, can_use_tool would be skipped and nobody would be asked.
    for options in (step2.build_options(), step3.build_options()):
        assert step3.PURCHASE_TOOL not in options.allowed_tools
        assert not any("*" in name for name in options.allowed_tools)


def test_step2_cannot_buy_at_all():
    options = step2.build_options()
    assert options.permission_mode == "dontAsk"
    assert options.can_use_tool is None


def test_step3_routes_unapproved_calls_to_our_policy():
    options = step3.build_options()
    assert options.permission_mode == "default"
    assert options.can_use_tool is step3.can_use_tool


def test_agent_ignores_settings_and_stray_mcp_config():
    for options in (step2.build_options(), step3.build_options()):
        assert options.setting_sources == []
        assert options.strict_mcp_config is True
        assert list(options.mcp_servers) == ["bookstore"]


def test_tool_names_match_the_server_key():
    # mcp__<server key>__<tool>: rename the key and every name must follow.
    (key,) = step2.MCP_SERVERS
    assert all(name.startswith(f"mcp__{key}__") for name in step2.READ_ONLY_TOOLS)
    assert step3.PURCHASE_TOOL.startswith(f"mcp__{key}__")


def test_show_prints_text_tool_calls_and_results(capsys):
    """Messages are plain dataclasses, so a fake conversation is easy to build."""
    step2.show(
        AssistantMessage(
            content=[
                TextBlock(text="Let me check."),
                ToolUseBlock(id="t1", name="mcp__bookstore__get_book", input={"book_id": "b9"}),
            ],
            model="test-model",
        )
    )
    step2.show(UserMessage(content=[ToolResultBlock(tool_use_id="t1", content="Dune", is_error=False)]))
    step2.show(
        ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=2,
            session_id="s1",
            total_cost_usd=0.0123,
        )
    )

    out = capsys.readouterr().out
    assert "Let me check." in out
    assert "[tool call] mcp__bookstore__get_book {'book_id': 'b9'}" in out
    assert "[tool result] ok: Dune" in out
    assert "[success] turns=2 cost~$0.0123" in out
