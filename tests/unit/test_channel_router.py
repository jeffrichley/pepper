"""Tests for pepper.channel.router -- routing table logic."""

from pepper.channel.router import Router


def test_add_and_lookup_route() -> None:
    # Arrange - create a router with a 1-hour TTL
    router = Router(ttl_seconds=3600)

    # Act - add a route and look it up
    router.add("chat-1", "discord")
    result = router.lookup("chat-1")

    # Assert - the route is found
    assert result == "discord"


def test_lookup_missing_returns_none() -> None:
    # Arrange - create a router with no routes
    router = Router(ttl_seconds=3600)

    # Act - look up a nonexistent route
    result = router.lookup("nonexistent")

    # Assert - returns None for missing routes
    assert result is None


def test_expired_route_returns_none() -> None:
    # Arrange - create a router with zero TTL so routes expire immediately
    router = Router(ttl_seconds=0)

    # Act - add a route and look it up (it's already expired)
    router.add("chat-1", "discord")
    result = router.lookup("chat-1")

    # Assert - expired route returns None
    assert result is None


def test_clean_expired() -> None:
    # Arrange - create a router with zero TTL and add routes
    router = Router(ttl_seconds=0)
    router.add("chat-1", "discord")
    router.add("chat-2", "email")

    # Act - clean expired routes
    router.clean_expired()

    # Assert - all expired routes are removed
    assert router.size == 0


def test_register_and_list_sources() -> None:
    # Arrange - create a router
    router = Router(ttl_seconds=3600)

    # Act - register two sources
    router.register_source("discord", "Discord bot")
    router.register_source("email", "Email integration")
    sources = router.registered_sources

    # Assert - both sources are listed
    assert "discord" in sources
    assert "email" in sources
