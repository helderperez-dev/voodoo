"""Model provider contract tests (ROADMAP §64, §47).

``ModelProviderContractTests`` is the portability suite every
``VoodooModelProvider`` implementation must pass unchanged. The default suite
runs against the deterministic ``MockProvider``; live providers
(OpenAI/Anthropic/Gemini/Ollama) are integration-gated behind their optional
SDK.
"""

from __future__ import annotations

import pytest

from voodoo.ai.providers import (
    EmbeddingResponse,
    ModelDescriptor,
    ProviderEvent,
    ProviderResponse,
)
from voodoo.ai.providers.mock import MockProvider


class ModelProviderContractTests:
    """Mixin run against every model provider."""

    def make_provider(self) -> MockProvider:
        raise NotImplementedError

    @pytest.fixture
    def provider(self) -> MockProvider:
        return self.make_provider()

    def test_describes_itself(self, provider):
        desc = provider.describe()
        assert isinstance(desc, ModelDescriptor)
        assert desc.provider == provider.name
        assert desc.model == provider.model
        assert isinstance(desc.modalities, list)
        assert "text" in desc.modalities
        assert isinstance(desc.context_window, int)
        assert isinstance(desc.streaming, bool)

    async def test_generate_returns_provider_response(self, provider):
        resp = await provider.generate([{"role": "user", "content": "hello"}])
        assert isinstance(resp, ProviderResponse)
        assert resp.content

    async def test_generate_matches_complete(self, provider):
        messages = [{"role": "user", "content": "hello contract"}]
        generated = await provider.generate(messages)
        completed = await provider.complete(messages)
        assert generated.content == completed.content

    async def test_stream_yields_events(self, provider):
        events = [e async for e in provider.stream([{"role": "user", "content": "hi"}])]
        assert events
        assert all(isinstance(e, ProviderEvent) for e in events)
        assert events[-1].type == "done"

    async def test_count_tokens_returns_non_negative_int(self, provider):
        count = await provider.count_tokens(
            [{"role": "user", "content": "one two three"}]
        )
        assert isinstance(count, int)
        assert count >= 0


class TestMockProviderContract(ModelProviderContractTests):
    """Mock provider is the default, deterministic contract subject."""

    def make_provider(self) -> MockProvider:
        return MockProvider(model="test")

    async def test_mock_embedding_roundtrip(self, provider):
        resp = await provider.embed(["hello world"])
        assert isinstance(resp, EmbeddingResponse)
        assert len(resp.embeddings) == 1
        assert all(isinstance(v, float) for v in resp.embeddings[0])

    async def test_mock_embedding_is_deterministic(self, provider):
        a = await provider.embed(["hello"])
        b = await provider.embed(["hello"])
        assert a.embeddings == b.embeddings

    async def test_mock_descriptor_advertises_embeddings(self, provider):
        desc = provider.describe()
        assert desc.embeddings is True
        assert desc.streaming is True


class TestEmbeddingDefault:
    """Providers that do not implement embeddings raise NotImplementedError."""

    async def test_base_embed_raises_not_implemented(self):
        from voodoo.ai.providers import LLMProvider

        class _NoEmbed(MockProvider):
            async def embed(self, texts: list[str], **kwargs: object):  # noqa: ARG002
                raise NotImplementedError(
                    f"provider {self.name!r} does not support embeddings"
                )

        provider = _NoEmbed(model="test")
        assert isinstance(provider, LLMProvider)
        with pytest.raises(NotImplementedError, match="embeddings"):
            await provider.embed(["x"])
