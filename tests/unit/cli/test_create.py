"""Release gates for the stable ``voodoo create`` scaffold."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from voodoo.cli import app

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
        assert (project / "app" / "page.py").exists()
        assert (project / "app" / "about" / "page.py").exists()
        assert (project / "app" / "users" / "[id]" / "page.py").exists()
        assert (project / "voodoo.toml").exists()
        assert (project / "pyproject.toml").exists()
        assert (project / "README.md").exists()
        assert "deprecated" in result.output.lower()

    def test_template_tracks_latest_voodoo_release(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        content = (tmp_cwd / "myapp" / "pyproject.toml").read_text()
        assert '"voodoo-framework>=3.2,<3.3"' in content

    def test_store_first_runtime_guidance(self, tmp_cwd: Path) -> None:
        runner.invoke(app, ["create", "myapp"])
        content = (tmp_cwd / "myapp" / "voodoo.toml").read_text()
        assert ".voodoo/application.vstore" in content
        assert "Runtime creates application.vstore" in content

    def test_rejects_existing_directory(self, tmp_cwd: Path) -> None:
        (tmp_cwd / "existing").mkdir()
        result = runner.invoke(app, ["create", "existing"])
        assert result.exit_code == 1


class TestRuntimeBanner:
    def test_banner_imports(self) -> None:
        from voodoo.cli.dev import _print_runtime_banner

        assert callable(_print_runtime_banner)
