# Pepper Google Skill + CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Google Workspace skill with a `pg` CLI tool wrapping `google-api-python-client`, starting with Calendar. Pepper can check schedules, find free time, and create events.

**Architecture:** A Claude Code skill at `.claude/skills/google/` with a Python CLI project in `scripts/`. The CLI handles OAuth2 and Google API calls. The SKILL.md teaches Pepper when and how to use the CLI. OAuth tokens stored at `~/.pepper/google/`.

**Tech Stack:** Python 3.12, google-api-python-client, google-auth-oauthlib, typer, rich, uv

**Spec:** `docs/superpowers/specs/2026-04-06-pepper-google-skill-design.md`

**Working directory:** `E:\workspaces\ai\pepper` (main branch)

---

## File Structure

```
.claude/skills/google/
  SKILL.md                          # Skill instructions + dynamic context
  references/
    calendar.md                     # Calendar command reference

.claude/skills/google/scripts/
  pyproject.toml                    # uv project
  pg.py                             # CLI entry point (typer)
  auth.py                           # OAuth2 flow + token management
  calendar.py                       # Calendar subcommands

tests/
  test_google_auth.py               # Auth module tests
  test_google_calendar.py           # Calendar module tests
```

---

### Task 1: Create Scripts Project

**Files:**
- Create: `.claude/skills/google/scripts/pyproject.toml`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p .claude/skills/google/scripts
mkdir -p .claude/skills/google/references
```

- [ ] **Step 2: Create pyproject.toml**

Create `.claude/skills/google/scripts/pyproject.toml`:

```toml
[project]
name = "pepper-google"
version = "0.1.0"
description = "Pepper Google Workspace CLI (pg)"
requires-python = ">=3.12"
dependencies = [
    "google-api-python-client>=2.0.0",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.0",
]
```

- [ ] **Step 3: Install dependencies**

```bash
cd .claude/skills/google/scripts && uv sync && cd ../../../..
```

- [ ] **Step 4: Create credentials directory**

```bash
mkdir -p ~/.pepper/google
```

- [ ] **Step 5: Copy client_secret.json**

```bash
cp "C:/Users/jeffr/.openclaw/workspace/secrets/client_secret.json" ~/.pepper/google/client_secret.json
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/google/scripts/pyproject.toml .claude/skills/google/scripts/uv.lock
git commit -m "feat: initialize Google skill scripts project with dependencies"
```

---

### Task 2: Auth Module

**Files:**
- Create: `.claude/skills/google/scripts/auth.py`
- Create: `tests/test_google_auth.py`

- [ ] **Step 1: Write tests**

Create `tests/test_google_auth.py`:

```python
"""Tests for Google OAuth2 auth module."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "google" / "scripts"))


def test_get_credentials_dir():
    """Credentials directory defaults to ~/.pepper/google/."""
    from auth import get_credentials_dir

    cred_dir = get_credentials_dir()
    assert cred_dir.name == "google"
    assert "pepper" in str(cred_dir).lower() or ".pepper" in str(cred_dir)


def test_get_credentials_dir_env_override(tmp_path, monkeypatch):
    """PG_TOKEN_PATH env var overrides token location."""
    token_path = tmp_path / "token.json"
    monkeypatch.setenv("PG_TOKEN_PATH", str(token_path))

    from auth import get_token_path

    assert get_token_path() == token_path


def test_load_credentials_missing_token(tmp_path, monkeypatch):
    """Returns None when no token file exists."""
    monkeypatch.setenv("PG_TOKEN_PATH", str(tmp_path / "nonexistent.json"))

    from auth import load_credentials

    assert load_credentials() is None


def test_save_and_load_credentials(tmp_path, monkeypatch):
    """Credentials can be saved and loaded."""
    token_path = tmp_path / "token.json"
    monkeypatch.setenv("PG_TOKEN_PATH", str(token_path))

    mock_creds = MagicMock()
    mock_creds.to_json.return_value = json.dumps({
        "token": "access_123",
        "refresh_token": "refresh_456",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_id",
        "client_secret": "test_secret",
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
    })

    from auth import save_credentials

    save_credentials(mock_creds)
    assert token_path.exists()

    # Verify the saved file is valid JSON
    data = json.loads(token_path.read_text())
    assert data["token"] == "access_123"
    assert data["refresh_token"] == "refresh_456"


def test_check_auth_status_not_configured(tmp_path, monkeypatch):
    """auth_status returns not_configured when no token."""
    monkeypatch.setenv("PG_TOKEN_PATH", str(tmp_path / "nonexistent.json"))

    from auth import auth_status

    status = auth_status()
    assert status["status"] == "not_configured"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_google_auth.py -v
```

Expected: FAIL (auth module not found).

- [ ] **Step 3: Write auth.py**

Create `.claude/skills/google/scripts/auth.py`:

```python
"""OAuth2 authentication for Google APIs.

