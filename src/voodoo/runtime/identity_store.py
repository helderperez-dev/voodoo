"""Durable Runtime identity registry backed by application.vstore."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

from voodoo.runtime.identity import Identity, IdentityKind

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

__all__ = ["IdentityStore", "VoodooStoreIdentityStore"]

_PREFIX = b"runtime:identity:data:"
_COLLECTION = b"runtime.identity"
_SCHEMA_KEY = "_schema_version"
_SCHEMA_VERSION = 1


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

    def _native_collections(self, store: Any) -> bool:
        """Return whether this binding supports native collection records."""
        return all(
            hasattr(store, method)
            for method in ("create_collection", "upsert_record", "get_record", "scan_collection")
        )

    def _ensure_collection(self, store: Any) -> None:
        if self._native_collections(store):
            store.create_collection(_COLLECTION, schema_version=_SCHEMA_VERSION, codec=b"json")

    @property
    def path(self) -> Any:
        return self._runtime().config.path

    def save(self, identity: Identity) -> None:
        record = identity.describe()
        record[_SCHEMA_KEY] = _SCHEMA_VERSION
        encoded = json.dumps(
            record, separators=(",", ":"), sort_keys=True, default=str
        ).encode("utf-8")
        store = self._store()
        if self._native_collections(store):
            self._ensure_collection(store)
            store.upsert_record(_COLLECTION, identity.id.encode("utf-8"), encoded)
            store.delete(self._key(identity.id))
            return
        store.put(self._key(identity.id), encoded)

    def get(self, identity_id: str) -> Identity | None:
        store = self._store()
        raw = None
        if self._native_collections(store):
            self._ensure_collection(store)
            record = store.get_record(_COLLECTION, identity_id.encode("utf-8"))
            if record is not None:
                raw = record[1]
        if raw is None:
            raw = store.get(self._key(identity_id))
        if raw is None:
            return None
        return Identity.from_record(self._decode(identity_id, bytes(raw)))

    def list(self, *, kind: IdentityKind | None = None) -> list[Identity]:
        store = self._store()
        identities_by_id: dict[str, Identity] = {}
        if self._native_collections(store):
            self._ensure_collection(store)
            for key, raw, _indexes in store.scan_collection(_COLLECTION):
                identity_id = bytes(key).decode("utf-8")
                identity = Identity.from_record(self._decode(identity_id, bytes(raw)))
                identities_by_id[identity.id] = identity
        identities_by_id.update({
            identity.id: identity
            for identity in (
            Identity.from_record(
                self._decode(key[len(_PREFIX) :].decode("utf-8"), bytes(raw))
            )
            for key, raw in store.scan_prefix(_PREFIX)
            )
            if identity.id not in identities_by_id
        })
        identities = list(identities_by_id.values())
        if kind is not None:
            identities = [identity for identity in identities if identity.kind is kind]
        identities.sort(key=lambda identity: (identity.kind.value, identity.id))
        return identities

    def delete(self, identity_id: str) -> bool:
        store = self._store()
        deleted = False
        if self._native_collections(store):
            self._ensure_collection(store)
            deleted = bool(store.delete_record(_COLLECTION, identity_id.encode("utf-8")))
        legacy = store.get(self._key(identity_id))
        if legacy is not None:
            tx = store.transaction()
            tx.delete(self._key(identity_id))
            tx.commit()
            deleted = True
        return deleted

    def close(self) -> None:
        """No-op: RuntimeStore owns the shared Store lifecycle."""

    @staticmethod
    def _key(identity_id: str) -> bytes:
        return _PREFIX + identity_id.encode("utf-8")

    @staticmethod
    def _decode(identity_id: str, raw: bytes) -> dict[str, Any]:
        try:
            record = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("identity record is not valid UTF-8 JSON") from error
        if not isinstance(record, dict):
            raise ValueError("identity record must be a JSON object")
        version = record.pop(_SCHEMA_KEY, 0)
        if not isinstance(version, int) or isinstance(version, bool):
            raise ValueError("identity schema version must be an integer")
        if version > _SCHEMA_VERSION:
            raise ValueError(
                f"identity schema {version} is newer than supported schema {_SCHEMA_VERSION}"
            )
        if record.get("id") not in (None, identity_id):
            raise ValueError("identity record does not match its key")
        record["id"] = identity_id
        return record
