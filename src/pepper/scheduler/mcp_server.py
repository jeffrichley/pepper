"""Pepper Scheduler MCP Server.

Entry point spawned by Claude Code via .mcp.json.
Runs the scheduler as an independent process.
Exposes scheduler tools via MCP over stdio.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from apscheduler import AsyncScheduler
from mcp.server.fastmcp import FastMCP

from .config import JOBS_YAML
from .core import configure_task_concurrency, create_scheduler, seed_default_jobs
from .tools import (
    create_job_impl,
    delete_job_impl,
    list_jobs_impl,
    pause_job_impl,
    resume_job_impl,
    update_job_impl,
)

# Configure logging to stderr (stdout is used by MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("pepper-scheduler")

# Global scheduler reference (set in lifespan)
_scheduler: AsyncScheduler | None = None


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Start scheduler on MCP server startup."""
    global _scheduler

    log.info("Starting Pepper Scheduler...")

    _scheduler = await create_scheduler()
    async with _scheduler:
        await configure_task_concurrency(_scheduler)
        await seed_default_jobs(_scheduler, JOBS_YAML)
        await _scheduler.start_in_background()
        log.info("Scheduler started")

        yield

        log.info("Shutting down scheduler...")


# Create the MCP server
mcp = FastMCP(
    "pepper-scheduler",
    lifespan=lifespan,
)


# --- Scheduler Tools ---


@mcp.tool()
async def create_job(
    name: str,
    trigger: str,
    schedule: dict[str, Any],
    prompt: str,
    channel_hint: str = "",
    timezone: str = "US/Eastern",
) -> dict[str, str]:
    """Create a new scheduled job.

    Args:
        name: Unique job identifier (snake_case).
        trigger: Trigger type: "interval", "cron", or "date" (one-shot).
        schedule: For interval: {minutes, hours, seconds}.
            For cron: {hour, minute, day_of_week, day, month}.
            For date: {run_time: "2026-04-10T09:00:00-04:00"} (ISO datetime).
        prompt: The prompt to send to Pepper when this job fires.
        channel_hint: Optional suggested Discord channel for context.
        timezone: Timezone for cron triggers (default: US/Eastern).
    """
    if _scheduler is None:
        return {"status": "error", "message": "Scheduler not initialized"}
    return await create_job_impl(
        _scheduler,
        name,
        trigger,
        schedule,
        prompt,
        channel_hint,
        timezone,
    )


@mcp.tool()
async def update_job(
    name: str,
    schedule: dict[str, Any] | None = None,
    prompt: str | None = None,
    channel_hint: str | None = None,
    timezone: str | None = None,
) -> dict[str, str]:
    """Update an existing scheduled job.

    Args:
        name: Job identifier to update.
        schedule: New schedule (optional).
        prompt: New prompt (optional).
        channel_hint: New channel hint (optional).
        timezone: New timezone (optional).
    """
    if _scheduler is None:
        return {"status": "error", "message": "Scheduler not initialized"}
    return await update_job_impl(
        _scheduler,
        name,
        schedule,
        prompt,
        channel_hint,
        timezone,
    )


@mcp.tool()
async def delete_job(name: str) -> dict[str, str]:
    """Delete a scheduled job.

    Args:
        name: Job identifier to delete.
    """
    if _scheduler is None:
        return {"status": "error", "message": "Scheduler not initialized"}
    return await delete_job_impl(_scheduler, name)


@mcp.tool()
async def list_jobs() -> list[dict[str, Any]]:
    """List all scheduled jobs with their schedules and next run times."""
    if _scheduler is None:
        return []
    return await list_jobs_impl(_scheduler)


@mcp.tool()
async def pause_job(name: str) -> dict[str, str]:
    """Pause a scheduled job (stops firing but keeps the definition).

    Args:
        name: Job identifier to pause.
    """
    if _scheduler is None:
        return {"status": "error", "message": "Scheduler not initialized"}
    return await pause_job_impl(_scheduler, name)


@mcp.tool()
async def resume_job(name: str) -> dict[str, str]:
    """Resume a paused job.

    Args:
        name: Job identifier to resume.
    """
    if _scheduler is None:
        return {"status": "error", "message": "Scheduler not initialized"}
    return await resume_job_impl(_scheduler, name)


def run() -> None:
    """Entry point for pepper-scheduler command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