Handles the installed app OAuth2 flow, token storage at ~/.pepper/google/,
and automatic token refresh.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Default scopes — expanded as new services are added
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_credentials_dir() -> Path:
    """Get the credentials directory (~/.pepper/google/)."""
    return Path.home() / ".pepper" / "google"


def get_token_path() -> Path:
    """Get the token file path, respecting PG_TOKEN_PATH env var."""
    env_path = os.environ.get("PG_TOKEN_PATH")
    if env_path:
        return Path(env_path)
    return get_credentials_dir() / "token.json"


def get_client_secret_path() -> Path:
    """Get the client_secret.json path, respecting PG_CLIENT_SECRET env var."""
    env_path = os.environ.get("PG_CLIENT_SECRET")
    if env_path:
        return Path(env_path)
    return get_credentials_dir() / "client_secret.json"


def load_credentials() -> Credentials | None:
    """Load saved credentials from token.json.

    Returns None if no token file exists.
    Attempts to refresh expired tokens automatically.
    """
    token_path = get_token_path()
    if not token_path.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
        except Exception:
            return None

    if creds and creds.valid:
        return creds

    return None


def save_credentials(creds: Credentials) -> None:
    """Save credentials to token.json."""
    token_path = get_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())


def login() -> Credentials:
    """Run the OAuth2 installed app flow.

    Opens a browser for user consent and saves the resulting token.
    """
    client_secret = get_client_secret_path()
    if not client_secret.exists():
        print(f"Error: client_secret.json not found at {client_secret}", file=sys.stderr)
        print("Copy your Google Cloud OAuth2 credentials to that location.", file=sys.stderr)
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=8080)
    save_credentials(creds)
    return creds


def get_credentials() -> Credentials:
    """Get valid credentials, prompting login if needed."""
    creds = load_credentials()
    if creds:
        return creds

    print("Not authenticated. Run: pg auth login", file=sys.stderr)
    sys.exit(1)


def auth_status() -> dict:
    """Check authentication status."""
    token_path = get_token_path()
    if not token_path.exists():
        return {"status": "not_configured", "message": "No token found. Run: pg auth login"}

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception as e:
        return {"status": "error", "message": f"Invalid token: {e}"}

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return {
                "status": "authenticated",
                "scopes": list(creds.scopes or []),
                "message": "Token refreshed",
            }
        except Exception as e:
            return {"status": "expired", "message": f"Token expired and refresh failed: {e}"}

    if creds.valid:
        return {
            "status": "authenticated",
            "scopes": list(creds.scopes or []),
            "message": "Authenticated",
        }

    return {"status": "unknown", "message": "Token exists but state unclear"}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_google_auth.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/google/scripts/auth.py tests/test_google_auth.py
