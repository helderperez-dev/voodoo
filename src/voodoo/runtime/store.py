"""Runtime-owned durable store provider boundary for Sprint 28.

The Runtime owns the semantic contract. Native ``voodoo_store`` classes stay
behind this module so application code and higher runtime layers do not depend
on the binding directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from voodoo.core.errors import ConfigurationError, VoodooError

__all__ = [
    "StoreHealth",
    "StoreProvider",
    "StoreProviderError",
    "VoodooStoreProvider",
]


class StoreProviderError(VoodooError):
    """Runtime store provider lifecycle or verification failure."""


@dataclass(frozen=True, slots=True)
class StoreHealth:
    """Minimal provider-neutral health projection.

    Parameters
    ----------
    provider:
        Provider identifier.
    path:
        Durable store location.
    opened:
        Whether this provider currently owns an open store handle.
    verified:
        Whether the backing store passed its native verification operation.
    details:
        Provider-specific diagnostic values safe to expose to Runtime tooling.
    """

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


class VoodooStoreProvider:
    """Lazy adapter around the standalone ``voodoo-store`` Python binding.

    Parameters
    ----------
    path:
        Path to the application ``.vstore`` file.
    durability:
        Native Store durability mode: ``strict``, ``data`` or ``relaxed``.
    repair_torn_tail:
        Allow native recovery to repair a torn append-log tail on open.
    """

    name = "voodoo"

    def __init__(
        self,
        path: str | Path = ".voodoo/application.vstore",
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
            "committed_transactions": getattr(
                report, "committed_transactions", None
            ),
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
