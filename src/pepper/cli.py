"""Pepper CLI — manage your Second Brain runtime."""

import typer

app = typer.Typer(
    name="pepper",
    help="Pepper Second Brain — manage your runtime workspace.",
    no_args_is_help=True,
)


@app.command()
def init(
    migrate: bool = typer.Option(False, help="Migrate existing Memory/ vault from the repo"),
) -> None:
    """Initialize the Pepper runtime workspace at ~/.pepper/."""
    typer.echo("pepper init — not yet implemented")


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
