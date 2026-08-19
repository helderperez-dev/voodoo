# AI Agents & Tools Instructions

> **Read this before:** touching `src/voodoo/ai/`, `src/voodoo/tools/`, `src/voodoo/mcp/`, or anything related to agents, LLM providers, or tool registration.

---

## Agent System (`voodoo.ai.agent`)

### The `Agent` class

```python
from voodoo import Agent

agent = Agent(
    model="openai:gpt-4o",  # provider:model format
    tools=[search_web, send_email],  # list of @tool-decorated functions
    system_prompt="You are a helpful assistant.",
    max_iterations=10,
    capabilities=["web.search", "email.send"],
)

run = await agent.run("Find the latest Python release and email me the link.")
```

### AgentRun dataclass

Every agent run produces an `AgentRun`:

| Field | Type | Description |
|---|---|---|
| `run_id` | `str` | Unique run identifier |
| `model` | `str` | Full model string (`"openai:gpt-4o"`) |
| `provider` | `str` | Provider name (`"openai"`) |
| `prompt` | `str` | Input prompt |
| `output` | `str` | Final response |
| `tokens_in` | `int` | Input tokens |
| `tokens_out` | `int` | Output tokens |
| `cost` | `float` | Estimated cost in USD |
| `tool_calls` | `list[dict]` | Tool call history |
| `timings` | `dict` | Timing breakdown |
| `trace_id` | `str` | Correlation ID |

### Agent states (`AgentState` StrEnum)

```
idle → running → tool_calling → thinking → completed / error
```

### Agent events (`AgentEvent`)

```python
async for event in agent.stream("Hello"):
    if event.type == "text":
        print(event.data, end="")
    elif event.type == "tool_started":
        print(f"Calling tool: {event.data['name']}")
    elif event.type == "tool_finished":
        print(f"Tool result: {event.data['result']}")
    elif event.type == "thinking":
        print(f"Thinking: {event.data}")
    elif event.type == "error":
        print(f"Error: {event.data}")
    elif event.type == "completed":
        break
```

Event types: `text`, `tool_started`, `tool_finished`, `thinking`, `error`, `completed`.

---

## Agent Execution Loop

```
1. Build messages (system_prompt + user prompt)
2. Call provider.complete() or provider.stream()
3. If provider returns a tool call:
   a. Look up tool in ToolRegistry
   b. Execute tool with arguments
   c. Feed result back to provider
   d. Go to step 2
4. If provider returns text (no tool call):
   a. Return as final answer
5. If max_iterations reached:
   a. Return current state with warning
```

Every agent run flows through the `ExecutionEngine` and produces an `Execution` record with intent `"agent.run"`.

---

## LLM Providers (`voodoo.ai.providers`)

### Architecture

```
LLMProvider (ABC)
├── name: str (class attribute)
├── complete(messages, **kwargs) → ProviderResponse
└── stream(messages, **kwargs) → AsyncIterator[ProviderEvent]

Implementations:
├── MockProvider       — deterministic, no network, cost=0
├── OpenAIProvider     — lazy openai import, AsyncOpenAI
├── AnthropicProvider  — lazy anthropic import
├── GeminiProvider     — lazy google-generativeai import
└── OllamaProvider     — lazy ollama import
```

### Factory

```python
from voodoo.ai.providers import get_provider

provider = get_provider("openai:gpt-4o")
# 1. Split "openai:gpt-4o" → provider="openai", model="gpt-4o"
# 2. Look up _PROVIDER_CLASSES["openai"] → "voodoo.ai.providers.openai.OpenAIProvider"
# 3. importlib.import_module() — lazy load
# 4. Instantiate with model="gpt-4o"
```

### ProviderResponse

```python
@dataclass
class ProviderResponse:
    content: str
    tool_calls: list[dict] | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    model: str = ""
    finish_reason: str = "stop"
```

### ProviderEvent (streaming)

```python
@dataclass
class ProviderEvent:
    type: str  # "text", "tool_call", "done"
    data: str | dict
```

### MockProvider

`MockProvider` is the default for tests — deterministic, no network:

```python
from voodoo.ai.providers.mock import MockProvider

provider = MockProvider(
    responses=["Hello!", "How can I help?"],
    model="mock:default",
)
```

`ToolThenTextProvider` subclass simulates tool-call sequences:

```python
from voodoo.ai.providers.mock import ToolThenTextProvider

provider = ToolThenTextProvider(
    tool_call={"name": "search", "args": {"q": "python"}},
    final_text="Found it!",
)
```

### Missing SDK handling

```python
try:
    import openai
except ImportError:
    raise ConfigurationError(
        "openai not installed. Install with: uv pip install voodoo-framework[ai]"
    )
```

---

## Tool Registry (`voodoo.ai.tools.registry`)

### The `@tool` decorator

```python
from voodoo.ai.tools.registry import tool


@tool
async def search_web(query: str, max_results: int = 10) -> dict:
    """Search the web for a query.

    Parameters:
        query: The search query string.
        max_results: Maximum number of results to return.
    """
    # implementation
    return {"results": [...]}
```

