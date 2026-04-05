"""Shared test fixtures for Pepper foundation tests."""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault with Tier 1 files for testing."""
    vault = tmp_path / "Memory"
    vault.mkdir()

    (vault / "IDENTITY.md").write_text("# Identity\n\n**Name:** TestBot\n**Emoji:** 🤖\n**Role:** Test Agent\n**Created by:** Test\n")
    (vault / "SOUL.md").write_text("# Soul\n\n## Personality\nTest personality.\n\n## Behavioral Rules\nBe helpful.\n")
    (vault / "USER.md").write_text("# User Profile\n\n## About\n- **Name:** Tester\n- **Timezone:** UTC\n")
    (vault / "MEMORY.md").write_text("# Memory\n\n## Active Projects\n- Test project\n")
    (vault / "OPERATIONS.md").write_text("# Operations\n\n## Vault\n- **Location:** Memory/\n")

    summaries = vault / "daily" / "summaries"
    summaries.mkdir(parents=True)
    (summaries / "2026-04-04.md").write_text("# 2026-04-04 Summary\n\n## Key Accomplishments\n- Set up test vault\n")

    raw = vault / "daily" / "raw"
    raw.mkdir(parents=True)

    weekly = vault / "weekly"
    weekly.mkdir()
    (weekly / "2026-W14.md").write_text("# Week 14 Summary\n\n## Highlights\n- Testing week\n")

    return vault


@pytest.fixture
def mock_stdin_data():
    """Create mock stdin JSON data for hooks."""
    def _make(session_id="test-session-123", transcript_path=None, hook_event="SessionStart"):
        data = {
            "session_id": session_id,
            "transcript_path": transcript_path or "",
            "cwd": os.getcwd(),
            "hook_event_name": hook_event,
        }
        return json.dumps(data)
    return _make


@pytest.fixture
def temp_transcript(tmp_path):
    """Create a temporary transcript file."""
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(
        "User: What is the status of the Pepper project?\n"
        "Assistant: The Pepper project is in the foundation phase.\n"
        "User: Great, let's proceed with hooks.\n"
        "Assistant: I'll start implementing the SessionStart hook.\n"
    )
    return transcript
