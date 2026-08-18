"""Sprint 6 — Object store & artifacts tests."""

from __future__ import annotations

import hashlib

from voodoo.storage.objects import LocalObjectStore


class TestLocalObjectStore:
    def test_put_get_roundtrip(self, tmp_path):
        store = LocalObjectStore(tmp_path / "objects")
        data = b"hello world"
        checksum = store.put("greeting.txt", data, "text/plain")
        assert checksum == hashlib.sha256(data).hexdigest()
        assert store.get("greeting.txt") == data
        store.close()

    def test_put_replace_updates(self, tmp_path):
        store = LocalObjectStore(tmp_path / "objects")
        store.put("key", b"v1")
        store.put("key", b"v2")
        assert store.get("key") == b"v2"
        store.close()

    def test_delete(self, tmp_path):
        store = LocalObjectStore(tmp_path / "objects")
        store.put("key", b"data")
        assert store.delete("key")
        assert not store.exists("key")
        assert not store.delete("key")
        store.close()

    def test_stat(self, tmp_path):
        store = LocalObjectStore(tmp_path / "objects")
        store.put("file.bin", b"12345", "application/octet-stream")
        stat = store.stat("file.bin")
        assert stat["size"] == 5
        assert stat["content_type"] == "application/octet-stream"
        store.close()

    def test_list_by_prefix(self, tmp_path):
        store = LocalObjectStore(tmp_path / "objects")
        store.put("reports/2024.pdf", b"%PDF")
        store.put("reports/2025.pdf", b"%PDF")
        store.put("images/logo.png", b"PNG")
        assert len(store.list("reports/")) == 2
        assert len(store.list("images/")) == 1
        store.close()

    def test_missing_key_raises(self, tmp_path):
        store = LocalObjectStore(tmp_path / "objects")
        try:
            store.get("nope")
            raise AssertionError("should have raised KeyError")
        except KeyError:
            pass
        store.close()

    def test_data_survives_reopen(self, tmp_path):
        path = tmp_path / "objects"
        store = LocalObjectStore(path)
        store.put("durable", b"persist")
        store.close()

        reopened = LocalObjectStore(path)
        assert reopened.get("durable") == b"persist"
        reopened.close()

    def test_capabilities(self, tmp_path):
        store = LocalObjectStore(tmp_path / "objects")
        caps = store.capabilities()
        assert caps.provider == "local"
        assert caps.checksums is True
        assert caps.presign_urls is False
        store.close()


class TestExecutionArtifact:
    def test_artifact_metadata(self):
        from voodoo.primitives.intent import Intent
        from voodoo.runtime.execution import Execution

        ex = Execution(
            id="ex1", trace_id="t1", intent=Intent(name="art"), actor="alice"
        )
        artifact = ex.artifact("abc123def", tool="report_generator", model="gpt-4")
        assert artifact["execution_id"] == "ex1"
        assert artifact["created_by"] == "alice"
        assert artifact["tool"] == "report_generator"
        assert artifact["model"] == "gpt-4"
        assert artifact["checksum"] == "abc123def"
