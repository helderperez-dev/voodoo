"""Sprint 4 — Checkpoints & resume tests.

Covers: crash between steps → resume skips completed steps; duplicate
resume safe; checkpoint payload stays JSON-compatible.
"""

from __future__ import annotations

import json

import pytest

from voodoo.primitives.effect import Effect
from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.errors import ApprovalRequired
from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.storage.execution import SQLiteExecutionStore


class TestCheckpointBoundaries:
    async def test_checkpoint_after_state_changes(self):
        engine = ExecutionEngine()
        ex = await engine.execute(
            Intent(name="checkpoint_test"), lambda ctx: {"ok": True}
        )
        assert ex.checkpoint is not None
        assert ex.checkpoint["status"] == "completed"

    async def test_checkpoint_before_waiting(self):
        engine = ExecutionEngine()
        store = SQLiteExecutionStore(":memory:")

        engine.use_store(store)

        async def compute(ctx):
            raise ApprovalRequired("please approve")

        with pytest.raises(ApprovalRequired):
            await engine.execute(Intent(name="needs_approval"), compute)
        waiting = engine.recent(1)[0]
        assert waiting.status is ExecutionStatus.WAITING
        assert waiting.checkpoint is not None
        store.close()

    def test_checkpoint_is_json_serializable(self):
        engine = ExecutionEngine()
        ex = Execution(id="chk", trace_id="t", intent=Intent(name="chk"), actor="t")
        engine.executions[ex.id] = ex
        engine._build_checkpoint(ex)
        assert ex.checkpoint is not None
        json.dumps(ex.checkpoint)  # should not raise


class TestResumeSkipsCompletedEffects:
    async def test_resume_skips_completed_effects(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        engine = ExecutionEngine()
        engine.use_store(store)

        # First run: one effect completes, then process "crashes"
        from voodoo.primitives.intent import Intent as I
        from voodoo.runtime.execution import Execution

        ex = Execution(
            id="ex1", trace_id="t1", intent=I(name="multi_step"), actor="test"
        )
        effect = Effect(name="step1", idempotent=False)
        effect.mark_succeeded()
        ex.add_effect(effect)
        ex.start()
        engine._build_checkpoint(ex)
        store.save(ex)
        store.close()

        # "Restart": fresh engine recovers
        store2 = SQLiteExecutionStore(tmp_path / "executions.db")
        engine2 = ExecutionEngine()
        engine2.use_store(store2)
        recovered = engine2.recover()
        assert len(recovered) == 1
        resumed = recovered[0]
        completed = engine2.resume_checkpoint(resumed)
        assert effect.id in completed
        store2.close()

    async def test_duplicate_resume_is_safe(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        engine = ExecutionEngine()
        engine.use_store(store)

        # Simulate two recoveries
        ex = Execution(id="dup", trace_id="t", intent=Intent(name="dup"), actor="t")
        ex.wait()
        store.save(ex)

        engine2 = ExecutionEngine()
        engine2.use_store(store)
        recovered1 = engine2.recover()
        recovered2 = engine2.recover()  # duplicate
        assert len(recovered1) == 1
        assert len(recovered2) == 1
        assert recovered1[0].id == recovered2[0].id
        store.close()


class TestRecoveryRunningToWaiting:
    async def test_running_recovered_as_waiting(self, tmp_path):
        store = SQLiteExecutionStore(tmp_path / "executions.db")
        ex = Execution(id="crash", trace_id="t", intent=Intent(name="crash"), actor="t")
        ex.start()  # RUNNING
        store.save(ex)

        engine = ExecutionEngine()
        engine.use_store(store)
        recovered = engine.recover()
        assert recovered[0].status is ExecutionStatus.WAITING
        store.close()


class TestIdempotencyKeyOnEffects:
    async def test_effects_get_idempotency_key(self):
        engine = ExecutionEngine()

        async def compute(ctx):
            from voodoo.primitives.effect import Effect
            from voodoo.runtime.engine import ComputeResult

            return ComputeResult(effects=[Effect(name="send_email", idempotent=False)])

        ex = await engine.execute(Intent(name="with_effect"), compute)
        assert len(ex.effects) == 1
        assert ex.effects[0].idempotency_key is not None
        assert ex.effects[0].idempotency_key.startswith(ex.id)
