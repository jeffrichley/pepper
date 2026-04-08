"""Pepper Discord MCP Server.

Entry point spawned by Claude Code via .mcp.json.
Runs the Discord bot in one process.
Exposes Discord tools via MCP over stdio.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
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
from .bot import client, start_bot  # noqa: E402
from .config import CHANNEL_URL, DISCORD_BOT_TOKEN  # noqa: E402
from .discord_tools import (  # noqa: E402
    add_reaction_impl,
    cancel_scheduled_event_impl,
    create_poll_impl,
    create_scheduled_event_impl,
    create_thread_impl,
    download_attachments_impl,
    edit_message_impl,
    fetch_messages_impl,
    get_channel_info_impl,
    list_channels_impl,
    list_scheduled_events_impl,
    send_briefing_impl,
    send_discord_message_impl,
    send_typing_impl,
)

SHUTDOWN_TIMEOUT_SECONDS = 2.0


async def _watch_stdin(shutdown_event: asyncio.Event) -> None:
    """Watch for stdin EOF (MCP connection end) and signal shutdown."""
    loop = asyncio.get_running_loop()
    with contextlib.suppress(Exception):
        await loop.run_in_executor(None, sys.stdin.read)
    log.info("stdin closed — MCP connection ended")
    shutdown_event.set()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:  # noqa: ARG001
    """Start Discord bot on MCP server startup with graceful shutdown."""
    log.info("Starting Pepper Discord integration...")

    shutdown_event = asyncio.Event()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            signal.signal(sig, lambda *_: shutdown_event.set())

    # Start Discord bot and stdin watcher
    bot_task = asyncio.create_task(start_bot(DISCORD_BOT_TOKEN))
    stdin_task = asyncio.create_task(_watch_stdin(shutdown_event))
    log.info("Discord bot starting...")

    # Wait for shutdown signal
    shutdown_wait = asyncio.create_task(shutdown_event.wait())
    try:
        yield
    finally:
        # Shutdown triggered — clean up Discord client
        log.info("Shutting down Discord bot...")
        await client.close()
        bot_task.cancel()
        stdin_task.cancel()
        shutdown_wait.cancel()
        log.info("Discord bot shut down")


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
    reply_to: str | None = None,
) -> dict[str, str]:
    """Send a message to a Discord channel.

    Supports text, rich embeds, files, or any combination.
    Returns the message_id which can be used with edit_message
    for in-place updates.

    Args:
        channel_id: The Discord channel ID to send to.
        text: Message text (markdown supported).
        embed: Rich embed with title, description, color, fields.
        files: File paths or URLs to attach as files.
        reply_to: Message ID to reply to (creates a quote-reply thread).
    """
    return await send_discord_message_impl(
        client, channel_id, text, embed, files, reply_to,
    )


@mcp.tool()
async def edit_message(
    channel_id: str,
    message_id: str,
    text: str = "",
    embed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Edit a previously sent bot message.

    Edits don't trigger push notifications, so this is ideal for
    updating progress messages in-place without spamming the channel.

    Args:
        channel_id: The channel containing the message.
        message_id: The message ID to edit (from send_discord_message response).
        text: New message text.
        embed: New rich embed (replaces existing embed).
    """
    return await edit_message_impl(client, channel_id, message_id, text, embed)


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
async def fetch_messages(
    channel_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch recent messages from a Discord channel, oldest first.

    Returns messages with IDs, author info, content, timestamps,
    and attachment counts. This is the only lookback mechanism
    available (Discord search API is not exposed to bots).

    Args:
        channel_id: The channel to read from.
        limit: Number of messages to fetch (default 20, max 100).
    """
    return await fetch_messages_impl(client, channel_id, limit)


@mcp.tool()
async def get_channel_info(channel_id: str) -> dict[str, Any]:
    """Get detailed information about a Discord channel.

    Args:
        channel_id: The channel to inspect.
    """
    return await get_channel_info_impl(client, channel_id)


@mcp.tool()
async def create_poll(
    channel_id: str,
    question: str,
    answers: list[str],
    duration_hours: int = 1,
) -> dict[str, str]:
    """Create a poll in a Discord channel.

    Uses Discord's native poll feature. Good for helping Jeff
    decide what to focus on when he's scattered between projects.

    Args:
        channel_id: The channel to create the poll in.
        question: The poll question.
        answers: List of answer options (max 10).
        duration_hours: How long the poll runs (1-336 hours, default 1).
    """
    return await create_poll_impl(
        client, channel_id, question, answers, duration_hours,
    )


@mcp.tool()
async def create_scheduled_event(  # noqa: PLR0913
    guild_id: str,
    name: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
) -> dict[str, str]:
    """Create a scheduled event in a Discord server.

    Events appear in Discord's event list and users get native
    notifications. Use for deadlines, meetings, reviews.

    Args:
        guild_id: The server to create the event in.
        name: Event name.
        start_time: ISO 8601 start time (e.g. "2026-04-10T14:00:00").
        end_time: ISO 8601 end time.
        description: Event description with context.
        location: Event location (room, link, etc.).
    """
    return await create_scheduled_event_impl(
        client, guild_id, name, start_time, end_time, description, location,
    )


@mcp.tool()
async def list_scheduled_events(
    guild_id: str,
) -> list[dict[str, Any]]:
    """List all scheduled events in a Discord server.

    Args:
        guild_id: The server to list events from.
    """
    return await list_scheduled_events_impl(client, guild_id)


@mcp.tool()
async def cancel_scheduled_event(
    guild_id: str,
    event_id: str,
) -> dict[str, str]:
    """Cancel a scheduled event.

    Args:
        guild_id: The server containing the event.
        event_id: The event ID to cancel.
    """
    return await cancel_scheduled_event_impl(client, guild_id, event_id)


@mcp.tool()
async def create_thread(
    channel_id: str,
    name: str,
    message_id: str | None = None,
    auto_archive_minutes: int = 1440,
) -> dict[str, str]:
    """Create a thread in a Discord channel.

    Creates a public thread, optionally attached to a specific message.
    Use this to keep project discussions organized.

    Args:
        channel_id: The text channel to create the thread in.
        name: Thread name (e.g. "Redwing: No-Go Zones").
        message_id: Optional message ID to start the thread from.
        auto_archive_minutes: Inactivity before auto-archive (60, 1440, 4320, 10080).
    """
    return await create_thread_impl(
        client, channel_id, name, message_id, auto_archive_minutes,
    )


@mcp.tool()
async def send_briefing(
    channel_id: str,
    summary: str = "",
    embed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Send an interactive briefing with navigation buttons.

    Sends a summary embed with buttons for Tasks, Calendar,
    Priorities, and Projects. When Jeff taps a button, Pepper
    receives a prompt to expand that section.

    Args:
        channel_id: The channel to send the briefing to.
        summary: Brief summary text above the embed.
        embed: Rich embed with the briefing overview.
    """
    return await send_briefing_impl(
        client, channel_id, CHANNEL_URL, summary, embed,
    )


@mcp.tool()
async def download_attachments(
    channel_id: str,
    message_id: str,
) -> dict[str, Any]:
    """Download all attachments from a Discord message.

    Saves files to ~/.pepper/attachments/YYYY-MM-DD/ and returns
    local file paths and metadata. Use this when you need to
    inspect or process a file someone sent.

    Args:
        channel_id: The channel containing the message.
        message_id: The message with attachments to download.
    """
    return await download_attachments_impl(client, channel_id, message_id)


def run() -> None:
    """Entry point for pepper-discord command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
