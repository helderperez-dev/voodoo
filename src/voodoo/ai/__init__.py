"""Voodoo AI — LLM provider abstraction, agent, and tools.

Re-exports the provider interface and factory so subsystems import from a
single place.
"""

from __future__ import annotations

from voodoo.ai.providers import (
    EmbeddingResponse,
    LLMProvider,
    Message,
    ModelDescriptor,
    ProviderEvent,
    ProviderResponse,
    VoodooModelProvider,
    describe_model,
    get_provider,
    register_provider,
    resolve_model,
)

__all__ = [
    "LLMProvider",
    "VoodooModelProvider",
    "ProviderResponse",
    "ProviderEvent",
    "Message",
    "EmbeddingResponse",
    "ModelDescriptor",
    "get_provider",
    "resolve_model",
    "register_provider",
    "describe_model",
]
