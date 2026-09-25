"""Store-native public data model for Voodoo applications.

The public ``Model`` API is backed directly by Voodoo Store Collections. SQL is
not part of this module's import graph. Optional SQL adapters live under
``voodoo.storage.database`` and are loaded only when explicitly imported.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime
from enum import Enum
from types import UnionType
from typing import Any, get_args, get_origin, get_type_hints
from uuid import UUID

from voodoo.data.store_backend import (
    delete_record,
    get_record,
    insert_record,
    put_record,
    query_records,
    register_indexes,
    scan_records,
    uuid7,
)

__all__ = [
    "BaseModel",
    "Delete",
    "FK",
    "Model",
    "ModelMeta",
    "StoreQuery",
    "_get_table_name",
    "_models",
    "_rls_policies",
    "_triggers",
    "field",
    "relation",
    "validate",
    "validate_model",
    "on_insert",
    "on_update",
    "rls_policy",
]

_models: list[type] = []
_triggers: dict[str, dict[str, list[Callable[..., Any]]]] = {}
_rls_policies: dict[str, Callable[..., Any]] = {}
_relations: dict[str, list[tuple[str, str, Delete]]] = {}


_MISSING = object()


class _FieldSpec:
    """Persistence metadata for one Store-backed model field."""

    __slots__ = ("index", "unique", "default", "default_factory", "name")

    def __init__(
        self,
        *,
        index: bool = False,
        unique: bool = False,
        default: Any = _MISSING,
        default_factory: Callable[[], Any] | None = None,
    ) -> None:
        if default is not _MISSING and default_factory is not None:
            raise TypeError("field() cannot define both default and default_factory")
        self.index = bool(index or unique)
        self.unique = bool(unique)
        self.default = default
        self.default_factory = default_factory
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        del owner
        self.name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self.name is None or self.name not in instance.__dict__:
            raise AttributeError(self.name or "unbound field")
        return instance.__dict__[self.name]

    def __set__(self, instance: Any, value: Any) -> None:
        if self.name is None:
            raise AttributeError("field is not bound to a model")
        instance.__dict__[self.name] = value


def field(
    *,
    index: bool = False,
    unique: bool = False,
    default: Any = _MISSING,
    default_factory: Callable[[], Any] | None = None,
) -> Any:
    """Declare Store persistence metadata without redefining Python typing."""
    return _FieldSpec(
        index=index,
        unique=unique,
        default=default,
        default_factory=default_factory,
    )


class Delete(str, Enum):
    RESTRICT = "restrict"
    CASCADE = "cascade"
    SET_NULL = "set_null"


class _RelationSpec:
    __slots__ = ("target", "on_delete", "name")

    def __init__(
        self,
        target: type | None = None,
        *,
        on_delete: Delete = Delete.RESTRICT,
    ) -> None:
        self.target = target
        self.on_delete = Delete(on_delete)
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        del owner
        self.name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self.name is None or self.name not in instance.__dict__:
            raise AttributeError(self.name or "unbound relation")
        return instance.__dict__[self.name]

    def __set__(self, instance: Any, value: Any) -> None:
        if self.name is None:
            raise AttributeError("relation is not bound to a model")
        if isinstance(value, BaseModel):
            if not getattr(value, "id", None):
                raise ValueError("related model must be persisted before assignment")
            value = value.id
        instance.__dict__[self.name] = value


def relation(
    target: type | None = None,
    *,
    on_delete: Delete = Delete.RESTRICT,
) -> Any:
    """Declare an explicit model relationship.

    The stored value is the target model UUID. Referential actions are enforced
    by the Runtime Model layer rather than encoded as generic field metadata.
    """
    return _RelationSpec(target, on_delete=on_delete)


def validate(*fields: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a method as a field validator for one or more fields."""
    if not fields:
        raise TypeError("validate() requires at least one field name")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "__voodoo_validate_fields__", tuple(fields))
        return func

    return decorator


