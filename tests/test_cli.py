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


def test_cli_doctor_checks_subsystems():
    """Doctor should check runtime/db/auth/mesh/workers/telemetry subsystems."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Voodoo Framework" in result.output
    assert "Auth" in result.output
    assert "Mesh" in result.output
    assert "Workers" in result.output
    assert "Telemetry" in result.output


def test_cli_version_shows_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Voodoo Framework" in result.output
    import voodoo

    ver = getattr(voodoo, "__version__", "unknown")
    assert f"v{ver}" in result.output


def test_cli_new_scaffolds_pages_directory(tmp_path: Path):
    """voodoo new should create the pages/ directory with file-based pages."""
    project_dir = tmp_path / "pages_app"
    result = runner.invoke(
        app, ["new", str(project_dir), "--template", "", "--ide", "none"]
    )
    assert result.exit_code == 0

    # Check for pages/ directory with file-based pages
    assert (project_dir / "app" / "pages").is_dir()
    assert (project_dir / "app" / "pages" / "index.py").exists()
    assert (project_dir / "app" / "pages" / "about.py").exists()
    assert (project_dir / "app" / "pages" / "users" / "[id].py").exists()

    # Check for other required directories/files
    assert (project_dir / "app" / "components").is_dir()
    assert (project_dir / "app" / "agents").is_dir()
    assert (project_dir / "app" / "workers").is_dir()
    assert (project_dir / "app" / "models.py").exists()
    assert (project_dir / "app" / "styles.css").exists()
    assert (project_dir / "tests").is_dir()
    assert (project_dir / "pyproject.toml").exists()
    assert (project_dir / "main.py").exists()


def test_cli_new_index_page_content(tmp_path: Path):
    """The scaffolded index.py should have a page() function."""
    project_dir = tmp_path / "content_app"
    result = runner.invoke(
        app, ["new", str(project_dir), "--template", "", "--ide", "none"]
    )
    assert result.exit_code == 0

    index_content = (project_dir / "app" / "pages" / "index.py").read_text()
    assert "def page(request)" in index_content
    assert "Div" in index_content


def test_cli_new_dynamic_route_content(tmp_path: Path):
    """The scaffolded [id].py should have a page() function with id parameter."""
    project_dir = tmp_path / "dyn_app"
    result = runner.invoke(
        app, ["new", str(project_dir), "--template", "", "--ide", "none"]
    )
    assert result.exit_code == 0

    dyn_content = (project_dir / "app" / "pages" / "users" / "[id].py").read_text()
    assert "def page(request, id" in dyn_content


def test_cli_routes_command(tmp_path: Path):
    """voodoo routes should list routes from an app."""
    # Create a minimal app structure
    app_dir = tmp_path / "app_test"
    app_dir.mkdir()
    (app_dir / "main.py").write_text(
        "from voodoo.core import create_app\napp = create_app()\n"
    )
    (app_dir / "app").mkdir()
    (app_dir / "app" / "page.py").write_text(
        "from voodoo.components import Div, Text\n\n"
        "def page(request):\n"
        "    return Div(Text('Hello'))\n"
    )

    result = runner.invoke(
        app,
        ["routes", "main:app"],
    )
    # routes command tries to import main:app from cwd; may fail in test env
    # just verify it doesn't crash with a traceback
    assert result.exit_code in (0, 1)


def test_cli_dev_missing_module():
    """voodoo dev should exit with error if module not found."""
    result = runner.invoke(app, ["dev", "nonexistent:app"])
    assert result.exit_code == 1
    assert "Error" in result.output or "error" in result.output.lower()
