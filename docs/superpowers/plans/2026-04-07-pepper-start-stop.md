# Pepper Start/Stop/Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `pepper start`, `pepper stop`, and `pepper status` CLI commands that auto-update the runtime and manage Pepper's lifecycle from anywhere.

**Architecture:** `pepper start` calls `generate_runtime()` to auto-update config, then either execs Claude Code interactively or spawns it detached with a PID file. `pepper stop` reads the PID file and kills the process tree. `pepper status` checks PID liveness.

**Tech Stack:** Python 3.12, typer, rich, subprocess, psutil (for cross-platform process tree kill)

---

### Task 1: Add psutil dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add psutil to dependencies**

In `pyproject.toml`, add `"psutil>=7.0.0"` to the `dependencies` list, after `"mcp>=1.9.0"`.

- [ ] **Step 2: Sync**

Run: `uv sync`
Expected: psutil installs successfully

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add psutil dependency for process management"
```

---

### Task 2: Implement PID file helpers

**Files:**
- Create: `src/pepper/process.py`
- Create: `tests/test_process.py`

- [ ] **Step 1: Write failing tests for PID helpers**

```python
# tests/test_process.py
"""Tests for pepper.process — PID file and process management."""

import os
import signal
import subprocess
import sys
from pathlib import Path

from pepper.process import (
    get_runtime_path,
    read_pid,
    write_pid,
    remove_pid,
    is_process_alive,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_process.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pepper.process'`

- [ ] **Step 3: Implement process helpers**

```python
# src/pepper/process.py
"""Process management utilities for Pepper CLI.

PID file operations and cross-platform process management.
"""

from __future__ import annotations

import os
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
        # Wait for processes to actually terminate
        psutil.wait_procs(children + [parent], timeout=5)
    except psutil.NoSuchProcess:
        pass
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_process.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pepper/process.py tests/test_process.py
git commit -m "feat: add PID file helpers and process management utilities"
```

---

### Task 3: Implement `pepper start` (interactive)

**Files:**
- Modify: `src/pepper/cli.py`
- Create: `tests/test_cli_start.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli_start.py
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
        assert args[0] == ["claude"]
        assert ".pepper" in kwargs["cwd"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_start.py -v`
Expected: FAIL — `generate_runtime` not imported in cli, `os.execvp` not called

- [ ] **Step 3: Implement `pepper start` (interactive mode)**

Replace the `start` command in `src/pepper/cli.py`:

```python
# Add these imports at the top of src/pepper/cli.py
import subprocess
import sys

from pathlib import Path

import typer
from rich import print as rprint

from pepper.init.generator import generate_runtime
from pepper.process import get_runtime_path, get_pid_file, write_pid, read_pid, is_process_alive


app = typer.Typer(
    name="pepper",
    help="Pepper Second Brain — manage your runtime workspace.",
    no_args_is_help=True,
)


@app.command()
def init(
    migrate: bool = typer.Option(False, help="Migrate existing Memory/ vault from the repo"),
    repo_vault: str = typer.Option("", help="Path to existing Memory/ vault to migrate from"),
) -> None:
    """Initialize the Pepper runtime workspace at ~/.pepper/."""
    runtime_path = get_runtime_path()

    migrate_from = None
    if migrate:
        if repo_vault:
            migrate_from = Path(repo_vault)
        else:
            cwd_vault = Path.cwd() / "Memory"
            if cwd_vault.is_dir():
                migrate_from = cwd_vault
            else:
                rprint("[red]No Memory/ directory found. Use --repo-vault to specify the path.[/red]")
                raise typer.Exit(1)

        if not migrate_from.is_dir():
            rprint(f"[red]Vault path {migrate_from} does not exist.[/red]")
            raise typer.Exit(1)

        rprint(f"Migrating vault from {migrate_from}...")

    if runtime_path.exists() and not migrate:
        rprint("[yellow]~/.pepper/ already exists.[/yellow] Config files will be regenerated.")
        rprint("Vault files will NOT be overwritten.")

    result = generate_runtime(
        runtime_path=runtime_path,
        migrate_from=migrate_from,
    )

    rprint(f"[green]Pepper runtime initialized at {result}[/green]")
    if migrate_from:
        rprint("[green]Vault contents migrated successfully.[/green]")
    rprint("\nTo start Pepper:")
    rprint(f"  cd {result}")
    rprint("  claude")


@app.command()
def start(
    background: bool = typer.Option(False, help="Run Pepper in the background (headless)"),
) -> None:
    """Start Pepper. Auto-updates runtime config before launching."""
    runtime_path = get_runtime_path()

    # Auto-update runtime (creates if needed)
    generate_runtime(runtime_path=runtime_path)

    if background:
        _start_background(runtime_path)
    else:
        _start_interactive(runtime_path)


def _start_interactive(runtime_path: Path) -> None:
    """Launch Claude Code interactively in the runtime directory."""
    rprint(f"[green]Starting Pepper at {runtime_path}...[/green]")
    result = subprocess.run(["claude"], cwd=str(runtime_path))
    raise typer.Exit(result.returncode)


def _start_background(runtime_path: Path) -> None:
    """Spawn Claude Code in the background and write PID file."""
    pid_file = get_pid_file()

    # Check if already running
    existing_pid = read_pid(pid_file)
    if existing_pid and is_process_alive(existing_pid):
        rprint(f"[yellow]Pepper is already running (PID: {existing_pid})[/yellow]")
        raise typer.Exit(1)

    proc = subprocess.Popen(
        [
            "claude",
            "--dangerously-skip-permissions",
            "-p",
            "You are Pepper. Monitor Discord and handle scheduled tasks.",
        ],
        cwd=str(runtime_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    write_pid(pid_file, proc.pid)
    rprint(f"[green]Pepper started (PID: {proc.pid})[/green]")


@app.command()
def stop() -> None:
    """Stop a background Pepper instance."""
    from pepper.process import kill_process_tree, remove_pid

    pid_file = get_pid_file()
    pid = read_pid(pid_file)

    if pid is None or not is_process_alive(pid):
        rprint("[yellow]Pepper is not running.[/yellow]")
        remove_pid(pid_file)
        raise typer.Exit(0)

    kill_process_tree(pid)
    remove_pid(pid_file)
    rprint(f"[green]Pepper stopped (PID: {pid})[/green]")


@app.command()
def status() -> None:
    """Check if Pepper is running."""
    pid_file = get_pid_file()
    pid = read_pid(pid_file)

    if pid is None:
        rprint("[yellow]Pepper is not running.[/yellow]")
        raise typer.Exit(0)

    if is_process_alive(pid):
        rprint(f"[green]Pepper is running (PID: {pid})[/green]")
    else:
        rprint("[yellow]Pepper is not running (stale PID file).[/yellow]")
        remove_pid(pid_file)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_cli_start.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pepper/cli.py tests/test_cli_start.py
git commit -m "feat: implement pepper start with auto-update and background mode"
```

---

### Task 4: Test `pepper stop` and `pepper status`

**Files:**
- Create: `tests/test_cli_stop.py`

- [ ] **Step 1: Write tests for stop and status**

```python
# tests/test_cli_stop.py
"""Tests for pepper stop and pepper status CLI commands."""

from unittest.mock import patch
from pathlib import Path

from pepper.cli import app
from pepper.process import write_pid
from typer.testing import CliRunner

runner = CliRunner()


def test_stop_no_pid_file(tmp_path):
    """pepper stop with no PID file reports not running."""
    with patch("pepper.cli.get_pid_file", return_value=tmp_path / ".pid"):
        result = runner.invoke(app, ["stop"])
        assert "not running" in result.output.lower()


def test_stop_stale_pid(tmp_path):
    """pepper stop with a dead PID removes the file and reports not running."""
    pid_file = tmp_path / ".pid"
    write_pid(pid_file, 999999)  # almost certainly not running
    with patch("pepper.cli.get_pid_file", return_value=pid_file):
        result = runner.invoke(app, ["stop"])
        assert "not running" in result.output.lower()
        assert not pid_file.exists()


def test_status_no_pid_file(tmp_path):
    """pepper status with no PID file reports not running."""
    with patch("pepper.cli.get_pid_file", return_value=tmp_path / ".pid"):
        result = runner.invoke(app, ["status"])
        assert "not running" in result.output.lower()


def test_status_stale_pid(tmp_path):
    """pepper status with dead PID reports not running and cleans up."""
    pid_file = tmp_path / ".pid"
    write_pid(pid_file, 999999)
    with patch("pepper.cli.get_pid_file", return_value=pid_file):
        result = runner.invoke(app, ["status"])
        assert "not running" in result.output.lower()
        assert not pid_file.exists()


def test_status_alive_pid(tmp_path):
    """pepper status with a live PID reports running."""
    import os
    pid_file = tmp_path / ".pid"
    write_pid(pid_file, os.getpid())  # current process is alive
    with patch("pepper.cli.get_pid_file", return_value=pid_file):
        result = runner.invoke(app, ["status"])
        assert "running" in result.output.lower()
        assert str(os.getpid()) in result.output
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_cli_stop.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_stop.py
git commit -m "test: add tests for pepper stop and pepper status"
```

---

### Task 5: Verify full CLI and run all tests

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v --ignore=tests/test_spawn.py --ignore=tests/test_pyqmd_integration.py`
Expected: All PASS

- [ ] **Step 2: Verify CLI commands**

Run: `uv run pepper --help`
Expected: Shows `init`, `start`, `stop`, `status` commands

Run: `uv run pepper start --help`
Expected: Shows `--background` option

Run: `uv run pepper status`
Expected: "Pepper is not running."

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "chore: final fixes for start/stop/status"
```
