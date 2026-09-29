"""Canonical Store-first operational context for Voodoo CLI commands.

CLI commands must observe the same application infrastructure contract as the
Runtime. The default path opens exactly one application RuntimeStore and binds
it for domain adapters; SQL adapters are resolved only when explicitly
configured by the application.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from voodoo.config import VoodooConfig, get_config
from voodoo.data.store_backend import bind_runtime_store
from voodoo.runtime.store import (
    RuntimeStore,
    StoreConfig,
    activate_runtime_store,
    bind_active_runtime_store,
)


@dataclass(slots=True)
class CLIApplicationContext:
    """Operational view of the current Voodoo application."""

    config: VoodooConfig
    runtime_store: RuntimeStore

    @property
    def store_path(self) -> str:
        return str(self.runtime_store.config.path)

    def execution_store(self):
        """Return the configured execution store.

        Voodoo Store is the default. SQLite/PostgreSQL are compatibility
        adapters and are imported only when the user explicitly selects them.
        """
        provider = self.config.database.provider.strip().lower()
        if provider == "voodoo":
            from voodoo.storage.execution import VoodooStoreExecutionStore

            return VoodooStoreExecutionStore()
        if provider == "sqlite":
            from voodoo.storage.execution import SQLiteExecutionStore

            path = self.config.database.path or self.config.db_path
            if not path:
                raise RuntimeError(
                    "database.provider='sqlite' requires database.path or VOODOO_DB_PATH"
                )
            return SQLiteExecutionStore(path)
        if provider in {"postgres", "postgresql"}:
            from voodoo.storage.execution import PostgresExecutionStore

            url = self.config.database.url or self.config.db_path
            if not url:
                raise RuntimeError(
                    "database.provider='postgres' requires database.url or DATABASE_URL"
                )
            return PostgresExecutionStore(url)
        raise RuntimeError(
            f"Unknown execution provider {self.config.database.provider!r}. "
            "Use 'voodoo' (default), 'sqlite', or 'postgres'."
        )

    def schedule_store(self):
        from voodoo.storage.scheduler import create_schedule_store

        return create_schedule_store()

    def object_store(self):
        provider = self.config.objects.provider.strip().lower()
        if provider == "voodoo":
            from voodoo.storage.objects import VoodooStoreObjectStore

            return VoodooStoreObjectStore()
        if provider == "local":
            from voodoo.storage.objects import LocalObjectStore

            return LocalObjectStore(self.config.objects.base_dir or ".voodoo/objects")
        if provider == "s3":
            from voodoo.storage.objects import S3ObjectStore

            return S3ObjectStore()
        raise RuntimeError(
            f"Unknown object provider {self.config.objects.provider!r}. "
            "Use 'voodoo' (default), 'local', or 's3'."
        )

    def agent_registry(self):
        provider = self.config.database.provider.strip().lower()
        if provider == "voodoo":
            from voodoo.agents.registry import VoodooStoreAgentRegistry

            return VoodooStoreAgentRegistry()
        if provider == "sqlite":
            from voodoo.agents.registry import SQLiteAgentRegistry

            base = self.config.database.path or self.config.db_path
            if not base:
                raise RuntimeError(
                    "database.provider='sqlite' requires database.path or VOODOO_DB_PATH"
                )
            path = base.replace("data.db", "agents.db")
            return SQLiteAgentRegistry(path)
        raise RuntimeError(
            "Agent registry currently supports the default Voodoo Store or an "
            "explicit SQLite compatibility adapter."
        )


@contextmanager
def open_application_context() -> Iterator[CLIApplicationContext]:
    """Open the current application using the Runtime's canonical Store lifecycle."""
    config = get_config()
    runtime_store = activate_runtime_store(
        StoreConfig.from_mapping(config.store.model_dump())
    )
    bind_runtime_store(runtime_store)
    try:
        yield CLIApplicationContext(config=config, runtime_store=runtime_store)
    finally:
        bind_runtime_store(None)
        bind_active_runtime_store(None)
        runtime_store.stop()


__all__ = ["CLIApplicationContext", "open_application_context"]
