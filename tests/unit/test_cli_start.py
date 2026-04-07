"""Tests for pepper start CLI command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from pepper.cli import app

runner = CliRunner()


def test_start_calls_generate_runtime():
    """Pepper start should auto-update runtime before launching."""
    with (
        patch("pepper.cli.generate_runtime") as mock_gen,
        patch(
            "pepper.cli.subprocess.run", return_value=MagicMock(returncode=0)
        ) as mock_run,
    ):
        result = runner.invoke(app, ["start"])
        mock_gen.assert_called_once()


def test_start_launches_claude():
    """Pepper start should launch claude with cwd ~/.pepper/."""
    with (
        patch("pepper.cli.generate_runtime"),
        patch(
            "pepper.cli.subprocess.run", return_value=MagicMock(returncode=0)
        ) as mock_run,
    ):
        result = runner.invoke(app, ["start"])
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0][0] == "claude"
        assert "--resume" in args[0]
        assert "--channels" in args[0]
        assert "server:pepper-channel" in args[0]
        assert ".pepper" in kwargs["cwd"]
