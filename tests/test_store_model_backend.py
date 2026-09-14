"""Sprint 28.3 acceptance for Store-first Model persistence."""

from pathlib import Path

import pytest

from voodoo.data import Model, close_db
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