git commit -m "feat: add Google OAuth2 auth module with tests"
```

---

### Task 3: Calendar Module

**Files:**
- Create: `.claude/skills/google/scripts/calendar.py`
- Create: `tests/test_google_calendar.py`

- [ ] **Step 1: Write tests**

Create `tests/test_google_calendar.py`:

```python
"""Tests for Google Calendar module."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "google" / "scripts"))


@pytest.fixture
def mock_service():
    """Mock Google Calendar API service."""
    service = MagicMock()

    # Mock events().list()
    events_response = {
        "items": [
            {
                "id": "event1",
                "summary": "Team standup",
                "start": {"dateTime": "2026-04-07T09:00:00-04:00"},
                "end": {"dateTime": "2026-04-07T09:30:00-04:00"},
                "status": "confirmed",
                "htmlLink": "https://calendar.google.com/event?eid=event1",
            },
            {
                "id": "event2",
                "summary": "All day review",
                "start": {"date": "2026-04-07"},
                "end": {"date": "2026-04-08"},
                "status": "confirmed",
                "htmlLink": "https://calendar.google.com/event?eid=event2",
            },
        ]
    }
    service.events.return_value.list.return_value.execute.return_value = events_response

    # Mock freebusy().query()
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    {"start": "2026-04-07T09:00:00-04:00", "end": "2026-04-07T09:30:00-04:00"},
                    {"start": "2026-04-07T14:00:00-04:00", "end": "2026-04-07T15:00:00-04:00"},
                ]
            }
        }
    }
    service.freebusy.return_value.query.return_value.execute.return_value = freebusy_response

    # Mock events().insert()
    service.events.return_value.insert.return_value.execute.return_value = {
        "id": "new_event",
        "summary": "New meeting",
        "htmlLink": "https://calendar.google.com/event?eid=new_event",
    }

    # Mock calendarList().list()
    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": "primary", "summary": "Jeff Richley", "primary": True, "accessRole": "owner"},
            {"id": "work@example.com", "summary": "Work", "primary": False, "accessRole": "owner"},
        ]
    }

    return service


def test_list_events(mock_service):
    """list_events returns formatted event list."""
    from calendar import list_events

    events = list_events(mock_service, "2026-04-07", "2026-04-08")
    assert len(events) == 2
    assert events[0]["summary"] == "Team standup"
    assert events[0]["id"] == "event1"
    assert "start" in events[0]


def test_list_events_all_day(mock_service):
    """All-day events have date instead of dateTime."""
    from calendar import list_events

    events = list_events(mock_service, "2026-04-07", "2026-04-08")
    all_day = [e for e in events if e.get("all_day")]
    assert len(all_day) == 1
    assert all_day[0]["summary"] == "All day review"


def test_get_freebusy(mock_service):
    """get_freebusy returns busy and free blocks."""
    from calendar import get_freebusy

    result = get_freebusy(mock_service, "2026-04-07", "2026-04-08")
    assert "busy" in result
    assert "free" in result
    assert len(result["busy"]) == 2


def test_compute_free_slots():
    """Free slots are computed from busy blocks within working hours."""
    from calendar import compute_free_slots

    busy = [
        {"start": "2026-04-07T09:00:00-04:00", "end": "2026-04-07T09:30:00-04:00"},
        {"start": "2026-04-07T14:00:00-04:00", "end": "2026-04-07T15:00:00-04:00"},
    ]
    free = compute_free_slots(busy, "2026-04-07", "08:00", "18:00", "US/Eastern")
    assert len(free) == 3  # 8-9, 9:30-14, 15-18


def test_create_event(mock_service):
    """create_event calls insert and returns result."""
    from calendar import create_event

    result = create_event(
        mock_service,
        summary="New meeting",
        start="2026-04-07T10:00:00-04:00",
        end="2026-04-07T11:00:00-04:00",
    )
    assert result["id"] == "new_event"
    mock_service.events.return_value.insert.assert_called_once()


def test_delete_event(mock_service):
    """delete_event calls delete."""
    from calendar import delete_event

    service = mock_service
    service.events.return_value.delete.return_value.execute.return_value = None

    delete_event(service, "event1")
    service.events.return_value.delete.assert_called_once()


def test_list_calendars(mock_service):
    """list_calendars returns calendar list."""
    from calendar import list_calendars

    calendars = list_calendars(mock_service)
    assert len(calendars) == 2
    assert calendars[0]["id"] == "primary"
    assert calendars[0]["primary"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_google_calendar.py -v
```

Expected: FAIL (calendar module not found).

- [ ] **Step 3: Write calendar.py**

Create `.claude/skills/google/scripts/calendar.py`:

```python
"""Google Calendar API operations.

All functions take a Google Calendar service object as first argument.
Build the service with: build('calendar', 'v3', credentials=creds)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from zoneinfo import ZoneInfo

TIMEZONE = os.environ.get("PG_TIMEZONE", "US/Eastern")
WORKING_START = os.environ.get("PG_WORKING_HOURS_START", "08:00")
WORKING_END = os.environ.get("PG_WORKING_HOURS_END", "18:00")


