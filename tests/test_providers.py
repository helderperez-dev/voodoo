"""Tests for the LLM provider abstraction: mock provider, complete/stream,
token accounting, model resolution, and the missing-SDK error path."""

from __future__ import annotations

import sys

import pytest

from voodoo import LLMProvider
from voodoo.ai import describe_model, get_provider, register_provider, resolve_model
from voodoo.ai.providers import (
    EmbeddingResponse,
    ModelDescriptor,
    ProviderEvent,
    ProviderResponse,
)
from voodoo.ai.providers import (
    LLMProvider as LLMProviderBase,
)
from voodoo.ai.providers.mock import MockProvider
from voodoo.core.errors import ConfigurationError

# ---------------------------------------------------------------------------
# resolve_model / get_provider
# ---------------------------------------------------------------------------


def test_resolve_model_splits_provider_and_model():
    provider, model_id = resolve_model("openai:gpt-4")
    assert provider == "openai"
    assert model_id == "gpt-4"


def test_resolve_model_mock():
    provider, model_id = resolve_model("mock:test")
    assert provider == "mock"
    assert model_id == "test"


def test_resolve_model_unknown_bare_reference_raises_configuration_error():
    # A bare name with no colon and no matching alias is rejected.
    with pytest.raises(ConfigurationError, match="provider:model"):
        resolve_model("gpt-4")


def test_resolve_model_unknown_provider_raises_configuration_error():
    with pytest.raises(ConfigurationError, match="Unknown provider"):
        resolve_model("acme:foo")


def test_resolve_model_missing_model_id_raises_configuration_error():
    with pytest.raises(ConfigurationError, match="model id missing"):
        resolve_model("openai:")


def test_resolve_model_builtin_alias():
    provider, model_id = resolve_model("best")
    assert provider == "openai"
    assert model_id == "gpt-4o"


def test_resolve_model_caller_alias_overrides_builtin():
    provider, model_id = resolve_model("best", aliases={"best": "mock:test"})
    assert provider == "mock"
    assert model_id == "test"


def test_resolve_model_unknown_alias_raises_configuration_error():
    with pytest.raises(ConfigurationError, match="Unknown model reference"):
        resolve_model("nonexistent-alias")


def test_get_provider_returns_mock_instance():
    provider = get_provider("mock:test")
    assert isinstance(provider, MockProvider)
    assert provider.model == "test"


def test_get_provider_resolves_alias():
    # ``best`` maps to OpenAI by default, which requires the SDK — so use a
    # caller alias to keep this test network/SDK-free.
    import voodoo.ai.providers as providers_mod

    original = dict(providers_mod.DEFAULT_ALIASES)
    try:
        providers_mod.DEFAULT_ALIASES["best"] = "mock:test"
        provider = get_provider("best")
        assert isinstance(provider, MockProvider)
    finally:
        providers_mod.DEFAULT_ALIASES.clear()
        providers_mod.DEFAULT_ALIASES.update(original)


def test_get_provider_unknown_raises_configuration_error():
    with pytest.raises(ConfigurationError):
        get_provider("acme:foo")


def test_register_provider_and_resolve():
    register_provider("mocktest", "voodoo.ai.providers.mock.MockProvider")
    try:
        provider = get_provider("mocktest:abc")
        assert isinstance(provider, MockProvider)
        assert provider.model == "abc"
    finally:
        import voodoo.ai.providers as providers_mod

        providers_mod._PROVIDER_CLASSES.pop("mocktest", None)


def test_describe_model_returns_descriptor():
    desc = describe_model("mock:test")
    assert isinstance(desc, ModelDescriptor)
    assert desc.provider == "mock"
    assert desc.model == "test"
    assert desc.qualified_name == "mock:test"


def test_llmprovider_is_abstract_base():
    assert isinstance(LLMProvider, type)
    # Cannot instantiate the abstract base directly.
    with pytest.raises(TypeError):
        LLMProvider(model="x")  # type: ignore[abstract]


def test_mock_provider_is_llmprovider():
    assert issubclass(MockProvider, LLMProviderBase)


# ---------------------------------------------------------------------------
# MockProvider — complete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_complete_returns_provider_response():
    provider = MockProvider(model="test")
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello world"},
    ]
    resp = await provider.complete(messages)
    assert isinstance(resp, ProviderResponse)
    assert resp.content == "Mock response to: hello world"
    assert resp.model == "test"
    assert resp.finish_reason == "stop"
    assert resp.cost == 0.0


