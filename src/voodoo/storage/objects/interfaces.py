"""Object store capability interface (Sprint 6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ObjectStoreCapabilities:
    """Declarative contract of what an object store guarantees."""

    provider: str
    presign_urls: bool = False
    checksums: bool = True
    metadata: bool = True
    multipart: bool = False


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

    def delete(self, key: str) -> bool: ...

    def exists(self, key: str) -> bool: ...

    def stat(self, key: str) -> dict[str, Any]: ...

    def list(self, prefix: str = "") -> list[str]: ...

    def presign(self, key: str, expires_in: int = 3600) -> str: ...