def _parse_date(date_str: str) -> datetime:
    """Parse a date string (YYYY-MM-DD) into a timezone-aware datetime at midnight."""
    tz = ZoneInfo(TIMEZONE)
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)


def _to_rfc3339(dt: datetime) -> str:
    """Convert datetime to RFC3339 string."""
    return dt.isoformat()


def list_events(
    service,
    start_date: str,
    end_date: str,
    calendar_id: str = "primary",
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """List calendar events in a date range.

    Args:
        service: Google Calendar API service object.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        calendar_id: Calendar ID (default: primary).
        max_results: Maximum events to return.

    Returns:
        List of event dicts with normalized fields.
    """
    time_min = _to_rfc3339(_parse_date(start_date))
    time_max = _to_rfc3339(_parse_date(end_date) + timedelta(days=1))

    result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
        maxResults=max_results,
    ).execute()

    events = []
    for item in result.get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})
        is_all_day = "date" in start

        events.append({
            "id": item.get("id", ""),
            "summary": item.get("summary", "(No title)"),
            "start": start.get("date") if is_all_day else start.get("dateTime", ""),
            "end": end.get("date") if is_all_day else end.get("dateTime", ""),
            "all_day": is_all_day,
            "location": item.get("location", ""),
            "attendees": [a.get("email", "") for a in item.get("attendees", [])],
            "status": item.get("status", ""),
            "html_link": item.get("htmlLink", ""),
        })

    return events


def get_freebusy(
    service,
    start_date: str,
    end_date: str,
    calendar_id: str = "primary",
) -> dict[str, list]:
    """Get free/busy information for a date range.

    Returns dict with 'busy' and 'free' lists of time blocks.
    Free blocks are computed within working hours.
    """
    time_min = _to_rfc3339(_parse_date(start_date))
    time_max = _to_rfc3339(_parse_date(end_date) + timedelta(days=1))

    result = service.freebusy().query(body={
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": calendar_id}],
    }).execute()

    busy = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
    free = compute_free_slots(busy, start_date, WORKING_START, WORKING_END, TIMEZONE)

    return {"busy": busy, "free": free}


def compute_free_slots(
    busy: list[dict],
    date_str: str,
    work_start: str,
    work_end: str,
    timezone: str,
) -> list[dict[str, str]]:
    """Compute free time slots from busy blocks within working hours.

    Args:
        busy: List of {"start": rfc3339, "end": rfc3339} busy blocks.
        date_str: Date string (YYYY-MM-DD).
        work_start: Working hours start (HH:MM).
        work_end: Working hours end (HH:MM).
        timezone: Timezone string.

    Returns:
        List of {"start": rfc3339, "end": rfc3339} free blocks.
    """
    tz = ZoneInfo(timezone)
    base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)

    start_h, start_m = map(int, work_start.split(":"))
    end_h, end_m = map(int, work_end.split(":"))

    day_start = base.replace(hour=start_h, minute=start_m, second=0)
    day_end = base.replace(hour=end_h, minute=end_m, second=0)

    # Parse busy blocks into datetime pairs
    busy_pairs = []
    for block in busy:
        b_start = datetime.fromisoformat(block["start"])
        b_end = datetime.fromisoformat(block["end"])
        # Clip to working hours
        b_start = max(b_start, day_start)
        b_end = min(b_end, day_end)
        if b_start < b_end:
            busy_pairs.append((b_start, b_end))

    # Sort and merge overlapping
    busy_pairs.sort()
    merged = []
    for start, end in busy_pairs:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Compute free slots as gaps
    free = []
    cursor = day_start
    for b_start, b_end in merged:
        if cursor < b_start:
            free.append({"start": _to_rfc3339(cursor), "end": _to_rfc3339(b_start)})
        cursor = b_end
    if cursor < day_end:
        free.append({"start": _to_rfc3339(cursor), "end": _to_rfc3339(day_end)})

    return free


