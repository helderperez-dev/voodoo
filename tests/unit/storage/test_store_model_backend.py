"""Sprint 28.3 acceptance for Store-first Model persistence."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from voodoo.data import (
    Delete,
    Model,
    close_db,
    field,
    relation,
    store_backend,
    validate,
    validate_model,
)
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
    assert isinstance(lead.id, UUID)
    assert lead.id.version == 7

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

    assert isinstance(record_id, UUID)
    assert record_id.version == 7
    assert native.kv == {}
    record = native.get_record(b"lead", record_id.bytes)
    assert record is not None
    loaded = store_backend.get_record("lead", record_id)
    assert loaded == {"id": str(record_id), "name": "Ada"}


def test_native_scan_and_update_use_collection_records_only(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    first_id = UUID("018f0000-0000-7000-8000-000000000001")
    second_id = UUID("018f0000-0000-7000-8000-000000000002")

    native.create_collection(b"lead", codec=b"json")
    native.upsert_record(
        b"lead",
        first_id.bytes,
        ('{"id":"' + str(first_id) + '","name":"Ada"}').encode(),
    )
    native.upsert_record(
        b"lead",
        second_id.bytes,
        ('{"id":"' + str(second_id) + '","name":"Grace"}').encode(),
    )

    assert store_backend.scan_records("lead") == [
        {"id": str(first_id), "name": "Ada"},
        {"id": str(second_id), "name": "Grace"},
    ]

    store_backend.put_record("lead", first_id, {"name": "Updated"})
    assert store_backend.get_record("lead", first_id) == {
        "id": str(first_id),
        "name": "Updated",
    }


def test_backend_maintains_declared_native_indexes(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("lead", {"email": False, "score": False, "active": False})

    record_id = store_backend.insert_record(
        "lead",
        {"name": "Ada", "email": "ada@x.io", "score": 42, "active": True},
    )

    record = native.records[(b"lead", record_id.bytes)]
    indexes = dict(record[1])
    assert isinstance(record_id, UUID)
    assert set(native.indexes[b"lead"]) == {b"email", b"score", b"active"}
    assert indexes[b"email"].startswith(b"s:")
    assert indexes[b"score"].startswith(b"i:")
    assert indexes[b"active"] == b"b:1"


def test_query_records_uses_exact_index_without_collection_scan(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("lead", {"email": False, "score": False})

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
    store_backend.register_indexes("lead", {"score": False})

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

    record_id = store_backend.insert_record(
        "backfill_lead",
        {"name": "Ada", "email": "ada@x.io"},
    )
    assert native.records[(b"backfill_lead", record_id.bytes)][1] == []

    store_backend.register_indexes("backfill_lead", {"email": False})
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
        native.records[(b"backfill_lead", record_id.bytes)][1]
    )
    assert indexes[b"email"].startswith(b"s:")


def test_multi_column_order_falls_back_without_corrupting_order(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)
    store_backend.register_indexes("multi_order_lead", {"score": False})

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



@pytest.mark.asyncio
async def test_model_defaults_optional_fields_and_default_factory(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    class Profile(Model):
        name: str
        nickname: str | None
        active: bool = True
        created_at: datetime = field(
            default_factory=lambda: datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
        )

    profile = await Profile.create(name="Ada")
    assert profile.nickname is None
    assert profile.active is True
    assert profile.created_at == datetime(2026, 9, 24, 12, 0, tzinfo=UTC)

    loaded = await Profile.get(profile.id)
    assert loaded is not None
    assert loaded.nickname is None
    assert loaded.active is True
    assert loaded.created_at == profile.created_at


@pytest.mark.asyncio
async def test_model_rejects_missing_required_and_non_nullable_none(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    class RequiredProfile(Model):
        name: str
        nickname: str | None

    with pytest.raises(TypeError, match="Missing required field: name"):
        await RequiredProfile.create()

    with pytest.raises(TypeError, match="name cannot be None"):
        await RequiredProfile.create(name=None)


@pytest.mark.asyncio
async def test_field_and_model_validators_are_separate_from_storage_metadata(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    class Account(Model):
        email: str
        start: int
        end: int

        @validate("email")
        def normalize_email(self, value):
            if "@" not in value:
                raise ValueError("invalid email")
            return value.strip().lower()

        @validate_model
        def interval_is_valid(self):
            if self.end <= self.start:
                raise ValueError("end must be after start")

    account = await Account.create(
        email=" ADA@EXAMPLE.COM ",
        start=1,
        end=2,
    )
    assert account.email == "ada@example.com"

    with pytest.raises(ValueError, match="invalid email"):
        await Account.create(email="invalid", start=1, end=2)

    with pytest.raises(ValueError, match="end must be after start"):
        await Account.create(email="a@x.io", start=2, end=1)


@pytest.mark.asyncio
async def test_relation_hydrates_target_model_and_persists_only_uuid(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    class RelationCustomer(Model):
        name: str

    class RelationOrder(Model):
        customer: RelationCustomer = relation()
        total: int

    customer = await RelationCustomer.create(name="Ada")
    order = await RelationOrder.create(customer=customer, total=42)

    stored = store_backend.get_record("relationorder", order.id)
    assert stored is not None
    assert stored["customer"] == str(customer.id)

    loaded = await RelationOrder.get(order.id)
    assert loaded is not None
    assert isinstance(loaded.customer, RelationCustomer)
    assert loaded.customer.id == customer.id
    assert loaded.customer.name == "Ada"


@pytest.mark.asyncio
async def test_relation_delete_policies_are_explicit(monkeypatch):
    native = _FakeNativeCollections()
    monkeypatch.setattr(store_backend, "_native", lambda: native)

    class ParentRestrict(Model):
        name: str

    class ChildRestrict(Model):
        parent: ParentRestrict = relation(on_delete=Delete.RESTRICT)

    parent = await ParentRestrict.create(name="p")
    await ChildRestrict.create(parent=parent)
    with pytest.raises(ValueError, match="Cannot delete"):
        await parent.delete()

    class ParentCascade(Model):
        name: str

    class ChildCascade(Model):
        parent: ParentCascade = relation(on_delete=Delete.CASCADE)

    cascade_parent = await ParentCascade.create(name="p")
    cascade_child = await ChildCascade.create(parent=cascade_parent)
    await cascade_parent.delete()
    assert await ChildCascade.get(cascade_child.id) is None

    class ParentOptional(Model):
        name: str

    class ChildOptional(Model):
        parent: ParentOptional | None = relation(on_delete=Delete.SET_NULL)

    optional_parent = await ParentOptional.create(name="p")
    optional_child = await ChildOptional.create(parent=optional_parent)
    await optional_parent.delete()
    loaded_child = await ChildOptional.get(optional_child.id)
    assert loaded_child is not None
    assert loaded_child.parent is None
