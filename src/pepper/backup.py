"""Vault backup — tar.gz ~/.pepper/Memory/ and upload to Google Drive."""

from __future__ import annotations

import logging
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("pepper-backup")

DRIVE_FOLDER_ID = "19bKxRGUpDH6S0d0ifScB7MLlMF34wwk_"
BACKUP_DIR = Path.home() / ".pepper" / "backups"
MAX_LOCAL_BACKUPS = 7


def backup_vault() -> dict[str, str]:
    """Create a tar.gz of the vault and upload to Google Drive.

    Returns a dict with status, archive path, and drive file ID.
    """
    vault_path = Path.home() / ".pepper" / "Memory"
    if not vault_path.exists():
        log.warning("Vault not found, skipping backup")
        return {"status": "skipped", "reason": "vault not found"}

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Create timestamped archive
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    archive_name = f"{ts}-pepper-vault.tar.gz"
    archive_path = BACKUP_DIR / archive_name

    log.info(f"Creating backup: {archive_path}")
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(vault_path, arcname="Memory")

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    log.info(f"Archive created: {size_mb:.1f} MB")

    # Upload to Google Drive
    drive_id = _upload_to_drive(archive_path)

    # Rotate old local backups
    _rotate_local_backups()

    return {
        "status": "ok",
        "archive": str(archive_path),
        "size_mb": f"{size_mb:.1f}",
        "drive_id": drive_id,
    }


def _upload_to_drive(archive_path: Path) -> str:
    """Upload archive to Google Drive via gog CLI. Returns file ID."""
    try:
        result = subprocess.run(
            [
                "gog",
                "drive",
                "upload",
                str(archive_path),
                "--parent",
                DRIVE_FOLDER_ID,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        log.info(f"Uploaded to Drive: {result.stdout.strip()}")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        log.error(f"Drive upload failed: {e.stderr}")
        return f"error: {e.stderr}"
    except FileNotFoundError:
        log.error("gog CLI not found — is it installed?")
        return "error: gog not found"


def _rotate_local_backups() -> None:
    """Keep only the most recent MAX_LOCAL_BACKUPS archives."""
    archives = sorted(
        BACKUP_DIR.glob("*-pepper-vault.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in archives[MAX_LOCAL_BACKUPS:]:
        log.info(f"Rotating old backup: {old.name}")
        old.unlink()
