"""APScheduler setup and job execution.

Loads default jobs from jobs.yaml, persists state to SQLite,
and executes jobs by POSTing prompts to the channel server.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import create_async_engine

from config import CHANNEL_URL, SCHEDULER_DB, TIMEZONE

log = logging.getLogger("pepper-scheduler")


def load_seed_jobs(yaml_path: Path) -> dict[str, Any]:
    """Load job definitions from a YAML file."""
    if not yaml_path.exists():
        log.warning(f"Jobs file not found: {yaml_path}")
        return {}

    with open(yaml_path) as f:
        return yaml.safe_load(f) or {}


def build_trigger(job_def: dict[str, Any]):
    """Build an APScheduler trigger from a job definition."""
    trigger_type = job_def["trigger"]
    schedule = job_def["schedule"]

    if trigger_type == "interval":
        return IntervalTrigger(
            hours=schedule.get("hours", 0),
            minutes=schedule.get("minutes", 0),
            seconds=schedule.get("seconds", 0),
        )
    elif trigger_type == "cron":
        return CronTrigger(
            hour=schedule.get("hour"),
            minute=schedule.get("minute", 0),
            day_of_week=schedule.get("day_of_week"),
            day=schedule.get("day"),
            month=schedule.get("month"),
            timezone=job_def.get("timezone", TIMEZONE),
        )
    else:
        raise ValueError(f"Unknown trigger type: {trigger_type}")


async def execute_job(name: str, prompt: str, channel_hint: str = ""):
    """Execute a scheduled job by POSTing to the channel server."""
    chat_id = f"scheduler-{name}-{int(time.time())}"

    payload = {
        "source": "scheduler",
        "chat_id": chat_id,
        "sender": "scheduler",
        "content": prompt,
        "metadata": {
            "job_name": name,
            "channel_hint": channel_hint,
        },
    }

    async with httpx.AsyncClient() as http:
        try:
            resp = await http.post(
                f"{CHANNEL_URL}/message",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 200:
                log.info(f"Job {name} fired (chat_id: {chat_id})")
            else:
                log.error(f"Job {name} failed: {resp.status_code} {resp.text}")
        except httpx.ConnectError:
            log.error(f"Job {name}: channel server unreachable")


async def create_scheduler() -> AsyncScheduler:
    """Create and configure the APScheduler instance."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{SCHEDULER_DB}")
    data_store = SQLAlchemyDataStore(engine)
    scheduler = AsyncScheduler(data_store=data_store)
    return scheduler


async def seed_default_jobs(scheduler: AsyncScheduler, yaml_path: Path):
    """Seed default jobs from YAML if they don't already exist."""
    existing = await scheduler.get_schedules()
    existing_ids = {s.id for s in existing}

    seed_jobs = load_seed_jobs(yaml_path)

    for name, job_def in seed_jobs.items():
        if name in existing_ids:
            log.debug(f"Job {name} already exists, skipping seed")
            continue

        trigger = build_trigger(job_def)
        prompt = job_def["prompt"]
        channel_hint = job_def.get("channel_hint", "")

        await scheduler.add_schedule(
            execute_job,
            trigger,
            id=name,
            args=[name, prompt, channel_hint],
        )
        log.info(f"Seeded job: {name}")
