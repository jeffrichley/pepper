"""Tests for pepper.attachments — download, storage, and cleanup."""

from datetime import datetime, timedelta

from pepper.attachments import (
    cleanup_attachments,
    get_today_dir,
)


def test_get_today_dir(tmp_path, monkeypatch):
    # Arrange - patch runtime path to a temp directory
    monkeypatch.setattr("pepper.attachments.get_runtime_path", lambda: tmp_path)
    today = datetime.now().strftime("%Y-%m-%d")

    # Act - resolve today's attachment directory
    result = get_today_dir()

    # Assert - directory exists under attachments/<today>
    assert result == tmp_path / "attachments" / today
    assert result.is_dir()


def test_cleanup_deletes_old_directories(tmp_path, monkeypatch):
    # Arrange - create one old and one recent date directory
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)
    old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
    old_dir = tmp_path / old_date
    old_dir.mkdir()
    (old_dir / "old_file.txt").write_text("old")
    recent_date = datetime.now().strftime("%Y-%m-%d")
    recent_dir = tmp_path / recent_date
    recent_dir.mkdir()
    (recent_dir / "new_file.txt").write_text("new")

    # Act - run age-based cleanup
    stats = cleanup_attachments()

    # Assert - old directory removed, recent directory preserved
    assert stats["deleted_age"] == 1
    assert not old_dir.exists()
    assert recent_dir.exists()


def test_cleanup_preserves_recent_directories(tmp_path, monkeypatch):
    # Arrange - create a recent date directory with a file
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)
    recent_date = datetime.now().strftime("%Y-%m-%d")
    recent_dir = tmp_path / recent_date
    recent_dir.mkdir()
    (recent_dir / "file.txt").write_text("keep me")

    # Act - run cleanup
    stats = cleanup_attachments()

    # Assert - no age-based deletions and directory still exists
    assert stats["deleted_age"] == 0
    assert recent_dir.exists()


def test_cleanup_enforces_size_cap(tmp_path, monkeypatch):
    # Arrange - create files totaling over the 100-byte cap
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)
    monkeypatch.setattr("pepper.attachments.MAX_TOTAL_BYTES", 100)
    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = tmp_path / today
    today_dir.mkdir()
    (today_dir / "file1.txt").write_bytes(b"x" * 60)
    (today_dir / "file2.txt").write_bytes(b"y" * 60)

    # Act - run size-capped cleanup
    stats = cleanup_attachments()

    # Assert - at least one file deleted and total size is under cap
    assert stats["deleted_size"] >= 1
    total = sum(f.stat().st_size for f in tmp_path.rglob("*") if f.is_file())
    assert total <= 100


def test_cleanup_empty_dir(tmp_path, monkeypatch):
    # Arrange - point to an empty attachments directory
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)

    # Act - run cleanup on an empty directory
    stats = cleanup_attachments()

    # Assert - no files deleted
    assert stats["deleted_age"] == 0
    assert stats["deleted_size"] == 0


def test_cleanup_nonexistent_dir(tmp_path, monkeypatch):
    # Arrange - point to a directory that does not exist
    monkeypatch.setattr(
        "pepper.attachments.get_attachments_dir", lambda: tmp_path / "nope"
    )

    # Act - run cleanup when the attachments directory is missing
    stats = cleanup_attachments()

    # Assert - returns zero counts without raising an error
    assert stats["deleted_age"] == 0
    assert stats["deleted_size"] == 0
