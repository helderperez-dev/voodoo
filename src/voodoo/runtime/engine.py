"""Execution Engine — the heart of the Voodoo runtime.

The engine turns an :class:`~voodoo.primitives.intent.Intent` (plus an
optional compute callable) into an :class:`~voodoo.runtime.execution.Execution`
by walking the canonical pipeline:

    Intent → Capability Resolution → Compute → Effect → State → Mesh events

Everything that executes (Python function, Agent, Tool, Worker, Human,
Workflow task) is expressed as a *compute callable* receiving the shared
:class:`~voodoo.runtime.context.ExecutionContext` and returning a result
plus optional effects/state changes. This keeps the architecture
AI-independent: agents are one kind of compute participant, not the
foundation.

The engine is deliberately small. Sophistication belongs in the model,
not the surface.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Union

from voodoo.primitives.effect import Effect
from voodoo.primitives.intent import Intent
from voodoo.primitives.resource import Resource
from voodoo.runtime.capability import CapabilityResolver
from voodoo.runtime.constraint import ConstraintEnforcer, ResourceAccountant
from voodoo.runtime.context import ExecutionContext, use_context
from voodoo.runtime.errors import (
    ApprovalRequired,
    ExecutionCancelled,
    ExecutionError,
    ExecutionTimeout,
)
from voodoo.runtime.execution import Execution, ExecutionStatus

__all__ = [
    "ComputeFn",
    "ComputeResult",
    "ExecutionEngine",
    "engine",
]

#: A compute participant. Receives the shared context, returns a result.
ComputeFn = Callable[[ExecutionContext], Union[Awaitable["ComputeResult"], "ComputeResult"]]


@dataclass
class ComputeResult:
    """What a compute participant returns to the engine.

    ``value``    — the primary output (validated when ``output_type`` is set)
    ``effects``  — side effects produced (recorded on the execution)
    ``states``   — state changes produced (recorded on the execution)
    ``resources``— resource usage to account for
    """

    value: Any = None
    effects: list[Effect] = field(default_factory=list)
    states: list[Any] = field(default_factory=list)
    resources: Resource | None = None
    output_type: type | None = None

    def validated(self) -> Any:
        """Validate ``value`` against ``output_type`` (pydantic/BaseModel)."""
        if self.output_type is None or self.value is None:
            return self.value
        from voodoo.runtime.errors import ValidationError

        try:
            if hasattr(self.output_type, "model_validate"):
                return self.output_type.model_validate(self.value)
            return self.output_type(**self.value) if isinstance(self.value, dict) else self.value
        except Exception as e:  # noqa: BLE001
            raise ValidationError(
                f"Structured output validation failed: {e}",
                context={"output_type": getattr(self.output_type, "__name__", str(self.output_type))},
            ) from e


@dataclass
class ExecutionEngine:
    """The single execution engine for the Voodoo runtime.

    Holds the capability resolver, constraint enforcer and resource
    accountant so that *one* policy system governs Agent, Tool, Worker,
    Workflow and Task — instead of each reimplementing authorization,
    retries, cost limits and telemetry.
    """

    capabilities: CapabilityResolver = field(default_factory=CapabilityResolver)
    constraints: ConstraintEnforcer = field(default_factory=ConstraintEnforcer)
    resources: ResourceAccountant = field(default_factory=ResourceAccountant)
    executions: dict[str, Execution] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Imported lazily to avoid a circular module dependency.
        from voodoo.runtime.human import ApprovalRegistry

        self.approvals = ApprovalRegistry()
        self._execution_store: Any = None

    # -- persistence / recovery ---------------------------------------------

    def use_store(self, store: Any) -> None:
        """Attach an ExecutionStore (persistence seam, Phase 11)."""
        self._execution_store = store

    def _persist(self, execution: Execution) -> None:
        """Checkpoint an execution (best-effort — never breaks execution)."""
        if self._execution_store is None:
            return
        try:
            self._execution_store.save(execution)
        except Exception:  # noqa: BLE001
            pass

    def checkpoint(self, execution: Execution) -> None:
        """Public checkpoint API — persists an execution mid-flight.

        Used by workflows to checkpoint per-task progress so a restart
        can recover partial workflow state.
        """
        self._persist(execution)

    def recover(self) -> list[Execution]:
        """Reload unfinished executions from the attached store.

        Restores ``waiting``/``running`` executions into the engine after a
        restart so they remain inspectable and resumable (e.g. pending
        human approvals). Returns the recovered executions.
        """
        from voodoo.runtime.persistence import filter_unfinished

        if self._execution_store is None:
            return []
        try:
            all_execs = self._execution_store.load_all()
        except Exception:  # noqa: BLE001
            return []
        recovered = []
        for ex in filter_unfinished(all_execs):
            self.executions.setdefault(ex.id, ex)
            ex = self.executions[ex.id]
            recovered.append(ex)
            # Rebuild a pending approval record for waiting executions so
            # `inspect approvals` and `approve()` work after a restart.
            # Note: the original compute/intent are not serialized yet, so a
            # restarted approval can be decided but not re-run (documented).
            if ex.status is ExecutionStatus.WAITING and self.approvals.get(ex.id) is None:
                self.approvals.create(
                    execution=ex,
                    requested_by=ex.actor,
                )
        return recovered

    # -- human-in-the-loop --------------------------------------------------

    async def approve(
        self, execution_id: str, *, by: str = "human", note: str | None = None
    ) -> Execution | None:
        """Approve a waiting execution and resume it as a child execution."""
        from voodoo.primitives.capability import Capability
        from voodoo.runtime.human import ApprovalStatus

        approval = self.approvals.decide(
            execution_id, ApprovalStatus.APPROVED, by=by, reason=note
        )
        if approval is None:
            return None
        waiting = self.executions.get(execution_id)
        if waiting is not None:
            waiting.metadata["approved_by"] = by
        await self._emit(
            "human.approved",
            {"execution_id": execution_id, "by": by, "capability": approval.capability},
        )
        if approval.compute is None or approval.intent is None:
            if waiting is not None:
                waiting.complete(result={"approved": True, "by": by})
            return waiting

        # Resume under a child context carrying the decision.
        base = approval.context or ExecutionContext(actor=approval.requested_by)
        child_ctx = base.child(actor=f"approved:{by}")
        child_ctx.metadata["approval"] = ApprovalStatus.APPROVED.value
        if note:
            child_ctx.metadata["approval_note"] = note
        if approval.capability:
            child_ctx.grant(Capability(name=approval.capability))

        resumed = await self.execute(
            approval.intent,
            approval.compute,
            actor=child_ctx.actor,
            output_type=approval.output_type,
            parent=child_ctx,
        )
        # link + complete the waiting execution with the resumed result
        resumed.parent_execution_id = waiting.id if waiting else None
        if waiting is not None:
            waiting.complete(result=resumed.result)
        return resumed

    async def deny(
        self, execution_id: str, *, by: str = "human", reason: str = "denied"
    ) -> Execution | None:
        """Deny a waiting execution; it fails with the denial reason."""
        from voodoo.runtime.human import ApprovalStatus

        approval = self.approvals.decide(execution_id, ApprovalStatus.DENIED, by=by, reason=reason)
        if approval is None:
            return None
        waiting = self.executions.get(execution_id)
        if waiting is not None:
            waiting.fail(f"denied by {by}: {reason}")
        await self._emit(
            "human.denied",
            {"execution_id": execution_id, "by": by, "reason": reason},
        )
        return waiting

    # -- public API --------------------------------------------------------

    async def execute(
        self,
        intent: Intent,
        compute: ComputeFn | None = None,
        *,
        actor: str = "system",
        capabilities: list[str] | None = None,
        output_type: type | None = None,
        parent: ExecutionContext | None = None,
    ) -> Execution:
        """Execute an intent through the canonical pipeline.

        Parameters
        ----------
        intent:
            The outcome to achieve.
        compute:
            The compute participant (sync or async). If ``None``, the
            intent's ``params`` are returned as the result — useful for
            pure intent routing / testing.
        actor:
            Who is requesting the execution.
        capabilities:
            Capability names to grant for this execution (resolved against
            the registered capability templates).
        output_type:
            Optional structured-output type to validate the result against.
        parent:
            Optional parent context for delegated/child executions.
        """
        ctx = self._build_context(intent, actor=actor, parent=parent)
        if capabilities:
            from voodoo.primitives.capability import Capability

            for name in capabilities:
                cap = self.capabilities.capabilities.get(name)
                ctx.grant(cap if cap is not None else Capability(name=name))

        execution = Execution(
            id=ctx.execution_id,
            trace_id=ctx.trace_id,
            parent_execution_id=ctx.parent_execution_id,
            intent=intent,
            actor=actor,
            capabilities=[c.name for c in ctx.capabilities],
        )
        if ctx.intent is not None:
            ctx.intent.execute()
        self.executions[execution.id] = execution

        await self._emit("intent.created", {"intent": intent.name, "execution_id": execution.id})
        await self._emit(
            "execution.started",
            {"execution_id": execution.id, "trace_id": ctx.trace_id, "intent": intent.name},
        )

        try:
            # 1. Capability resolution
            for required in intent.requires:
                self.capabilities.authorize(required, context=ctx, execution_id=execution.id)
            execution.mark_authorized()

            # 2. Constraint pre-check
            self.constraints.enforce(ctx, execution_id=execution.id)

            # 3. Compute
            execution.start()
            result = await self._run_compute(compute, ctx, output_type=output_type)

            # 4. Record effects / state / resources + post-compute checks
            await self._record_result(execution, intent, result, ctx)

            # 5. Complete intent + execution
            value = result.validated()
            if ctx.intent is not None:
                ctx.intent.complete(result=value)
            execution.complete(result=value)

            await self._emit(
                "execution.completed",
                {"execution_id": execution.id, "status": "completed", "cost": execution.cost},
            )
            self._persist(execution)
        except Exception as e:  # noqa: BLE001
            await self._handle_failure(
                execution, ctx, e, intent=intent, compute=compute, output_type=output_type
            )

        # Record to existing telemetry store for continuity.
        self._record_telemetry(execution)
        return execution

    async def _record_result(
        self, execution: Execution, intent: Intent, result: ComputeResult, ctx: ExecutionContext
    ) -> None:
        """Record a compute result's effects, state changes and resources."""
        for effect in result.effects:
            effect.intent_id = intent.id
            execution.add_effect(effect)
            await self._emit(
                "effect.executed",
                {
                    "execution_id": execution.id,
                    "effect": effect.name,
                    "status": effect.status.value,
                },
            )
        for st in result.states:
            execution.record_state_change(st)
            await self._emit(
                "state.changed",
                {"execution_id": execution.id, "kind": getattr(st, "kind", "entity")},
            )
        if result.resources is not None:
            execution.add_resources(result.resources)
            self.resources.account(result.resources, execution_id=execution.id)

        # Post-compute constraint enforcement against accumulated usage.
        self.constraints.enforce(
            ctx,
            cost=execution.resources.cost or None,
            tokens=execution.resources.tokens,
            latency_ms=execution.resources.latency_ms,
            execution_id=execution.id,
        )

    async def _handle_failure(
        self,
        execution: Execution,
        ctx: ExecutionContext,
        exc: Exception,
        *,
        intent: Intent | None = None,
        compute: ComputeFn | None = None,
        output_type: type | None = None,
    ) -> None:
        """Transition the execution to its terminal state and re-raise.

        Structured runtime errors pass through unchanged, retaining their
        execution identity; bare exceptions are wrapped in ``ExecutionError``.
        """
        if isinstance(exc, ApprovalRequired):
            execution.wait()
            # Register a resumable approval: approve() re-runs the compute
            # under a child context carrying the decision.
            self.approvals.create(
                execution=execution,
                capability=exc.context.get("capability"),
                question=exc.message,
                requested_by=execution.actor,
                intent=intent,
                compute=compute,
                output_type=output_type,
                context=ctx,
            )
            await self._emit(
                "human.approval_required",
                {
                    "execution_id": execution.id,
                    "capability": exc.context.get("capability"),
                    "question": exc.message,
                },
            )
        elif isinstance(exc, ExecutionCancelled):
            execution.cancel()
            await self._emit("execution.cancelled", {"execution_id": execution.id})
        elif isinstance(exc, ExecutionTimeout):
            execution.time_out()
            await self._emit(
                "execution.failed", {"execution_id": execution.id, "reason": "timeout"}
            )
        elif isinstance(exc, ExecutionError):
            execution.fail(exc.message)
            await self._emit(
                "execution.failed",
                {
                    "execution_id": execution.id,
                    "reason": type(exc).__name__,
                    "message": exc.message,
                },
            )
        else:
            execution.fail(str(exc))
            await self._emit(
                "execution.failed",
                {"execution_id": execution.id, "reason": "error", "message": str(exc)},
            )
            raise ExecutionError(
                str(exc), execution_id=execution.id, trace_id=ctx.trace_id
            ) from exc
        self._persist(execution)
        raise exc

    async def delegate(
        self,
        intent: Intent,
        compute: ComputeFn,
        *,
        parent: ExecutionContext,
        actor: str,
        output_type: type | None = None,
    ) -> Execution:
        """Execute a delegated (child) intent under a narrowed context.

        Delegation always creates a child execution with
        ``parent_execution_id`` set, enabling auditability and limiting
        privilege escalation.
        """
        return await self.execute(
            intent,
            compute,
            actor=actor,
            output_type=output_type,
            parent=parent,
        )

    # -- inspection --------------------------------------------------------

    def get(self, execution_id: str) -> Execution | None:
        return self.executions.get(execution_id)

    def recent(self, limit: int = 20) -> list[Execution]:
        return list(self.executions.values())[-limit:]

    # -- internals ---------------------------------------------------------

    def _build_context(
        self, intent: Intent, *, actor: str, parent: ExecutionContext | None
    ) -> ExecutionContext:
        if parent is not None:
            ctx = parent.child(actor=actor)
            ctx.intent = intent
            # narrow authority: child may only keep capabilities it holds
            return ctx
        ctx = ExecutionContext(actor=actor, intent=intent)
        ctx.engine = self
        # inherit intent constraints/deadline
        for c in intent.constraints:
            ctx.constrain(c)
        if intent.deadline is not None:
            ctx.deadline = intent.deadline
        return ctx

    async def _run_compute(
        self,
        compute: ComputeFn | None,
        ctx: ExecutionContext,
        *,
        output_type: type | None,
    ) -> ComputeResult:
        if compute is None:
            return ComputeResult(value=ctx.intent.params if ctx.intent else None, output_type=output_type)

        async with use_context(ctx):
            started = time.time()
            try:
                out = compute(ctx)
                if inspect.isawaitable(out):
                    out = await out
            except asyncio.CancelledError:
                raise ExecutionCancelled(
                    "Compute was cancelled",
                    execution_id=ctx.execution_id,
                    trace_id=ctx.trace_id,
                ) from None

            if isinstance(out, ComputeResult):
                if out.output_type is None:
                    out.output_type = output_type
            else:
                # bare return → wrap
                latency = (time.time() - started) * 1000
                out = ComputeResult(
                    value=out,
                    output_type=output_type,
                    resources=Resource(latency_ms=latency),
                )

            # Lift effects recorded on the context (e.g. tool calls made
            # deep inside an Agent run) onto the compute result so they
            # materialize on the Execution record.
            if ctx.effects:
                seen = {e.id for e in out.effects}
                out.effects.extend(e for e in ctx.effects if e.id not in seen)
            return out

    async def _emit(self, event: str, payload: dict[str, Any]) -> None:
        """Publish a namespaced mesh event (best-effort, never breaks)."""
        try:
            from voodoo.mesh import mesh

            await mesh.broadcast(event, payload)
        except Exception:  # noqa: BLE001
            pass

    def _record_telemetry(self, execution: Execution) -> None:
        try:
            from voodoo.telemetry import telemetry_store

            telemetry_store.record_trace(
                f"execution.{execution.intent.name if execution.intent else 'anonymous'}",
                (execution.duration_seconds or 0.0) * 1000,
                error=execution.failed,
            )
        except Exception:  # noqa: BLE001
            pass


#: The default/global execution engine.
engine = ExecutionEngine()
