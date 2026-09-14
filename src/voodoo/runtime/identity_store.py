"""Durable Runtime identity registry backed by application.vstore."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

from voodoo.runtime.identity import Identity, IdentityKind

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

__all__ = ["IdentityStore", "VoodooStoreIdentityStore"]

_PREFIX = b"runtime:identity:data:"


class IdentityStore(Protocol):
    def save(self, identity: Identity) -> None: ...

    def get(self, identity_id: str) -> Identity | None: ...

    def list(self, *, kind: IdentityKind | None = None) -> list[Identity]: ...

    def delete(self, identity_id: str) -> bool: ...


class VoodooStoreIdentityStore:
    """Persist Runtime identity state without defining authorization semantics."""

    provider = "voodoo"

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self._runtime_store = runtime_store

    def _runtime(self) -> RuntimeStore:
        if self._runtime_store is not None:
            return self._runtime_store
        from voodoo.runtime.store import acquire_runtime_store

        return acquire_runtime_store()

    def _store(self) -> Any:
        runtime = self._runtime()
        provider = runtime.provider or runtime.start()
        if provider is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "Voodoo Store is disabled; durable Identity requires an explicit "
                "IdentityStore adapter or an enabled Runtime Store."
            )
        native = getattr(provider, "native", None)
        if native is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "The active Voodoo Store provider does not expose durable KV storage."
            )
        return native

    @property
    def path(self):
        return self._runtime().config.path

    def save(self, identity: Identity) -> None:
        self._store().put(
            self._key(identity.id),
            json.dumps(
                identity.describe(),
                separators=(",", ":"),
                sort_keys=True,
                default=str,
            ).encode("utf-8"),
        )

    def get(self, identity_id: str) -> Identity | None:
        raw = self._store().get(self._key(identity_id))
        if raw is None:
            return None
        return Identity.from_record(json.loads(bytes(raw).decode("utf-8")))

    def list(self, *, kind: IdentityKind | None = None) -> list[Identity]:
        identities = [
            Identity.from_record(json.loads(bytes(raw).decode("utf-8")))
            for _key, raw in self._store().scan_prefix(_PREFIX)
        ]
        if kind is not None:
            identities = [identity for identity in identities if identity.kind is kind]
        identities.sort(key=lambda identity: (identity.kind.value, identity.id))
        return identities

    def delete(self, identity_id: str) -> bool:
        store = self._store()
        if store.get(self._key(identity_id)) is None:
            return False
        tx = store.transaction()
        tx.delete(self._key(identity_id))
        tx.commit()
        return True

    def close(self) -> None:
        """No-op: RuntimeStore owns the shared Store lifecycle."""

    @staticmethod
    def _key(identity_id: str) -> bytes:
        return _PREFIX + identity_id.encode("utf-8")