def validate_model(func: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a method as a whole-model invariant validator."""
    setattr(func, "__voodoo_validate_model__", True)
    return func


class _FKRef:
    __slots__ = ("target",)

    def __init__(self, target: type) -> None:
        self.target = target


class FK:
    """Field annotation declaring a Store-native cascade relationship."""

    def __class_getitem__(cls, target: type) -> _FKRef:
        if not isinstance(target, type):
            raise TypeError("FK[...] requires a model class")
        return _FKRef(target)


def _get_table_name(cls_or_obj: Any) -> str:
    cls = cls_or_obj if isinstance(cls_or_obj, type) else cls_or_obj.__class__
    name = getattr(cls, "__tablename__", None)
    return str(name) if name else cls.__name__.lower()


def _relation_target(annotation: Any) -> type | None:
    if isinstance(annotation, type):
        return annotation
    origin = get_origin(annotation)
    if origin is UnionType or str(origin) == "typing.Union":
        candidates = [
            item for item in get_args(annotation)
            if item is not type(None) and isinstance(item, type)
        ]
        if len(candidates) == 1:
            return candidates[0]
    return None


def _register_relations(cls: type) -> None:
    child = _get_table_name(cls)
    try:
        hints = get_type_hints(cls)
    except Exception:
        hints = getattr(cls, "__annotations__", {})
    for name, spec in vars(cls).items():
        if not isinstance(spec, _RelationSpec):
            continue
        target = spec.target or _relation_target(hints.get(name))
        if target is None:
            raise TypeError(
                f"relation field {cls.__name__}.{name} requires a model annotation "
                "or an explicit target"
            )
        spec.target = target
        parent = _get_table_name(target)
        _relations.setdefault(parent, []).append((child, name, spec.on_delete))


def _clear_cascades() -> None:
    _relations.clear()


def _allows_none(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is UnionType or str(origin) == "typing.Union":
        return type(None) in get_args(annotation)
    return False


def _field_specs(model: type) -> dict[str, _FieldSpec]:
    return {
        name: value
        for name, value in vars(model).items()
        if isinstance(value, _FieldSpec)
    }


def _apply_defaults(model: type, values: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(values)
    hints = get_type_hints(model)
    specs = _field_specs(model)
    for name, annotation in hints.items():
        if name.startswith("__") or name == "id" or name in resolved:
            continue
        spec = specs.get(name)
        if spec is not None:
            if spec.default_factory is not None:
                resolved[name] = spec.default_factory()
                continue
            if spec.default is not _MISSING:
                resolved[name] = spec.default
                continue
        class_value = getattr(model, name, _MISSING)
        if class_value is not _MISSING and not isinstance(
            class_value, (_FieldSpec, _RelationSpec)
        ):
            resolved[name] = class_value
            continue
        if _allows_none(annotation):
            resolved[name] = None
            continue
        raise TypeError(f"Missing required field: {name}")
    return resolved


def _prepare_instance(obj: Any) -> None:
    values = _apply_defaults(obj.__class__, _model_values(obj))
    for name, value in values.items():
        if not hasattr(obj, name):
            setattr(obj, name, value)


def _run_validators(obj: Any) -> None:
    hints = get_type_hints(obj.__class__)
    for name, annotation in hints.items():
        if name.startswith("__") or name == "id":
            continue
        if not hasattr(obj, name):
            if _allows_none(annotation):
                continue
            raise TypeError(f"Missing required field: {name}")
        value = getattr(obj, name)
        if value is None and not _allows_none(annotation):
            raise TypeError(f"{name} cannot be None")

    for name in dir(obj.__class__):
        member = getattr(obj.__class__, name, None)
        fields = getattr(member, "__voodoo_validate_fields__", ())
        if fields:
            bound = getattr(obj, name)
            for field_name in fields:
                value = getattr(obj, field_name)
                result = bound(value)
                if result is not None:
                    setattr(obj, field_name, result)
        if getattr(member, "__voodoo_validate_model__", False):
            result = getattr(obj, name)()
            if result is False:
                raise ValueError(f"Model validation failed: {name}")


class ModelMeta(type):
    def __init__(
        cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]
    ) -> None:
        super().__init__(name, bases, attrs)
        if name not in ("BaseModel", "Model"):
            _models.append(cls)
            _register_relations(cls)
            indexes = {
                field_name: spec.unique
                for field_name, spec in vars(cls).items()
                if isinstance(spec, _FieldSpec) and spec.index
            }
            register_indexes(_get_table_name(cls), indexes)


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
        if not hasattr(obj, name):
            continue
        value = getattr(obj, name)
        spec = vars(obj.__class__).get(name)
        if isinstance(spec, _RelationSpec) and isinstance(value, BaseModel):
            value = value.id
        values[name] = value
    return values


def _hydrate(model: type[Any], row: dict[str, Any]) -> Any:
    obj = model()
    try:
        hints = get_type_hints(model)
    except Exception:
        hints = getattr(model, "__annotations__", {})
    for key, value in row.items():
        annotation = hints.get(key)
        if annotation is bool:
            value = bool(value)
        elif annotation is UUID and value is not None and not isinstance(value, UUID):
            value = UUID(str(value))
        elif annotation is datetime and value is not None and not isinstance(value, datetime):
            value = datetime.fromisoformat(str(value))
        elif annotation is date and value is not None and not isinstance(value, date):
            value = date.fromisoformat(str(value))
        relation_spec = vars(model).get(key)
        if isinstance(relation_spec, _RelationSpec) and value is not None:
            target = relation_spec.target
            if target is None:
                raise TypeError(f"Unresolved relation target for {model.__name__}.{key}")
            related_row = get_record(_get_table_name(target), UUID(str(value)))
            value = None if related_row is None else _hydrate(target, related_row)
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

    id: UUID
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
        if not getattr(self, "id", None):
            self.id = uuid7()
        _prepare_instance(self)
        _run_validators(self)
        self.id = insert_record(table, _model_values(self), record_id=self.id)
        _fire_hooks(table, "insert", self)
        return self

    async def update(self) -> BaseModel:
        if not getattr(self, "id", None):
            raise ValueError("Cannot update a model without an id")
        table = _get_table_name(self)
        _prepare_instance(self)
        _run_validators(self)
        put_record(table, self.id, _model_values(self))
        _fire_hooks(table, "update", self)
        return self


class Model(BaseModel):
    """Async CRUD facade backed exclusively by Voodoo Store."""

    @classmethod
    async def create(cls, **kwargs: Any) -> Model:
        obj = cls()
        values = _apply_defaults(cls, kwargs)
        for key, value in values.items():
            setattr(obj, key, value)
        await obj.insert()
        return obj

    @classmethod
    async def get(cls, id: UUID | str) -> Model | None:
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
        for child_table, relation_name, action in _relations.get(table, []):
            for child in scan_records(child_table):
                child_value = child.get(relation_name)
                if child_value is None or UUID(str(child_value)) != self.id:
                    continue
                child_id = UUID(str(child["id"]))
                if action is Delete.RESTRICT:
                    raise ValueError(
                        f"Cannot delete {table}: related {child_table}.{relation_name} exists"
                    )
                if action is Delete.CASCADE:
                    delete_record(child_table, child_id)
                elif action is Delete.SET_NULL:
                    child[relation_name] = None
                    put_record(
                        child_table,
                        child_id,
                        {k: v for k, v in child.items() if k != "id"},
                    )
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
        return query_records(
            _get_table_name(self._model),
            filters=self._filters,
            order_by=self._order_by,
            limit=self._limit,
            offset=self._offset,
        )

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
            delete_record(collection, UUID(str(row["id"])))
        return len(rows)

    async def _execute(self) -> list[Model]:
        return [_hydrate(self._model, row) for row in self._rows()]

    def __await__(self):
        return self._execute().__await__()
