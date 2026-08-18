"""Tests for Human-in-the-Loop — humans as compute participants.

Covers the approval flow: ``ask_human`` raises ``ApprovalRequired`` (the
execution enters ``waiting``), ``engine.approve`` resumes it as a child
execution, ``engine.deny`` fails it, and ``Task(human=True)`` + workflows
participate in the same model.
"""

from __future__ import annotations

import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.errors import ApprovalRequired, WorkflowFailure
from voodoo.runtime.execution import ExecutionStatus
from voodoo.runtime.human import ApprovalStatus, ask_human


class TestAskHuman:
    async def test_ask_human_waits_for_approval(self):
        engine = ExecutionEngine()
        with pytest.raises(ApprovalRequired):
            await engine.execute(
                Intent(name="debit.account"), ask_human("Approve debit?")
            )

        ex = engine.get(list(engine.executions)[-1])
        assert ex.status is ExecutionStatus.WAITING
        approval = engine.approvals.get(ex.id)
        assert approval is not None
        assert approval.question == "Approve debit?"
        assert approval.status is ApprovalStatus.PENDING

    async def test_approve_resumes_and_completes(self):
        engine = ExecutionEngine()
        with pytest.raises(ApprovalRequired):
            await engine.execute(
                Intent(name="debit.account"),
                ask_human("Approve debit?", capability="pay.debit"),
            )

        ex = engine.get(list(engine.executions)[-1])
        resumed = await engine.approve(ex.id, by="admin", note="ok")
        assert resumed is not None
        assert resumed.status is ExecutionStatus.COMPLETED
        assert resumed.result == "ok"
        # the resumed execution is a child of the waiting one
        assert resumed.parent_execution_id == ex.id
        assert resumed.trace_id == ex.trace_id

        approval = engine.approvals.get(ex.id)
        assert approval.status is ApprovalStatus.APPROVED
        assert approval.decided_by == "admin"

    async def test_deny_fails_execution(self):
        engine = ExecutionEngine()
        with pytest.raises(ApprovalRequired):
            await engine.execute(Intent(name="debit.account"), ask_human("Approve?"))

        ex = engine.get(list(engine.executions)[-1])
        denied = await engine.deny(ex.id, by="admin", reason="not now")
        assert denied is not None
        assert denied.status is ExecutionStatus.FAILED
        assert "not now" in (denied.error or "")
        assert engine.approvals.get(ex.id).status is ApprovalStatus.DENIED

    async def test_approving_unknown_execution_returns_none(self):
        engine = ExecutionEngine()
        assert await engine.approve("does-not-exist", by="admin") is None
        assert await engine.deny("does-not-exist", by="admin") is None


class TestTaskHuman:
    async def test_human_task_waits_then_completes(self):
        from voodoo.runtime import Task, TaskStatus

        engine = ExecutionEngine()
        task = Task(
            name="review",
            description="Approve the payout",
            human=True,
            approval_capability="payout.release",
        )
        with pytest.raises(ApprovalRequired):
            await task.run(engine=engine)

        assert task.status is TaskStatus.WAITING
        assert task.execution is not None
        assert task.execution.status is ExecutionStatus.WAITING

        resumed = await engine.approve(task.execution.id, by="manager")
        assert resumed is not None
        assert resumed.status is ExecutionStatus.COMPLETED


class TestWorkflowHuman:
    async def test_human_step_reaches_waiting_then_completes_on_approval(self):
        """A human task inside a sequential workflow enters waiting; the
        workflow stops there (resume orchestration is pending) and the
        waiting execution can be approved."""
        from voodoo.runtime import Task, Workflow, WorkflowStrategy

        engine = ExecutionEngine()
        recorded: list[str] = []

        async def prep(ctx):
            recorded.append("prep")
            return "data"

        prep_task = Task(name="prep", compute=prep)
        human = Task(
            name="approve",
            description="Approve?",
            human=True,
            depends_on=[prep_task],
        )
        wf = Workflow(tasks=[prep_task, human], strategy=WorkflowStrategy.SEQUENTIAL)

        with pytest.raises(WorkflowFailure):
            await wf.run(engine=engine)

        assert recorded == ["prep"]
        pending = [
            ex
            for ex in engine.executions.values()
            if ex.intent
            and ex.intent.name == "approve"
            and ex.status is ExecutionStatus.WAITING
        ]
        assert pending
        resumed = await engine.approve(pending[0].id, by="boss")
        assert resumed.status is ExecutionStatus.COMPLETED
