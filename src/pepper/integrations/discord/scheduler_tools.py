"""Scheduler MCP tool implementations.

These are the raw async functions. The MCP tool decorators
are in mcp_server.py which calls these.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler import AsyncScheduler
from apscheduler.abc import Trigger

from .scheduler import build_trigger, execute_job

log = logging.getLogger("pepper-scheduler")


async def list_jobs_impl(scheduler: AsyncScheduler) -> list[dict[str, Any]]:
    """List all scheduled jobs with their details."""
    schedules = await scheduler.get_schedules()
    result = []

    for s in schedules:
        job_info = {
            "name": s.id,
            "trigger": str(s.trigger),
            "next_run": s.next_fire_time.isoformat() if s.next_fire_time else None,
            "paused": getattr(s, "paused", False),
        }
        if s.args and len(s.args) >= 2:  # noqa: PLR2004
            job_info["prompt"] = s.args[1]
        if s.args and len(s.args) >= 3:  # noqa: PLR2004
            job_info["channel_hint"] = s.args[2]
        result.append(job_info)

    return result


async def create_job_impl(  # noqa: PLR0913
    scheduler: AsyncScheduler,
    name: str,
    trigger: str,
    schedule: dict[str, Any],
    prompt: str,
    channel_hint: str = "",
    timezone: str = "US/Eastern",
) -> dict[str, str]:
    """Create a new scheduled job."""
    job_def = {
        "trigger": trigger,
        "schedule": schedule,
        "timezone": timezone,
    }

    try:
        apscheduler_trigger = build_trigger(job_def)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    await scheduler.add_schedule(
        execute_job,
        apscheduler_trigger,
        id=name,
        args=[name, prompt, channel_hint],
    )

    log.info(f"Created job: {name}")
    return {"status": "created", "name": name}


def _get_schedule_arg(args: tuple[str, ...] | None, index: int) -> str:
    """Extract an argument from a schedule's args tuple, defaulting to ''."""
    if args and len(args) > index:
        return str(args[index])
    return ""


def _resolve_trigger(
    existing_trigger: Trigger,
    schedule: dict[str, Any] | None,
    timezone: str | None,
) -> Trigger:
    """Build a new trigger from schedule dict, or reuse the existing one."""
    if not schedule:
        return existing_trigger
    trigger_str = str(existing_trigger)
    trigger_type = "interval" if "interval" in trigger_str.lower() else "cron"
    job_def = {
        "trigger": trigger_type,
        "schedule": schedule,
        "timezone": timezone or "US/Eastern",
    }
    return build_trigger(job_def)


async def update_job_impl(  # noqa: PLR0913
    scheduler: AsyncScheduler,
    name: str,
    schedule: dict[str, Any] | None = None,
    prompt: str | None = None,
    channel_hint: str | None = None,
    timezone: str | None = None,
) -> dict[str, str]:
    """Update an existing job. Removes and re-creates it."""
    try:
        existing = await scheduler.get_schedule(name)
    except Exception:
        return {"status": "error", "message": f"Job {name} not found"}

    current_prompt = _get_schedule_arg(existing.args, 1)
    current_hint = _get_schedule_arg(existing.args, 2)

    await scheduler.remove_schedule(name)

    new_trigger = _resolve_trigger(existing.trigger, schedule, timezone)

    await scheduler.add_schedule(
        execute_job,
        new_trigger,
        id=name,
        args=[name, prompt or current_prompt, channel_hint or current_hint],
    )

    log.info(f"Updated job: {name}")
    return {"status": "updated", "name": name}


async def delete_job_impl(
    scheduler: AsyncScheduler,
    name: str,
) -> dict[str, str]:
    """Delete a scheduled job."""
    await scheduler.remove_schedule(name)
    log.info(f"Deleted job: {name}")
    return {"status": "deleted", "name": name}


async def pause_job_impl(
    scheduler: AsyncScheduler,
    name: str,
) -> dict[str, str]:
    """Pause a scheduled job."""
    await scheduler.pause_schedule(name)
    log.info(f"Paused job: {name}")
    return {"status": "paused", "name": name}


async def resume_job_impl(
    scheduler: AsyncScheduler,
    name: str,
) -> dict[str, str]:
    """Resume a paused job."""
    await scheduler.unpause_schedule(name, resume_from="now")
    log.info(f"Resumed job: {name}")
    return {"status": "resumed", "name": name}
