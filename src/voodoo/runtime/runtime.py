"""Canonical composition root for Voodoo runtime subsystems.

Runtime owns the semantic control-plane objects that previously had to be wired
by application code.  It does not create a second execution path:
ExecutionEngine remains the only authority boundary for executable work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from voodoo.primitives.intent import Intent
from voodoo.runtime.adaptive import AdaptiveSupervisor, SupervisorConfig
from voodoo.runtime.application_graph import (
    ApplicationGraph,
    ApplicationNodeKind,
    ChangeReason,
    Invalidation,
    InvalidationEngine,
    contribute_goal,
)
from voodoo.runtime.dependency_graph import DependencyGraph
from voodoo.runtime.dispatch import DispatchPlan, RuntimeDispatcher
from voodoo.runtime.engine import ComputeFn, ExecutionEngine
from voodoo.runtime.execution import Execution
from voodoo.runtime.extension import RuntimeExtensionRegistry
from voodoo.runtime.fabric import RuntimeFabric
from voodoo.runtime.goal import Goal, GoalDecomposer, GoalRun, GoalRuntime, GoalStore
from voodoo.runtime.handoff import ExecutionHandoff
from voodoo.runtime.lineage import RuntimeLineage
from voodoo.runtime.planner import ComputeParticipant, Planner
from voodoo.runtime.reconcile import (
    GoalIntentFactory,
    GoalPredicate,
    GoalReconciliation,
    ReconcileAction,
    ReconcileDecision,
    ReconcileHandler,
    Reconciler,
)
from voodoo.runtime.store import RuntimeStore, StoreConfig
from voodoo.runtime.work_scheduler import RuntimeScheduler, WorkEligibility


@dataclass(frozen=True, slots=True)
class RuntimeCycle:
    """Structured result of one bounded reconciliation cycle."""

    invalidation: Invalidation
    decisions: tuple[ReconcileDecision, ...]
    executions: tuple[Execution, ...]


class Runtime:
    """Own and connect one Voodoo runtime control plane.

    The class intentionally composes existing subsystems instead of replacing
    them.  Reconciliation proposes work, dispatch schedules/places it, and
    handoff always submits eligible work to the canonical ExecutionEngine.
    """

    def __init__(
        self,
        *,
        engine: ExecutionEngine | None = None,
        graph: ApplicationGraph | None = None,
        dependencies: DependencyGraph | None = None,
        world: Any | None = None,
        fabric: RuntimeFabric | None = None,
        store: RuntimeStore | None = None,
        store_config: StoreConfig | None = None,
        lineage: RuntimeLineage | None = None,
        extensions: RuntimeExtensionRegistry | None = None,
        goal_store: GoalStore | None = None,
        supervisor_config: SupervisorConfig | None = None,
        local_node_id: str | None = None,
    ) -> None:
        if store is not None and store_config is not None:
            raise ValueError("pass store or store_config, not both")

        self.engine = engine or ExecutionEngine()
        self.graph = graph or ApplicationGraph()
        self.dependencies = dependencies or DependencyGraph()
        self.world = world
        self.fabric = fabric
        self.store = store or RuntimeStore(store_config)
        self.lineage = lineage or RuntimeLineage()
        self.extensions = extensions or RuntimeExtensionRegistry()

        self.planner = Planner(engine=self.engine)
        self.supervisor = AdaptiveSupervisor(
            self.planner,
            engine=self.engine,
            config=supervisor_config,
        )
        self.goals = GoalRuntime(
            self.supervisor,
            world=self.world,
            store=goal_store,
        )

        self.invalidations = InvalidationEngine(self.graph)
        self.reconciler = Reconciler(self.graph)
        self.scheduler = RuntimeScheduler()
        self.dispatcher = RuntimeDispatcher(
            self.scheduler,
            fabric=self.fabric,
            lineage=self.lineage,
        )
        self.handoff = ExecutionHandoff(
            self.engine,
            local_node_id=local_node_id,
            lineage=self.lineage,
        )

        if self.world is not None:
            self.engine.capabilities.policy.use_world(self.world)

    def start(self) -> Runtime:
        """Start owned infrastructure and contribute active extensions."""
        self.store.start()
        self.extensions.contribute(self.graph)
        return self

    def stop(self) -> None:
        """Stop infrastructure owned by this Runtime."""
        self.store.stop()

    def register_reconciler(
        self,
        kind: ApplicationNodeKind,
        handler: ReconcileHandler,
    ) -> Runtime:
        self.reconciler.register(kind, handler)
        return self

    def register_goal(
        self,
        goal: Goal,
        *,
        satisfied: GoalPredicate,
        propose: GoalIntentFactory | None = None,
        observes: tuple[str, ...] = (),
    ) -> Runtime:
        """Project a Goal into the graph and register canonical reconciliation."""
        node_id = f"goal:{goal.id}"
        node = self.graph.get(node_id)
        if node is None:
            node = contribute_goal(self.graph, goal)
        elif node.kind is not ApplicationNodeKind.GOAL or node.name != goal.name:
            raise ValueError(f"Application node {node_id!r} conflicts with Goal")
        for source_id in observes:
            if self.graph.get(source_id) is None:
                raise KeyError(f"Unknown observed application node: {source_id}")
            self.graph.connect(node.id, "observes", source_id)
        self.reconciler.register_node(
            node.id,
            GoalReconciliation(goal, satisfied=satisfied, propose=propose),
        )
        return self

    def register_compute(self, participant: ComputeParticipant) -> Runtime:
        """Register adaptive compute without creating a parallel runtime."""
        self.planner.register(participant)
        return self

    async def achieve(
        self,
        goal: Goal,
        *,
        intents: list[Intent] | None = None,
        decomposer: GoalDecomposer | None = None,
        context: dict[str, Any] | None = None,
    ) -> GoalRun:
        """Run a durable/adaptive Goal through the Runtime-owned executor."""
        return await self.goals.achieve(
            goal,
            intents=intents,
            decomposer=decomposer,
            context=context,
        )

    async def resume_goal(self, goal_id: str) -> GoalRun:
        """Resume a durable Goal run owned by this Runtime."""
        return await self.goals.resume(goal_id)

    def invalidate(
        self,
        source: str,
        *,
        reason: ChangeReason = ChangeReason.STATE,
        revision: str | None = None,
    ) -> Invalidation:
        """Invalidate a structural source in the Application Graph."""
        return self.invalidations.invalidate(source, reason=reason, revision=revision)

    def reconcile(self, invalidation: Invalidation) -> tuple[ReconcileDecision, ...]:
        """Evaluate affected semantic nodes against the current World."""
        return self.reconciler.reconcile(invalidation, world=self.world)

    def prepare(self, decision: ReconcileDecision) -> tuple[DispatchPlan, ...]:
        """Turn a reconciliation proposal into governed scheduled work."""
        return self.dispatcher.prepare(decision)

    async def cycle(
        self,
        source: str,
        compute: ComputeFn | None = None,
        *,
        reason: ChangeReason = ChangeReason.STATE,
        revision: str | None = None,
        actor: str = "system",
        principal: Any | None = None,
    ) -> RuntimeCycle:
        """Run exactly one invalidate → reconcile → execute cycle.

        A cycle is deliberately bounded: it does not recursively react to effects
        or observations produced by its own executions.
        """
        invalidation = self.invalidate(source, reason=reason, revision=revision)
        decisions = self.reconcile(invalidation)
        executions: list[Execution] = []
        for decision in decisions:
            executions.extend(
                await self.execute_decision(
                    decision,
                    compute,
                    actor=actor,
                    principal=principal,
                )
            )
        return RuntimeCycle(
            invalidation=invalidation,
            decisions=decisions,
            executions=tuple(executions),
        )

    async def execute_decision(
        self,
        decision: ReconcileDecision,
        compute: ComputeFn | None = None,
        *,
        actor: str = "system",
        principal: Any | None = None,
    ) -> tuple[Execution, ...]:
        """Execute only work explicitly proposed by reconciliation.

        Reconciliation remains a decision boundary: satisfied, waiting, blocked,
        failed, and human-request decisions never enter compute.
        """
        if decision.action is not ReconcileAction.PROPOSE_INTENT:
            return ()
        executions = []
        for plan in self.prepare(decision):
            if plan.scheduling.status is not WorkEligibility.ELIGIBLE:
                continue
            executions.append(
                await self.execute(
                    plan,
                    compute,
                    actor=actor,
                    principal=principal,
                )
            )
        return tuple(executions)

    async def execute(
        self,
        plan: DispatchPlan,
        compute: ComputeFn | None = None,
        *,
        actor: str = "system",
        principal: Any | None = None,
    ) -> Execution:
        """Execute eligible prepared work through the canonical engine."""
        return await self.handoff.execute(
            plan,
            compute,
            actor=actor,
            principal=principal,
        )


__all__ = ["Runtime", "RuntimeCycle"]
