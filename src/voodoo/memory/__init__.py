"""Memory — durable, queryable entity state (Sprint 16).

Memory gives entities the ability to recall what happened, what they know,
and what they need to do. It is layered:

    Layer 0 — Working memory: short-lived, in-process scratch pad
    Layer 1 — Episodic memory: execution-derived, auto-written from journal
    Layer 2 — Durable memory: explicit read/write/search (SQLite + FTS5)
    Layer 3 — Semantic memory: embeddings-based retrieval (future adapter)

The default backend is SQLite with FTS5 for full-text search. No new
dependencies are required — FTS5 is built into Python's ``sqlite3`` module.

Memory is NOT context. Context is an opaque dict passed to tool calls.
Memory is a queryable, durable record of what the entity knows.
"""

from voodoo.memory.interfaces import (
    MemoryEntry,
    MemoryLayer,
    MemorySearchResult,
    MemoryStore,
)
from voodoo.memory.sqlite import SQLiteMemoryStore

__all__ = [
    "MemoryEntry",
    "MemoryLayer",
    "MemorySearchResult",
    "MemoryStore",
    "SQLiteMemoryStore",
]
