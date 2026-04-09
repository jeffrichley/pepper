"""Transcript hook — appends conversation-level JSONL to daily raw log."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from filelock import FileLock

from pepper.hooks.shared import get_vault_path
from pepper.pipeline.model import PipelineMessage

log = logging.getLogger("pepper-pipeline")


def _get_transcript_path() -> Path:
    """Return today's JSONL transcript path.

    Returns:
        Path to today's JSONL file under <vault>/daily/raw/.
    """
    vault = get_vault_path()
    today = datetime.now().strftime("%Y-%m-%d")
    return vault / "daily" / "raw" / f"{today}.jsonl"


def transcript_hook(message: PipelineMessage) -> PipelineMessage:
    """Append message to today's JSONL transcript. Never blocks delivery.

    Writes a single JSONL line to <vault>/daily/raw/YYYY-MM-DD.jsonl.
    Uses a file lock for concurrency safety. All exceptions are caught
    and logged so that write failures never interrupt message delivery.

    Args:
        message: The pipeline message to record.

    Returns:
        The original message, unchanged.
    """
    try:
        path = _get_transcript_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(".jsonl.lock")

        line = message.to_transcript_json() + "\n"

        with FileLock(lock_path), open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        log.warning(f"Transcript write failed: {exc}")

    return message
