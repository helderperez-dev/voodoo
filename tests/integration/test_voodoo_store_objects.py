from __future__ import annotations

import hashlib

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
