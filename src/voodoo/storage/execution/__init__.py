"""Durable execution storage adapters.

Voodoo Store is the default execution persistence substrate. SQL adapters are
loaded only when explicitly requested.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from voodoo.storage.execution.store import VoodooStoreExecutionStore

__all__ = [
    "PostgresExecutionStore",
    "SQLiteExecutionStore",
    "VoodooStoreExecutionStore",
]

_LAZY_EXPORTS = {
    "PostgresExecutionStore": (
        "voodoo.storage.execution.postgres",
        "PostgresExecutionStore",
    ),
    "SQLiteExecutionStore": (
        "voodoo.storage.execution.sqlite",
        "SQLiteExecutionStore",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(
            f"module 'voodoo.storage.execution' has no attribute {name!r}"
        )
    module_name, symbol = target
    value = getattr(import_module(module_name), symbol)
    globals()[name] = value
    return value
