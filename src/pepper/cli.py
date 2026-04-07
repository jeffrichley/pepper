"""Pepper CLI — manage your Second Brain runtime."""

from pathlib import Path

import typer
from rich import print as rprint

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
    from pepper.init.generator import generate_runtime

    runtime_path = Path.home() / ".pepper"

    migrate_from = None
    if migrate:
        if repo_vault:
            migrate_from = Path(repo_vault)
        else:
            # Try to find Memory/ in current directory
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
def start() -> None:
    """Start Pepper MCP servers and integrations."""
    typer.echo("pepper start — not yet implemented")


@app.command()
def stop() -> None:
    """Stop running Pepper services."""
    typer.echo("pepper stop — not yet implemented")


if __name__ == "__main__":
    app()
