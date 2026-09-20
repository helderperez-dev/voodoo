"""Tests for Sprint 17 — Agents as durable entities.

Covers:
- AgentEntity / AgentRunRecord data models (CRUD, serialization)
- InMemoryAgentRegistry (register, get, list, update, delete, record_run, get_runs)
- SQLiteAgentRegistry (same + persistence across restart)
- Agent integration (agent_registry parameter, auto-register, run history)
- Multi-agent collaboration via events
"""

from __future__ import annotations

import pytest

from voodoo.agents.models import AgentEntity, AgentRunRecord
from voodoo.agents.registry import InMemoryAgentRegistry, SQLiteAgentRegistry
from voodoo.ai.agent import Agent

# ---------------------------------------------------------------------------
# AgentEntity
# ---------------------------------------------------------------------------


class TestAgentEntity:
    def test_default_values(self) -> None:
        entity = AgentEntity()
        assert entity.agent_id
        assert entity.name == ""
        assert entity.state == "active"
        assert entity.capabilities == []
        assert entity.tools == []
        assert entity.created_at
        assert entity.updated_at

    def test_custom_values(self) -> None:
        entity = AgentEntity(
            agent_id="lead-scorer",
            name="Lead Scorer",
            model="openai:gpt-4o",
            capabilities=["scoring.read"],
            tools=["get_lead", "update_lead"],
            state="active",
        )
        assert entity.agent_id == "lead-scorer"
        assert entity.name == "Lead Scorer"
        assert entity.capabilities == ["scoring.read"]
        assert entity.tools == ["get_lead", "update_lead"]

    def test_to_dict_roundtrip(self) -> None:
        entity = AgentEntity(
            agent_id="test-agent",
            name="Test Agent",
            model="mock:test",
            config={"temperature": 0.7},
        )
        d = entity.to_dict()
        restored = AgentEntity.from_dict(d)
        assert restored.agent_id == entity.agent_id
        assert restored.config == {"temperature": 0.7}


# ---------------------------------------------------------------------------
# AgentRunRecord
# ---------------------------------------------------------------------------


class TestAgentRunRecord:
    def test_default_values(self) -> None:
        record = AgentRunRecord()
        assert record.run_id
        assert record.status == "completed"
        assert record.tokens_in == 0
        assert record.cost == 0.0

    def test_to_dict_roundtrip(self) -> None:
        record = AgentRunRecord(
            run_id="run-123",
            agent_id="agent-1",
            prompt="hello",
            output="world",
            status="completed",
            tokens_in=10,
            tokens_out=5,
            cost=0.001,
        )
        d = record.to_dict()
        restored = AgentRunRecord.from_dict(d)
        assert restored.run_id == "run-123"
        assert restored.agent_id == "agent-1"
        assert restored.tokens_in == 10


# ---------------------------------------------------------------------------
# InMemoryAgentRegistry
# ---------------------------------------------------------------------------


