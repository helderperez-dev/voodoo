"""Store-first public Model facade with explicit SQL compatibility fallback."""

from __future__ import annotations

from typing import Any

from voodoo.data.base import _get_table_name
from voodoo.data.model import Model as SQLModel
from voodoo.data.store_backend import (
    delete_record,
    get_record,
    scan_records,
    should_use_store,
)
from voodoo.data.store_model import StoreModelMixin, _hydrate


class Model(StoreModelMixin, SQLModel):
    """Public Store-first model API.

    Fresh applications persist through Voodoo Store. Calling ``init_db()`` or
    explicitly selecting a SQL provider preserves the legacy SQL adapter path.
    """

    @classmethod
    async def create(cls, **kwargs: Any) -> Model:
        if not should_use_store():
            return await super().create(**kwargs)
        obj = cls()
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await obj.insert()
        return obj

    @classmethod
    async def get(cls, id: int) -> Model | None:
        if not should_use_store():
            return await super().get(id)
        row = get_record(_get_table_name(cls), id)
        return None if row is None else _hydrate(cls, row)

    @classmethod
    def where(cls, **filters: Any) -> StoreQuery | Any:
        if not should_use_store():
            return super().where(**filters)
        return StoreQuery(cls, filters)

    @classmethod
    async def count(cls, **filters: Any) -> int:
        return await cls.where(**filters).count()

    @classmethod
    async def first(cls, **filters: Any) -> Model | None:
        return await cls.where(**filters).order_by("id").first()

    @classmethod
    async def delete_where(cls, **filters: Any) -> int:
        return await cls.where(**filters).delete()

    async def delete(self) -> None:
        if not should_use_store():
            await super().delete()
            return
        await self._store_delete()


class StoreQuery:
    """Lazy Store query preserving the existing ``Model.where`` ergonomics."""

    def __init__(self, model: type[Model], filters: dict[str, Any]) -> None:
        self._model = model
        self._filters = dict(filters)
        self._order_by: list[str] = []
        self._limit: int | None = None
        self._offset: int | None = None

    def _clone(self) -> StoreQuery:
        query = StoreQuery(self._model, self._filters)
        query._order_by = list(self._order_by)
        query._limit = self._limit
        query._offset = self._offset
        return query

    def where(self, **filters: Any) -> StoreQuery:
        query = self._clone()
        query._filters.update(filters)
        return query

    def order_by(self, *columns: str) -> StoreQuery:
        query = self._clone()
        query._order_by.extend(columns)
        return query

    def limit(self, n: int) -> StoreQuery:
        query = self._clone()
        query._limit = n
        return query

    def offset(self, n: int) -> StoreQuery:
        query = self._clone()
        query._offset = n
        return query

    def _rows(self) -> list[dict[str, Any]]:
        rows = scan_records(_get_table_name(self._model))
        for key, expected in self._filters.items():
            rows = [row for row in rows if row.get(key) == expected]
        for column in reversed(self._order_by):
            descending = column.startswith("-")
            name = column[1:] if descending else column
            rows.sort(key=lambda row: row.get(name), reverse=descending)
        if self._offset is not None:
            rows = rows[self._offset :]
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    async def first(self) -> Model | None:
        rows = self.limit(1)._rows()
        return None if not rows else _hydrate(self._model, rows[0])

    async def count(self) -> int:
        return len(self._rows())

    async def delete(self) -> int:
        if not self._filters:
            raise ValueError(
                "delete() requires at least one filter; use explicit where(...) before delete()."
            )
        rows = self._rows()
        collection = _get_table_name(self._model)
        for row in rows:
            delete_record(collection, int(row["id"]))
        return len(rows)

    async def _execute(self) -> list[Model]:
        return [_hydrate(self._model, row) for row in self._rows()]

    def __await__(self):
        return self._execute().__await__()