def create_event(
    service,
    summary: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
    location: str = "",
    description: str = "",
    attendees: list[str] | None = None,
    all_day: bool = False,
) -> dict[str, Any]:
    """Create a calendar event.

    Args:
        service: Google Calendar API service.
        summary: Event title.
        start: Start time (RFC3339) or date (YYYY-MM-DD for all-day).
        end: End time (RFC3339) or date (YYYY-MM-DD for all-day).
        calendar_id: Target calendar.
        location: Event location.
        description: Event description.
        attendees: List of attendee email addresses.
        all_day: If True, use date instead of dateTime.
    """
    body: dict[str, Any] = {"summary": summary}

    if all_day:
        body["start"] = {"date": start}
        body["end"] = {"date": end}
    else:
        body["start"] = {"dateTime": start}
        body["end"] = {"dateTime": end}

    if location:
        body["location"] = location
    if description:
        body["description"] = description
    if attendees:
        body["attendees"] = [{"email": e} for e in attendees]

    return service.events().insert(calendarId=calendar_id, body=body).execute()


def delete_event(
    service,
    event_id: str,
    calendar_id: str = "primary",
) -> None:
    """Delete a calendar event."""
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def list_calendars(service) -> list[dict[str, Any]]:
    """List all calendars the user has access to."""
    result = service.calendarList().list(maxResults=100).execute()
    calendars = []
    for item in result.get("items", []):
        calendars.append({
            "id": item.get("id", ""),
            "summary": item.get("summary", ""),
            "primary": item.get("primary", False),
            "access_role": item.get("accessRole", ""),
        })
    return calendars
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_google_calendar.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/google/scripts/calendar.py tests/test_google_calendar.py
git commit -m "feat: add Google Calendar module with events, freebusy, and CRUD"
```

---

### Task 4: CLI Entry Point

**Files:**
- Create: `.claude/skills/google/scripts/pg.py`

- [ ] **Step 1: Write pg.py**

Create `.claude/skills/google/scripts/pg.py`:

```python
"""Pepper Google CLI (pg).

CLI entry point for Google Workspace operations.
Usage: uv --directory .claude/skills/google/scripts run python pg.py [command]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from zoneinfo import ZoneInfo

from auth import auth_status, get_credentials, login
from calendar import (
    create_event,
    delete_event,
    get_freebusy,
    list_calendars,
    list_events,
)

app = typer.Typer(help="Pepper Google Workspace CLI")
auth_app = typer.Typer(help="Authentication commands")
cal_app = typer.Typer(help="Google Calendar commands")
app.add_typer(auth_app, name="auth")
app.add_typer(cal_app, name="calendar")

console = Console(stderr=True)
TIMEZONE = "US/Eastern"


def _build_service():
    """Build the Google Calendar service."""
    from googleapiclient.discovery import build

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


def _output(data, as_json: bool):
    """Print data as JSON to stdout or rich table to stderr."""
    if as_json:
        print(json.dumps(data, indent=2, default=str))
    else:
        console.print_json(json.dumps(data, default=str))


# --- Auth commands ---


@auth_app.command("login")
def auth_login_cmd():
    """Authenticate with Google (opens browser)."""
    creds = login()
    console.print("[green]Authenticated successfully![/green]")
    console.print(f"Token saved. Scopes: {list(creds.scopes or [])}")


@auth_app.command("status")
def auth_status_cmd(
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Check authentication status."""
    status = auth_status()
    _output(status, json_output)


# --- Calendar commands ---


