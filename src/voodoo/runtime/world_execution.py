"""World-aware execution helpers.

This module binds the existing ExecutionEngine to a WorldModel without creating
another runtime. Capability policy sees the same world projection and compute
participants receive a world-aware ExecutionContext before they run.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from voodoo.runtime.context import ExecutionContext

__all__ = ["bind_world", "world_aware", "resolve_target_entity_id"]


ComputeLike = Callable[[ExecutionContext], Any | Awaitable[Any]]


def bind_world(engine: Any, world: Any) -> Any:
    """Attach one WorldModel to an ExecutionEngine and its policy boundary.

    The engine remains the canonical execution lifecycle. The binding only
    exposes a shared world query/evidence service to authorization and compute.
    """
    engine.world = world
    policy = getattr(getattr(engine, "capabilities", None), "policy", None)
    if policy is not None and hasattr(policy, "use_world"):
        policy.use_world(world)
    return engine


def resolve_target_entity_id(ctx: ExecutionContext) -> str | None:
    """Resolve the semantic target for the current execution."""
    if ctx.target_entity_id is not None:
        return ctx.target_entity_id
    metadata_target = ctx.metadata.get("target_entity_id")
    if metadata_target is not None:
        return str(metadata_target)
    if ctx.intent is None:
        return None
    params = ctx.intent.params
    target = params.get("_target_entity_id", params.get("entity_id"))
    return str(target) if target is not None else None


def world_aware(compute: ComputeLike) -> ComputeLike:
    """Adapt a compute participant so it receives the engine's bound world.

    The adapter is intentionally thin. It does not create an Execution and it
    does not project Effects into the world. Participants must report actual
    consequences through ``ctx.observe(...)``.
    """

    async def wrapped(ctx: ExecutionContext) -> Any:
        world = getattr(ctx.engine, "world", None) if ctx.engine is not None else None
        ctx.world = world
        ctx.target_entity_id = resolve_target_entity_id(ctx)
        result = compute(ctx)
        if inspect.isawaitable(result):
            return await result
        return result

    return wrapped
