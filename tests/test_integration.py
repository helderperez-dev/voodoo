"""Cross-subsystem integration tests.

Exercises the full chain: UI → state → event → WS patch, mesh → worker →
agent → tool → db, auth-guarded routes, MCP tool exposure, agent run with
mock provider and tool calling, and correlation-ID propagation.

All tests use the deterministic mock provider — no network calls.
"""

from __future__ import annotations

import asyncio

import pytest
from starlette.testclient import TestClient

import voodoo.data
from voodoo import Agent, Div, Text, page, state
from voodoo.ai.providers import ProviderResponse
from voodoo.ai.providers.mock import MockProvider
from voodoo.auth import create_access_token
from voodoo.core import create_app
from voodoo.core.events import event, ws_manager
from voodoo.core.state import StateRenderer, state_renderer
from voodoo.mcp import MCPServer
from voodoo.mesh import mesh
from voodoo.telemetry import telemetry_store, trace_id_var
from voodoo.tools import registry as tools_module
from voodoo.tools.registry import ToolRegistry, build_spec

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_subsystems():
    """Isolate mesh, tools registry, event handlers, and telemetry between tests."""
    # Save ws_manager.broadcast_patch (monkeypatched in some tests).
    saved_broadcast = ws_manager.broadcast_patch

    mesh.event_handlers.clear()
    mesh.active_nodes.clear()
    mesh.exposed_functions.clear()
    tools_module.default_registry._tools.clear()
    from voodoo.core.events import event_handlers as _event_handlers

    _event_handlers.clear()
    state_renderer._bindings.clear()
    ws_manager.active_connections.clear()
    yield
    mesh.event_handlers.clear()
    mesh.active_nodes.clear()
    mesh.exposed_functions.clear()
    tools_module.default_registry._tools.clear()
    _event_handlers.clear()
    state_renderer._bindings.clear()
    ws_manager.active_connections.clear()
    ws_manager.broadcast_patch = saved_broadcast


@pytest.fixture
async def test_db():
    await voodoo.data.init_db(":memory:")
    db = await voodoo.data.get_db()
    yield db
    if voodoo.data._db_connection:
        await voodoo.data._db_connection.close()
        voodoo.data._db_connection = None


# ---------------------------------------------------------------------------
# 1. Full reactive loop: state → event → re-render → WS patch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reactive_loop_state_change_triggers_rerender_and_ws_patch():
    """State change → StateRenderer.rerender → ws_manager.broadcast_patch."""
    count = state(0)

    def counter_view():
        return Div(Text(f"Count: {count.get()}"), id="counter-box")

    renderer = StateRenderer()
    renderer.bind("counter-box", counter_view, [count])

    # Capture WS broadcasts
    broadcast_calls: list[tuple[str, str]] = []

    async def fake_broadcast(element_id, html):
        broadcast_calls.append((element_id, html))

    ws_manager.broadcast_patch = fake_broadcast  # type: ignore[assignment]

    html = await renderer.rerender("counter-box")

    assert html is not None
    assert "Count: 0" in html
    assert len(broadcast_calls) == 1
    assert broadcast_calls[0][0] == "counter-box"
    assert "Count: 0" in broadcast_calls[0][1]

    # Mutate state and re-render
    count.set(42)
    html2 = await renderer.rerender("counter-box")
    assert "Count: 42" in html2
    assert "Count: 42" in broadcast_calls[1][1]


@pytest.mark.asyncio
async def test_reactive_event_handler_updates_state():
    """Event handler registered via @event updates state cell."""

    counter = state(0)

    @event
    async def increment(element_id, value):
        counter.set(counter.get() + value)

    from voodoo.core.events import event_handlers

    handler = event_handlers["increment"]
    assert handler is not None

    await handler("btn-1", 5)
    assert counter.get() == 5

    await handler("btn-1", 3)
    assert counter.get() == 8


# ---------------------------------------------------------------------------
# 2. Mesh → worker → agent → tool → db chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mesh_to_worker_to_agent_chain(test_db):
    """Mesh event fires → worker task picks it up → agent runs → result recorded."""

    from voodoo.data import Model

    class Lead(Model):
        name: str
        score: int = 0
        email: str = ""

    await Lead._create_table()

    received: list[dict] = []

    @mesh.on("lead.created")
    async def process_lead(payload):
        received.append(payload)
        lead = await Lead.create(name=payload.get("name", "Unknown"))
        return lead.id

    await mesh.emit("lead.created", {"name": "Ada Lovelace"})

    # Mesh events fire synchronously on local handlers
    assert len(received) == 1
    assert received[0]["name"] == "Ada Lovelace"

    # Verify the lead was persisted
    leads = await Lead.all()
    assert len(leads) == 1
    assert leads[0].name == "Ada Lovelace"


