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
import logging
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast

try:
    import boto3  # type: ignore[import-untyped]
    import botocore.config  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised when boto3 is absent
    boto3 = None

from voodoo.observability import store_operation
from voodoo.security.redaction import redact_string
from voodoo.storage.objects.interfaces import (
    ObjectStoreCapabilities,
    validate_chunk_size,
    validate_content_type,
    validate_object_key,
    validate_object_prefix,
)

#: Uploads at or above this size use multipart upload (8 MiB, the S3 default).
MULTIPART_THRESHOLD = 8 * 1024 * 1024

#: Per-part size for multipart uploads (8 MiB — matches the threshold).
MULTIPART_PART_SIZE = 8 * 1024 * 1024
MAX_PRESIGN_SECONDS = 7 * 24 * 60 * 60

logger = logging.getLogger(__name__)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _verify_checksum(digest: str, expected: Any) -> None:
    """Reject provider bytes when our upload metadata reports a mismatch."""
    if expected is not None and str(expected).lower() != digest:
        raise ValueError("object content checksum mismatch")


def _validated_checksum(value: Any) -> str | None:
    """Validate optional provider checksum metadata before exposing it."""
    if value is None:
        return None
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value.lower()) is None:
        raise ValueError("object metadata checksum must be a SHA-256 hex digest")
    return value.lower()


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
        endpoint = self.endpoint or ""
        return "amazonaws.com" in endpoint

    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Store an object and return its SHA-256 checksum.

        Uploads at or above ``multipart_threshold`` are uploaded with
        multipart upload for large-object robustness.
        """
        key = validate_object_key(key)
        content_type = validate_content_type(content_type)
        with store_operation("object.put", provider=self.provider) as details:
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
            details["bytes"] = len(data)
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
            try:
                client.abort_multipart_upload(
                    Bucket=self.bucket, Key=full_key, UploadId=upload_id
                )
            except Exception as abort_error:
                # Cleanup is best-effort; never mask the initiating upload
                # failure with a secondary provider error.
                logger.warning(
                    "s3 multipart cleanup failed key=%s error=%s",
                    redact_string(key),
                    redact_string(str(abort_error)),
                )
            raise

    def get(self, key: str) -> bytes:
        key = validate_object_key(key)
        with store_operation("object.get", provider=self.provider) as details:
            client = self._require_client()
            try:
                response = client.get_object(Bucket=self.bucket, Key=self._full_key(key))
            except Exception as error:
                if self._is_missing_error(error):
                    raise KeyError(f"object {key!r} not found") from error
                logger.warning(
                    "s3 object read failed key=%s error=%s",
                    redact_string(key),
                    redact_string(str(error)),
                )
                raise
            body = response["Body"]
            try:
                data = cast(bytes, body.read())
                _verify_checksum(
                    hashlib.sha256(data).hexdigest(),
                    response.get("Metadata", {}).get("sha256"),
                )
                details["bytes"] = len(data)
                return data
            finally:
                close = getattr(body, "close", None)
                if close is not None:
                    close()

    def iter_chunks(self, key: str, chunk_size: int = 65_536) -> Iterator[bytes]:
        """Yield bounded chunks directly from the provider response body."""
        with store_operation("object.get", provider=self.provider) as details:
            validate_chunk_size(chunk_size)
            key = validate_object_key(key)
            client = self._require_client()
            try:
                response = client.get_object(Bucket=self.bucket, Key=self._full_key(key))
            except Exception as error:
                if self._is_missing_error(error):
                    raise KeyError(f"object {key!r} not found") from error
                logger.warning(
                    "s3 object chunk read failed key=%s error=%s",
                    redact_string(key),
                    redact_string(str(error)),
                )
                raise
            body = response["Body"]
            digest = hashlib.sha256()
            try:
                if hasattr(body, "iter_chunks"):
                    for chunk in body.iter_chunks(chunk_size=chunk_size):
                        digest.update(chunk)
                        details["bytes"] = details.get("bytes", 0) + len(chunk)
                        yield chunk
                    _verify_checksum(
                        digest.hexdigest(), response.get("Metadata", {}).get("sha256")
                    )
                    return
                while chunk := body.read(chunk_size):
                    digest.update(chunk)
                    details["bytes"] = details.get("bytes", 0) + len(chunk)
                    yield chunk
                _verify_checksum(
                    digest.hexdigest(), response.get("Metadata", {}).get("sha256")
                )
            finally:
                close = getattr(body, "close", None)
                if close is not None:
                    close()

    def delete(self, key: str) -> bool:
        key = validate_object_key(key)
        client = self._require_client()
        if not self.exists(key):
            return False
        client.delete_object(Bucket=self.bucket, Key=self._full_key(key))
        return True

    def exists(self, key: str) -> bool:
        key = validate_object_key(key)
        client = self._require_client()
        try:
            client.head_object(Bucket=self.bucket, Key=self._full_key(key))
            return True
        except Exception as error:
            # A missing object is a normal negative result, but authentication,
            # throttling, networking, and provider outages must not be
            # misreported as absence.  boto3 exposes the provider code on
            # ``ClientError.response``; keeping this structural avoids a hard
            # runtime dependency on botocore in optional-install environments.
            if self._is_missing_error(error):
                return False
            logger.warning(
                "s3 object existence check failed key=%s error=%s",
                redact_string(key),
                redact_string(str(error)),
            )
            raise

    def stat(self, key: str) -> dict[str, Any]:
        key = validate_object_key(key)
        client = self._require_client()
        try:
            head = client.head_object(Bucket=self.bucket, Key=self._full_key(key))
        except Exception as error:
            if self._is_missing_error(error):
                raise KeyError(f"object {key!r} not found") from error
            logger.warning(
                "s3 object stat failed key=%s error=%s",
                redact_string(key),
                redact_string(str(error)),
            )
            raise
        size = head.get("ContentLength", 0)
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("object metadata size must be a non-negative integer")
        provider_metadata = head.get("Metadata") or {}
        if not isinstance(provider_metadata, dict):
            raise ValueError("object metadata must be a mapping")
        return {
            "key": key,
            "size": size,
            "content_type": head.get("ContentType", "application/octet-stream"),
            "checksum": _validated_checksum(provider_metadata.get("sha256")),
            "created_at": head.get("LastModified", datetime.now(UTC)).isoformat(),
        }

    def list(self, prefix: str = "") -> list[str]:
        prefix = validate_object_prefix(prefix)
        client = self._require_client()
        response = client.list_objects_v2(
            Bucket=self.bucket, Prefix=self._full_key(prefix)
        )
        objects = response.get("Contents", [])
        base = len(self.root_prefix)
        return [obj["Key"][base:] for obj in objects]

    @staticmethod
    def _is_missing_error(error: Exception) -> bool:
        """Return whether an optional S3 provider explicitly reported absence."""
        response = getattr(error, "response", None)
        if not isinstance(response, dict):
            return False
        provider_error = response.get("Error")
        if not isinstance(provider_error, dict):
            return False
        return str(provider_error.get("Code")) in {"404", "NoSuchKey", "NotFound"}

    def presign(self, key: str, expires_in: int = 3600) -> str:
        key = validate_object_key(key)
        client = self._require_client()
        expires_in = self._validate_presign_expiry(expires_in)
        return cast(str, client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(key)},
            ExpiresIn=expires_in,
        ))

    def presign_put(self, key: str, expires_in: int = 3600) -> str:
        """Return a presigned URL that permits a PUT to this object."""
        key = validate_object_key(key)
        client = self._require_client()
        expires_in = self._validate_presign_expiry(expires_in)
        return cast(str, client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": self._full_key(key)},
            ExpiresIn=expires_in,
        ))

    @staticmethod
    def _validate_presign_expiry(expires_in: int) -> int:
        """Bound presigned URL lifetime to a positive seven-day maximum."""
        if isinstance(expires_in, bool) or not isinstance(expires_in, int):
            raise TypeError("presigned URL expiry must be an integer number of seconds")
        if not 1 <= expires_in <= MAX_PRESIGN_SECONDS:
            raise ValueError(
                f"presigned URL expiry must be between 1 and {MAX_PRESIGN_SECONDS} seconds"
            )
        return expires_in

    def url(self, key: str) -> str:
        """Return a plain (non-presigned) URL for the object."""
        key = validate_object_key(key)
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
