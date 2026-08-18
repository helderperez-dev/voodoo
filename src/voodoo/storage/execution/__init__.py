"""Durable execution storage adapters.

``SQLiteExecutionStore`` persists executions and their event journal through
the Voodoo database layer (Sprint 3). ``JSONFileExecutionStore`` remains in
``voodoo.runtime.persistence`` as a legacy reader for one-time migration.
"""

from voodoo.storage.execution.sqlite import SQLiteExecutionStore

__all__ = ["SQLiteExecutionStore"]