@cal_app.command("events")
def cal_events_cmd(
    today: bool = typer.Option(False, "--today", help="Today's events"),
    date: Optional[str] = typer.Option(None, "--date", help="Events for a specific date (YYYY-MM-DD)"),
    week: bool = typer.Option(False, "--week", help="This week's events"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end: Optional[str] = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    calendar_id: str = typer.Option("primary", "--calendar", help="Calendar ID"),
    max_results: int = typer.Option(50, "--max", help="Max events"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
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
    date: Optional[str] = typer.Option(None, "--date", help="Date (YYYY-MM-DD)"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date"),
    end: Optional[str] = typer.Option(None, "--end", help="End date"),
    calendar_id: str = typer.Option("primary", "--calendar", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
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
    start: str = typer.Option(..., "--start", help="Start time (YYYY-MM-DD HH:MM or RFC3339)"),
    end: Optional[str] = typer.Option(None, "--end", help="End time"),
    duration: Optional[int] = typer.Option(None, "--duration", help="Duration in minutes (alternative to --end)"),
    date: Optional[str] = typer.Option(None, "--date", help="All-day event date (YYYY-MM-DD)"),
    location: str = typer.Option("", "--location", help="Location"),
    description: str = typer.Option("", "--description", help="Description"),
    attendees: Optional[str] = typer.Option(None, "--attendees", help="Comma-separated emails"),
    calendar_id: str = typer.Option("primary", "--calendar", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
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
                end_rfc = datetime.strptime(end, "%Y-%m-%d %H:%M").replace(tzinfo=tz).isoformat()
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
):
    """Delete a calendar event."""
    delete_event(_build_service(), event_id, calendar_id)
    console.print(f"[green]Deleted event {event_id}[/green]")


@cal_app.command("calendars")
def cal_calendars_cmd(
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List available calendars."""
    service = _build_service()
    calendars = list_calendars(service)
    _output(calendars, json_output)


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/google/scripts/pg.py
git commit -m "feat: add pg CLI entry point with auth and calendar commands"
```

---

### Task 5: Skill Files

**Files:**
- Create: `.claude/skills/google/SKILL.md`
- Create: `.claude/skills/google/references/calendar.md`

- [ ] **Step 1: Create SKILL.md**

Create `.claude/skills/google/SKILL.md`:

```markdown
---
name: google
description: Google Workspace integration for calendar, email, and documents. Use when user mentions calendar, schedule, meetings, availability, events, free time, or booking. Handles event lookup, scheduling, free/busy queries, and event creation. Do NOT use for general web search or non-Google questions.
allowed-tools: Bash(uv --directory * run python pg.py *) Read
metadata:
  author: Pepper
  version: "1.0"
---

# Google Workspace

Pepper's Google integration. Currently supports Calendar. Gmail and Drive coming soon.

## Setup Check

If any command below returns an error about authentication, guide the user:
1. Run: `uv --directory $CLAUDE_PROJECT_DIR/.claude/skills/google/scripts run python pg.py auth login`
2. This opens a browser for Google OAuth consent
3. After approval, the token is saved at `~/.pepper/google/token.json`

## Current Context

**Today's calendar:**
```!
uv --directory $CLAUDE_PROJECT_DIR/.claude/skills/google/scripts run python pg.py calendar events --today --json 2>/dev/null || echo "GOOGLE_NOT_CONFIGURED"
```

If the output above is `GOOGLE_NOT_CONFIGURED`, tell the user to run `pg auth login` first.

## Calendar Commands

All commands run via:
`uv --directory $CLAUDE_PROJECT_DIR/.claude/skills/google/scripts run python pg.py calendar [subcommand]`

### Reading Events
- Today: `pg.py calendar events --today --json`
- Specific date: `pg.py calendar events --date 2026-04-07 --json`
- This week: `pg.py calendar events --week --json`
- Date range: `pg.py calendar events --start 2026-04-07 --end 2026-04-14 --json`

### Finding Free Time
- Today: `pg.py calendar freebusy --today --json`
- Tomorrow: `pg.py calendar freebusy --date tomorrow --json`

### Creating Events
CRITICAL: Never create an event without explicit user confirmation. Always show what you plan to create and wait for approval.

- Timed: `pg.py calendar create "Meeting" --start "2026-04-07 10:00" --end "2026-04-07 11:00" --json`
- With duration: `pg.py calendar create "Lunch" --start "2026-04-07 12:00" --duration 60 --json`
- All day: `pg.py calendar create "Review day" --date 2026-04-07 --json`

### Deleting Events
CRITICAL: Never delete without explicit user confirmation.

- `pg.py calendar delete EVENT_ID`

### Listing Calendars
- `pg.py calendar calendars --json`

## Workflow Guidelines

- When asked about schedule: fetch events first, then summarize
- When asked to schedule something: check freebusy first, suggest times, get confirmation, then create
- For morning briefings: fetch today's events and format as a summary
- When sending calendar info to Discord: use rich embeds with fields for each event
- Check `references/calendar.md` for detailed API patterns and error handling

## Error Handling

- "Not authenticated": Direct user to `pg auth login`
- "Token expired": The CLI auto-refreshes. If it fails, direct to `pg auth login`
- API quota errors: Wait 60 seconds, retry once
- 404 on event: Event was deleted or calendar changed, inform user
```

- [ ] **Step 2: Create calendar reference**

Create `.claude/skills/google/references/calendar.md`:

```markdown
# Google Calendar Reference

## pg CLI Command Reference

### pg auth login
Opens browser for OAuth2 consent. Stores token at `~/.pepper/google/token.json`.

### pg auth status [--json]
Check authentication state. Returns: authenticated, expired, not_configured, or error.

### pg calendar events [options] [--json]
| Option | Description |
|--------|-------------|
| `--today` | Today's events (default) |
| `--date DATE` | Events for YYYY-MM-DD |
| `--week` | Monday through Sunday |
| `--start DATE --end DATE` | Custom range |
| `--calendar ID` | Calendar ID (default: primary) |
| `--max N` | Max results (default: 50) |

### pg calendar freebusy [options] [--json]
| Option | Description |
|--------|-------------|
| `--today` | Today (default) |
| `--date DATE` | Specific date or "tomorrow" |
| `--start DATE --end DATE` | Custom range |
| `--calendar ID` | Calendar ID |

Free blocks computed within working hours (default 8AM-6PM ET).

### pg calendar create SUMMARY [options] [--json]
| Option | Description |
|--------|-------------|
| `--start DATETIME` | Start (YYYY-MM-DD HH:MM) |
| `--end DATETIME` | End time |
| `--duration MINUTES` | Alternative to --end |
| `--date DATE` | All-day event |
| `--location TEXT` | Location |
| `--description TEXT` | Description |
| `--attendees EMAIL,...` | Comma-separated |
| `--calendar ID` | Calendar ID |

### pg calendar delete EVENT_ID [--calendar ID]
Delete an event by ID.

### pg calendar calendars [--json]
List all calendars.

## Date/Time Formats
- Dates: `YYYY-MM-DD` (e.g., 2026-04-07)
- Times: `YYYY-MM-DD HH:MM` (e.g., 2026-04-07 10:00)
- RFC3339: `2026-04-07T10:00:00-04:00`
- All times default to US/Eastern timezone

## Common Errors
| Error | Cause | Fix |
|-------|-------|-----|
| "Not authenticated" | No token | `pg auth login` |
| "Token expired" | Refresh failed | `pg auth login` |
| 403 Forbidden | Scope missing | `pg auth login` (re-consent) |
| 404 Not Found | Event deleted | Inform user |
| 429 Rate Limit | Too many requests | Wait 60s, retry |

## JSON Output Format

### Events
```json
[{"id": "...", "summary": "...", "start": "...", "end": "...", "all_day": false, "location": "...", "attendees": [...], "status": "...", "html_link": "..."}]
```

### Free/Busy
```json
{"busy": [{"start": "...", "end": "..."}], "free": [{"start": "...", "end": "..."}]}
```
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/google/SKILL.md .claude/skills/google/references/calendar.md
git commit -m "feat: add Google skill SKILL.md with calendar workflows and reference"
```

---

### Task 6: Setup and Integration Test

- [ ] **Step 1: Run all unit tests**

```bash
uv run pytest tests/test_google_auth.py tests/test_google_calendar.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 2: Run OAuth login**

```bash
uv --directory .claude/skills/google/scripts run python pg.py auth login
```

This opens a browser. Approve the consent screen. Token saved to `~/.pepper/google/token.json`.

- [ ] **Step 3: Test CLI commands**

```bash
uv --directory .claude/skills/google/scripts run python pg.py auth status --json
uv --directory .claude/skills/google/scripts run python pg.py calendar events --today --json
uv --directory .claude/skills/google/scripts run python pg.py calendar calendars --json
uv --directory .claude/skills/google/scripts run python pg.py calendar freebusy --today --json
```

Expected: JSON output for each command. Events and calendars from your real Google account.

- [ ] **Step 4: Final commit and push**

```bash
git add -A
git commit -m "feat: Google Calendar skill complete — pg CLI, OAuth, events, freebusy"
git push origin main
```
