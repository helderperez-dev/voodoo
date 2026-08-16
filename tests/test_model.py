import asyncio

import pytest

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
async def test_create_and_get(test_db):
    lead = await Lead.create(name="Ada", email="ada@x.io", score=42)
    assert lead.id is not None

    fetched = await Lead.get(lead.id)
    assert fetched is not None
    assert fetched.name == "Ada"
    assert fetched.email == "ada@x.io"
    assert fetched.score == 42


@pytest.mark.asyncio
async def test_get_missing_returns_none(test_db):
    assert await Lead.get(99999) is None


@pytest.mark.asyncio
async def test_all_returns_rows(test_db):
    await Lead.create(name="A", email="a@x.io", score=1)
    await Lead.create(name="B", email="b@x.io", score=2)

    leads = await Lead.all()
    assert len(leads) == 2
    assert {lead.name for lead in leads} == {"A", "B"}
    # all() returns Model instances
    assert all(isinstance(lead, Lead) for lead in leads)


@pytest.mark.asyncio
async def test_all_is_alias_of_find_all(test_db):
    await Lead.create(name="C", email="c@x.io", score=3)
    via_all = await Lead.all()
    via_find_all = await Lead.find_all()
    assert len(via_all) == len(via_find_all) == 1


@pytest.mark.asyncio
async def test_save_inserts_when_no_id(test_db):
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
async def test_save_updates_when_has_id(test_db):
    lead = await Lead.create(name="Ada", email="ada@x.io", score=1)
    lead.score = 99
    await lead.save()

    fetched = await Lead.get(lead.id)
    assert fetched is not None
    assert fetched.score == 99


@pytest.mark.asyncio
async def test_delete_removes_row(test_db):
    lead = await Lead.create(name="Ada", email="a@x.io", score=1)
    lid = lead.id
    await lead.delete()
    assert await Lead.get(lid) is None


@pytest.mark.asyncio
async def test_on_insert_hook_fires(test_db):
    inserted_leads.clear()
    await Lead.create(name="Hooked", email="h@x.io", score=1)
    # async hook is scheduled via create_task; let the loop tick.
    await asyncio.sleep(0.01)
    assert "Hooked" in inserted_leads


@pytest.mark.asyncio
async def test_on_update_hook_fires(test_db):
    updated_leads.clear()
    lead = await Lead.create(name="Upd", email="u@x.io", score=1)
    lead.score = 7
    await lead.save()  # has id -> update path
    # sync hook is called directly inside update()
    assert "Upd" in updated_leads


@pytest.mark.asyncio
async def test_table_created_during_init(test_db):
    # The `lead` table must have been created by init_db() for the model.
    async with test_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='lead'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert len(rows) == 1
