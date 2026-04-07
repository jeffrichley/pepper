"""Google Calendar API operations.

All functions take a Google Calendar service object as first argument.
Build the service with: build('calendar', 'v3', credentials=creds)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, cast
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
    service: Any,
    start_date: str,
    end_date: str,
    calendar_id: str = "primary",
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """List calendar events in a date range."""
    time_min = _to_rfc3339(_parse_date(start_date))
    time_max = _to_rfc3339(_parse_date(end_date) + timedelta(days=1))

    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})
        is_all_day = "date" in start

        events.append(
            {
                "id": item.get("id", ""),
                "summary": item.get("summary", "(No title)"),
                "start": start.get("date") if is_all_day else start.get("dateTime", ""),
                "end": end.get("date") if is_all_day else end.get("dateTime", ""),
                "all_day": is_all_day,
                "location": item.get("location", ""),
                "attendees": [a.get("email", "") for a in item.get("attendees", [])],
                "status": item.get("status", ""),
                "html_link": item.get("htmlLink", ""),
            }
        )

    return events


def get_freebusy(
    service: Any,
    start_date: str,
    end_date: str,
    calendar_id: str = "primary",
) -> dict[str, list[Any]]:
    """Get free/busy information for a date range."""
    time_min = _to_rfc3339(_parse_date(start_date))
    time_max = _to_rfc3339(_parse_date(end_date) + timedelta(days=1))

    result = (
        service.freebusy()
        .query(
            body={
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": calendar_id}],
            }
        )
        .execute()
    )

    busy = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
    free = compute_free_slots(busy, start_date, WORKING_START, WORKING_END, TIMEZONE)

    return {"busy": busy, "free": free}


def compute_free_slots(
    busy: list[dict[str, Any]],
    date_str: str,
    work_start: str,
    work_end: str,
    timezone: str,
) -> list[dict[str, str]]:
    """Compute free time slots from busy blocks within working hours."""
    tz = ZoneInfo(timezone)
    base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)

    start_h, start_m = map(int, work_start.split(":"))
    end_h, end_m = map(int, work_end.split(":"))

    day_start = base.replace(hour=start_h, minute=start_m, second=0)
    day_end = base.replace(hour=end_h, minute=end_m, second=0)

    busy_pairs = []
    for block in busy:
        b_start = datetime.fromisoformat(block["start"])
        b_end = datetime.fromisoformat(block["end"])
        b_start = max(b_start, day_start)
        b_end = min(b_end, day_end)
        if b_start < b_end:
            busy_pairs.append((b_start, b_end))

    busy_pairs.sort()
    merged: list[tuple[datetime, datetime]] = []
    for start, end in busy_pairs:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

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
    service: Any,
    summary: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
    location: str = "",
    description: str = "",
    attendees: list[str] | None = None,
    all_day: bool = False,
) -> dict[str, Any]:
    """Create a calendar event."""
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

    return cast(dict[str, Any], service.events().insert(calendarId=calendar_id, body=body).execute())


def delete_event(
    service: Any,
    event_id: str,
    calendar_id: str = "primary",
) -> None:
    """Delete a calendar event."""
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def list_calendars(service: Any) -> list[dict[str, Any]]:
    """List all calendars the user has access to."""
    result = service.calendarList().list(maxResults=100).execute()
    return [
        {
            "id": item.get("id", ""),
            "summary": item.get("summary", ""),
            "primary": item.get("primary", False),
            "access_role": item.get("accessRole", ""),
        }
        for item in result.get("items", [])
    ]
