"""A scripted stand-in for Gemini so the agent runs with no network.

`script` is a queue of replies. Each item is the text the fake model should
answer with. Every request the agent makes is kept in `requests`, so a test
can check what the model would have seen (for example, that a card number
was redacted before it got there).
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field


class ScriptedLlm(BaseLlm):
    script: list[str] = Field(default_factory=list)
    requests: list[LlmRequest] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        if not self.script:
            raise AssertionError("model called more times than scripted")
        yield LlmResponse(content=types.Content(
            role="model", parts=[types.Part(text=self.script.pop(0))]))

    def last_user_text(self) -> str:
        """The latest user message in the most recent request."""
        for content in reversed(self.requests[-1].contents or []):
            if content.role == "user":
                return " ".join(p.text or "" for p in content.parts or [])
        return ""
