import asyncio
import os
from collections.abc import Iterator
from typing import cast
from urllib.parse import quote

import aiofiles  # type: ignore[import-untyped]

from voodoo.adapters.registry import registry
from voodoo.config import get_config
from voodoo.storage.objects.interfaces import validate_chunk_size
from voodoo.storage.objects.s3 import S3ObjectStore


def _safe_object_key(bucket: str, path: str) -> str:
    """Return a provider key while rejecting filesystem/path traversal input."""
    if not isinstance(bucket, str) or not isinstance(path, str):
        raise TypeError("object bucket and path must be strings")
    combined = f"{bucket}/{path}"
    if "\\" in combined:
        raise ValueError("object path must not contain backslashes")
    if not combined or combined.startswith("/") or "\x00" in combined:
        raise ValueError("object path must be relative and non-empty")
    segments = combined.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("object path must not contain empty, dot, or traversal segments")
    return "/".join(segments)


class StorageManager:
    """Thin facade over the active storage adapter (Sprint 6, Sprint 9, Sprint 28).

    The configured object adapter owns persistence. S3 keeps its existing remote
    URL behavior, local storage keeps the ``/storage/...`` route, and the Voodoo
    Store provider persists object bytes in the application-owned Runtime Store.
    """

    def __init__(self) -> None:
        cfg = get_config().objects
        self.max_upload_bytes = cfg.max_upload_bytes
        self._store = registry.get_objects(cfg)
        self._s3 = (
            self._store if isinstance(self._store, S3ObjectStore) else S3ObjectStore()
        )
        self.s3_bucket = self._s3.bucket
        self.key = self._s3.key
        self.secret = self._s3.secret
        self.endpoint = self._s3.endpoint
        self.use_s3 = isinstance(self._store, S3ObjectStore) and self._s3.use_s3
        self.use_voodoo = getattr(self._store, "provider", "") == "voodoo"
        self.s3_client = self._s3.s3_client

    @property
    def base_dir(self) -> str:
        try:
            return os.path.join(os.getcwd(), os.getenv("VOODOO_STORAGE_DIR", "storage"))
        except FileNotFoundError:
            return os.path.join(".", os.getenv("VOODOO_STORAGE_DIR", "storage"))

    def _get_local_path(self, bucket: str, path: str) -> str:
        """Helper to resolve the local file path for a specific bucket."""
        key = _safe_object_key(bucket, path)
        return os.path.join(self.base_dir, *key.split("/"))

    async def upload(
        self,
        file_content: bytes | str,
        path: str,
        bucket: str = "public",
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to the configured object provider.

        ``content_type`` is persisted by metadata-capable providers and is
        validated before any provider I/O to prevent malformed header values.
        """
        if isinstance(file_content, str):
            file_content = file_content.encode("utf-8")
        if not isinstance(file_content, bytes):
            raise TypeError("file_content must be bytes or str")
        if (
            not isinstance(content_type, str)
            or not content_type.strip()
            or len(content_type) > 255
            or "\r" in content_type
            or "\n" in content_type
            or "/" not in content_type
        ):
            raise ValueError("content_type must be a valid MIME type")
        if len(file_content) > self.max_upload_bytes:
            raise ValueError(
                "object upload exceeds configured max_upload_bytes "
                f"({self.max_upload_bytes})"
            )

        object_key = _safe_object_key(bucket, path)
        if self.use_s3 and self.s3_client:
            await asyncio.to_thread(
                self._s3.put, object_key, file_content, content_type
            )
            return self.url(path, bucket)
        if self.use_voodoo:
            await asyncio.to_thread(
                self._store.put,
                object_key,
                file_content,
                content_type,
            )
            return self.url(path, bucket)

        local_path = self._get_local_path(bucket, path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        async with aiofiles.open(local_path, "wb") as f:
            await f.write(file_content)
        return self.url(path, bucket)

    async def delete(self, path: str, bucket: str = "public") -> bool:
        """Delete a file from the configured object provider."""
        object_key = _safe_object_key(bucket, path)
        if self.use_s3 and self.s3_client:
            await asyncio.to_thread(self._s3.delete, object_key)
            return True
        if self.use_voodoo:
            return bool(await asyncio.to_thread(self._store.delete, object_key))

        local_path = self._get_local_path(bucket, path)
        if os.path.exists(local_path):
            os.remove(local_path)
            return True
        return False

    def iter_chunks(
        self, path: str, bucket: str = "public", chunk_size: int = 65_536
    ) -> Iterator[bytes]:
        """Stream an object through the configured provider in bounded chunks."""
        validate_chunk_size(chunk_size)
        object_key = _safe_object_key(bucket, path)
        if self.use_s3 or self.use_voodoo:
            yield from self._store.iter_chunks(object_key, chunk_size)
            return

        local_path = self._get_local_path(bucket, path)
        try:
            handle = open(local_path, "rb")
        except FileNotFoundError as error:
            raise KeyError(f"object {object_key!r} not found") from error
        with handle:
            while chunk := handle.read(chunk_size):
                yield chunk

    def url(self, path: str, bucket: str = "public") -> str:
        """Return the provider-specific reference for a stored object."""
        object_key = _safe_object_key(bucket, path)
        if self.use_s3 and self.s3_client:
            return self._s3.url(object_key)
        if self.use_voodoo:
            return cast(str, self._store.presign(object_key))
        return f"/storage/{quote(object_key, safe='/')}"


storage = StorageManager()