The decorator:
1. Extracts the function name, docstring, and type hints.
2. Builds a `ToolSpec` with JSON schema for parameters.
3. Registers in `default_registry` (the singleton `ToolRegistry`).

### ToolSpec

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema
    func: Callable[..., Awaitable[Any]]
```

### Registry API

```python
from voodoo.ai.tools.registry import default_registry

# Register
default_registry.register(my_tool_func)

# Look up
spec = default_registry.get("search_web")

# List all
specs = default_registry.list_all()

# Execute
result = await default_registry.execute("search_web", query="python", max_results=5)
```

### Compatibility shim

`voodoo/tools/registry.py` replaces itself in `sys.modules` with `voodoo.ai.tools.registry`:

```python
# voodoo/tools/registry.py
import sys
from voodoo.ai.tools.registry import *  # noqa: F401,F403

sys.modules[__name__] = sys.modules["voodoo.ai.tools.registry"]
```

This ensures `voodoo.tools.registry` and `voodoo.ai.tools.registry` share the same `default_registry` singleton.

---

## MCP Integration (`voodoo.mcp`)

### MCPServer

```python
from voodoo.mcp import mcp


@mcp.tool()
async def search_web(query: str) -> dict:
    """Search the web."""
    ...


@mcp.resource("voodoo://status")
async def get_status() -> str:
    return "healthy"
```

The `@mcp.tool()` decorator registers in both `MCPServer.tools` and `ToolRegistry`, so tools are available to both MCP clients and AI agents.

### SSE endpoints

- `/mcp/sse` — SSE stream for MCP events
- `/mcp/messages` — POST endpoint for MCP requests

### Protocol methods

- `initialize` — handshake
- `tools/list` — list available tools
- `tools/call` — execute a tool
- `resources/list` — list resources
- `resources/read` — read a resource

### Auto-bridge from mesh

```python
from voodoo.mesh import mesh


@mesh.expose("search.web")
async def search_web(query: str) -> dict: ...
```

`mesh.expose()` auto-bridges the function to MCP, making it available as an MCP tool without double-registration.

---

## Mesh Integration (`voodoo.mesh`)

### MeshNetwork

```python
from voodoo.mesh import mesh


# Subscribe to namespaced events
@mesh.on("agent.started")
async def on_agent_started(envelope): ...


# Broadcast/emit events
await mesh.broadcast("agent.completed", {"run_id": "abc123"})

# Connect to remote mesh
client = await mesh.connect("wss://remote.mesh/voodoo")
```

### Event namespacing

All events must use dotted namespaces:
- ✅ `"agent.started"`, `"tool.completed"`, `"mesh.connected"`
- ❌ `"started"`, `"completed"`, `"connected"`

`_validate_namespace()` enforces this — bare event names raise `MeshError`.

### Envelope

```python
@dataclass
class Envelope:
    event: str  # namespaced event name
    data: dict
    trace_id: str  # correlation ID
    timestamp: str
    source: str  # sender identifier
```

---

## When Adding AI Features

1. **Use the Agent class** — Don't call providers directly. The Agent handles the execution loop, tool calls, and telemetry.
2. **Register tools** — Use `@tool` decorator. The registry handles schema generation.
3. **Use MockProvider for tests** — Never make real API calls in tests.
4. **Propagate trace_id** — Agent runs inherit `trace_id` from the execution context.
5. **Namespace events** — All mesh/MCP events use dotted namespaces.
6. **Lazy import SDKs** — `openai`, `anthropic`, `google-generativeai`, `ollama` are imported at function level.
7. **Cost tracking** — `AgentRun` records `cost`, `tokens_in`, `tokens_out`. Use these for budget enforcement.
8. **Capabilities** — Agents declare required capabilities. The `CapabilityResolver` checks them before execution.

---

## Testing AI Features

### Mock provider patterns

```python
async def test_agent_basic():
    agent = Agent(
        model="mock:default",
        tools=[],
        system_prompt="You are helpful.",
    )
    run = await agent.run("Hello")
    assert run.output == "Hello! How can I help you?"


async def test_agent_with_tool():
    provider = ToolThenTextProvider(
        tool_call={"name": "search", "args": {"q": "python"}},
        final_text="Found Python!",
    )
    agent = Agent(model="mock:default", tools=[search_tool])
    agent.provider = provider
    run = await agent.run("Search for Python")
    assert "Found Python!" in run.output
```

### Tool testing

```python
async def test_tool_registration():
    from voodoo.ai.tools.registry import ToolRegistry

    registry = ToolRegistry()  # fresh instance

    @tool
    async def my_tool(x: int) -> int:
        """Double a number.

        Parameters:
            x: The number to double.
        """
        return x * 2

    registry.register(my_tool)
    spec = registry.get("my_tool")
    assert spec.name == "my_tool"
    assert "Double a number" in spec.description
```

### Isolation

The `_isolated_registry` autouse fixture in `tests/conftest.py` monkeypatches a fresh `ToolRegistry` for each test, preventing cross-test tool leakage.
