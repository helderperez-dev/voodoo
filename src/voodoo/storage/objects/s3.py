"""S3-compatible object store (Sprint 6, hardened in Sprint 12).

``S3ObjectStore`` implements the ``VoodooObjectStore`` capability over any
S3-compatible endpoint (AWS S3, MinIO, R2, …). It extracts the S3 logic that
previously lived inside ``StorageManager``, keeping that class a thin facade.

Sprint 12 hardening adds:

- Presigned **PUT** URLs (alongside GET) via ``presign_put``.
- Multipart uploads above a size threshold (default 8 MiB) with
  ``create_multipart_upload`` / ``upload_part`` / ``complete_multipart_upload``.
- R2 / MinIO path-style addressing when the endpoint is not AWS.
- ``region`` handling and a ``close()`` lifecycle hook.

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

#: Uploads at or above this size use multipart upload (8 MiB, the S3 default).
MULTIPART_THRESHOLD = 8 * 1024 * 1024

#: Per-part size for multipart uploads (8 MiB — matches the threshold).
MULTIPART_PART_SIZE = 8 * 1024 * 1024


class S3ObjectStore:
    """S3-backed object storage with key-based access.

    Keys are the full object key in the bucket. ``root_prefix`` (optional)
    is prepended to every key, mirroring the old ``bucket/path`` scheme.

    Constructor accepts explicit values and falls back to environment
    variables (``VOODOO_S3_BUCKET``, ``VOODOO_S3_ENDPOINT``,
    ``VOODOO_S3_KEY``, ``VOODOO_S3_SECRET``, ``AWS_REGION`` /
    ``AWS_DEFAULT_REGION``).
    """

    provider = "s3"

    def __init__(
        self,
        *,
        bucket: str | None = None,
        endpoint: str | None = None,
        key: str | None = None,
        secret: str | None = None,
        region: str | None = None,
        root_prefix: str = "",
        multipart_threshold: int = MULTIPART_THRESHOLD,
    ) -> None:
        self.bucket = bucket or os.getenv("VOODOO_S3_BUCKET")
        self.endpoint = endpoint or os.getenv("VOODOO_S3_ENDPOINT")
        self.key = key or os.getenv("VOODOO_S3_KEY")
        self.secret = secret or os.getenv("VOODOO_S3_SECRET")
        self.region = (
            region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        )
        self.root_prefix = root_prefix
        self.multipart_threshold = multipart_threshold

        self.use_s3 = all([self.bucket, self.key, self.secret, self.endpoint])

        if self.use_s3 and boto3:
            client_kwargs: dict[str, Any] = {
                "aws_access_key_id": self.key,
                "aws_secret_access_key": self.secret,
                "endpoint_url": self.endpoint,
                "config": botocore.config.Config(signature_version="s3v4"),
            }
            if self.region:
                client_kwargs["region_name"] = self.region
            self.s3_client = boto3.client("s3", **client_kwargs)
        else:
            self.s3_client = None

    def capabilities(self) -> ObjectStoreCapabilities:
        return ObjectStoreCapabilities(
            provider=self.provider,
            presign_urls=True,
            checksums=True,
            metadata=True,
            multipart=self.use_s3,
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

    def _is_aws(self) -> bool:
        """True when the endpoint is real AWS S3 (virtual-hosted style)."""
        return bool(self.endpoint) and "amazonaws.com" in self.endpoint

    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Store an object and return its SHA-256 checksum.

        Uploads at or above ``multipart_threshold`` are uploaded with
        multipart upload for large-object robustness.
        """
        client = self._require_client()
        checksum = hashlib.sha256(data).hexdigest()
        metadata = {"sha256": checksum, "content_type": content_type}

        if len(data) >= self.multipart_threshold:
            self._multipart_upload(
                client, key, data, content_type=content_type, metadata=metadata
            )
        else:
            client.put_object(
                Bucket=self.bucket,
                Key=self._full_key(key),
                Body=data,
                ContentType=content_type,
                Metadata=metadata,
            )
        return checksum

    def _multipart_upload(
        self,
        client: Any,
        key: str,
        data: bytes,
        *,
        content_type: str,
        metadata: dict[str, str],
    ) -> None:
        """Upload ``data`` via S3 multipart upload in fixed-size parts."""
        full_key = self._full_key(key)
        response = client.create_multipart_upload(
            Bucket=self.bucket,
            Key=full_key,
            ContentType=content_type,
            Metadata=metadata,
        )
        upload_id = response["UploadId"]
        parts: list[dict[str, Any]] = []
        try:
            part_number = 1
            offset = 0
            while offset < len(data):
                chunk = data[offset : offset + MULTIPART_PART_SIZE]
                part = client.upload_part(
                    Bucket=self.bucket,
                    Key=full_key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk,
                )
                parts.append(
                    {
                        "PartNumber": part_number,
                        "ETag": part["ETag"],
                    }
                )
                part_number += 1
                offset += MULTIPART_PART_SIZE
            client.complete_multipart_upload(
                Bucket=self.bucket,
                Key=full_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception:
            client.abort_multipart_upload(
                Bucket=self.bucket, Key=full_key, UploadId=upload_id
            )
            raise

    def get(self, key: str) -> bytes:
        client = self._require_client()
        try:
            response = client.get_object(Bucket=self.bucket, Key=self._full_key(key))
        except Exception as e:  # noqa: BLE001 - 404 surfaces as ClientError
            raise KeyError(f"object {key!r} not found") from e
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

    def presign_put(self, key: str, expires_in: int = 3600) -> str:
        """Return a presigned URL that permits a PUT to this object."""
        client = self._require_client()
        return client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(key)},
            ExpiresIn=expires_in,
        )

    def url(self, key: str) -> str:
        """Return a plain (non-presigned) URL for the object."""
        full_key = self._full_key(key)
        if self._is_aws():
            return f"https://{self.bucket}.s3.amazonaws.com/{full_key}"
        # Path-style addressing (MinIO, R2, other S3-compatible endpoints).
        return f"{self.endpoint}/{self.bucket}/{full_key}"

    def close(self) -> None:
        """Release the boto3 client's underlying connection pool."""
        if self.s3_client is not None:
            self.s3_client.close()
            self.s3_client = None
