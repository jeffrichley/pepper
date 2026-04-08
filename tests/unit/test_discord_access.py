"""Tests for Discord access control."""

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def access_file(tmp_path):
    """Create a temporary access.json file."""
    path = tmp_path / "access.json"

    def _write(config):
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    return _write


def _make_message(
    *,
    author_id: int = 100,
    is_bot: bool = False,
    guild_id: int | None = 999,
    channel_id: int = 123,
    mentions: list | None = None,
    reference_message_id: int | None = None,
    content: str = "hello",
):
    """Build a mock discord.Message."""
    msg = MagicMock()
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.author.bot = is_bot
    msg.content = content

    if guild_id:
        msg.guild = MagicMock()
        msg.guild.id = guild_id
    else:
        msg.guild = None

    msg.channel = MagicMock()
    msg.channel.id = channel_id
    msg.mentions = mentions or []

    if reference_message_id:
        msg.reference = MagicMock()
        msg.reference.message_id = reference_message_id
    else:
        msg.reference = None

    return msg


def _make_bot_user(user_id: int = 42):
    """Build a mock bot user."""
    user = MagicMock()
    user.id = user_id
    return user


def test_load_access_defaults(tmp_path):
    """Missing access.json returns defaults."""
    from pepper.integrations.discord.access import load_access

    # Arrange - point to non-existent file
    path = tmp_path / "missing.json"

    # Act
    config = load_access(path)

    # Assert
    assert config["dmPolicy"] == "allowlist"
    assert config["allowFrom"] == []
    assert config["channels"] == {}


def test_load_access_from_file(access_file):
    """Loads config from access.json."""
    from pepper.integrations.discord.access import load_access

    # Arrange
    path = access_file({"dmPolicy": "disabled", "allowFrom": ["100"]})

    # Act
    config = load_access(path)

    # Assert
    assert config["dmPolicy"] == "disabled"
    assert config["allowFrom"] == ["100"]


def test_save_access(tmp_path):
    """Saves config to access.json."""
    from pepper.integrations.discord.access import save_access

    # Arrange
    path = tmp_path / "subdir" / "access.json"
    config = {"dmPolicy": "allowlist", "allowFrom": ["100"]}

    # Act
    save_access(config, path)

    # Assert
    assert path.exists()
    saved = json.loads(path.read_text())
    assert saved["dmPolicy"] == "allowlist"


def test_gate_dm_allowlist_allowed():
    """DM from allowed user passes gate."""
    from pepper.integrations.discord.access import gate

    # Arrange
    config = {"dmPolicy": "allowlist", "allowFrom": ["100"]}
    msg = _make_message(guild_id=None, author_id=100)
    bot = _make_bot_user()

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is True


def test_gate_dm_allowlist_denied():
    """DM from unknown user is denied."""
    from pepper.integrations.discord.access import gate

    # Arrange
    config = {"dmPolicy": "allowlist", "allowFrom": ["100"]}
    msg = _make_message(guild_id=None, author_id=999)
    bot = _make_bot_user()

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is False


def test_gate_dm_disabled():
    """DMs disabled blocks all DMs."""
    from pepper.integrations.discord.access import gate

    # Arrange
    config = {"dmPolicy": "disabled", "allowFrom": ["100"]}
    msg = _make_message(guild_id=None, author_id=100)
    bot = _make_bot_user()

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is False


def test_gate_guild_not_configured():
    """Guild message in unconfigured channel is dropped."""
    from pepper.integrations.discord.access import gate

    # Arrange
    config = {"channels": {}}
    msg = _make_message(guild_id=999, channel_id=123)
    bot = _make_bot_user()

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is False


def test_gate_guild_mention_required_and_mentioned():
    """Guild message with @mention in configured channel passes."""
    from pepper.integrations.discord.access import gate

    # Arrange
    bot = _make_bot_user()
    config = {
        "channels": {"123": {"requireMention": True, "allowFrom": []}},
        "mentionPatterns": [],
    }
    msg = _make_message(guild_id=999, channel_id=123, mentions=[bot])

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is True


def test_gate_guild_mention_required_not_mentioned():
    """Guild message without mention is dropped."""
    from pepper.integrations.discord.access import gate

    # Arrange
    bot = _make_bot_user()
    config = {
        "channels": {"123": {"requireMention": True, "allowFrom": []}},
        "mentionPatterns": [],
    }
    msg = _make_message(guild_id=999, channel_id=123, mentions=[])

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is False


def test_gate_guild_no_mention_required():
    """Guild message in channel that doesn't require mention passes."""
    from pepper.integrations.discord.access import gate

    # Arrange
    bot = _make_bot_user()
    config = {
        "channels": {"123": {"requireMention": False, "allowFrom": []}},
        "mentionPatterns": [],
    }
    msg = _make_message(guild_id=999, channel_id=123, mentions=[])

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is True


def test_gate_guild_reply_to_bot():
    """Reply to bot's message passes mention check."""
    from pepper.integrations.discord.access import gate

    # Arrange
    bot = _make_bot_user()
    config = {
        "channels": {"123": {"requireMention": True, "allowFrom": []}},
        "mentionPatterns": [],
    }
    msg = _make_message(
        guild_id=999,
        channel_id=123,
        reference_message_id=555,
    )
    recent_ids = {555}

    # Act
    result = gate(msg, bot, config, recent_ids)

    # Assert
    assert result is True


def test_gate_guild_custom_pattern():
    """Custom mention pattern triggers response."""
    from pepper.integrations.discord.access import gate

    # Arrange
    bot = _make_bot_user()
    config = {
        "channels": {"123": {"requireMention": True, "allowFrom": []}},
        "mentionPatterns": ["hey pepper"],
    }
    msg = _make_message(
        guild_id=999,
        channel_id=123,
        content="hey pepper, what's up?",
    )

    # Act
    result = gate(msg, bot, config, set())

    # Assert
    assert result is True


def test_gate_guild_channel_allowfrom():
    """Channel allowFrom restricts to specific users."""
    from pepper.integrations.discord.access import gate

    # Arrange
    bot = _make_bot_user()
    config = {
        "channels": {"123": {"requireMention": False, "allowFrom": ["200"]}},
        "mentionPatterns": [],
    }
    msg = _make_message(guild_id=999, channel_id=123, author_id=100)

    # Act
    result = gate(msg, bot, config, set())

    # Assert — author 100 not in allowFrom
    assert result is False
