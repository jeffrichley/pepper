"""Tests for Discord embed formatting helpers."""

import sys
from pathlib import Path

# Add the discord integration to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "discord"))


def test_build_embed_basic():
    """Build an embed with title and description."""
    from embeds import build_embed

    embed_data = {
        "title": "Daily Briefing",
        "description": "Here's what's happening today.",
        "color": 3447003,
    }
    embed = build_embed(embed_data)
    assert embed.title == "Daily Briefing"
    assert embed.description == "Here's what's happening today."
    assert embed.color.value == 3447003


def test_build_embed_with_fields():
    """Build an embed with fields."""
    from embeds import build_embed

    embed_data = {
        "title": "Status",
        "fields": [
            {"name": "Calendar", "value": "3 meetings", "inline": True},
            {"name": "Email", "value": "5 unread", "inline": True},
        ],
    }
    embed = build_embed(embed_data)
    assert len(embed.fields) == 2
    assert embed.fields[0].name == "Calendar"
    assert embed.fields[0].value == "3 meetings"
    assert embed.fields[0].inline is True


def test_build_embed_empty():
    """Empty embed data returns a basic embed."""
    from embeds import build_embed

    embed = build_embed({})
    assert embed.title is None
    assert embed.description is None


def test_build_embed_none():
    """None input returns None."""
    from embeds import build_embed

    assert build_embed(None) is None
