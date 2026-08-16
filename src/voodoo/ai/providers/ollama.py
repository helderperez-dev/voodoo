"""Ollama provider (local models, lazy import of the ``ollama`` SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from voodoo.ai.providers import LLMProvider, Message, ProviderEvent, ProviderResponse
from voodoo.core.errors import ConfigurationError

__all__ = ["OllamaProvider"]


def _require_ollama() -> Any:
    try:
        import ollama  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without SDK
        raise ConfigurationError(
            "The 'ollama' package is required for the ollama provider. "
            "Install it with: pip install voodoo-framework[ai]"
        ) from exc
    return ollama


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, model: str = "llama3", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        ollama = _require_ollama()
        self._client = ollama.AsyncClient(host=kwargs.get("host"))

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        resp = await self._client.chat(model=self.model, messages=messages, **kwargs)
        content = (
            resp.get("message", {}).get("content", "") if isinstance(resp, dict) else ""
        )
        usage = resp.get("prompt_eval_count", 0) if isinstance(resp, dict) else 0
        out_tokens = resp.get("eval_count", 0) if isinstance(resp, dict) else 0
        return ProviderResponse(
            content=content,
            model=self.model,
            tokens_in=usage,
            tokens_out=out_tokens,
            cost=0.0,
            finish_reason="stop",
        )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ProviderEvent]:
        async for part in await self._client.chat(
            model=self.model, messages=messages, stream=True, **kwargs
        ):
            text = (
                part.get("message", {}).get("content", "")
                if isinstance(part, dict)
                else ""
            )
            if text:
                yield ProviderEvent(type="text", data={"text": text})
        yield ProviderEvent(
            type="done",
            data={"model": self.model, "finish_reason": "stop"},
        )
