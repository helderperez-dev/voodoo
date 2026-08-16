"""Voodoo tools — ``@tool`` decorator and Tool Registry.

Usage::

    from voodoo import tool

    @tool
    async def search_leads(query: str) -> list[dict]:
        \"\"\"Search for leads matching a query.\"\"\"
        ...

    @tool(permissions=["leads:read"])
    async def read_lead(lead_id: int) -> dict:
        ...

The decorated function remains callable as plain Python while carrying a
``__tool_spec__`` attribute (a :class:`ToolSpec`) and being registered in the
default registry (``voodoo.tools.registry.default_registry``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, overload

from voodoo.ai.tools.registry import ToolRegistry, ToolSpec, build_spec

__all__ = ["tool", "ToolSpec", "ToolRegistry", "default_registry"]

# Re-export the default registry instance (lives in the registry module so it
# can be monkeypatched in tests without being shadowed by this package).
from voodoo.ai.tools.registry import default_registry  # noqa: E402, F401


def _resolve_default_registry() -> ToolRegistry:
    """Fetch the current default registry dynamically (test-monkeypatchable)."""
    from voodoo.ai.tools import registry as _registry_module

    return _registry_module.default_registry


@overload
def tool(func: Callable[..., Any]) -> Callable[..., Any]: ...


@overload
def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    permissions: list[str] | None = None,
    version: str = "1.0.0",
    registry: ToolRegistry | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def tool(  # noqa: ANN201 — intentionally generic decorator return
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    permissions: list[str] | None = None,
    version: str = "1.0.0",
    registry: ToolRegistry | None = None,
) -> Any:
    """Register a function as a tool.

    Works bare (``@tool``) or parametrized (``@tool(permissions=[...])``).
    The original function is returned unchanged so it stays callable as
    plain Python; a :class:`ToolSpec` is attached as ``__tool_spec__`` and
    registered in the chosen registry (the default global one by default).
    """
    target = registry if registry is not None else _resolve_default_registry()

    def _decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        spec = build_spec(
            fn,
            name=name,
            description=description,
            permissions=permissions,
            version=version,
        )
        target.register(spec)
        fn.__tool_spec__ = spec  # type: ignore[attr-defined]
        return fn

    if func is not None:
        # Bare ``@tool`` usage.
        return _decorate(func)
    # Parametrized ``@tool(...)`` usage.
    return _decorate
