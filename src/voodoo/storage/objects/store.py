"""Voodoo Store-backed object storage.

This adapter keeps object bytes and metadata inside the Runtime-owned
``application.vstore`` so the default Runtime does not require a parallel
filesystem metadata database or S3 service. It consumes the central Runtime
Store boundary rather than opening a competing writer.

The standalone Store core already has a richer object subsystem; until that
surface is exposed by the Python binding, this adapter uses the Store KV
contract as the stable compatibility boundary. The public Voodoo object API
therefore stays unchanged and can move to native Store Objects later without
application changes.
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

_DATA_PREFIX = b"runtime:objects:data:"
_META_PREFIX = b"runtime:objects:meta:"


class VoodooStoreObjectStore:
    """Object storage backed by the process-shared Runtime Store."""

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
        if native is None:
            raise ConfigurationError(
                "The active Voodoo Store provider does not expose durable KV storage"
            )
        return native

    @staticmethod
    def _key(prefix: bytes, key: str) -> bytes:
        return prefix + key.encode("utf-8")

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
        store = self._native()
        tx = store.transaction()
        tx.put(self._key(_DATA_PREFIX, key), payload)
        tx.put(
            self._key(_META_PREFIX, key),
            json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        )
        tx.commit()
        return checksum

    def get(self, key: str) -> bytes:
        raw = self._native().get(self._key(_DATA_PREFIX, key))
        if raw is None:
            raise KeyError(f"object {key!r} not found")
        return bytes(raw)

    def delete(self, key: str) -> bool:
        store = self._native()
        meta_key = self._key(_META_PREFIX, key)
        if store.get(meta_key) is None:
            return False
        tx = store.transaction()
        tx.delete(self._key(_DATA_PREFIX, key))
        tx.delete(meta_key)
        tx.commit()
        return True

    def exists(self, key: str) -> bool:
        return self._native().get(self._key(_META_PREFIX, key)) is not None

    def stat(self, key: str) -> dict[str, Any]:
        raw = self._native().get(self._key(_META_PREFIX, key))
        if raw is None:
            raise KeyError(f"object {key!r} not found")
        return json.loads(bytes(raw).decode("utf-8"))

    def list(self, prefix: str = "") -> list[str]:
        scan_prefix = _META_PREFIX + prefix.encode("utf-8")
        keys: list[str] = []
        for raw_key, _value in self._native().scan_prefix(scan_prefix):
            key = bytes(raw_key)[len(_META_PREFIX) :].decode("utf-8")
            keys.append(key)
        return sorted(keys)

    def presign(self, key: str, expires_in: int = 3600) -> str:
        del expires_in
        if not self.exists(key):
            raise KeyError(f"object {key!r} not found")
        return f"voodoo://objects/{quote(key, safe='/')}"

    def close(self) -> None:
        """Lifecycle is owned centrally by RuntimeStore."""
