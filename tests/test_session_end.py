"""Tests for SessionEnd hook."""

import json
import subprocess
import sys
from pathlib import Path

from shared import append_to_daily_log


def test_session_end_appends_transcript(temp_vault, mock_stdin_data, temp_transcript):
    stdin = mock_stdin_data(
        session_id="end-sess-1",
        transcript_path=str(temp_transcript),
        hook_event="SessionEnd",
    )
    _run_hook(temp_vault, stdin)
    log_files = list((temp_vault / "daily" / "raw").glob("*.md"))
    assert len(log_files) == 1
    text = log_files[0].read_text()
    assert "[session-end]" in text
    assert "(session: end-sess-1)" in text


def test_session_end_dedup_after_precompact(temp_vault, mock_stdin_data, temp_transcript):
    append_to_daily_log(
        vault_path=temp_vault,
        content="Pre-compact transcript dump",
        source="pre-compact",
        session_id="dedup-sess-1",
    )

    stdin = mock_stdin_data(
        session_id="dedup-sess-1",
        transcript_path=str(temp_transcript),
        hook_event="SessionEnd",
    )
    _run_hook(temp_vault, stdin)

    log_path = list((temp_vault / "daily" / "raw").glob("*.md"))[0]
    text = log_path.read_text()
    assert text.count("(session: dedup-sess-1)") == 1
    assert "[pre-compact]" in text
    assert "[session-end]" not in text


def test_session_end_returns_empty_json(temp_vault, mock_stdin_data, temp_transcript):
    stdin = mock_stdin_data(
        session_id="end-sess-2",
        transcript_path=str(temp_transcript),
        hook_event="SessionEnd",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert data == {}


def test_session_end_no_transcript(temp_vault, mock_stdin_data):
    stdin = mock_stdin_data(
        session_id="end-sess-3",
        transcript_path="/nonexistent/path.txt",
        hook_event="SessionEnd",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert data == {}


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "session_end_flush.py"
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
