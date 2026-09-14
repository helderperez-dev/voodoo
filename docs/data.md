# Data & Models

## What it is

`Model` is Store-first. In a fresh Voodoo application, persistent model records
are stored in `.voodoo/application.vstore` through Voodoo Store Collections.
SQLite and PostgreSQL remain explicit SQL adapters; they are not the default
persistence path.

```text
Model
  |
  v
Voodoo Runtime
  |
  v
Voodoo Store Collections
  |
  v
.voodoo/application.vstore
```

## Minimal example

```python
from voodoo import Model


class Lead(Model):
    name: str
    email: str
    score: int = 0


lead = await Lead.create(name="Ada", email="ada@x.io")
lead = await Lead.get(lead.id)
leads = await Lead.all()
lead.score = 95
await lead.save()
await lead.delete()
```

No database initialization is required for this default path. The application
Runtime owns the Store lifecycle.

## Queries

```python
leads = await Lead.where(email="ada@x.io").order_by("-score").limit(20)
first = await Lead.first(email="ada@x.io")
count = await Lead.count()
deleted = await Lead.delete_where(email="old@x.io")
```

The current Store-backed query facade preserves the public `Model` ergonomics.
Filtering/order/offset/limit are evaluated through the Store compatibility
layer while richer native indexes/query capabilities evolve.

## Lifecycle hooks

Lifecycle hooks remain available on the Store path:

```python
from voodoo.data import on_insert


@on_insert(Lead)
async def validate_lead(model):
    if not model.email:
        raise ValueError("Email required")
```

Store-backed inserts/updates fire the same model hook registry.

## Row-Level Security caveat

The legacy `rls_policy()` API returns SQL predicates. SQL predicate strings do
not map safely onto Voodoo Store Collections, so they are **not silently
interpreted** on the Store backend.

If a model currently depends on SQL-string RLS, select an explicit SQL adapter
until the policy-native Model authorization contract lands:

```toml
[database]
provider = "postgres"
url = "postgresql://user:pass@localhost:5432/voodoo"
```

Attempting to use a SQL-string RLS policy through the Store backend fails
clearly instead of bypassing the policy.

## `Model` vs `BaseModel`

- `Model` — public Store-first CRUD/query facade.
- `BaseModel` — legacy/raw SQL ORM compatibility surface.

Calling `init_db()` explicitly or configuring a SQL database provider selects
the SQL compatibility path.

## Explicit SQLite adapter

SQLite is still available when explicitly requested:

```bash
pip install "voodoo-framework[sqlite]"
```

```toml
[database]
provider = "sqlite"
path = ".voodoo/state/data.db"
```

Or initialize the compatibility API directly:

```python
from voodoo.data import get_db, init_db

await init_db("data.db")
db = await get_db()
```

This is an adapter choice, not the fresh-app default.

## PostgreSQL adapter

Install the optional extra:

```bash
pip install "voodoo-framework[postgres]"
```

Configure only the database domain:

```toml
[database]
provider = "postgres"
url = "postgresql://user:pass@localhost:5432/voodoo"
```

The rest of the Runtime can continue using Voodoo Store unless separately
overridden.

## Store transaction boundary

For operations that must atomically mutate Store state and stage an application
message, use the Runtime transaction boundary rather than opening a second
storage system:

```python
from voodoo.runtime import OutboxMessage, transaction

with transaction() as tx:
    tx.upsert_record(b"orders", b"42", b'{"status":"created"}')
    tx.stage_outbox(
        OutboxMessage(
            id="order-42-created",
            topic="order.created",
            payload={"order_id": "42"},
        )
    )
```

The supported atomicity is local to one Runtime Store commit. Voodoo does not
claim global transactions across external systems or nodes.

## Memory is a separate abstraction

`Model` persistence and agent/entity Memory are different concepts. The legacy
`SQLiteMemoryStore` remains an explicit Memory implementation with FTS5 search;
it does not redefine the default `Model` backend.

```python
from voodoo import MemoryEntry, MemoryLayer, SQLiteMemoryStore

memory = SQLiteMemoryStore("memory.db")
entry = MemoryEntry(
    entity_id="user:42",
    layer=MemoryLayer.EPISODIC,
    content="User asked about enterprise pricing",
)
await memory.write(entry)
```

For ephemeral tests, use `InMemoryMemoryStore`.

## Current boundaries

- Voodoo Store is the default `Model` persistence backend.
- SQLite/PostgreSQL are explicit adapters.
- Store-backed CRUD, queries and lifecycle hooks are supported.
- Legacy SQL-string RLS requires an explicit SQL adapter today.
- Native richer Store query/index capabilities can replace compatibility
  implementations without changing the `Model` API.

## API reference

- `Model.create(**kwargs)` — insert and return a Store-backed model by default.
- `Model.get(id)` — fetch by primary key.
- `Model.all()` — fetch all records.
- `Model.where(**filters)` — lazy query facade.
- `Model.first(**filters)` — first match or `None`.
- `Model.count(**filters)` — matching record count.
- `Model.delete_where(**filters)` — delete filtered records.
- `model.save()` — insert or update.
- `model.delete()` — delete one record.
- `BaseModel` — explicit/legacy SQL ORM base.
- `init_db()` / `get_db()` — explicit SQL compatibility APIs.
- `on_insert()` / `on_update()` — model lifecycle hook decorators.
- `rls_policy()` — legacy SQL predicate policy; requires SQL backend today.
