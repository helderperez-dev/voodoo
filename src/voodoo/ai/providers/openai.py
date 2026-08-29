"""OpenAI provider (lazy import of the ``openai`` SDK)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from voodoo.ai.providers import (
    EmbeddingResponse,
    LLMProvider,
    Message,
    ModelDescriptor,
    ProviderEvent,
    ProviderResponse,
    ToolCall,
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


def _parse_tool_calls(msg: Any) -> list[ToolCall]:
    """Extract native OpenAI tool calls from a chat-completion message."""
    calls: list[ToolCall] = []
    for tc in getattr(msg, "tool_calls", None) or []:
        fn = getattr(tc, "function", None)
        if fn is None and isinstance(tc, dict):
            fn = tc.get("function")
        if fn is None:
            continue
        name = getattr(fn, "name", "")
        if not name and isinstance(fn, dict):
            name = fn.get("name", "")
        raw_args = getattr(fn, "arguments", "{}") or "{}"
        if isinstance(fn, dict):
            raw_args = fn.get("arguments", "{}") or "{}"
        try:
            arguments = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            arguments = {"_raw": raw_args}
        calls.append(
            ToolCall(name=name, arguments=arguments, id=getattr(tc, "id", None))
        )
    return calls


def _append_tool_delta(buffers: dict[int, dict[str, Any]], tc: Any) -> None:
    """Accumulate one streaming tool-call delta into ``buffers`` keyed by index."""
    index = getattr(tc, "index", 0)
    buf = buffers.setdefault(index, {"id": None, "name": "", "args": ""})
    if getattr(tc, "id", None):
        buf["id"] = tc.id
    fn = getattr(tc, "function", None)
    if fn is None:
        return
    if getattr(fn, "name", None):
        buf["name"] = fn.name
    if getattr(fn, "arguments", None):
        buf["args"] += fn.arguments


def _flush_tool_calls(buffers: dict[int, dict[str, Any]]) -> list[ProviderEvent]:
    """Convert accumulated streaming tool-call fragments into ``tool_call`` events."""
    events: list[ProviderEvent] = []
    for buf in buffers.values():
        raw_args = buf["args"] or "{}"
        try:
            arguments = json.loads(raw_args)
        except json.JSONDecodeError:
            arguments = {"_raw": raw_args}
        events.append(
            ProviderEvent(
                type="tool_call",
                data={"name": buf["name"], "arguments": arguments, "id": buf["id"]},
            )
        )
    return events


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
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs,
            )
        except Exception:
            # If the request failed and tools were included, retry without
            # them — some OpenAI-compatible endpoints reject unsupported params.
            if kwargs.get("tools"):
                kwargs.pop("tools", None)
                kwargs.pop("tool_choice", None)
                resp = await self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **kwargs,
                )
            else:
                raise
        choice = resp.choices[0]
        msg = choice.message
        usage = getattr(resp, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0
        return ProviderResponse(
            content=msg.content or "",
            model=resp.model or self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=_cost(self.model, tokens_in, tokens_out),
            finish_reason=choice.finish_reason or "stop",
            tool_calls=_parse_tool_calls(msg),
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
        # OpenAI streams tool calls as incremental JSON fragments keyed by
        # index; accumulate them and flush as ``tool_call`` events on done.
        tool_buffers: dict[int, dict[str, Any]] = {}
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if getattr(delta, "content", None):
                yield ProviderEvent(type="text", data={"text": delta.content})
            for tc in getattr(delta, "tool_calls", None) or []:
                _append_tool_delta(tool_buffers, tc)
        for event in _flush_tool_calls(tool_buffers):
            yield event
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
        # Models known to support native tool/function calling.  Unknown
        # OpenAI-compatible models (e.g. LiteLLM proxied non-OpenAI models)
        # default to False so the agent doesn't send unsupported params.
        _tool_capable = (
            gpt4o
            or "gpt-4" in self.model
            or "gpt-3.5" in self.model
            or "o1" in self.model
            or "o3" in self.model
            or "o4" in self.model
            or "claude" in self.model
            or "deepseek" in self.model
        )
        return ModelDescriptor(
            provider=self.name,
            model=self.model,
            modalities=["text"],
            context_window=128000 if gpt4o else 0,
            tool_use=_tool_capable,
            structured_output=_tool_capable,
            streaming=True,
            reasoning="o1" in self.model or "o3" in self.model,
            vision=gpt4o or "gpt-4.5" in self.model,
            audio=gpt4o,
            embeddings=True,
        )
