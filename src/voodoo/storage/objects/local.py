"""Local object store (Sprint 6).

Objects live under ``.voodoo/objects/`` with sharded paths (first two
chars of the content hash) plus a metadata table for size, content type,
and checksum.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from voodoo.observability import store_operation
from voodoo.storage.objects.interfaces import (
    ObjectStoreCapabilities,
    validate_chunk_size,
    validate_content_type,
    validate_object_key,
    validate_object_prefix,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class LocalObjectStore:
    """Embedded object store — default backend (zero infrastructure)."""

    provider = "local"

    def __init__(self, root: str | Path = ".voodoo/objects") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db_path = self.root / "metadata.db"
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self._db_path), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS objects (
                key TEXT PRIMARY KEY,
                size INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                checksum TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def capabilities(self) -> ObjectStoreCapabilities:
        return ObjectStoreCapabilities(
            provider=self.provider,
            presign_urls=False,  # local files have no presigning
            checksums=True,
            metadata=True,
            multipart=False,
        )

    def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Store an object and return its checksum."""
        key = validate_object_key(key)
        content_type = validate_content_type(content_type)
        with store_operation("object.put", provider=self.provider) as details:
            checksum = hashlib.sha256(data).hexdigest()
            shard = checksum[:2]
            obj_dir = self.root / shard
            obj_dir.mkdir(parents=True, exist_ok=True)
            obj_path = obj_dir / checksum
            obj_path.write_bytes(data)

            self._conn.execute(
                """
                INSERT OR REPLACE INTO objects (key, size, content_type, checksum, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, len(data), content_type, checksum, datetime.now(UTC).isoformat()),
            )
            self._conn.commit()
            details["bytes"] = len(data)
            return checksum

    def get(self, key: str) -> bytes:
        """Retrieve an object by key."""
        key = validate_object_key(key)
        with store_operation("object.get", provider=self.provider) as details:
            row = self._conn.execute(
                "SELECT checksum FROM objects WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                raise KeyError(f"object {key!r} not found")
            checksum = cast(str, row["checksum"])
            obj_path = self.root / checksum[:2] / checksum
            data = obj_path.read_bytes()
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError("object content checksum mismatch")
            details["bytes"] = len(data)
            return data

    def iter_chunks(self, key: str, chunk_size: int = 65_536) -> Iterator[bytes]:
        """Read a local object incrementally from its content-addressed file."""
        with store_operation("object.get", provider=self.provider) as details:
            validate_chunk_size(chunk_size)
            key = validate_object_key(key)
            row = self._conn.execute(
                "SELECT checksum FROM objects WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                raise KeyError(f"object {key!r} not found")
            checksum = cast(str, row["checksum"])
            obj_path = self.root / checksum[:2] / checksum
            digest = hashlib.sha256()
            with obj_path.open("rb") as handle:
                while chunk := handle.read(chunk_size):
                    digest.update(chunk)
                    details["bytes"] = details.get("bytes", 0) + len(chunk)
                    yield chunk
            if digest.hexdigest() != checksum:
                raise ValueError("object content checksum mismatch")

    def delete(self, key: str) -> bool:
        """Delete an object. Returns True if it existed."""
        key = validate_object_key(key)
        with store_operation("object.delete", provider=self.provider):
            row = self._conn.execute(
                "SELECT checksum FROM objects WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return False
            checksum = cast(str, row["checksum"])
            obj_path = self.root / checksum[:2] / checksum
            if obj_path.exists():
                obj_path.unlink()
            self._conn.execute("DELETE FROM objects WHERE key = ?", (key,))
            self._conn.commit()
            return True

    def exists(self, key: str) -> bool:
        key = validate_object_key(key)
        row = self._conn.execute(
            "SELECT 1 FROM objects WHERE key = ?", (key,)
        ).fetchone()
        return row is not None

    def stat(self, key: str) -> dict[str, Any]:
        key = validate_object_key(key)
        row = self._conn.execute(
            "SELECT * FROM objects WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            raise KeyError(f"object {key!r} not found")
        metadata = dict(row)
        if metadata.get("key") != key:
            raise ValueError("object metadata key does not match the requested key")
        size = metadata.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("object metadata size must be a non-negative integer")
        checksum = metadata.get("checksum")
        if not isinstance(checksum, str) or _SHA256_RE.fullmatch(checksum) is None:
            raise ValueError("object metadata checksum must be a SHA-256 hex digest")
        if not isinstance(metadata.get("content_type"), str):
            raise ValueError("object metadata content_type must be a string")
        if not isinstance(metadata.get("created_at"), str):
            raise ValueError("object metadata created_at must be a string")
        return metadata

    def list(self, prefix: str = "") -> list[str]:
        prefix = validate_object_prefix(prefix)
        escaped = prefix.replace("%", "\\%").replace("_", "\\_")
        rows = self._conn.execute(
            "SELECT key FROM objects WHERE key LIKE ? ESCAPE '\\' ORDER BY key",
            (f"{escaped}%",),
        ).fetchall()
        return [row["key"] for row in rows]

    def presign(self, key: str, expires_in: int = 3600) -> str:
        """Local objects have no presigned URLs — return a file:// path."""
        key = validate_object_key(key)
        row = self._conn.execute(
            "SELECT checksum FROM objects WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            raise KeyError(f"object {key!r} not found")
        checksum = cast(str, row["checksum"])
        return str(self.root / checksum[:2] / checksum)

    def close(self) -> None:
        with store_operation("object.close", provider=self.provider):
            if self._conn is not None:
                self._conn.close()
                self._conn = None  # type: ignore[assignment]