@pytest.mark.asyncio
async def test_agent_with_tool_and_db(test_db):
    """Agent calls a tool that persists to the database."""

    from voodoo.data import Model

    class Note(Model):
        title: str
        body: str = ""

    await Note._create_table()

    registry = ToolRegistry()

    async def create_note(title: str, body: str = "") -> str:
        """Create a note in the database."""
        note = await Note.create(title=title, body=body)
        return f"Note #{note.id}: {title}"

    spec = build_spec(create_note)
    registry.register(spec)

    # Mock provider that returns a tool-call marker
    class ToolThenTextProvider(MockProvider):
        def __init__(self):
            super().__init__(model="test")
            self._call = 0

        async def complete(self, messages, **kwargs):
            self._call += 1
            if self._call == 1:
                return ProviderResponse(
                    content='[TOOL: create_note] args: {"title": "Hello", "body": "World"}',
                    model=self.model,
                    tokens_in=5,
                    tokens_out=5,
                    cost=0.0,
                )
            return ProviderResponse(
                content="Note created successfully.",
                model=self.model,
                tokens_in=2,
                tokens_out=2,
                cost=0.0,
            )

    provider = ToolThenTextProvider()
    agent = Agent(
        model="mock:test",
        tools=["create_note"],
        registry=registry,
    )
    agent.provider = provider

    run = await agent.run("Create a note titled Hello")

    assert run.status == "completed"
    assert len(run.tool_calls) == 1
    assert run.tool_calls[0]["name"] == "create_note"
    assert "Note #" in run.tool_calls[0]["result"]

    # Verify DB
    notes = await Note.all()
    assert len(notes) == 1
    assert notes[0].title == "Hello"
    assert notes[0].body == "World"


# ---------------------------------------------------------------------------
# 3. Auth-guarded routes with @page
# ---------------------------------------------------------------------------


def test_auth_guarded_route_redirects_unauthenticated(monkeypatch):
    """A @page with require_auth should redirect unauthenticated users."""

    from voodoo.auth import require_auth
    from voodoo.core.routing import page_registry

    page_registry.clear()

    original_init_db = voodoo.data.init_db

    async def mock_init_db(db_path=":memory:"):
        await original_init_db(db_path)

    monkeypatch.setattr(voodoo.data, "init_db", mock_init_db)

    @page("/protected")
    @require_auth(redirect_url="/login")
    async def protected(request):
        return Text("Secret area")

    fresh_app = create_app()
    with TestClient(fresh_app) as c:
        resp = c.get(
            "/protected", headers={"Accept": "text/html"}, follow_redirects=False
        )
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("location", "")


def test_auth_guarded_route_allows_authenticated(monkeypatch):
    """A @page with require_auth should allow authenticated users."""

    from voodoo.auth import require_auth
    from voodoo.core.routing import page_registry

    page_registry.clear()

    original_init_db = voodoo.data.init_db

    async def mock_init_db(db_path=":memory:"):
        await original_init_db(db_path)

    monkeypatch.setattr(voodoo.data, "init_db", mock_init_db)

    @page("/dashboard")
    @require_auth(redirect_url="/login")
    async def dashboard(request):
        return Text("Welcome to dashboard")

    fresh_app = create_app()
    token = create_access_token({"sub": 1, "username": "admin", "role": "admin"})

    with TestClient(fresh_app) as c:
        resp = c.get(
            "/dashboard",
            headers={
                "Accept": "text/html",
                "Authorization": f"Bearer {token}",
            },
        )
        assert resp.status_code == 200
        assert "Welcome to dashboard" in resp.text


