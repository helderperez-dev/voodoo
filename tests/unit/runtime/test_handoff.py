import pytest

from voodoo.primitives.intent import Intent
from voodoo.runtime.dispatch import DispatchPlan
from voodoo.runtime.engine import ComputeResult, ExecutionEngine
from voodoo.runtime.handoff import ExecutionHandoff
from voodoo.runtime.work_scheduler import (
    ScheduledWork,
    SchedulingDecision,
    WorkEligibility,
)


@pytest.mark.asyncio
async def test_handoff_uses_canonical_execution_engine():
    engine = ExecutionEngine()
    intent = Intent(name="compute")
    work = ScheduledWork(intent)
    plan = DispatchPlan(
        work=work,
        scheduling=SchedulingDecision(
            intent.id, WorkEligibility.ELIGIBLE, "work is eligible", 0
        ),
    )

    async def compute(ctx):
        return ComputeResult(value="ok")

    execution = await ExecutionHandoff(engine).execute(plan, compute)

    assert engine.get(execution.id) is execution
    assert execution.intent is intent
    assert execution.result == "ok"


@pytest.mark.asyncio
async def test_handoff_refuses_ineligible_work():
    engine = ExecutionEngine()
    intent = Intent(name="wait")
    plan = DispatchPlan(
        work=ScheduledWork(intent),
        scheduling=SchedulingDecision(
            intent.id, WorkEligibility.WAITING, "backpressured", 0
        ),
    )

    with pytest.raises(RuntimeError, match="not eligible"):
        await ExecutionHandoff(engine).execute(plan)

    assert engine.recent() == []


@pytest.mark.asyncio
async def test_handoff_requires_transport_for_remote_placement():
    from types import SimpleNamespace

    from voodoo.runtime.handoff import RemoteExecutionRequired

    engine = ExecutionEngine()
    intent = Intent(name="remote")
    plan = DispatchPlan(
        work=ScheduledWork(intent),
        scheduling=SchedulingDecision(
            intent.id, WorkEligibility.ELIGIBLE, "work is eligible", 0
        ),
        placement=SimpleNamespace(
            node_id="edge-2",
            reasons=("capability:camera",),
        ),
    )

    with pytest.raises(RemoteExecutionRequired, match="edge-2"):
        await ExecutionHandoff(engine, local_node_id="runtime-1").execute(plan)

    assert engine.recent() == []
