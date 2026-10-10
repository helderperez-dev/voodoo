from __future__ import annotations

import pytest

from voodoo.storage.objects.s3 import S3ObjectStore


class _Body:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            payload, self.payload = self.payload, b""
            return payload
        payload, self.payload = self.payload[:size], self.payload[size:]
        return payload

    def close(self) -> None:
        self.closed = True


class _Client:
    def __init__(self, payload: bytes, checksum: str) -> None:
        self.payload = payload
        self.checksum = checksum
        self.body: _Body | None = None

    def get_object(self, **_kwargs):
        self.body = _Body(self.payload)
        return {"Body": self.body, "Metadata": {"sha256": self.checksum}}

    def head_object(self, **_kwargs):
        return {
            "ContentLength": len(self.payload),
            "ContentType": "application/octet-stream",
            "Metadata": {"sha256": self.checksum},
        }


def _store(payload: bytes, checksum: str) -> tuple[S3ObjectStore, _Client]:
    store = S3ObjectStore(bucket="bucket", endpoint="http://s3", key="key", secret="secret")
    client = _Client(payload, checksum)
    store.s3_client = client
    store.use_s3 = True
    return store, client


def test_s3_get_rejects_checksum_mismatch():
    store, client = _store(b"tampered", "0" * 64)
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.get("reports/item.txt")
    assert client.body is not None and client.body.closed is True


def test_s3_iter_chunks_rejects_checksum_mismatch_and_closes_body():
    store, client = _store(b"tampered", "0" * 64)
    with pytest.raises(ValueError, match="checksum mismatch"):
        list(store.iter_chunks("reports/item.txt", chunk_size=3))
    assert client.body is not None and client.body.closed is True


def test_s3_stat_rejects_malformed_checksum_metadata():
    store, _client = _store(b"payload", "not-a-checksum")
    with pytest.raises(ValueError, match="SHA-256"):
        store.stat("reports/item.txt")
