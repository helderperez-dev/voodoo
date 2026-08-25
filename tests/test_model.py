import asyncio

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


# ---------------------------------------------------------------------------
# Fluent query API (Phase 3 — less-code initiative)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_leads(test_db):
    await test_db.execute("DELETE FROM lead")
    await test_db.execute(
        "INSERT INTO lead (name, email, score) VALUES ('A', 'a@x.io', 5)"
    )
    await test_db.execute(
        "INSERT INTO lead (name, email, score) VALUES ('B', 'b@x.io', 15)"
    )
    await test_db.execute(
        "INSERT INTO lead (name, email, score) VALUES ('C', 'a@x.io', 10)"
    )
    await test_db.commit()


@pytest.mark.asyncio
async def test_where_filters_by_equality(test_db, seeded_leads):
    leads = await Lead.where(email="a@x.io")
    assert {lead.name for lead in leads} == {"A", "C"}
    # Chained filters are AND-ed.
    leads2 = await Lead.where(email="a@x.io", score=10)
    assert [lead.name for lead in leads2] == ["C"]


@pytest.mark.asyncio
async def test_where_order_by_desc_and_limit(test_db, seeded_leads):
    top = await Lead.where().order_by("-score").limit(2)
    assert [lead.score for lead in top] == [15, 10]


@pytest.mark.asyncio
async def test_first_returns_earliest_match(test_db, seeded_leads):
    lead = await Lead.first(email="a@x.io")
    assert lead is not None
    assert lead.name in {"A", "C"}
    assert await Lead.first(email="none@x.io") is None


@pytest.mark.asyncio
async def test_count_counts_matching_rows(test_db, seeded_leads):
    assert await Lead.count() == 3
    assert await Lead.count(email="a@x.io") == 2


@pytest.mark.asyncio
async def test_delete_where_removes_rows_and_reports_count(test_db, seeded_leads):
    deleted = await Lead.delete_where(email="a@x.io")
    assert deleted == 2
    assert await Lead.count() == 1


@pytest.mark.asyncio
async def test_query_is_lazy_and_chainable(test_db, seeded_leads):
    q = Lead.where(email="a@x.io")
    refined = q.order_by("-score").limit(1)
    # Original query unchanged by later chaining (immutable clone).
    assert q._limit is None
    rows = await refined
    assert [r.score for r in rows] == [10]


# ---------------------------------------------------------------------------
# FK cascades (Phase 3 — less-code initiative)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fk_cascade_deletes_children(test_db):
    from voodoo.data import FK

    class Conv(Model):
        title: str

    class Msg(Model):
        conversation_id: FK[Conv]
        content: str

    # Models defined after init_db create their tables explicitly.
    await Conv._create_table()
    await Msg._create_table()

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
