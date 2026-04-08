"""Discord access control — DM policy, guild channel opt-in, allowlists.

Loads access configuration from ~/.pepper/discord/access.json.
Provides a gate function to check whether a message should be processed.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import discord

log = logging.getLogger("pepper-discord")

DEFAULT_ACCESS_PATH = Path.home() / ".pepper" / "discord" / "access.json"

# Default config: only Jeff can DM, no guild channels enabled
DEFAULT_ACCESS: dict[str, Any] = {
    "dmPolicy": "allowlist",
    "allowFrom": [],
    "mentionPatterns": [],
    "channels": {},
}


def load_access(path: Path | None = None) -> dict[str, Any]:
    """Load access config from JSON file, returning defaults if missing."""
    access_path = path or DEFAULT_ACCESS_PATH
    if not access_path.exists():
        return dict(DEFAULT_ACCESS)
    try:
        data = json.loads(access_path.read_text(encoding="utf-8"))
        # Merge with defaults so missing keys don't crash
        return {**DEFAULT_ACCESS, **data}
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Failed to load access.json: {e}, using defaults")
        return dict(DEFAULT_ACCESS)


def save_access(config: dict[str, Any], path: Path | None = None) -> None:
    """Save access config to JSON file."""
    access_path = path or DEFAULT_ACCESS_PATH
    access_path.parent.mkdir(parents=True, exist_ok=True)
    access_path.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )


def _check_dm_access(
    config: dict[str, Any],
    author_id: str,
) -> bool:
    """Check whether a DM should be processed based on DM policy."""
    policy = config.get("dmPolicy", "allowlist")

    if policy == "disabled":
        return False

    if policy == "allowlist":
        allow_from = config.get("allowFrom", [])
        return author_id in allow_from

    # "open" policy — accept all DMs
    return True


def _check_guild_access(
    config: dict[str, Any],
    channel_id: str,
    author_id: str,
) -> bool:
    """Check whether a guild message passes channel-level access control."""
    channels = config.get("channels", {})
    channel_config = channels.get(channel_id)

    if channel_config is None:
        # Channel not configured — not opted in
        return False

    # Check allowFrom if specified for this channel
    allow_from = channel_config.get("allowFrom", [])
    return not (allow_from and author_id not in allow_from)


def _is_mentioned(
    message: discord.Message,
    bot_user: discord.User | discord.ClientUser,
    config: dict[str, Any],
    recent_bot_message_ids: set[int],
) -> bool:
    """Check if the bot is being addressed in a guild message.

    Returns True if:
    - Bot is @mentioned
    - Message is a reply to one of the bot's recent messages
    - Message matches a custom mention pattern
    """
    # Direct @mention
    if bot_user in message.mentions:
        return True

    # Reply to bot's message
    if (
        message.reference
        and message.reference.message_id
        and message.reference.message_id in recent_bot_message_ids
    ):
        return True

    # Custom regex patterns
    patterns = config.get("mentionPatterns", [])
    for pattern in patterns:
        if re.search(pattern, message.content, re.IGNORECASE):
            return True

    return False


def is_outbound_allowed(
    config: dict[str, Any],
    channel_id: str,
) -> bool:
    """Check if sending to a channel is allowed.

    Returns True for channels in the config's channels list,
    or if no channels are configured (open mode).
    """
    channels = config.get("channels", {})
    # If no channels configured, allow all (open mode)
    if not channels:
        return True
    return channel_id in channels


def gate(
    message: discord.Message,
    bot_user: discord.User | discord.ClientUser,
    config: dict[str, Any],
    recent_bot_message_ids: set[int],
) -> bool:
    """Check whether a message should be processed.

    Returns True if the message passes all access checks.
    """
    author_id = str(message.author.id)
    is_dm = message.guild is None

    if is_dm:
        return _check_dm_access(config, author_id)

    # Guild message — check channel access first
    channel_id = str(message.channel.id)
    if not _check_guild_access(config, channel_id, author_id):
        return False

    # Check if mention is required for this channel
    channels = config.get("channels", {})
    channel_config = channels.get(channel_id, {})
    require_mention = channel_config.get("requireMention", True)

    if require_mention:
        return _is_mentioned(message, bot_user, config, recent_bot_message_ids)

    return True
