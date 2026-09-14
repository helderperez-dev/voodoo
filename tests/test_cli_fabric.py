"""Sprint 28.19 CLI/DX acceptance for Store-first fabric operations."""

from click.utils import strip_ansi
from typer.testing import CliRunner

from voodoo.cli import app

runner = CliRunner()


def test_fabric_cli_exposes_operational_commands() -> None:
    result = runner.invoke(app, ["fabric", "--help"])

    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    for command in ("status", "health", "verify", "join", "backup"):
        assert command in output


def test_fabric_join_help_describes_topology_metadata() -> None:
    result = runner.invoke(app, ["fabric", "join", "--help"])

    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "--capability" in output
    assert "--service" in output
    assert "--owner" in output
    assert "--location" in output
