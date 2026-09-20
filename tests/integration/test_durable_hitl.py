"""Tests for Sprint 18 — Durable human-in-the-loop.

Acceptance criterion: request approval → kill process → decide via CLI →
execution resumes and completes with the correct result.
"""

from __future__ import annotations

import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.errors import ApprovalRequired
from voodoo.runtime.human import Approval, ApprovalRegistry, ApprovalStatus
from voodoo.storage.execution import SQLiteExecutionStore

# ---------------------------------------------------------------------------
# Approval model
# ---------------------------------------------------------------------------


class TestApprovalParticipant:
    async def test_approval_has_participant_field(self) -> None:
        approval = Approval(
            execution_id="ex-1",
            trace_id="tr-1",
            question="Deploy?",
            participant="deploy_workflow",
        )
        assert approval.participant == "deploy_workflow"
        assert approval.status is ApprovalStatus.PENDING

    async def test_approval_participant_defaults_none(self) -> None:
        approval = Approval(execution_id="ex-1", trace_id="tr-1")
        assert approval.participant is None


# ---------------------------------------------------------------------------
# Participant registry
# ---------------------------------------------------------------------------


class TestParticipantRegistry:
    async def test_register_and_resolve(self) -> None:
        eng = ExecutionEngine()

        def compute(ctx: ExecutionContext):  # type: ignore[type-arg]
            return None

        eng.register_participant("deployer", compute)
        resolved = eng.resolve_participant("deployer")
        assert resolved is not None
        assert resolved["compute"] is compute
        assert resolved["kind"] == "compute"

    async def test_resolve_unknown_returns_none(self) -> None:
        eng = ExecutionEngine()
        assert eng.resolve_participant("ghost") is None


# ---------------------------------------------------------------------------
# Durable approval persistence (participant column)
# ---------------------------------------------------------------------------


class TestDurableApprovalPersistence:
    async def test_participant_persisted_and_rehydrated(self, tmp_path) -> None:
        """Approvals persist their participant across a store reopen."""
        db = str(tmp_path / "state.db")

        # Process 1: execute something requiring approval with a
        # registered participant, then "die".
        eng = ExecutionEngine()
        store = SQLiteExecutionStore(db)
        eng.use_store(store)

        def risky(ctx: ExecutionContext):  # type: ignore[type-arg]
            raise ApprovalRequired(
                "Deploy to production?",
                execution_id=ctx.execution_id,
                trace_id=ctx.trace_id,
                context={"capability": "deploy.execute"},
            )

        with pytest.raises(ApprovalRequired):
            await eng.execute(Intent(name="deploy"), risky)
        ex = eng.executions[list(eng.executions)[-1]]

        # Attach the participant name to the persisted approval record.
        approval = eng.approvals.get(ex.id)
        assert approval is not None
        approval.participant = "deploy_workflow"
        eng._persist_approval(approval)
        store.close()

        # Process 2: fresh engine + same store. The approval survives with
        # its participant name intact.
        eng2 = ExecutionEngine()
        store2 = SQLiteExecutionStore(db)
        eng2.use_store(store2)
        eng2.recover()

        rehydrated = eng2.approvals.get(ex.id)
        assert rehydrated is not None
        assert rehydrated.participant == "deploy_workflow"
        assert rehydrated.status is ApprovalStatus.PENDING
        store2.close()

    async def test_load_approvals_lists_pending(self, tmp_path) -> None:
        db = str(tmp_path / "state.db")
        store = SQLiteExecutionStore(db)

        approval = Approval(
            execution_id="ex-a",
            trace_id="tr-a",
            question="Ship it?",
            participant="ship_wf",
        )
        store.save_approval(approval)

        pending = store.load_approvals(pending_only=True)
        assert len(pending) == 1
        assert pending[0]["execution_id"] == "ex-a"
        assert pending[0]["participant"] == "ship_wf"
        assert pending[0]["status"] == "pending"

        # Decide it; pending list empties, full list keeps it.
        decided = Approval(
            execution_id="ex-a",
            trace_id="tr-a",
            question="Ship it?",
            participant="ship_wf",
            status=ApprovalStatus.APPROVED,
            decided_by="ops",
            id=approval.id,
        )
        store.save_approval(decided)

        assert store.load_approvals(pending_only=True) == []
        assert len(store.load_approvals()) == 1
        assert store.load_approvals()[0]["status"] == "approved"
        store.close()


