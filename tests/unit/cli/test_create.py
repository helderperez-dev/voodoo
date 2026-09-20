"""Release gates for the stable ``voodoo create`` scaffold."""

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
    old = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old)


class TestCreateScaffold:
    def test_creates_minimal_project(self, tmp_cwd: Path) -> None:
        result = runner.invoke(app, ["create", "myapp"])
        assert result.exit_code == 0
        project = tmp_cwd / "myapp"
        assert (project / "main.py").exists()
        assert (project / "voodoo.toml").exists()
        assert (project / "pyproject.toml").exists()
        assert (project / ".voodoo").is_dir()
        assert not (project / "app").exists()

    def test_template_tracks_latest_voodoo_release(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        content = (tmp_cwd / "myapp" / "pyproject.toml").read_text()
        assert 'dependencies = ["voodoo-framework"]' in content
        assert ">=1." not in content
        assert ">=2." not in content

    def test_store_first_runtime_guidance(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        content = (tmp_cwd / "myapp" / "voodoo.toml").read_text()
        assert ".voodoo/application.vstore" in content
        assert "No database, queue, cache, or object-server" in content

    def test_rejects_existing_directory(self, tmp_cwd: Path) -> None:
        (tmp_cwd / "existing").mkdir()
        result = runner.invoke(app, ["create", "existing"])
        assert result.exit_code == 1


class TestStableMainTemplate:
    def _content(self, tmp_cwd: Path) -> str:
        runner.invoke(app, ["create", "myapp"])
        return (tmp_cwd / "myapp" / "main.py").read_text()

    def test_uses_only_stable_core_surface(self, tmp_cwd: Path) -> None:
        content = self._content(tmp_cwd)
        assert "from voodoo import App, page" in content
        assert "from voodoo.ui import" in content
        assert "Agent" not in content
        assert "Model" not in content
        assert "@queue" not in content
        assert "@tool" not in content
        assert "@event" not in content
        assert "state(" not in content

    def test_has_one_async_page(self, tmp_cwd: Path) -> None:
        content = self._content(tmp_cwd)
        assert '@page("/")' in content
        assert "async def home()" in content

    def test_template_imports_in_clean_python_process(self, tmp_path: Path) -> None:
        project = tmp_path / "generated"
        project.mkdir()
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
