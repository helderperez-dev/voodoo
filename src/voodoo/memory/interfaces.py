"""Memory interfaces — Protocol, data models, and layer definitions.

The memory system is built on three concepts:

- ``MemoryEntry`` — a single piece of knowledge (what, when, where, relevance)
- ``MemoryStore`` — the persistence surface (read, write, search)
- ``MemoryLayer`` — semantic tagging for the origin of a memory

The ``MemoryProtocol`` defines the contract that all backends must satisfy.
It is deliberately minimal: read, write, search, delete. Backends may
implement additional capabilities (e.g. FTS5, vector search) but the
protocol surface is the same.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import uuid4

__all__ = [
    "MemoryEntry",
    "MemoryLayer",
    "MemorySearchResult",
    "MemoryStore",
]


# ---------------------------------------------------------------------------
# Memory layers
# ---------------------------------------------------------------------------


class MemoryLayer(StrEnum):
    """Semantic origin of a memory entry.

    Layers are tags, not storage tiers — a single SQLite table stores all
    layers. Queries can filter by layer to scope recall.
    """

    WORKING = "working"
    EPISODIC = "episodic"
    DURABLE = "durable"
    SEMANTIC = "semantic"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class MemoryEntry:
    """A single piece of knowledge stored in memory.

    Parameters
    ----------
    id:
        Unique identifier (auto-generated if omitted).
    entity_id:
        The entity this memory belongs to (agent id, user id, etc.).
    layer:
        Semantic layer tag.
    content:
        The memory content (text). Structured data goes in ``metadata``.
    metadata:
        Arbitrary structured data attached to this memory.
    tags:
        Freeform tags for filtering (e.g. ``["user-preference", "python"]``).
    source_execution_id:
        If derived from an execution, the execution id.
    importance:
        0.0–1.0 importance score. Higher = more likely to surface in recall.
    created_at:
        When this memory was created.
    updated_at:
        When this memory was last updated.
    expires_at:
        Optional TTL. ``None`` = never expires.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    entity_id: str = "default"
    layer: MemoryLayer = MemoryLayer.DURABLE
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source_execution_id: str | None = None
    importance: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for storage."""
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "layer": self.layer.value
            if isinstance(self.layer, MemoryLayer)
            else self.layer,
            "content": self.content,
            "metadata": self.metadata,
            "tags": self.tags,
            "source_execution_id": self.source_execution_id,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """Restore from a dict."""
        return cls(
            id=data["id"],
            entity_id=data.get("entity_id", "default"),
            layer=MemoryLayer(data["layer"]),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            source_execution_id=data.get("source_execution_id"),
            importance=data.get("importance", 0.5),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=(
                datetime.fromisoformat(data["expires_at"])
                if data.get("expires_at")
                else None
            ),
        )


@dataclass
class MemorySearchResult:
    """A single result from a memory search.

    Parameters
    ----------
    entry:
        The matched memory entry.
    score:
        Relevance score (0.0–1.0). Higher = more relevant.
    snippet:
        A text snippet highlighting the match context.
    """

    entry: MemoryEntry
    score: float = 0.0
    snippet: str = ""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class MemoryStore(Protocol):
    """The persistence contract for memory backends.

    All backends (SQLite, future pgvector, etc.) must implement this
    protocol. The surface is deliberately minimal.
    """

    def write(self, entry: MemoryEntry) -> str:
        """Write a memory entry. Returns the entry id."""
        ...

    def read(self, entry_id: str) -> MemoryEntry | None:
        """Read a single memory entry by id."""
        ...

    def search(
        self,
        query: str,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """Search memory by text query. Returns ranked results."""
        ...

    def list_entries(
        self,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        """List memory entries with optional filters."""
        ...

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry. Returns True if found and deleted."""
        ...

    def count(
        self,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
    ) -> int:
        """Count memory entries with optional filters."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation (tests)
# ---------------------------------------------------------------------------


class InMemoryMemoryStore:
    """Non-durable in-memory store — for tests."""

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}

    def write(self, entry: MemoryEntry) -> str:
        self._entries[entry.id] = entry
        return entry.id

    def read(self, entry_id: str) -> MemoryEntry | None:
        return self._entries.get(entry_id)

    def search(
        self,
        query: str,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        results: list[MemorySearchResult] = []
        if not query.strip():
            return results
        query_lower = query.lower()
        for entry in self._entries.values():
            if entity_id and entry.entity_id != entity_id:
                continue
            if layers and entry.layer not in layers:
                continue
            if tags and not set(tags).issubset(set(entry.tags)):
                continue
            if query_lower in entry.content.lower():
                results.append(
                    MemorySearchResult(
                        entry=entry,
                        score=1.0,
                        snippet=entry.content[:200],
                    )
                )
        results.sort(key=lambda r: r.entry.importance, reverse=True)
        return results[:limit]

    def list_entries(
        self,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        entries = list(self._entries.values())
        if entity_id:
            entries = [e for e in entries if e.entity_id == entity_id]
        if layers:
            entries = [e for e in entries if e.layer in layers]
        if tags:
            entries = [e for e in entries if set(tags).issubset(set(e.tags))]
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[offset : offset + limit]

    def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    def count(
        self,
        entity_id: str | None = None,
        layers: list[MemoryLayer] | None = None,
    ) -> int:
        entries = list(self._entries.values())
        if entity_id:
            entries = [e for e in entries if e.entity_id == entity_id]
        if layers:
            entries = [e for e in entries if e.layer in layers]
        return len(entries)


# ---------------------------------------------------------------------------
# Protocol compliance check
# ---------------------------------------------------------------------------

# Placed at file bottom per spec: Protocol checks go under TYPE_CHECKING.
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    _memory_check: MemoryStore = InMemoryMemoryStore()  # type: ignore[assignment]
