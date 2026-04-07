"""Pepper Discord bot — bridges Discord to the channel server.

Listens for messages in DMs and channels the bot is in.
Posts them to the channel server. Reads replies from the SSE stream
and sends them back to Discord.

This module is imported by mcp_server.py. Do not run directly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import discord
import httpx

from pepper.attachments import download_attachment

from .config import CHANNEL_URL
from .embeds import build_embed

log = logging.getLogger("pepper-discord")

# --- Discord client setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

DISCORD_MSG_LIMIT = 2000
_MAX_EMOJI_LEN = 2

# Track pending messages so we can hold typing indicators
pending_chat_ids: dict[str, discord.abc.Messageable] = {}


def make_chat_id(message: discord.Message) -> str:
    """Build a chat_id from a Discord message."""
    if message.guild:
        return f"discord-{message.guild.id}-{message.channel.id}-{message.id}"
    return f"discord-dm-{message.channel.id}-{message.id}"


@client.event
async def on_ready():
    """Register with the channel server on startup."""
    log.info(f"Logged in as {client.user} (id: {client.user.id})")
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


@client.event
async def on_message(message: discord.Message):
    """Forward Discord messages to the channel server."""
    # Ignore our own messages
    if message.author == client.user:
        return

    # Ignore bot messages
    if message.author.bot:
        return

    chat_id = make_chat_id(message)
    is_dm = message.guild is None

    # Download attachments and build content/metadata
    content = message.content
    attachment_infos = []
    for att in message.attachments:
        local_path = await download_attachment(
            url=att.url,
            filename=att.filename,
            message_id=str(message.id),
        )
        if local_path:
            attachment_infos.append(
                {
                    "filename": att.filename,
                    "content_type": att.content_type or "unknown",
                    "path": str(local_path),
                    "size_bytes": local_path.stat().st_size,
                }
            )
            content += f"\n[📎 {att.filename}]"

    metadata = {
        "guild_id": str(message.guild.id) if message.guild else "",
        "channel_id": str(message.channel.id),
        "message_id": str(message.id),
        "is_dm": str(is_dm),
        "author_id": str(message.author.id),
    }
    if attachment_infos:
        metadata["attachments"] = json.dumps(attachment_infos)

    payload = {
        "source": "discord",
        "chat_id": chat_id,
        "sender": message.author.display_name,
        "content": content,
        "metadata": metadata,
    }

    # Track the channel for typing indicator
    pending_chat_ids[chat_id] = message.channel

    async with httpx.AsyncClient() as http:
        try:
            # Show typing while sending
            async with message.channel.typing():
                resp = await http.post(
                    f"{CHANNEL_URL}/message",
                    json=payload,
                    timeout=10.0,
                )
                if resp.status_code != 200:  # noqa: PLR2004
                    log.error(f"Channel server error: {resp.status_code} {resp.text}")
        except httpx.ConnectError:
            log.error("Channel server unreachable")
            await message.channel.send(
                "I'm having trouble connecting right now. Try again in a moment.",
            )


async def listen_for_replies():
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


async def handle_reply(data: dict[str, Any]):  # noqa: C901, PLR0912, PLR0915
    """Process a reply from the channel server and send it to Discord."""
    chat_id = data.get("chat_id", "")
    text = data.get("text", "")
    metadata = data.get("metadata", {})

    # Parse chat_id to find the channel
    parts = chat_id.split("-")
    try:
        if (parts[0] == "discord" and parts[1] == "dm") or parts[0] == "discord":
            channel_id = int(parts[2])
        else:
            log.warning(f"Unknown chat_id format: {chat_id}")
            return
    except (IndexError, ValueError):
        log.warning(f"Could not parse chat_id: {chat_id}")
        return

    channel = client.get_channel(channel_id)
    if channel is None:
        # Try fetching it (might be a DM channel not in cache)
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            log.warning(f"Channel {channel_id} not found")
            return

    # Remove from pending (stop typing indicator tracking)
    pending_chat_ids.pop(chat_id, None)

    # Handle reactions
    reply_type = metadata.get("type", "message")
    reactions = metadata.get("reactions", [])

    # Try to find the original message for reactions
    original_message_id = None
    try:
        if (parts[0] == "discord" and parts[1] == "dm") or parts[0] == "discord":
            original_message_id = int(parts[3])
    except (IndexError, ValueError):
        pass

    if reactions and original_message_id:
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

    # If reaction-only, we're done
    if reply_type == "reaction":
        return

    # Build and send the reply
    embed_data = metadata.get("embed")
    embed = build_embed(embed_data)

    # Prepare outbound file attachments
    files = []
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

    if text:
        # Discord has a 2000 char limit per message
        if len(text) <= DISCORD_MSG_LIMIT:
            await channel.send(text, embed=embed, files=files or None)
        else:
            # Split into chunks, attach files to last chunk
            chunks = [
                text[i : i + DISCORD_MSG_LIMIT]
                for i in range(0, len(text), DISCORD_MSG_LIMIT)
            ]
            for i, chunk in enumerate(chunks):
                is_last = i == len(chunks) - 1
                await channel.send(
                    chunk,
                    embed=embed if is_last else None,
                    files=files if is_last else None,
                )
    elif embed or files:
        await channel.send(text="" if files else None, embed=embed, files=files or None)


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


async def keep_typing():
    """Refresh typing indicators for pending messages."""
    while True:
        await asyncio.sleep(8)  # Discord typing expires after 10s
        for chat_id, channel in list(pending_chat_ids.items()):
            try:
                await channel.typing()
            except Exception:
                pending_chat_ids.pop(chat_id, None)


async def start_bot(token: str):
    """Start the Discord bot as an async task.

    Call this from the MCP server lifespan. Uses client.start()
    which is the async version of client.run().
    """
    log.info("Starting Discord bot...")
    asyncio.create_task(listen_for_replies())  # noqa: RUF006
    asyncio.create_task(keep_typing())  # noqa: RUF006
    await client.start(token)
