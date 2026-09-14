"""Sprint 28.19 CLI/DX acceptance for Store-first fabric operations."""

from typer.testing import CliRunner

from voodoo.cli import app

runner = CliRunner()


def test_fabric_cli_exposes_operational_commands() -> None:
    result = runner.invoke(app, ["fabric", "--help"])

    assert result.exit_code == 0
    for command in ("status", "health", "verify", "join", "backup"):
        assert command in result.stdout


def test_fabric_join_help_describes_topology_metadata() -> None:
    result = runner.invoke(app, ["fabric", "join", "--help"])

    assert result.exit_code == 0
    assert "--capability" in result.stdout
    assert "--service" in result.stdout
    assert "--owner" in result.stdout
    assert "--location" in result.stdout