# ---------------------------------------------------------------------------
# Acceptance criterion: crash → decide → resume completes
# ---------------------------------------------------------------------------


class TestCrashResumeAcceptance:
    async def test_crash_decide_via_fresh_engine_resume_completes(
        self, tmp_path
    ) -> None:
        """The Sprint 18 acceptance path, end to end.

        1. Engine A executes a participant-backed workflow that needs
           approval → execution waits, approval persisted with participant.
        2. Engine A "dies" (a fresh engine takes over — no shared memory).
        3. Engine B recovers from the store, decides the approval, and the
           registered participant actually re-runs to completion.
        """
        db = str(tmp_path / "state.db")
        results_dir = tmp_path / "out"
        results_dir.mkdir()

        # --- Engine A -----------------------------------------------------
        eng_a = ExecutionEngine()
        store_a = SQLiteExecutionStore(db)
        eng_a.use_store(store_a)

        def deploy_compute(ctx: ExecutionContext):  # type: ignore[type-arg]
            if ctx.metadata.get("approval") != "approved":
                raise ApprovalRequired(
                    "Deploy to production?",
                    execution_id=ctx.execution_id,
                    trace_id=ctx.trace_id,
                    context={"capability": "deploy.execute"},
                )
            # This branch only runs after a real approve — write the marker
            # so we can assert the compute actually re-ran.
            (results_dir / "deployed.txt").write_text(
                f"approved_by={ctx.metadata.get('approval_note') or 'human'}"
            )
            return "deployed"

        eng_a.register_participant("deploy_wf", deploy_compute)

        intent = Intent(name="deploy", params={"env": "prod"})
        with pytest.raises(ApprovalRequired):
            await eng_a.execute(intent, deploy_compute)
        waiting_ex = eng_a.executions[list(eng_a.executions)[-1]]
        assert waiting_ex.status.value == "waiting"

        approval = eng_a.approvals.get(waiting_ex.id)
        assert approval is not None
        approval.participant = "deploy_wf"
        eng_a._persist_approval(approval)
        # Engine A dies here — store and engine are discarded.

        # --- Engine B: recover + decide -----------------------------------
        eng_b = ExecutionEngine()
        store_b = SQLiteExecutionStore(db)
        eng_b.use_store(store_b)
        recovered = eng_b.recover()
        assert any(e.id == waiting_ex.id for e in recovered)

        eng_b.register_participant("deploy_wf", deploy_compute)

        resumed = await eng_b.approve(waiting_ex.id, by="ops", note="ship it")

        assert resumed is not None
        assert resumed.status.value == "completed"
        assert resumed.result == "deployed"
        # The compute really re-ran:
        assert (results_dir / "deployed.txt").exists()
        assert "ship it" in (results_dir / "deployed.txt").read_text()

        # The waiting execution itself completed with the resumed result.
        original = eng_b.executions[waiting_ex.id]
        assert original.status.value == "completed"
        store_b.close()

    async def test_crash_deny_fails_waiting_execution(self, tmp_path) -> None:
        db = str(tmp_path / "state.db")

        eng_a = ExecutionEngine()
        store_a = SQLiteExecutionStore(db)
        eng_a.use_store(store_a)

        def guarded(ctx: ExecutionContext):  # type: ignore[type-arg]
            raise ApprovalRequired(
                "Delete all data?",
                execution_id=ctx.execution_id,
                trace_id=ctx.trace_id,
                context={"capability": "data.destroy"},
            )

        with pytest.raises(ApprovalRequired):
            await eng_a.execute(Intent(name="purge"), guarded)
        ex = eng_a.executions[list(eng_a.executions)[-1]]
        approval = eng_a.approvals.get(ex.id)
        assert approval is not None
        approval.participant = "purge_wf"
        eng_a._persist_approval(approval)

        # Fresh engine, recover, deny.
        eng_b = ExecutionEngine()
        store_b = SQLiteExecutionStore(db)
        eng_b.use_store(store_b)
        eng_b.recover()

        denied = await eng_b.deny(ex.id, by="admin", reason="too risky")
        assert denied is not None
        assert denied.status.value == "failed"
        assert "denied" in (denied.error or "")
        store_b.close()


