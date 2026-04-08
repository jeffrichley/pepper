"""Pepper Discord bot — bridges Discord to the channel server.

Listens for messages in DMs and channels the bot is in.
Posts them to the channel server. Reads replies from the SSE stream
and sends them back to Discord.

This module is imported by mcp_server.py. Do not run directly.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import discord
import httpx

from .access import gate, load_access
from .chunking import smart_chunk
from .config import CHANNEL_URL
from .embeds import build_embed
from .slash_commands import setup_commands

# Type alias for channels that support send/fetch_message/typing/history
Messageable = (
    discord.TextChannel | discord.Thread | discord.VoiceChannel | discord.StageChannel
)

log = logging.getLogger("pepper-discord")

# --- Discord client setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

DISCORD_MSG_LIMIT = 2000
_MAX_EMOJI_LEN = 2
_MAX_RECENT_BOT_MESSAGES = 200

# Access control config (loaded on startup)
_access_config = load_access()

# Track recent message IDs sent by the bot (for reply-to detection)
_recent_bot_message_ids: set[int] = set()

# Track pending messages so we can hold typing indicators
# Stores (channel, timestamp) so we can expire stale entries
TYPING_TIMEOUT_SECONDS = 120  # 2 minutes max typing indicator
pending_chat_ids: dict[str, tuple[discord.abc.Messageable, float]] = {}


def make_chat_id(message: discord.Message) -> str:
    """Build a chat_id from a Discord message."""
    if message.guild:
        return f"discord-{message.guild.id}-{message.channel.id}-{message.id}"
    return f"discord-dm-{message.channel.id}-{message.id}"


# Set up slash commands
_command_tree = setup_commands(client, CHANNEL_URL, _access_config)


@client.event
async def on_ready() -> None:
    """Register with the channel server and sync slash commands on startup."""
    assert client.user is not None
    log.info(f"Logged in as {client.user} (id: {client.user.id})")

    # Sync slash commands with Discord
    try:
        synced = await _command_tree.sync()
        log.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        log.error(f"Failed to sync slash commands: {e}")

    # Register with channel server
    async with httpx.AsyncClient() as http:
        try:
            await http.post(
                f"{CHANNEL_URL}/register",
                json={
                    "source": "discord",
                    "description": f"Discord bot: {client.user.name}",
                },
            )
            log.info("Registered with channel server")
        except httpx.ConnectError:
            log.warning("Channel server not reachable — will retry on first message")


def _collect_attachments(message: discord.Message) -> tuple[str, list[dict[str, Any]]]:
    """Collect attachment metadata from a message without downloading."""
    content = message.content
    infos = []
    for att in message.attachments:
        infos.append(
            {
                "filename": att.filename,
                "url": att.url,
                "content_type": att.content_type or "unknown",
                "size_bytes": att.size,
            }
        )
        content += f"\n[📎 {att.filename}]"
    return content, infos


def _build_payload(
    message: discord.Message,
    chat_id: str,
    content: str,
    attachment_infos: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the channel server payload from a Discord message."""
    is_dm = message.guild is None
    metadata: dict[str, Any] = {
        "guild_id": str(message.guild.id) if message.guild else "",
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
        "is_dm": str(is_dm),
        "author_id": str(message.author.id),
    }
    if attachment_infos:
        metadata["attachments"] = json.dumps(attachment_infos)
    return {
        "source": "discord",
        "chat_id": chat_id,
        "sender": message.author.display_name,
        "content": content,
        "metadata": metadata,
    }


