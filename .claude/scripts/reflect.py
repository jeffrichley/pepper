"""Daily reflection script — runs at 3 AM ET.

Gathers today's raw daily log and project statuses,
then spawns a Claude Code session to write a curated summary.

Usage:
    uv run python .claude/scripts/reflect.py
    uv run python .claude/scripts/reflect.py --date 2026-04-04
"""

import glob
from datetime import datetime
from pathlib import Path

import typer

from spawn_session import spawn

PROJECT_ROOT = Path(__file__).parent.parent.parent
VAULT = PROJECT_ROOT / "Memory"

app = typer.Typer()


@app.command()
def reflect(date: str = typer.Option(None, help="Date to reflect on (YYYY-MM-DD). Defaults to today.")):
    """Run the daily reflection: summarize raw logs and update MEMORY.md."""
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    raw_log = VAULT / "daily" / "raw" / f"{target_date}.md"

    if not raw_log.exists():
        typer.echo(f"No raw log found for {target_date}. Nothing to reflect on.")
        raise typer.Exit()

    raw_content = raw_log.read_text(encoding="utf-8")

    status_files = glob.glob(str(VAULT / "projects" / "*" / "STATUS.md"))
    status_files += glob.glob(str(VAULT / "projects" / "*" / "*" / "STATUS.md"))
    project_context = ""
    for sf in sorted(status_files):
        project_context += f"\n\n---\n\n# {Path(sf).relative_to(VAULT)}\n"
        project_context += Path(sf).read_text(encoding="utf-8")

    prompt = f"""You are running the nightly reflection for {target_date}.

## Raw Daily Log
{raw_content}

## Project Statuses
{project_context}

## Your Task
1. Write a daily summary to `Memory/daily/summaries/{target_date}.md` using this template:
   - Key Accomplishments (with relative-link pointers to source files)
   - Decisions Made (with pointers)
   - Open Items (with pointers)
   - Active Focus (projects + current work)
   - Tomorrow (what carries forward)
2. Update `Memory/MEMORY.md` with anything worth keeping long-term.
3. Include relative-link pointers to source files for each item.
"""

    typer.echo(f"Reflecting on {target_date}...")
    result = spawn(prompt, timeout=180)
    typer.echo(result)
    typer.echo(f"Reflection complete for {target_date}.")


if __name__ == "__main__":
    app()
