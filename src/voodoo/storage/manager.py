import asyncio
import os

import aiofiles

from voodoo.adapters.registry import registry
from voodoo.config import get_config
from voodoo.storage.objects.s3 import S3ObjectStore


class StorageManager:
    """Thin facade over the active storage adapter (Sprint 6, Sprint 9, Sprint 28).

    The configured object adapter owns persistence. S3 keeps its existing remote
    URL behavior, local storage keeps the ``/storage/...`` route, and the Voodoo
    Store provider persists object bytes in the application-owned Runtime Store.
    """

    def __init__(self):
        cfg = get_config().objects
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
        return os.path.join(self.base_dir, bucket, path)

    async def upload(
        self, file_content: bytes | str, path: str, bucket: str = "public"
    ) -> str:
        """Upload a file to the configured object provider."""
        if isinstance(file_content, str):
            file_content = file_content.encode("utf-8")

        object_key = f"{bucket}/{path}"
        if self.use_s3 and self.s3_client:
            await asyncio.to_thread(
                self._s3.put, object_key, file_content, "application/octet-stream"
            )
            return self.url(path, bucket)
        if self.use_voodoo:
            await asyncio.to_thread(
                self._store.put,
                object_key,
                file_content,
                "application/octet-stream",
            )
            return self.url(path, bucket)

        local_path = self._get_local_path(bucket, path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        async with aiofiles.open(local_path, "wb") as f:
            await f.write(file_content)
        return self.url(path, bucket)

    async def delete(self, path: str, bucket: str = "public") -> bool:
        """Delete a file from the configured object provider."""
        object_key = f"{bucket}/{path}"
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

    def url(self, path: str, bucket: str = "public") -> str:
        """Return the provider-specific reference for a stored object."""
        object_key = f"{bucket}/{path}"
        if self.use_s3 and self.s3_client:
            return self._s3.url(object_key)
        if self.use_voodoo:
            return self._store.presign(object_key)
        return f"/storage/{bucket}/{path}"


storage = StorageManager()
