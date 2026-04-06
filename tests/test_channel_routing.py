"""Tests for the channel server HTTP endpoints.

Starts pepper-channel.ts as a standalone Bun process (no Claude Code)
and tests the HTTP API. The MCP connection will fail (no stdio parent),
but the HTTP server starts independently.
"""

import json
import subprocess
import time
import os
from pathlib import Path

import httpx
import pytest

CHANNEL_DIR = Path(__file__).parent.parent / "channel"
PORT = 18788  # Use a non-default port to avoid conflicts


@pytest.fixture(scope="module")
def channel_server():
    """Start the channel server on a test port."""
    env = {**os.environ, "PEPPER_CHANNEL_PORT": str(PORT)}
    proc = subprocess.Popen(
        ["bun", "run", "pepper-channel.ts"],
        cwd=str(CHANNEL_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    for _ in range(30):
        try:
            httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=1.0)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            time.sleep(0.5)
    else:
        proc.kill()
        pytest.fail("Channel server did not start")

    yield proc

    proc.terminate()
    proc.wait(timeout=5)


@pytest.mark.slow
def test_health_endpoint(channel_server):
    """Health endpoint returns status and port."""
    resp = httpx.get(f"http://127.0.0.1:{PORT}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["port"] == PORT


@pytest.mark.slow
def test_register_integration(channel_server):
    """Register an integration and see it in health."""
    resp = httpx.post(
        f"http://127.0.0.1:{PORT}/register",
        json={"source": "test-bot", "description": "Test integration"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "registered"

    health = httpx.get(f"http://127.0.0.1:{PORT}/health").json()
    assert "test-bot" in health["registered_sources"]


@pytest.mark.slow
def test_post_message(channel_server):
    """Post a message and get queued response."""
    resp = httpx.post(
        f"http://127.0.0.1:{PORT}/message",
        json={
            "source": "test-bot",
            "chat_id": "test-msg-1",
            "sender": "tester",
            "content": "Hello from test",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["chat_id"] == "test-msg-1"


@pytest.mark.slow
def test_post_message_validation(channel_server):
    """Missing required fields return 400."""
    resp = httpx.post(
        f"http://127.0.0.1:{PORT}/message",
        json={"source": "test-bot"},
    )
    assert resp.status_code == 400


@pytest.mark.slow
def test_register_validation(channel_server):
    """Missing source on register returns 400."""
    resp = httpx.post(
        f"http://127.0.0.1:{PORT}/register",
        json={"description": "no source"},
    )
    assert resp.status_code == 400


@pytest.mark.slow
def test_not_found(channel_server):
    """Unknown routes return 404."""
    resp = httpx.get(f"http://127.0.0.1:{PORT}/nonexistent")
    assert resp.status_code == 404
