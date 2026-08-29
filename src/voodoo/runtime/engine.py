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
from datetime import datetime
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
ComputeFn = Callable[
    [ExecutionContext], Union[Awaitable["ComputeResult"], "ComputeResult"]
]


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
            return (
                self.output_type(**self.value)
                if isinstance(self.value, dict)
                else self.value
            )
        except Exception as e:  # noqa: BLE001
            raise ValidationError(
                f"Structured output validation failed: {e}",
                context={
                    "output_type": getattr(
                        self.output_type, "__name__", str(self.output_type)
                    )
                },
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
        self._checkpoint_sequences: dict[str, int] = {}
        #: Durable compute registry — named participants that can be
        #: re-resolved after a restart (Sprint 18). Maps participant
        #: name → compute callable + metadata.
        self._participants: dict[str, Any] = {}

    # -- persistence / recovery ---------------------------------------------

    def use_store(self, store: Any) -> None:
        """Attach an ExecutionStore (persistence seam, Phase 11)."""
        self._execution_store = store

    def register_participant(
        self,
        name: str,
        compute: ComputeFn | None = None,
        *,
        execute: Any | None = None,
        kind: str = "compute",
        capabilities: list[str] | None = None,
    ) -> None:
        """Register a named compute participant for durable resume (Sprint 18).

        Participants registered here can be re-resolved by name after a
        process restart, making ``WAITING_FOR_HUMAN`` executions fully
        resumable on any worker (ROADMAP §50).
        """
        self._participants[name] = {
            "compute": compute,
            "execute": execute,
            "kind": kind,
            "capabilities": capabilities or [],
        }

    def resolve_participant(self, name: str) -> Any | None:
        """Resolve a registered participant by name.

        Returns the registration dict, or ``None`` when not registered.
        """
        return self._participants.get(name)

    def _persist(self, execution: Execution) -> None:
        """Checkpoint an execution — raises on failure (spec §51.16)."""
        if self._execution_store is None:
            return
        self._execution_store.save(execution)

    def _persist_approval(self, approval: Any) -> None:
        """Persist an approval record when the store supports it (Sprint 4)."""
        store = self._execution_store
        if store is None or not hasattr(store, "save_approval"):
            return
        store.save_approval(approval)

    def _journal_approval_decision(
        self, execution_id: str, event: str, payload: dict
    ) -> None:
        """Record an approval decision as a journal event (Sprint 4)."""
        store = self._execution_store
        if store is not None and hasattr(store, "append_event"):
            store.append_event(execution_id, event, payload)

    def checkpoint(self, execution: Execution) -> None:
        """Public checkpoint API — persists an execution mid-flight.

        Used by workflows to checkpoint per-task progress so a restart
        can recover partial workflow state.
        """
        self._build_checkpoint(execution)
        self._persist(execution)

    def _build_checkpoint(self, execution: Execution) -> None:
        """Build a JSON-serializable checkpoint payload (spec §14).

        Captures resumable state: completed effect ids (for idempotency
        skip), current step, state changes count, and metadata.
        Never includes live Python objects.
        """
        from voodoo.primitives.effect import EffectStatus

        completed_effects = [
            e.id for e in execution.effects if e.status is EffectStatus.SUCCEEDED
        ]
        execution.checkpoint = {
            "sequence": self._checkpoint_sequences.get(execution.id, 0),
            "completed_effects": completed_effects,
            "state_changes_count": len(execution.state_changes),
            "status": execution.status.value,
            "metadata": execution.metadata,
        }
        self._checkpoint_sequences[execution.id] = (
            self._checkpoint_sequences.get(execution.id, 0) + 1
        )

    def resume_checkpoint(self, execution: Execution) -> list[str]:
        """Return effect ids already completed at last checkpoint.

        Used by resumed executions to skip re-running non-idempotent
        effects (spec §15).
        """
        if execution.checkpoint is None:
            return []
        return list(execution.checkpoint.get("completed_effects", []))

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
            # A running execution left over from a crash is recoverable:
            # mark it waiting so it can be resumed from its last checkpoint.
            if ex.status is ExecutionStatus.RUNNING:
                ex.wait()
            self.executions.setdefault(ex.id, ex)
            ex = self.executions[ex.id]
            recovered.append(ex)
            # Rebuild a pending approval record for waiting executions so
            # `inspect approvals` and `approve()` work after a restart.
            # When the store persisted the approval (Sprint 4), rehydrate
            # it (status, decided_by, reason, …); otherwise create an
            # in-memory placeholder (the original compute/intent are not
            # serialized, so a restarted approval can be decided but not
            # re-run — documented).
            if (
                ex.status is ExecutionStatus.WAITING
                and self.approvals.get(ex.id) is None
            ):
                persisted = None
                if hasattr(self._execution_store, "load_approval"):
                    persisted = self._execution_store.load_approval(ex.id)
                if persisted is not None:
                    self._rehydrate_approval(ex, persisted)
                else:
                    self.approvals.create(
                        execution=ex,
                        requested_by=ex.actor,
                    )
        return recovered

    def _rehydrate_approval(self, execution: Execution, record: dict) -> None:
        """Reconstruct an approval record from its persisted form (Sprint 4)."""
        from voodoo.runtime.human import Approval, ApprovalStatus

        approval = Approval(
            id=record["id"],
            execution_id=record["execution_id"],
            trace_id=record["trace_id"] or execution.trace_id,
            capability=record["capability"],
            question=record["question"] or "",
            requested_by=record["requested_by"] or execution.actor,
            status=ApprovalStatus(record["status"]),
            decided_by=record["decided_by"],
            decided_at=(
                datetime.fromisoformat(record["decided_at"])
                if record["decided_at"]
                else None
            ),
            reason=record["reason"],
            participant=record.get("participant"),
        )
        self.approvals.records[execution.id] = approval

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
        self._persist_approval(approval)
        self._journal_approval_decision(
            execution_id,
            "approval.granted",
            {"by": by, "capability": approval.capability},
        )
        waiting = self.executions.get(execution_id)
        if waiting is not None:
            waiting.metadata["approved_by"] = by
        await self._emit(
            "human.approved",
            {"execution_id": execution_id, "by": by, "capability": approval.capability},
        )

        # Durable resume (Sprint 18): when the live compute is gone (e.g.
        # after a restart) but a registered participant exists, re-resolve
        # the compute from the participant registry. The waiting execution's
        # persisted intent supplies the outcome when the approval record
        # has none (a restarted process serializes no live objects).
        if approval.compute is None and approval.participant is not None:
            approval.compute = self._participant_compute(approval)
        if approval.intent is None and waiting is not None:
            approval.intent = waiting.intent
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

    def _participant_compute(self, approval: Any) -> ComputeFn | None:
        """Synchronously re-resolve compute from the participant registry."""
        if approval.participant is None:
            return None
        participant = self.resolve_participant(approval.participant)
        if participant is None:
            return None
        return participant["compute"]

    async def deny(
        self, execution_id: str, *, by: str = "human", reason: str = "denied"
    ) -> Execution | None:
        """Deny a waiting execution; it fails with the denial reason."""
        from voodoo.runtime.human import ApprovalStatus

        approval = self.approvals.decide(
            execution_id, ApprovalStatus.DENIED, by=by, reason=reason
        )
        if approval is None:
            return None
        self._persist_approval(approval)
        self._journal_approval_decision(
            execution_id,
            "approval.denied",
            {"by": by, "reason": reason},
        )
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

        await self._emit(
            "intent.created", {"intent": intent.name, "execution_id": execution.id}
        )
        await self._emit(
            "execution.started",
            {
                "execution_id": execution.id,
                "trace_id": ctx.trace_id,
                "intent": intent.name,
            },
        )

        try:
            # 1. Capability resolution
            for required in intent.requires:
                self.capabilities.authorize(
                    required, context=ctx, execution_id=execution.id
                )
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
                {
                    "execution_id": execution.id,
                    "status": "completed",
                    "cost": execution.cost,
                },
            )
            self._build_checkpoint(execution)
            self._persist(execution)
        except Exception as e:  # noqa: BLE001
            await self._handle_failure(
                execution,
                ctx,
                e,
                intent=intent,
                compute=compute,
                output_type=output_type,
            )

        # Record to existing telemetry store for continuity.
        self._record_telemetry(execution)
        return execution

    async def _record_result(
        self,
        execution: Execution,
        intent: Intent,
        result: ComputeResult,
        ctx: ExecutionContext,
    ) -> None:
        """Record a compute result's effects, state changes and resources."""
        for effect in result.effects:
            effect.intent_id = intent.id
            # Idempotency key: stable per execution+effect so a resumed
            # execution can safely skip already-completed effects (spec §15).
            if effect.idempotency_key is None:
                effect.idempotency_key = f"{execution.id}:{effect.id}"
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

        # Checkpoint after state mutation / effects recorded (Sprint 4).
        self._build_checkpoint(execution)

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
            self._build_checkpoint(execution)
            # Register a resumable approval: approve() re-runs the compute
            # under a child context carrying the decision.
            approval = self.approvals.create(
                execution=execution,
                capability=exc.context.get("capability"),
                question=exc.message,
                requested_by=execution.actor,
                intent=intent,
                compute=compute,
                output_type=output_type,
                context=ctx,
            )
            # Persist the pending approval so a restart can rehydrate it
            # (spec §30 — decisions recorded as journal events on decide).
            self._persist_approval(approval)
            self._journal_approval_decision(
                execution.id,
                "approval.requested",
                {
                    "capability": exc.context.get("capability"),
                    "question": exc.message,
                    "requested_by": execution.actor,
                },
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
            return ComputeResult(
                value=ctx.intent.params if ctx.intent else None, output_type=output_type
            )

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
