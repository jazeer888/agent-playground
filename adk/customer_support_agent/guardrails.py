"""Guardrails for the support agent, as ADK callbacks.

Two checks, both in plain code so they hold whatever the model is told:

1. Prompt-injection screen (before the model). If the latest user message
   tries to override the agent's instructions, the model is skipped and a
   fixed reply is returned instead.
2. Data leak protection (before and after the model). Card numbers, API
   keys/tokens and passwords are replaced with placeholders in the text sent
   to the model and in the text the model sends back.

The pure functions at the top (`redact`, `looks_like_injection`) take strings
and return values, so they are easy to unit test. The two callbacks at the
bottom wire them into ADK.
"""

from __future__ import annotations

import re
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# --- Data leak protection ---------------------------------------------------------

# Each rule: a name (used in the placeholder), a regex, and an optional extra
# check on the match. Order matters: more specific patterns go first.
_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_API_KEY_RE = re.compile(
    r"\b(?:AIza[0-9A-Za-z_-]{35}"      # Google API key
    r"|sk-[A-Za-z0-9_-]{20,}"          # OpenAI-style secret key
    r"|ghp_[A-Za-z0-9]{36}"            # GitHub token
    r"|hk_[A-Za-z0-9_]{12,})\b"        # HelixID-style key
)
_PASSWORD_RE = re.compile(
    r"(?i)\b(password|passcode|pin|otp|one[- ]time code)\b(\s*(?:is|:|=)\s*)(\S+)"
)


def _luhn_ok(digits: str) -> bool:
    """True if the digit string passes the Luhn checksum used by card numbers."""
    total, double = 0, False
    for d in reversed(digits):
        n = int(d)
        if double:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
        double = not double
    return total % 10 == 0


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Replaces secrets in `text` with placeholders.

    Returns the cleaned text and a count per kind, e.g. {"card": 1}.
    Card numbers must pass the Luhn check, so a 16-digit order number is
    left alone.
    """
    counts: dict[str, int] = {}

    def bump(kind: str) -> None:
        counts[kind] = counts.get(kind, 0) + 1

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            bump("card")
            return "[CARD NUMBER REMOVED]"
        return m.group(0)

    def key(m: re.Match) -> str:
        bump("api_key")
        return "[API KEY REMOVED]"

    def password(m: re.Match) -> str:
        bump("password")
        return f"{m.group(1)}{m.group(2)}[PASSWORD REMOVED]"

    text = _API_KEY_RE.sub(key, text)
    text = _CARD_RE.sub(card, text)
    text = _PASSWORD_RE.sub(password, text)
    return text, counts


# --- Prompt-injection screen --------------------------------------------------------

_INJECTION_RE = re.compile(
    r"(?i)(ignore (?:all |your |the )?(?:previous |prior |above )?instructions"
    r"|disregard (?:your|the) (?:instructions|rules)"
    r"|you are now (?:a|an|in) "
    r"|(?:reveal|print|show|repeat) (?:your|the) (?:system prompt|instructions)"
    r"|developer mode"
    r"|jailbreak)"
)

INJECTION_REPLY = (
    "I can only help with Lumen Audio orders, products, returns and support. "
    "I can't change how I work. What can I help you with today?"
)


def looks_like_injection(text: str) -> bool:
    """True if the text contains a common instruction-override phrase."""
    return bool(_INJECTION_RE.search(text))


# --- ADK callbacks -------------------------------------------------------------------

def _latest_user_parts(llm_request: LlmRequest) -> list[types.Part]:
    """Text parts of the most recent user message in the request."""
    for content in reversed(llm_request.contents or []):
        if content.role == "user":
            return [p for p in (content.parts or []) if p.text]
    return []


def screen_input(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """before_model_callback: injection check, then redact secrets in the user turn.

    Returning an LlmResponse skips the model and uses it as the reply.
    Returning None lets the (now redacted) request go to the model.
    """
    parts = _latest_user_parts(llm_request)
    text = " ".join(p.text for p in parts)

    if looks_like_injection(text):
        callback_context.state["guardrail_blocks"] = callback_context.state.get("guardrail_blocks", 0) + 1
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=INJECTION_REPLY)]))

    total = 0
    for p in parts:
        p.text, counts = redact(p.text)
        total += sum(counts.values())
    if total:
        callback_context.state["dlp_redactions_in"] = callback_context.state.get("dlp_redactions_in", 0) + total
    return None


def screen_output(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    """after_model_callback: redact secrets in the model's reply.

    Returning a new LlmResponse replaces the model's; None keeps it.
    """
    if not llm_response.content or not llm_response.content.parts:
        return None
    total = 0
    new_parts = []
    for p in llm_response.content.parts:
        if p.text:
            cleaned, counts = redact(p.text)
            total += sum(counts.values())
            new_parts.append(types.Part(text=cleaned))
        else:
            new_parts.append(p)
    if not total:
        return None
    callback_context.state["dlp_redactions_out"] = callback_context.state.get("dlp_redactions_out", 0) + total
    return LlmResponse(content=types.Content(role="model", parts=new_parts))
