"""Pepper Discord MCP Server.

Entry point spawned by Claude Code via .mcp.json.
Runs the Discord bot, scheduler, and SSE listener in one process.
Exposes Discord and scheduler tools via MCP over stdio.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (stdout is used by MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("pepper-mcp")

# Import integration modules
from apscheduler import AsyncScheduler  # noqa: E402

from .bot import client, start_bot  # noqa: E402
from .config import DISCORD_BOT_TOKEN, JOBS_YAML  # noqa: E402
from .discord_tools import (  # noqa: E402
    add_reaction_impl,
    get_channel_info_impl,
    get_recent_messages_impl,
    list_channels_impl,
    send_discord_message_impl,
    send_typing_impl,
)
from .scheduler import create_scheduler, seed_default_jobs  # noqa: E402
from .scheduler_tools import (  # noqa: E402
    create_job_impl,
    delete_job_impl,
    list_jobs_impl,
    pause_job_impl,
    resume_job_impl,
    update_job_impl,
)

# Global scheduler reference (set in lifespan)
_scheduler: AsyncScheduler | None = None


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:  # noqa: ARG001
    """Start Discord bot and scheduler on MCP server startup."""
    global _scheduler  # noqa: PLW0603

    log.info("Starting Pepper Discord integration...")

    # Create and start scheduler
    _scheduler = await create_scheduler()
    async with _scheduler:
        await seed_default_jobs(_scheduler, JOBS_YAML)
        await _scheduler.start_in_background()
        log.info("Scheduler started")

        # Start Discord bot as a background task
        bot_task = asyncio.create_task(start_bot(DISCORD_BOT_TOKEN))
        log.info("Discord bot starting...")

        yield

        # Shutdown
        log.info("Shutting down...")
        client.clear()
        bot_task.cancel()


# Create the MCP server
mcp = FastMCP(
    "pepper-discord",
    lifespan=lifespan,
)


# --- Discord Tools ---


@mcp.tool()
async def send_discord_message(
    channel_id: str,
    text: str = "",
    embed: dict[str, Any] | None = None,
    files: list[str] | None = None,
) -> dict[str, str]:
    """Send a message to a Discord channel.

    Supports text, rich embeds, files, or any combination.

    Args:
        channel_id: The Discord channel ID to send to.
        text: Message text (markdown supported).
        embed: Rich embed with title, description, color, fields.
        files: File paths or URLs to attach as files.
    """
    return await send_discord_message_impl(client, channel_id, text, embed, files)


@mcp.tool()
async def add_reaction(
    channel_id: str,
    message_id: str,
    emoji: str,
) -> dict[str, str]:
    """Add a reaction to a Discord message.

    Args:
        channel_id: The channel containing the message.
        message_id: The message to react to.
        emoji: Emoji name (thumbs_up, fire, rocket, etc.) or unicode character.
    """
    return await add_reaction_impl(client, channel_id, message_id, emoji)


@mcp.tool()
async def send_typing(channel_id: str) -> dict[str, str]:
    """Show typing indicator in a Discord channel.

    Args:
        channel_id: The channel to show typing in.
    """
    return await send_typing_impl(client, channel_id)


@mcp.tool()
async def list_channels(guild_id: str | None = None) -> list[dict[str, Any]]:
    """List all Discord channels the bot can see.

    Args:
        guild_id: Optional guild/server ID to filter by.
    """
    return await list_channels_impl(client, guild_id)


@mcp.tool()
async def get_recent_messages(
    channel_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent messages from a Discord channel.

    Args:
        channel_id: The channel to read from.
        limit: Number of messages to fetch (default 10, max 50).
    """
    return await get_recent_messages_impl(client, channel_id, limit)


@mcp.tool()
async def get_channel_info(channel_id: str) -> dict[str, Any]:
    """Get detailed information about a Discord channel.

    Args:
        channel_id: The channel to inspect.
    """
    return await get_channel_info_impl(client, channel_id)


# --- Scheduler Tools ---


@mcp.tool()
async def create_job(  # noqa: PLR0913
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
        trigger: Trigger type: "interval" or "cron".
        schedule: For interval: {minutes, hours, seconds}.
            For cron: {hour, minute, day_of_week, day, month}.
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
    """Entry point for pepper-discord command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
