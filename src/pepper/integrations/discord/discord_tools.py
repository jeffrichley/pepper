"""Discord MCP tool implementations.

These are the raw async functions. The MCP tool decorators
are in mcp_server.py which calls these.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from .embeds import build_embed

log = logging.getLogger("pepper-discord")

EMOJI_MAP = {
    "thumbs_up": "\U0001f44d",
    "thumbs_down": "\U0001f44e",
    "eyes": "\U0001f440",
    "fire": "\U0001f525",
    "heart": "\u2764\ufe0f",
    "check": "\u2705",
    "white_check_mark": "\u2705",
    "x": "\u274c",
    "warning": "\u26a0\ufe0f",
    "rocket": "\U0001f680",
    "thinking": "\U0001f914",
    "wave": "\U0001f44b",
    "star": "\u2b50",
    "bulb": "\U0001f4a1",
    "memo": "\U0001f4dd",
    "clock": "\U0001f570\ufe0f",
    "pin": "\U0001f4cc",
}


_MAX_EMOJI_LEN = 2


def _resolve_emoji(name: str) -> str | None:
    return EMOJI_MAP.get(name, name if len(name) <= _MAX_EMOJI_LEN else None)


DISCORD_MSG_LIMIT = 2000


async def send_discord_message_impl(
    client: discord.Client,
    channel_id: str,
    text: str = "",
    embed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Send a message to a Discord channel."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"status": "error", "message": f"Channel {channel_id} not found"}

    discord_embed = build_embed(embed)

    if text and len(text) > DISCORD_MSG_LIMIT:
        for i in range(0, len(text), DISCORD_MSG_LIMIT):
            chunk = text[i : i + DISCORD_MSG_LIMIT]
            chunk_embed = discord_embed if i + DISCORD_MSG_LIMIT >= len(text) else None
            await channel.send(chunk, embed=chunk_embed)
    elif text:
        await channel.send(text, embed=discord_embed)
    elif discord_embed:
        await channel.send(embed=discord_embed)
    else:
        return {"status": "error", "message": "Either text or embed is required"}

    return {"status": "sent", "channel_id": channel_id}


async def add_reaction_impl(
    client: discord.Client,
    channel_id: str,
    message_id: str,
    emoji: str,
) -> dict[str, str]:
    """Add a reaction to a Discord message."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"status": "error", "message": f"Channel {channel_id} not found"}

    try:
        message = await channel.fetch_message(int(message_id))
    except Exception:
        return {"status": "error", "message": f"Message {message_id} not found"}

    resolved = _resolve_emoji(emoji)
    if not resolved:
        return {"status": "error", "message": f"Unknown emoji: {emoji}"}

    await message.add_reaction(resolved)
    return {"status": "reacted", "emoji": emoji}


async def send_typing_impl(
    client: discord.Client,
    channel_id: str,
) -> dict[str, str]:
    """Show typing indicator in a Discord channel."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"status": "error", "message": f"Channel {channel_id} not found"}

    await channel.typing()
    return {"status": "typing", "channel_id": channel_id}


async def list_channels_impl(
    client: discord.Client,
    guild_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all text and forum channels the bot can see."""
    channels = []
    for guild in client.guilds:
        if guild_id and str(guild.id) != guild_id:
            continue
        channels.extend(
            {
                "id": str(channel.id),
                "name": channel.name,
                "type": str(channel.type),
                "topic": getattr(channel, "topic", None) or "",
                "guild_id": str(guild.id),
                "guild_name": guild.name,
            }
            for channel in guild.channels
            if isinstance(channel, (discord.TextChannel, discord.ForumChannel))
        )
    return channels


async def get_recent_messages_impl(
    client: discord.Client,
    channel_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent messages from a Discord channel."""
    limit = min(limit, 50)
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return []

    return [
        {
            "id": str(msg.id),
            "author": msg.author.display_name,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
        }
        async for msg in channel.history(limit=limit)
    ]


async def get_channel_info_impl(
    client: discord.Client,
    channel_id: str,
) -> dict[str, Any]:
    """Get detailed information about a Discord channel."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"error": f"Channel {channel_id} not found"}

    info = {
        "id": str(channel.id),
        "name": getattr(channel, "name", "DM"),
        "type": str(channel.type),
        "topic": getattr(channel, "topic", None) or "",
    }
    if hasattr(channel, "guild") and channel.guild:
        info["guild_id"] = str(channel.guild.id)
        info["guild_name"] = channel.guild.name
        info["member_count"] = channel.guild.member_count
    return info
