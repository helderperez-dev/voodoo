import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from voodoo.cli import _detect_ide, _sync_ai_assets, app

runner = CliRunner()


def test_detect_ide_from_env():
    with patch.dict(os.environ, {"TRAE_PID": "12345"}, clear=False):
        assert _detect_ide() == "trae"

    with patch.dict(os.environ, {"CURSOR_TRACE": "1"}, clear=False):
        assert _detect_ide() == "cursor"

    with patch.dict(os.environ, {"WINDSURF_PORT": "9000"}, clear=False):
        assert _detect_ide() == "windsurf"

    with patch.dict(os.environ, {"TERM_PROGRAM": "vscode"}, clear=False):
        assert _detect_ide() == "vscode"


def test_sync_ai_assets_none(tmp_path: Path):
    mock_progress = MagicMock()
    _sync_ai_assets(tmp_path, mock_progress, ide="none")

    # Core AI docs exist
    assert (tmp_path / ".voodoo/ai/README.md").exists()
    assert (tmp_path / ".voodoo/ai/RULES.md").exists()
    assert (tmp_path / ".voodoo/ai/MESH.md").exists()
    assert (tmp_path / ".voodoo/ai/SEO.md").exists()

    # IDE specific folders do NOT exist
    assert not (tmp_path / ".trae").exists()
    assert not (tmp_path / ".cursor").exists()
    assert not (tmp_path / ".windsurfrules").exists()
    assert not (tmp_path / ".github").exists()


def test_sync_ai_assets_trae(tmp_path: Path):
    mock_progress = MagicMock()
    _sync_ai_assets(tmp_path, mock_progress, ide="trae")

    # Core AI docs exist
    assert (tmp_path / ".voodoo/ai/README.md").exists()

    # Trae assets exist
    assert (tmp_path / ".trae/rules").exists()
    assert (tmp_path / ".trae/skills/voodoo-builder/SKILL.md").exists()

    # Other IDE rules do NOT exist
    assert not (tmp_path / ".cursor").exists()
    assert not (tmp_path / ".windsurfrules").exists()


def test_sync_ai_assets_cursor(tmp_path: Path):
    mock_progress = MagicMock()
    _sync_ai_assets(tmp_path, mock_progress, ide="cursor")

    # Core AI docs exist
    assert (tmp_path / ".voodoo/ai/README.md").exists()

    # Cursor assets exist
    assert (tmp_path / ".cursor/rules/voodoo.mdc").exists()

    # Other IDE rules do NOT exist
    assert not (tmp_path / ".trae").exists()
    assert not (tmp_path / ".windsurfrules").exists()


def test_sync_ai_assets_windsurf(tmp_path: Path):
    mock_progress = MagicMock()
    _sync_ai_assets(tmp_path, mock_progress, ide="windsurf")

    # Core AI docs exist
    assert (tmp_path / ".voodoo/ai/README.md").exists()

    # Windsurf assets exist
    assert (tmp_path / ".windsurfrules").exists()

    # Other IDE rules do NOT exist
    assert not (tmp_path / ".trae").exists()
    assert not (tmp_path / ".cursor").exists()


def test_sync_ai_assets_all(tmp_path: Path):
    mock_progress = MagicMock()
    _sync_ai_assets(tmp_path, mock_progress, ide="all")

    # All IDE rules exist
    assert (tmp_path / ".trae/rules").exists()
    assert (tmp_path / ".cursor/rules/voodoo.mdc").exists()
    assert (tmp_path / ".windsurfrules").exists()
    assert (tmp_path / ".github/copilot-instructions.md").exists()


def test_cli_new_with_ide_flag(tmp_path: Path):
    project_dir = tmp_path / "test_app"
    result = runner.invoke(
        app, ["new", str(project_dir), "--template", "", "--ide", "cursor"]
    )
    assert result.exit_code == 0
    assert (project_dir / ".cursor/rules/voodoo.mdc").exists()
    assert not (project_dir / ".trae").exists()
    assert not (project_dir / ".windsurfrules").exists()


def test_cli_auth_secret_key():
    result = runner.invoke(app, ["auth", "secret-key"])
    assert result.exit_code == 0
    assert "VOODOO_SECRET_KEY" in result.output


def test_cli_auth_hash_password():
    result = runner.invoke(app, ["auth", "hash-password", "MyPassword123!"])
    assert result.exit_code == 0
    assert "pbkdf2_sha256$" in result.output


def test_cli_auth_generate_key():
    result = runner.invoke(app, ["auth", "generate-key", "--prefix", "vd_test"])
    assert result.exit_code == 0
    assert "vd_test_" in result.output
    assert "SHA-256 Hash" in result.output


def test_cli_auth_create_user(tmp_path: Path):
    db_file = str(tmp_path / "cli_users.db")
    with patch.dict(os.environ, {"VOODOO_DB_PATH": db_file}, clear=False):
        from voodoo.config import config

        config.db_path = db_file
        result = runner.invoke(
            app,
            [
                "auth",
                "create-user",
                "--email",
                "admin@voodoo.dev",
                "--password",
                "StrongAdminPass123!",
                "--username",
                "admin",
                "--role",
                "admin",
            ],
        )
        assert result.exit_code == 0
        assert "User created successfully!" in result.output
        assert "admin@voodoo.dev" in result.output


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Voodoo Framework" in result.output
    assert "Python" in result.output


def test_cli_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Voodoo Doctor" in result.output
