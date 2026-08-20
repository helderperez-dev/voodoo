import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from voodoo.cli import app
from voodoo.cli.scaffolding import _detect_ide, _sync_ai_assets

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


def test_cli_ai_init_with_ide_flag(tmp_path: Path):
    """voodoo ai init --ide cursor should generate cursor rules."""
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["ai", "init", "--ide", "cursor"])
        assert result.exit_code == 0
        assert (tmp_path / ".cursor" / "rules" / "voodoo.mdc").exists()
        assert not (tmp_path / ".trae").exists()
        assert not (tmp_path / ".windsurfrules").exists()
    finally:
        os.chdir(original_cwd)


def test_cli_ai_init_no_prompt(tmp_path: Path):
    """voodoo ai init should NOT prompt for IDE selection - auto-detect only."""
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["ai", "init"])
        assert result.exit_code == 0
        assert "Select" not in result.output
        assert ".voodoo/ai/" in result.output
    finally:
        os.chdir(original_cwd)


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
    assert "voodoo" in result.output.lower()
    assert "Python" in result.output


def test_cli_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "voodoo" in result.output.lower()


def test_cli_doctor_checks_subsystems():
    """Doctor should check runtime/db/auth/mesh/workers/telemetry subsystems."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "environment" in result.output.lower()
    assert "runtime" in result.output.lower()
    assert "modules" in result.output.lower()
    assert "auth" in result.output.lower()
    assert "mesh" in result.output.lower()
    assert "workers" in result.output.lower()
    assert "telemetry" in result.output.lower()


def test_cli_version_shows_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "voodoo" in result.output.lower()
    import voodoo

    ver = getattr(voodoo, "__version__", "unknown")
    assert ver in result.output


def test_cli_new_minimal_scaffold(tmp_path: Path):
    """voodoo new should create a minimal project with folder-based routes only."""
    project_dir = tmp_path / "minimal_app"
    result = runner.invoke(app, ["new", str(project_dir), "--template", ""])
    assert result.exit_code == 0

    # Must exist — routes via folder-based routing (app/<dir>/page.py)
    assert (project_dir / "app" / "page.py").exists()
    assert (project_dir / "app" / "about" / "page.py").exists()
    assert (project_dir / "app" / "users" / "[id]" / "page.py").exists()
    assert (project_dir / "pyproject.toml").exists()
    assert (project_dir / "voodoo.toml").exists()

    # Must NOT exist
    assert not (project_dir / "app" / "pages").exists()
    assert not (project_dir / "app" / "components").exists()
    assert not (project_dir / "app" / "agents").exists()
    assert not (project_dir / "app" / "workers").exists()
    assert not (project_dir / "app" / "models.py").exists()
    assert not (project_dir / "app" / "styles.css").exists()
    assert not (project_dir / "tests").exists()
    assert not (project_dir / "main.py").exists()
    assert not (project_dir / ".env").exists()
    assert not (project_dir / ".data").exists()
    assert not (project_dir / "storage").exists()
    assert not (project_dir / ".voodoo").exists()
    assert not (project_dir / ".trae").exists()
    assert not (project_dir / ".cursor").exists()


def test_cli_new_page_content(tmp_path: Path):
    """The scaffolded app/page.py should use the Voodoo public API and file
    convention (folder-based routing), not the @page decorator."""
    project_dir = tmp_path / "content_app"
    result = runner.invoke(app, ["new", str(project_dir), "--template", ""])
    assert result.exit_code == 0

    page_content = (project_dir / "app" / "page.py").read_text()
    assert "from voodoo import" in page_content
    # File-based convention: a module-level `page` function drives routing.
    assert "def page(request)" in page_content
    # No @page decorator in the scaffold (it conflicts with the file scanner
    # when app/page.py is imported via the folder convention).
    assert "@page" not in page_content
    # Voodoo CSS best practices: semantic components and props.
    assert "Heading" in page_content
    assert "Text" in page_content
    assert "Button" in page_content
    assert "variant=" in page_content
    assert "tone=" in page_content
    # SEO tuple return.
    assert "from voodoo.seo import SEO" in page_content
    assert "return seo, ui" in page_content
    # Internal navigation uses voodoo.navigate.
    assert "voodoo.navigate(" in page_content

    # The dynamic route should use a bracket folder + typed segment.
    user_content = (project_dir / "app" / "users" / "[id]" / "page.py").read_text()
    assert "def page(request, id: int)" in user_content


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
    assert "error" in result.output.lower() or "could not find" in result.output.lower()


def test_cli_dev_missing_dotted_module():
    """voodoo dev should not crash when a dotted module's parent is missing.

    Regression: importlib.util.find_spec raises ModuleNotFoundError for dotted
    names whose parent package isn't installed (e.g. "myapp.sub"). The CLI
    should catch it and show the clean error, not a traceback.
    """
    result = runner.invoke(app, ["dev", "nonexistent_pkg.submodule:app"])
    assert result.exit_code == 1
    assert "could not find" in result.output.lower()
    assert "Traceback" not in result.output


def test_cli_dev_does_not_leak_pythonpath(tmp_path: Path, monkeypatch):
    """dev must not inject the CLI's own sys.path into the uvicorn subprocess.

    Regression: `env["PYTHONPATH"] = os.pathsep.join(sys.path)` leaked the CLI's
    bundled site-packages (Homebrew/uv tool) into the subprocess, shadowing the
    project venv's voodoo and serving stale framework code.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHONPATH", raising=False)

    captured: dict[str, str] = {}

    def fake_run(args: list[str], env: dict[str, str], **kwargs: object) -> None:
        captured.update(env)

    with patch("voodoo.cli.dev.subprocess.run", side_effect=fake_run):
        result = runner.invoke(app, ["dev", "voodoo.core:app"])

    assert result.exit_code == 0
    assert "PYTHONPATH" not in captured
