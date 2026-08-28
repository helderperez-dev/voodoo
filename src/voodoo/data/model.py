"""Model facade — async CRUD and fluent queries on top of :class:`BaseModel`.

``Model`` adds a small, ergonomic async CRUD API (``create``, ``get``,
``all``, ``save``, ``delete``) plus a lazy, chainable query builder
(``where``/``order_by``/``limit``/``offset`` → ``await``/``first``/
``count``/``delete``), while reusing the existing aiosqlite storage layer
and the ``on_insert`` / ``on_update`` hook system from
:mod:`voodoo.data.base`.

Storage backend boundary
-------------------------
Everything in this module talks to the database through ``get_db()``
and builds portable ANSI-SQL strings.  Schema management flows through
the ``VoodooDatabase`` adapter in :mod:`voodoo.storage.database`
(SQLite default); the user-model DDL is migration 0001 in its ledger.
Swapping backends means providing another adapter — no call-site here
changes.
"""

from __future__ import annotations

from typing import Any, get_type_hints

from voodoo.data.base import BaseModel, _get_table_name, get_db

__all__ = ["Model", "Query"]


class Model(BaseModel):
    """Async CRUD facade over :class:`voodoo.data.BaseModel`.

    Subclass it just like ``BaseModel`` and use the async helpers::

        class Lead(Model):
            name: str
            email: str

        lead = await Lead.create(name="Ada", email="ada@x.io")
        lead = await Lead.get(lead.id)
        leads = await Lead.all()
        lead.email = "ada@y.io"
        await lead.save()
        await lead.delete()

    Fluent querying (evaluated only when awaited)::

        leads = await Lead.where(email="ada@x.io")
        top = await Lead.where(status="new").order_by("-created_at").limit(10)
        one = await Lead.where(email="ada@x.io").first()
        n = await Lead.where(status="new").count()
        await Lead.delete_where(status="stale")
    """

    # ------------------------------------------------------------------
    # Class-level CRUD
    # ------------------------------------------------------------------

    @classmethod
    async def create(cls, **kwargs: Any) -> Model:
        """Instantiate, insert, and return the new row as a model instance."""
        obj = cls()
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await obj.insert()
        return obj

    @classmethod
    async def get(cls, id: int) -> Model | None:
        """Fetch a single row by primary key; ``None`` if not found."""
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        db = await get_db()
        table_name = _get_table_name(cls)
        query = f"SELECT * FROM {table_name} WHERE id = ?"
        async with db.execute(query, (id,)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        obj = cls()
        hints = get_type_hints(cls)
        for key in row.keys():
            val = row[key]
            if key in hints and hints[key] is bool:
                val = bool(val)
            setattr(obj, key, val)
        return obj

    @classmethod
    async def all(cls, user_context: dict | None = None) -> list[Model]:
        """Return every row as model instances (alias of ``find_all``)."""
        return await cls.find_all(user_context=user_context)

    # ------------------------------------------------------------------
    # Fluent query API
    # ------------------------------------------------------------------

    @classmethod
    def where(cls, **filters: Any) -> Query:
        """Start a fluent query filtered by equality on the given columns.

        The query is lazy — nothing hits the database until it is awaited
        (returns the matched rows) or a terminal method (``first``,
        ``count``, ``delete``) is awaited.
        """
        return Query(cls, filters)

    @classmethod
    async def count(cls, **filters: Any) -> int:
        """Count rows, optionally filtered by equality on the given columns."""
        return await Query(cls, filters).count()

    @classmethod
    async def first(cls, **filters: Any) -> Model | None:
        """Return the first matching row (ordered by ``id``), or ``None``."""
        return await Query(cls, filters).order_by("id").first()

    @classmethod
    async def delete_where(cls, **filters: Any) -> int:
        """Delete rows matching all equality filters; return rows deleted."""
        return await Query(cls, filters).delete()

    # ------------------------------------------------------------------
    # Instance-level CRUD
    # ------------------------------------------------------------------

    async def save(self) -> Model:
        """Insert if the instance has no ``id`` yet, otherwise update."""
        if not getattr(self, "id", None):
            await self.insert()
        else:
            await self.update()
        return self

    async def delete(self) -> None:
        """Delete the row represented by this instance.

        Registered ``FK`` cascades fire first: child rows referencing this
        row are removed before the row itself.
        """
        from voodoo.data.base import _cascade_delete_children
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        db = await get_db()
        table_name = _get_table_name(self)
        await _cascade_delete_children(table_name, self.id)
        await db.execute(f"DELETE FROM {table_name} WHERE id = ?", (self.id,))
        await db.commit()


class Query:
    """Lazy, chainable query builder for :class:`Model` subclasses.

    Built from ``Model.where(**filters)``; refines with ``order_by`` /
    ``limit`` / ``offset``; terminates with ``await`` (rows), ``first()``,
    ``count()``, or ``delete()``. SQL is portable ANSI (``?`` placeholders)
    and flows through the same adapter-managed connection as the rest of
    the data layer.
    """

    def __init__(self, model: type[Model], filters: dict[str, Any]) -> None:
        self._model = model
        self._filters = dict(filters)
        self._order_by: list[str] = []
        self._limit: int | None = None
        self._offset: int | None = None

    # -- chaining ----------------------------------------------------------

    def where(self, **filters: Any) -> Query:
        """Add equality filters (AND-ed); returns a new Query."""
        clone = self._clone()
        clone._filters.update(filters)
        return clone

    def order_by(self, *columns: str) -> Query:
        """Order results by columns; prefix ``-`` for descending (e.g. ``-id``)."""
        clone = self._clone()
        clone._order_by.extend(columns)
        return clone

    def limit(self, n: int) -> Query:
        """Cap the number of rows returned."""
        clone = self._clone()
        clone._limit = n
        return clone

    def offset(self, n: int) -> Query:
        """Skip ``n`` rows (for pagination; pair with ``limit``)."""
        clone = self._clone()
        clone._offset = n
        return clone

    def _clone(self) -> Query:
        q = Query(self._model, self._filters)
        q._order_by = list(self._order_by)
        q._limit = self._limit
        q._offset = self._offset
        return q

    # -- SQL assembly -------------------------------------------------------

    def _where_clause(self) -> tuple[str, list[Any]]:
        if not self._filters:
            return "", []
        clauses = " AND ".join(f"{col} = ?" for col in self._filters)
        return f" WHERE {clauses}", list(self._filters.values())

    def _order_clause(self) -> str:
        if not self._order_by:
            return ""
        parts = []
        for col in self._order_by:
            if col.startswith("-"):
                parts.append(f"{col[1:]} DESC")
            else:
                parts.append(col)
        return f" ORDER BY {', '.join(parts)}"

    # -- terminals (async) --------------------------------------------------

    def _execute_select(self) -> Any:
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        table_name = _get_table_name(self._model)
        where, params = self._where_clause()
        query = f"SELECT * FROM {table_name}{where}{self._order_clause()}"
        if self._limit is not None:
            query += f" LIMIT {int(self._limit)}"
            if self._offset is not None:
                query += f" OFFSET {int(self._offset)}"
        elif self._offset is not None:
            # ANSI portability: OFFSET without LIMIT (SQLite requires LIMIT
            # before OFFSET; Postgres allows bare OFFSET).
            query += f" LIMIT -1 OFFSET {int(self._offset)}"
        return _fetch_models(self._model, query, params)

    async def first(self) -> Model | None:
        """Return the first matching row, or ``None`` when no match."""
        rows = await self.limit(1)._execute_select()
        return rows[0] if rows else None

    async def count(self) -> int:
        """Return the number of rows matching the filters."""
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        db = await get_db()
        table_name = _get_table_name(self._model)
        where, params = self._where_clause()
        query = f"SELECT COUNT(*) FROM {table_name}{where}"
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
        return int(row[0] if isinstance(row, (tuple, list)) else row[0])

    async def delete(self) -> int:
        """Delete matching rows; return the number of rows removed."""
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        db = await get_db()
        table_name = _get_table_name(self._model)
        where, params = self._where_clause()
        if not where:
            # Guard: refuse unconditional DELETE without explicit filters —
            # callers must opt in via where() (defensive default).
            raise ValueError(
                "delete() requires at least one filter; use explicit "
                "where(...) before delete()."
            )
        query = f"DELETE FROM {table_name}{where}"
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.rowcount

    def __await__(self):
        """``await query`` → the matched rows as model instances."""
        return self._execute_select().__await__()


async def _fetch_models(
    model: type[Model], query: str, params: list[Any]
) -> list[Model]:
    """Run a SELECT and hydrate rows into model instances (bool-coerced)."""
    db = await get_db()
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    hints = get_type_hints(model)
    results: list[Model] = []
    for row in rows:
        obj = model()
        for k in row.keys():
            val = row[k]
            if k in hints and hints[k] is bool:
                val = bool(val)
            setattr(obj, k, val)
        results.append(obj)
    return results
