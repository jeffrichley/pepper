"""Tests for pepper.attachments — download, storage, and cleanup."""

from datetime import datetime, timedelta

from pepper.attachments import (
    cleanup_attachments,
    get_today_dir,
)


def test_get_today_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("pepper.attachments.get_runtime_path", lambda: tmp_path)
    today = datetime.now().strftime("%Y-%m-%d")
    result = get_today_dir()
    assert result == tmp_path / "attachments" / today
    assert result.is_dir()


def test_cleanup_deletes_old_directories(tmp_path, monkeypatch):
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)

    # Create an old date directory (40 days ago)
    old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
    old_dir = tmp_path / old_date
    old_dir.mkdir()
    (old_dir / "old_file.txt").write_text("old")

    # Create a recent date directory
    recent_date = datetime.now().strftime("%Y-%m-%d")
    recent_dir = tmp_path / recent_date
    recent_dir.mkdir()
    (recent_dir / "new_file.txt").write_text("new")

    stats = cleanup_attachments()
    assert stats["deleted_age"] == 1
    assert not old_dir.exists()
    assert recent_dir.exists()


def test_cleanup_preserves_recent_directories(tmp_path, monkeypatch):
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)

    recent_date = datetime.now().strftime("%Y-%m-%d")
    recent_dir = tmp_path / recent_date
    recent_dir.mkdir()
    (recent_dir / "file.txt").write_text("keep me")

    stats = cleanup_attachments()
    assert stats["deleted_age"] == 0
    assert recent_dir.exists()


def test_cleanup_enforces_size_cap(tmp_path, monkeypatch):
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)
    monkeypatch.setattr("pepper.attachments.MAX_TOTAL_BYTES", 100)  # 100 bytes cap

    today = datetime.now().strftime("%Y-%m-%d")
    today_dir = tmp_path / today
    today_dir.mkdir()

    # Create files totaling > 100 bytes
    (today_dir / "file1.txt").write_bytes(b"x" * 60)
    (today_dir / "file2.txt").write_bytes(b"y" * 60)

    stats = cleanup_attachments()
    assert stats["deleted_size"] >= 1

    # Total should now be under cap
    total = sum(f.stat().st_size for f in tmp_path.rglob("*") if f.is_file())
    assert total <= 100


def test_cleanup_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("pepper.attachments.get_attachments_dir", lambda: tmp_path)
    stats = cleanup_attachments()
    assert stats["deleted_age"] == 0
    assert stats["deleted_size"] == 0


def test_cleanup_nonexistent_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "pepper.attachments.get_attachments_dir", lambda: tmp_path / "nope"
    )
    stats = cleanup_attachments()
    assert stats["deleted_age"] == 0
    assert stats["deleted_size"] == 0
