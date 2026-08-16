"""Tool Registry — the single source of truth for tools.

A ``ToolSpec`` is the introspectable metadata that powers the Agent (S7),
MCP, CLI, docs, and telemetry. The ``@tool`` decorator builds a ``ToolSpec``
from a function's type hints and registers it in a registry.

One tool definition serves four consumers: direct Python call, agent run,
MCP consumer, and mesh exposure.
"""

from __future__ import annotations

import inspect
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

from voodoo.core.errors import ToolError

__all__ = ["ToolSpec", "ToolRegistry", "default_registry"]


# ---------------------------------------------------------------------------
# Type → JSON-schema mapping
# ---------------------------------------------------------------------------

_PRIMITIVE_SCHEMAS: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    bytes: "string",
    type(None): "null",
}


def _annotation_to_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python type annotation into a JSON-schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is None:
        return {}

    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # Optional / Union (includes ``X | None`` via types.UnionType on 3.10+)
    if origin is typing.Union or origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            schema = dict(_annotation_to_schema(non_none[0]))
            schema["nullable"] = True
            return schema
        return {"type": "object"}

    if origin is list:
        item = _annotation_to_schema(args[0]) if args else {}
        return {"type": "array", "items": item}

    if origin is tuple:
        return {"type": "array"}

    if origin is dict:
        return {"type": "object"}

    if annotation in _PRIMITIVE_SCHEMAS:
        return {"type": _PRIMITIVE_SCHEMAS[annotation]}

    if isinstance(annotation, type):
        return {"type": "string", "python_type": annotation.__name__}

    return {"type": "string"}


def _build_schemas(func: Callable[..., Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive input/output JSON schemas from a function's type hints."""
    try:
        hints = get_type_hints(func)
    except Exception:  # noqa: BLE001 — unresolved forward refs fall back to raw
        hints = getattr(func, "__annotations__", {}) or {}

    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        ann = hints.get(name, param.annotation)
        properties[name] = _annotation_to_schema(ann)
        if param.default is inspect.Parameter.empty:
            required.append(name)

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required

    return_annotation = hints.get("return", sig.return_annotation)
    output_schema = _annotation_to_schema(return_annotation)
    return input_schema, output_schema


def _source_metadata(func: Callable[..., Any]) -> str:
    """``module:file:line`` provenance for telemetry and debugging."""
    module = getattr(func, "__module__", "unknown")
    try:
        file = inspect.getsourcefile(inspect.unwrap(func)) or "<unknown>"
        line = inspect.getsourcelines(inspect.unwrap(func))[1]
    except (OSError, TypeError):  # noqa: UP024 — broad: builtins/C extensions
        line = 0
        file = "<unknown>"
    return f"{module}:{file}:{line}"


# ---------------------------------------------------------------------------
# ToolSpec
# ---------------------------------------------------------------------------


@dataclass
class ToolSpec:
    """Introspectable metadata for a tool.

    Fields follow the internal contract (§6.3):
    ``name, description, input_schema, output_schema, permissions, source,
    version``. ``func`` is held so the registry can invoke the tool.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permissions: list[str] = field(default_factory=list)
    source: str = ""
    version: str = "1.0.0"
    func: Callable[..., Any] | None = None

    @property
    def identity(self) -> str:
        """Stable string identity (not a memory address)."""
        return f"{self.source.split(':')[0]}:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """Schema-only projection (drops the callable) for MCP/docs/telemetry."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permissions": list(self.permissions),
            "source": self.source,
            "version": self.version,
        }


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Single source of truth for registered tools.

    Consumers (Agent, MCP, CLI, docs, telemetry) read from a registry rather
    than importing tool functions directly.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        """Register a ``ToolSpec``. Re-registering overwrites by name."""
        if not spec.name:
            raise ToolError("ToolSpec.name must be a non-empty string")
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> ToolSpec | None:
        """Return a registered ``ToolSpec`` by name, or ``None``."""
        return self._tools.get(name)

    def all(self) -> list[ToolSpec]:
        """Return every registered ``ToolSpec`` (insertion order)."""
        return list(self._tools.values())

    def names(self) -> list[str]:
        """Return every registered tool name."""
        return list(self._tools.keys())

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    async def call(self, name: str, /, **kwargs: Any) -> Any:
        """Invoke a registered tool by name with keyword arguments.

        Awaits coroutine results; plain return values are returned as-is.
        Raises ``ToolError`` if the tool is not registered.
        """
        spec = self._tools.get(name)
        if spec is None or spec.func is None:
            raise ToolError(f"Tool {name!r} is not registered")
        result = spec.func(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result


# Module-level default registry. ``@tool`` registers here; subsystems that
# need isolation (tests, multi-tenant) construct their own ``ToolRegistry``.
default_registry = ToolRegistry()


def build_spec(
    func: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
    permissions: list[str] | None = None,
    version: str = "1.0.0",
) -> ToolSpec:
    """Construct a ``ToolSpec`` from a function and optional metadata."""
    input_schema, output_schema = _build_schemas(func)
    if description is not None:
        desc = description
    else:
        doc = (func.__doc__ or "").strip()
        desc = doc.splitlines()[0] if doc else ""
    return ToolSpec(
        name=name or func.__name__,
        description=desc,
        input_schema=input_schema,
        output_schema=output_schema,
        permissions=list(permissions) if permissions else [],
        source=_source_metadata(func),
        version=version,
        func=func,
    )
