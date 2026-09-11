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

ComputeFn = Callable[
    [ExecutionContext], Union[Awaitable["ComputeResult"], "ComputeResult"]
]


@dataclass
class ComputeResult:
    """What a compute participant returns to the engine."""

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
    """The single execution engine for the Voodoo runtime."""

    capabilities: CapabilityResolver = field(default_factory=CapabilityResolver)
    constraints: ConstraintEnforcer = field(default_factory=ConstraintEnforcer)
    resources: ResourceAccountant = field(default_factory=ResourceAccountant)
    executions: dict[str, Execution] = field(default_factory=dict)

    def __post_init__(self) -> None:
        from voodoo.runtime.human import ApprovalRegistry

        self.approvals = ApprovalRegistry()
        self._execution_store: Any = None
        self._checkpoint_sequences: dict[str, int] = {}
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
        """Register a named compute participant for durable resume (Sprint 18)."""
        self._participants[name] = {
            "compute": compute,
            "execute": execute,
            "kind": kind,
            "capabilities": capabilities or [],
        }

    def resolve_participant(self, name: str) -> Any | None:
        """Resolve a registered participant by name."""
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
        """Record a redacted approval decision as a journal event."""
        store = self._execution_store
        if store is not None and hasattr(store, "append_event"):
            from voodoo.security.redaction import redact

            store.append_event(execution_id, event, redact(payload))

    def checkpoint(self, execution: Execution) -> None:
        """Public checkpoint API — persists an execution mid-flight."""
        self._build_checkpoint(execution)
        self._persist(execution)

    def _build_checkpoint(self, execution: Execution) -> None:
        """Build a JSON-serializable checkpoint payload (spec §14)."""
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
        """Return effect ids already completed at last checkpoint."""
        if execution.checkpoint is None:
            return []
        return list(execution.checkpoint.get("completed_effects", []))

    def recover(self) -> list[Execution]:
        """Reload unfinished executions from the attached store."""
        from voodoo.runtime.persistence import filter_unfinished

        if self._execution_store is None:
            return []
        try:
            all_execs = self._execution_store.load_all()
        except Exception:  # noqa: BLE001
            return []
        recovered = []
        for ex in filter_unfinished(all_execs):
            if ex.status is ExecutionStatus.RUNNING:
                ex.wait()
            self.executions.setdefault(ex.id, ex)
            ex = self.executions[ex.id]
            recovered.append(ex)
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
                    self.approvals.create(execution=ex, requested_by=ex.actor)
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

    def _approval_parent_context(
        self, waiting: Execution | None, approval: Any
    ) -> ExecutionContext:
        """Rebuild the exact parent boundary used for an approved resume."""
        from voodoo.primitives.capability import Capability

        if approval.context is not None:
            parent = approval.context
            parent.engine = self
        elif waiting is not None:
            parent = ExecutionContext(
                execution_id=waiting.id,
                trace_id=waiting.trace_id,
                parent_execution_id=waiting.parent_execution_id,
                actor=waiting.actor,
                intent=waiting.intent,
                capabilities=[Capability(name=name) for name in waiting.capabilities],
                engine=self,
            )
            if waiting.intent is not None:
                for constraint in waiting.intent.constraints:
                    parent.constrain(constraint)
                parent.deadline = waiting.intent.deadline
        else:
            parent = ExecutionContext(actor=approval.requested_by, engine=self)
        return parent

    def _resolve_approved_compute(
        self, approval: Any, waiting: Execution | None
    ) -> None:
        """Restore compute and intent references available after a restart."""
        if approval.compute is None and approval.participant is not None:
            approval.compute = self._participant_compute(approval)
        if approval.intent is None and waiting is not None:
            approval.intent = waiting.intent

    def _complete_waiting(self, waiting: Execution, result: Any) -> None:
        """Transition the original waiting execution and persist it durably."""
        if waiting.status.terminal:
            return
        waiting.complete(result=result)
        self._build_checkpoint(waiting)
        self._persist(waiting)

    async def _resume_approved(
        self,
        approval: Any,
        waiting: Execution | None,
        *,
        by: str,
        note: str | None,
    ) -> Execution | None:
        """Resume approved compute as one direct child of the waiting execution."""
        from voodoo.primitives.capability import Capability
        from voodoo.runtime.human import ApprovalStatus

        self._resolve_approved_compute(approval, waiting)
        if approval.compute is None or approval.intent is None:
            if waiting is not None:
                self._complete_waiting(waiting, {"approved": True, "by": by})
            return waiting

        parent = self._approval_parent_context(waiting, approval)
        parent.metadata["approval"] = ApprovalStatus.APPROVED.value
        if note:
            parent.metadata["approval_note"] = note
        if approval.capability and not parent.has_capability(approval.capability):
            parent.grant(Capability(name=approval.capability))

        try:
            resumed = await self.execute(
                approval.intent,
                approval.compute,
                actor=f"approved:{by}",
                output_type=approval.output_type,
                parent=parent,
            )
        except Exception as error:
            if waiting is not None and not waiting.status.terminal:
                waiting.fail(f"approval resume failed: {error}")
                self._build_checkpoint(waiting)
                self._persist(waiting)
            raise

        if waiting is not None:
            self._complete_waiting(waiting, resumed.result)
        return resumed

    async def approve(
        self, execution_id: str, *, by: str = "human", note: str | None = None
    ) -> Execution | None:
        """Approve a waiting execution and durably resume it as a child."""
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
        return await self._resume_approved(approval, waiting, by=by, note=note)

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
        """Deny a waiting execution and persist its terminal failure."""
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
            self._build_checkpoint(waiting)
            self._persist(waiting)
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
        """Execute an intent through the canonical pipeline."""
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
            for required in intent.requires:
                self.capabilities.authorize(
                    required, context=ctx, execution_id=execution.id
                )
            execution.mark_authorized()
            self.constraints.enforce(ctx, execution_id=execution.id)
            execution.start()
            result = await self._run_compute(compute, ctx, output_type=output_type)
            await self._record_result(execution, intent, result, ctx)
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
            if effect.actor is None:
                effect.actor = ctx.actor
            if effect.capability_name is None and ctx.capabilities:
                effect.capability_name = ctx.capabilities[0].name
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

        self._build_checkpoint(execution)
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
        """Transition the execution to its terminal state and re-raise."""
        if isinstance(exc, ApprovalRequired):
            execution.wait()
            self._build_checkpoint(execution)
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
        """Execute a delegated (child) intent under a narrowed context."""
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
            return ctx
        ctx = ExecutionContext(actor=actor, intent=intent)
        ctx.engine = self
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
                latency = (time.time() - started) * 1000
                out = ComputeResult(
                    value=out,
                    output_type=output_type,
                    resources=Resource(latency_ms=latency),
                )

            if ctx.effects:
                seen = {e.id for e in out.effects}
                out.effects.extend(e for e in ctx.effects if e.id not in seen)
            return out

    async def _emit(self, event: str, payload: dict[str, Any]) -> None:
        """Publish a redacted namespaced mesh event best-effort."""
        try:
            from voodoo.mesh import mesh
            from voodoo.security.redaction import redact

            await mesh.broadcast(event, redact(payload))
        except Exception:  # noqa: BLE001
            pass

    def _record_telemetry(self, execution: Execution) -> None:
        """Record execution telemetry with redaction (Sprint 19)."""
        try:
            from voodoo.telemetry import telemetry_store

            telemetry_store.record_trace(
                f"execution.{execution.intent.name if execution.intent else 'anonymous'}",
                (execution.duration_seconds or 0.0) * 1000,
                error=execution.failed,
            )
        except Exception:  # noqa: BLE001
            pass


engine = ExecutionEngine()
