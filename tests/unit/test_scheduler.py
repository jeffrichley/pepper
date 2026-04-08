"""Tests for scheduler core functionality."""

from pathlib import Path

import pytest
import yaml

JOBS_YAML = (
    Path(__file__).parent.parent.parent
    / "src"
    / "pepper"
    / "scheduler"
    / "jobs.yaml"
)


def test_jobs_yaml_loads():
    """jobs.yaml is valid YAML with expected structure."""
    # Arrange - locate the jobs.yaml file
    yaml_path = JOBS_YAML

    # Act - load and parse the YAML
    with open(yaml_path) as f:
        jobs = yaml.safe_load(f)

    # Assert - verify structure contains expected jobs
    assert isinstance(jobs, dict)
    assert "heartbeat" in jobs
    assert "morning_briefing" in jobs
    assert "nightly_reflection" in jobs


def test_jobs_yaml_required_fields():
    """Each job has trigger, schedule, and prompt."""
    # Arrange - load the jobs YAML
    with open(JOBS_YAML) as f:
        jobs = yaml.safe_load(f)

    # Act - iterate over all jobs (validation happens in assert)

    # Assert - verify each job has required fields
    for name, job in jobs.items():
        assert "trigger" in job, f"Job {name} missing trigger"
        assert "schedule" in job, f"Job {name} missing schedule"
        if job.get("type") == "function":
            assert "function" in job, f"Function job {name} missing function"
        else:
            assert "prompt" in job, f"Job {name} missing prompt"
        assert job["trigger"] in ("interval", "cron", "once"), (
            f"Job {name} has invalid trigger"
        )


def test_load_seed_jobs():
    """load_seed_jobs returns parsed job definitions."""
    from pepper.scheduler.core import load_seed_jobs

    # Arrange - use the real jobs.yaml path
    yaml_path = JOBS_YAML

    # Act - load seed jobs from YAML
    jobs = load_seed_jobs(yaml_path)

    # Assert - verify correct number and content of jobs
    assert len(jobs) == 4
    assert "heartbeat" in jobs
    assert jobs["heartbeat"]["trigger"] == "interval"
    assert jobs["heartbeat"]["schedule"]["minutes"] == 30


@pytest.mark.asyncio
async def test_execute_job_posts_to_channel():
    """Job execution POSTs to the channel server."""
    from unittest.mock import AsyncMock, patch

    from pepper.scheduler.core import execute_job

    # Arrange - mock the HTTP client
    with patch("pepper.scheduler.core.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock()
        mock_client_cls.return_value = mock_client

        # Act - execute a job
        await execute_job("heartbeat", "Check stuff", "#pepper-chat")

        # Assert - verify the HTTP POST was made with correct payload
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["source"] == "scheduler"
        assert "heartbeat" in payload["chat_id"]
        assert payload["content"] == "Check stuff"
