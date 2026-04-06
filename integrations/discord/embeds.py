"""Rich embed formatting helpers for Discord messages."""

from __future__ import annotations

from typing import Any

import discord


def build_embed(data: dict[str, Any] | None) -> discord.Embed | None:
    """Convert a metadata embed dict to a discord.Embed.

    Args:
        data: Dict with optional keys: title, description, color, fields.
              fields is a list of {name, value, inline} dicts.
              Returns None if data is None.
    """
    if data is None:
        return None

    embed = discord.Embed(
        title=data.get("title"),
        description=data.get("description"),
        color=discord.Color(data["color"]) if "color" in data else None,
    )

    for field in data.get("fields", []):
        embed.add_field(
            name=field["name"],
            value=field["value"],
            inline=field.get("inline", False),
        )

    return embed
