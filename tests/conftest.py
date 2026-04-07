"""Pytest configuration with auto marker injection, network guard, and project fixtures."""

from __future__ import annotations

import json
import os
import pathlib
import socket
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Auto marker injection based on test directory
# ---------------------------------------------------------------------------
MARKER_MAP: dict[str, str] = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Inject markers based on test file directory (tests/unit/, tests/integration/, tests/e2e/)."""
    for item in items:
        test_path = pathlib.Path(item.fspath)
        parts = test_path.parts
        for directory, marker_name in MARKER_MAP.items():
            if directory in parts:
                item.add_marker(getattr(pytest.mark, marker_name))
                break


# ---------------------------------------------------------------------------
# Network guard: block outbound connections in unit tests
# ---------------------------------------------------------------------------
_original_connect = socket.socket.connect
_original_create_connection = socket.create_connection


def _guarded_connect(self: socket.socket, address: Any) -> None:
    """Block non-localhost connections unless test is marked integration or e2e."""
    host = str(address[0]) if isinstance(address, tuple) else str(address)
    if host not in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ConnectionError(
            f"Network access blocked in test: attempted connection to {host}. "
            "Mark test with @pytest.mark.integration or @pytest.mark.e2e to allow network."
        )
    _original_connect(self, address)


def _guarded_create_connection(
    address: tuple[str, int],
    *args: Any,
    **kwargs: Any,
) -> socket.socket:
    """Block non-localhost create_connection calls."""
    host = address[0]
    if host not in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ConnectionError(
            f"Network access blocked in test: attempted connection to {host}. "
            "Mark test with @pytest.mark.integration or @pytest.mark.e2e to allow network."
        )
    return _original_create_connection(address, *args, **kwargs)


@pytest.fixture(autouse=True)
def _network_guard(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Block outbound network in unit tests. Integration and e2e tests bypass this."""
    markers = {m.name for m in request.node.iter_markers()}
    if markers & {"integration", "e2e"}:
        return  # Allow network for integration and e2e tests

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket, "create_connection", _guarded_create_connection)


# ---------------------------------------------------------------------------
# Session-scoped path fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def project_root() -> pathlib.Path:
    """Return the project root directory."""
    return pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def src_path(project_root: pathlib.Path) -> pathlib.Path:
    """Return the src directory."""
    return project_root / "src"


# ---------------------------------------------------------------------------
# Pepper-specific fixtures (from original conftest.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault with Tier 1 files for testing."""
    vault = tmp_path / "Memory"
    vault.mkdir()

    (vault / "IDENTITY.md").write_text(
        "# Identity\n\n**Name:** TestBot\n**Emoji:** 🤖\n**Role:** Test Agent\n**Created by:** Test\n"
    )
    (vault / "SOUL.md").write_text(
        "# Soul\n\n## Personality\nTest personality.\n\n## Behavioral Rules\nBe helpful.\n"
    )
    (vault / "USER.md").write_text(
        "# User Profile\n\n## About\n- **Name:** Tester\n- **Timezone:** UTC\n"
    )
    (vault / "MEMORY.md").write_text("# Memory\n\n## Active Projects\n- Test project\n")
    (vault / "OPERATIONS.md").write_text(
        "# Operations\n\n## Vault\n- **Location:** Memory/\n"
    )

    summaries = vault / "daily" / "summaries"
    summaries.mkdir(parents=True)
    (summaries / "2026-04-04.md").write_text(
        "# 2026-04-04 Summary\n\n## Key Accomplishments\n- Set up test vault\n"
    )

    raw = vault / "daily" / "raw"
    raw.mkdir(parents=True)

    weekly = vault / "weekly"
    weekly.mkdir()
    (weekly / "2026-W14.md").write_text(
        "# Week 14 Summary\n\n## Highlights\n- Testing week\n"
    )

    return vault


@pytest.fixture
def mock_stdin_data():
    """Create mock stdin JSON data for hooks."""

    def _make(
        session_id="test-session-123", transcript_path=None, hook_event="SessionStart"
    ):
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
