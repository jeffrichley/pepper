"""Discord slash commands for quick access to Pepper.

Commands send prompts to the channel server. Pepper handles the
actual response — these are just structured entry points.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import discord
from discord import app_commands

from .access import load_access

log = logging.getLogger("pepper-discord")


def setup_commands(
    client: discord.Client,
    channel_url: str,
) -> app_commands.CommandTree:
    """Register slash commands on the client and return the CommandTree."""
    tree = app_commands.CommandTree(client)

    @tree.command(name="brief", description="Get your morning briefing")
    async def brief(interaction: discord.Interaction) -> None:
        if not _check_access(interaction):
            await interaction.response.send_message(
                "You don't have access to Pepper.", ephemeral=True,
            )
            return
        await interaction.response.defer()
        await _send_prompt(
            channel_url,
            interaction,
            "Morning briefing for Jeff. Check project statuses, scan for "
            "upcoming deadlines this week, summarize yesterday's activity, "
            "and list today's priorities. Send the briefing to this channel "
            "using send_discord_message with a rich embed.",
        )

    @tree.command(name="tasks", description="Show current task list")
    async def tasks(interaction: discord.Interaction) -> None:
        if not _check_access(interaction):
            await interaction.response.send_message(
                "You don't have access to Pepper.", ephemeral=True,
            )
            return
        await interaction.response.defer()
        await _send_prompt(
            channel_url,
            interaction,
            "Show Jeff's current task list from Memory/TASKS.md. "
            "Send it to this channel using send_discord_message with "
            "a rich embed. Group by project.",
        )

    @tree.command(name="focus", description="Show today's recommended focus")
    async def focus(interaction: discord.Interaction) -> None:
        if not _check_access(interaction):
            await interaction.response.send_message(
                "You don't have access to Pepper.", ephemeral=True,
            )
            return
        await interaction.response.defer()
        await _send_prompt(
            channel_url,
            interaction,
            "What should Jeff focus on today? Check TASKS.md, calendar, "
            "and recent activity. Recommend the top 1-3 priorities. "
            "Send to this channel using send_discord_message.",
        )

    @tree.command(
        name="status",
        description="Show project status",
    )
    @app_commands.describe(project="Project name")
    async def status(
        interaction: discord.Interaction,
        project: str,
    ) -> None:
        if not _check_access(interaction):
            await interaction.response.send_message(
                "You don't have access to Pepper.", ephemeral=True,
            )
            return
        await interaction.response.defer()
        await _send_prompt(
            channel_url,
            interaction,
            f"Show the status of the {project} project. Check Memory/ "
            f"for any files related to {project}. Include: current status, "
            f"recent activity, blockers, and next steps. Send to this "
            f"channel using send_discord_message with a rich embed.",
        )

    return tree


def _check_access(interaction: discord.Interaction) -> bool:
    """Check if the interaction user has access via the access config."""
    config = load_access()
    author_id = str(interaction.user.id)
    allow_from = config.get("allowFrom", [])
    # If allowFrom is empty, allow all. Otherwise check membership.
    return not allow_from or author_id in allow_from


async def _send_prompt(
    channel_url: str,
    interaction: discord.Interaction,
    prompt: str,
) -> None:
    """Send a prompt to the channel server on behalf of a slash command."""
    import httpx  # noqa: PLC0415  # deferred to avoid import at module level

    chat_id = (
        f"discord-{interaction.guild_id or 'dm'}"
        f"-{interaction.channel_id}"
        f"-slash-{int(time.time())}"
    )

    metadata: dict[str, Any] = {
        "guild_id": str(interaction.guild_id or ""),
        "channel_id": str(interaction.channel_id),
        "is_dm": str(interaction.guild is None),
        "author_id": str(interaction.user.id),
        "source": "slash_command",
    }

    payload = {
        "source": "discord",
        "chat_id": chat_id,
        "sender": interaction.user.display_name,
        "content": prompt,
        "metadata": metadata,
    }

    async with httpx.AsyncClient() as http:
        try:
            resp = await http.post(
                f"{channel_url}/message",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code != 200:  # noqa: PLR2004
                log.error(
                    f"Slash command failed: {resp.status_code} {resp.text}",
                )
                await interaction.followup.send(
                    "Something went wrong. Try again.",
                )
        except httpx.ConnectError:
            log.error("Channel server unreachable for slash command")
            await interaction.followup.send(
                "I can't reach the channel server right now.",
            )
