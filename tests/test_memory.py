"""Tests for memory — durable entity state (Sprint 16).

Covers:
- MemoryEntry creation and serialization
- InMemoryMemoryStore CRUD and search
- SQLiteMemoryStore CRUD, search (FTS5 + LIKE fallback), and persistence
- Agent.memory property and episodic memory auto-write
- Memory survives store restart (SQLite)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from voodoo.memory.interfaces import (
    InMemoryMemoryStore,
    MemoryEntry,
    MemoryLayer,
    MemorySearchResult,
)
from voodoo.memory.sqlite import SQLiteMemoryStore

# ---------------------------------------------------------------------------
# MemoryEntry
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    """Tests for the MemoryEntry dataclass."""

    def test_create_with_defaults(self) -> None:
        entry = MemoryEntry(content="hello world")
        assert entry.entity_id == "default"
        assert entry.layer == MemoryLayer.DURABLE
        assert entry.content == "hello world"
        assert entry.importance == 0.5
        assert entry.tags == []
        assert entry.metadata == {}
        assert entry.id  # auto-generated

    def test_create_with_all_fields(self) -> None:
        entry = MemoryEntry(
            id="mem-1",
            entity_id="agent-1",
            layer=MemoryLayer.EPISODIC,
            content="user asked about Python",
            metadata={"topic": "python"},
            tags=["python", "question"],
            source_execution_id="exec-1",
            importance=0.8,
        )
        assert entry.id == "mem-1"
        assert entry.entity_id == "agent-1"
        assert entry.layer == MemoryLayer.EPISODIC
        assert entry.importance == 0.8
        assert "python" in entry.tags

    def test_to_dict_roundtrip(self) -> None:
        entry = MemoryEntry(
            content="test",
            layer=MemoryLayer.WORKING,
            tags=["a", "b"],
            metadata={"key": "value"},
        )
        d = entry.to_dict()
        restored = MemoryEntry.from_dict(d)
        assert restored.id == entry.id
        assert restored.content == entry.content
        assert restored.layer == entry.layer
        assert restored.tags == entry.tags
        assert restored.metadata == entry.metadata

    def test_expires_at_serialization(self) -> None:
        exp = datetime(2026, 12, 31, tzinfo=UTC)
        entry = MemoryEntry(content="temp", expires_at=exp)
        d = entry.to_dict()
        assert d["expires_at"] is not None
        restored = MemoryEntry.from_dict(d)
        assert restored.expires_at is not None
        assert restored.expires_at.year == 2026


# ---------------------------------------------------------------------------
# MemoryLayer
# ---------------------------------------------------------------------------


class TestMemoryLayer:
    def test_layers_exist(self) -> None:
        assert MemoryLayer.WORKING == "working"
        assert MemoryLayer.EPISODIC == "episodic"
        assert MemoryLayer.DURABLE == "durable"
        assert MemoryLayer.SEMANTIC == "semantic"


# ---------------------------------------------------------------------------
# InMemoryMemoryStore
# ---------------------------------------------------------------------------


class TestInMemoryMemoryStore:
    """Tests for the in-memory memory store."""

    def test_write_and_read(self) -> None:
        store = InMemoryMemoryStore()
        entry = MemoryEntry(content="hello", entity_id="e1")
        eid = store.write(entry)
        assert eid == entry.id
        loaded = store.read(eid)
        assert loaded is not None
        assert loaded.content == "hello"

    def test_read_nonexistent(self) -> None:
        store = InMemoryMemoryStore()
        assert store.read("nope") is None

    def test_search_basic(self) -> None:
        store = InMemoryMemoryStore()
        store.write(MemoryEntry(content="Python is great", entity_id="e1"))
        store.write(MemoryEntry(content="JavaScript is popular", entity_id="e1"))
        results = store.search("Python")
        assert len(results) == 1
        assert "Python" in results[0].entry.content

    def test_search_with_entity_filter(self) -> None:
        store = InMemoryMemoryStore()
        store.write(MemoryEntry(content="hello world", entity_id="e1"))
        store.write(MemoryEntry(content="hello world", entity_id="e2"))
        results = store.search("hello", entity_id="e1")
        assert len(results) == 1
        assert results[0].entry.entity_id == "e1"

    def test_search_with_layer_filter(self) -> None:
        store = InMemoryMemoryStore()
        store.write(MemoryEntry(content="test", layer=MemoryLayer.EPISODIC))
        store.write(MemoryEntry(content="test", layer=MemoryLayer.DURABLE))
        results = store.search("test", layers=[MemoryLayer.EPISODIC])
        assert len(results) == 1
        assert results[0].entry.layer == MemoryLayer.EPISODIC

    def test_search_with_tag_filter(self) -> None:
        store = InMemoryMemoryStore()
        store.write(MemoryEntry(content="test", tags=["python", "code"]))
        store.write(MemoryEntry(content="test", tags=["javascript"]))
        results = store.search("test", tags=["python"])
        assert len(results) == 1

    def test_search_empty_query(self) -> None:
        store = InMemoryMemoryStore()
        store.write(MemoryEntry(content="test"))
        results = store.search("")
        assert len(results) == 0

    def test_list_entries(self) -> None:
        store = InMemoryMemoryStore()
        for i in range(5):
            store.write(MemoryEntry(content=f"item {i}", entity_id="e1"))
        entries = store.list_entries(entity_id="e1", limit=3)
        assert len(entries) == 3

    def test_delete(self) -> None:
        store = InMemoryMemoryStore()
        entry = MemoryEntry(content="delete me")
        store.write(entry)
        assert store.delete(entry.id) is True
        assert store.read(entry.id) is None
        assert store.delete(entry.id) is False

    def test_count(self) -> None:
        store = InMemoryMemoryStore()
        store.write(MemoryEntry(content="a", entity_id="e1"))
        store.write(MemoryEntry(content="b", entity_id="e1"))
        store.write(MemoryEntry(content="c", entity_id="e2"))
        assert store.count() == 3
        assert store.count(entity_id="e1") == 2
        assert store.count(layers=[MemoryLayer.DURABLE]) == 3


# ---------------------------------------------------------------------------
# SQLiteMemoryStore
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStore:
    """Tests for the SQLite memory store."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "test_memory.db"

    def test_write_and_read(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        entry = MemoryEntry(content="hello SQLite", entity_id="e1")
        eid = store.write(entry)
        assert eid == entry.id
        loaded = store.read(eid)
        assert loaded is not None
        assert loaded.content == "hello SQLite"
        assert loaded.entity_id == "e1"
        store.close()

    def test_read_nonexistent(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        assert store.read("nope") is None
        store.close()

    def test_upsert(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        entry = MemoryEntry(id="fixed-id", content="original")
        store.write(entry)
        entry.content = "updated"
        store.write(entry)
        loaded = store.read("fixed-id")
        assert loaded is not None
        assert loaded.content == "updated"
        store.close()

    def test_search_basic(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        store.write(MemoryEntry(content="Python is a great language"))
        store.write(MemoryEntry(content="JavaScript is popular"))
        results = store.search("Python")
        assert len(results) >= 1
        assert any("Python" in r.entry.content for r in results)
        store.close()

    def test_search_with_entity_filter(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        store.write(MemoryEntry(content="hello world", entity_id="e1"))
        store.write(MemoryEntry(content="hello world", entity_id="e2"))
        results = store.search("hello", entity_id="e1")
        assert all(r.entry.entity_id == "e1" for r in results)
        store.close()

    def test_search_with_layer_filter(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        store.write(MemoryEntry(content="test content", layer=MemoryLayer.EPISODIC))
        store.write(MemoryEntry(content="test content", layer=MemoryLayer.DURABLE))
        results = store.search("test", layers=[MemoryLayer.EPISODIC])
        assert all(r.entry.layer == MemoryLayer.EPISODIC for r in results)
        store.close()

    def test_search_with_tag_filter(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        store.write(MemoryEntry(content="test content", tags=["python", "code"]))
        store.write(MemoryEntry(content="test content", tags=["javascript"]))
        results = store.search("test", tags=["python"])
        assert len(results) >= 1
        store.close()

    def test_search_empty_query(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        store.write(MemoryEntry(content="test"))
        results = store.search("")
        assert len(results) == 0
        store.close()

    def test_list_entries(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        for i in range(5):
            store.write(MemoryEntry(content=f"item {i}", entity_id="e1"))
        entries = store.list_entries(entity_id="e1", limit=3)
        assert len(entries) == 3
        store.close()

    def test_delete(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        entry = MemoryEntry(content="delete me")
        store.write(entry)
        assert store.delete(entry.id) is True
        assert store.read(entry.id) is None
        assert store.delete(entry.id) is False
        store.close()

    def test_count(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        store.write(MemoryEntry(content="a", entity_id="e1"))
        store.write(MemoryEntry(content="b", entity_id="e1"))
        store.write(MemoryEntry(content="c", entity_id="e2"))
        assert store.count() == 3
        assert store.count(entity_id="e1") == 2
        store.close()

    def test_persistence_across_reopen(self, db_path: Path) -> None:
        """Memory survives store restart — Sprint 16 acceptance criterion."""
        store = SQLiteMemoryStore(db_path)
        entry = MemoryEntry(
            content="persistent knowledge",
            entity_id="e1",
            tags=["important"],
        )
        store.write(entry)
        entry_id = entry.id
        store.close()

        # Reopen — data must survive.
        store2 = SQLiteMemoryStore(db_path)
        loaded = store2.read(entry_id)
        assert loaded is not None
        assert loaded.content == "persistent knowledge"
        assert loaded.entity_id == "e1"
        assert "important" in loaded.tags
        store2.close()

    def test_metadata_roundtrip(self, db_path: Path) -> None:
        store = SQLiteMemoryStore(db_path)
        entry = MemoryEntry(
            content="test",
            metadata={"nested": {"key": [1, 2, 3]}},
        )
        store.write(entry)
        loaded = store.read(entry.id)
        assert loaded is not None
        assert loaded.metadata["nested"]["key"] == [1, 2, 3]
        store.close()

    def test_fts_availability(self, db_path: Path) -> None:
        """Check that FTS5 is available (most Python builds include it)."""
        store = SQLiteMemoryStore(db_path)
        # We don't assert True here — some minimal builds lack FTS5.
        # The store should work either way (FTS or LIKE fallback).
        assert isinstance(store._has_fts, bool)
        store.close()


# ---------------------------------------------------------------------------
# Agent memory integration
# ---------------------------------------------------------------------------


class TestAgentMemory:
    """Tests for Agent.memory property and episodic memory auto-write."""

    @pytest.mark.asyncio
    async def test_agent_has_memory_property(self) -> None:
        from voodoo.ai.agent import Agent

        agent = Agent(model="mock:test", tools=[])
        # memory is lazily created
        assert agent.memory is not None
        assert hasattr(agent.memory, "write")
        assert hasattr(agent.memory, "search")

    @pytest.mark.asyncio
    async def test_agent_memory_is_stable(self) -> None:
        """Accessing .memory twice returns the same store."""
        from voodoo.ai.agent import Agent

        agent = Agent(model="mock:test", tools=[])
        m1 = agent.memory
        m2 = agent.memory
        assert m1 is m2

    @pytest.mark.asyncio
    async def test_agent_run_writes_episodic_memory(self) -> None:
        from voodoo.ai.agent import Agent

        agent = Agent(model="mock:test", tools=[])
        run = await agent.run("What is 2+2?")
        # Episodic memory should be written
        entries = agent.memory.list_entries(entity_id="agent")
        assert len(entries) >= 1
        episodic = [e for e in entries if e.layer == MemoryLayer.EPISODIC]
        assert len(episodic) >= 1
        assert episodic[0].source_execution_id == run.run_id
        assert "agent-run" in episodic[0].tags

    @pytest.mark.asyncio
    async def test_agent_stream_writes_episodic_memory(self) -> None:
        from voodoo.ai.agent import Agent

        agent = Agent(model="mock:test", tools=[])
        events = []
        async for event in agent.stream("Hello"):
            events.append(event)
        # Episodic memory should be written
        entries = agent.memory.list_entries(entity_id="agent")
        assert len(entries) >= 1
        episodic = [e for e in entries if e.layer == MemoryLayer.EPISODIC]
        assert len(episodic) >= 1

    @pytest.mark.asyncio
    async def test_agent_custom_memory_store(self) -> None:
        """Agent accepts a custom memory store."""
        from voodoo.ai.agent import Agent
        from voodoo.memory.interfaces import InMemoryMemoryStore

        custom_store = InMemoryMemoryStore()
        agent = Agent(model="mock:test", tools=[], memory=custom_store)
        assert agent.memory is custom_store

    @pytest.mark.asyncio
    async def test_agent_memory_search_after_runs(self) -> None:
        from voodoo.ai.agent import Agent

        agent = Agent(model="mock:test", tools=[])
        await agent.run("Tell me about Python")
        results = agent.memory.search("Python", entity_id="agent")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# MemorySearchResult
# ---------------------------------------------------------------------------


class TestMemorySearchResult:
    def test_creation(self) -> None:
        entry = MemoryEntry(content="test")
        result = MemorySearchResult(entry=entry, score=0.9, snippet="tes...")
        assert result.score == 0.9
        assert result.snippet == "tes..."
