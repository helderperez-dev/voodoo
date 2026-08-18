"""Local object store (Sprint 6).

Objects live under ``.voodoo/objects/`` with sharded paths (first two
chars of the content hash) plus a metadata table for size, content type,
and checksum.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voodoo.storage.objects.interfaces import ObjectStoreCapabilities


class LocalObjectStore:
    """Embedded object store — default backend (zero infrastructure)."""

    provider = "local"

    def __init__(self, root: str | Path = ".voodoo/objects") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db_path = self.root / "metadata.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
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
        return checksum

    def get(self, key: str) -> bytes:
        """Retrieve an object by key."""
        row = self._conn.execute(
            "SELECT checksum FROM objects WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            raise KeyError(f"object {key!r} not found")
        checksum = row["checksum"]
        obj_path = self.root / checksum[:2] / checksum
        return obj_path.read_bytes()

    def delete(self, key: str) -> bool:
        """Delete an object. Returns True if it existed."""
        row = self._conn.execute(
            "SELECT checksum FROM objects WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return False
        checksum = row["checksum"]
        obj_path = self.root / checksum[:2] / checksum
        if obj_path.exists():
            obj_path.unlink()
        self._conn.execute("DELETE FROM objects WHERE key = ?", (key,))
        self._conn.commit()
        return True

    def exists(self, key: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM objects WHERE key = ?", (key,)
        ).fetchone()
        return row is not None

    def stat(self, key: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM objects WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            raise KeyError(f"object {key!r} not found")
        return dict(row)

    def list(self, prefix: str = "") -> list[str]:
        rows = self._conn.execute(
            "SELECT key FROM objects WHERE key LIKE ? ORDER BY key", (f"{prefix}%",)
        ).fetchall()
        return [row["key"] for row in rows]

    def presign(self, key: str, expires_in: int = 3600) -> str:
        """Local objects have no presigned URLs — return a file:// path."""
        row = self._conn.execute(
            "SELECT checksum FROM objects WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            raise KeyError(f"object {key!r} not found")
        checksum = row["checksum"]
        return str(self.root / checksum[:2] / checksum)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
