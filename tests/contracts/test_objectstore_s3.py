"""S3-compatible object store contract tests (Sprint 6, hardened Sprint 12).

The same ``ObjectStoreContractTests`` suite used for ``LocalObjectStore``
runs against a real S3-compatible server (AWS S3, MinIO, R2, …) when
``VOODOO_TEST_S3_ENDPOINT`` is set — CI provides one via a service
container (``.github/workflows/ci.yml``, ``minio/minio``). Locally the
module is skipped when no server is available, so the default ``pytest``
run stays green without boto3 or a running object store.
"""

from __future__ import annotations

import hashlib
import os

import pytest

from tests.contracts.test_objectstore import ObjectStoreContractTests

boto3 = pytest.importorskip("boto3")

pytestmark = pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_S3_ENDPOINT"),
    reason="VOODOO_TEST_S3_ENDPOINT not set (no S3-compatible server available)",
)

ENDPOINT = os.environ.get("VOODOO_TEST_S3_ENDPOINT")
BUCKET = os.environ.get("VOODOO_TEST_S3_BUCKET", "voodoo-test")
ACCESS_KEY = os.environ.get("VOODOO_TEST_S3_KEY", "minioadmin")
SECRET_KEY = os.environ.get("VOODOO_TEST_S3_SECRET", "minioadmin")


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        config=boto3.session.Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


@pytest.fixture(scope="module", autouse=True)
def _ensure_bucket():
    """Create the test bucket once; skip if the server is unreachable."""
    client = _s3_client()
    try:
        existing = client.list_buckets()["Buckets"]
        if not any(b["Name"] == BUCKET for b in existing):
            client.create_bucket(Bucket=BUCKET)
    except Exception as exc:  # noqa: BLE001 - unreachable server
        pytest.skip(f"S3 server at {ENDPOINT} unreachable: {exc}")
    finally:
        client.close()


class TestS3ObjectStore(ObjectStoreContractTests):
    """Contract suite against a live S3-compatible server."""

    def make_store(self, tmp_path):
        from voodoo.storage.objects.s3 import S3ObjectStore

        # tmp_path is unique per test but stable across the two make_store
        # calls inside test_data_survives_reopen, so the prefix isolates
        # each test while allowing reopen to find the same objects.
        store = S3ObjectStore(
            bucket=BUCKET,
            endpoint=ENDPOINT,
            key=ACCESS_KEY,
            secret=SECRET_KEY,
            region="us-east-1",
            root_prefix=f"contract/{tmp_path.name}/",
        )
        assert store.use_s3
        return store

    # -- provider-specific behavior ---------------------------------------

    def test_s3_capabilities(self, store):
        caps = store.capabilities()
        assert caps.provider == "s3"
        assert caps.presign_urls is True
        assert caps.checksums is True
        assert caps.metadata is True
        assert caps.multipart is True

    def test_presign_get_roundtrip(self, store):
        import urllib.request

        store.put("presigned.txt", b"presign-get", "text/plain")
        url = store.presign("presigned.txt", expires_in=300)
        assert url.startswith("http")
        with urllib.request.urlopen(url) as resp:  # noqa: S310 - test server
            assert resp.read() == b"presign-get"

    def test_presign_put_roundtrip(self, store):
        import urllib.request

        url = store.presign_put("uploaded.txt", expires_in=300)
        data = b"presign-put-bytes"
        req = urllib.request.Request(
            url, data=data, method="PUT", headers={"Content-Type": "text/plain"}
        )
        with urllib.request.urlopen(req):  # noqa: S310 - test server
            pass
        assert store.get("uploaded.txt") == data

    def test_multipart_upload(self, store):
        # Force the multipart path with a small threshold (no 8 MiB payload).
        store.multipart_threshold = 0
        data = b"m" * (8 * 1024 * 1024 + 1024)  # > one part, exercises splitting
        checksum = store.put("big.bin", data, "application/octet-stream")
        assert checksum == hashlib.sha256(data).hexdigest()
        assert store.get("big.bin") == data
        stat = store.stat("big.bin")
        assert stat["size"] == len(data)
        assert stat["checksum"] == checksum

    def test_stat_reports_metadata_checksum(self, store):
        store.put("meta.bin", b"payload", "text/x-custom")
        stat = store.stat("meta.bin")
        assert stat["content_type"] == "text/x-custom"
        assert stat["checksum"] == hashlib.sha256(b"payload").hexdigest()

    def test_url_path_style(self, store):
        url = store.url("docs/file.pdf")
        assert url.startswith(ENDPOINT)
        assert f"/{BUCKET}/" in url
