# MCP

## What it is

Voodoo includes a built-in Model Context Protocol (MCP) server. Every `@tool` is automatically exposed to MCP consumers (AI IDEs, other applications) via SSE. The MCP server consumes the same `ToolRegistry` as agents and Python code.

## Minimal example

```python
from voodoo import tool


@tool
async def get_user(id: int) -> dict:
    """Get a user by ID."""
    return {"id": id, "name": "Ada"}
```

This tool is now available:
- As a direct Python call
- To agents via `Agent(tools=["get_user"])`
- To MCP consumers via the `/mcp/sse` endpoint

## Common usage

### MCP server endpoints

- `GET /mcp/sse` — SSE stream for MCP session
- `POST /mcp/messages?sessionId=...` — send JSON-RPC messages

### Using the MCP client

```python
from voodoo.mcp import MCPClient

client = MCPClient("http://localhost:8000/mcp/messages")
result = await client.call_tool("get_user", {"id": 1})
```

### Registering MCP resources

```python
from voodoo.mcp import mcp


@mcp.resource("voodoo://config", name="app_config")
def app_config():
    return json.dumps({"version": "1.0.0"})
```

### MCP protocol methods

- `initialize` — start a session
- `tools/list` — list all tools (from registry + self.tools)
- `tools/call` — invoke a tool
- `resources/list` — list resources
- `resources/read` — read a resource

## How it works

1. The `MCPServer` is instantiated at import time as the `mcp` singleton.
2. When `@tool` registers a `ToolSpec` in the default registry, the MCP server's `_list_tools()` includes it.
3. MCP consumers connect via SSE, then send JSON-RPC messages.
4. Tool calls are dispatched to the same functions that Python and agents use.

## Advanced

### Auto-bridge from mesh

```python
from voodoo.mesh import mesh


@mesh.expose(name="sync_crm")
async def sync_crm(contact_id: int) -> str:
    """Sync a contact to CRM."""
    return "synced"
```

`mesh.expose()` auto-bridges the function to MCP, making it available as both a mesh remote-call and an MCP tool.

### Custom registry

```python
from voodoo.mcp import MCPServer
from voodoo.tools.registry import ToolRegistry

custom_registry = ToolRegistry()
mcp_server = MCPServer(registry=custom_registry)
```

## API reference

- `mcp` — the global `MCPServer` singleton.
- `MCPServer(name="voodoo-mcp", version="1.0.0", registry=None)` — create an MCP server.
- `mcp.tool(name=None, description=None)` — register an MCP tool (also registers in ToolRegistry).
- `mcp.resource(uri, name=None)` — register a resource.
- `MCPClient(endpoint_url)` — client for calling MCP tools.
