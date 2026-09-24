"""Voodoo Store-backed object storage.

Object bytes are stored through Voodoo Store's native content-addressed Object
subsystem. Public object keys are durable named references. Metadata is itself a
content-addressed Object under a separate reference namespace, keeping the
adapter fully on native Object primitives without a parallel KV index.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.store import acquire_runtime_store
from voodoo.storage.objects.interfaces import ObjectStoreCapabilities

_DATA_NAMESPACE = b"runtime.objects.data"
_META_NAMESPACE = b"runtime.objects.meta"


class VoodooStoreObjectStore:
    """Object storage backed by native content-addressed Voodoo Store Objects."""

    provider = "voodoo"

    def capabilities(self) -> ObjectStoreCapabilities:
        return ObjectStoreCapabilities(
            provider=self.provider,
            presign_urls=False,
            checksums=True,
            metadata=True,
            multipart=False,
        )

    def _native(self) -> Any:
        runtime = acquire_runtime_store()
        provider = runtime.provider or runtime.start()
        if provider is None:
            raise ConfigurationError("Voodoo Store is disabled for object storage")
        native = getattr(provider, "native", None)
        required = (
            "resolve_object_ref",
            "get_object",
            "list_object_refs",
            "transaction",
        )
        missing = [
            name for name in required if native is None or not hasattr(native, name)
        ]
        if missing:
            raise ConfigurationError(
                "Voodoo Store 0.3+ native Objects are required for object storage. "
                f"Missing Store capabilities: {', '.join(missing)}."
            )
        return native

    @staticmethod
    def _name(key: str) -> bytes:
        encoded = key.encode("utf-8")
        if not encoded:
            raise ValueError("object key cannot be empty")
        return encoded

    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        payload = bytes(data)
        checksum = hashlib.sha256(payload).hexdigest()
        metadata = {
            "key": key,
            "size": len(payload),
            "content_type": content_type,
            "checksum": checksum,
            "created_at": datetime.now(UTC).isoformat(),
        }
        encoded_metadata = json.dumps(
            metadata,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        store = self._native()
        name = self._name(key)
        tx = store.transaction()
        if not hasattr(tx, "put_linked_object"):
            raise ConfigurationError(
                "Voodoo Store 0.3+ cross-domain Object transactions are required."
            )
        tx.put_linked_object(payload, _DATA_NAMESPACE, name)
        tx.put_linked_object(encoded_metadata, _META_NAMESPACE, name)
        tx.commit()
        return checksum

    def _resolve(self, namespace: bytes, key: str) -> bytes | None:
        object_id = self._native().resolve_object_ref(namespace, self._name(key))
        return bytes(object_id) if object_id is not None else None

    def get(self, key: str) -> bytes:
        store = self._native()
        object_id = self._resolve(_DATA_NAMESPACE, key)
        if object_id is None:
            raise KeyError(f"object {key!r} not found")
        raw = store.get_object(object_id)
        if raw is None:
            raise KeyError(f"object {key!r} not found")
        return bytes(raw)

    def delete(self, key: str) -> bool:
        store = self._native()
        name = self._name(key)
        if store.resolve_object_ref(_DATA_NAMESPACE, name) is None:
            return False

        tx = store.transaction()
        tx.unlink_object(_DATA_NAMESPACE, name)
        tx.unlink_object(_META_NAMESPACE, name)
        tx.commit()
        return True

    def exists(self, key: str) -> bool:
        return self._resolve(_DATA_NAMESPACE, key) is not None

    def stat(self, key: str) -> dict[str, Any]:
        store = self._native()
        metadata_id = self._resolve(_META_NAMESPACE, key)
        if metadata_id is None:
            raise KeyError(f"object {key!r} not found")
        raw = store.get_object(metadata_id)
        if raw is None:
            raise KeyError(f"object {key!r} not found")
        return json.loads(bytes(raw).decode("utf-8"))

    def list(self, prefix: str = "") -> list[str]:
        entries = self._native().list_object_refs(
            _DATA_NAMESPACE,
            prefix.encode("utf-8"),
        )
        return [bytes(name).decode("utf-8") for name, _object_id in entries]

    def presign(self, key: str, expires_in: int = 3600) -> str:
        del expires_in
        if not self.exists(key):
            raise KeyError(f"object {key!r} not found")
        return f"voodoo://objects/{quote(key, safe='/')}"

    def close(self) -> None:
        """Lifecycle is owned centrally by RuntimeStore."""
