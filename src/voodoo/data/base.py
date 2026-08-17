import asyncio
import os
from collections.abc import Callable
from typing import Any, get_type_hints

import aiosqlite

_db_connection = None
_triggers: dict[str, dict[str, list[Callable]]] = {}
_rls_policies: dict[str, Callable] = {}


async def init_db(db_path: str = None):
    if db_path is None:
        from voodoo.config import config

        db_path = config.db_path

    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    global _db_connection
    _db_connection = await aiosqlite.connect(db_path)
    _db_connection.row_factory = aiosqlite.Row
    for model in _models:
        await model._create_table()


async def get_db():
    if _db_connection is None:
        await init_db()
    return _db_connection


async def close_db():
    """Close the database connection if one is open.

    aiosqlite runs each connection on a dedicated non-daemon thread; an
    unclosed connection would keep the interpreter alive at shutdown.
    No-op when no connection is open (keeps startup lazy).
    """
    global _db_connection
    if _db_connection is not None:
        try:
            await _db_connection.close()
        finally:
            _db_connection = None


def _get_table_name(cls_or_obj: Any) -> str:
    cls = cls_or_obj if isinstance(cls_or_obj, type) else cls_or_obj.__class__
    if hasattr(cls, "__tablename__") and cls.__tablename__:
        return str(cls.__tablename__)
    return cls.__name__.lower()


def on_insert(model_cls: type):
    def decorator(func: Callable):
        table = _get_table_name(model_cls)
        if table not in _triggers:
            _triggers[table] = {"insert": [], "update": []}
        _triggers[table]["insert"].append(func)
        return func

    return decorator


def on_update(model_cls: type):
    def decorator(func: Callable):
        table = _get_table_name(model_cls)
        if table not in _triggers:
            _triggers[table] = {"insert": [], "update": []}
        _triggers[table]["update"].append(func)
        return func

    return decorator


def rls_policy(model_cls: type):
    def decorator(func: Callable):
        table = _get_table_name(model_cls)
        _rls_policies[table] = func
        return func

    return decorator


_models: list[type] = []


class ModelMeta(type):
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        # BaseModel and the Model facade are abstract; concrete models
        # (subclasses of either) register themselves for table creation.
        if name not in ("BaseModel", "Model"):
            _models.append(cls)


class BaseModel(metaclass=ModelMeta):
    id: int
    __tablename__: str | None = None

    @classmethod
    async def _create_table(cls):
        db = await get_db()
        table_name = _get_table_name(cls)
        hints = get_type_hints(cls)
        columns = []
        for col_name, col_type in hints.items():
            if col_name.startswith("__"):
                continue
            if col_name == "id":
                columns.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
            elif col_type is int:
                columns.append(f"{col_name} INTEGER")
            elif col_type is str:
                columns.append(f"{col_name} TEXT")
            elif col_type is bool:
                columns.append(f"{col_name} BOOLEAN")
            else:
                columns.append(f"{col_name} TEXT")

        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)})"
        await db.execute(query)
        await db.commit()

    @classmethod
    async def find_all(cls, user_context: dict = None) -> list["BaseModel"]:
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        db = await get_db()
        table_name = _get_table_name(cls)
        query = f"SELECT * FROM {table_name}"
        params = []

        if user_context is None:
            try:
                from voodoo.auth import current_user

                u = current_user.get()
                if u and u.is_authenticated:
                    user_context = u.to_dict()
            except Exception:
                pass

        if table_name in _rls_policies and user_context:
            policy = _rls_policies[table_name]
            where_clause = policy(user_context)
            if where_clause:
                query += f" WHERE {where_clause}"

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            results = []
            hints = get_type_hints(cls)
            for row in rows:
                obj = cls()
                for k in row.keys():
                    val = row[k]
                    if k in hints and hints[k] is bool:
                        val = bool(val)
                    setattr(obj, k, val)
                results.append(obj)
            return results

    async def insert(self):
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        db = await get_db()
        table_name = _get_table_name(self)

        hints = get_type_hints(self.__class__)
        cols = []
        vals = []
        placeholders = []

        for col_name in hints.keys():
            if col_name.startswith("__"):
                continue
            if col_name == "id" and not hasattr(self, "id"):
                continue
            if hasattr(self, col_name):
                cols.append(col_name)
                vals.append(getattr(self, col_name))
                placeholders.append("?")

        query = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
        cursor = await db.execute(query, vals)
        await db.commit()

        self.id = cursor.lastrowid

        # Trigger hooks
        if table_name in _triggers and _triggers[table_name]["insert"]:
            for hook in _triggers[table_name]["insert"]:
                if asyncio.iscoroutinefunction(hook):
                    asyncio.create_task(hook(self))
                else:
                    hook(self)
        return self

    async def update(self):
        from voodoo.telemetry import telemetry_store

        telemetry_store.record_db_query()
        db = await get_db()
        table_name = _get_table_name(self)

        hints = get_type_hints(self.__class__)
        cols = []
        vals = []

        for col_name in hints.keys():
            if col_name.startswith("__"):
                continue
            if col_name != "id" and hasattr(self, col_name):
                cols.append(f"{col_name} = ?")
                vals.append(getattr(self, col_name))

        vals.append(self.id)
        query = f"UPDATE {table_name} SET {', '.join(cols)} WHERE id = ?"
        await db.execute(query, vals)
        await db.commit()

        # Trigger hooks
        if table_name in _triggers and _triggers[table_name]["update"]:
            for hook in _triggers[table_name]["update"]:
                if asyncio.iscoroutinefunction(hook):
                    asyncio.create_task(hook(self))
                else:
                    hook(self)
        return self
