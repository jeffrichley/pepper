"""Tests for pepper.hooks.shared — vault path resolution and utilities."""

import os
from pathlib import Path

from pepper.hooks.shared import get_vault_path, TIER_1_FILES


def test_vault_path_from_env(tmp_path, monkeypatch):
    """PEPPER_VAULT_PATH env var overrides default."""
    vault = tmp_path / "Memory"
    vault.mkdir()
    monkeypatch.setenv("PEPPER_VAULT_PATH", str(vault))
    assert get_vault_path() == vault


def test_vault_path_default(monkeypatch):
    """Default vault path is ~/.pepper/Memory."""
    monkeypatch.delenv("PEPPER_VAULT_PATH", raising=False)
    expected = Path.home() / ".pepper" / "Memory"
    assert get_vault_path() == expected


def test_tier1_files_list():
    """Tier 1 files list is correct."""
    assert TIER_1_FILES == [
        "IDENTITY.md",
        "SOUL.md",
        "USER.md",
        "MEMORY.md",
        "OPERATIONS.md",
    ]