class TestInMemoryAgentRegistry:
    @pytest.fixture
    def registry(self) -> InMemoryAgentRegistry:
        return InMemoryAgentRegistry()

    async def test_register_and_get(self, registry: InMemoryAgentRegistry) -> None:
        entity = AgentEntity(agent_id="a1", name="Agent 1", model="mock:test")
        await registry.register(entity)
        got = await registry.get("a1")
        assert got is not None
        assert got.name == "Agent 1"

    async def test_get_nonexistent(self, registry: InMemoryAgentRegistry) -> None:
        assert await registry.get("nope") is None

    async def test_list_agents(self, registry: InMemoryAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1", name="A1"))
        await registry.register(AgentEntity(agent_id="a2", name="A2", state="paused"))
        all_agents = await registry.list_agents()
        assert len(all_agents) == 2
        active = await registry.list_agents(state="active")
        assert len(active) == 1
        assert active[0].agent_id == "a1"

    async def test_update(self, registry: InMemoryAgentRegistry) -> None:
        entity = AgentEntity(agent_id="a1", name="Old Name")
        await registry.register(entity)
        entity.name = "New Name"
        await registry.update(entity)
        got = await registry.get("a1")
        assert got is not None
        assert got.name == "New Name"

    async def test_update_nonexistent(self, registry: InMemoryAgentRegistry) -> None:
        entity = AgentEntity(agent_id="ghost")
        with pytest.raises(KeyError):
            await registry.update(entity)

    async def test_delete(self, registry: InMemoryAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1"))
        assert await registry.delete("a1") is True
        assert await registry.get("a1") is None
        assert await registry.delete("a1") is False

    async def test_record_run_and_get_runs(
        self, registry: InMemoryAgentRegistry
    ) -> None:
        await registry.register(AgentEntity(agent_id="a1"))
        r1 = AgentRunRecord(run_id="r1", agent_id="a1", status="completed")
        r2 = AgentRunRecord(run_id="r2", agent_id="a1", status="error")
        await registry.record_run(r1)
        await registry.record_run(r2)
        runs = await registry.get_runs("a1")
        assert len(runs) == 2
        # get_runs returns newest-first
        assert runs[0].run_id == "r2"
        assert runs[1].run_id == "r1"

    async def test_count_agents(self, registry: InMemoryAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1"))
        await registry.register(AgentEntity(agent_id="a2", state="paused"))
        assert await registry.count_agents() == 2
        assert await registry.count_agents(state="active") == 1

    async def test_count_runs(self, registry: InMemoryAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1"))
        await registry.record_run(AgentRunRecord(run_id="r1", agent_id="a1"))
        await registry.record_run(AgentRunRecord(run_id="r2", agent_id="a1"))
        assert await registry.count_runs("a1") == 2
        assert await registry.count_runs("a2") == 0


# ---------------------------------------------------------------------------
# SQLiteAgentRegistry
# ---------------------------------------------------------------------------


class TestSQLiteAgentRegistry:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "test_agents.db")

    @pytest.fixture
    def registry(self, db_path) -> SQLiteAgentRegistry:
        return SQLiteAgentRegistry(db_path)

    async def test_register_and_get(self, registry: SQLiteAgentRegistry) -> None:
        entity = AgentEntity(
            agent_id="a1",
            name="Agent 1",
            model="openai:gpt-4o",
            capabilities=["read", "write"],
            tools=["search", "update"],
        )
        await registry.register(entity)
        got = await registry.get("a1")
        assert got is not None
        assert got.name == "Agent 1"
        assert got.capabilities == ["read", "write"]
        assert got.tools == ["search", "update"]
        registry.close()

    async def test_list_agents(self, registry: SQLiteAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1", name="A1"))
        await registry.register(AgentEntity(agent_id="a2", name="A2", state="paused"))
        all_agents = await registry.list_agents()
        assert len(all_agents) == 2
        active = await registry.list_agents(state="active")
        assert len(active) == 1
        registry.close()

    async def test_update(self, registry: SQLiteAgentRegistry) -> None:
        entity = AgentEntity(agent_id="a1", name="Old")
        await registry.register(entity)
        entity.name = "New"
        await registry.update(entity)
        got = await registry.get("a1")
        assert got is not None
        assert got.name == "New"
        registry.close()

    async def test_delete(self, registry: SQLiteAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1"))
        assert await registry.delete("a1") is True
        assert await registry.get("a1") is None
        registry.close()

    async def test_record_run_and_get_runs(self, registry: SQLiteAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1"))
        r1 = AgentRunRecord(
            run_id="r1", agent_id="a1", status="completed", tokens_in=100
        )
        r2 = AgentRunRecord(run_id="r2", agent_id="a1", status="error", tokens_in=50)
        await registry.record_run(r1)
        await registry.record_run(r2)
        runs = await registry.get_runs("a1")
        assert len(runs) == 2
        # get_runs returns newest-first
        assert runs[0].run_id == "r2"
        assert runs[1].run_id == "r1"
        assert runs[1].tokens_in == 100
        registry.close()

    async def test_persistence_across_reopen(self, db_path: str) -> None:
        """Sprint 17 acceptance criterion: agent survives restart."""
        reg1 = SQLiteAgentRegistry(db_path)
        await reg1.register(
            AgentEntity(
                agent_id="persistent-agent",
                name="Persistent",
                model="mock:test",
                capabilities=["read"],
            )
        )
        await reg1.record_run(
            AgentRunRecord(
                run_id="run-1",
                agent_id="persistent-agent",
                status="completed",
                tokens_in=42,
            )
        )
        reg1.close()

        # Reopen — data must survive.
        reg2 = SQLiteAgentRegistry(db_path)
        entity = await reg2.get("persistent-agent")
        assert entity is not None
        assert entity.name == "Persistent"
        assert entity.capabilities == ["read"]
        runs = await reg2.get_runs("persistent-agent")
        assert len(runs) == 1
        assert runs[0].tokens_in == 42
        reg2.close()

    async def test_count(self, registry: SQLiteAgentRegistry) -> None:
        await registry.register(AgentEntity(agent_id="a1"))
        await registry.register(AgentEntity(agent_id="a2"))
        assert await registry.count_agents() == 2
        await registry.record_run(AgentRunRecord(run_id="r1", agent_id="a1"))
        assert await registry.count_runs("a1") == 1
        assert await registry.count_runs("a2") == 0
        registry.close()


# ---------------------------------------------------------------------------
# Agent integration with registry
# ---------------------------------------------------------------------------


class TestAgentRegistryIntegration:
    async def test_agent_auto_registers(self) -> None:
        """Agent with agent_id + agent_registry auto-registers on first run."""
        registry = InMemoryAgentRegistry()
        agent = Agent(
            model="mock:test",
            agent_id="auto-agent",
            name="Auto Agent",
            agent_registry=registry,
        )
        await agent.run("Hello")
        entity = await registry.get("auto-agent")
        assert entity is not None
        assert entity.name == "Auto Agent"
        assert entity.model == "mock:test"

    async def test_agent_records_run_history(self) -> None:
        """Agent.run() persists a run record to the registry."""
        registry = InMemoryAgentRegistry()
        agent = Agent(
            model="mock:test",
            agent_id="history-agent",
            agent_registry=registry,
        )
        run = await agent.run("Test prompt")
        runs = await registry.get_runs("history-agent")
        assert len(runs) == 1
        assert runs[0].run_id == run.run_id
        assert runs[0].prompt == "Test prompt"
        assert runs[0].status in ("completed", "error", "failed")

    async def test_agent_stream_records_run_history(self) -> None:
        """Agent.stream() persists a run record to the registry."""
        registry = InMemoryAgentRegistry()
        agent = Agent(
            model="mock:test",
            agent_id="stream-agent",
            agent_registry=registry,
        )
        events = []
        async for event in agent.stream("Stream test"):
            events.append(event)
        runs = await registry.get_runs("stream-agent")
        assert len(runs) == 1
        assert runs[0].prompt == "Stream test"

    async def test_agent_custom_memory_store(self) -> None:
        """Agent with both memory and registry."""
        from voodoo.memory.interfaces import InMemoryMemoryStore

        registry = InMemoryAgentRegistry()
        memory = InMemoryMemoryStore()
        agent = Agent(
            model="mock:test",
            agent_id="full-agent",
            agent_registry=registry,
            memory=memory,
        )
        await agent.run("Full test")
        # Both registry and memory should have records
        runs = await registry.get_runs("full-agent")
        assert len(runs) == 1
        entries = memory.list_entries()
        assert len(entries) >= 1  # episodic memory written

    async def test_agent_without_registry_no_error(self) -> None:
        """Agent without agent_registry works fine (no-op)."""
        agent = Agent(model="mock:test", agent_id="solo-agent")
        run = await agent.run("Solo test")
        assert run.status in ("completed", "error", "failed")


# ---------------------------------------------------------------------------
# Multi-agent collaboration
# ---------------------------------------------------------------------------


class TestMultiAgentCollaboration:
    async def test_two_agents_share_registry(self) -> None:
        """Two agents registered in the same registry produce distinct histories."""
        registry = InMemoryAgentRegistry()
        agent1 = Agent(
            model="mock:test",
            agent_id="agent-a",
            name="Agent A",
            agent_registry=registry,
        )
        agent2 = Agent(
            model="mock:test",
            agent_id="agent-b",
            name="Agent B",
            agent_registry=registry,
        )
        await agent1.run("Hello from A")
        await agent2.run("Hello from B")
        await agent1.run("Follow-up from A")

        runs_a = await registry.get_runs("agent-a")
        runs_b = await registry.get_runs("agent-b")
        assert len(runs_a) == 2
        assert len(runs_b) == 1

        total = await registry.count_agents()
        assert total == 2
