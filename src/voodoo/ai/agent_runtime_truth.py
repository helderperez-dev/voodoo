"""Runtime-truth behavior for Voodoo agents.

This module centralizes the corrections required for Sprint 24.2 without
creating a second agent runtime. It is imported by ``voodoo.ai.agent`` and
keeps ``Execution`` as the canonical lifecycle while preserving standalone
Agent compatibility.
"""

from __future__ import annotations

from typing import Any

from voodoo.ai.agent_legacy import Agent as LegacyAgent
from voodoo.ai.agent_legacy import AgentRun


class RuntimeTruthAgent(LegacyAgent):
    """Agent implementation aligned with the canonical Execution lifecycle."""

    @staticmethod
    def _runtime_context() -> Any | None:
        try:
            from voodoo.runtime.context import current_context

            return current_context()
        except Exception:  # noqa: BLE001
            return None

    def _canonical_execution_id(self, run_record: AgentRun) -> str | None:
        """Return the canonical execution id when the run is engine-backed."""
        if run_record.execution_id:
            return run_record.execution_id
        ctx = self._runtime_context()
        if ctx is not None and run_record.run_id == ctx.execution_id:
            return ctx.execution_id
        return None

    def _canonical_trace_id(self, run_record: AgentRun) -> str | None:
        """Prefer the runtime trace over optional telemetry-local correlation."""
        ctx = self._runtime_context()
        if ctx is not None and run_record.run_id == ctx.execution_id:
            return ctx.trace_id
        return run_record.trace_id

    def _apply_lineage(self, run_record: AgentRun) -> tuple[str | None, str | None]:
        execution_id = self._canonical_execution_id(run_record)
        trace_id = self._canonical_trace_id(run_record)
        if execution_id is not None:
            run_record.execution_id = execution_id
        if trace_id is not None:
            run_record.trace_id = trace_id
        return execution_id, trace_id

    async def _record_run(self, run_record: AgentRun) -> None:
        """Persist agent history with execution and trace identities separated."""
        if self._agent_registry is None:
            return
        from voodoo.agents.models import AgentRunRecord

        await self._ensure_registered()
        execution_id, trace_id = self._apply_lineage(run_record)
        record = AgentRunRecord(
            run_id=run_record.run_id,
            agent_id=self.agent_id,
            execution_id=execution_id,
            prompt=run_record.prompt,
            output=run_record.output,
            status=run_record.status,
            tokens_in=run_record.tokens_in,
            tokens_out=run_record.tokens_out,
            cost=run_record.cost,
            tool_calls=run_record.tool_calls,
            started_at=run_record.started_at,
            completed_at=run_record.completed_at,
            trace_id=trace_id,
        )
        await self._agent_registry.record_run(record)

    async def _write_episodic_memory(self, run_record: AgentRun) -> None:
        """Write private episodic memory linked to the canonical execution."""
        from voodoo.memory.interfaces import MemoryEntry, MemoryLayer

        tool_summary = ""
        if run_record.tool_calls:
            names = [tc["name"] for tc in run_record.tool_calls]
            tool_summary = f" Tools used: {', '.join(names)}."

        execution_id, trace_id = self._apply_lineage(run_record)
        content = (
            f"Run {run_record.run_id}: {run_record.prompt[:200]} "
            f"→ {run_record.output[:200]}.{tool_summary}"
        )
        entry = MemoryEntry(
            entity_id=self.agent_id,
            layer=MemoryLayer.EPISODIC,
            content=content,
            metadata={
                "run_id": run_record.run_id,
                "agent_id": self.agent_id,
                "execution_id": execution_id,
                "trace_id": trace_id,
                "model": run_record.model,
                "provider": run_record.provider,
                "tokens_in": run_record.tokens_in,
                "tokens_out": run_record.tokens_out,
                "cost": run_record.cost,
                "status": run_record.status,
                "tool_count": len(run_record.tool_calls),
            },
            tags=["agent-run", run_record.provider],
            source_execution_id=execution_id,
            importance=0.6,
        )
        try:
            self.memory.write(entry)
        except Exception:  # noqa: BLE001 — memory writes never break the run
            pass

    async def _execute_tool_as_child_execution(
        self,
        engine: Any,
        name: str,
        arguments: dict[str, Any],
        spec: Any,
        parent_ctx: Any,
    ) -> Any:
        """Persist a failed child Execution when a tool raises.

        The parent agent may still reason about the returned error and recover,
        but observability must never claim the tool Execution succeeded.
        """
        from voodoo.primitives.intent import Intent
        from voodoo.runtime.context import ExecutionContext
        from voodoo.runtime.errors import ExecutionError

        intent = Intent(
            name=f"tool.{name}",
            description=f"Tool call: {name}",
            params={"tool": name, "arguments": arguments},
            requires=list(spec.permissions if spec else []),
        )

        async def _tool_compute(ctx: ExecutionContext) -> Any:
            await self._broadcast("tool.called", {"tool": name, "arguments": arguments})
            try:
                result = await self.registry.call(name, **arguments)
            except Exception as error:
                await self._broadcast(
                    "tool.completed",
                    {"tool": name, "status": "failed", "error": str(error)},
                )
                raise
            await self._broadcast(
                "tool.completed", {"tool": name, "status": "succeeded"}
            )
            return result

        try:
            execution = await engine.execute(
                intent,
                _tool_compute,
                actor=f"agent:{self.agent_id}",
                capabilities=list(spec.permissions if spec else []),
                parent=parent_ctx,
            )
        except ExecutionError as error:
            return {"error": error.message}
        return execution.result

    async def _provider_loop(self, *args: Any, **kwargs: Any) -> AgentRun:
        """Propagate engine-backed agent failure into the canonical Execution.

        Standalone callers retain the historic behavior of receiving a failed
        ``AgentRun``. Inside an ``ExecutionEngine`` context a failed provider
        loop raises ``ExecutionError`` after telemetry/history/memory have been
        recorded, allowing the engine to persist the Execution as FAILED.
        """
        run_record = await super()._provider_loop(*args, **kwargs)
        execution_id, trace_id = self._apply_lineage(run_record)

        if run_record.status == "failed" and execution_id is not None:
            from voodoo.runtime.errors import AgentExecutionError

            raise AgentExecutionError(
                run_record.error or "agent run failed",
                execution_id=execution_id,
                trace_id=trace_id,
                context={"agent_id": self.agent_id, "run_id": run_record.run_id},
            )
        return run_record
