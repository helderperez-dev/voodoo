from __future__ import annotations

import hashlib

import pytest

from voodoo.storage.objects import LocalObjectStore


def _corrupt_payload(store: LocalObjectStore, key: str) -> None:
    row = store._conn.execute(  # noqa: SLF001 - corruption fixture is intentional
        "SELECT checksum FROM objects WHERE key = ?", (key,)
    ).fetchone()
    assert row is not None
    checksum = row["checksum"]
    (store.root / checksum[:2] / checksum).write_bytes(b"tampered")


def test_local_object_get_rejects_checksum_corruption(tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    try:
        payload = b"durable payload"
        assert store.put("reports/item.txt", payload) == hashlib.sha256(payload).hexdigest()
        _corrupt_payload(store, "reports/item.txt")
        with pytest.raises(ValueError, match="checksum mismatch"):
            store.get("reports/item.txt")
    finally:
        store.close()


def test_local_object_iter_chunks_rejects_checksum_corruption(tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    try:
        store.put("reports/item.txt", b"durable payload")
        _corrupt_payload(store, "reports/item.txt")
        with pytest.raises(ValueError, match="checksum mismatch"):
            list(store.iter_chunks("reports/item.txt", chunk_size=4))
    finally:
        store.close()


def test_local_object_stat_rejects_corrupt_metadata(tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    try:
        store.put("reports/item.txt", b"durable payload")
        store._conn.execute(  # noqa: SLF001 - corruption fixture is intentional
            "UPDATE objects SET checksum = ? WHERE key = ?",
            ("not-a-checksum", "reports/item.txt"),
        )
        store._conn.commit()
        with pytest.raises(ValueError, match="SHA-256"):
            store.stat("reports/item.txt")
    finally:
        store.close()


def test_local_object_list_treats_wildcards_as_literal_prefixes(tmp_path):
    store = LocalObjectStore(tmp_path / "objects")
    try:
        store.put("reports/%_literal.txt", b"literal")
        store.put("reports/other.txt", b"other")
        assert store.list("reports/%_") == ["reports/%_literal.txt"]
    finally:
        store.close()
