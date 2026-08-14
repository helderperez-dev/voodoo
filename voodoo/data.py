import asyncio
import aiosqlite
from typing import Any, Callable, Dict, List, Type, get_type_hints

_db_connection = None
_triggers: Dict[str, Dict[str, List[Callable]]] = {}
_rls_policies: Dict[str, Callable] = {}

import os

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

def on_insert(model_cls: Type):
    def decorator(func: Callable):
        table = model_cls.__name__.lower()
        if table not in _triggers:
            _triggers[table] = {"insert": [], "update": []}
        _triggers[table]["insert"].append(func)
        return func
    return decorator

def on_update(model_cls: Type):
    def decorator(func: Callable):
        table = model_cls.__name__.lower()
        if table not in _triggers:
            _triggers[table] = {"insert": [], "update": []}
        _triggers[table]["update"].append(func)
        return func
    return decorator

def rls_policy(model_cls: Type):
    def decorator(func: Callable):
        table = model_cls.__name__.lower()
        _rls_policies[table] = func
        return func
    return decorator

_models: List[Type] = []

class ModelMeta(type):
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if name != "BaseModel":
            _models.append(cls)

class BaseModel(metaclass=ModelMeta):
    id: int
    
    @classmethod
    async def _create_table(cls):
        db = await get_db()
        table_name = cls.__name__.lower()
        hints = get_type_hints(cls)
        columns = []
        for col_name, col_type in hints.items():
            if col_name == "id":
                columns.append("id INTEGER PRIMARY KEY AUTOINCREMENT")
            elif col_type == int:
                columns.append(f"{col_name} INTEGER")
            elif col_type == str:
                columns.append(f"{col_name} TEXT")
            elif col_type == bool:
                columns.append(f"{col_name} BOOLEAN")
            else:
                columns.append(f"{col_name} TEXT")
                
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)})"
        await db.execute(query)
        await db.commit()

    @classmethod
    async def find_all(cls, user_context: dict = None) -> List['BaseModel']:
        from voodoo.telemetry import telemetry_store
        telemetry_store.record_db_query()
        db = await get_db()
        table_name = cls.__name__.lower()
        query = f"SELECT * FROM {table_name}"
        params = []
        
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
                    if k in hints and hints[k] == bool:
                        val = bool(val)
                    setattr(obj, k, val)
                results.append(obj)
            return results

    async def insert(self):
        from voodoo.telemetry import telemetry_store
        telemetry_store.record_db_query()
        db = await get_db()
        table_name = self.__class__.__name__.lower()
        
        hints = get_type_hints(self.__class__)
        cols = []
        vals = []
        placeholders = []
        
        for col_name in hints.keys():
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
        table_name = self.__class__.__name__.lower()
        
        hints = get_type_hints(self.__class__)
        cols = []
        vals = []
        
        for col_name in hints.keys():
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
