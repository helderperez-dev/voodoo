"""Anthropic provider (lazy import of the ``anthropic`` SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from voodoo.ai.providers import (
    LLMProvider,
    Message,
    ModelDescriptor,
    ProviderEvent,
    ProviderResponse,
    ToolCall,
)
from voodoo.core.errors import ConfigurationError

__all__ = ["AnthropicProvider"]


def _require_anthropic() -> Any:
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without SDK
        raise ConfigurationError(
            "The 'anthropic' package is required for the anthropic provider. "
            "Install it with: pip install voodoo-framework[ai]"
        ) from exc
    return anthropic


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str = "claude-3-5-sonnet-latest", **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        anthropic = _require_anthropic()
        self._client = anthropic.AsyncAnthropic(api_key=kwargs.get("api_key"))

    def _split_system(
        self, messages: list[Message]
    ) -> tuple[str | None, list[Message]]:
        system = None
        rest: list[Message] = []
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content")
            else:
                rest.append(msg)
        return system, rest

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        system, rest = self._split_system(messages)
        params: dict[str, Any] = {"model": self.model, "messages": rest, **kwargs}
        if system is not None:
            params["system"] = system
        resp = await self._client.messages.create(**params)
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            block_type = getattr(block, "type", "")
            if block_type == "text":
                content_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=getattr(block, "name", ""),
                        arguments=getattr(block, "input", {}) or {},
                        id=getattr(block, "id", None),
                    )
                )
        return ProviderResponse(
            content="".join(content_parts),
            model=resp.model or self.model,
            tokens_in=getattr(resp.usage, "input_tokens", 0),
            tokens_out=getattr(resp.usage, "output_tokens", 0),
            cost=0.0,
            finish_reason=resp.stop_reason or "stop",
            tool_calls=tool_calls,
        )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ProviderEvent]:
        system, rest = self._split_system(messages)
        params: dict[str, Any] = {
            "model": self.model,
            "messages": rest,
            **kwargs,
        }
        if system is not None:
            params["system"] = system
        async with self._client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield ProviderEvent(type="text", data={"text": text})
        yield ProviderEvent(
            type="done",
            data={"model": self.model, "finish_reason": "stop"},
        )

    def describe(self) -> ModelDescriptor:
        """Advertise the Anthropic capability matrix for this model."""
        claude3 = self.model.startswith("claude-3")
        return ModelDescriptor(
            provider=self.name,
            model=self.model,
            modalities=["text"],
            context_window=200000 if claude3 else 0,
            tool_use=True,
            structured_output=True,
            streaming=True,
            reasoning="opus" in self.model or "sonnet" in self.model,
            vision=claude3,
            audio=False,
            embeddings=False,
        )
