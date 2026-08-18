"""S3-compatible object store (Sprint 6).

``S3ObjectStore`` implements the ``VoodooObjectStore`` capability over any
S3-compatible endpoint (AWS S3, MinIO, R2, …). It extracts the S3 logic that
previously lived inside ``StorageManager``, keeping that class a thin facade.

boto3 is an optional dependency — when it is missing or the S3 env vars are
not set, ``use_s3`` is ``False`` and the store refuses to operate, so
callers can fall back to ``LocalObjectStore`` without importing boto3.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Any

try:
    import boto3
    import botocore.config
except ImportError:  # pragma: no cover - exercised when boto3 is absent
    boto3 = None

from voodoo.storage.objects.interfaces import ObjectStoreCapabilities


class S3ObjectStore:
    """S3-backed object storage with key-based access.

    Keys are the full object key in the bucket. ``root_prefix`` (optional)
    is prepended to every key, mirroring the old ``bucket/path`` scheme.
    """

    provider = "s3"

    def __init__(
        self,
        *,
        bucket: str | None = None,
        endpoint: str | None = None,
        key: str | None = None,
        secret: str | None = None,
        root_prefix: str = "",
    ) -> None:
        self.bucket = bucket or os.getenv("VOODOO_S3_BUCKET")
        self.endpoint = endpoint or os.getenv("VOODOO_S3_ENDPOINT")
        self.key = key or os.getenv("VOODOO_S3_KEY")
        self.secret = secret or os.getenv("VOODOO_S3_SECRET")
        self.root_prefix = root_prefix

        self.use_s3 = all([self.bucket, self.key, self.secret, self.endpoint])

        if self.use_s3 and boto3:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.key,
                aws_secret_access_key=self.secret,
                endpoint_url=self.endpoint,
                config=botocore.config.Config(signature_version="s3v4"),
            )
        else:
            self.s3_client = None

    def capabilities(self) -> ObjectStoreCapabilities:
        return ObjectStoreCapabilities(
            provider=self.provider,
            presign_urls=True,
            checksums=True,
            metadata=True,
            multipart=False,
        )

    def _full_key(self, key: str) -> str:
        return f"{self.root_prefix}{key}" if self.root_prefix else key

    def _require_client(self) -> Any:
        if not self.use_s3 or self.s3_client is None:
            raise RuntimeError(
                "S3ObjectStore is not configured (set VOODOO_S3_BUCKET, "
                "VOODOO_S3_KEY, VOODOO_S3_SECRET, VOODOO_S3_ENDPOINT)"
            )
        return self.s3_client

    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Store an object and return its SHA-256 checksum."""
        client = self._require_client()
        checksum = hashlib.sha256(data).hexdigest()
        client.put_object(
            Bucket=self.bucket,
            Key=self._full_key(key),
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": checksum, "content_type": content_type},
        )
        return checksum

    def get(self, key: str) -> bytes:
        client = self._require_client()
        response = client.get_object(Bucket=self.bucket, Key=self._full_key(key))
        return response["Body"].read()

    def delete(self, key: str) -> bool:
        client = self._require_client()
        if not self.exists(key):
            return False
        client.delete_object(Bucket=self.bucket, Key=self._full_key(key))
        return True

    def exists(self, key: str) -> bool:
        client = self._require_client()
        try:
            client.head_object(Bucket=self.bucket, Key=self._full_key(key))
            return True
        except Exception:  # noqa: BLE001 - 404 surfaces as ClientError
            return False

    def stat(self, key: str) -> dict[str, Any]:
        client = self._require_client()
        try:
            head = client.head_object(Bucket=self.bucket, Key=self._full_key(key))
        except Exception as e:  # noqa: BLE001
            raise KeyError(f"object {key!r} not found") from e
        return {
            "key": key,
            "size": head.get("ContentLength", 0),
            "content_type": head.get("ContentType", "application/octet-stream"),
            "checksum": (
                head.get("Metadata", {}).get("sha256") if head.get("Metadata") else None
            ),
            "created_at": head.get("LastModified", datetime.now(UTC)).isoformat(),
        }

    def list(self, prefix: str = "") -> list[str]:
        client = self._require_client()
        response = client.list_objects_v2(
            Bucket=self.bucket, Prefix=self._full_key(prefix)
        )
        objects = response.get("Contents", [])
        base = len(self.root_prefix)
        return [obj["Key"][base:] for obj in objects]

    def presign(self, key: str, expires_in: int = 3600) -> str:
        client = self._require_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(key)},
            ExpiresIn=expires_in,
        )

    def url(self, key: str) -> str:
        """Return a plain (non-presigned) URL for the object."""
        if self.endpoint and "amazonaws.com" in self.endpoint:
            return f"https://{self.bucket}.s3.amazonaws.com/{self._full_key(key)}"
        return f"{self.endpoint}/{self.bucket}/{self._full_key(key)}"
