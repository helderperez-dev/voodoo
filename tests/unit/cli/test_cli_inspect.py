"""Tests for the voodoo inspect CLI."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from voodoo.cli.inspect import inspect_app
from voodoo.primitives import Capability, Effect, Resource
from voodoo.runtime import ComputeResult, Intent, execute, register_capability

runner = CliRunner()


@pytest.fixture(autouse=True)
def fresh_engine():
    """Give each test a fresh engine so executions don't leak across tests."""
    from voodoo.runtime import engine

    engine.executions.clear()
    yield
    engine.executions.clear()


async def _run_sample_execution() -> str:
    register_capability(Capability(name="test.write"))
    await execute(
        Intent(name="sample_intent").require("test.write"),
        lambda ctx: ComputeResult(
            value={"ok": 1},
            effects=[Effect(name="sample.effect")],
            resources=Resource(cost=0.01),
        ),
        capabilities=["test.write"],
    )
    from voodoo.runtime import engine

    return engine.recent(1)[0].id


class TestInspectRun:
    async def test_list_renders_table(self):
        await _run_sample_execution()
        result = runner.invoke(inspect_app, ["run"])
        assert result.exit_code == 0
        assert "sample_intent" in result.output
        assert "completed" in result.output

    async def test_list_json(self):
        await _run_sample_execution()
        result = runner.invoke(inspect_app, ["run", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]["intent"] == "sample_intent"
        assert data[0]["effects"] == ["sample.effect"]

    async def test_show_single_execution(self):
        exec_id = await _run_sample_execution()
        result = runner.invoke(inspect_app, ["run", exec_id])
        assert result.exit_code == 0
        assert "sample_intent" in result.output
        assert "test.write" in result.output

    async def test_missing_execution_fails(self):
        result = runner.invoke(inspect_app, ["run", "does-not-exist"])
        assert result.exit_code == 1


class TestInspectCapabilities:
    async def test_shows_registered_capability(self):
        register_capability(Capability(name="cap.x"))
        result = runner.invoke(inspect_app, ["capabilities"])
        assert result.exit_code == 0
        assert "cap.x" in result.output

    async def test_json_includes_tool_permissions(self):
        result = runner.invoke(inspect_app, ["capabilities", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "capabilities" in data
        assert "tool_permissions" in data


class TestInspectOther:
    async def test_agent(self):
        result = runner.invoke(inspect_app, ["agent"])
        assert result.exit_code == 0

    async def test_tool(self):
        result = runner.invoke(inspect_app, ["tool"])
        assert result.exit_code == 0

    async def test_task(self):
        await _run_sample_execution()
        result = runner.invoke(inspect_app, ["task"])
        assert result.exit_code == 0

    async def test_workflow(self):
        await _run_sample_execution()
        result = runner.invoke(inspect_app, ["workflow"])
        assert result.exit_code == 0
        assert "sample_intent" in result.output

    async def test_state(self):
        from voodoo.primitives import State
        from voodoo.runtime import engine

        async def compute(ctx):
            return ComputeResult(value=1, states=[State(kind="lead", data={"n": 1})])

        await engine.execute(Intent(name="with_state"), compute)
        result = runner.invoke(inspect_app, ["state"])
        assert result.exit_code == 0
        assert "lead" in result.output

    async def test_mesh(self):
        result = runner.invoke(inspect_app, ["mesh"])
        assert result.exit_code == 0


class TestInspectApprovals:
    def test_lists_pending_approvals_json(self):
        from voodoo.runtime import engine
        from voodoo.runtime.human import Approval, ApprovalStatus

        engine.approvals.records["a1"] = Approval(
            execution_id="a1",
            trace_id="t1",
            capability="pay.debit",
            question="Approve debit?",
            status=ApprovalStatus.PENDING,
        )
        result = runner.invoke(inspect_app, ["approvals", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["execution_id"] == "a1"
        assert data[0]["capability"] == "pay.debit"
        assert data[0]["status"] == "pending"

    def test_pending_filter_excludes_decided(self):
        from voodoo.runtime import engine
        from voodoo.runtime.human import Approval, ApprovalStatus

        engine.approvals.records["a1"] = Approval(
            execution_id="a1", trace_id="t1", status=ApprovalStatus.PENDING
        )
        engine.approvals.records["a2"] = Approval(
            execution_id="a2",
            trace_id="t2",
            status=ApprovalStatus.APPROVED,
            decided_by="admin",
        )
        result = runner.invoke(inspect_app, ["approvals", "--pending", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert [d["execution_id"] for d in data] == ["a1"]


class TestRecoverCLI:
    def test_recover_returns_empty_for_missing_store(self, tmp_path):
        from voodoo.cli import app

        store = tmp_path / "executions.jsonl"
        result = runner.invoke(app, ["recover", "--store", str(store), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["recovered"] == []

    def test_recover_restores_unfinished_execution(self, tmp_path):
        from voodoo.cli import app
        from voodoo.primitives.intent import Intent
        from voodoo.runtime import engine
        from voodoo.runtime.execution import Execution, ExecutionStatus
        from voodoo.runtime.persistence import JSONFileExecutionStore

        store = JSONFileExecutionStore(tmp_path / "executions.jsonl")
        waiting = Execution(
            id="w1",
            trace_id="t-wait",
            intent=Intent(name="needs.approval"),
            actor="alice",
            status=ExecutionStatus.WAITING,
        )
        store.save(waiting)
        # A completed execution must NOT be recovered.
        done = Execution(
            id="d1",
            trace_id="t-done",
            intent=Intent(name="already.done"),
            status=ExecutionStatus.COMPLETED,
        )
        store.save(done)

        result = runner.invoke(app, ["recover", "--store", str(store.path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        ids = {d["id"] for d in data["recovered"]}
        assert ids == {"w1"}
        # Recovered waiting execution gets a pending approval record.
        assert engine.approvals.get("w1") is not None


class TestInspectPlan:
    def test_plan_shows_unresolved_capabilities(self):
        result = runner.invoke(
            inspect_app,
            ["plan", "notify.customer", "--requires", "email.send,sms.send", "--json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["intent"] == "notify.customer"
        assert set(data["unresolved"]) == {"email.send", "sms.send"}

    def test_plan_no_requires(self):
        result = runner.invoke(inspect_app, ["plan", "simple.intent", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["intent"] == "simple.intent"
        assert data["steps"] == []
        assert data["unresolved"] == []
