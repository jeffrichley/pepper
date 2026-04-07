"""Routing table for the Pepper channel server.

Maps chat_id -> source with TTL-based expiration.
Tracks registered integration sources.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Router:
    """In-memory routing table with TTL expiration."""

    ttl_seconds: int = 24 * 60 * 60
    _routes: dict[str, tuple[str, float]] = field(default_factory=dict)
    _sources: dict[str, tuple[str, float]] = field(default_factory=dict)

    def add(self, chat_id: str, source: str) -> None:
        """Record a route from chat_id to source."""
        self._routes[chat_id] = (source, time.monotonic())

    def lookup(self, chat_id: str) -> str | None:
        """Look up the source for a chat_id. Returns None if missing or expired."""
        entry = self._routes.get(chat_id)
        if entry is None:
            return None
        source, ts = entry
        if time.monotonic() - ts >= self.ttl_seconds:
            del self._routes[chat_id]
            return None
        return source

    def clean_expired(self) -> None:
        """Remove all expired routes."""
        now = time.monotonic()
        expired = [
            cid for cid, (_, ts) in self._routes.items() if now - ts >= self.ttl_seconds
        ]
        for cid in expired:
            del self._routes[cid]

    @property
    def size(self) -> int:
        """Return the number of active routes."""
        return len(self._routes)

    def register_source(self, source: str, description: str = "") -> None:
        """Register an integration source."""
        self._sources[source] = (description, time.monotonic())

    @property
    def registered_sources(self) -> list[str]:
        """Return the list of registered source names."""
        return list(self._sources.keys())
