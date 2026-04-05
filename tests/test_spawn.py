"""Tests for spawn_session utility.

NOTE: These tests invoke real Claude Code sessions. They require:
- Claude Code CLI installed and authenticated
- CLAUDE_CODE_GIT_BASH_PATH set in .env
- Network access to Anthropic API

Mark them to run only with -m slow.
"""

import subprocess
import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / ".claude" / "scripts"))


@pytest.mark.slow
def test_spawn_basic():
    from spawn_session import spawn
    result = spawn("Respond with exactly the word: PONG")
    assert "PONG" in result


@pytest.mark.slow
def test_spawn_with_context():
    from spawn_session import spawn
    result = spawn(
        "What is your name? Respond with just the name.",
        append_context="Your name is Pepper. Only respond with the name Pepper.",
    )
    assert "Pepper" in result


@pytest.mark.slow
def test_spawn_reads_vault():
    from spawn_session import spawn
    result = spawn("Read Memory/IDENTITY.md and tell me only the agent's name.")
    assert "Pepper" in result


@pytest.mark.slow
def test_spawn_timeout():
    from spawn_session import spawn
    with pytest.raises(subprocess.TimeoutExpired):
        spawn("Write a 10000 word essay about the history of computing", timeout=5)
