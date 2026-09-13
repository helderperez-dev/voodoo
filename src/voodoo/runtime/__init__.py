"""Voodoo runtime — the unified execution model.

This package makes the computational model *operational*.
Every meaningful operation is represented as an Execution produced by a
single ExecutionEngine walking the operational model:

    World → Goal → Intent → Capability → Policy → Execution → Effect → Observation
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
from voodoo.runtime.dashboard import runtime_dashboard
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
from voodoo.runtime.goal import (
    Goal,
    GoalDecomposer,
    GoalIntentRun,
    GoalRun,
    GoalRuntime,
    GoalStatus,
)
from voodoo.runtime.goal_store import GoalStore, SQLiteGoalStore
from voodoo.runtime.graph import ExecutionGraph, ExecutionNode
from voodoo.runtime.human import (
    Approval,
    ApprovalRegistry,
    ApprovalStatus,
    Human,
    ask_human,
)
from voodoo.runtime.operations import OperationalRuntime
from voodoo.runtime.persistence import (
    ExecutionStore,
    InMemoryExecutionStore,
    JSONFileExecutionStore,
)
from voodoo.runtime.planner import ComputeParticipant, Plan, Planner, PlanStep
from voodoo.runtime.policy import (
    PolicyDecision,
    PolicyEngine,
    PolicyRequest,
    PolicyResult,
    PolicyRule,
)
from voodoo.runtime.store import (
    DEFAULT_STORE_PATH,
    RuntimeStore,
    StoreConfig,
    StoreHealth,
    StoreProvider,
    StoreProviderError,
    StoreProviderRegistry,
    VoodooStoreProvider,
    create_store_provider,
    store_registry,
)
from voodoo.runtime.task import Task, TaskStatus
from voodoo.runtime.workflow import Workflow, WorkflowRun, WorkflowStrategy
from voodoo.runtime.world_execution import (
    bind_world,
    resolve_target_entity_id,
    world_aware,
)

__all__ = [
    "Execution",
    "ExecutionStatus",
    "ExecutionContext",
    "current_context",
    "use_context",
    "ExecutionEngine",
    "engine",
    "ComputeFn",
    "ComputeResult",
    "CapabilityResolver",
    "Resolution",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyRequest",
    "PolicyResult",
    "PolicyRule",
    "ConstraintEnforcer",
    "Decision",
    "ResourceAccountant",
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
    "Task",
    "TaskStatus",
    "Workflow",
    "WorkflowRun",
    "WorkflowStrategy",
    "ExecutionGraph",
    "ExecutionNode",
    "Approval",
    "ApprovalStatus",
    "ApprovalRegistry",
    "Human",
    "ask_human",
    "ExecutionStore",
    "InMemoryExecutionStore",
    "JSONFileExecutionStore",
    "DEFAULT_STORE_PATH",
    "StoreConfig",
    "StoreHealth",
    "StoreProvider",
    "StoreProviderError",
    "StoreProviderRegistry",
    "RuntimeStore",
    "VoodooStoreProvider",
    "create_store_provider",
    "store_registry",
    "ComputeParticipant",
    "Plan",
    "PlanStep",
    "Planner",
    "AdaptiveRun",
    "AdaptiveSupervisor",
    "SupervisorDecision",
    "SupervisorConfig",
    "Goal",
    "GoalStatus",
    "GoalIntentRun",
    "GoalRun",
    "GoalRuntime",
    "GoalDecomposer",
    "GoalStore",
    "SQLiteGoalStore",
    "OperationalRuntime",
    "runtime_dashboard",
    "bind_world",
    "world_aware",
    "resolve_target_entity_id",
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
    """Execute an intent through the default runtime engine."""
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
