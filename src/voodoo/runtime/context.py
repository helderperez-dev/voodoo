"""Execution Context — one shared context for the whole runtime.

A single :class:`ExecutionContext` is created per top-level execution and
propagated (via :func:`use_context` / :func:`current_context`) to every
participant — Agent, Tool, Worker, Workflow, HTTP handler, Mesh handler,
MCP, Effect — so they all share identity, correlation, authority, limits
and cancellation.

This replaces ad-hoc per-subsystem context systems with one coherent
carrier, while still integrating with the existing ``trace_id_var``
telemetry context variable.
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

#: Context variable holding the active :class:`ExecutionContext`.
_context_var: contextvars.ContextVar[ExecutionContext | None] = contextvars.ContextVar(
    "voodoo_execution_context", default=None
)


def new_trace_id() -> str:
    """Generate a new trace id."""
    return str(uuid4())


def current_context() -> ExecutionContext | None:
    """Return the active execution context, if any."""
    return _context_var.get()


@asynccontextmanager
async def use_context(ctx: ExecutionContext) -> AsyncIterator[ExecutionContext]:
    """Activate ``ctx`` for the duration of the ``async with`` block.

    Also mirrors ``ctx.trace_id`` onto the existing ``trace_id_var`` so
    legacy telemetry/mesh code keeps correlating correctly.
    """
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

    Carries everything the runtime needs to govern a single execution:
    identity/correlation, the originating intent, granted capabilities,
    constraints, resource budgets, a deadline, and a cancellation flag.

    Mutations to ``capabilities`` / ``constraints`` during execution are
    intentional — delegation narrows authority, retries add constraints.
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
    #: The engine governing this execution (set by the engine on build;
    #: enables child executions to run on the same engine).
    engine: Any | None = None

    # -- derivation --------------------------------------------------------

    def child(self, actor: str | None = None) -> ExecutionContext:
        """Create a child context for a delegated/sub execution.

        The child inherits the trace id and a narrowed view of the parent's
        capabilities/constraints. It records ``parent_execution_id`` so the
        execution graph stays traceable.
        """
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
        )

    # -- authority ---------------------------------------------------------

    def grant(self, capability: Capability) -> None:
        """Add a capability to this context."""
        self.capabilities.append(capability)

    def has_capability(self, name: str, *, scope: str | None = None) -> bool:
        """Whether a valid capability with ``name`` (and optional scope) is held."""
        for cap in self.capabilities:
            if cap.name != name or not cap.valid:
                continue
            if scope is not None and cap.scope is not None and cap.scope != scope:
                continue
            return True
        return False

    def constrain(self, constraint: Constraint) -> None:
        """Add a constraint to this context."""
        self.constraints.append(constraint)

    # -- effects -----------------------------------------------------------

    def add_effect(self, effect: Effect) -> None:
        """Record an effect produced inside this execution.

        The engine lifts context effects onto the :class:`Execution` when
        the compute participant finishes, so tool calls made deep inside
        an Agent run still appear in the execution record.
        """
        self.effects.append(effect)

    # -- temporal ----------------------------------------------------------

    def with_deadline(self, seconds: float) -> ExecutionContext:
        """Set a deadline ``seconds`` from now."""
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

    # -- cancellation ------------------------------------------------------

    def cancel(self) -> None:
        """Mark this execution (and its children) as cancelled."""
        self.cancelled = True

    # -- inspectability ----------------------------------------------------

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
        }
