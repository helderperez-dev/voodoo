# Tools

## What it is

The `@tool` decorator turns a function into an introspectable `ToolSpec` registered in a `ToolRegistry`. One tool definition serves four consumers: direct Python calls, agent runs, MCP consumers, and mesh exposure.

## Minimal example

```python
from voodoo import tool


@tool
async def search_leads(query: str) -> list[dict]:
    """Search for leads matching a query."""
    return [{"name": "Ada", "email": "ada@x.io"}]


# Still callable as plain Python
results = await search_leads("Ada")

# Also available to agents and MCP
from voodoo.tools.registry import default_registry

spec = default_registry.get("search_leads")
```

## Common usage

### With permissions

```python
@tool(permissions=["leads:read"])
async def read_lead(lead_id: int) -> dict:
    """Read a lead by ID."""
    return {"id": lead_id, "name": "Ada"}
```

### Custom name and description

```python
@tool(name="lookup_lead", description="Look up a lead by ID")
async def get_lead(lead_id: int) -> dict: ...
```

### Direct registry call

```python
from voodoo.tools.registry import default_registry

result = await default_registry.call("search_leads", query="test")
```

### Custom registry

```python
from voodoo.tools.registry import ToolRegistry

registry = ToolRegistry()
spec = build_spec(my_function)
registry.register(spec)
result = await registry.call("my_function", arg1="value")
```

## How it works

1. `@tool` inspects the function's type hints and builds JSON schemas (input + output).
2. The `ToolSpec` is registered in the `default_registry`.
3. The original function remains callable as plain Python.
4. When an `Agent` is given a tool name, it looks up the spec, sends the schema to the LLM, and calls the function when the LLM requests it.

## Advanced

### ToolSpec fields

```python
spec.name  # "search_leads"
spec.description  # from docstring
spec.input_schema  # JSON schema dict
spec.output_schema  # JSON schema dict
spec.permissions  # ["leads:read"]
spec.source  # "module:file:line" provenance
spec.to_dict()  # schema-only projection for MCP/docs
```

### One tool, many consumers

```python
@tool
async def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


# 1. Direct Python call
result = await calculate(1, 2)

# 2. Agent tool calling
agent = Agent(model="mock:test", tools=["calculate"])
run = await agent.run("Add 1 and 2")

# 3. MCP consumer (auto-registered)
# 4. Mesh exposure
mesh.expose(name="calculate")(calculate)
```

## API reference

- `tool(func=None, *, name=None, description=None, permissions=None, version="1.0.0", registry=None)` — decorator.
- `ToolSpec` — introspectable metadata (name, description, schemas, permissions, source).
- `ToolRegistry` — registry for tools.
  - `register(spec)` — add a tool.
  - `get(name)` — lookup by name.
  - `all()` — list all tools.
  - `call(name, **kwargs)` — invoke a tool.
- `build_spec(func, *, name=None, ...)` — build a `ToolSpec` from a function.
- `default_registry` — the global `ToolRegistry` instance.
