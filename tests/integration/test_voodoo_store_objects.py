from __future__ import annotations

import hashlib
import json

import pytest

from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store
from voodoo.storage.objects.store import VoodooStoreObjectStore


def _start(tmp_path):
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "objects.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    return runtime, VoodooStoreObjectStore()


def test_native_store_object_adapter_contract_and_reopen(tmp_path):
    runtime, store = _start(tmp_path)
    try:
        checksum = store.put("reports/2026.txt", b"version-1", "text/plain")
        assert checksum == hashlib.sha256(b"version-1").hexdigest()
        assert store.get("reports/2026.txt") == b"version-1"
        assert list(store.iter_chunks("reports/2026.txt", chunk_size=4)) == [
            b"vers",
            b"ion-",
            b"1",
        ]
        assert store.exists("reports/2026.txt") is True

        stat = store.stat("reports/2026.txt")
        assert stat["key"] == "reports/2026.txt"
        assert stat["size"] == len(b"version-1")
        assert stat["content_type"] == "text/plain"
        assert stat["checksum"] == checksum

        store.put("reports/2025.txt", b"older", "text/plain")
        store.put("images/logo.bin", b"logo")
        assert store.list("reports/") == [
            "reports/2025.txt",
            "reports/2026.txt",
        ]

        replacement = store.put("reports/2026.txt", b"version-2", "text/plain")
        assert replacement == hashlib.sha256(b"version-2").hexdigest()
        assert store.get("reports/2026.txt") == b"version-2"

        uri = store.presign("reports/2026.txt")
        assert uri == "voodoo://objects/reports/2026.txt"
    finally:
        store.close()
        bind_active_runtime_store(None)
        runtime.stop()

    reopened, reopened_store = _start(tmp_path)
    try:
        assert reopened_store.get("reports/2026.txt") == b"version-2"
        assert reopened_store.stat("reports/2026.txt")["checksum"] == replacement
        assert reopened_store.delete("reports/2026.txt") is True
        assert reopened_store.delete("reports/2026.txt") is False
        assert reopened_store.exists("reports/2026.txt") is False
        assert reopened_store.list("reports/") == ["reports/2025.txt"]
    finally:
        reopened_store.close()
        bind_active_runtime_store(None)
        reopened.stop()


def test_native_store_object_chunk_size_is_bounded(tmp_path):
    runtime, store = _start(tmp_path)
    try:
        store.put("bounded.bin", b"payload")
        with pytest.raises(ValueError, match="chunk_size"):
            list(store.iter_chunks("bounded.bin", chunk_size=0))
        with pytest.raises(ValueError, match="chunk_size"):
            list(store.iter_chunks("bounded.bin", chunk_size=8 * 1024 * 1024 + 1))
    finally:
        store.close()
        bind_active_runtime_store(None)
        runtime.stop()


def test_native_store_object_metadata_rejects_malformed_json():
    class FakeStore:
        def resolve_object_ref(self, namespace, name):
            del namespace, name
            return b"metadata-id"

        def get_object(self, object_id):
            assert object_id == b"metadata-id"
            return b"[\"not\", \"metadata\"]"

    store = VoodooStoreObjectStore()
    store._native = lambda: FakeStore()
    with pytest.raises(ValueError, match="JSON object"):
        store.stat("reports/corrupt.txt")


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (
            {
                "key": "reports/other.txt",
                "size": 1,
                "content_type": "text/plain",
                "checksum": "0" * 64,
                "created_at": "2026-10-09T00:00:00+00:00",
            },
            "key does not match",
        ),
        (
            {
                "key": "reports/corrupt.txt",
                "size": -1,
                "content_type": "text/plain",
                "checksum": "0" * 64,
                "created_at": "2026-10-09T00:00:00+00:00",
            },
            "non-negative",
        ),
        (
            {
                "key": "reports/corrupt.txt",
                "size": 1,
                "content_type": "text/plain",
                "checksum": "not-a-checksum",
                "created_at": "2026-10-09T00:00:00+00:00",
            },
            "SHA-256",
        ),
    ],
)
def test_native_store_object_metadata_rejects_integrity_mismatch(metadata, message):
    class FakeStore:
        def resolve_object_ref(self, namespace, name):
            del namespace, name
            return b"metadata-id"

        def get_object(self, object_id):
            assert object_id == b"metadata-id"
            return json.dumps(metadata).encode("utf-8")

    store = VoodooStoreObjectStore()
    store._native = lambda: FakeStore()
    with pytest.raises(ValueError, match=message):
        store.stat("reports/corrupt.txt")


def test_native_store_object_get_rejects_payload_checksum_mismatch():
    class FakeStore:
        def resolve_object_ref(self, namespace, name):
            del name
            return b"data-id" if namespace == b"runtime.objects.data" else b"meta-id"

        def get_object(self, object_id):
            if object_id == b"data-id":
                return b"tampered"
            return json.dumps(
                {
                    "key": "reports/item.txt",
                    "size": len(b"original"),
                    "content_type": "text/plain",
                    "checksum": hashlib.sha256(b"original").hexdigest(),
                    "created_at": "2026-10-09T00:00:00+00:00",
                }
            ).encode("utf-8")

    store = VoodooStoreObjectStore()
    store._native = lambda: FakeStore()
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.get("reports/item.txt")
