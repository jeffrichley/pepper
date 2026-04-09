"""Shared utilities for Pepper — vault path resolution."""

import os
from datetime import datetime
from pathlib import Path


def get_vault_path() -> Path:
    """Return the absolute path to the Memory vault.

    Uses PEPPER_VAULT_PATH env var if set, otherwise defaults to ~/.pepper/Memory.
    """
    override = os.environ.get("PEPPER_VAULT_PATH")
    if override:
        return Path(override)
    return Path.home() / ".pepper" / "Memory"


def get_daily_log_path(vault_path: Path) -> Path:
    """Return today's raw daily log path: Memory/daily/raw/YYYY-MM-DD.jsonl."""
    today = datetime.now().strftime("%Y-%m-%d")
    return vault_path / "daily" / "raw" / f"{today}.jsonl"
