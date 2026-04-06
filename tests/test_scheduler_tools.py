"""Tests for scheduler MCP tool implementations."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "discord"))


@pytest.fixture
def mock_scheduler():
    scheduler = AsyncMock()

    schedule1 = MagicMock()
    schedule1.id = "heartbeat"
    schedule1.trigger = MagicMock()
    schedule1.trigger.__str__ = lambda self: "interval[0:30:00]"
    schedule1.next_fire_time = None
    schedule1.args = ["heartbeat", "Check stuff", "#pepper-chat"]
    schedule1.paused = False

    scheduler.get_schedules = AsyncMock(return_value=[schedule1])
    scheduler.get_schedule = AsyncMock(return_value=schedule1)

    return scheduler


@pytest.mark.asyncio
async def test_list_jobs(mock_scheduler):
    from scheduler_tools import list_jobs_impl

    result = await list_jobs_impl(mock_scheduler)
    assert len(result) == 1
    assert result[0]["name"] == "heartbeat"


@pytest.mark.asyncio
async def test_create_job(mock_scheduler):
    from scheduler_tools import create_job_impl

    result = await create_job_impl(
        mock_scheduler,
        name="test_job",
        trigger="interval",
        schedule={"minutes": 10},
        prompt="Test prompt",
    )
    assert result["status"] == "created"
    mock_scheduler.add_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_delete_job(mock_scheduler):
    from scheduler_tools import delete_job_impl

    result = await delete_job_impl(mock_scheduler, "heartbeat")
    assert result["status"] == "deleted"
    mock_scheduler.remove_schedule.assert_called_once_with("heartbeat")


@pytest.mark.asyncio
async def test_pause_job(mock_scheduler):
    from scheduler_tools import pause_job_impl

    result = await pause_job_impl(mock_scheduler, "heartbeat")
    assert result["status"] == "paused"
    mock_scheduler.pause_schedule.assert_called_once_with("heartbeat")
