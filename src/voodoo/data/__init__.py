"""Voodoo data layer.

This package re-exports the names that previously lived in the flat
``voodoo/data.py`` module (now ``voodoo/data/base.py``) and adds the
``Model`` facade from ``voodoo/data/model.py``.

Storage backend boundary
-------------------------
The default backend is SQLite (via :mod:`aiosqlite`) managed by the
``VoodooDatabase`` adapter in :mod:`voodoo.storage.database` — it owns
connection lifecycle, WAL pragmas and the ``schema_migrations`` ledger.
``init_db`` publishes the raw aiosqlite connection as
``_db_connection`` / ``get_db()``; everything above it (``BaseModel``,
``Model`` and the hooks) is backend-agnostic.  A future PostgreSQL
adapter replaces the adapter, not this package.
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
from voodoo.data.model import Model

__all__ = [
    # Core
    "BaseModel",
    "Model",
    "ModelMeta",
    "FK",
    # Helpers
    "close_db",
    "get_db",
    "init_db",
    "on_insert",
    "on_update",
    "rls_policy",
    # Internal-ish (kept for tests / back-compat)
    "_db_connection",
    "_get_table_name",
    "_models",
    "_rls_policies",
    "_triggers",
]

# Mutable module-level globals that live in ``base`` and are mutated in place
# (e.g. ``init_db`` reassigns ``_db_connection``).  Attribute *reads* on this
# package forward to ``base`` via the PEP 562 module ``__getattr__`` hook, so
# callers using ``voodoo.data._db_connection`` always see the *live* value.
#
# NOTE: Python has no module-level ``__setattr__`` — assigning
# ``voodoo.data._db_connection = x`` would create a stale shadow global in
# this package's namespace.  Always assign through ``voodoo.data.base``
# (or use ``init_db`` / ``close_db``).
_FORWARDED_GLOBALS = frozenset(
    {"_db_connection", "_models", "_triggers", "_rls_policies"}
)


def __getattr__(name: str):
    if name in _FORWARDED_GLOBALS:
        from voodoo.data import base

        return getattr(base, name)
    raise AttributeError(f"module 'voodoo.data' has no attribute {name!r}")
