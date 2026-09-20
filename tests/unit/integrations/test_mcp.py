"""Tests for MCP + ToolRegistry integration: tool registration, schema generation, tools/list."""

from __future__ import annotations

import asyncio

import pytest

from voodoo.mcp import MCPServer
from voodoo.tools.registry import ToolRegistry, ToolSpec, build_spec

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_registry():
    return ToolRegistry()


@pytest.fixture
def fresh_mcp(fresh_registry):
    """MCPServer with a fresh, isolated registry (no route registration side effects)."""
    server = MCPServer.__new__(MCPServer)
    server.name = "test-mcp"
    server.version = "1.0.0"
    server.tools = {}
    server.resources = {}
    server.registry = fresh_registry
    server.sessions = {}
    return server


# ---------------------------------------------------------------------------
# tool() decorator registers in both self.tools and ToolRegistry
# ---------------------------------------------------------------------------


def test_mcp_tool_registers_in_registry(fresh_mcp, fresh_registry):
    @fresh_mcp.tool()
    def my_tool(query: str) -> str:
        """Search for something."""
        return f"result:{query}"

    assert "my_tool" in fresh_mcp.tools
    assert "my_tool" in fresh_registry
    assert fresh_registry.get("my_tool") is not None


def test_mcp_tool_with_custom_name(fresh_mcp, fresh_registry):
    @fresh_mcp.tool(name="custom_tool_name")
    def some_func(x: int) -> int:
        """Doubler."""
        return x * 2

    assert "custom_tool_name" in fresh_mcp.tools
    assert "custom_tool_name" in fresh_registry


def test_mcp_tool_attaches_spec(fresh_mcp):
    @fresh_mcp.tool()
    def my_tool(query: str) -> str:
        """Search."""
        return query

    assert "spec" in fresh_mcp.tools["my_tool"]
    assert isinstance(fresh_mcp.tools["my_tool"]["spec"], ToolSpec)


# ---------------------------------------------------------------------------
# tools/list — schema generation from ToolSpec
# ---------------------------------------------------------------------------


def test_list_tools_includes_mcp_tools(fresh_mcp):
    @fresh_mcp.tool()
    def search(query: str) -> str:
        """Search."""
        return query

    tools = fresh_mcp._list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "search"
    assert tools[0]["description"] == "Search."


def test_list_tools_includes_registry_tools(fresh_mcp, fresh_registry):
    """Tools registered directly in the registry (via @tool) appear in tools/list."""

    def fetch_data(id: int) -> str:
        """Fetch data by id."""
        return f"data:{id}"

    spec = build_spec(fetch_data, name="fetch_data")
    fresh_registry.register(spec)

    tools = fresh_mcp._list_tools()
    names = [t["name"] for t in tools]
    assert "fetch_data" in names


def test_list_tools_no_duplicates(fresh_mcp, fresh_registry):
    """A tool registered via mcp.tool() appears once even if also in registry."""

    @fresh_mcp.tool()
    def my_tool(x: int) -> int:
        """Doubler."""
        return x * 2

    tools = fresh_mcp._list_tools()
    names = [t["name"] for t in tools]
    assert names.count("my_tool") == 1


def test_list_tools_generates_input_schema_from_typespec(fresh_mcp):
    @fresh_mcp.tool()
    def typed_tool(query: str, limit: int) -> str:
        """Typed tool."""
        return f"{query}:{limit}"

    tools = fresh_mcp._list_tools()
    tool = tools[0]
    assert "inputSchema" in tool
    assert tool["inputSchema"]["type"] == "object"
    assert "query" in tool["inputSchema"]["properties"]
    assert tool["inputSchema"]["properties"]["query"]["type"] == "string"
    assert tool["inputSchema"]["properties"]["limit"]["type"] == "integer"
    assert "query" in tool["inputSchema"]["required"]
    assert "limit" in tool["inputSchema"]["required"]


# ---------------------------------------------------------------------------
# tools/call — can invoke tools from both self.tools and registry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_tool_from_self_tools(fresh_mcp):
    @fresh_mcp.tool()
    def doubler(x: int) -> int:
        """Double a number."""
        return x * 2

    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "doubler", "arguments": {"x": 5}},
        },
        queue,
    )
    result = await queue.get()
    assert result["result"]["content"][0]["text"] == "10"


@pytest.mark.asyncio
async def test_call_tool_from_registry_only(fresh_mcp, fresh_registry):
    """A tool registered only in the registry (not via mcp.tool) can still be called."""

    def registry_tool(x: int) -> int:
        """Triple a number."""
        return x * 3

    spec = build_spec(registry_tool, name="registry_tool")
    fresh_registry.register(spec)

    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "registry_tool", "arguments": {"x": 4}},
        },
        queue,
    )
    result = await queue.get()
    assert result["result"]["content"][0]["text"] == "12"


@pytest.mark.asyncio
async def test_call_unknown_tool_returns_error(fresh_mcp):
    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "nonexistent", "arguments": {}},
        },
        queue,
    )
    result = await queue.get()
    assert "error" in result
    assert result["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_call_async_tool(fresh_mcp):
    @fresh_mcp.tool()
    async def async_tool(query: str) -> str:
        """Async tool."""
        return f"async:{query}"

    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "async_tool", "arguments": {"query": "hi"}},
        },
        queue,
    )
    result = await queue.get()
    assert result["result"]["content"][0]["text"] == "async:hi"


@pytest.mark.asyncio
async def test_call_tool_with_error(fresh_mcp):
    @fresh_mcp.tool()
    def failing_tool() -> str:
        """Always fails."""
        raise ValueError("tool error")

    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "failing_tool", "arguments": {}},
        },
        queue,
    )
    result = await queue.get()
    assert "error" in result
    assert "tool error" in result["error"]["message"]


# ---------------------------------------------------------------------------
# Initialize + tools/list full flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_returns_server_info(fresh_mcp):
    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        },
        queue,
    )
    result = await queue.get()
    assert result["result"]["serverInfo"]["name"] == "test-mcp"


@pytest.mark.asyncio
async def test_tools_list_full_flow(fresh_mcp):
    @fresh_mcp.tool()
    def tool_a(x: str) -> str:
        """Tool A."""
        return x

    @fresh_mcp.tool()
    def tool_b(y: int) -> int:
        """Tool B."""
        return y

    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        queue,
    )
    result = await queue.get()
    tools = result["result"]["tools"]
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert names == {"tool_a", "tool_b"}


# ---------------------------------------------------------------------------
# Resource handling (existing functionality preserved)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resources_list(fresh_mcp):
    @fresh_mcp.resource(uri="test://data", name="test_data")
    def get_data():
        return "data content"

    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}},
        queue,
    )
    result = await queue.get()
    assert result["result"]["resources"][0]["uri"] == "test://data"


@pytest.mark.asyncio
async def test_resource_read(fresh_mcp):
    @fresh_mcp.resource(uri="test://info")
    def get_info():
        return "info text"

    queue = asyncio.Queue()
    await fresh_mcp._handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/read",
            "params": {"uri": "test://info"},
        },
        queue,
    )
    result = await queue.get()
    assert result["result"]["contents"][0]["text"] == "info text"
