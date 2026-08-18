import asyncio
from collections.abc import Callable
from typing import Any, get_type_hints

from voodoo.storage.database import Migration, SQLiteDatabase, VoodooDatabase

_db_connection = None
_database: SQLiteDatabase | None = None
_triggers: dict[str, dict[str, list[Callable]]] = {}
_rls_policies: dict[str, Callable] = {}


async def _ensure_user_tables(db: VoodooDatabase) -> None:
    """Create tables for every registered user model (idempotent DDL)."""
    for model in _models:
        await model._create_table()


# Migration 0001: the user-model baseline. Runs once to enter the ledger,
# then re-runs its idempotent DDL on every ``init_db`` so models imported
# after the baseline still get their tables (preserves pre-migration
# behavior exactly).
USER_MODEL_BASELINE = Migration(
    version=1,
    name="user_model_baseline",
    fn=_ensure_user_tables,
    rerun=True,
)


async def init_db(db_path: str = None):
    """Initializes the database connection using the configured provider (Sprint 9).

    Uses the central :class:`~voodoo.adapters.registry.ProviderRegistry` to
    resolve the active database adapter from ``config.database``, running
    migrations and ensuring user model tables are created.

    The connection is published as ``_db_connection`` / ``get_db()`` for
    backward compatibility with the rest of the framework (models, hooks,
    queue, …). ``database.migrate()`` runs the USER_MODEL_BASELINE (version
    1, rerun=True) which creates every registered user table — meaning the
    baseline must be registered with the adapter *before* ``migrate()`` is
    called, otherwise ``_create_table`` → ``get_db`` would re-enter
    ``init_db`` (there is no connection yet) and recurse forever.
    """
    from voodoo.adapters.registry import registry
    from voodoo.config import DatabaseConfig, get_config

    cfg = get_config().database
    if db_path:
        cfg = DatabaseConfig(provider="sqlite", path=db_path, url="")

    database = registry.get_database(cfg, migrations=(USER_MODEL_BASELINE,))
    await database.connect()
    # Publish the connection *before* migrating so the rerunnable
    # user-model baseline (and any other migration fn) can resolve the
    # database via ``get_db()`` without recursing.
    global _db_connection, _database
    _database = database
    if hasattr(database, "connection"):
        _db_connection = database.connection
    await database.migrate()
    await _ensure_user_tables(database)
    return database


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
    global _db_connection, _database
    if _db_connection is not None:
        try:
            # Close via the adapter so its internal ``_conn`` is also
            # invalidated; the raw aiosqlite connection is the same object.
            if _database is not None:
                await _database.close()
            else:
                await _db_connection.close()
        finally:
            _db_connection = None
            _database = None


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
