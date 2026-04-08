"""Discord MCP tool implementations.

These are the raw async functions. The MCP tool decorators
are in mcp_server.py which calls these.
"""

from __future__ import annotations

import logging
import pathlib
import tempfile
from typing import Any

import discord
import httpx

from .chunking import smart_chunk
from .embeds import build_embed
from .views import BriefingView

# Type alias for channels that support send/fetch_message/typing/history
Messageable = (
    discord.TextChannel | discord.Thread | discord.VoiceChannel | discord.StageChannel
)

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


async def _get_messageable(
    client: discord.Client,
    channel_id: str,
) -> Messageable | None:
    """Resolve a channel ID to a messageable channel, or None."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return None
    if not isinstance(channel, Messageable):
        return None
    return channel


async def _prepare_files(
    file_paths: list[str] | None,
) -> list[discord.File]:
    """Convert file paths and URLs to discord.File objects."""
    if not file_paths:
        return []

    files: list[discord.File] = []
    for path_or_url in file_paths:
        if path_or_url.startswith(("http://", "https://")):
            file = await _download_url_to_file(path_or_url)
            if file:
                files.append(file)
        else:
            p = pathlib.Path(path_or_url)
            if p.exists():
                files.append(discord.File(str(p), filename=p.name))
    return files


async def _download_url_to_file(
    url: str,
) -> discord.File | None:
    """Download a URL to a temp file and return a discord.File."""
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                url,
                timeout=30.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            name = url.rsplit("/", maxsplit=1)[-1].split("?", maxsplit=1)[0]
            filename = name or "file"
            path = tempfile.mktemp(suffix=f"_{filename}")
            pathlib.Path(path).write_bytes(resp.content)
            return discord.File(path, filename=filename)
    except Exception:
        return None


async def send_discord_message_impl(  # noqa: PLR0913
    client: discord.Client,
    channel_id: str,
    text: str = "",
    embed: dict[str, Any] | None = None,
    files: list[str] | None = None,
    reply_to: str | None = None,
) -> dict[str, str]:
    """Send a message to a Discord channel with optional file attachments."""
    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return {"status": "error", "message": f"Channel {channel_id} not found"}

    discord_embed = build_embed(embed)
    discord_files = await _prepare_files(files)

    # Build message reference for reply threading
    reference = None
    if reply_to:
        reference = discord.MessageReference(
            message_id=int(reply_to),
            channel_id=int(channel_id),
            fail_if_not_exists=False,
        )

    sent_message: discord.Message | None = None
    if text:
        chunks = smart_chunk(text)
        for i, chunk in enumerate(chunks):
            is_first = i == 0
            is_last = i == len(chunks) - 1
            sent_message = await channel.send(  # type: ignore[arg-type]
                chunk,
                embed=discord_embed if is_last else None,
                files=discord_files if is_first else None,
                reference=reference if is_first else None,
            )
    elif discord_embed or discord_files:
        sent_message = await channel.send(  # type: ignore[arg-type]
            embed=discord_embed,
            files=discord_files or None,
            reference=reference,
        )
    else:
        return {
            "status": "error",
            "message": "Either text, embed, or files is required",
        }

    result: dict[str, str] = {"status": "sent", "channel_id": channel_id}
    if sent_message is not None:
        result["message_id"] = str(sent_message.id)
    return result


async def edit_message_impl(
    client: discord.Client,
    channel_id: str,
    message_id: str,
    text: str = "",
    embed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Edit a previously sent bot message.

    Only works on messages the bot itself sent (Discord enforces this).
    Edits don't trigger push notifications.
    """
    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return {"status": "error", "message": f"Channel {channel_id} not found"}

    try:
        message = await channel.fetch_message(int(message_id))
    except discord.NotFound:
        return {"status": "error", "message": f"Message {message_id} not found"}

    if message.author != client.user:
        return {"status": "error", "message": "Can only edit bot's own messages"}

    discord_embed = build_embed(embed)
    await message.edit(content=text or None, embed=discord_embed)  # type: ignore[arg-type]
    return {"status": "edited", "message_id": message_id}


async def add_reaction_impl(
    client: discord.Client,
    channel_id: str,
    message_id: str,
    emoji: str,
) -> dict[str, str]:
    """Add a reaction to a Discord message."""
    channel = await _get_messageable(client, channel_id)
    if channel is None:
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
    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return {"status": "error", "message": f"Channel {channel_id} not found"}

    await channel.typing()
    return {"status": "typing", "channel_id": channel_id}


async def list_channels_impl(
    client: discord.Client,
    guild_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all text and forum channels the bot can see."""
    channels: list[dict[str, Any]] = []
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


async def fetch_messages_impl(
    client: discord.Client,
    channel_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Fetch recent messages from a Discord channel, oldest first.

    Returns up to `limit` messages (max 100 per Discord API).
    Each message includes ID, author, content, timestamp, and attachment count.
    """
    limit = min(limit, 100)
    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return []

    messages = [
        {
            "id": str(msg.id),
            "author": msg.author.display_name,
            "is_bot": msg.author.bot,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
            "attachments": len(msg.attachments),
        }
        async for msg in channel.history(limit=limit)
    ]
    messages.reverse()  # Oldest first
    return messages


async def get_channel_info_impl(
    client: discord.Client,
    channel_id: str,
) -> dict[str, Any]:
    """Get detailed information about a Discord channel."""
    raw_channel = client.get_channel(int(channel_id))
    if raw_channel is None:
        try:
            raw_channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"error": f"Channel {channel_id} not found"}

    info: dict[str, Any] = {
        "id": str(raw_channel.id),
        "name": getattr(raw_channel, "name", "DM"),
        "type": str(getattr(raw_channel, "type", "unknown")),
        "topic": getattr(raw_channel, "topic", None) or "",
    }
    guild = getattr(raw_channel, "guild", None)
    if guild is not None:
        info["guild_id"] = str(guild.id)
        info["guild_name"] = guild.name
        info["member_count"] = guild.member_count
    return info


async def send_briefing_impl(
    client: discord.Client,
    channel_id: str,
    channel_url: str,
    summary: str = "",
    embed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Send an interactive briefing with navigation buttons.

    The briefing includes a summary embed and buttons for
    Tasks, Calendar, Priorities, and Projects. Button presses
    send prompts to the channel server for Pepper to handle.
    """
    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return {"status": "error", "message": f"Channel {channel_id} not found"}

    discord_embed = build_embed(embed)
    view = BriefingView(channel_url, channel_id)

    msg = await channel.send(
        summary,
        embed=discord_embed,  # type: ignore[arg-type]
        view=view,
    )
    return {"status": "sent", "message_id": str(msg.id)}
