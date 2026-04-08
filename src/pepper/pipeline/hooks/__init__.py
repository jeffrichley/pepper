"""Pipeline hook registration — lists of hooks for inbound and outbound messages."""

from __future__ import annotations

from pepper.pipeline.runner import Hook

INBOUND_HOOKS: list[Hook] = []
OUTBOUND_HOOKS: list[Hook] = []
