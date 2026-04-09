"""Tests for hook shared utilities."""

from pepper.hooks.shared import get_daily_log_path, get_vault_path


def test_get_vault_path():
    vault = get_vault_path()
    assert vault.name == "Memory"


def test_get_daily_log_path(temp_vault):
    path = get_daily_log_path(temp_vault)
    assert path.parent.name == "raw"
    assert path.suffix == ".jsonl"
    assert path.stem.count("-") == 2
