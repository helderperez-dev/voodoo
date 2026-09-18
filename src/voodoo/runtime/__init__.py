from voodoo.runtime.dispatch import DispatchPlan, RuntimeDispatcher
"""Voodoo runtime — the unified execution model.

This package makes the computational model *operational*.
Every meaningful operation is represented as an Execution produced by a
single ExecutionEngine walking the operational model:

    World → Goal → Intent → Capability → Policy → Execution → Effect → Observation
"""

from __future__ import annotations

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime.application_graph import (
    ApplicationEdge,
    ApplicationGraph,
    ApplicationGraphChange,
    ApplicationGraphContributor,
    ApplicationNode,
    ApplicationNodeKind,
    ChangeReason,
    Extension,
    ExtensionManifest,
    ExtensionRegistry,
    Invalidation,
    InvalidationEngine,
    build_application_graph,
    contribute_goal,
    diff_application_graph,
)
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
from voodoo.runtime.fabric import (
    FabricLease,
    FabricRoutingError,
    FabricWork,
    NoEligibleNodeError,
    PlacementDecision,
    PlacementRequirement,
    RuntimeFabric,
    WorkNotFailoverSafeError,
)
from voodoo.runtime.goal import (
    Goal,
    GoalDecomposer,
    GoalIntentRun,
    GoalRun,
    GoalRuntime,
    GoalStatus,
)
from voodoo.runtime.goal_store import GoalStore, SQLiteGoalStore, VoodooStoreGoalStore
from voodoo.runtime.graph import ExecutionGraph, ExecutionNode
from voodoo.runtime.human import (
    Approval,
    ApprovalRegistry,
    ApprovalStatus,
    Human,
    ask_human,
)
from voodoo.runtime.identity import (
    AuthenticationEvidence,
    Identity,
    IdentityKind,
    IdentityStatus,
    Principal,
)
from voodoo.runtime.identity_store import IdentityStore, VoodooStoreIdentityStore
from voodoo.runtime.membership import (
    MemberStatus,
    NodeAdvertisement,
    NodeMembership,
    VoodooStoreMembershipStore,
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
    bind_active_runtime_store,
    create_store_provider,
    get_active_runtime_store,
    store_registry,
)
from voodoo.runtime.task import Task, TaskStatus
from voodoo.runtime.transaction import (
    OutboxDispatcher,
    OutboxMessage,
    RuntimeTransaction,
    dispatch_events,
    dispatch_outbox,
    transaction,
)
from voodoo.runtime.workflow import Workflow, WorkflowRun, WorkflowStrategy
from voodoo.runtime.workflow_store import VoodooStoreWorkflowStore, WorkflowStore
from voodoo.runtime.world_execution import (
    bind_world,
    resolve_target_entity_id,
    world_aware,
)

__all__ = [
    "ApplicationNodeKind",
    "ChangeReason",
    "Extension",
    "ExtensionManifest",
    "ExtensionRegistry",
    "Invalidation",
    "InvalidationEngine",
    "ApplicationNode",
    "ApplicationEdge",
    "ApplicationGraph",
    "ApplicationGraphChange",
    "ApplicationGraphContributor",
    "build_application_graph",
    "contribute_goal",
    "diff_application_graph",
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
    "IdentityKind",
    "IdentityStatus",
    "Identity",
    "AuthenticationEvidence",
    "Principal",
    "IdentityStore",
    "VoodooStoreIdentityStore",
    "MemberStatus",
    "NodeAdvertisement",
    "NodeMembership",
    "VoodooStoreMembershipStore",
    "PlacementRequirement",
    "PlacementDecision",
    "FabricWork",
    "FabricLease",
    "RuntimeFabric",
    "FabricRoutingError",
    "NoEligibleNodeError",
    "WorkNotFailoverSafeError",
    "Task",
    "TaskStatus",
    "Workflow",
    "WorkflowRun",
    "WorkflowStrategy",
    "WorkflowStore",
    "VoodooStoreWorkflowStore",
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
    "bind_active_runtime_store",
    "create_store_provider",
    "get_active_runtime_store",
    "store_registry",
    "RuntimeTransaction",
    "OutboxMessage",
    "OutboxDispatcher",
    "transaction",
    "dispatch_outbox",
    "dispatch_events",
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
    "VoodooStoreGoalStore",
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
    principal: Principal | None = None,
    capabilities: list[str    "RuntimeScheduler",
    "ScheduledWork",
    "SchedulingDecision",
    "WorkEligibility",
    "DispatchPlan",
    "RuntimeDispatcher",
] | None = None,
    output_type: type | None = None,
    parent: ExecutionContext | None = None,
) -> Execution:
    """Execute an intent through the default runtime engine."""
    return await engine.execute(
        intent,
        compute,
        actor=actor,
        principal=principal,
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

from voodoo.runtime.work_scheduler import (
    RuntimeScheduler,
    ScheduledWork,
    SchedulingDecision,
    WorkEligibility,
)
