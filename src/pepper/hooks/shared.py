"""Shared utilities for Pepper hooks.

Provides vault path resolution, Tier 1 file reading, daily log management,
and summary reading. All file operations use filelock for concurrency safety.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from filelock import FileLock

TIER_1_FILES = [
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    "OPERATIONS.md",
]


def get_vault_path() -> Path:
    """Return the absolute path to the Memory vault.

    Uses PEPPER_VAULT_PATH env var if set, otherwise defaults to ~/.pepper/Memory.
    """
    override = os.environ.get("PEPPER_VAULT_PATH")
    if override:
        return Path(override)
    return Path.home() / ".pepper" / "Memory"


def read_tier1_files(vault_path: Path) -> str:
    """Read and concatenate all Tier 1 files with separators."""
    parts = []
    for filename in TIER_1_FILES:
        filepath = vault_path / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"# {filename}\n{content}")
    return "\n\n---\n\n".join(parts)


def get_daily_log_path(vault_path: Path) -> Path:
    """Return today's raw daily log path: Memory/daily/raw/YYYY-MM-DD.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    return vault_path / "daily" / "raw" / f"{today}.md"


def append_to_daily_log(
    vault_path: Path,
    content: str,
    source: str,
    session_id: str,
) -> None:
    """Append a timestamped entry to today's raw daily log."""
    log_path = get_daily_log_path(vault_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = log_path.with_suffix(".md.lock")
    now = datetime.now().strftime("%H:%M")

    header = f"\n\n## {now} [{source}] (session: {session_id})\n\n"

    with FileLock(lock_path), open(log_path, "a", encoding="utf-8") as f:
        f.write(header)
        f.write(content)
        f.write("\n")


def session_already_logged(vault_path: Path, session_id: str) -> bool:
    """Check if a session ID already has an entry in today's daily log."""
    log_path = get_daily_log_path(vault_path)
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8")
    return f"(session: {session_id})" in text


def read_recent_summaries(
    vault_path: Path,
    daily_count: int = 2,
    include_weekly: bool = True,
) -> str:
    """Read the most recent daily summaries and optional weekly summary."""
    parts = []

    summaries_dir = vault_path / "daily" / "summaries"
    if summaries_dir.exists():
        summary_files = sorted(summaries_dir.glob("*.md"), reverse=True)[:daily_count]
        for f in summary_files:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"# Recent Summary ({f.stem})\n{content}")

    if include_weekly:
        weekly_dir = vault_path / "weekly"
        if weekly_dir.exists():
            weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)[:1]
            for f in weekly_files:
                content = f.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(f"# Weekly Summary ({f.stem})\n{content}")

    return "\n\n---\n\n".join(parts)


def read_stdin() -> dict[str, object]:
    """Read and parse JSON from stdin (hook input)."""
    result: dict[str, object] = json.loads(sys.stdin.read())
    return result


def write_stdout(data: dict[str, object]) -> None:
    """Write JSON to stdout (hook output)."""
    print(json.dumps(data))
