"""Deterministic mock provider for CI (no network).

Returns reproducible responses so agent/provider tests are stable and
network-free. Token accounting is derived from the input/output word counts;
cost is always zero.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from voodoo.ai.providers import LLMProvider, Message, ProviderEvent, ProviderResponse

__all__ = ["MockProvider"]

_FINISH = "stop"


def _last_user_content(messages: list[Message]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(str(p) for p in content)
            return str(content)
    return ""


def _word_count(text: str) -> int:
    return len(text.split())


class MockProvider(LLMProvider):
    """Provider that returns deterministic responses without any network."""

    name = "mock"

    def __init__(self, model: str = "test", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        # Optional fixed response override (useful for tests).
        self.response: str | None = kwargs.get("response")

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        prompt = _last_user_content(messages)
        content = self.response or f"Mock response to: {prompt}"
        tokens_in = _word_count(prompt)
        tokens_out = _word_count(content)
        return ProviderResponse(
            content=content,
            model=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=0.0,
            finish_reason=_FINISH,
        )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ProviderEvent]:
        prompt = _last_user_content(messages)
        content = self.response or f"Mock response to: {prompt}"
        # Stream word-by-word so callers observe multiple text events.
        for word in content.split():
            yield ProviderEvent(type="text", data={"text": word + " "})
        yield ProviderEvent(
            type="done",
            data={
                "model": self.model,
                "tokens_in": _word_count(prompt),
                "tokens_out": _word_count(content),
                "cost": 0.0,
                "finish_reason": _FINISH,
            },
        )
