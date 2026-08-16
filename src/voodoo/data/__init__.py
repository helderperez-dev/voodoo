"""Voodoo data layer.

This package re-exports the names that previously lived in the flat
``voodoo/data.py`` module (now ``voodoo/data/base.py``) and adds the
``Model`` facade from ``voodoo/data/model.py``.

Storage backend boundary
-------------------------
The default backend is SQLite (via :mod:`aiosqlite`).  The functions
``init_db`` and ``get_db`` together with the module-level ``_db_connection``
form the seam a future PostgreSQL adapter would replace; everything above
them (``BaseModel``, ``Model`` and the hooks) is backend-agnostic.
"""

from voodoo.data.base import (
    BaseModel,
    ModelMeta,
    _get_table_name,
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
    # Helpers
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
# (e.g. ``init_db`` reassigns ``_db_connection``).  We forward attribute access
# on this package back to ``base`` so callers using ``voodoo.data._db_connection``
# always see — and can reset — the *live* value rather than a stale import-time
# copy.  PEP 562 supplies the module-level ``__getattr__`` / ``__setattr__`` hooks.
_FORWARDED_GLOBALS = frozenset(
    {"_db_connection", "_models", "_triggers", "_rls_policies"}
)


def __getattr__(name: str):
    if name in _FORWARDED_GLOBALS:
        from voodoo.data import base

        return getattr(base, name)
    raise AttributeError(f"module 'voodoo.data' has no attribute {name!r}")


def __setattr__(name: str, value):
    if name in _FORWARDED_GLOBALS:
        from voodoo.data import base

        setattr(base, name, value)
    else:
        globals()[name] = value
