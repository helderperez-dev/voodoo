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

The default backend is SQLite (via `aiosqlite`). Swapping to PostgreSQL requires replacing `init_db`/`get_db` and the DDL in `BaseModel._create_table`. The facade stays the same.

## API reference

- `Model` — async CRUD facade over `BaseModel`.
  - `Model.create(**kwargs)` — insert and return.
  - `Model.get(id)` — fetch by PK.
  - `Model.all(user_context=None)` — fetch all rows.
  - `model.save()` — insert or update.
  - `model.delete()` — delete row.
- `BaseModel` — base ORM class.
- `init_db(db_path=None)` — initialize the database.
- `get_db()` — get the database connection.
- `on_insert(model_cls)` / `on_update(model_cls)` — lifecycle hook decorators.
- `rls_policy(model_cls)` — RLS policy decorator.
