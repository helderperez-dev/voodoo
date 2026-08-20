"""OpenAI provider (lazy import of the ``openai`` SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from voodoo.ai.providers import (
    EmbeddingResponse,
    LLMProvider,
    Message,
    ModelDescriptor,
    ProviderEvent,
    ProviderResponse,
)
from voodoo.core.errors import ConfigurationError

__all__ = ["OpenAIProvider"]

# Rough per-1k-token cost table (USD) for common models; unknown → 0.0.
_RATES: dict[str, tuple[float, float]] = {
    # model_prefix: (input_per_1k, output_per_1k)
}
_DEFAULT_RATE = (0.0, 0.0)


def _cost(model: str, tokens_in: int, tokens_out: int) -> float:
    rate_in, rate_out = _DEFAULT_RATE
    for prefix, (rin, rout) in _RATES.items():
        if model.startswith(prefix):
            rate_in, rate_out = rin, rout
            break
    return tokens_in / 1000 * rate_in + tokens_out / 1000 * rate_out


def _require_openai() -> Any:
    try:
        import openai  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without SDK
        raise ConfigurationError(
            "The 'openai' package is required for the openai provider. "
            "Install it with: pip install voodoo-framework[ai]"
        ) from exc
    return openai


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        openai = _require_openai()
        # ``base_url`` enables OpenAI-compatible endpoints (e.g. OpenRouter).
        self._client = openai.AsyncOpenAI(
            api_key=kwargs.get("api_key"), base_url=kwargs.get("base_url")
        )

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        choice = resp.choices[0]
        usage = getattr(resp, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0
        return ProviderResponse(
            content=choice.message.content or "",
            model=resp.model or self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=_cost(self.model, tokens_in, tokens_out),
            finish_reason=choice.finish_reason or "stop",
        )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ProviderEvent]:
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield ProviderEvent(
                    type="text",
                    data={"text": chunk.choices[0].delta.content},
                )
        yield ProviderEvent(
            type="done",
            data={"model": self.model, "finish_reason": "stop"},
        )

    async def embed(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        """Produce embeddings via the OpenAI embeddings API."""
        resp = await self._client.embeddings.create(
            model=kwargs.pop("embedding_model", "text-embedding-3-small"),
            input=texts,
            **kwargs,
        )
        usage = getattr(resp, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        return EmbeddingResponse(
            embeddings=[d.embedding for d in resp.data],
            model=self.model,
            tokens_in=tokens_in,
            cost=0.0,
        )

    def describe(self) -> ModelDescriptor:
        """Advertise the OpenAI capability matrix for this model."""
        gpt4o = "gpt-4o" in self.model or "gpt-4.1" in self.model
        return ModelDescriptor(
            provider=self.name,
            model=self.model,
            modalities=["text"],
            context_window=128000 if gpt4o else 0,
            tool_use=True,
            structured_output=True,
            streaming=True,
            reasoning="o1" in self.model or "o3" in self.model,
            vision=gpt4o or "gpt-4.5" in self.model,
            audio=gpt4o,
            embeddings=True,
        )
