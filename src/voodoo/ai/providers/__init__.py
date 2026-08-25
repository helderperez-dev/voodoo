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
from typing import Any, Protocol

from voodoo.core.errors import ConfigurationError

__all__ = [
    "LLMProvider",
    "VoodooModelProvider",
    "ProviderResponse",
    "ProviderEvent",
    "ToolCall",
    "Message",
    "EmbeddingResponse",
    "ModelDescriptor",
    "get_provider",
    "resolve_model",
    "default_model",
    "register_provider",
    "describe_model",
]

# A chat message: ``{"role": "system"|"user"|"assistant"|"tool", "content": str}``
Message = dict[str, Any]


@dataclass
class EmbeddingResponse:
    """Normalized embedding result with token/cost accounting."""

    embeddings: list[list[float]]
    model: str
    tokens_in: int = 0
    cost: float = 0.0


@dataclass
class ModelDescriptor:
    """Static capability description of a model behind a provider.

    Exposes a model's capability matrix (modalities, context window, tool
    use, structured output, streaming, reasoning, vision, audio, embeddings,
    pricing) without making a network call. Used for routing-alias resolution
    and runtime introspection (ROADMAP §64, §47).
    """

    provider: str
    model: str
    modalities: list[str] = field(default_factory=lambda: ["text"])
    context_window: int = 0
    tool_use: bool = False
    structured_output: bool = False
    streaming: bool = True
    reasoning: bool = False
    vision: bool = False
    audio: bool = False
    embeddings: bool = False
    pricing: dict[str, Any] = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        """The ``"provider:model"`` string identifying this model."""
        return f"{self.provider}:{self.model}"