def test_auth_guarded_route_returns_401_for_api(monkeypatch):
    """A @page with require_auth should return 401 JSON for non-HTML requests."""

    from voodoo.auth import require_auth
    from voodoo.core.routing import page_registry

    page_registry.clear()

    original_init_db = voodoo.data.init_db

    async def mock_init_db(db_path=":memory:"):
        await original_init_db(db_path)

    monkeypatch.setattr(voodoo.data, "init_db", mock_init_db)

    @page("/api/protected")
    @require_auth()
    async def api_protected(request):
        return Text("data")

    fresh_app = create_app()

    with TestClient(fresh_app) as c:
        resp = c.get("/api/protected", headers={"Accept": "application/json"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 401


# ---------------------------------------------------------------------------
# 4. MCP tool exposure via ToolRegistry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_tool_exposed_and_callable():
    """A tool registered via @tool is visible through the MCP server's registry."""

    from voodoo import tool

    @tool
    async def calculate_sum(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    # The tool should be in the default registry
    from voodoo.tools.registry import default_registry

    spec = default_registry.get("calculate_sum")
    assert spec is not None
    assert spec.name == "calculate_sum"
    assert "Add two numbers" in spec.description

    # MCP server should list it
    mcp_server = MCPServer(registry=default_registry)
    tools = mcp_server._list_tools()
    tool_names = [t["name"] for t in tools]
    assert "calculate_sum" in tool_names

    # The tool should be callable
    result = await default_registry.call("calculate_sum", a=3, b=4)
    assert result == 7


@pytest.mark.asyncio
async def test_mesh_expose_bridges_to_mcp_and_registry():
    """mesh.expose() auto-bridges to MCP and the tool registry."""

    @mesh.expose(name="lookup_order")
    async def lookup_order(order_id: int) -> dict:
        """Look up an order by ID."""
        return {"order_id": order_id, "status": "shipped"}

    # Should be in mesh exposed functions
    assert "lookup_order" in mesh.exposed_functions

    # Should be in the default tool registry (bridged via MCP)
    from voodoo.tools.registry import default_registry

    spec = default_registry.get("lookup_order")
    assert spec is not None

    # Should be callable from the registry
    result = await default_registry.call("lookup_order", order_id=42)
    assert result["order_id"] == 42
    assert result["status"] == "shipped"


# ---------------------------------------------------------------------------
# 5. Agent run with mock provider and tool calling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_run_with_mock_provider_no_network():
    """Agent.run() with the mock provider produces a completed run (no network)."""

    agent = Agent(model="mock:test")
    run = await agent.run("Hello, agent!")

    assert run.status == "completed"
    assert "Mock response to: Hello, agent!" in run.output
    assert run.provider == "mock"
    assert run.tokens_in > 0
    assert run.tokens_out > 0
    assert run.cost == 0.0


@pytest.mark.asyncio
async def test_agent_stream_with_mock_provider():
    """Agent.stream() yields text events and a final completed event."""

    agent = Agent(model="mock:test")
    events = []
    async for ev in agent.stream("Stream test"):
        events.append(ev)

    text_events = [e for e in events if e.type == "text"]
    completed = [e for e in events if e.type == "completed"]

    assert len(text_events) > 0
    assert len(completed) == 1
    assert "Mock response to: Stream test" in completed[0].data["output"]


@pytest.mark.asyncio
async def test_agent_tool_call_with_mock_and_registry():
    """Agent invokes a tool via the [TOOL: ...] marker convention."""

    registry = ToolRegistry()

    async def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Sunny in {city}"

    spec = build_spec(get_weather)
    registry.register(spec)

    class ToolProvider(MockProvider):
        def __init__(self):
            super().__init__(model="test")
            self._call = 0

        async def complete(self, messages, **kwargs):
            self._call += 1
            if self._call == 1:
                return ProviderResponse(
                    content='[TOOL: get_weather] args: {"city": "London"}',
                    model=self.model,
                    tokens_in=3,
                    tokens_out=3,
                    cost=0.0,
                )
            return ProviderResponse(
                content="The weather in London is sunny.",
                model=self.model,
                tokens_in=2,
                tokens_out=2,
                cost=0.0,
            )

    agent = Agent(model="mock:test", tools=["get_weather"], registry=registry)
    agent.provider = ToolProvider()

    run = await agent.run("What is the weather in London?")

    assert run.status == "completed"
    assert len(run.tool_calls) == 1
    assert run.tool_calls[0]["name"] == "get_weather"
    assert "Sunny in London" in str(run.tool_calls[0]["result"])
    assert "sunny" in run.output.lower()


# ---------------------------------------------------------------------------
# 6. Correlation ID propagation across subsystems
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_correlation_id_propagates_to_telemetry():
    """A trace_id set via trace_id_var appears in telemetry records."""

    trace_id = "test-trace-abc-123"
    token = trace_id_var.set(trace_id)
    try:
        telemetry_store.record_trace("test.span", 1.5, error=False)
        traces = telemetry_store.metrics["custom_traces"]
        assert len(traces) > 0
        last = traces[-1]
        assert last["trace_id"] == trace_id
        assert last["name"] == "test.span"
    finally:
        trace_id_var.reset(token)


@pytest.mark.asyncio
async def test_correlation_id_propagates_to_agent_run():
    """Agent runs capture the current trace_id in their telemetry record."""

    trace_id = "agent-trace-xyz"
    token = trace_id_var.set(trace_id)
    try:
        agent = Agent(model="mock:test")
        run = await agent.run("Trace test")

        assert run.trace_id == trace_id

        # The telemetry store should have the run with the trace_id
        agent_runs = telemetry_store.metrics["agent_runs"]
        recent = [r for r in agent_runs if r.get("run_id") == run.run_id]
        assert len(recent) == 1
        assert recent[0]["trace_id"] == trace_id
    finally:
        trace_id_var.reset(token)


@pytest.mark.asyncio
async def test_correlation_id_propagates_to_tool_call_telemetry():
    """Tool call telemetry records carry the current trace_id."""

    trace_id = "tool-trace-456"
    token = trace_id_var.set(trace_id)
    try:
        telemetry_store.record_tool_call("my_tool", 2.5, error=False)
        tool_calls = telemetry_store.metrics["tool_calls"]
        last = tool_calls[-1]
        assert last["trace_id"] == trace_id
        assert last["tool"] == "my_tool"
        assert last["latency_ms"] == 2.5
    finally:
        trace_id_var.reset(token)


@pytest.mark.asyncio
async def test_correlation_id_propagates_to_queue():
    """Enqueue captures the current trace_id and stores it in the queue envelope."""

    from voodoo.queue import _queues, enqueue

    _queues["test_corr_queue"] = asyncio.Queue()

    trace_id = "queue-trace-789"
    token = trace_id_var.set(trace_id)
    try:
        await enqueue("test_corr_queue", {"data": "hello"})
    finally:
        trace_id_var.reset(token)

    # Drain the queue — the item should carry the trace_id from the envelope
    item = await _queues["test_corr_queue"].get()
    _queues["test_corr_queue"].task_done()

    assert item["trace_id"] == trace_id
    assert item["payload"] == {"data": "hello"}


@pytest.mark.asyncio
async def test_full_chain_correlation_id():
    """Full chain: trace_id → agent → tool call → telemetry, all correlated."""

    trace_id = "full-chain-trace-001"
    token = trace_id_var.set(trace_id)
    try:
        registry = ToolRegistry()

        async def persist_record(title: str) -> str:
            """Persist a record."""
            return f"persisted:{title}"

        spec = build_spec(persist_record)
        registry.register(spec)

        class ChainProvider(MockProvider):
            def __init__(self):
                super().__init__(model="test")
                self._call = 0

            async def complete(self, messages, **kwargs):
                self._call += 1
                if self._call == 1:
                    return ProviderResponse(
                        content='[TOOL: persist_record] args: {"title": "Test"}',
                        model=self.model,
                        tokens_in=1,
                        tokens_out=1,
                        cost=0.0,
                    )
                return ProviderResponse(
                    content="Record persisted.",
                    model=self.model,
                    tokens_in=1,
                    tokens_out=1,
                    cost=0.0,
                )

        agent = Agent(model="mock:test", tools=["persist_record"], registry=registry)
        agent.provider = ChainProvider()

        run = await agent.run("Persist a record titled Test")

        # Agent run carries the trace_id
        assert run.trace_id == trace_id

        # Tool call telemetry carries the trace_id
        tool_calls = telemetry_store.metrics["tool_calls"]
        recent_tool = [tc for tc in tool_calls if tc.get("trace_id") == trace_id]
        assert len(recent_tool) >= 1
        assert recent_tool[-1]["tool"] == "persist_record"

        # Agent run telemetry carries the trace_id
        agent_runs = telemetry_store.metrics["agent_runs"]
        recent_run = [r for r in agent_runs if r.get("run_id") == run.run_id]
        assert len(recent_run) == 1
        assert recent_run[0]["trace_id"] == trace_id
    finally:
        trace_id_var.reset(token)