# ---------------------------------------------------------------------------
# Journal events
# ---------------------------------------------------------------------------


class TestApprovalJournalEvents:
    async def test_requested_granted_denied_journal_events(self, tmp_path) -> None:
        db = str(tmp_path / "state.db")
        eng = ExecutionEngine()
        store = SQLiteExecutionStore(db)
        eng.use_store(store)

        def guarded(ctx: ExecutionContext):  # type: ignore[type-arg]
            if ctx.metadata.get("approval") == "approved":
                return "ok"
            raise ApprovalRequired(
                "Proceed?",
                execution_id=ctx.execution_id,
                trace_id=ctx.trace_id,
                context={"capability": "test.run"},
            )

        with pytest.raises(ApprovalRequired):
            await eng.execute(Intent(name="op"), guarded)
        ex = eng.executions[list(eng.executions)[-1]]

        # approval.requested journaled on creation
        events = store.timeline(ex.id)
        types = [e["event_type"] for e in events]
        assert "approval.requested" in types

        await eng.approve(ex.id, by="t")
        events = store.timeline(ex.id)
        types = [e["event_type"] for e in events]
        assert "approval.granted" in types
        store.close()

    async def test_denied_journal_event(self, tmp_path) -> None:
        db = str(tmp_path / "state.db")
        eng = ExecutionEngine()
        store = SQLiteExecutionStore(db)
        eng.use_store(store)

        def guarded(ctx: ExecutionContext):  # type: ignore[type-arg]
            raise ApprovalRequired(
                "Proceed?",
                execution_id=ctx.execution_id,
                trace_id=ctx.trace_id,
            )

        with pytest.raises(ApprovalRequired):
            await eng.execute(Intent(name="op"), guarded)
        ex = eng.executions[list(eng.executions)[-1]]
        await eng.deny(ex.id, by="t")

        events = store.timeline(ex.id)
        types = [e["event_type"] for e in events]
        assert "approval.denied" in types
        store.close()


# ---------------------------------------------------------------------------
# ApprovalRegistry basic behaviors (regression guard)
# ---------------------------------------------------------------------------


class TestApprovalRegistryBasics:
    async def test_create_and_pending(self) -> None:
        from voodoo.runtime.execution import Execution

        registry = ApprovalRegistry()
        ex = Execution(id="ex-1", trace_id="tr-1", intent=Intent(name="t"))
        approval = registry.create(execution=ex, question="OK?", participant="p1")
        assert registry.get("ex-1") is approval
        assert registry.pending() == [approval]

    async def test_decide_idempotent(self) -> None:
        from voodoo.runtime.execution import Execution

        registry = ApprovalRegistry()
        ex = Execution(id="ex-1", trace_id="tr-1", intent=Intent(name="t"))
        registry.create(execution=ex)
        first = registry.decide("ex-1", ApprovalStatus.APPROVED, by="a")
        second = registry.decide("ex-1", ApprovalStatus.DENIED, by="b")
        assert first is not None
        assert second is None  # already decided
        assert registry.get("ex-1").status is ApprovalStatus.APPROVED
