"""Sprint 28.1 tests for Store registry/config/lifecycle semantics."""

from pathlib import Path

import pytest

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.store import (
    DEFAULT_STORE_PATH,
    RuntimeStore,
    StoreConfig,
    StoreHealth,
    StoreProvider,
    StoreProviderRegistry,
)


class FakeProvider:
    name = "fake"

    def __init__(self, config: StoreConfig) -> None:
        self.config = config
        self._opened = False
        self.open_calls = 0
        self.close_calls = 0

    @property
    def path(self) -> Path:
        return self.config.path

    @property
    def opened(self) -> bool:
        return self._opened

    def open(self) -> None:
        self.open_calls += 1
        self._opened = True

    def close(self) -> None:
        self.close_calls += 1
        self._opened = False

    def health(self) -> StoreHealth:
        return StoreHealth(
            provider=self.name,
            path=self.path,
            opened=self.opened,
            verified=True,
            details={"fake": True},
        )


def _registry() -> StoreProviderRegistry:
    registry = StoreProviderRegistry()
    registry.register("fake", FakeProvider)
    return registry


def test_store_config_has_future_default_without_enabling_it_yet() -> None:
    config = StoreConfig()

    assert config.provider == "voodoo"
    assert config.path == DEFAULT_STORE_PATH
    assert config.enabled is False
    assert config.durability == "data"
    assert config.repair_torn_tail is True


def test_store_config_from_mapping_preserves_provider_specific_extra() -> None:
    config = StoreConfig.from_mapping(
        {
            "provider": "fake",
            "path": ".voodoo/custom.vstore",
            "enabled": True,
            "durability": "strict",
            "repair_torn_tail": False,
            "region": "local-a",
        }
    )

    assert config.provider == "fake"
    assert config.path == Path(".voodoo/custom.vstore")
    assert config.enabled is True
    assert config.durability == "strict"
    assert config.repair_torn_tail is False
    assert config.extra == {"region": "local-a"}


def test_registry_resolves_provider_without_leaking_native_binding() -> None:
    registry = _registry()
    config = StoreConfig(provider="fake", enabled=True)

    provider = registry.create(config)

    assert isinstance(provider, StoreProvider)
    assert isinstance(provider, FakeProvider)
    assert provider.config is config
    assert registry.names() == ("fake",)


def test_registry_rejects_unknown_provider_with_available_names() -> None:
    registry = _registry()

    with pytest.raises(ConfigurationError, match="Unknown Store provider 'missing'") as exc:
        registry.create(StoreConfig(provider="missing"))

    assert "fake" in str(exc.value)


def test_registry_rejects_empty_registration_name() -> None:
    registry = StoreProviderRegistry()

    with pytest.raises(ConfigurationError, match="cannot be empty"):
        registry.register(" ", FakeProvider)


def test_runtime_store_disabled_does_not_create_or_open_provider() -> None:
    registry = _registry()
    runtime_store = RuntimeStore(StoreConfig(provider="fake", enabled=False), registry=registry)

    assert runtime_store.start() is None
    assert runtime_store.provider is None
    assert runtime_store.started is False
    assert runtime_store.health() is None


def test_runtime_store_owns_single_provider_lifecycle() -> None:
    registry = _registry()
    runtime_store = RuntimeStore(StoreConfig(provider="fake", enabled=True), registry=registry)

    first = runtime_store.start()
    second = runtime_store.start()

    assert first is second
    assert isinstance(first, FakeProvider)
    assert first.open_calls == 2
    assert runtime_store.started is True
    assert runtime_store.health() == StoreHealth(
        provider="fake",
        path=DEFAULT_STORE_PATH,
        opened=True,
        verified=True,
        details={"fake": True},
    )

    runtime_store.stop()

    assert first.close_calls == 1
    assert runtime_store.provider is None
    assert runtime_store.started is False


def test_runtime_store_stop_is_idempotent() -> None:
    registry = _registry()
    runtime_store = RuntimeStore(StoreConfig(provider="fake", enabled=True), registry=registry)

    provider = runtime_store.start()
    assert isinstance(provider, FakeProvider)

    runtime_store.stop()
    runtime_store.stop()

    assert provider.close_calls == 1
