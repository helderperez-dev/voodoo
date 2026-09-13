"""Execution Context — one shared context for the whole runtime.

A single :class:`ExecutionContext` is created per top-level execution and
propagated (via :func:`use_context` / :func:`current_context`) to every
participant — Agent, Tool, Worker, Workflow, HTTP handler, Mesh handler,
MCP, Effect — so they all share identity, correlation, authority, limits,
world awareness and cancellation.
"""

from __future__ import annotations

import contextvars
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from voodoo.primitives.capability import Capability
from voodoo.primitives.constraint import Constraint
from voodoo.primitives.effect import Effect
from voodoo.primitives.intent import Intent
from voodoo.primitives.resource import Resource

__all__ = [
    "ExecutionContext",
    "current_context",
    "use_context",
    "new_trace_id",
]

_context_var: contextvars.ContextVar[ExecutionContext | None] = contextvars.ContextVar(
    "voodoo_execution_context", default=None
)


def new_trace_id() -> str:
    return str(uuid4())


def current_context() -> ExecutionContext | None:
    return _context_var.get()


@asynccontextmanager
async def use_context(ctx: ExecutionContext) -> AsyncIterator[ExecutionContext]:
    from voodoo.telemetry import trace_id_var

    token = _context_var.set(ctx)
    prev_trace = trace_id_var.get()
    if ctx.trace_id is not None:
        trace_id_var.set(ctx.trace_id)
    try:
        yield ctx
    finally:
        _context_var.reset(token)
        trace_id_var.set(prev_trace)


@dataclass
class ExecutionContext:
    """The single shared execution context.

    World access is read/query oriented by default. A participant may report
    observed consequences through :meth:`observe`, which automatically carries
    trace/execution lineage. Issuing an Effect never mutates world state by
    itself; evidence must come back as an Observation.
    """

    execution_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=new_trace_id)
    parent_execution_id: str | None = None
    actor: str = "system"
    intent: Intent | None = None
    capabilities: list[Capability] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    resources: Resource = field(default_factory=Resource)
    effects: list[Effect] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    deadline: datetime | None = None
    cancelled: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    engine: Any | None = None
    world: Any | None = None
    target_entity_id: str | None = None

    def child(self, actor: str | None = None) -> ExecutionContext:
        return ExecutionContext(
            execution_id=str(uuid4()),
            trace_id=self.trace_id,
            parent_execution_id=self.execution_id,
            actor=actor or self.actor,
            intent=self.intent,
            capabilities=list(self.capabilities),
            constraints=list(self.constraints),
            resources=Resource(
                cost=self.resources.cost,
                latency_ms=self.resources.latency_ms,
                tokens=self.resources.tokens,
            ),
            state=dict(self.state),
            metadata=dict(self.metadata),
            deadline=self.deadline,
            engine=self.engine,
            world=self.world,
            target_entity_id=self.target_entity_id,
        )

    def grant(self, capability: Capability) -> None:
        self.capabilities.append(capability)

    def has_capability(self, name: str, *, scope: str | None = None) -> bool:
        for cap in self.capabilities:
            if cap.name != name or not cap.valid:
                continue
            if scope is not None and cap.scope is not None and cap.scope != scope:
                continue
            return True
        return False

    def constrain(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)

    def add_effect(self, effect: Effect) -> None:
        self.effects.append(effect)

    def world_snapshot(self, entity_id: str | None = None) -> Any | None:
        """Return a current WorldSnapshot for the target/selected entity."""
        if self.world is None:
            return None
        target = entity_id or self.target_entity_id
        if target is None:
            return None
        try:
            return self.world.snapshot(target)
        except KeyError:
            return None

    def observe(
        self,
        entity_id: str,
        property: str,
        value: Any,
        *,
        source: str,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        observation_id: str | None = None,
    ) -> Any:
        """Report evidence to the attached WorldModel with automatic lineage."""
        if self.world is None:
            raise RuntimeError("execution context has no WorldModel attached")
        return self.world.observe(
            entity_id,
            property,
            value,
            source=source,
            confidence=confidence,
            trace_id=self.trace_id,
            execution_id=self.execution_id,
            metadata=metadata,
            observation_id=observation_id,
        )

    def with_deadline(self, seconds: float) -> ExecutionContext:
        self.deadline = datetime.now(UTC) + timedelta(seconds=seconds)
        return self

    @property
    def deadline_expired(self) -> bool:
        if self.deadline is None:
            return False
        return datetime.now(UTC) >= self.deadline

    @property
    def remaining_seconds(self) -> float | None:
        if self.deadline is None:
            return None
        return max((self.deadline - datetime.now(UTC)).total_seconds(), 0.0)

    def cancel(self) -> None:
        self.cancelled = True

    def describe(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "parent_execution_id": self.parent_execution_id,
            "actor": self.actor,
            "intent": self.intent.name if self.intent else None,
            "capabilities": [c.name for c in self.capabilities if c.valid],
            "constraint_count": len(self.constraints),
            "resources": self.resources.describe(),
            "deadline_expired": self.deadline_expired,
            "remaining_seconds": self.remaining_seconds,
            "cancelled": self.cancelled,
            "world_attached": self.world is not None,
            "target_entity_id": self.target_entity_id,
        }
