# Voodoo Database

The default Voodoo local data stack is:

- `aiosqlite`
- database file: `.data/voodoo.db`

## Basic Pattern

```python
import aiosqlite


async def get_items():
    async with aiosqlite.connect(".data/voodoo.db") as db:
        async with db.execute("SELECT id, name FROM items ORDER BY id DESC") as cursor:
            return await cursor.fetchall()
```

## Good Defaults

- create `.data/` if it does not exist
- keep SQL straightforward
- move repeated queries into helper functions
- keep database I/O async

## When AI Writes Data Code

- use parameterized queries
- commit writes explicitly
- do not hide all database work behind unnecessary abstractions
