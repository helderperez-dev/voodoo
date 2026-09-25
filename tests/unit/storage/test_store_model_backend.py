"""Sprint 28.3 acceptance for Store-first Model persistence."""

from pathlib import Path

import pytest

from voodoo.data import Model, close_db, field, store_backend
from voodoo.data.store_backend import bind_runtime_store
from voodoo.runtime.store import RuntimeStore, StoreConfig


class StoreLead(Model):
    name: str
    email: str = field(index=True)
    score: int = field(index=True)
    active: bool = field(index=True)


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
        self.indexes: dict[bytes, set[bytes]] = {}
        self.index_uniqueness: dict[tuple[bytes, bytes], bool] = {}
        self.scan_calls = 0
        self.exact_query_calls: list[tuple[bytes, bytes, bytes]] = []
        self.range_query_calls: list[tuple[bytes, bytes, bool]] = []

    def create_collection(self, name: bytes, **_kwargs) -> bool:
        created = name not in self.collections
        self.collections.add(bytes(name))
        return created

    def define_index(
        self, collection: bytes, name: bytes, *, unique: bool = False, **_kwargs
    ) -> bool:
        collection_key = bytes(collection)
        name_key = bytes(name)
        indexes = self.indexes.setdefault(collection_key, set())
        created = name_key not in indexes
        indexes.add(name_key)
        self.index_uniqueness[(collection_key, name_key)] = bool(unique)
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
        return (
            self.records.pop((bytes(collection), bytes(primary_key)), None) is not None
        )

    def scan_collection(self, collection: bytes):
        self.scan_calls += 1
        rows = []
        for (record_collection, primary_key), (value, indexes) in sorted(
            self.records.items()
        ):
            if record_collection == collection:
                rows.append((primary_key, value, indexes))
        return rows

    def query_index_exact(self, collection: bytes, index: bytes, value: bytes):
        self.exact_query_calls.append((bytes(collection), bytes(index), bytes(value)))
        rows = []
        for (record_collection, primary_key), (payload, indexes) in sorted(
            self.records.items()
        ):
            if record_collection != collection:
                continue
            if (bytes(index), bytes(value)) in indexes:
                rows.append((primary_key, payload, indexes))
        return rows

    def query_index_range(
        self,
        collection: bytes,
        index: bytes,
        *,
        start=None,
        end=None,
        start_inclusive=True,
        end_inclusive=True,
        descending=False,
        limit=None,
    ):
        del start, end, start_inclusive, end_inclusive
        self.range_query_calls.append(
            (bytes(collection), bytes(index), bool(descending))
        )
        rows = []
        for (record_collection, primary_key), (payload, indexes) in self.records.items():
            if record_collection != collection:
                continue
            for index_name, index_value in indexes:
                if bytes(index_name) == bytes(index):
                    rows.append(
                        (
                            bytes(index_value),
                            (primary_key, payload, indexes),
                        )
                    )
                    break
        rows.sort(key=lambda item: (item[0], item[1][0]), reverse=descending)
        if limit is not None:
            rows = rows[:limit]
        return rows


