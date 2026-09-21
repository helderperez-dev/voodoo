from __future__ import annotations

from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.testclient import TestClient

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.inspection import runtime_dashboard
from voodoo.runtime.operations import OperationalRuntime
from voodoo.world import Entity, WorldModel


async def test_operational_snapshot_combines_execution_and_world():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.inspect"))
    execution = await engine.execute(
        Intent(name="inspect").require("robot.inspect"),
        lambda ctx: "healthy",
        capabilities=["robot.inspect"],
    )
    world = WorldModel()
    world.put_entity(Entity(type="robot", id="robot-1"))
    world.observe("robot-1", "battery.level", 0.82, source="bms")

    snapshot = OperationalRuntime(engine, world=world).snapshot()

    assert snapshot["summary"]["executions"] == 1
    assert snapshot["summary"]["entities"] == 1
    assert snapshot["executions"][0]["id"] == execution.id
    assert snapshot["entities"][0]["id"] == "robot-1"
    assert snapshot["entities"][0]["observation_count"] == 1


def test_operational_snapshot_is_json_safe_for_arbitrary_goal_results():
    engine = ExecutionEngine()
    fake_goal = SimpleNamespace(status=SimpleNamespace(value="completed"))
    fake_run = SimpleNamespace(
        goal=fake_goal,
        describe=lambda: {
            "goal": {"id": "goal-1", "name": "demo", "status": "completed"},
            "planned_intents": [],
            "current_index": 0,
            "result": object(),
        },
    )
    goals = SimpleNamespace(runs={"goal-1": fake_run})

    snapshot = OperationalRuntime(engine, goals=goals).snapshot()

    assert isinstance(snapshot["goals"][0]["result"], str)


def test_dashboard_mounts_html_and_json_routes():
    engine = ExecutionEngine()
    inspector = OperationalRuntime(engine)
    starlette = Starlette()
    app = SimpleNamespace(starlette=starlette)
    runtime_dashboard(inspector)(app)

    client = TestClient(starlette)
    html_response = client.get("/_voodoo/runtime")
    json_response = client.get("/_voodoo/runtime/api")

    assert html_response.status_code == 200
    assert "Voodoo Runtime" in html_response.text
    assert json_response.status_code == 200
    assert json_response.json()["summary"]["executions"] == 0
