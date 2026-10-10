"""Voodoo Store-backed object storage.

Object bytes are stored through Voodoo Store's native content-addressed Object
subsystem. Public object keys are durable named references. Metadata is itself a
content-addressed Object under a separate reference namespace, keeping the
adapter fully on native Object primitives without a parallel KV index.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote

from voodoo.core.errors import ConfigurationError
from voodoo.observability import store_operation
from voodoo.runtime.store import acquire_runtime_store
from voodoo.storage.objects.interfaces import (
    ObjectStoreCapabilities,
    validate_content_type,
    validate_object_key,
    validate_object_prefix,
)

_DATA_NAMESPACE = b"runtime.objects.data"
_META_NAMESPACE = b"runtime.objects.meta"
_CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")


def _bounded_native_chunk(chunk: Any, chunk_size: int) -> bytes:
    """Coerce one native object chunk while enforcing the transfer bound."""
    value = bytes(chunk)
    if len(value) > chunk_size:
        raise ValueError(
            "object provider returned a chunk larger than the requested limit"
        )
    return value


def _verify_payload(data: bytes, metadata: dict[str, Any]) -> None:
    """Verify native bytes against their durable metadata contract."""
    if len(data) != metadata["size"] or hashlib.sha256(data).hexdigest() != metadata[
        "checksum"
    ]:
        raise ValueError("object content checksum mismatch")


def _verify_stream(digest: Any, size: int, metadata: dict[str, Any]) -> None:
    if size != metadata["size"] or digest.hexdigest() != metadata["checksum"]:
        raise ValueError("object content checksum mismatch")


def _validate_object_metadata(metadata: Any, key: str) -> dict[str, Any]:
    """Validate the durable metadata shape before exposing it to callers."""
    if not isinstance(metadata, dict):
        raise ValueError("object metadata must be a JSON object")
    if metadata.get("key") != key:
        raise ValueError("object metadata key does not match the requested key")
    size = metadata.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError("object metadata size must be a non-negative integer")
    checksum = metadata.get("checksum")
    if not isinstance(checksum, str) or _CHECKSUM_RE.fullmatch(checksum) is None:
        raise ValueError("object metadata checksum must be a SHA-256 hex digest")
    if not isinstance(metadata.get("content_type"), str):
        raise ValueError("object metadata content_type must be a string")
    if not isinstance(metadata.get("created_at"), str):
        raise ValueError("object metadata created_at must be a string")
    return cast(dict[str, Any], metadata)


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
        return validate_object_key(key).encode("utf-8")

    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        content_type = validate_content_type(content_type)
        with store_operation("object.put", provider=self.provider) as details:
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
            details["bytes"] = len(payload)
            return checksum

    def _resolve(self, namespace: bytes, key: str) -> bytes | None:
        object_id = self._native().resolve_object_ref(namespace, self._name(key))
        return bytes(object_id) if object_id is not None else None

    def get(self, key: str) -> bytes:
        with store_operation("object.get", provider=self.provider) as details:
            store = self._native()
            object_id = self._resolve(_DATA_NAMESPACE, key)
            if object_id is None:
                raise KeyError(f"object {key!r} not found")
            raw = store.get_object(object_id)
            if raw is None:
                raise KeyError(f"object {key!r} not found")
            data = bytes(raw)
            _verify_payload(data, self.stat(key))
            details["bytes"] = len(data)
            return data

    def iter_chunks(self, key: str, chunk_size: int = 65_536) -> Iterator[bytes]:
        """Yield bounded native chunks without materializing the full object."""
        with store_operation("object.get", provider=self.provider) as details:
            if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
                raise TypeError("chunk_size must be an integer")
            if chunk_size <= 0 or chunk_size > 8 * 1024 * 1024:
                raise ValueError("chunk_size must be between 1 and 8388608 bytes")
            store = self._native()
            object_id = self._resolve(_DATA_NAMESPACE, key)
            if object_id is None:
                raise KeyError(f"object {key!r} not found")
            metadata = self.stat(key)
            digest = hashlib.sha256()
            size = 0
            get_chunk = getattr(store, "get_object_chunk", None)
            if get_chunk is None:
                # Older 0.3 wheels predate the bounded native primitive. Keep
                # the adapter compatible while making the fallback explicit;
                # current bindings take the bounded path below.
                raw = store.get_object(object_id)
                if raw is None:
                    raise KeyError(f"object {key!r} not found")
                data = bytes(raw)
                for offset in range(0, len(data), chunk_size):
                    value = data[offset : offset + chunk_size]
                    digest.update(value)
                    size += len(value)
                    details["bytes"] = details.get("bytes", 0) + len(value)
                    yield value
                _verify_stream(digest, size, metadata)
                return
            offset = 0
            while True:
                chunk = get_chunk(object_id, offset, chunk_size)
                if chunk is None:
                    raise KeyError(f"object {key!r} not found")
                value = _bounded_native_chunk(chunk, chunk_size)
                if not value:
                    _verify_stream(digest, size, metadata)
                    return
                digest.update(value)
                size += len(value)
                details["bytes"] = details.get("bytes", 0) + len(value)
                yield value
                offset += len(value)

    def delete(self, key: str) -> bool:
        with store_operation("object.delete", provider=self.provider):
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
        try:
            metadata = json.loads(bytes(raw).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("object metadata is not valid JSON") from error
        return _validate_object_metadata(metadata, key)

    def list(self, prefix: str = "") -> list[str]:
        prefix = validate_object_prefix(prefix)
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
