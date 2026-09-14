"""Voodoo data layer.

``Model`` is Store-first: fresh applications persist durable model records in
``application.vstore``. SQLite/PostgreSQL remain explicit SQL adapters through
``init_db`` and provider configuration. ``BaseModel`` is kept as the legacy SQL
compatibility surface while the public ``Model`` facade converges on Store.
"""

from voodoo.data.base import (
    FK,
    BaseModel,
    ModelMeta,
    _get_table_name,
    close_db,
    get_db,
    init_db,
    on_insert,
    on_update,
    rls_policy,
)
from voodoo.data.store_facade import Model

__all__ = [
    "BaseModel",
    "Model",
    "ModelMeta",
    "FK",
    "close_db",
    "get_db",
    "init_db",
    "on_insert",
    "on_update",
    "rls_policy",
    "_db_connection",
    "_get_table_name",
    "_models",
    "_rls_policies",
    "_triggers",
]

_FORWARDED_GLOBALS = frozenset(
    {"_db_connection", "_models", "_triggers", "_rls_policies"}
)


def __getattr__(name: str):
    if name in _FORWARDED_GLOBALS:
        from voodoo.data import base

        return getattr(base, name)
    raise AttributeError(f"module 'voodoo.data' has no attribute {name!r}")
