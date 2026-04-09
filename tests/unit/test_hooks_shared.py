"""Tests for pepper.hooks.shared — vault path resolution."""

from pathlib import Path

from pepper.hooks.shared import get_vault_path


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
