from __future__ import annotations

from pathlib import Path

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import (
    AdaptiveSupervisor,
    ComputeParticipant,
    ExecutionEngine,
    Goal,
    GoalRun,
    GoalRuntime,
    GoalStatus,
    Planner,
    SQLiteGoalStore,
)


def _runtime(store, participant):
    engine = ExecutionEngine()
    planner = Planner(engine=engine)
    for capability in participant.capabilities:
        engine.capabilities.register(Capability(name=capability))
    planner.register(participant)
    return GoalRuntime(AdaptiveSupervisor(planner, engine=engine), store=store)


def test_sqlite_goal_store_survives_reopen(tmp_path: Path):
    path = tmp_path / "goals.db"
    store = SQLiteGoalStore(path)
    payload = {
        "goal": {"status": "running", "updated_at": "2026-09-13T00:00:00+00:00"},
        "value": {"nested": [1, 2, 3]},
    }
    store.save("goal-1", payload)
    store.close()

    reopened = SQLiteGoalStore(path)
    assert reopened.load("goal-1") == payload
    assert reopened.load_unfinished() == [payload]
    reopened.close()


async def test_goal_runtime_checkpoints_completed_goal(tmp_path: Path):
    store = SQLiteGoalStore(tmp_path / "goals.db")
    participant = ComputeParticipant(
        name="inspector",
        kind="compute",
        capabilities=["machine.inspect"],
        compute=lambda ctx: "healthy",
    )
    runtime = _runtime(store, participant)
    goal = Goal(name="verify", requires=["machine.inspect"])

    run = await runtime.achieve(goal)
    persisted = store.load(goal.id)

    assert run.status is GoalStatus.COMPLETED
    assert persisted is not None
    assert persisted["goal"]["status"] == "completed"
    assert persisted["current_index"] == 1
    store.close()


async def test_unfinished_goal_can_resume_after_runtime_restart(tmp_path: Path):
    path = tmp_path / "goals.db"
    intent = Intent(name="inspect").require("machine.inspect")
    goal = Goal(name="verify", requires=["machine.inspect"])
    goal.intent_ids = [intent.id]
    goal.transition(GoalStatus.RUNNING)
    checkpoint = GoalRun(
        goal=goal,
        planned_intents=[intent],
        current_index=0,
        context={"goal_id": goal.id, "goal_name": goal.name},
    )

    store = SQLiteGoalStore(path)
    store.save(goal.id, checkpoint.describe())
    store.close()

    reopened = SQLiteGoalStore(path)
    participant = ComputeParticipant(
        name="inspector",
        kind="compute",
        capabilities=["machine.inspect"],
        compute=lambda ctx: "healthy",
    )
    runtime = _runtime(reopened, participant)
    recovered = runtime.recover()

    assert len(recovered) == 1
    assert recovered[0].goal.id == goal.id
    resumed = await runtime.resume(goal.id)
    assert resumed.status is GoalStatus.COMPLETED
    assert resumed.result == "healthy"
    assert resumed.current_index == 1
    reopened.close()


async def test_terminal_goal_resume_is_idempotent(tmp_path: Path):
    store = SQLiteGoalStore(tmp_path / "goals.db")
    participant = ComputeParticipant(
        name="inspector",
        kind="compute",
        capabilities=["machine.inspect"],
        compute=lambda ctx: "healthy",
    )
    runtime = _runtime(store, participant)
    goal = Goal(name="verify", requires=["machine.inspect"])
    original = await runtime.achieve(goal)

    restarted = _runtime(store, participant)
    loaded = await restarted.resume(goal.id)

    assert loaded.status is GoalStatus.COMPLETED
    assert loaded.result == original.result
    assert len(loaded.intent_runs) == 1
    store.close()
