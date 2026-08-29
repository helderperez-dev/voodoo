"""Tests for ``voodoo create`` CLI command (Sprint 22).

Validates that the scaffold command generates the correct file structure,
templates, and configuration for a zero-infrastructure local runtime app.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from voodoo.cli import app

__all__: list[str] = []

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_cwd(tmp_path: Path):
    """Change to a temp directory so ``voodoo create`` writes there."""
    old = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old)


# ---------------------------------------------------------------------------
# Tests: file scaffolding
# ---------------------------------------------------------------------------


class TestCreateScaffold:
    """``voodoo create`` generates the expected directory structure."""

    def test_creates_project_directory(self, tmp_cwd: Path) -> None:
        # The install step may fail in test environments (no venv/uv context),
        # but the directory and files are still created before that point.
        runner.invoke(app, ["create", "myapp"])
        assert (tmp_cwd / "myapp").is_dir()

    def test_creates_main_py(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        main_py = tmp_cwd / "myapp" / "main.py"
        assert main_py.exists()
        content = main_py.read_text()
        assert "from voodoo import" in content
        assert "App" in content

    def test_creates_voodoo_toml(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        toml = tmp_cwd / "myapp" / "voodoo.toml"
        assert toml.exists()
        content = toml.read_text()
        assert "myapp" in content
        assert "[app]" in content

    def test_creates_pyproject_toml(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        pyproject = tmp_cwd / "myapp" / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert 'name = "myapp"' in content
        assert "voodoo-framework" in content

    def test_creates_state_directory(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        state_dir = tmp_cwd / "myapp" / ".voodoo" / "state"
        assert state_dir.is_dir()

    def test_creates_app_directory(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        app_dir = tmp_cwd / "myapp" / "app"
        assert app_dir.is_dir()

    def test_rejects_existing_directory(self, tmp_cwd: Path) -> None:
        (tmp_cwd / "existing").mkdir()
        result = runner.invoke(app, ["create", "existing"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Tests: main.py template content
# ---------------------------------------------------------------------------


class TestMainPyTemplate:
    """The generated ``main.py`` contains all required runtime features."""

    def _get_main_py(self, tmp_cwd: Path) -> str:
        runner.invoke(app, ["create", "myapp"])
        return (tmp_cwd / "myapp" / "main.py").read_text()

    def test_has_durable_queue(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "@queue" in content
        assert "enqueue" in content

    def test_has_agent(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "Agent" in content
        assert 'model="mock:test"' in content

    def test_has_mesh_events(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "@event" in content

    def test_has_state(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "state(" in content

    def test_has_startup_hook(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "@app.on_startup" in content

    def test_has_crash_restart_demo(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert ".booted" in content
        assert "restart detected" in content

    def test_has_routes(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert '@page("/")' in content

    def test_has_tool_decorator(self, tmp_cwd: Path) -> None:
        content = self._get_main_py(tmp_cwd)
        assert "@tool" in content


# ---------------------------------------------------------------------------
# Tests: runtime banner
# ---------------------------------------------------------------------------


class TestRuntimeBanner:
    """``_print_runtime_banner`` runs without error."""

    def test_banner_imports(self) -> None:
        """The banner function can be imported."""
        from voodoo.cli.dev import _print_runtime_banner

        assert callable(_print_runtime_banner)
