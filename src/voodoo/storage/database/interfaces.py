"""Voodoo database capability interface.

Every durable Voodoo subsystem (state, executions, tasks, events, schedules)
persists through a ``VoodooDatabase`` implementation. SQLite is the default
embedded backend (spec §11); PostgreSQL arrives later as an optional adapter
behind the same protocol.

Application code must never import ``aiosqlite``/``psycopg`` directly — the
adapter boundary lives here (spec §2).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from voodoo.adapters.capabilities import DatabaseCapabilities

__all__ = ["DatabaseCapabilities", "Migration", "VoodooDatabase"]


@dataclass(frozen=True)
class Migration:
    """One ordered, tracked schema change.

    Version numbering is a single global namespace shared by the framework
    and the application: version 1 is the user-model baseline, the framework
    reserves 2+, applications may use 100+.

    ``fn`` receives the ``VoodooDatabase`` instance, keeping migrations
    backend-neutral. ``rerun=True`` steps re-execute ``fn`` on every
    ``migrate()`` call (idempotent DDL only) so items registered after the
    baseline — e.g. models imported later — still get their tables.
    """

    version: int
    name: str
    statements: tuple[str, ...] = ()
    fn: Callable[[VoodooDatabase], Awaitable[None]] | None = None
    rerun: bool = False


class VoodooDatabase(Protocol):
    """Backend-neutral database capability.

    Implementations provide: connection lifecycle, an ordered idempotent
    migration runner backed by a ledger table, a transaction helper, and
    query primitives. ``connect()`` intentionally does not migrate — callers
    control when schema changes apply.
    """

    provider: str

    async def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def migrate(self) -> None: ...

    def current_version(self) -> int: ...

    def capabilities(self) -> DatabaseCapabilities: ...

    @asynccontextmanager
    def transaction(self) -> AsyncIterator[Any]: ...

    async def execute(self, query: str, params: Sequence[Any] = ()) -> Any: ...

    async def fetch_all(self, query: str, params: Sequence[Any] = ()) -> list[Any]: ...

    async def fetch_one(self, query: str, params: Sequence[Any] = ()) -> Any | None: ...
