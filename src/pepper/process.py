"""Process management utilities for Pepper CLI.

PID file operations and cross-platform process management.
"""

from __future__ import annotations

from pathlib import Path

import psutil


def get_runtime_path() -> Path:
    """Return the path to the Pepper runtime workspace."""
    return Path.home() / ".pepper"


def get_pid_file() -> Path:
    """Return the path to the PID file."""
    return get_runtime_path() / ".pid"


def write_pid(pid_file: Path, pid: int) -> None:
    """Write a PID to the PID file."""
    pid_file.write_text(str(pid))


def read_pid(pid_file: Path) -> int | None:
    """Read a PID from the PID file. Returns None if missing or corrupt."""
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def remove_pid(pid_file: Path) -> None:
    """Remove the PID file if it exists."""
    pid_file.unlink(missing_ok=True)


def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    return psutil.pid_exists(pid)


def kill_process_tree(pid: int) -> None:
    """Kill a process and all its children."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        parent.kill()
        psutil.wait_procs([*children, parent], timeout=5)
    except psutil.NoSuchProcess:
        pass
