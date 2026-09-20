"""Tests for the Tool Registry: @tool, ToolSpec, permissions, registry."""

from __future__ import annotations

import pytest

from voodoo import ToolRegistry, ToolSpec, tool
from voodoo.tools import registry as tools_module


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch):
    """Give each test a fresh default registry so registrations don't leak."""
    fresh = ToolRegistry()
    monkeypatch.setattr(tools_module, "default_registry", fresh)
    yield fresh


# ---------------------------------------------------------------------------
# @tool decorator — bare and parametrized
# ---------------------------------------------------------------------------


def test_bare_tool_decorator_registers_and_returns_callable():
    @tool
    async def search_leads(query: str) -> list[dict]:
        """Search for leads."""
        return [{"id": 1, "query": query}]

    # Original function is still callable.
    import asyncio

    result = asyncio.run(search_leads("acme"))
    assert result == [{"id": 1, "query": "acme"}]

    # Spec attached.
    spec: ToolSpec = search_leads.__tool_spec__  # type: ignore[attr-defined]
    assert isinstance(spec, ToolSpec)
    assert spec.name == "search_leads"
    assert spec.description == "Search for leads."
    assert "search_leads" in tools_module.default_registry


def test_parametrized_tool_decorator_with_permissions():
    @tool(permissions=["leads:read"])
    async def read_lead(lead_id: int) -> dict:
        """Read a lead."""
        return {"id": lead_id}

    spec: ToolSpec = read_lead.__tool_spec__  # type: ignore[attr-defined]
    assert spec.permissions == ["leads:read"]
    assert spec.name == "read_lead"


def test_parametrized_tool_decorator_with_explicit_name_and_description():
    @tool(name="find_leads", description="Find leads by query.")
    async def search(query: str) -> list[str]:
        return [query]

    spec: ToolSpec = search.__tool_spec__  # type: ignore[attr-defined]
    assert spec.name == "find_leads"
    assert spec.description == "Find leads by query."


def test_tool_registers_in_custom_registry():
    custom = ToolRegistry()

    @tool(registry=custom)
    async def ping(target: str) -> str:
        """Ping."""
        return f"pong:{target}"

    assert "ping" in custom
    assert "ping" not in tools_module.default_registry


# ---------------------------------------------------------------------------
# ToolSpec schema derivation from typing
# ---------------------------------------------------------------------------


def test_input_schema_derived_from_type_hints():
    @tool
    async def create_lead(name: str, score: float) -> dict:
        """Create."""
        return {}

    spec: ToolSpec = create_lead.__tool_spec__  # type: ignore[attr-defined]
    props = spec.input_schema["properties"]
    assert props["name"] == {"type": "string"}
    assert props["score"] == {"type": "number"}
    assert set(spec.input_schema["required"]) == {"name", "score"}


def test_output_schema_derived_from_return_annotation():
    @tool
    async def list_leads() -> list[str]:
        """List."""
        return []

    spec: ToolSpec = list_leads.__tool_spec__  # type: ignore[attr-defined]
    assert spec.output_schema == {"type": "array", "items": {"type": "string"}}


def test_optional_param_not_required_and_nullable():
    @tool
    async def search(query: str, limit: int | None = None) -> str:
        """Search."""
        return query

    spec: ToolSpec = search.__tool_spec__  # type: ignore[attr-defined]
    assert "limit" not in spec.input_schema.get("required", [])
    assert spec.input_schema["properties"]["limit"]["nullable"] is True


def test_source_metadata_is_string():
    @tool
    async def noop(x: int) -> int:
        """Noop."""
        return x

    spec: ToolSpec = noop.__tool_spec__  # type: ignore[attr-defined]
    assert isinstance(spec.source, str)
    assert spec.source.split(":")[0] == noop.__module__
    assert spec.version == "1.0.0"


def test_identity_is_stable_string():
    @tool
    async def fn(x: int) -> int:
        """Fn."""
        return x

    spec: ToolSpec = fn.__tool_spec__  # type: ignore[attr-defined]
    assert isinstance(spec.identity, str)
    assert spec.identity.endswith(":fn")


def test_to_dict_drops_callable():
    @tool
    async def fn(x: int) -> int:
        """Fn."""
        return x

    spec: ToolSpec = fn.__tool_spec__  # type: ignore[attr-defined]
    d = spec.to_dict()
    assert "func" not in d
    assert d["name"] == "fn"
    assert d["permissions"] == []


# ---------------------------------------------------------------------------
# ToolRegistry behavior
# ---------------------------------------------------------------------------


def test_registry_register_get_all_names():
    reg = ToolRegistry()

    @tool(registry=reg)
    async def a(x: int) -> int:
        """A."""
        return x

    @tool(registry=reg)
    async def b(y: str) -> str:
        """B."""
        return y

    assert reg.names() == ["a", "b"]
    assert len(reg.all()) == 2
    assert reg.get("a").name == "a"
    assert reg.get("missing") is None
    assert "a" in reg
    assert len(reg) == 2


def test_registry_register_overwrites_by_name():
    reg = ToolRegistry()
    reg.register(
        ToolSpec(name="dup", description="v1", input_schema={}, output_schema={})
    )
    reg.register(
        ToolSpec(name="dup", description="v2", input_schema={}, output_schema={})
    )
    assert len(reg) == 1
    assert reg.get("dup").description == "v2"


def test_registry_register_rejects_empty_name():
    from voodoo.core.errors import ToolError

    reg = ToolRegistry()
    with pytest.raises(ToolError):
        reg.register(
            ToolSpec(name="", description="x", input_schema={}, output_schema={})
        )


@pytest.mark.asyncio
async def test_registry_call_async_tool():
    reg = ToolRegistry()

    @tool(registry=reg)
    async def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    result = await reg.call("add", a=2, b=3)
    assert result == 5


@pytest.mark.asyncio
async def test_registry_call_sync_tool():
    reg = ToolRegistry()

    @tool(registry=reg)
    def sync_add(a: int, b: int) -> int:
        """Add sync."""
        return a + b

    result = await reg.call("sync_add", a=4, b=5)
    assert result == 9


@pytest.mark.asyncio
async def test_registry_call_unknown_raises_toolerror():
    from voodoo.core.errors import ToolError

    reg = ToolRegistry()
    with pytest.raises(ToolError):
        await reg.call("does_not_exist", x=1)


def test_tool_with_no_docstring_has_empty_description():
    @tool
    async def nodoc(x: int) -> int:
        return x

    spec: ToolSpec = nodoc.__tool_spec__  # type: ignore[attr-defined]
    assert spec.description == ""
