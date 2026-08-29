# Data & Models

## What it is

Voodoo ships with an async SQLite data layer. Define models with typed fields, and get CRUD operations for free. Row-Level Security (RLS) policies and lifecycle hooks (`on_insert`, `on_update`) are built in.

## Minimal example

```python
from voodoo import Model


class Lead(Model):
    name: str
    email: str
    score: int = 0


# CRUD
lead = await Lead.create(name="Ada", email="ada@x.io")
lead = await Lead.get(lead.id)
leads = await Lead.all()
lead.score = 95
await lead.save()
await lead.delete()
```

## Common usage

### Lifecycle hooks

```python
from voodoo.data import on_insert


@on_insert(Lead)
async def validate_lead(model):
    if not model.email:
        raise ValueError("Email required")
```

### Row-Level Security

```python
from voodoo.data import rls_policy


@rls_policy(Lead)
def lead_rls(user_context):
    if user_context["role"] == "admin":
        return "1=1"
    return f"user_id = {user_context['id']}"
```

### Querying with RLS

```python
user_ctx = {"role": "user", "id": 42}
leads = await Lead.all(user_context=user_ctx)
```

## Advanced

### BaseModel vs Model

- `BaseModel` — the raw ORM (async `insert()`, `update()`, `_create_table()`).
- `Model` — the CRUD facade (`create()`, `get()`, `all()`, `save()`, `delete()`).

### Database initialization

```python
from voodoo.data import init_db, get_db

await init_db(":memory:")  # or a file path
db = await get_db()
```

### Storage backend boundary

The default backend is SQLite (via `aiosqlite`). Since Sprint 10, PostgreSQL
sits behind the same `VoodooDatabase` protocol — the data layer detects the
backend and adapts the small dialect differences (identity columns vs
`AUTOINCREMENT`, `RETURNING id` vs `lastrowid`, `%s` vs `?` placeholders).
The facade stays the same:

```python
# voodoo.yaml
database:
  provider: postgres
  url: postgresql://user:pass@localhost:5432/voodoo

# or environment
#   VOODOO_DATABASE_PROVIDER=postgres
#   VOODOO_DATABASE_URL=postgresql://user:pass@localhost:5432/voodoo
```

The `postgres` provider requires the optional extra:

```bash
pip install "voodoo-framework[postgres]"   # psycopg[binary]
```

**Pooling** (spec §4 / §49): the current adapter keeps one async `psycopg`
connection per process, mirroring the SQLite adapter's single connection —
introspection, migrations, and per-request queries share it, and the
`transaction()` context gives atomic commit/rollback. A `psycopg_pool`
`AsyncConnectionPool` (per-backend proxy) is the documented future option for
multi-worker deployments; it is deliberately not introduced in Sprint 10 to
keep the protocol and the in-process default stable. JSONB payload columns
(spec §50) stay `TEXT` for parity with SQLite — the queue, event bus, and
execution store (Sprint 11) reuse the same shared translated migrations, so
PostgreSQL uses TEXT columns just like SQLite (JSONB / TIMESTAMPTZ remain a
future sprint).

The full provider contract (write/read roundtrip, migration ledger,
idempotent migrations, transaction commit/rollback, reconnect durability)
is enforced by `DatabaseContractTests` — run against SQLite always, and
against a real PostgreSQL server in CI via a service container (or locally
with `VOODOO_TEST_DATABASE_URL` set). The queue, event bus, and execution
store each have their own PostgreSQL contract + failure-path suites
(`tests/contracts/test_queue_postgres.py`, `test_eventbus_postgres.py`,
`test_execution_postgres.py`) that run against the same service container.

## Memory (Sprint 16)

Entities need durable, queryable memory — not just one-shot state. The memory
system gives every entity layered recall: **working** (current context),
**episodic** (what happened during an execution), **durable** (long-term facts),
and **semantic** (searchable knowledge). The default backend is SQLite with FTS5
for full-text search — no external dependencies.

### Minimal example

