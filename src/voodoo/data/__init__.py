"""Voodoo Store-native data layer.

``Model`` and ``BaseModel`` use Voodoo Store directly. SQL adapters are optional
and are never imported by the default data package. Applications that need a
SQL adapter should import it explicitly from ``voodoo.storage.database``.
"""

from __future__ import annotations

from typing import Any

from voodoo.data.store_facade import (
    Delete,
    FK,
    BaseModel,
    Model,
    field,
    relation,
    validate,
    validate_model,
    ModelMeta,
    _get_table_name,
    _models,
    _rls_policies,
    _triggers,
    on_insert,
    on_update,
    rls_policy,
)

__all__ = [
    "BaseModel",
    "Model",
    "ModelMeta",
    "Delete",
    "FK",
    "field",
    "relation",
    "validate",
    "validate_model",
    "on_insert",
    "on_update",
    "rls_policy",
    "_get_table_name",
    "_models",
    "_rls_policies",
    "_triggers",
]

_sql_initialized = False


async def init_db(*args: Any, **kwargs: Any) -> Any:
    """Compatibility entry point for the optional SQL subsystem.

    Importing ``voodoo`` does not load SQL or require ``aiosqlite``. Calling
    this function explicitly opts into the legacy SQL adapter surface.
    """
    global _sql_initialized

    from voodoo.data.base import init_db as _init_db

    result = await _init_db(*args, **kwargs)
    _sql_initialized = True
    return result


async def get_db() -> Any:
    """Return the explicitly initialized optional SQL connection."""
    from voodoo.data.base import get_db as _get_db

    return await _get_db()


async def close_db() -> None:
    """Close SQL only when the optional subsystem was explicitly initialized.

    The Store-first Runtime calls this compatibility hook during shutdown. A
    default application must therefore treat it as a no-op instead of importing
    the legacy SQLite adapter merely to discover that no SQL connection exists.
    """
    global _sql_initialized

    if not _sql_initialized:
        return

    from voodoo.data.base import close_db as _close_db

    await _close_db()
    _sql_initialized = False
