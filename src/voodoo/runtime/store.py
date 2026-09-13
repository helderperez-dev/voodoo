"""Runtime-owned durable Store provider boundary for Sprint 28.

The Runtime owns the semantic contract. Native ``voodoo_store`` classes stay
behind this module so application code and higher Runtime layers do not depend
on the binding directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from voodoo.core.errors import ConfigurationError, VoodooError

__all__ = [
    "DEFAULT_STORE_PATH",
    "StoreConfig",
    "StoreHealth",
    "StoreProvider",
    "StoreProviderError",
    "StoreProviderRegistry",
    "RuntimeStore",
    "VoodooStoreProvider",
    "create_store_provider",
    "store_registry",
]

DEFAULT_STORE_PATH = Path(".voodoo/application.vstore")


class StoreProviderError(VoodooError):
    """Runtime Store provider lifecycle or verification failure."""


@dataclass(frozen=True, slots=True)
class StoreConfig:
    """Provider-neutral Store configuration owned by the Runtime.

    ``enabled`` intentionally remains ``False`` during Sprint 28.1. The next
    slice makes Voodoo Store the application default only after packaging and
    compatibility behavior are wired. Keeping the switch explicit here lets
    the lifecycle land before changing existing 2.x defaults.
    """

    provider: str = "voodoo"
    path: Path = DEFAULT_STORE_PATH
    enabled: bool = False
    durability: str = "data"
    repair_torn_tail: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None = None) -> StoreConfig:
        data = dict(value or {})
        known = {
            "provider",
            "path",
            "enabled",
            "durability",
            "repair_torn_tail",
        }
        return cls(
            provider=str(data.get("provider") or "voodoo"),
            path=Path(data.get("path") or DEFAULT_STORE_PATH),
            enabled=bool(data.get("enabled", False)),
            durability=str(data.get("durability") or "data"),
            repair_torn_tail=bool(data.get("repair_torn_tail", True)),
            extra={key: item for key, item in data.items() if key not in known},
        )


@dataclass(frozen=True, slots=True)
class StoreHealth:
    """Minimal provider-neutral health projection."""

    provider: str
    path: Path
    opened: bool
    verified: bool
    details: dict[str, Any]


@runtime_checkable
class StoreProvider(Protocol):
    """Runtime-owned lifecycle contract for durable application infrastructure."""

    @property
    def name(self) -> str: ...

    @property
    def path(self) -> Path: ...

    @property
    def opened(self) -> bool: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def health(self) -> StoreHealth: ...


StoreProviderFactory = Callable[[StoreConfig], StoreProvider]


class StoreProviderRegistry:
    """Registry for Runtime infrastructure providers.

    This registry is intentionally separate from the legacy per-domain adapter
    registry. A Store provider is an application-infrastructure substrate from
    which Data/Work/Events/Objects adapters can later be derived; it is not a
    database adapter itself.
    """

    def __init__(self) -> None:
        self._providers: dict[str, StoreProviderFactory] = {}

    def register(self, name: str, factory: StoreProviderFactory) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ConfigurationError("Store provider name cannot be empty")
        self._providers[normalized] = factory

    def create(self, config: StoreConfig) -> StoreProvider:
        name = config.provider.strip().lower()
        factory = self._providers.get(name)
        if factory is None:
            available = ", ".join(sorted(self._providers)) or "none"
            raise ConfigurationError(
                f"Unknown Store provider '{config.provider}'. "
                f"Available Store providers: {available}."
            )
        return factory(config)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


class VoodooStoreProvider:
    """Lazy adapter around the standalone ``voodoo-store`` Python binding."""

    name = "voodoo"

    def __init__(
        self,
        path: str | Path = DEFAULT_STORE_PATH,
        *,
        durability: str = "data",
        repair_torn_tail: bool = True,
    ) -> None:
        self._path = Path(path)
        self._durability = durability
        self._repair_torn_tail = repair_torn_tail
        self._store: Any | None = None
        self._store_type: Any | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def opened(self) -> bool:
        return self._store is not None

    @property
    def native(self) -> Any:
        """Return the private native handle for lower adapter layers.

        Higher-level application APIs must not expose this object directly.
        """
        if self._store is None:
            raise StoreProviderError("Voodoo Store provider is not open")
        return self._store

    def open(self) -> None:
        """Open the Store exactly once for this provider instance."""
        if self._store is not None:
            return

        store_type = self._load_store_type()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._store = store_type.open(
                self._path,
                durability=self._durability,
                repair_torn_tail=self._repair_torn_tail,
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary normalizes SDK errors
            raise StoreProviderError(
                f"Unable to open Voodoo Store at {self._path}: {exc}"
            ) from exc

    def close(self) -> None:
        """Close the Store; repeated calls are safe."""
        store = self._store
        if store is None:
            return
        try:
            store.close()
        except Exception as exc:  # noqa: BLE001 - provider boundary normalizes SDK errors
            raise StoreProviderError(
                f"Unable to close Voodoo Store at {self._path}: {exc}"
            ) from exc
        finally:
            self._store = None

    def health(self) -> StoreHealth:
        """Return provider-neutral health using native verification evidence."""
        store_type = self._load_store_type()
        if not self._path.exists():
            return StoreHealth(
                provider=self.name,
                path=self._path,
                opened=self.opened,
                verified=False,
                details={"exists": False},
            )

        try:
            report = store_type.verify(self._path)
        except Exception as exc:  # noqa: BLE001 - provider boundary normalizes SDK errors
            return StoreHealth(
                provider=self.name,
                path=self._path,
                opened=self.opened,
                verified=False,
                details={"exists": True, "error": str(exc)},
            )

        details = {
            "exists": True,
            "file_bytes": getattr(report, "file_bytes", None),
            "valid_bytes": getattr(report, "valid_bytes", None),
            "records": getattr(report, "records", None),
            "committed_transactions": getattr(report, "committed_transactions", None),
            "pending_transactions": getattr(report, "pending_transactions", None),
            "keys": getattr(report, "keys", None),
            "has_torn_tail": getattr(report, "has_torn_tail", None),
        }
        return StoreHealth(
            provider=self.name,
            path=self._path,
            opened=self.opened,
            verified=True,
            details=details,
        )

    def _load_store_type(self) -> Any:
        if self._store_type is not None:
            return self._store_type
        try:
            module = import_module("voodoo_store")
        except ImportError as exc:
            raise ConfigurationError(
                "Voodoo Store is not installed. Sprint 28 keeps the binding behind "
                "a lazy Runtime provider boundary while packaging/default migration "
                "is completed. Install the 'voodoo-store' package to use provider "
                "'voodoo'."
            ) from exc
        self._store_type = module.Store
        return self._store_type


def _create_voodoo_provider(config: StoreConfig) -> StoreProvider:
    return VoodooStoreProvider(
        config.path,
        durability=config.durability,
        repair_torn_tail=config.repair_torn_tail,
    )


store_registry = StoreProviderRegistry()
store_registry.register("voodoo", _create_voodoo_provider)


def create_store_provider(
    config: StoreConfig,
    *,
    registry: StoreProviderRegistry = store_registry,
) -> StoreProvider:
    """Resolve one Store provider through the Runtime-owned registry."""
    return registry.create(config)


class RuntimeStore:
    """Own exactly one Store provider for a Runtime lifecycle.

    Construction does not open files or import the native Store binding. The
    provider is created/opened only when ``start`` is called and the Store is
    enabled. This is the seam the application lifespan will adopt when Sprint
    28.2 turns Store-backed infrastructure on by default.
    """

    def __init__(
        self,
        config: StoreConfig | None = None,
        *,
        registry: StoreProviderRegistry = store_registry,
    ) -> None:
        self.config = config or StoreConfig()
        self._registry = registry
        self._provider: StoreProvider | None = None

    @property
    def provider(self) -> StoreProvider | None:
        return self._provider

    @property
    def started(self) -> bool:
        return self._provider is not None and self._provider.opened

    def start(self) -> StoreProvider | None:
        if not self.config.enabled:
            return None
        if self._provider is None:
            self._provider = create_store_provider(self.config, registry=self._registry)
        if not self._provider.opened:
            self._provider.open()
        return self._provider

    def stop(self) -> None:
        if self._provider is None:
            return
        try:
            self._provider.close()
        finally:
            self._provider = None

    def health(self) -> StoreHealth | None:
        if self._provider is None:
            return None
        return self._provider.health()
