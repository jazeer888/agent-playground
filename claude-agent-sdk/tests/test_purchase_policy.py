"""Lesson 5a: the purchase policy, tested as a plain function.

No model, no network, no bookstore server. `decide()` takes the "ask a human"
step as an argument, so each test passes in a fake human that answers
instantly and records what it was asked.
"""

from __future__ import annotations

import asyncio

import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

import step3_permissions as policy

ORDER = {"book_id": "b9", "quantity": 1, "customer_name": "Asha"}


class FakeOwner:
    """Stands in for the person at the terminal."""

    def __init__(self, answer: bool):
        self.answer = answer
        self.asked: list[str] = []

    def __call__(self, summary: str) -> bool:
        self.asked.append(summary)
        return self.answer


def test_owner_says_yes_order_is_allowed():
    owner = FakeOwner(True)
    result = policy.decide(policy.PURCHASE_TOOL, ORDER, owner)
    assert isinstance(result, PermissionResultAllow)
    # The owner saw what they were approving.
    assert owner.asked == ["Order 1 x book b9 for Asha"]


def test_owner_says_no_order_is_denied_with_a_reason():
    result = policy.decide(policy.PURCHASE_TOOL, ORDER, FakeOwner(False))
    assert isinstance(result, PermissionResultDeny)
    assert "declined" in result.message  # Claude reads this to explain the refusal


def test_quantity_at_the_limit_still_reaches_the_owner():
    owner = FakeOwner(True)
    order = {**ORDER, "quantity": policy.MAX_QUANTITY}
    assert isinstance(policy.decide(policy.PURCHASE_TOOL, order, owner), PermissionResultAllow)
    assert len(owner.asked) == 1


@pytest.mark.parametrize(
    "quantity",
    [policy.MAX_QUANTITY + 1, 100, 0, -1, "2", 1.5, None],
)
def test_bad_quantity_is_denied_without_asking_the_owner(quantity):
    # The owner would say yes, to prove the hard rule wins over a human "yes".
    owner = FakeOwner(True)
    order = {**ORDER, "quantity": quantity}
    result = policy.decide(policy.PURCHASE_TOOL, order, owner)
    assert isinstance(result, PermissionResultDeny)
    assert owner.asked == []


def test_missing_quantity_is_denied():
    owner = FakeOwner(True)
    order = {"book_id": "b9", "customer_name": "Asha"}
    assert isinstance(policy.decide(policy.PURCHASE_TOOL, order, owner), PermissionResultDeny)
    assert owner.asked == []


@pytest.mark.parametrize("tool_name", ["Bash", "Write", "WebFetch", "mcp__bookstore__list_orders"])
def test_any_other_tool_is_denied_by_default(tool_name):
    owner = FakeOwner(True)
    result = policy.decide(tool_name, {}, owner)
    assert isinstance(result, PermissionResultDeny)
    assert tool_name in result.message
    assert owner.asked == []


def test_sdk_callback_uses_the_same_policy(monkeypatch, capsys):
    """can_use_tool is the async wrapper the SDK actually calls."""
    monkeypatch.setattr(policy, "ask_in_terminal", lambda summary: True)

    allowed = asyncio.run(policy.can_use_tool(policy.PURCHASE_TOOL, ORDER, ToolPermissionContext()))
    denied = asyncio.run(policy.can_use_tool("Bash", {"command": "ls"}, ToolPermissionContext()))

    assert isinstance(allowed, PermissionResultAllow)
    assert isinstance(denied, PermissionResultDeny)
    out = capsys.readouterr().out
    assert "purchase_book -> allow" in out
    assert "Bash -> deny" in out