@dataclass
class ToolCall:
    """A structured tool-call request from a provider.

    ``id`` is the provider's call identifier, used to match tool results back
    to calls in native multi-turn transcripts (OpenAI/Anthropic/etc.). It is
    ``None`` for providers that use the legacy ``[TOOL: ...]`` text-marker
    convention, where the agent derives the call from the response content.
    """

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass
class ProviderResponse:
    """Normalized non-streaming completion result with token/cost accounting.

    ``tool_calls`` carries structured tool-call requests (the native protocol,
    ROADMAP §47). When empty, the response is a plain completion (or a legacy
    ``[TOOL: ...]`` marker that the Agent parses from ``content``).
    """

    content: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float
    finish_reason: str = "stop"
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class ProviderEvent:
    """A normalized streaming event.

    ``type`` is one of: ``text``, ``tool_call``, ``tool_result``, ``done``,
    ``error``. ``data`` carries the event payload (e.g. ``{"text": "..."}``
    for text, ``{"error": "..."}`` for errors).
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


class VoodooModelProvider(Protocol):
    """Normalized model surface every model provider must satisfy (spec gap #7).

    Concrete providers subclass :class:`LLMProvider` (which supplies default
    :meth:`generate`, :meth:`embed`, :meth:`count_tokens`, and
    :meth:`describe` implementations), but any object satisfying this
    structural Protocol is a valid model provider.
    """

    name: str

    async def generate(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        """Produce a completion (alias of :meth:`LLMProvider.complete`)."""
        ...

    def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[ProviderEvent]:
        """Yield normalized streaming events."""
        ...

    async def embed(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        """Produce vector embeddings for ``texts`` (not all providers)."""
        ...

    async def count_tokens(self, messages: list[Message], **kwargs: Any) -> int:
        """Estimate the token count of ``messages`` (optional)."""
        ...

    def describe(self) -> ModelDescriptor:
        """Return the model's static capability descriptor."""
        ...


class LLMProvider(ABC):
    """Abstract base for LLM providers.

    Subclasses implement :meth:`complete` (non-streaming) and :meth:`stream`
    (normalized streaming events). Both return provider-agnostic objects so
    the Agent never sees provider-native formats. The base also supplies
    default :meth:`generate`, :meth:`embed`, :meth:`count_tokens`, and
    :meth:`describe` so every provider conforms to
    :class:`VoodooModelProvider`.
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

    async def generate(
        self, messages: list[Message], **kwargs: Any
    ) -> ProviderResponse:
        """Normalized completion — defaults to delegating to :meth:`complete`."""
        return await self.complete(messages, **kwargs)

    async def embed(self, texts: list[str], **kwargs: Any) -> EmbeddingResponse:
        """Return embeddings for ``texts``.

        Not every provider supports embeddings; the default raises
        :class:`NotImplementedError`. Embedding-capable providers override
        this method.
        """
        raise NotImplementedError(f"provider {self.name!r} does not support embeddings")

    async def count_tokens(self, messages: list[Message], **kwargs: Any) -> int:
        """Estimate token usage (word-count heuristic by default)."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content.split())
            elif isinstance(content, list):
                total += sum(len(str(p).split()) for p in content)
        return total

    def describe(self) -> ModelDescriptor:
        """Return a conservative capability descriptor.

        Providers override this to advertise accurate capabilities.
        """
        return ModelDescriptor(provider=self.name, model=self.model)


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

#: Built-in routing aliases resolved when no explicit config alias exists.
#: The ``models.aliases`` block in ``voodoo.yaml`` overrides these (ROADMAP §47).
DEFAULT_ALIASES: dict[str, str] = {
    "best": "openai:gpt-4o",
    "fast": "openai:gpt-4o-mini",
    "cheap": "openai:gpt-4o-mini",
    "vision": "openai:gpt-4o",
    "reasoning": "openai:o1-mini",
}


def register_provider(name: str, class_path: str) -> None:
    """Register a provider class path under ``name`` for lazy resolution."""
    if not name or ":" in name:
        raise ConfigurationError(
            f"provider name must be a bare identifier (got {name!r})"
        )
    _PROVIDER_CLASSES[name] = class_path


def _routing_aliases(aliases: dict[str, str] | None) -> dict[str, str]:
    """Merge config-provided aliases over the built-in defaults.

    Config aliases come from ``models.aliases`` and ``ai.aliases`` in
    ``voodoo.yaml``/``voodoo.toml`` (surfaced via :data:`voodoo.config.config`);
    explicit caller-provided ``aliases`` win over both.
    """
    merged = dict(DEFAULT_ALIASES)
    try:
        from voodoo.config import config

        merged.update(config.models.aliases or {})
        merged.update(config.ai.aliases or {})
    except Exception:  # noqa: BLE001 — config resolution is best-effort here
        pass
    if aliases:
        merged.update(aliases)
    return merged


def resolve_model(model: str, aliases: dict[str, str] | None = None) -> tuple[str, str]:
    """Resolve a model reference to ``(provider_name, model_id)``.

    Accepts either ``"provider:model"`` (e.g. ``"openai:gpt-4"``) or a
    routing alias (``best``, ``fast``, ``cheap``, ``vision``, ``reasoning``,
    or any alias defined in ``models.aliases``). Aliases resolve through
    config-provided mappings first, then built-in defaults.

    Raises :class:`ConfigurationError` if the format is invalid, the alias is
    unknown, or the provider is unknown.
    """
    target = model
    if ":" not in model:
        routing = _routing_aliases(aliases)
        if model not in routing:
            raise ConfigurationError(
                f"Unknown model reference {model!r}. Use 'provider:model' "
                f"(e.g. 'openai:gpt-4', 'mock:test') or a known alias: "
                f"{', '.join(sorted(routing))}."
            )
        target = routing[model]

    provider_name, _, model_id = target.partition(":")
    if provider_name not in _PROVIDER_CLASSES:
        raise ConfigurationError(
            f"Unknown provider {provider_name!r}. "
            f"Known providers: {', '.join(sorted(_PROVIDER_CLASSES))}."
        )
    if not model_id:
        raise ConfigurationError(
            f"model id missing in {target!r} (expected 'provider:model')."
        )
    return provider_name, model_id


def default_model() -> str:
    """Return the configured default model reference (``provider:model``).

    The ``ai`` block wins when it declares a model (combined with
    ``ai.provider``, defaulting to ``openai``), otherwise ``models.default``
    is used. Falls back to ``mock:default`` when config is unavailable.

    This lets ``Agent()`` and other entry points be configured entirely from
    ``voodoo.toml``/``voodoo.yaml`` with zero code.
    """
    try:
        from voodoo.config import config

        if config.ai.model:
            provider = config.ai.provider or "openai"
            return f"{provider}:{config.ai.model}"
        return config.models.default
    except Exception:  # noqa: BLE001 — config resolution is best-effort here
        return "mock:default"


def get_provider(model: str, **kwargs: Any) -> LLMProvider:
    """Resolve ``"provider:model"`` (or a routing alias) into a provider instance.

    Provider modules are imported lazily; a missing optional SDK raises an
    actionable :class:`ConfigurationError`. For OpenAI-compatible providers,
    the ``ai`` config block supplies ``base_url``/``api_key`` fallbacks when
    not passed explicitly, so e.g. DeepSeek works with zero provider code.
    """
    provider_name, model_id = resolve_model(model)
    class_path = _PROVIDER_CLASSES[provider_name]
    module_path, _, class_name = class_path.rpartition(".")
    import importlib

    module = importlib.import_module(module_path)
    provider_cls: type[LLMProvider] = getattr(module, class_name)

    if provider_name == "openai":
        try:
            from voodoo.config import config

            if config.ai.base_url:
                kwargs.setdefault("base_url", config.ai.base_url)
            if config.ai.api_key:
                kwargs.setdefault("api_key", config.ai.api_key)
        except Exception:  # noqa: BLE001 — config resolution is best-effort here
            pass

    return provider_cls(model=model_id, **kwargs)


def describe_model(model: str) -> ModelDescriptor:
    """Return the capability descriptor for ``model`` (no network calls).

    Instantiates the provider (which, for non-mock providers, requires its
    optional SDK) and returns :meth:`LLMProvider.describe`.
    """
    return get_provider(model).describe()
