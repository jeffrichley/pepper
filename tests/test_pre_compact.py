"""Tests for PreCompact hook."""

import json
import subprocess
import sys
from pathlib import Path


def test_pre_compact_appends_transcript(temp_vault, mock_stdin_data, temp_transcript):
    stdin = mock_stdin_data(
        session_id="compact-sess-1",
        transcript_path=str(temp_transcript),
        hook_event="PreCompact",
    )
    _run_hook(temp_vault, stdin)

    log_files = list((temp_vault / "daily" / "raw").glob("*.md"))
    assert len(log_files) == 1
    text = log_files[0].read_text()
    assert "What is the status of the Pepper project?" in text
    assert "[pre-compact]" in text
    assert "(session: compact-sess-1)" in text


def test_pre_compact_returns_nudge(temp_vault, mock_stdin_data, temp_transcript):
    stdin = mock_stdin_data(
        transcript_path=str(temp_transcript),
        hook_event="PreCompact",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert "systemMessage" in data
    assert "compacted" in data["systemMessage"].lower() or "unsaved" in data["systemMessage"].lower()


def test_pre_compact_creates_log_file(temp_vault, mock_stdin_data, temp_transcript):
    log_dir = temp_vault / "daily" / "raw"
    assert len(list(log_dir.glob("*.md"))) == 0
    stdin = mock_stdin_data(
        transcript_path=str(temp_transcript),
        hook_event="PreCompact",
    )
    _run_hook(temp_vault, stdin)
    assert len(list(log_dir.glob("*.md"))) == 1


def test_pre_compact_no_transcript(temp_vault, mock_stdin_data):
    stdin = mock_stdin_data(
        transcript_path="/nonexistent/path.txt",
        hook_event="PreCompact",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert "systemMessage" in data


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "pre_compact_flush.py"
    result = subprocess.run(
        [sys.executable, str(hook_path)],
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
