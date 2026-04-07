"""Tests for pepper start CLI command."""

from unittest.mock import patch, MagicMock

from pepper.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_start_calls_generate_runtime():
    """pepper start should auto-update runtime before launching."""
    with patch("pepper.cli.generate_runtime") as mock_gen, \
         patch("pepper.cli.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
        result = runner.invoke(app, ["start"])
        mock_gen.assert_called_once()


def test_start_launches_claude():
    """pepper start should launch claude with cwd ~/.pepper/."""
    with patch("pepper.cli.generate_runtime"), \
         patch("pepper.cli.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
        result = runner.invoke(app, ["start"])
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0][0] == "claude"
        assert "server:pepper-channel" in args[0]
        assert ".pepper" in kwargs["cwd"]
