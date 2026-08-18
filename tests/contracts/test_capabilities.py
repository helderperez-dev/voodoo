"""Adapter capability negotiation contract tests (spec §9–§10, Sprint 8).

These tests pin the negotiation layer's core rules:

- every adapter kind declares its guarantees through a ``*Capabilities``
  model that shares one shape (provider + boolean flags);
- ``require`` rejects loudly and never silently violates correctness;
- ``negotiate`` proceeds when supported, emulates when safe, and fails
  otherwise;
- ``capability_matrix`` renders a uniform provider matrix.

The per-adapter ``.capabilities()`` declarations are verified in the
dedicated contract suites (database/queue/eventbus/objectstore); this file
covers the shared machinery only.
"""

from __future__ import annotations

import pytest

from voodoo.adapters.capabilities import (
    AdapterCapabilities,
    CapabilityError,
    DatabaseCapabilities,
    EventBusCapabilities,
    ObjectStoreCapabilities,
    QueueCapabilities,
    capability_matrix,
    negotiate,
    require,
)


class TestRequire:
    def test_require_passes_when_supported(self) -> None:
        caps = DatabaseCapabilities("sqlite", transactions=True, migrations=True)
        require(caps, "transactions")  # must not raise

    def test_require_raises_on_unsupported(self) -> None:
        caps = ObjectStoreCapabilities("local", presign_urls=False)
        with pytest.raises(CapabilityError) as exc:
            require(caps, "presign_urls", hint="use s3 / minio for presigned URLs")
        err = exc.value
        assert err.kind == "objectstore"
        assert err.provider == "local"
        assert err.feature == "presign_urls"
        assert "presign_urls" in str(err)
        assert "s3 / minio" in str(err)

    def test_require_raises_attribute_error_for_unknown_flag(self) -> None:
        caps = QueueCapabilities("sqlite")
        with pytest.raises(AttributeError):
            require(caps, "nonexistent_flag")

    def test_supports_rejects_unknown_flag(self) -> None:
        caps = AdapterCapabilities("x")
        with pytest.raises(AttributeError):
            caps.supports("nope")


class TestNegotiate:
    def test_supported_returns_none(self) -> None:
        caps = DatabaseCapabilities("sqlite")
        assert negotiate(caps, "transactions") is None

    def test_emulate_runs_when_unsupported(self) -> None:
        caps = QueueCapabilities("memory", delayed_delivery=False)
        calls: list[str] = []
        result = negotiate(
            caps,
            "delayed_delivery",
            emulate=lambda: calls.append("emulated") or "fallback",
        )
        assert result == "fallback"
        assert calls == ["emulated"]

    def test_unsupported_without_emulate_raises(self) -> None:
        caps = EventBusCapabilities("local", durable=False)
        with pytest.raises(CapabilityError):
            negotiate(caps, "durable")


class TestCapabilityMatrix:
    def test_matrix_uses_provider_keys(self) -> None:
        adapters = [
            DatabaseCapabilities("sqlite"),
            EventBusCapabilities("local"),
        ]
        matrix = capability_matrix(adapters)
        assert set(matrix) == {"sqlite", "local"}
        assert matrix["sqlite"]["transactions"] is True
        assert matrix["local"]["durable"] is False

    def test_matrix_is_plain_json_values(self) -> None:
        desc = ObjectStoreCapabilities("s3", presign_urls=True).describe()
        assert desc["provider"] == "s3"
        assert desc["presign_urls"] is True
        assert isinstance(desc["checksums"], bool)


class TestSharedShape:
    def test_all_models_are_adapters(self) -> None:
        for caps in (
            DatabaseCapabilities("sqlite"),
            QueueCapabilities("sqlite"),
            EventBusCapabilities("local"),
            ObjectStoreCapabilities("local"),
        ):
            assert isinstance(caps, AdapterCapabilities)
            assert caps.provider

    def test_at_least_once_and_fifo_flags_are_booleans(self) -> None:
        caps = QueueCapabilities("sqlite")
        assert caps.delayed_delivery is True
        assert isinstance(caps.priority, bool)
        assert isinstance(caps.transactions, bool)
