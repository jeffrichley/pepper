"""Tests for Discord MCP server graceful shutdown."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_watch_stdin_sets_event_on_eof():
    """stdin EOF triggers the shutdown event."""
    from pepper.integrations.discord.mcp_server import _watch_stdin

    # Arrange - create a shutdown event
    shutdown_event = asyncio.Event()

    # Act - run _watch_stdin with stdin.read that returns immediately (EOF)
    with patch("pepper.integrations.discord.mcp_server.sys") as mock_sys:
        mock_sys.stdin.read = MagicMock(return_value="")
        await _watch_stdin(shutdown_event)

    # Assert - shutdown event is set
    assert shutdown_event.is_set()


@pytest.mark.asyncio
async def test_lifespan_calls_client_close():
    """Lifespan context manager calls client.close() on exit."""
    # Arrange - mock the bot and client
    with (
        patch(
            "pepper.integrations.discord.mcp_server.start_bot",
            new_callable=AsyncMock,
        ),
        patch(
            "pepper.integrations.discord.mcp_server.client"
        ) as mock_client,
        patch(
            "pepper.integrations.discord.mcp_server._watch_stdin",
            new_callable=AsyncMock,
        ),
    ):
        mock_client.close = AsyncMock()
        from pepper.integrations.discord.mcp_server import lifespan

        mock_server = MagicMock()

        # Act - enter and exit the lifespan context
        async with lifespan(mock_server):
            pass

        # Assert - client.close() was called during shutdown
        mock_client.close.assert_called_once()
