"""Pepper Discord MCP Server.

Entry point spawned by Claude Code via .mcp.json.
Runs the Discord bot in one process.
Exposes Discord tools via MCP over stdio.
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
from .bot import client, start_bot  # noqa: E402
from .config import DISCORD_BOT_TOKEN  # noqa: E402
from .discord_tools import (  # noqa: E402
    add_reaction_impl,
    edit_message_impl,
    fetch_messages_impl,
    get_channel_info_impl,
    list_channels_impl,
    send_discord_message_impl,
    send_typing_impl,
)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:  # noqa: ARG001
    """Start Discord bot on MCP server startup."""
    log.info("Starting Pepper Discord integration...")

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
    Returns the message_id which can be used with edit_message
    for in-place updates.

    Args:
        channel_id: The Discord channel ID to send to.
        text: Message text (markdown supported).
        embed: Rich embed with title, description, color, fields.
        files: File paths or URLs to attach as files.
    """
    return await send_discord_message_impl(client, channel_id, text, embed, files)


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


def run() -> None:
    """Entry point for pepper-discord command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
