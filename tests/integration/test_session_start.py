"""Tests for SessionStart hook."""

import json
import subprocess
import sys
from pathlib import Path


def test_session_start_output_is_valid_json(temp_vault, mock_stdin_data):
    result = _run_hook(temp_vault, mock_stdin_data())
    data = json.loads(result)
    assert "systemMessage" in data


def test_session_start_includes_all_tier1(temp_vault, mock_stdin_data):
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "# Identity" in msg or "# IDENTITY.md" in msg
    assert "TestBot" in msg
    assert "# Soul" in msg or "# SOUL.md" in msg
    assert "# User Profile" in msg or "# USER.md" in msg
    assert "# Memory" in msg or "# MEMORY.md" in msg
    assert "# Operations" in msg or "# OPERATIONS.md" in msg


def test_session_start_includes_recent_summary(temp_vault, mock_stdin_data):
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "2026-04-04 Summary" in msg


def test_session_start_includes_weekly_summary(temp_vault, mock_stdin_data):
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "Week 14 Summary" in msg


def test_session_start_missing_file_resilience(temp_vault, mock_stdin_data):
    (temp_vault / "SOUL.md").unlink()
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "TestBot" in msg
    assert "Soul" not in msg


def test_session_start_empty_file(temp_vault, mock_stdin_data):
    (temp_vault / "SOUL.md").write_text("")
    result = _run_hook(temp_vault, mock_stdin_data())
    data = json.loads(result)
    assert "systemMessage" in data


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pepper.hooks.session_start_context"],
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
