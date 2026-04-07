"""Attachment storage and cleanup for Pepper.

Downloads files to ~/.pepper/attachments/YYYY-MM-DD/<id>_<filename>,
with age-based and size-based cleanup.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from pepper.process import get_runtime_path

log = logging.getLogger("pepper-attachments")

MAX_AGE_DAYS = 30
MAX_TOTAL_BYTES = 500 * 1024 * 1024  # 500MB


def get_attachments_dir() -> Path:
    """Return the root attachments directory."""
    return get_runtime_path() / "attachments"


def get_today_dir() -> Path:
    """Return today's attachment subdirectory, creating it if needed."""
    today = datetime.now().strftime("%Y-%m-%d")
    d = get_attachments_dir() / today
    d.mkdir(parents=True, exist_ok=True)
    return d


async def download_attachment(
    url: str,
    filename: str,
    message_id: str,
) -> Path | None:
    """Download a file from a URL to the attachments directory.

    Returns the local path on success, None on failure.
    """
    safe_name = f"{message_id}_{filename}".replace("/", "_").replace("\\", "_")
    dest = get_today_dir() / safe_name

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            log.info(f"Downloaded attachment: {dest} ({len(resp.content)} bytes)")
            return dest
    except Exception as e:
        log.error(f"Failed to download {url}: {e}")
        return None


def cleanup_attachments() -> dict[str, int]:
    """Run cleanup: delete files older than MAX_AGE_DAYS, then enforce MAX_TOTAL_BYTES.

    Returns stats about what was cleaned.
    """
    attachments_dir = get_attachments_dir()
    if not attachments_dir.exists():
        return {"deleted_age": 0, "deleted_size": 0}

    deleted_age = 0
    deleted_size = 0
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)

    # Phase 1: delete by age (remove old date directories)
    for date_dir in sorted(attachments_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        try:
            dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
            if dir_date < cutoff:
                count = sum(1 for _ in date_dir.rglob("*") if _.is_file())
                shutil.rmtree(date_dir)
                deleted_age += count
                log.info(f"Cleaned up {date_dir.name} ({count} files, older than {MAX_AGE_DAYS} days)")
        except ValueError:
            continue  # skip non-date directories

    # Phase 2: enforce size cap
    total_size = _get_total_size(attachments_dir)
    if total_size > MAX_TOTAL_BYTES:
        # Delete oldest files until under cap
        all_files = sorted(
            (f for f in attachments_dir.rglob("*") if f.is_file()),
            key=lambda f: f.stat().st_mtime,
        )
        for f in all_files:
            if total_size <= MAX_TOTAL_BYTES:
                break
            size = f.stat().st_size
            f.unlink()
            total_size -= size
            deleted_size += 1

        # Clean up empty date directories
        for date_dir in attachments_dir.iterdir():
            if date_dir.is_dir() and not any(date_dir.iterdir()):
                date_dir.rmdir()

    return {"deleted_age": deleted_age, "deleted_size": deleted_size}


def _get_total_size(directory: Path) -> int:
    """Calculate total size of all files in a directory tree."""
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
