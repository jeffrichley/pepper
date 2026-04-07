"""Tests for PreCompact hook."""

import json
import subprocess
import sys
from pathlib import Path


def test_pre_compact_returns_nudge(temp_vault, mock_stdin_data):
    """PreCompact should return a systemMessage nudging to save context."""
    stdin = mock_stdin_data(hook_event="PreCompact")
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert "systemMessage" in data
    assert (
        "compacted" in data["systemMessage"].lower()
        or "unsaved" in data["systemMessage"].lower()
    )


def test_pre_compact_does_not_dump_transcript(
    temp_vault, mock_stdin_data, temp_transcript
):
    """PreCompact should NOT write the raw transcript to the daily log."""
    stdin = mock_stdin_data(
        session_id="compact-sess-1",
        transcript_path=str(temp_transcript),
        hook_event="PreCompact",
    )
    _run_hook(temp_vault, stdin)

    log_dir = temp_vault / "daily" / "raw"
    log_files = list(log_dir.glob("*.md"))
    assert len(log_files) == 0, "PreCompact should not create daily log entries"


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pepper.hooks.pre_compact_flush"],
        input=stdin_data,
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "PEPPER_VAULT_PATH": str(vault_path),
        },
    )
    assert result.returncode == 0, f"Hook failed: {result.stderr}"
    return result.stdout
