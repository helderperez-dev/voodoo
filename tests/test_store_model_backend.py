"""Sprint 28.3 acceptance for Store-first Model persistence."""

from pathlib import Path

import pytest

from voodoo.data import Model, close_db
from voodoo.data import store_backend
from voodoo.data.store_backend import bind_runtime_store
from voodoo.runtime.store import RuntimeStore, StoreConfig


class StoreLead(Model):
    name: str
    email: str
    score: int
    active: bool


@pytest.fixture
def store_runtime(tmp_path: Path):
    runtime = RuntimeStore(
        StoreConfig(path=tmp_path / "application.vstore", enabled=True)
    )
    runtime.start()
    bind_runtime_store(runtime)
    try:
        yield runtime
    finally:
        bind_runtime_store(None)
        runtime.stop()


@pytest.mark.asyncio
async def test_model_crud_uses_application_store_without_sqlite(store_runtime):
    await close_db()

    lead = await StoreLead.create(
        name="Ada", email="ada@voodoo.build", score=42, active=True
    )
    assert lead.id == 1

    fetched = await StoreLead.get(lead.id)
    assert fetched is not None
    assert fetched.name == "Ada"
    assert fetched.score == 42
    assert fetched.active is True

    lead.score = 99
    await lead.save()
    updated = await StoreLead.get(lead.id)
    assert updated is not None
    assert updated.score == 99

    await lead.delete()
    assert await StoreLead.get(lead.id) is None


@pytest.mark.asyncio
async def test_store_query_preserves_model_ergonomics(store_runtime):
    await close_db()

    await StoreLead.create(name="A", email="a@x.io", score=5, active=True)
    await StoreLead.create(name="B", email="b@x.io", score=15, active=False)
    await StoreLead.create(name="C", email="a@x.io", score=10, active=True)

    rows = await StoreLead.where(email="a@x.io").order_by("-score").limit(1)
    assert [row.name for row in rows] == ["C"]
    assert await StoreLead.count(active=True) == 2
    assert (await StoreLead.first(email="b@x.io")).name == "B"

    deleted = await StoreLead.delete_where(email="a@x.io")
    assert deleted == 2
    assert await StoreLead.count() == 1


def test_store_model_uses_same_runtime_store_file(store_runtime):
    assert store_runtime.config.path.exists()
    assert store_runtime.started is True


class _FakeNativeTransaction:
    def __init__(self, store: "_FakeNativeCollections") -> None:
        self.store = store
        self.kv = dict(store.kv)
        self.records = dict(store.records)

    def get(self, key: bytes):
        return self.kv.get(key)

    def put(self, key: bytes, value: bytes) -> None:
        self.kv[key] = bytes(value)

    def upsert_record(
        self,
        collection: bytes,
        primary_key: bytes,
        value: bytes,
        *,
        indexes=(),
    ) -> None:
        self.records[(bytes(collection), bytes(primary_key))] = (
            bytes(value),
            list(indexes),
        )

    def commit(self) -> None:
        self.store.kv = self.kv
        self.store.records = self.records


class _FakeNativeCollections:
    def __init__(self) -> None:
        self.kv: dict[bytes, bytes] = {}
        self.records: dict[tuple[bytes, bytes], tuple[bytes, list]] = {}
        self.collections: set[bytes] = set()

    def create_collection(self, name: bytes, **_kwargs) -> bool:
        created = name not in self.collections
        self.collections.add(bytes(name))
        return created

    def transaction(self) -> _FakeNativeTransaction:
        return _FakeNativeTransaction(self)

    def get(self, key: bytes):
        return self.kv.get(key)

    def put(self, key: bytes, value: bytes) -> None:
        self.kv[key] = bytes(value)

    def delete(self, key: bytes) -> None:
        self.kv.pop(key, None)

    def scan_prefix(self, prefix: bytes):
        return sorted(
            (key, value) for key, value in self.kv.items() if key.startswith(prefix)
        )

    def upsert_record(
        self,
        collection: bytes,
        primary_key: bytes,
        value: bytes,
        *,
        indexes=(),
    ) -> None:
        self.records[(bytes(collection), bytes(primary_key))] = (
            bytes(value),
            list(indexes),
        )

    def get_record(self, collection: bytes, primary_key: bytes):
        record = self.records.get((bytes(collection), bytes(primary_key)))
        if record is None:
            return None
        value, indexes = record
        return bytes(primary_key), value, indexes

    def delete_record(self, collection: bytes, primary_key: bytes) -> bool:
        return self.records.pop((bytes(collection), bytes(primary_key)), None) is not None

    def scan_collection(self, collection: bytes):
        rows = []
        for (record_collection, primary_key), (value, indexes) in sorted(
            self.records.items()
        ):
            if record_collection == collection:
                rows.append((primary_key, value, indexes))
        return rows


def test_backend_prefers_native_collections_when_binding_supports_them(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    record_id = store_backend.insert_record("lead", {"name": "Ada"})

    assert record_id == 1
    assert native.kv[b"data:lead:meta:next_id"] == b"2"
    assert b"data:lead:record:00000000000000000001" not in native.kv
    record = native.get_record(b"lead", b"00000000000000000001")
    assert record is not None
    assert store_backend.get_record("lead", 1) == {"id": 1, "name": "Ada"}


def test_native_scan_migrates_progressively_from_legacy_records(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    legacy_key = b"data:lead:record:00000000000000000001"
    native.put(legacy_key, b'{"id":1,"name":"Legacy"}')
    native.create_collection(b"lead", codec=b"json")
    native.upsert_record(
        b"lead",
        b"00000000000000000001",
        b'{"id":1,"name":"Native"}',
    )
    native.upsert_record(
        b"lead",
        b"00000000000000000002",
        b'{"id":2,"name":"Grace"}',
    )

    assert store_backend.scan_records("lead") == [
        {"id": 1, "name": "Native"},
        {"id": 2, "name": "Grace"},
    ]

    store_backend.put_record("lead", 1, {"name": "Updated"})
    assert legacy_key not in native.kv
    assert store_backend.get_record("lead", 1) == {"id": 1, "name": "Updated"}
