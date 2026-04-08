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

from pepper.attachments import download_attachment

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
DISCORD_FILE_SIZE_LIMIT = 25 * 1024 * 1024  # 25MB
DISCORD_MAX_FILES = 10
_BLOCKED_DIRS = [
    str(pathlib.Path.home() / ".pepper" / "discord"),
    str(pathlib.Path.home() / ".pepper" / ".claude"),
    str(pathlib.Path.home() / ".pepper" / ".env"),
]


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


def _validate_file_path(path: pathlib.Path) -> str | None:
    """Validate a file path for sending. Returns error message or None."""
    real = str(path.resolve())
    for blocked in _BLOCKED_DIRS:
        if real.startswith(blocked):
            return f"Blocked: {path.name} is in a protected directory"
    if path.stat().st_size > DISCORD_FILE_SIZE_LIMIT:
        return f"Too large: {path.name} exceeds 25MB"
    return None


async def _prepare_files(
    file_paths: list[str] | None,
) -> list[discord.File]:
    """Convert file paths and URLs to discord.File objects.

    Validates paths against security rules and enforces limits.
    """
    if not file_paths:
        return []

    files: list[discord.File] = []
    for path_or_url in file_paths[:DISCORD_MAX_FILES]:
        if path_or_url.startswith(("http://", "https://")):
            file = await _download_url_to_file(path_or_url)
            if file:
                files.append(file)
        else:
            p = pathlib.Path(path_or_url)
            if p.exists():
                error = _validate_file_path(p)
                if error:
                    log.warning(f"File rejected: {error}")
                    continue
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


async def create_scheduled_event_impl(  # noqa: PLR0913
    client: discord.Client,
    guild_id: str,
    name: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
) -> dict[str, str]:
    """Create a scheduled event in a Discord guild.

    Uses external entity type (not voice channel). Start and end times
    are ISO 8601 strings.
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    guild = client.get_guild(int(guild_id))
    if guild is None:
        return {"status": "error", "message": f"Guild {guild_id} not found"}

    try:
        start = datetime.fromisoformat(start_time).replace(tzinfo=UTC)
        end = datetime.fromisoformat(end_time).replace(tzinfo=UTC)
    except ValueError as e:
        return {"status": "error", "message": f"Invalid datetime: {e}"}

    event = await guild.create_scheduled_event(
        name=name,
        start_time=start,
        end_time=end,
        entity_type=discord.EntityType.external,
        privacy_level=discord.PrivacyLevel.guild_only,
        location=location or "TBD",
        description=description,
    )
    return {
        "status": "created",
        "event_id": str(event.id),
        "name": event.name,
    }


async def list_scheduled_events_impl(
    client: discord.Client,
    guild_id: str,
) -> list[dict[str, Any]]:
    """List all scheduled events in a guild."""
    guild = client.get_guild(int(guild_id))
    if guild is None:
        return []

    events = await guild.fetch_scheduled_events()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "start_time": e.start_time.isoformat() if e.start_time else None,
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "description": e.description or "",
            "location": e.location or "",
            "status": e.status.name,
        }
        for e in events
    ]


async def cancel_scheduled_event_impl(
    client: discord.Client,
    guild_id: str,
    event_id: str,
) -> dict[str, str]:
    """Cancel (delete) a scheduled event."""
    guild = client.get_guild(int(guild_id))
    if guild is None:
        return {"status": "error", "message": f"Guild {guild_id} not found"}

    try:
        event = await guild.fetch_scheduled_event(int(event_id))
        await event.delete()
        return {"status": "cancelled", "event_id": event_id}
    except discord.NotFound:
        return {"status": "error", "message": f"Event {event_id} not found"}


async def create_poll_impl(
    client: discord.Client,
    channel_id: str,
    question: str,
    answers: list[str],
    duration_hours: int = 1,
) -> dict[str, str]:
    """Create a poll in a Discord channel.

    Uses Discord's native poll feature. Results are visible to all.
    """
    from datetime import timedelta  # noqa: PLC0415

    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return {"status": "error", "message": f"Channel {channel_id} not found"}

    duration_hours = max(1, min(duration_hours, 336))  # 1h to 14 days

    poll = discord.Poll(
        question=question,
        duration=timedelta(hours=duration_hours),
    )
    for answer_text in answers[:10]:  # Discord allows max 10 answers
        poll.add_answer(text=answer_text)

    msg = await channel.send(poll=poll)
    return {"status": "sent", "message_id": str(msg.id)}


async def create_thread_impl(
    client: discord.Client,
    channel_id: str,
    name: str,
    message_id: str | None = None,
    auto_archive_minutes: int = 1440,
) -> dict[str, str]:
    """Create a thread in a Discord channel.

    Can create a thread from a specific message or as a standalone thread.
    Auto-archives after the specified inactivity period.
    """
    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return {"status": "error", "message": f"Channel {channel_id} not found"}

    if not isinstance(channel, discord.TextChannel):
        return {
            "status": "error",
            "message": "Threads can only be created in text channels",
        }

    # Clamp to Discord's allowed values: 60, 1440, 4320, 10080
    allowed = [60, 1440, 4320, 10080]
    archive = min(allowed, key=lambda x: abs(x - auto_archive_minutes))

    if message_id:
        try:
            message = await channel.fetch_message(int(message_id))
            thread = await message.create_thread(
                name=name,
                auto_archive_duration=archive,
            )
        except discord.NotFound:
            return {"status": "error", "message": f"Message {message_id} not found"}
    else:
        thread = await channel.create_thread(
            name=name,
            auto_archive_duration=archive,
            type=discord.ChannelType.public_thread,
        )

    return {
        "status": "created",
        "thread_id": str(thread.id),
        "name": thread.name,
    }


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


async def download_attachments_impl(
    client: discord.Client,
    channel_id: str,
    message_id: str,
) -> dict[str, Any]:
    """Download all attachments from a Discord message.

    Saves files to ~/.pepper/attachments/YYYY-MM-DD/ and returns
    paths and metadata.
    """
    channel = await _get_messageable(client, channel_id)
    if channel is None:
        return {"status": "error", "message": f"Channel {channel_id} not found"}

    try:
        message = await channel.fetch_message(int(message_id))
    except discord.NotFound:
        return {"status": "error", "message": f"Message {message_id} not found"}

    if not message.attachments:
        return {"status": "ok", "message": "No attachments", "files": []}

    downloaded: list[dict[str, Any]] = []
    for att in message.attachments:
        local_path = await download_attachment(
            url=att.url,
            filename=att.filename,
            message_id=message_id,
        )
        if local_path:
            downloaded.append({
                "filename": att.filename,
                "path": str(local_path),
                "content_type": att.content_type or "unknown",
                "size_bytes": local_path.stat().st_size,
            })

    return {
        "status": "ok",
        "message": f"Downloaded {len(downloaded)} attachment(s)",
        "files": downloaded,
    }
