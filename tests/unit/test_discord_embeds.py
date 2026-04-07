"""Tests for Discord embed formatting helpers."""


def test_build_embed_basic():
    """Build an embed with title and description."""
    from pepper.integrations.discord.embeds import build_embed

    # Arrange - set up embed data with title, description, and color
    embed_data = {
        "title": "Daily Briefing",
        "description": "Here's what's happening today.",
        "color": 3447003,
    }

    # Act - build the embed from the data dict
    embed = build_embed(embed_data)

    # Assert - verify all fields are set correctly
    assert embed.title == "Daily Briefing"
    assert embed.description == "Here's what's happening today."
    assert embed.color.value == 3447003


def test_build_embed_with_fields():
    """Build an embed with fields."""
    from pepper.integrations.discord.embeds import build_embed

    # Arrange - set up embed data with inline fields
    embed_data = {
        "title": "Status",
        "fields": [
            {"name": "Calendar", "value": "3 meetings", "inline": True},
            {"name": "Email", "value": "5 unread", "inline": True},
        ],
    }

    # Act - build the embed from the data dict
    embed = build_embed(embed_data)

    # Assert - verify fields are present and correct
    assert len(embed.fields) == 2
    assert embed.fields[0].name == "Calendar"
    assert embed.fields[0].value == "3 meetings"
    assert embed.fields[0].inline is True


def test_build_embed_empty():
    """Empty embed data returns a basic embed."""
    from pepper.integrations.discord.embeds import build_embed

    # Arrange - empty dict as input
    embed_data = {}

    # Act - build embed from empty data
    embed = build_embed(embed_data)

    # Assert - verify embed has no title or description
    assert embed.title is None
    assert embed.description is None


def test_build_embed_none():
    """None input returns None."""
    from pepper.integrations.discord.embeds import build_embed

    # Arrange - None as input (no embed data)
    embed_data = None

    # Act - build embed from None
    result = build_embed(embed_data)

    # Assert - verify None is returned
    assert result is None
