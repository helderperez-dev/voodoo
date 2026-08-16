"""Google Gemini provider (lazy import of ``google.generativeai``)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from voodoo.ai.providers import LLMProvider, Message, ProviderEvent, ProviderResponse
from voodoo.core.errors import ConfigurationError

__all__ = ["GeminiProvider"]


def _require_gemini() -> Any:
    try:
        import google.generativeai as genai  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without SDK
        raise ConfigurationError(
            "The 'google-generativeai' package is required for the gemini "
            "provider. Install it with: pip install voodoo-framework[ai]"
        ) from exc
    return genai


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-1.5-pro", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        genai = _require_gemini()
        if kwargs.get("api_key"):
            genai.configure(api_key=kwargs["api_key"])
        self._model = genai.GenerativeModel(self.model)

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        prompt = "\n".join(
            str(m.get("content", "")) for m in messages if m.get("role") != "system"
        )
        resp = await self._model.generate_content_async(prompt, **kwargs)
        content = getattr(resp, "text", "") or ""
        usage = getattr(resp, "usage_metadata", None)
        tokens_in = getattr(usage, "prompt_token_count", 0) if usage else 0
        tokens_out = getattr(usage, "candidates_token_count", 0) if usage else 0
        return ProviderResponse(
            content=content,
            model=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=0.0,
            finish_reason="stop",
        )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ProviderEvent]:
        prompt = "\n".join(
            str(m.get("content", "")) for m in messages if m.get("role") != "system"
        )
        async for chunk in self._model.generate_content_async(
            prompt, stream=True, **kwargs
        ):
            text = getattr(chunk, "text", "") or ""
            if text:
                yield ProviderEvent(type="text", data={"text": text})
        yield ProviderEvent(
            type="done",
            data={"model": self.model, "finish_reason": "stop"},
        )
