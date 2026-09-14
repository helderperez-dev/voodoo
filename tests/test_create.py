"""Tests for ``voodoo create`` Store-first project scaffolding."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from voodoo.cli import app
from voodoo.cli.create import _MAIN_PY

__all__: list[str] = []

runner = CliRunner()


@pytest.fixture()
def tmp_cwd(tmp_path: Path):
    """Change to a temp directory so ``voodoo create`` writes there."""
    old = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old)


class TestCreateScaffold:
    """``voodoo create`` generates a Store-first project structure."""

    def test_creates_project_directory(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        assert (tmp_cwd / "myapp").is_dir()

    def test_creates_main_py(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        main_py = tmp_cwd / "myapp" / "main.py"
        assert main_py.exists()
        content = main_py.read_text()
        assert "from voodoo import" in content
        assert "App" in content
        assert "Model" in content

    def test_creates_voodoo_toml_with_store_first_guidance(
        self, tmp_cwd: Path
    ) -> None:
        runner.invoke(app, ["create", "myapp"])
        toml = tmp_cwd / "myapp" / "voodoo.toml"
        assert toml.exists()
        content = toml.read_text()
        assert "myapp" in content
        assert "[app]" in content
        assert ".voodoo/application.vstore" in content
        assert "SQLite, local filesystem" not in content
        assert "in-memory queues by default" not in content

    def test_creates_pyproject_toml(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        pyproject = tmp_cwd / "myapp" / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert 'name = "myapp"' in content
        assert "voodoo-framework" in content

    def test_creates_voodoo_directory_not_legacy_state_tree(
        self, tmp_cwd: Path
    ) -> None:
        runner.invoke(app, ["create", "myapp"])
        voodoo_dir = tmp_cwd / "myapp" / ".voodoo"
        assert voodoo_dir.is_dir()
        assert not (voodoo_dir / "state").exists()

    def test_creates_app_directory(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        assert (tmp_cwd / "myapp" / "app").is_dir()

    def test_rejects_existing_directory(self, tmp_cwd: Path) -> None:
        (tmp_cwd / "existing").mkdir()
        result = runner.invoke(app, ["create", "existing"])
        assert result.exit_code == 1


class TestMainPyTemplate:
    """The generated ``main.py`` demonstrates actual Store-backed semantics."""

    def _get_main_py(self, tmp_cwd: Path) -> str:
        runner.invoke(app, ["create", "myapp"])
        return (tmp_cwd / "myapp" / "main.py").read_text()

    def test_has_durable_queue(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert '@queue("increment")' in content
        assert "enqueue(" in content

    def test_has_store_backed_model(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "class Counter(Model):" in content
        assert "await Counter.create" in content
        assert "await row.save()" in content

    def test_has_agent(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "Agent" in content
        assert 'model="mock:test"' in content

    def test_has_events(self, tmp_cwd: Path) -> None:
        assert "@event" in self._get_main_py(tmp_cwd)

    def test_has_reactive_state_without_claiming_it_is_durable(
        self, tmp_cwd: Path
    ) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "state(" in content
        assert "Persistent application data stored in application.vstore" in content

    def test_has_restart_durability_explanation(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert ".voodoo/application.vstore" in content
        assert "restart the process" in content
        assert ".booted" not in content
        assert "@app.on_startup" not in content

    def test_has_async_route_that_reads_store(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert '@page("/")' in content
        assert "async def home()" in content
        assert "row = await _counter()" in content

    def test_has_tool_decorator(self, tmp_cwd: Path) -> None:
        assert "@tool" in self._get_main_py(tmp_cwd)

    def test_template_imports_in_clean_python_process(self, tmp_path: Path) -> None:
        project = tmp_path / "generated"
        project.mkdir()
        (project / "app").mkdir()
        (project / ".voodoo").mkdir()
        (project / "main.py").write_text(_MAIN_PY.format(name="generated"))

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path('main.py', run_name='generated_app')",
            ],
            cwd=project,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


class TestRuntimeBanner:
    def test_banner_imports(self) -> None:
        from voodoo.cli.dev import _print_runtime_banner

        assert callable(_print_runtime_banner)
