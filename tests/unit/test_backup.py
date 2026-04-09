"""Tests for vault backup."""

import tarfile
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_backup_vault_creates_archive(tmp_path, monkeypatch):
    """backup_vault creates a tar.gz of the vault."""
    # Set up fake vault
    vault = tmp_path / ".pepper" / "Memory"
    vault.mkdir(parents=True)
    (vault / "IDENTITY.md").write_text("# Test")
    (vault / "daily" / "raw").mkdir(parents=True)
    (vault / "daily" / "raw" / "2026-04-08.jsonl").write_text('{"test": true}\n')

    backup_dir = tmp_path / ".pepper" / "backups"

    monkeypatch.setattr("pepper.backup.BACKUP_DIR", backup_dir)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    with patch("pepper.backup._upload_to_drive", return_value="fake-drive-id"):
        from pepper.backup import backup_vault

        result = backup_vault()

    assert result["status"] == "ok"
    assert result["drive_id"] == "fake-drive-id"

    # Verify archive exists and contains vault files
    archives = list(backup_dir.glob("*.tar.gz"))
    assert len(archives) == 1

    with tarfile.open(archives[0], "r:gz") as tar:
        names = tar.getnames()
        assert "Memory/IDENTITY.md" in names
        assert "Memory/daily/raw/2026-04-08.jsonl" in names


@pytest.mark.unit
def test_backup_vault_skips_missing_vault(tmp_path, monkeypatch):
    """backup_vault returns skipped if vault doesn't exist."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    from pepper.backup import backup_vault

    result = backup_vault()
    assert result["status"] == "skipped"


@pytest.mark.unit
def test_rotate_local_backups(tmp_path, monkeypatch):
    """Rotation keeps only MAX_LOCAL_BACKUPS archives."""
    monkeypatch.setattr("pepper.backup.BACKUP_DIR", tmp_path)
    monkeypatch.setattr("pepper.backup.MAX_LOCAL_BACKUPS", 3)

    # Create 5 fake archives with different timestamps
    import time

    for i in range(5):
        f = tmp_path / f"2026-04-0{i + 1}T00-00-00-pepper-vault.tar.gz"
        f.write_text("fake")
        # Stagger mtime so sort order is deterministic
        mtime = time.time() - (4 - i) * 100
        import os

        os.utime(f, (mtime, mtime))

    from pepper.backup import _rotate_local_backups

    _rotate_local_backups()

    remaining = list(tmp_path.glob("*-pepper-vault.tar.gz"))
    assert len(remaining) == 3
