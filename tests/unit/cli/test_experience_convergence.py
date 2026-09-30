"""Sprint 29 experience-convergence regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from voodoo.agents.models import AgentEntity, AgentRunRecord
from voodoo.agents.registry import VoodooStoreAgentRegistry
from voodoo.cli import app
from voodoo.cli.context import (
    acquire_execution_store,
    acquire_schedule_store,
)
from voodoo.cli.new import _scaffold_offline
from voodoo.cli.scaffolding import _fallback_ai_assets
from voodoo.runtime.store import (
    RuntimeStore,
    StoreConfig,
    bind_active_runtime_store,
)


def test_voodoo_new_scaffold_is_store_first(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    _scaffold_offline(project, "sample")

    config = (project / "voodoo.toml").read_text()
    home = (project / "app" / "page.py").read_text()

    assert "[store]" in config
    assert 'provider = "voodoo"' in config
    assert 'path = ".voodoo/application.vstore"' in config
    assert "from voodoo.ui import" in home
    assert "from voodoo import A" not in home
    assert list(project.rglob("*.db")) == []


def test_ai_scaffold_teaches_voodoo_store_not_aiosqlite() -> None:
    assets = _fallback_ai_assets()
    persistence = assets[".voodoo/ai/DATABASE.md"]
    rules = assets[".voodoo/ai/RULES.md"]
    skills = assets[".voodoo/ai/SKILLS.md"]

    combined = "\n".join((persistence, rules, skills))
    assert "application.vstore" in combined
    assert "from voodoo import Model" in persistence
    assert "aiosqlite" not in combined
    assert ".voodoo/state/data.db" not in combined


def test_cli_operational_store_creates_no_sqlite_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    executions, store_path = acquire_execution_store()
    try:
        assert store_path == ".voodoo/application.vstore"
        assert Path(store_path).exists()
        assert executions.load_all() == []
    finally:
        executions.close()

    schedules, schedule_store_path = acquire_schedule_store()
    try:
        assert schedule_store_path == ".voodoo/application.vstore"
        assert schedules.list_all() == []
    finally:
        schedules.close()

    assert list(tmp_path.rglob("*.db")) == []


@pytest.mark.asyncio
async def test_store_backed_agent_registry_round_trip(tmp_path: Path) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "application.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        registry = VoodooStoreAgentRegistry()
        agent = AgentEntity(agent_id="agent-1", name="Planner", model="mock:default")
        await registry.register(agent)

        restored = await registry.get("agent-1")
        assert restored is not None
        assert restored.name == "Planner"

        run = AgentRunRecord(
            run_id="run-1",
            agent_id="agent-1",
            prompt="plan",
            output="done",
            tokens_in=10,
            tokens_out=4,
        )
        await registry.record_run(run)
        runs = await registry.get_runs("agent-1")
        assert [item.run_id for item in runs] == ["run-1"]
        assert await registry.count_agents() == 1
        assert await registry.count_runs("agent-1") == 1

        assert await registry.delete("agent-1") is True
        assert await registry.get("agent-1") is None
        assert await registry.count_runs("agent-1") == 0
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_status_json_exposes_store_first_application_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["store"]["provider"] == "voodoo"
    assert payload["store"]["path"] == ".voodoo/application.vstore"
    assert payload["providers"]["database"] == "voodoo"
    assert payload["providers"]["queue"] == "voodoo"
    assert payload["providers"]["objects"] == "voodoo"
    assert payload["runtime"]["requests_total"] >= 0


def test_doctor_json_is_store_first_and_side_effect_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["application"]["store"]["provider"] == "voodoo"
    assert payload["integrity"]["legacy_sqlite"] == []
    assert payload["integrity"]["store_first_clean"] is True
    assert not Path(".voodoo/application.vstore").exists()
    assert list(tmp_path.rglob("*.db")) == []
