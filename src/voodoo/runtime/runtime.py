"""Canonical composition root for Voodoo runtime subsystems.

Runtime owns the semantic control-plane objects that previously had to be wired
by application code.  It does not create a second execution path:
ExecutionEngine remains the only authority boundary for executable work.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
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


class ConvergenceStatus(StrEnum):
    STABLE = "stable"
    WAITING = "waiting"
    BLOCKED = "blocked"
    FAILED = "failed"
    LIMIT_REACHED = "limit_reached"


@dataclass(frozen=True, slots=True)
class RuntimeConvergence:
    """Semantic result of an explicitly bounded observation convergence run."""

    cycles: tuple[RuntimeCycle, ...]
    processed: int
    max_cycles: int
    status: ConvergenceStatus

    @property
    def exhausted(self) -> bool:
        return self.status is ConvergenceStatus.LIMIT_REACHED


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
        self._owns_store = True
        self.lineage = lineage or RuntimeLineage()
        self.extensions = extensions or RuntimeExtensionRegistry()
        self._observation_sources: dict[tuple[str, str], str] = {}

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

    def use_store(self, store: RuntimeStore, *, owned: bool = False) -> Runtime:
        """Use a RuntimeStore and record whether this Runtime owns its lifecycle."""
        if self.store is store:
            self._owns_store = owned
            return self
        if self.store.started:
            raise RuntimeError("cannot replace a started RuntimeStore")
        self.store = store
        self._owns_store = owned
        return self

    def start(self) -> Runtime:
        """Start owned infrastructure and contribute active extensions."""
        self.store.start()
        self.extensions.contribute(self.graph)
        return self

    def stop(self) -> None:
        """Stop infrastructure owned by this Runtime."""
        if self._owns_store:
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

    def bind_observation(
        self,
        entity_id: str,
        property: str,
        *,
        resource_id: str | None = None,
    ) -> str:
        """Bind one World property to an Application Graph resource."""
        if self.world is None:
            raise RuntimeError("observation bindings require a WorldModel")
        node_id = resource_id or f"resource:{entity_id}:{property}"
        node = self.graph.get(node_id)
        if node is None:
            node = self.graph.node(
                ApplicationNodeKind.RESOURCE,
                f"{entity_id}.{property}",
                node_id=node_id,
                metadata={"entity_id": entity_id, "property": property},
            )
        elif node.kind is not ApplicationNodeKind.RESOURCE:
            raise ValueError(f"Application node {node_id!r} is not a resource")
        self._observation_sources[(entity_id, property)] = node.id
        return node.id

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

    @staticmethod
    def _convergence_status(
        cycles: list[RuntimeCycle],
        *,
        limit_reached: bool,
    ) -> ConvergenceStatus:
        if limit_reached:
            return ConvergenceStatus.LIMIT_REACHED
        actions = {
            decision.action
            for cycle in cycles
            for decision in cycle.decisions
            if decision.node_id != "application"
        }
        if ReconcileAction.FAILED in actions:
            return ConvergenceStatus.FAILED
        if ReconcileAction.BLOCKED in actions:
            return ConvergenceStatus.BLOCKED
        if ReconcileAction.REQUEST_HUMAN in actions or ReconcileAction.WAIT in actions:
            return ConvergenceStatus.WAITING
        if not actions or actions <= {ReconcileAction.SATISFIED}:
            return ConvergenceStatus.STABLE
        return ConvergenceStatus.WAITING

    async def converge(
        self,
        observations: list[dict[str, Any]],
        compute: ComputeFn | None = None,
        *,
        max_cycles: int = 16,
        actor: str = "system",
        principal: Any | None = None,
    ) -> RuntimeConvergence:
        """Process explicit observations sequentially with a hard cycle bound."""
        if max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")
        cycles: list[RuntimeCycle] = []
        processed = 0
        for item in observations:
            if processed >= max_cycles:
                break
            payload = dict(item)
            try:
                entity_id = payload.pop("entity_id")
                property_name = payload.pop("property")
                value = payload.pop("value")
                source = payload.pop("source")
            except KeyError as error:
                raise ValueError(
                    f"observation is missing required field: {error.args[0]}"
                ) from error
            cycle = await self.observe(
                entity_id,
                property_name,
                value,
                source=source,
                compute=compute,
                actor=actor,
                principal=principal,
                **payload,
            )
            processed += 1
            if cycle is not None:
                cycles.append(cycle)
        status = self._convergence_status(
            cycles,
            limit_reached=processed >= max_cycles and processed < len(observations),
        )
        return RuntimeConvergence(
            cycles=tuple(cycles),
            processed=processed,
            max_cycles=max_cycles,
            status=status,
        )

    async def observe(
        self,
        entity_id: str,
        property: str,
        value: Any,
        *,
        source: str,
        compute: ComputeFn | None = None,
        actor: str = "system",
        principal: Any | None = None,
        **observation: Any,
    ) -> RuntimeCycle | None:
        """Record World evidence and reconcile its explicitly bound resource."""
        if self.world is None:
            raise RuntimeError("observe requires a WorldModel")
        evidence = self.world.observe(
            entity_id,
            property,
            value,
            source=source,
            **observation,
        )
        resource_id = self._observation_sources.get((entity_id, property))
        if resource_id is None:
            return None
        return await self.cycle(
            resource_id,
            compute,
            reason=ChangeReason.OBSERVATION,
            revision=evidence.id,
            actor=actor,
            principal=principal,
        )

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


__all__ = [
    "ConvergenceStatus",
    "Runtime",
    "RuntimeConvergence",
    "RuntimeCycle",
]
