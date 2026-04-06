"""Tests for Google Calendar module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "google" / "scripts"))


@pytest.fixture
def mock_service():
    """Mock Google Calendar API service."""
    service = MagicMock()

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

    service.events.return_value.insert.return_value.execute.return_value = {
        "id": "new_event",
        "summary": "New meeting",
        "htmlLink": "https://calendar.google.com/event?eid=new_event",
    }

    service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [
            {"id": "primary", "summary": "Jeff Richley", "primary": True, "accessRole": "owner"},
            {"id": "work@example.com", "summary": "Work", "primary": False, "accessRole": "owner"},
        ]
    }

    return service


def test_list_events(mock_service):
    from gcal import list_events

    events = list_events(mock_service, "2026-04-07", "2026-04-08")
    assert len(events) == 2
    assert events[0]["summary"] == "Team standup"
    assert events[0]["id"] == "event1"


def test_list_events_all_day(mock_service):
    from gcal import list_events

    events = list_events(mock_service, "2026-04-07", "2026-04-08")
    all_day = [e for e in events if e.get("all_day")]
    assert len(all_day) == 1
    assert all_day[0]["summary"] == "All day review"


def test_get_freebusy(mock_service):
    from gcal import get_freebusy

    result = get_freebusy(mock_service, "2026-04-07", "2026-04-08")
    assert "busy" in result
    assert "free" in result
    assert len(result["busy"]) == 2


def test_compute_free_slots():
    from gcal import compute_free_slots

    busy = [
        {"start": "2026-04-07T09:00:00-04:00", "end": "2026-04-07T09:30:00-04:00"},
        {"start": "2026-04-07T14:00:00-04:00", "end": "2026-04-07T15:00:00-04:00"},
    ]
    free = compute_free_slots(busy, "2026-04-07", "08:00", "18:00", "US/Eastern")
    assert len(free) == 3


def test_create_event(mock_service):
    from gcal import create_event

    result = create_event(
        mock_service,
        summary="New meeting",
        start="2026-04-07T10:00:00-04:00",
        end="2026-04-07T11:00:00-04:00",
    )
    assert result["id"] == "new_event"
    mock_service.events.return_value.insert.assert_called_once()


def test_delete_event(mock_service):
    from gcal import delete_event

    mock_service.events.return_value.delete.return_value.execute.return_value = None
    delete_event(mock_service, "event1")
    mock_service.events.return_value.delete.assert_called_once()


def test_list_calendars(mock_service):
    from gcal import list_calendars

    calendars = list_calendars(mock_service)
    assert len(calendars) == 2
    assert calendars[0]["id"] == "primary"
    assert calendars[0]["primary"] is True
