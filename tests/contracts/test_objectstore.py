"""Object store adapter contract tests (Sprint 6, spec §18).

``ObjectStoreContractTests`` is the portability suite every
``VoodooObjectStore`` implementation must pass unchanged — ``LocalObjectStore``
today, ``S3ObjectStore`` in the same sprint. Provider-specific behavior
(ctor validation, S3 client wiring, sharding) gets its own tests on top.
"""

from __future__ import annotations

import hashlib

import pytest


class ObjectStoreContractTests:
    """Mixin run against every object store adapter."""

    def make_store(self, tmp_path):
        raise NotImplementedError

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        s = self.make_store(tmp_path)
        yield s
        s.close()

    def test_declares_provider_and_capabilities(self, store):
        assert isinstance(store.provider, str) and store.provider
        caps = store.capabilities()
        assert caps.checksums is True
        assert isinstance(caps.presign_urls, bool)

    def test_put_returns_sha256_checksum(self, store):
        data = b"contract-bytes"
        checksum = store.put("a.bin", data)
        assert checksum == hashlib.sha256(data).hexdigest()

    def test_put_get_roundtrip(self, store):
        store.put("greeting.txt", b"hello world", "text/plain")
        assert store.get("greeting.txt") == b"hello world"

    def test_put_replace_updates(self, store):
        store.put("key", b"v1")
        store.put("key", b"v2")
        assert store.get("key") == b"v2"

    def test_delete(self, store):
        store.put("key", b"data")
        assert store.delete("key")
        assert not store.exists("key")
        assert not store.delete("key")

    def test_missing_get_raises_key_error(self, store):
        with pytest.raises(KeyError):
            store.get("nope")

    def test_missing_stat_raises_key_error(self, store):
        with pytest.raises(KeyError):
            store.stat("nope")

    def test_stat_reports_size_and_content_type(self, store):
        store.put("file.bin", b"12345", "application/octet-stream")
        stat = store.stat("file.bin")
        assert stat["size"] == 5
        assert stat["content_type"] == "application/octet-stream"

    def test_list_by_prefix(self, store):
        store.put("reports/2024.pdf", b"%PDF")
        store.put("reports/2025.pdf", b"%PDF")
        store.put("images/logo.png", b"PNG")
        assert len(store.list("reports/")) == 2
        assert len(store.list("images/")) == 1
        assert len(store.list("")) == 3

    def test_data_survives_reopen(self, store, tmp_path):
        store.put("durable", b"persist")
        store.close()
        reopened = self.make_store(tmp_path)
        try:
            assert reopened.get("durable") == b"persist"
        finally:
            reopened.close()


class TestLocalObjectStore(ObjectStoreContractTests):
    def make_store(self, tmp_path):
        from voodoo.storage.objects import LocalObjectStore

        return LocalObjectStore(tmp_path / "objects")

    def test_local_capabilities(self, store):
        caps = store.capabilities()
        assert caps.provider == "local"
        assert caps.presign_urls is False
        assert caps.metadata is True
