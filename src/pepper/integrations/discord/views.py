"""Discord UI views — interactive buttons and components.

Views are attached to messages and provide button callbacks.
Button presses send prompts to the channel server for Pepper to handle.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import discord
from discord import ui

log = logging.getLogger("pepper-discord")

BRIEFING_TIMEOUT_SECONDS = 300  # 5 minutes


class BriefingView(ui.View):
    """Morning briefing dashboard with navigation buttons.

    Each button sends a prompt to the channel server asking
    Pepper to expand that section.
    """

    def __init__(self, channel_url: str, channel_id: str) -> None:
        """Initialize the briefing view with channel server URL and target channel."""
        super().__init__(timeout=BRIEFING_TIMEOUT_SECONDS)
        self.channel_url = channel_url
        self.channel_id = channel_id

    @ui.button(label="Tasks", emoji="\U0001f4cb", style=discord.ButtonStyle.primary)
    async def tasks_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button[BriefingView],
    ) -> None:
        """Expand the tasks section."""
        await self._handle_button(
            interaction,
            "Show Jeff's full task list from Memory/TASKS.md. Group by "
            "project. Send to this channel using send_discord_message "
            "with a rich embed.",
        )

    @ui.button(
        label="Calendar",
        emoji="\U0001f4c5",
        style=discord.ButtonStyle.primary,
    )
    async def calendar_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button[BriefingView],
    ) -> None:
        """Expand the calendar section."""
        await self._handle_button(
            interaction,
            "Show today's calendar events and upcoming deadlines this week. "
            "Use gog calendar to check. Send to this channel using "
            "send_discord_message with a rich embed.",
        )

    @ui.button(
        label="Priorities",
        emoji="\U0001f525",
        style=discord.ButtonStyle.primary,
    )
    async def priorities_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button[BriefingView],
    ) -> None:
        """Expand the priorities section."""
        await self._handle_button(
            interaction,
            "What should Jeff focus on today? Check TASKS.md and recent "
            "activity. Rank the top 3 priorities with reasoning. Send to "
            "this channel using send_discord_message with a rich embed.",
        )

    @ui.button(
        label="Projects",
        emoji="\U0001f4ca",
        style=discord.ButtonStyle.primary,
    )
    async def projects_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button[BriefingView],
    ) -> None:
        """Expand the projects section."""
        await self._handle_button(
            interaction,
            "Show a status summary for all active projects. Check Memory/ "
            "for project files. Include: status, recent activity, blockers. "
            "Send to this channel using send_discord_message with a rich embed.",
        )

    async def _handle_button(
        self,
        interaction: discord.Interaction,
        prompt: str,
    ) -> None:
        """Send a prompt to the channel server when a button is pressed."""
        await interaction.response.defer()
        await _post_prompt(
            self.channel_url,
            self.channel_id,
            interaction.user,
            prompt,
        )


async def _post_prompt(
    channel_url: str,
    channel_id: str,
    user: discord.User | discord.Member,
    prompt: str,
) -> None:
    """POST a prompt to the channel server."""
    import httpx

    chat_id = f"discord-briefing-{channel_id}-{int(time.time())}"

    metadata: dict[str, Any] = {
        "channel_id": channel_id,
        "author_id": str(user.id),
        "source": "briefing_button",
    }

    payload = {
        "source": "discord",
        "chat_id": chat_id,
        "sender": user.display_name,
        "content": prompt,
        "metadata": metadata,
    }

    async with httpx.AsyncClient() as http:
        try:
            await http.post(
                f"{channel_url}/message",
                json=payload,
                timeout=10.0,
            )
        except httpx.ConnectError:
            log.error("Channel server unreachable for briefing button")