@pytest.mark.asyncio
async def test_mock_complete_token_accounting():
    provider = MockProvider(model="test")
    messages = [{"role": "user", "content": "hello world foo bar"}]  # 4 words
    resp = await provider.complete(messages)
    assert resp.tokens_in == 4
    # output "Mock response to: hello world foo bar" -> 7 words
    assert resp.tokens_out == len(resp.content.split())
    assert resp.tokens_out == 7


@pytest.mark.asyncio
async def test_mock_complete_deterministic():
    provider = MockProvider(model="test")
    messages = [{"role": "user", "content": "same prompt"}]
    a = await provider.complete(messages)
    b = await provider.complete(messages)
    assert a.content == b.content
    assert a.tokens_in == b.tokens_in


@pytest.mark.asyncio
async def test_mock_complete_with_fixed_response_override():
    provider = MockProvider(model="test", response="custom output")
    resp = await provider.complete([{"role": "user", "content": "anything"}])
    assert resp.content == "custom output"


# ---------------------------------------------------------------------------
# MockProvider — stream()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_stream_yields_text_then_done():
    provider = MockProvider(model="test")
    messages = [{"role": "user", "content": "hello world"}]
    events = []
    async for event in provider.stream(messages):
        events.append(event)

    assert events, "stream produced no events"
    assert all(isinstance(e, ProviderEvent) for e in events)
    text_events = [e for e in events if e.type == "text"]
    assert len(text_events) > 1, "expected multiple text chunks"
    reconstructed = "".join(e.data["text"] for e in text_events)
    assert reconstructed.strip() == "Mock response to: hello world"
    assert events[-1].type == "done"
    assert events[-1].data["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_mock_stream_done_event_has_token_accounting():
    provider = MockProvider(model="test")
    messages = [{"role": "user", "content": "one two three"}]
    events = [e async for e in provider.stream(messages)]
    done = events[-1]
    assert done.type == "done"
    assert done.data["tokens_in"] == 3
    assert done.data["cost"] == 0.0


@pytest.mark.asyncio
async def test_mock_stream_deterministic():
    provider = MockProvider(model="test")
    messages = [{"role": "user", "content": "stable prompt"}]
    a = [e async for e in provider.stream(messages)]
    b = [e async for e in provider.stream(messages)]
    assert len(a) == len(b)
    assert [e.data for e in a] == [e.data for e in b]


# ---------------------------------------------------------------------------
# MockProvider — embed() / describe()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_embed_returns_embedding_response():
    provider = MockProvider(model="test")
    resp = await provider.embed(["hello world", "second text"])
    assert isinstance(resp, EmbeddingResponse)
    assert len(resp.embeddings) == 2
    assert all(isinstance(v, float) for e in resp.embeddings for v in e)
    assert resp.model == "test"


def test_mock_describe_returns_descriptor():
    provider = MockProvider(model="test")
    desc = provider.describe()
    assert isinstance(desc, ModelDescriptor)
    assert desc.provider == "mock"
    assert desc.model == "test"
    assert desc.streaming is True
    assert desc.embeddings is True


# ---------------------------------------------------------------------------
# Missing SDK → actionable ConfigurationError
# ---------------------------------------------------------------------------


def test_openai_missing_sdk_raises_configuration_error(monkeypatch):
    # Force `import openai` to fail regardless of whether it is installed.
    monkeypatch.setitem(sys.modules, "openai", None)
    from voodoo.ai.providers.openai import OpenAIProvider

    with pytest.raises(ConfigurationError, match="openai"):
        OpenAIProvider(model="gpt-4")


def test_anthropic_missing_sdk_raises_configuration_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    from voodoo.ai.providers.anthropic import AnthropicProvider

    with pytest.raises(ConfigurationError, match="anthropic"):
        AnthropicProvider(model="claude-3")


def test_gemini_missing_sdk_raises_configuration_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "google", None)
    monkeypatch.setitem(sys.modules, "google.generativeai", None)
    from voodoo.ai.providers.gemini import GeminiProvider

    with pytest.raises(ConfigurationError, match="google-generativeai"):
        GeminiProvider(model="gemini-1.5-pro")


def test_ollama_missing_sdk_raises_configuration_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", None)
    from voodoo.ai.providers.ollama import OllamaProvider

    with pytest.raises(ConfigurationError, match="ollama"):
        OllamaProvider(model="llama3")
