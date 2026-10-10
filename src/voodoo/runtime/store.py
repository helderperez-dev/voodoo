"""Runtime-owned durable Store provider boundary for Sprint 28.

The Runtime owns the semantic contract. Native ``voodoo_store`` classes stay
behind this module so application code and higher Runtime layers do not depend
on the binding directly.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
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
    "acquire_runtime_store",
    "activate_runtime_store",
    "bind_active_runtime_store",
    "create_store_provider",
    "get_active_runtime_store",
    "store_registry",
]

DEFAULT_STORE_PATH = Path(".voodoo/application.vstore")


def _parse_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


class StoreProviderError(VoodooError):
    """Runtime Store provider lifecycle or verification failure."""


@dataclass(frozen=True, slots=True)
class StoreConfig:
    """Provider-neutral Store configuration owned by the Runtime.

    Voodoo Store is the default durable application infrastructure. Applications
    may explicitly disable it or replace individual higher-level domains with
    external adapters, but a fresh Runtime starts with one local
    ``.voodoo/application.vstore``.
    """

    provider: str = "voodoo"
    path: Path = DEFAULT_STORE_PATH
    enabled: bool = True
    durability: str = "data"
    repair_torn_tail: bool = True
    max_bytes: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None = None) -> StoreConfig:
        """Resolve Store config with explicit mapping > env > defaults."""
        data = dict(value or {})
        known = {
            "provider",
            "path",
            "enabled",
            "durability",
            "repair_torn_tail",
            "max_bytes",
        }
        provider = (
            data.get("provider") or os.getenv("VOODOO_STORE_PROVIDER") or "voodoo"
        )
        path = data.get("path") or os.getenv("VOODOO_STORE_PATH") or DEFAULT_STORE_PATH
        enabled_value = (
            data["enabled"] if "enabled" in data else os.getenv("VOODOO_STORE_ENABLED")
        )
        durability = (
            data.get("durability") or os.getenv("VOODOO_STORE_DURABILITY") or "data"
        )
        repair_value = (
            data["repair_torn_tail"]
            if "repair_torn_tail" in data
            else os.getenv("VOODOO_STORE_REPAIR_TORN_TAIL")
        )
        max_bytes_value = data.get("max_bytes") or os.getenv("VOODOO_STORE_MAX_BYTES")
        max_bytes = int(max_bytes_value) if max_bytes_value is not None else None
        if max_bytes is not None and max_bytes < 1:
            raise ValueError("Store max_bytes must be positive")
        return cls(
            provider=str(provider),
            path=Path(path),
            enabled=_parse_bool(enabled_value, default=True),
            durability=str(durability),
            repair_torn_tail=_parse_bool(repair_value, default=True),
            max_bytes=max_bytes,
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
        max_bytes: int | None = None,
    ) -> None:
        self._path = Path(path)
        self._durability = durability
        self._repair_torn_tail = repair_torn_tail
        self._max_bytes = max_bytes
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
        if self._max_bytes is not None and self._path.exists():
            current_bytes = self._path.stat().st_size
            if current_bytes > self._max_bytes:
                raise StoreProviderError(
                    f"Store at {self._path} exceeds configured max_bytes "
                    f"({current_bytes} > {self._max_bytes})"
                )
        started = time.perf_counter()
        try:
            try:
                from voodoo.observability import store_span

                with store_span(
                    "store.open",
                    attributes={"provider": self.name, "durability": self._durability},
                ):
                    self._store = store_type.open(
                        self._path,
                        durability=self._durability,
                        repair_torn_tail=self._repair_torn_tail,
                        max_bytes=self._max_bytes,
                    )
            except TypeError as exc:
                # Older installed Store bindings predate native max_bytes.
                # Keep the compatibility path explicit; startup size checks
                # still apply, while new bindings enforce the limit per append.
                if "max_bytes" not in str(exc):
                    raise
                from voodoo.observability import store_span

                with store_span(
                    "store.open",
                    attributes={"provider": self.name, "durability": self._durability},
                ):
                    self._store = store_type.open(
                        self._path,
                        durability=self._durability,
                        repair_torn_tail=self._repair_torn_tail,
                    )
        except Exception as exc:
            raise StoreProviderError(
                f"Unable to open Voodoo Store at {self._path}: {exc}"
            ) from exc
        finally:
            self._record_metric(
                "open",
                (time.perf_counter() - started) * 1000,
                error=self._store is None,
            )

    def close(self) -> None:
        """Close the Store; repeated calls are safe."""
        store = self._store
        if store is None:
            return
        started = time.perf_counter()
        failed = False
        try:
            from voodoo.observability import store_span

            with store_span("store.close", attributes={"provider": self.name}):
                store.close()
        except Exception as exc:
            failed = True
            raise StoreProviderError(
                f"Unable to close Voodoo Store at {self._path}: {exc}"
            ) from exc
        finally:
            self._store = None
            self._record_metric(
                "close", (time.perf_counter() - started) * 1000, error=failed
            )

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

        started = time.perf_counter()
        try:
            from voodoo.observability import store_span

            with store_span("store.health", attributes={"provider": self.name}):
                report = store_type.verify(self._path)
        except Exception as exc:
            # The native writer keeps an exclusive lock while this provider is
            # open, so a second verification handle can report the expected
            # "already open" contention.  The open handle itself is the
            # stronger readiness signal; retain a bounded size check and mark
            # integrity verification as deferred until shutdown/recovery.
            if self.opened and "already open by another writer" in str(exc):
                file_bytes = self._path.stat().st_size
                within_limit = (
                    self._max_bytes is None or file_bytes <= self._max_bytes
                )
                details = {
                    "exists": True,
                    "file_bytes": file_bytes,
                    "max_bytes": self._max_bytes,
                    "within_limit": within_limit,
                    "verification_deferred": True,
                }
                self._attach_native_health(details)
                return StoreHealth(
                    provider=self.name,
                    path=self._path,
                    opened=True,
                    verified=within_limit,
                    details=details,
                )
            self._record_metric(
                "recovery.verify",
                (time.perf_counter() - started) * 1000,
                error=True,
            )
            failure_details: dict[str, Any] = {"exists": True, "error": str(exc)}
            self._attach_native_health(failure_details)
            return StoreHealth(
                provider=self.name,
                path=self._path,
                opened=self.opened,
                verified=False,
                details=failure_details,
            )

        self._record_metric(
            "recovery.verify",
            (time.perf_counter() - started) * 1000,
            bytes_count=int(getattr(report, "file_bytes", 0) or 0),
        )

        file_bytes = int(getattr(report, "file_bytes", 0) or 0)
        details = {
            "exists": True,
            "file_bytes": file_bytes,
            "valid_bytes": getattr(report, "valid_bytes", None),
            "records": getattr(report, "records", None),
            "committed_transactions": getattr(report, "committed_transactions", None),
            "pending_transactions": getattr(report, "pending_transactions", None),
            "keys": getattr(report, "keys", None),
            "has_torn_tail": getattr(report, "has_torn_tail", None),
            "max_bytes": self._max_bytes,
        }
        self._attach_native_health(details)
        if self._max_bytes is not None and file_bytes > self._max_bytes:
            details["within_limit"] = False
            return StoreHealth(
                provider=self.name,
                path=self._path,
                opened=self.opened,
                verified=False,
                details=details,
            )
        details["within_limit"] = True
        return StoreHealth(
            provider=self.name,
            path=self._path,
            opened=self.opened,
            verified=True,
            details=details,
        )

    def _attach_native_health(self, details: dict[str, Any]) -> None:
        """Attach bounded numeric native health without exposing payload data.

        The Runtime provider is intentionally compatible with older bindings,
        so a missing or failing ``health_report`` must not turn an otherwise
        valid verification result into a failure. Only documented scalar
        counters and bounded nested metric maps are copied; store IDs,
        namespaces, keys, and object payloads never cross this boundary.
        """
        store = self._store
        report_fn = getattr(store, "health_report", None) if store is not None else None
        if not callable(report_fn):
            return
        try:
            report = report_fn()
        except Exception as exc:
            self._record_metric("health_report", 0.0, error=True)
            import logging

            from voodoo.security.redaction import redact_string

            logging.getLogger(__name__).debug(
                "native Store health report unavailable error=%s",
                redact_string(str(exc)),
            )
            return
        if not isinstance(report, Mapping):
            return

        snapshot = self._bounded_health_snapshot(report)
        if snapshot:
            details["native_health"] = snapshot

    @staticmethod
    def _bounded_health_snapshot(report: Mapping[str, Any]) -> dict[str, Any]:
        """Copy only documented scalar health values and bounded metric maps."""

        scalar_keys = (
            "format_major",
            "format_minor",
            "max_bytes",
            "namespace_max_bytes",
            "compaction_backlog_bytes",
            "lock_contentions_total",
            "object_reads_total",
            "object_bytes_read_total",
            "queue_ready",
            "queue_leased",
            "queue_dead",
            "queue_total",
            "queue_oldest_ready_at_ms",
            "queue_ready_lag_ms",
            "within_limit",
        )
        snapshot: dict[str, Any] = {}
        for key in scalar_keys:
            value = report.get(key)
            if value is None or isinstance(value, (bool, int, float)):
                snapshot[key] = value
        for section in ("metrics", "storage"):
            values = report.get(section)
            if not isinstance(values, Mapping):
                continue
            bounded = {
                str(key): value
                for key, value in values.items()
                if value is None or isinstance(value, (bool, int, float))
            }
            if bounded:
                snapshot[section] = bounded
        return snapshot

    @staticmethod
    def _record_metric(
        operation: str,
        latency_ms: float,
        *,
        error: bool = False,
        bytes_count: int = 0,
    ) -> None:
        """Report metrics and a correlated metric span without requiring telemetry."""
        try:
            from voodoo.observability import store_span, telemetry_store

            with store_span(
                f"store.metric.{operation}",
                attributes={"provider": "voodoo", "operation": operation},
            ):
                telemetry_store.record_store_operation(
                    operation,
                    latency_ms,
                    error=error,
                    bytes_count=bytes_count,
                )
        except Exception as error:
            # Observability must not become a Store availability dependency.
            import logging

            from voodoo.security.redaction import redact_string

            logging.getLogger(__name__).debug(
                "Store operation telemetry unavailable error=%s",
                redact_string(str(error)),
            )
            return

    def _load_store_type(self) -> Any:
        if self._store_type is not None:
            return self._store_type
        try:
            module = import_module("voodoo_store")
        except ImportError as exc:
            raise ConfigurationError(
                "Voodoo Store is the default durable provider but the 'voodoo-store' "
                "package is not installed. Reinstall voodoo-framework or run "
                "`pip install voodoo-store`."
            ) from exc
        self._store_type = module.Store
        return self._store_type


def _create_voodoo_provider(config: StoreConfig) -> StoreProvider:
    return VoodooStoreProvider(
        config.path,
        durability=config.durability,
        repair_torn_tail=config.repair_torn_tail,
        max_bytes=config.max_bytes,
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
    """Own exactly one Store provider for a Runtime lifecycle."""

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


_active_runtime_store: RuntimeStore | None = None
_shared_runtime_store: RuntimeStore | None = None


def bind_active_runtime_store(runtime_store: RuntimeStore | None) -> None:
    """Bind the application-owned Store for Runtime infrastructure adapters.

    Domain adapters consume this Runtime-owned handle instead of opening their
    own ``.vstore`` files. Standalone consumers use :func:`acquire_runtime_store`
    so every subsystem inside one process converges on one writer.
    """
    global _active_runtime_store
    _active_runtime_store = runtime_store


def get_active_runtime_store() -> RuntimeStore | None:
    """Return the Store owned by the active application Runtime, if any."""
    return _active_runtime_store


def acquire_runtime_store(config: StoreConfig | None = None) -> RuntimeStore:
    """Return the process-shared Store for standalone Runtime infrastructure.

    This is the only supported escape hatch for infrastructure used before an
    ``App`` lifespan exists (for example ``mesh`` or direct ``enqueue()``). It
    prevents each adapter from opening its own writer against the same embedded
    Store file.
    """
    global _shared_runtime_store

    if _active_runtime_store is not None:
        return _active_runtime_store

    resolved = config or StoreConfig.from_mapping()
    if _shared_runtime_store is None:
        _shared_runtime_store = RuntimeStore(resolved)
        _shared_runtime_store.start()
        return _shared_runtime_store

    if _shared_runtime_store.config != resolved:
        _shared_runtime_store.stop()
        _shared_runtime_store = RuntimeStore(resolved)
        _shared_runtime_store.start()
    elif not _shared_runtime_store.started:
        _shared_runtime_store.start()
    return _shared_runtime_store


def activate_runtime_store(config: StoreConfig) -> RuntimeStore:
    """Promote the shared standalone Store into the application lifecycle.

    If infrastructure touched Store before ASGI startup, the App adopts that
    exact ``RuntimeStore`` instance instead of attempting to open a competing
    writer. A mismatched standalone configuration is closed before activation.
    A failed startup may leave an unstarted RuntimeStore registered as active;
    that inert residue is safe to replace on the next activation.
    """
    global _active_runtime_store, _shared_runtime_store

    if _active_runtime_store is not None:
        if _active_runtime_store.config == config:
            if config.enabled and not _active_runtime_store.started:
                _active_runtime_store.start()
            return _active_runtime_store
        if _active_runtime_store.started:
            raise StoreProviderError(
                "A Voodoo RuntimeStore is already active with a different configuration"
            )
        _active_runtime_store.stop()
        _active_runtime_store = None

    if _shared_runtime_store is not None:
        if _shared_runtime_store.config == config:
            runtime_store = _shared_runtime_store
            _shared_runtime_store = None
        else:
            _shared_runtime_store.stop()
            _shared_runtime_store = None
            runtime_store = RuntimeStore(config)
    else:
        runtime_store = RuntimeStore(config)

    if config.enabled:
        runtime_store.start()
    _active_runtime_store = runtime_store
    return runtime_store
