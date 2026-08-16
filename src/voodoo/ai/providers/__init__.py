"""LLM provider abstraction.

Defines the :class:`LLMProvider` interface and a factory that resolves a
``provider:model`` string (e.g. ``"openai:gpt-4"``, ``"mock:test"``) into a
provider instance. Provider SDKs are imported lazily — a missing optional
dependency raises an actionable :class:`ConfigurationError`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from voodoo.core.errors import ConfigurationError

__all__ = [
    "LLMProvider",
    "ProviderResponse",
    "ProviderEvent",
    "Message",
    "get_provider",
    "resolve_model",
]

# A chat message: ``{"role": "system"|"user"|"assistant"|"tool", "content": str}``
Message = dict[str, Any]


@dataclass
class ProviderResponse:
    """Normalized non-streaming completion result with token/cost accounting."""

    content: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float
    finish_reason: str = "stop"


@dataclass
class ProviderEvent:
    """A normalized streaming event.

    ``type`` is one of: ``text``, ``tool_call``, ``tool_result``, ``done``,
    ``error``. ``data`` carries the event payload (e.g. ``{"text": "..."}``
    for text, ``{"error": "..."}`` for errors).
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base for LLM providers.

    Subclasses implement :meth:`complete` (non-streaming) and :meth:`stream`
    (normalized streaming events). Both return provider-agnostic objects so
    the Agent never sees provider-native formats.
    """

    #: Provider name used in ``model="provider:model"`` resolution.
    name: str = "abstract"

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self.options = kwargs

    @abstractmethod
    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        """Return a normalized completion result."""
        raise NotImplementedError

    @abstractmethod
    def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ProviderEvent]:
        """Yield normalized streaming events."""
        raise NotImplementedError
        # pragma: no cover - abstract generator marker
        yield  # type: ignore[unreachable]  # noqa: B018


# ---------------------------------------------------------------------------
# Provider registry & factory
# ---------------------------------------------------------------------------

#: Maps provider name → fully-qualified provider class path (lazy import).
_PROVIDER_CLASSES: dict[str, str] = {
    "openai": "voodoo.ai.providers.openai.OpenAIProvider",
    "anthropic": "voodoo.ai.providers.anthropic.AnthropicProvider",
    "gemini": "voodoo.ai.providers.gemini.GeminiProvider",
    "ollama": "voodoo.ai.providers.ollama.OllamaProvider",
    "mock": "voodoo.ai.providers.mock.MockProvider",
}


def resolve_model(model: str) -> tuple[str, str]:
    """Split a ``"provider:model"`` string into ``(provider_name, model_id)``.

    Raises :class:`ConfigurationError` if the format is invalid or the
    provider is unknown.
    """
    if ":" not in model:
        raise ConfigurationError(
            f"model must be in 'provider:model' format (got {model!r}). "
            f"Example: 'openai:gpt-4', 'anthropic:claude-3', 'mock:test'."
        )
    provider_name, _, model_id = model.partition(":")
    if provider_name not in _PROVIDER_CLASSES:
        raise ConfigurationError(
            f"Unknown provider {provider_name!r}. "
            f"Known providers: {', '.join(sorted(_PROVIDER_CLASSES))}."
        )
    if not model_id:
        raise ConfigurationError(
            f"model id missing in {model!r} (expected 'provider:model')."
        )
    return provider_name, model_id


def get_provider(model: str, **kwargs: Any) -> LLMProvider:
    """Resolve ``"provider:model"`` into a ready :class:`LLMProvider` instance.

    Provider modules are imported lazily; a missing optional SDK raises an
    actionable :class:`ConfigurationError`.
    """
    provider_name, model_id = resolve_model(model)
    class_path = _PROVIDER_CLASSES[provider_name]
    module_path, _, class_name = class_path.rpartition(".")
    import importlib

    module = importlib.import_module(module_path)
    provider_cls: type[LLMProvider] = getattr(module, class_name)
    return provider_cls(model=model_id, **kwargs)