```python
from voodoo import SQLiteMemoryStore, MemoryEntry, MemoryLayer

store = SQLiteMemoryStore("memory.db")

# Write a memory
entry = MemoryEntry(
    entity_id="user:42",
    layer=MemoryLayer.EPISODIC,
    content="User asked about pricing for the enterprise plan",
    tags=["pricing", "enterprise"],
    importance=0.8,
)
await store.write(entry)

# Search memories
results = await store.search("pricing", entity_id="user:42")
for result in results:
    print(result.entry.content, result.score)

# Read a specific memory
entry = await store.read(entry_id=results[0].entry.id)

# List all memories for an entity
entries = await store.list_entries(
    entity_id="user:42",
    layer=MemoryLayer.EPISODIC,
    limit=10,
)
```

### Memory layers

| Layer | Purpose | Typical source |
|---|---|---|
| `WORKING` | Current session context, short-lived | Manual write |
| `EPISODIC` | What happened during an execution | Auto-written by Agent |
| `DURABLE` | Long-term facts that survive sessions | Manual write |
| `SEMANTIC` | Searchable knowledge, tags + full-text | Manual or derived |

### In-memory store

For tests or ephemeral workloads, use `InMemoryMemoryStore` — same protocol,
runs entirely in RAM:

```python
from voodoo.memory import InMemoryMemoryStore

store = InMemoryMemoryStore()
```

### SQLite memory store

`SQLiteMemoryStore` persists to a SQLite file with WAL mode and FTS5
full-text search. When FTS5 is unavailable, it falls back to `LIKE` queries.

```python
from voodoo import SQLiteMemoryStore

store = SQLiteMemoryStore("data/memory.db")

# Count entries
n = await store.count(entity_id="user:42", layer=MemoryLayer.EPISODIC)

# Delete a memory
await store.delete(entry_id=some_id)
```

### MemoryEntry fields

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique ID (auto-generated UUID) |
| `entity_id` | `str` | Owner entity (e.g. `"user:42"`, `"agent:lead-scorer"`) |
| `layer` | `MemoryLayer` | Working / Episodic / Durable / Semantic |
| `content` | `str` | The memory content text |
| `metadata` | `dict` | Arbitrary key-value metadata |
| `tags` | `list[str]` | Searchable tags |
| `importance` | `float` | 0.0–1.0 importance score |
| `source_execution_id` | `str \| None` | Link to the execution that produced this memory |
| `created_at` | `str` | ISO timestamp |
| `updated_at` | `str` | ISO timestamp |
| `expires_at` | `str \| None` | Optional expiration (for working memory) |

## API reference

- `Model` — async CRUD facade over `BaseModel`.
  - `Model.create(**kwargs)` — insert and return.
  - `Model.get(id)` — fetch by PK.
  - `Model.all(user_context=None)` — fetch all rows.
  - `model.save()` — insert or update.
  - `model.delete()` — delete row (fires FK cascades first).
- **Fluent queries** — `Model.where(**filters)` returns a lazy, chainable
  `Query`; nothing hits the database until awaited or a terminal runs:
  - `await Model.where(status="new")` — matching rows as instances.
  - `.order_by("-updated_at")` — order (prefix `-` for descending).
  - `.limit(n)` / `.offset(n)` — paging.
  - `.first()` — first match or `None`; `.count()` — row count.
  - `.delete()` — delete matching rows (returns count; requires filters).
  - Shortcuts: `Model.count(**f)`, `Model.first(**f)`, `Model.delete_where(**f)`.
- **Foreign keys with cascade** — annotate a column as `FK[ParentModel]`
  (stored as `INTEGER`); deleting the parent removes referencing children:

  ```python
  from voodoo.data import FK, Model


  class Conversation(Model):
      title: str


  class ChatMessage(Model):
      conversation_id: FK[Conversation]
      content: str


  await conversation.delete()  # also deletes its ChatMessages
  ```

- `BaseModel` — base ORM class.
- `FK` — foreign-key annotation with cascade delete.
- `Query` — the lazy query builder behind `Model.where()`.
- `init_db(db_path=None)` — initialize the database.
- `get_db()` — get the database connection.
- `on_insert(model_cls)` / `on_update(model_cls)` — lifecycle hook decorators.
- `rls_policy(model_cls)` — RLS policy decorator.
