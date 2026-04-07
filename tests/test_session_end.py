"""Tests for SessionEnd hook."""

import json
import subprocess
import sys
from pathlib import Path


def test_session_end_returns_empty_json(temp_vault, mock_stdin_data):
    """SessionEnd should return empty JSON (session is ending)."""
    stdin = mock_stdin_data(
        session_id="end-sess-1",
        hook_event="SessionEnd",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert data == {}


def test_session_end_does_not_dump_transcript(temp_vault, mock_stdin_data, temp_transcript):
    """SessionEnd should NOT write the raw transcript to the daily log."""
    stdin = mock_stdin_data(
        session_id="end-sess-2",
        transcript_path=str(temp_transcript),
        hook_event="SessionEnd",
    )
    _run_hook(temp_vault, stdin)

    log_dir = temp_vault / "daily" / "raw"
    log_files = list(log_dir.glob("*.md"))
    assert len(log_files) == 0, "SessionEnd should not create daily log entries"


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pepper.hooks.session_end_flush"],
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
