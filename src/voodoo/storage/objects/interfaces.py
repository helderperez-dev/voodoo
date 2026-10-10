"""Object store capability interface (Sprint 6)."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from typing import Any, Protocol

from voodoo.adapters.capabilities import ObjectStoreCapabilities

__all__ = [
    "ObjectStoreCapabilities",
    "VoodooObjectStore",
    "validate_chunk_size",
    "validate_content_type",
    "validate_object_key",
    "validate_object_prefix",
]


def validate_chunk_size(chunk_size: int) -> int:
    """Validate the bounded object-read contract shared by every adapter."""
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
        raise TypeError("chunk_size must be an integer")
    if chunk_size <= 0 or chunk_size > 8 * 1024 * 1024:
        raise ValueError("chunk_size must be between 1 and 8388608 bytes")
    return chunk_size


def validate_content_type(content_type: str) -> str:
    """Validate MIME metadata before it reaches a provider or response."""
    if (
        not isinstance(content_type, str)
        or not content_type.strip()
        or len(content_type) > 255
        or "\r" in content_type
        or "\n" in content_type
        or "/" not in content_type
    ):
        raise ValueError("content_type must be a valid MIME type")
    return content_type


def validate_object_key(key: str) -> str:
    """Validate a public object key consistently across storage adapters."""
    if not isinstance(key, str):
        raise TypeError("object key must be a string")
    if "\\" in key:
        raise ValueError("object key must not contain backslashes")
    normalized = key
    if not normalized or normalized.startswith("/") or "\x00" in normalized:
        raise ValueError("object key must be relative, non-empty, and NUL-free")
    if any(unicodedata.category(char) in {"Cc", "Cf"} for char in normalized):
        raise ValueError("object key must not contain control or format characters")
    if any(segment in {"", ".", ".."} for segment in normalized.split("/")):
        raise ValueError("object key must not contain empty, dot, or traversal segments")
    return normalized


def validate_object_prefix(prefix: str) -> str:
    """Validate a literal object-list prefix without allowing path escapes."""
    if not isinstance(prefix, str):
        raise TypeError("object prefix must be a string")
    if "\\" in prefix:
        raise ValueError("object prefix must not contain backslashes")
    normalized = prefix
    if not normalized:
        return ""
    if normalized.startswith("/") or "\x00" in normalized:
        raise ValueError("object prefix must be relative and NUL-free")
    if any(unicodedata.category(char) in {"Cc", "Cf"} for char in normalized):
        raise ValueError("object prefix must not contain control or format characters")
    segments = normalized.split("/")
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("object prefix must not contain dot or traversal segments")
    if any(segment == "" for segment in segments[:-1]):
        raise ValueError("object prefix must not contain empty segments")
    return normalized


class VoodooObjectStore(Protocol):
    """Backend-neutral object storage capability.

    Every implementation provides put/get/delete/exists/stat/list plus
    capability declarations. Optional presign/url support is declared.
    """

    provider: str

    def capabilities(self) -> ObjectStoreCapabilities: ...

    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str: ...

    def get(self, key: str) -> bytes: ...

    def iter_chunks(self, key: str, chunk_size: int = 65_536) -> Iterator[bytes]: ...

    def delete(self, key: str) -> bool: ...

    def exists(self, key: str) -> bool: ...

    def stat(self, key: str) -> dict[str, Any]: ...

    def list(self, prefix: str = "") -> list[str]: ...

    def presign(self, key: str, expires_in: int = 3600) -> str: ...
