"""Tests for hook shared utilities."""

from pathlib import Path

from pepper.hooks.shared import (
    get_vault_path,
    read_tier1_files,
    get_daily_log_path,
    append_to_daily_log,
    read_recent_summaries,
)


def test_get_vault_path():
    vault = get_vault_path()
    assert vault.name == "Memory"


def test_read_tier1_files_all_present(temp_vault):
    result = read_tier1_files(temp_vault)
    assert "# Identity" in result
    assert "TestBot" in result
    assert "# Soul" in result
    assert "# User Profile" in result
    assert "# Memory" in result
    assert "# Operations" in result
    assert "---" in result


def test_read_tier1_files_missing_file(temp_vault):
    (temp_vault / "SOUL.md").unlink()
    result = read_tier1_files(temp_vault)
    assert "# Identity" in result
    assert "# Soul" not in result
    assert "# User Profile" in result


def test_read_tier1_files_empty_file(temp_vault):
    (temp_vault / "SOUL.md").write_text("")
    result = read_tier1_files(temp_vault)
    assert "# Identity" in result
    assert "# User Profile" in result


def test_get_daily_log_path(temp_vault):
    path = get_daily_log_path(temp_vault)
    assert path.parent.name == "raw"
    assert path.suffix == ".md"
    assert path.stem.count("-") == 2


def test_append_to_daily_log(temp_vault):
    log_path = get_daily_log_path(temp_vault)
    append_to_daily_log(
        vault_path=temp_vault,
        content="Test content here",
        source="session",
        session_id="abc-123",
    )
    text = log_path.read_text()
    assert "[session]" in text
    assert "(session: abc-123)" in text
    assert "Test content here" in text


def test_append_to_daily_log_creates_file(temp_vault):
    log_path = get_daily_log_path(temp_vault)
    assert not log_path.exists()
    append_to_daily_log(
        vault_path=temp_vault,
        content="First entry",
        source="session",
        session_id="first-123",
    )
    assert log_path.exists()


def test_append_to_daily_log_appends_not_overwrites(temp_vault):
    append_to_daily_log(temp_vault, "First", "session", "s1")
    append_to_daily_log(temp_vault, "Second", "session", "s2")
    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()
    assert "First" in text
    assert "Second" in text


def test_daily_log_has_session_id(temp_vault):
    append_to_daily_log(temp_vault, "Content", "pre-compact", "sess-xyz")
    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()
    assert "(session: sess-xyz)" in text


def test_read_recent_summaries(temp_vault):
    result = read_recent_summaries(temp_vault, daily_count=1, include_weekly=True)
    assert "2026-04-04 Summary" in result
    assert "Week 14 Summary" in result


def test_read_recent_summaries_empty_dir(temp_vault):
    for f in (temp_vault / "daily" / "summaries").iterdir():
        f.unlink()
    for f in (temp_vault / "weekly").iterdir():
        f.unlink()
    result = read_recent_summaries(temp_vault, daily_count=1, include_weekly=True)
    assert result == ""