def test_backend_uses_native_collections(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    record_id = store_backend.insert_record("lead", {"name": "Ada"})

    assert record_id == 1
    assert native.kv[b"data:lead:meta:next_id"] == b"2"
    record = native.get_record(b"lead", b"00000000000000000001")
    assert record is not None
    assert store_backend.get_record("lead", 1) == {"id": 1, "name": "Ada"}


def test_native_scan_and_update_use_collection_records_only(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    native.create_collection(b"lead", codec=b"json")
    native.upsert_record(
        b"lead",
        b"00000000000000000001",
        b'{"id":1,"name":"Ada"}',
    )
    native.upsert_record(
        b"lead",
        b"00000000000000000002",
        b'{"id":2,"name":"Grace"}',
    )

    assert store_backend.scan_records("lead") == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]

    store_backend.put_record("lead", 1, {"name": "Updated"})
    assert store_backend.get_record("lead", 1) == {"id": 1, "name": "Updated"}


def test_backend_maintains_declared_native_indexes(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("lead", {"email": false, "score": false, "active": false})

    record_id = store_backend.insert_record(
        "lead",
        {"name": "Ada", "email": "ada@x.io", "score": 42, "active": True},
    )

    record = native.records[(b"lead", b"00000000000000000001")]
    indexes = dict(record[1])
    assert record_id == 1
    assert set(native.indexes[b"lead"]) == {b"email", b"score", b"active"}
    assert indexes[b"email"].startswith(b"s:")
    assert indexes[b"score"].startswith(b"i:")
    assert indexes[b"active"] == b"b:1"


def test_query_records_uses_exact_index_without_collection_scan(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("lead", {"email": false, "score": false})

    store_backend.insert_record(
        "lead", {"name": "A", "email": "a@x.io", "score": 5}
    )
    store_backend.insert_record(
        "lead", {"name": "B", "email": "b@x.io", "score": 15}
    )
    store_backend.insert_record(
        "lead", {"name": "C", "email": "a@x.io", "score": 10}
    )
    native.scan_calls = 0

    rows = store_backend.query_records(
        "lead",
        filters={"email": "a@x.io"},
        order_by=["-score"],
        limit=1,
        offset=None,
    )

    assert [row["name"] for row in rows] == ["C"]
    assert len(native.exact_query_calls) == 1
    assert native.exact_query_calls[0][:2] == (b"lead", b"email")
    assert native.scan_calls == 0


def test_query_records_uses_range_index_for_native_order(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("lead", {"score": false})

    for name, score in [("A", 5), ("B", 15), ("C", 10)]:
        store_backend.insert_record("lead", {"name": name, "score": score})
    native.scan_calls = 0

    rows = store_backend.query_records(
        "lead",
        filters={},
        order_by=["-score"],
        limit=2,
        offset=None,
    )

    assert [row["score"] for row in rows] == [15, 10]
    assert native.range_query_calls == [(b"lead", b"score", True)]
    assert native.scan_calls == 0


def test_new_index_backfills_existing_collection_records(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("backfill_lead", {})

    store_backend.insert_record(
        "backfill_lead",
        {"name": "Ada", "email": "ada@x.io"},
    )
    assert native.records[
        (b"backfill_lead", b"00000000000000000001")
    ][1] == []

    store_backend.register_indexes("backfill_lead", {"email": false})
    rows = store_backend.query_records(
        "backfill_lead",
        filters={"email": "ada@x.io"},
        order_by=[],
        limit=None,
        offset=None,
    )

    assert [row["name"] for row in rows] == ["Ada"]
    assert native.exact_query_calls[-1][:2] == (b"backfill_lead", b"email")
    indexes = dict(
        native.records[(b"backfill_lead", b"00000000000000000001")][1]
    )
    assert indexes[b"email"].startswith(b"s:")


def test_multi_column_order_falls_back_without_corrupting_order(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("multi_order_lead", {"score": false})

    for name, score in [("B", 10), ("A", 10), ("C", 5)]:
        store_backend.insert_record(
            "multi_order_lead",
            {"name": name, "score": score},
        )
    native.scan_calls = 0
    native.range_query_calls.clear()

    rows = store_backend.query_records(
        "multi_order_lead",
        filters={},
        order_by=["-score", "name"],
        limit=None,
        offset=None,
    )

    assert [(row["score"], row["name"]) for row in rows] == [
        (10, "A"),
        (10, "B"),
        (5, "C"),
    ]
    assert native.range_query_calls == []
    assert native.scan_calls == 1


def test_field_unique_implies_native_unique_index(monkeypatch):
    class UniqueLead(Model):
        email: str = field(unique=True)

    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    # ModelMeta has already registered the field metadata; creating the
    # collection must carry the unique flag into Store.define_index.
    store_backend.insert_record("uniquelead", {"email": "ada@x.io"})
    assert b"email" in native.indexes[b"uniquelead"]
    assert native.index_uniqueness[(b"uniquelead", b"email")] is True
