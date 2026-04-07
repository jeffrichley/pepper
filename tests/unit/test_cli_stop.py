"""Tests for pepper stop and pepper status CLI commands."""

from unittest.mock import patch

from typer.testing import CliRunner

from pepper.cli import app
from pepper.process import write_pid

runner = CliRunner()


def test_stop_no_pid_file(tmp_path):
    """Pepper stop with no PID file reports not running."""
    with patch("pepper.cli.get_pid_file", return_value=tmp_path / ".pid"):
        result = runner.invoke(app, ["stop"])
        assert "not running" in result.output.lower()


def test_stop_stale_pid(tmp_path):
    """Pepper stop with a dead PID removes the file and reports not running."""
    pid_file = tmp_path / ".pid"
    write_pid(pid_file, 999999)  # almost certainly not running
    with patch("pepper.cli.get_pid_file", return_value=pid_file):
        result = runner.invoke(app, ["stop"])
        assert "not running" in result.output.lower()
        assert not pid_file.exists()


def test_status_no_pid_file(tmp_path):
    """Pepper status with no PID file reports not running."""
    with patch("pepper.cli.get_pid_file", return_value=tmp_path / ".pid"):
        result = runner.invoke(app, ["status"])
        assert "not running" in result.output.lower()


def test_status_stale_pid(tmp_path):
    """Pepper status with dead PID reports not running and cleans up."""
    pid_file = tmp_path / ".pid"
    write_pid(pid_file, 999999)
    with patch("pepper.cli.get_pid_file", return_value=pid_file):
        result = runner.invoke(app, ["status"])
        assert "not running" in result.output.lower()
        assert not pid_file.exists()


def test_status_alive_pid(tmp_path):
    """Pepper status with a live PID reports running."""
    import os

    pid_file = tmp_path / ".pid"
    write_pid(pid_file, os.getpid())  # current process is alive
    with patch("pepper.cli.get_pid_file", return_value=pid_file):
        result = runner.invoke(app, ["status"])
        assert "running" in result.output.lower()
        assert str(os.getpid()) in result.output
