"""Tests for pepper.process — PID file and process management."""

import os
import subprocess
import sys
from pathlib import Path

from pepper.process import (
    get_runtime_path,
    is_process_alive,
    read_pid,
    remove_pid,
    write_pid,
)


def test_get_runtime_path():
    path = get_runtime_path()
    assert path == Path.home() / ".pepper"


def test_write_and_read_pid(tmp_path):
    pid_file = tmp_path / ".pid"
    write_pid(pid_file, 12345)
    assert read_pid(pid_file) == 12345


def test_read_pid_missing(tmp_path):
    pid_file = tmp_path / ".pid"
    assert read_pid(pid_file) is None


def test_read_pid_corrupt(tmp_path):
    pid_file = tmp_path / ".pid"
    pid_file.write_text("not-a-number")
    assert read_pid(pid_file) is None


def test_remove_pid(tmp_path):
    pid_file = tmp_path / ".pid"
    pid_file.write_text("12345")
    remove_pid(pid_file)
    assert not pid_file.exists()


def test_remove_pid_missing(tmp_path):
    pid_file = tmp_path / ".pid"
    remove_pid(pid_file)  # should not raise


def test_is_process_alive_self():
    """Current process should be alive."""
    assert is_process_alive(os.getpid()) is True


def test_is_process_alive_dead():
    """A completed subprocess should not be alive."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "pass"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    proc.wait()
    assert is_process_alive(proc.pid) is False
