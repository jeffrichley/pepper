"""Pepper Google CLI (pg).

CLI entry point for Google Workspace operations.
Usage: uv --directory .claude/skills/google/scripts run python pg.py [command]
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import typer
from auth import auth_status, get_credentials, login  # type: ignore[import-not-found]
from gcal import (  # type: ignore[import-not-found]
    create_event,
    delete_event,
    get_freebusy,
    list_calendars,
    list_events,
)
from rich.console import Console

app = typer.Typer(help="Pepper Google Workspace CLI")
auth_app = typer.Typer(help="Authentication commands")
cal_app = typer.Typer(help="Google Calendar commands")
app.add_typer(auth_app, name="auth")
app.add_typer(cal_app, name="calendar")

console = Console(stderr=True)
TIMEZONE = "US/Eastern"


def _build_service() -> Any:
    """Build the Google Calendar service."""
    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


def _today() -> str:
    """Today's date as YYYY-MM-DD."""
    return datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


def _tomorrow() -> str:
    """Tomorrow's date as YYYY-MM-DD."""
    return (datetime.now(ZoneInfo(TIMEZONE)) + timedelta(days=1)).strftime("%Y-%m-%d")


def _week_range() -> tuple[str, str]:
    """Current week Monday to Sunday."""
    now = datetime.now(ZoneInfo(TIMEZONE))
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def _output(data: Any, as_json: bool) -> None:
    """Print data as JSON to stdout or rich JSON to stderr."""
    if as_json:
        print(json.dumps(data, indent=2, default=str))
    else:
        console.print_json(json.dumps(data, default=str))


# --- Auth commands ---


@auth_app.command("login")
def auth_login_cmd() -> None:
    """Authenticate with Google (opens browser)."""
    creds = login()
    console.print("[green]Authenticated successfully![/green]")
    console.print(f"Token saved. Scopes: {list(creds.scopes or [])}")


@auth_app.command("status")
def auth_status_cmd(
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Check authentication status."""
    status = auth_status()
    _output(status, json_output)


# --- Calendar commands ---


@cal_app.command("events")
def cal_events_cmd(
    today: bool = typer.Option(False, "--today", help="Today's events"),
    date: str | None = typer.Option(
        None, "--date", help="Events for a specific date (YYYY-MM-DD)"
    ),
    week: bool = typer.Option(False, "--week", help="This week's events"),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    calendar_id: str = typer.Option("primary", "--calendar", help="Calendar ID"),
    max_results: int = typer.Option(50, "--max", help="Max events"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List calendar events."""
    if date:
        start_date, end_date = date, date
    elif week:
        start_date, end_date = _week_range()
    elif start and end:
        start_date, end_date = start, end
    else:
        start_date = end_date = _today()

    service = _build_service()
    events = list_events(service, start_date, end_date, calendar_id, max_results)
    _output(events, json_output)


@cal_app.command("freebusy")
def cal_freebusy_cmd(
    today: bool = typer.Option(False, "--today", help="Today's free/busy"),
    date: str | None = typer.Option(
        None, "--date", help="Date (YYYY-MM-DD) or 'tomorrow'"
    ),
    start: str | None = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: str | None = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    calendar_id: str = typer.Option("primary", "--calendar", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Show free/busy blocks."""
    if date == "tomorrow":
        target = _tomorrow()
    elif date:
        target = date
    else:
        target = _today()

    if start and end:
        start_date, end_date = start, end
    else:
        start_date = end_date = target

    service = _build_service()
    result = get_freebusy(service, start_date, end_date, calendar_id)
    _output(result, json_output)


@cal_app.command("create")
def cal_create_cmd(
    summary: str = typer.Argument(help="Event title"),
    start: str = typer.Option(
        ..., "--start", help="Start time (YYYY-MM-DD HH:MM or RFC3339)"
    ),
    end: str | None = typer.Option(None, "--end", help="End time"),
    duration: int | None = typer.Option(
        None, "--duration", help="Duration in minutes (alternative to --end)"
    ),
    date: str | None = typer.Option(
        None, "--date", help="All-day event date (YYYY-MM-DD)"
    ),
    location: str = typer.Option("", "--location", help="Location"),
    description: str = typer.Option("", "--description", help="Description"),
    attendees: str | None = typer.Option(
        None, "--attendees", help="Comma-separated emails"
    ),
    calendar_id: str = typer.Option("primary", "--calendar", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """Create a calendar event."""
    tz = ZoneInfo(TIMEZONE)

    if date:
        # All-day event
        result = create_event(
            _build_service(),
            summary=summary,
            start=date,
            end=date,
            calendar_id=calendar_id,
            location=location,
            description=description,
            attendees=attendees.split(",") if attendees else None,
            all_day=True,
        )
    else:
        # Parse start time
        if "T" not in start:
            start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            start_rfc = start_dt.isoformat()
        else:
            start_rfc = start
            start_dt = datetime.fromisoformat(start)

        # Compute end time
        if end:
            if "T" not in end:
                end_rfc = (
                    datetime.strptime(end, "%Y-%m-%d %H:%M")
                    .replace(tzinfo=tz)
                    .isoformat()
                )
            else:
                end_rfc = end
        elif duration:
            end_rfc = (start_dt + timedelta(minutes=duration)).isoformat()
        else:
            end_rfc = (start_dt + timedelta(hours=1)).isoformat()

        result = create_event(
            _build_service(),
            summary=summary,
            start=start_rfc,
            end=end_rfc,
            calendar_id=calendar_id,
            location=location,
            description=description,
            attendees=attendees.split(",") if attendees else None,
        )

    _output(result, json_output)


@cal_app.command("delete")
def cal_delete_cmd(
    event_id: str = typer.Argument(help="Event ID to delete"),
    calendar_id: str = typer.Option("primary", "--calendar", help="Calendar ID"),
) -> None:
    """Delete a calendar event."""
    delete_event(_build_service(), event_id, calendar_id)
    console.print(f"[green]Deleted event {event_id}[/green]")


@cal_app.command("calendars")
def cal_calendars_cmd(
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
) -> None:
    """List available calendars."""
    service = _build_service()
    calendars = list_calendars(service)
    _output(calendars, json_output)


if __name__ == "__main__":
    app()
