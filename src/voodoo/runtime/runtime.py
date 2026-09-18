"""Canonical composition root for Voodoo runtime subsystems.

Runtime owns the semantic control-plane objects that previously had to be wired
by application code.  It does not create a second execution path:
ExecutionEngine remains the only authority boundary for executable work.
"""

from __future__ import annotations

from typing import Any

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
from voodoo.runtime.goal import Goal
from voodoo.runtime.handoff import ExecutionHandoff
from voodoo.runtime.lineage import RuntimeLineage
from voodoo.runtime.reconcile import (
    GoalIntentFactory,
    GoalPredicate,
    GoalReconciliation,
    ReconcileDecision,
    ReconcileHandler,
    Reconciler,
)
from voodoo.runtime.store import RuntimeStore, StoreConfig
from voodoo.runtime.work_scheduler import RuntimeScheduler


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
        node = contribute_goal(self.graph, goal)
        for source_id in observes:
            if self.graph.get(source_id) is None:
                raise KeyError(f"Unknown observed application node: {source_id}")
            self.graph.connect(node.id, "observes", source_id)
        self.reconciler.register_node(
            node.id,
            GoalReconciliation(goal, satisfied=satisfied, propose=propose),
        )
        return self

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


__all__ = ["Runtime"]
