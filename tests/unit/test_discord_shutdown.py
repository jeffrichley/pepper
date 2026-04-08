"""Tests for Discord MCP server graceful shutdown."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_lifespan_calls_client_close():
    """Lifespan context manager calls client.close() on exit."""
    # Arrange - mock the bot and client
    with (
        patch(
            "pepper.integrations.discord.mcp_server.start_bot",
            new_callable=AsyncMock,
        ),
        patch("pepper.integrations.discord.mcp_server.client") as mock_client,
    ):
        mock_client.close = AsyncMock()
        from pepper.integrations.discord.mcp_server import lifespan

        mock_server = MagicMock()

        # Act - enter and exit the lifespan context
        async with lifespan(mock_server):
            pass

        # Assert - client.close() was called during shutdown
        mock_client.close.assert_called_once()
