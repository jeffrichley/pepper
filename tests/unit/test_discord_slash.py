"""Tests for Discord slash commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_setup_commands_registers_four():
    """setup_commands registers brief, tasks, focus, status."""
    from discord import app_commands

    from pepper.integrations.discord.slash_commands import setup_commands

    # Arrange — patch CommandTree to avoid discord.py's singleton check
    with patch.object(
        app_commands, "CommandTree", wraps=app_commands.CommandTree,
    ) as mock_tree_cls:
        mock_client = MagicMock()
        mock_client.http = MagicMock()
        mock_client.application_id = None
        mock_client._command_tree = None  # noqa: SLF001

        # Bypass the "already has a tree" check
        mock_tree = MagicMock()
        mock_commands = []

        def _command(*, name, description):
            def decorator(func):
                cmd = MagicMock()
                cmd.name = name
                mock_commands.append(cmd)
                return func
            return decorator

        mock_tree.command = _command
        mock_tree.get_commands.return_value = mock_commands
        mock_tree_cls.return_value = mock_tree

        # Act
        tree = setup_commands(mock_client, "http://localhost:8788")

        # Assert — 4 commands registered
        names = {c.name for c in tree.get_commands()}
        assert names == {"brief", "tasks", "focus", "status"}


def test_check_access_allowed():
    """User in allowFrom passes access check."""
    from pepper.integrations.discord.slash_commands import _check_access

    # Arrange
    interaction = MagicMock()
    interaction.user.id = 100
    config = {"allowFrom": ["100"]}

    # Act
    with patch(
        "pepper.integrations.discord.slash_commands.load_access",
        return_value=config,
    ):
        result = _check_access(interaction)

    # Assert
    assert result is True


def test_check_access_denied():
    """User not in allowFrom is denied."""
    from pepper.integrations.discord.slash_commands import _check_access

    # Arrange
    interaction = MagicMock()
    interaction.user.id = 999
    config = {"allowFrom": ["100"]}

    # Act
    with patch(
        "pepper.integrations.discord.slash_commands.load_access",
        return_value=config,
    ):
        result = _check_access(interaction)

    # Assert
    assert result is False


def test_check_access_empty_allowfrom():
    """Empty allowFrom allows everyone."""
    from pepper.integrations.discord.slash_commands import _check_access

    # Arrange
    interaction = MagicMock()
    interaction.user.id = 999
    config = {"allowFrom": []}

    # Act
    with patch(
        "pepper.integrations.discord.slash_commands.load_access",
        return_value=config,
    ):
        result = _check_access(interaction)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_send_prompt_posts_to_channel():
    """Slash command prompt is POSTed to the channel server."""
    from pepper.integrations.discord.slash_commands import _send_prompt

    # Arrange
    interaction = MagicMock()
    interaction.guild_id = 999
    interaction.channel_id = 123
    interaction.guild = MagicMock()
    interaction.user.id = 100
    interaction.user.display_name = "Jeff"
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        # Act
        await _send_prompt(
            "http://localhost:8788", interaction, "Test prompt",
        )

        # Assert
        mock_client.post.assert_called_once()
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["content"] == "Test prompt"
        assert payload["source"] == "discord"
        assert payload["metadata"]["source"] == "slash_command"