@client.event
async def on_message(message: discord.Message) -> None:
    """Forward Discord messages to the channel server."""
    if message.author == client.user or message.author.bot:
        return

    assert client.user is not None
    if not gate(message, client.user, _access_config, _recent_bot_message_ids):
        return

    ack_emoji = _access_config.get("ackReaction", "")
    if ack_emoji:
        with contextlib.suppress(Exception):
            await message.add_reaction(ack_emoji)

    chat_id = make_chat_id(message)
    content, attachment_infos = _collect_attachments(message)
    payload = _build_payload(message, chat_id, content, attachment_infos)

    # Track the channel for typing indicator (with timestamp for expiry)
    pending_chat_ids[chat_id] = (message.channel, time.monotonic())

    async with httpx.AsyncClient() as http:
        try:
            # Show typing while sending
            async with message.channel.typing():
                resp = await http.post(
                    f"{CHANNEL_URL}/message",
                    json=payload,
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    log.error(f"Channel server error: {resp.status_code} {resp.text}")
        except httpx.ConnectError:
            log.error("Channel server unreachable")
            await message.channel.send(
                "I'm having trouble connecting right now. Try again in a moment.",
            )


async def listen_for_replies() -> None:
    """Connect to the channel server SSE stream and relay replies to Discord."""
    backoff = 1.0
    max_backoff = 30.0

    while True:
        try:
            async with (
                httpx.AsyncClient(timeout=httpx.Timeout(None)) as http,
                http.stream("GET", f"{CHANNEL_URL}/events?source=discord") as resp,
            ):
                backoff = 1.0  # Reset on successful connection
                log.info("Connected to channel server SSE stream")

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    await handle_reply(data)

        except (httpx.ConnectError, httpx.ReadError) as e:
            log.warning(f"SSE connection lost: {e}. Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


def _parse_channel_id(chat_id: str) -> int | None:
    """Extract the channel ID from a chat_id string. Returns None on failure."""
    parts = chat_id.split("-")
    try:
        if parts[0] == "discord":
            return int(parts[2])
    except (IndexError, ValueError):
        pass
    log.warning(f"Could not parse chat_id: {chat_id}")
    return None


def _parse_original_message_id(chat_id: str) -> int | None:
    """Extract the original message ID from a chat_id string."""
    parts = chat_id.split("-")
    try:
        if parts[0] == "discord":
            return int(parts[3])
    except (IndexError, ValueError):
        pass
    return None


async def _resolve_channel(channel_id: int) -> Messageable | None:
    """Look up a messageable channel by ID, fetching from API if needed."""
    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            log.warning(f"Channel {channel_id} not found")
            return None
    if not isinstance(channel, Messageable):
        log.warning(f"Channel {channel_id} is not a messageable channel")
        return None
    return channel


async def _handle_reactions(
    channel: Messageable,
    original_message_id: int,
    reactions: list[str],
) -> None:
    """Add emoji reactions to the original Discord message."""
    try:
        original = await channel.fetch_message(original_message_id)
        for emoji_name in reactions:
            emoji = _resolve_emoji(emoji_name)
            if emoji:
                await original.add_reaction(emoji)
    except discord.NotFound:
        log.warning(
            f"Original message {original_message_id} not found for reactions",
        )


def _prepare_file_attachments(metadata: dict[str, Any]) -> list[discord.File]:
    """Build a list of discord.File objects from metadata attachments."""
    files: list[discord.File] = []
    outbound_attachments = metadata.get("attachments", [])
    if isinstance(outbound_attachments, str):
        try:
            outbound_attachments = json.loads(outbound_attachments)
        except json.JSONDecodeError:
            outbound_attachments = []
    for file_path in outbound_attachments:
        p = Path(file_path)
        if p.exists():
            files.append(discord.File(str(p), filename=p.name))
    return files


def _track_bot_message(message_id: int) -> None:
    """Track a bot message ID for reply-to detection, capping the set."""
    _recent_bot_message_ids.add(message_id)
    while len(_recent_bot_message_ids) > _MAX_RECENT_BOT_MESSAGES:
        _recent_bot_message_ids.pop()


async def _send_text_reply(
    channel: Messageable,
    text: str,
    embed: discord.Embed | None,
    files: list[discord.File],
) -> None:
    """Send a text reply, splitting at natural boundaries if needed."""
    send_files = files if files else None
    chunks = smart_chunk(text)

    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        msg = await channel.send(
            chunk,
            embed=embed if is_last else None,  # type: ignore[arg-type]
            files=send_files if is_last else None,  # type: ignore[arg-type]
        )
        _track_bot_message(msg.id)


async def _send_embed_or_files(
    channel: Messageable,
    embed: discord.Embed | None,
    files: list[discord.File],
) -> None:
    """Send an embed and/or file attachments without text content."""
    msg: discord.Message | None = None
    if embed and files:
        msg = await channel.send("", embed=embed, files=files)
    elif embed:
        msg = await channel.send(embed=embed)
    elif files:
        msg = await channel.send("", files=files)
    if msg is not None:
        _track_bot_message(msg.id)


async def handle_reply(data: dict[str, Any]) -> None:
    """Process a reply from the channel server and send it to Discord."""
    chat_id = data.get("chat_id", "")
    text = data.get("text", "")
    metadata: dict[str, Any] = data.get("metadata", {})

    channel_id = _parse_channel_id(chat_id)
    if channel_id is None:
        return

    channel = await _resolve_channel(channel_id)
    if channel is None:
        return

    # Remove from pending (stop typing indicator tracking)
    pending_chat_ids.pop(chat_id, None)

    # Handle reactions
    reply_type = metadata.get("type", "message")
    reactions: list[str] = metadata.get("reactions", [])
    original_message_id = _parse_original_message_id(chat_id)

    if reactions and original_message_id:
        await _handle_reactions(channel, original_message_id, reactions)

    if reply_type == "reaction":
        return

    embed = build_embed(metadata.get("embed"))
    files = _prepare_file_attachments(metadata)

    if text:
        await _send_text_reply(channel, text, embed, files)
    else:
        await _send_embed_or_files(channel, embed, files)


# Common emoji name -> unicode mapping
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


def _resolve_emoji(name: str) -> str | None:
    """Resolve an emoji name to a unicode character."""
    return EMOJI_MAP.get(name, name if len(name) <= _MAX_EMOJI_LEN else None)


async def keep_typing() -> None:
    """Refresh typing indicators for pending messages, with timeout expiry."""
    while True:
        await asyncio.sleep(8)  # Discord typing expires after 10s
        now = time.monotonic()
        for chat_id, (channel, started_at) in list(pending_chat_ids.items()):
            if now - started_at > TYPING_TIMEOUT_SECONDS:
                pending_chat_ids.pop(chat_id, None)
                log.info(f"Typing expired for {chat_id} (>{TYPING_TIMEOUT_SECONDS}s)")
                continue
            try:
                await channel.typing()
            except Exception:
                pending_chat_ids.pop(chat_id, None)


_CLEANUP_INTERVAL_SECONDS = 6 * 3600  # Every 6 hours


async def _periodic_attachment_cleanup() -> None:
    """Run attachment cleanup on startup and every 6 hours."""
    from pepper.attachments import cleanup_attachments

    while True:
        try:
            result = cleanup_attachments()
            total = result["deleted_age"] + result["deleted_size"]
            if total > 0:
                log.info(f"Attachment cleanup: {result}")
        except Exception as e:
            log.error(f"Attachment cleanup failed: {e}")
        await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)


async def start_bot(token: str) -> None:
    """Start the Discord bot as an async task.

    Call this from the MCP server lifespan. Uses client.start()
    which is the async version of client.run().
    """
    log.info("Starting Discord bot...")
    asyncio.create_task(listen_for_replies())
    asyncio.create_task(keep_typing())
    asyncio.create_task(_periodic_attachment_cleanup())
    await client.start(token)
