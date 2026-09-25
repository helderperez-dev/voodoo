import asyncio

from uuid import UUID

import pytest
import pytest_asyncio

from voodoo.data import Model, on_insert, on_update


class Lead(Model):
    name: str
    email: str
    score: int


inserted_leads: list[str] = []
updated_leads: list[str] = []


@on_insert(Lead)
async def hook_insert_lead(lead: Lead) -> None:
    inserted_leads.append(lead.name)


@on_update(Lead)
def hook_update_lead(lead: Lead) -> None:
    updated_leads.append(lead.name)


@pytest.mark.asyncio
async def test_create_and_get(model_store):
    lead = await Lead.create(name="Ada", email="ada@x.io", score=42)
    assert lead.id is not None

    fetched = await Lead.get(lead.id)
    assert fetched is not None
    assert fetched.name == "Ada"
    assert fetched.email == "ada@x.io"
    assert fetched.score == 42


@pytest.mark.asyncio
async def test_get_missing_returns_none(model_store):
    missing = UUID("018f0000-0000-7000-8000-ffffffffffff")
    assert await Lead.get(missing) is None


@pytest.mark.asyncio
async def test_all_returns_rows(model_store):
    await Lead.create(name="A", email="a@x.io", score=1)
    await Lead.create(name="B", email="b@x.io", score=2)

    leads = await Lead.all()
    assert len(leads) == 2
    assert {lead.name for lead in leads} == {"A", "B"}
    assert all(isinstance(lead, Lead) for lead in leads)


@pytest.mark.asyncio
async def test_all_is_alias_of_find_all(model_store):
    await Lead.create(name="C", email="c@x.io", score=3)
    via_all = await Lead.all()
    via_find_all = await Lead.find_all()
    assert len(via_all) == len(via_find_all) == 1


@pytest.mark.asyncio
async def test_save_inserts_when_no_id(model_store):
    lead = Lead()
    lead.name = "Ada"
    lead.email = "ada@x.io"
    lead.score = 1
    await lead.save()
    assert lead.id is not None

    fetched = await Lead.get(lead.id)
    assert fetched is not None
    assert fetched.name == "Ada"


@pytest.mark.asyncio
async def test_save_updates_when_has_id(model_store):
    lead = await Lead.create(name="Ada", email="ada@x.io", score=1)
    lead.score = 99
    await lead.save()

    fetched = await Lead.get(lead.id)
    assert fetched is not None
    assert fetched.score == 99


@pytest.mark.asyncio
async def test_delete_removes_row(model_store):
    lead = await Lead.create(name="Ada", email="a@x.io", score=1)
    lead_id = lead.id
    await lead.delete()
    assert await Lead.get(lead_id) is None


@pytest.mark.asyncio
async def test_on_insert_hook_fires(model_store):
    inserted_leads.clear()
    await Lead.create(name="Hooked", email="h@x.io", score=1)
    await asyncio.sleep(0.01)
    assert "Hooked" in inserted_leads


@pytest.mark.asyncio
async def test_on_update_hook_fires(model_store):
    updated_leads.clear()
    lead = await Lead.create(name="Upd", email="u@x.io", score=1)
    lead.score = 7
    await lead.save()
    assert "Upd" in updated_leads


def test_model_uses_application_store(model_store):
    assert model_store.config.path.name == "application.vstore"
    assert model_store.config.path.exists()


@pytest_asyncio.fixture
async def seeded_leads(model_store):
    await Lead.create(name="A", email="a@x.io", score=5)
    await Lead.create(name="B", email="b@x.io", score=15)
    await Lead.create(name="C", email="a@x.io", score=10)


@pytest.mark.asyncio
async def test_where_filters_by_equality(seeded_leads):
    leads = await Lead.where(email="a@x.io")
    assert {lead.name for lead in leads} == {"A", "C"}
    leads2 = await Lead.where(email="a@x.io", score=10)
    assert [lead.name for lead in leads2] == ["C"]


@pytest.mark.asyncio
async def test_where_order_by_desc_and_limit(seeded_leads):
    top = await Lead.where().order_by("-score").limit(2)
    assert [lead.score for lead in top] == [15, 10]


@pytest.mark.asyncio
async def test_first_returns_earliest_match(seeded_leads):
    lead = await Lead.first(email="a@x.io")
    assert lead is not None
    assert lead.name == "A"
    assert await Lead.first(email="none@x.io") is None


@pytest.mark.asyncio
async def test_count_counts_matching_rows(seeded_leads):
    assert await Lead.count() == 3
    assert await Lead.count(email="a@x.io") == 2


@pytest.mark.asyncio
async def test_delete_where_removes_rows_and_reports_count(seeded_leads):
    deleted = await Lead.delete_where(email="a@x.io")
    assert deleted == 2
    assert await Lead.count() == 1


@pytest.mark.asyncio
async def test_query_is_lazy_and_chainable(seeded_leads):
    query = Lead.where(email="a@x.io")
    refined = query.order_by("-score").limit(1)
    assert query._limit is None
    rows = await refined
    assert [row.score for row in rows] == [10]


@pytest.mark.asyncio
async def test_fk_cascade_deletes_children(model_store):
    from voodoo.data import FK

    class Conv(Model):
        title: str

    class Msg(Model):
        conversation_id: FK[Conv]
        content: str

    conv = await Conv.create(title="hello")
    await Msg.create(conversation_id=conv.id, content="m1")
    await Msg.create(conversation_id=conv.id, content="m2")
    other = await Conv.create(title="other")
    await Msg.create(conversation_id=other.id, content="keep")

    await conv.delete()

    assert await Msg.count() == 1
    remaining = await Msg.first()
    assert remaining is not None
    assert remaining.content == "keep"
