# Model API

## Identity

Voodoo Models use UUIDv7 as technical identity.

Keep business identifiers separate:

```python
class Invoice(Model):
    number: int = field(unique=True)
```

Do not use the UUID timestamp as domain `created_at`. Model creation time explicitly when needed.

## Optionality

Use Python typing:

```python
name: str
nickname: str | None
```

Do not duplicate this as `nullable=True/False`.

## Persistence metadata

Keep `field()` narrow:

```python
email: str = field(unique=True)
score: int = field(index=True)
active: bool = field(default=True)
created_at: datetime = field(default_factory=utcnow)
```

Do not add generic `db_type`, `VARCHAR`, `length`, `nullable`, `cascade`, or validator bags to `field()`.

## Validation

Use `typing.Annotated` constraints for simple constraints supported by the current API.
Use `@validate(...)` for field validation/normalization.
Use `@validate_model` for cross-field invariants.

Validation may be async where the current public API supports it.

## Relations

Prefer typed relations:

```python
from voodoo.data import Delete, relation

class Order(Model):
    customer: Customer = relation(on_delete=Delete.RESTRICT)
```

Deletion policies are explicit:

- `RESTRICT`
- `CASCADE`
- `SET_NULL`

`SET_NULL` requires an optional relation.
