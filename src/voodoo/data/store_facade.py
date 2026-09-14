"""Store-native public data model for Voodoo applications.

The public ``Model`` API is backed directly by Voodoo Store Collections. SQL is
not part of this module's import graph. Optional SQL adapters live under
``voodoo.storage.database`` and are loaded only when explicitly imported.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, get_type_hints

from voodoo.data.store_backend import (
    delete_record,
    get_record,
    insert_record,
    put_record,
    scan_records,
)

__all__ = [
    "BaseModel",
    "FK",
    "Model",
    "ModelMeta",
    "StoreQuery",
    "_get_table_name",
    "_models",
    "_rls_policies",
    "_triggers",
    "on_insert",
    "on_update",
    "rls_policy",
]

_models: list[type] = []
_triggers: dict[str, dict[str, list[Callable[..., Any]]]] = {}
_rls_policies: dict[str, Callable[..., Any]] = {}
_cascades: dict[str, list[tuple[str, str]]] = {}


class _FKRef:
    __slots__ = ("target",)

    def __init__(self, target: type) -> None:
        self.target = target


class FK:
    """Field annotation declaring a Store-native cascade relationship."""

    def __class_getitem__(cls, target: type) -> _FKRef:  # noqa: N805
        if not isinstance(target, type):
            raise TypeError("FK[...] requires a model class")
        return _FKRef(target)


def _get_table_name(cls_or_obj: Any) -> str:
    cls = cls_or_obj if isinstance(cls_or_obj, type) else cls_or_obj.__class__
    name = getattr(cls, "__tablename__", None)
    return str(name) if name else cls.__name__.lower()


def _register_foreign_keys(cls: type) -> None:
    try:
        hints = get_type_hints(cls)
    except Exception:
        hints = getattr(cls, "__annotations__", {})
    for col_name, col_type in hints.items():
        if isinstance(col_type, _FKRef):
            parent = _get_table_name(col_type.target)
            _cascades.setdefault(parent, []).append((_get_table_name(cls), col_name))


def _clear_cascades() -> None:
    _cascades.clear()


class ModelMeta(type):
    def __init__(
        cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, attrs)
        if name not in ("BaseModel", "Model"):
            _models.append(cls)
            _register_foreign_keys(cls)


def on_insert(model_cls: type) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        table = _get_table_name(model_cls)
        _triggers.setdefault(table, {"insert": [], "update": []})["insert"].append(func)
        return func

    return decorator


def on_update(model_cls: type) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        table = _get_table_name(model_cls)
        _triggers.setdefault(table, {"insert": [], "update": []})["update"].append(func)
        return func

    return decorator


def rls_policy(model_cls: type) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register a Store-native row policy accepting ``(row, context)``."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        _rls_policies[_get_table_name(model_cls)] = func
        return func

    return decorator


def _model_values(obj: Any, *, include_id: bool = False) -> dict[str, Any]:
    values: dict[str, Any] = {}
    try:
        hints = get_type_hints(obj.__class__)
    except Exception:
        hints = getattr(obj.__class__, "__annotations__", {})
    for name in hints:
        if name.startswith("__") or (name == "id" and not include_id):
            continue
        if hasattr(obj, name):
            values[name] = getattr(obj, name)
    return values


def _hydrate(model: type[Any], row: dict[str, Any]) -> Any:
    obj = model()
    try:
        hints = get_type_hints(model)
    except Exception:
        hints = getattr(model, "__annotations__", {})
    for key, value in row.items():
        if hints.get(key) is bool:
            value = bool(value)
        setattr(obj, key, value)
    return obj


def _fire_hooks(table: str, event: str, obj: Any) -> None:
    for hook in _triggers.get(table, {}).get(event, []):
        if asyncio.iscoroutinefunction(hook):
            asyncio.create_task(hook(obj))
        else:
            hook(obj)


def _identity_context() -> dict[str, Any] | None:
    try:
        from voodoo.auth import current_user

        user = current_user.get()
    except Exception:
        return None
    if not user or not user.is_authenticated:
        return None
    return user.to_dict()


class BaseModel(metaclass=ModelMeta):
    """Store-native persistence base.

    ``BaseModel`` remains available as a compatibility spelling, but no longer
    implies SQL. New code should prefer ``Model``.
    """

    id: int
    __tablename__: str | None = None

    @classmethod
    async def _create_table(cls) -> None:
        """Ensure the model collection exists in Voodoo Store.

        The historical method name is retained as a Store-native collection
        initializer; it does not create SQL tables or import a SQL adapter.
        """
        scan_records(_get_table_name(cls))

    @classmethod
    async def find_all(cls, user_context: dict | None = None) -> list[Any]:
        table = _get_table_name(cls)
        context = user_context if user_context is not None else _identity_context()
        rows = scan_records(table)
        if table not in _rls_policies or context is None:
            return [_hydrate(cls, row) for row in rows]

        predicate = _rls_policies[table]
        selected: list[Any] = []
        for row in rows:
            try:
                allowed = predicate(row, context)
            except TypeError:
                raise RuntimeError(
                    "Store-native rls_policy callbacks must accept (row, context) "
                    "and return bool; SQL policy strings are not supported."
                ) from None
            if allowed:
                selected.append(_hydrate(cls, row))
        return selected

    async def insert(self) -> BaseModel:
        table = _get_table_name(self)
        self.id = insert_record(table, _model_values(self))
        _fire_hooks(table, "insert", self)
        return self

    async def update(self) -> BaseModel:
        if not getattr(self, "id", None):
            raise ValueError("Cannot update a model without an id")
        table = _get_table_name(self)
        put_record(table, self.id, _model_values(self))
        _fire_hooks(table, "update", self)
        return self


class Model(BaseModel):
    """Async CRUD facade backed exclusively by Voodoo Store."""

    @classmethod
    async def create(cls, **kwargs: Any) -> Model:
        obj = cls()
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await obj.insert()
        return obj

    @classmethod
    async def get(cls, id: int) -> Model | None:
        row = get_record(_get_table_name(cls), id)
        return None if row is None else _hydrate(cls, row)

    @classmethod
    async def all(cls, user_context: dict | None = None) -> list[Model]:
        return await cls.find_all(user_context=user_context)

    @classmethod
    def where(cls, **filters: Any) -> StoreQuery:
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

    async def save(self) -> Model:
        if getattr(self, "id", None):
            await self.update()
        else:
            await self.insert()
        return self

    async def delete(self) -> None:
        table = _get_table_name(self)
        for child_table, fk_col in _cascades.get(table, []):
            for child in scan_records(child_table):
                if child.get(fk_col) == self.id:
                    delete_record(child_table, int(child["id"]))
        delete_record(table, self.id)


class StoreQuery:
    """Lazy query over one Voodoo Store collection."""

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
