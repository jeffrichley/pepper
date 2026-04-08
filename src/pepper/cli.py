"""Pepper CLI — manage your Second Brain runtime."""

import os
import subprocess
from pathlib import Path

import typer
from rich import print as rprint

from pepper.init.generator import generate_runtime
from pepper.process import (
    get_pid_file,
    get_runtime_path,
    is_process_alive,
    read_pid,
    remove_pid,
    write_pid,
)

app = typer.Typer(
    name="pepper",
    help="Pepper Second Brain — manage your runtime workspace.",
    no_args_is_help=True,
)


@app.command()
def init(
    migrate: bool = typer.Option(
        False,
        help="Migrate existing Memory/ vault from the repo",
    ),
    repo_vault: str = typer.Option(
        "",
        help="Path to existing Memory/ vault to migrate from",
    ),
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
                rprint(
                    "[red]No Memory/ directory found."
                    " Use --repo-vault to specify"
                    " the path.[/red]"
                )
                raise typer.Exit(1)

        if not migrate_from.is_dir():
            rprint(f"[red]Vault path {migrate_from} does not exist.[/red]")
            raise typer.Exit(1)

        rprint(f"Migrating vault from {migrate_from}...")

    if runtime_path.exists() and not migrate:
        rprint(
            "[yellow]~/.pepper/ already exists.[/yellow]"
            " Config files will be regenerated.",
        )
        rprint("Vault files will NOT be overwritten.")

    result = generate_runtime(
        runtime_path=runtime_path,
        migrate_from=migrate_from,
    )

    rprint(
        f"[green]Pepper runtime initialized at {result}[/green]",
    )
    if migrate_from:
        rprint("[green]Vault contents migrated successfully.[/green]")
    rprint("\nTo start Pepper:")
    rprint(f"  cd {result}")
    rprint("  claude")


@app.command()
def start(
    background: bool = typer.Option(
        False,
        help="Run Pepper in the background (headless)",
    ),
) -> None:
    """Start Pepper. Auto-updates runtime config before launching."""
    runtime_path = get_runtime_path()

    # Auto-update runtime (creates if needed)
    generate_runtime(runtime_path=runtime_path)

    if background:
        _start_background(runtime_path)
    else:
        _start_interactive(runtime_path)


def _load_env(runtime_path: Path) -> dict[str, str]:
    """Load .env from runtime directory into a dict, merged with current env."""
    env = dict(os.environ)
    env_file = runtime_path / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def _start_interactive(runtime_path: Path) -> None:
    """Launch Claude Code interactively in the runtime directory."""
    rprint(f"[green]Starting Pepper at {runtime_path}...[/green]")
    env = _load_env(runtime_path)
    result = subprocess.run(  # noqa: PLW1510
        [
            "claude",
            "--continue",
            "--channels",
            "plugin:discord@claude-plugins-official",
        ],
        cwd=str(runtime_path),
        env=env,
    )
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
            "--channels",
            "plugin:discord@claude-plugins-official",
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
    from pepper.process import kill_process_tree  # noqa: PLC0415

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
