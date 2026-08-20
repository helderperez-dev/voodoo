"""Voodoo runtime — the unified execution model.

This package makes the computational model *operational*.
Every meaningful operation (HTTP request, Agent run, Task, Workflow task,
Tool invocation, MCP call, Worker job, Human approval, Event handler) is
represented as an :class:`~voodoo.runtime.execution.Execution` produced by
a single :class:`~voodoo.runtime.engine.ExecutionEngine` walking:

    Intent → Capability → Execution → Effect → State → Mesh

The developer surface stays small:

    from voodoo.runtime import Intent, execute, Task, Workflow, Agent
    from voodoo.primitives import Capability, Constraint, Resource

        result = await execute(Intent("qualify_customer", customer_id=123))

Simple at the surface. Deep underneath.
"""

from __future__ import annotations

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime.adaptive import (
    AdaptiveRun,
    AdaptiveSupervisor,
    SupervisorConfig,
    SupervisorDecision,
)
from voodoo.runtime.capability import CapabilityResolver, Resolution
from voodoo.runtime.constraint import ConstraintEnforcer, Decision, ResourceAccountant
from voodoo.runtime.context import ExecutionContext, current_context, use_context
from voodoo.runtime.engine import ComputeFn, ComputeResult, ExecutionEngine, engine
from voodoo.runtime.errors import (
    AgentExecutionError,
    ApprovalRequired,
    CapabilityDenied,
    ConstraintViolation,
    ExecutionCancelled,
    ExecutionError,
    ExecutionTimeout,
    ResourceExceeded,
    ToolExecutionError,
    ValidationError,
    WorkflowFailure,
)
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.runtime.graph import ExecutionGraph, ExecutionNode
from voodoo.runtime.human import (
    Approval,
    ApprovalRegistry,
    ApprovalStatus,
    Human,
    ask_human,
)
from voodoo.runtime.persistence import (
    ExecutionStore,
    InMemoryExecutionStore,
    JSONFileExecutionStore,
)
from voodoo.runtime.planner import ComputeParticipant, Plan, Planner, PlanStep
from voodoo.runtime.task import Task, TaskStatus
from voodoo.runtime.workflow import Workflow, WorkflowRun, WorkflowStrategy

__all__ = [
    # core
    "Execution",
    "ExecutionStatus",
    "ExecutionContext",
    "current_context",
    "use_context",
    "ExecutionEngine",
    "engine",
    "ComputeFn",
    "ComputeResult",
    # enforcement
    "CapabilityResolver",
    "Resolution",
    "ConstraintEnforcer",
    "Decision",
    "ResourceAccountant",
    # errors
    "ExecutionError",
    "CapabilityDenied",
    "ConstraintViolation",
    "ResourceExceeded",
    "ExecutionTimeout",
    "ExecutionCancelled",
    "ToolExecutionError",
    "AgentExecutionError",
    "ValidationError",
    "ApprovalRequired",
    "WorkflowFailure",
    # orchestration
    "Task",
    "TaskStatus",
    "Workflow",
    "WorkflowRun",
    "WorkflowStrategy",
    # graph
    "ExecutionGraph",
    "ExecutionNode",
    # human-in-the-loop
    "Approval",
    "ApprovalStatus",
    "ApprovalRegistry",
    "Human",
    "ask_human",
    # persistence / recovery
    "ExecutionStore",
    "InMemoryExecutionStore",
    "JSONFileExecutionStore",
    # planning / adaptive
    "ComputeParticipant",
    "Plan",
    "PlanStep",
    "Planner",
    "AdaptiveRun",
    "AdaptiveSupervisor",
    "SupervisorDecision",
    "SupervisorConfig",
    # convenience
    "execute",
    "register_capability",
    "grant",
]


async def execute(
    intent: Intent,
    compute: ComputeFn | None = None,
    *,
    actor: str = "system",
    capabilities: list[str] | None = None,
    output_type: type | None = None,
    parent: ExecutionContext | None = None,
) -> Execution:
    """Execute an intent through the default runtime engine.

    The canonical entry point:

        result = await execute(Intent("qualify_customer", customer_id=123))
    """
    return await engine.execute(
        intent,
        compute,
        actor=actor,
        capabilities=capabilities,
        output_type=output_type,
        parent=parent,
    )


def register_capability(capability: Capability) -> None:
    """Register a capability template with the default engine."""
    engine.capabilities.register(capability)


def grant(context: ExecutionContext, capability: Capability) -> None:
    """Grant a capability to an in-flight execution context."""
    context.grant(capability)
