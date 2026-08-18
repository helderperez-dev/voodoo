import asyncio
import os

import aiofiles

from voodoo.adapters.registry import registry
from voodoo.config import get_config
from voodoo.storage.objects.s3 import S3ObjectStore


class StorageManager:
    """Thin facade over the active storage adapter (Sprint 6, Sprint 9).

    When S3 is configured, upload/delete/url delegate to
    :class:`~voodoo.storage.objects.S3ObjectStore`; otherwise a local
    filesystem backend under ``base_dir`` is used. The public surface
    (``upload`` / ``delete`` / ``url`` / ``base_dir`` / ``use_s3`` /
    ``s3_client``) is preserved so ``status.py`` and downstream callers
    are unchanged.
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
        """Uploads a file to a specific bucket and returns its path/url"""
        if isinstance(file_content, str):
            file_content = file_content.encode("utf-8")

        if self.use_s3 and self.s3_client:
            s3_key = f"{bucket}/{path}"
            await asyncio.to_thread(
                self._s3.put, s3_key, file_content, "application/octet-stream"
            )
            return self.url(path, bucket)
        else:
            local_path = self._get_local_path(bucket, path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            async with aiofiles.open(local_path, "wb") as f:
                await f.write(file_content)
            return self.url(path, bucket)

    async def delete(self, path: str, bucket: str = "public") -> bool:
        """Deletes a file from a specific bucket"""
        if self.use_s3 and self.s3_client:
            await asyncio.to_thread(self._s3.delete, f"{bucket}/{path}")
            return True
        else:
            local_path = self._get_local_path(bucket, path)
            if os.path.exists(local_path):
                os.remove(local_path)
                return True
            return False

    def url(self, path: str, bucket: str = "public") -> str:
        """Returns the URL for a file in a specific bucket"""
        if self.use_s3 and self.s3_client:
            return self._s3.url(f"{bucket}/{path}")
        else:
            return f"/storage/{bucket}/{path}"


storage = StorageManager()
