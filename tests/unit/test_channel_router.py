"""Tests for pepper.channel.router — routing table logic."""

from pepper.channel.router import Router


def test_add_and_lookup_route():
    router = Router(ttl_seconds=3600)
    router.add("chat-1", "discord")
    assert router.lookup("chat-1") == "discord"


def test_lookup_missing_returns_none():
    router = Router(ttl_seconds=3600)
    assert router.lookup("nonexistent") is None


def test_expired_route_returns_none():
    router = Router(ttl_seconds=0)
    router.add("chat-1", "discord")
    assert router.lookup("chat-1") is None


def test_clean_expired():
    router = Router(ttl_seconds=0)
    router.add("chat-1", "discord")
    router.add("chat-2", "email")
    router.clean_expired()
    assert router.size == 0


def test_register_and_list_sources():
    router = Router(ttl_seconds=3600)
    router.register_source("discord", "Discord bot")
    router.register_source("email", "Email integration")
    sources = router.registered_sources
    assert "discord" in sources
    assert "email" in sources
