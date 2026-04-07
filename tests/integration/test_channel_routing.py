"""Tests for the channel server HTTP endpoints.

Tests the Python channel server HTTP API directly.
"""

import threading
import time

import httpx
import pytest
import uvicorn

from pepper.channel.router import Router
from pepper.channel.server import create_http_app

PORT = 18788  # Use a non-default port to avoid conflicts


@pytest.fixture(scope="module")
def channel_server():
    """Start the Python channel HTTP server on a test port."""
    router = Router(ttl_seconds=3600)
    app = create_http_app(router)

    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(30):
        try:
            httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=1.0)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            time.sleep(0.1)
    else:
        pytest.fail("Channel server did not start")

    yield server


def test_health_endpoint(channel_server):
    """Health endpoint returns status and port."""
    resp = httpx.get(f"http://127.0.0.1:{PORT}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


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


def test_post_message_validation(channel_server):
    """Missing required fields return 400."""
    resp = httpx.post(
        f"http://127.0.0.1:{PORT}/message",
        json={"source": "test-bot"},
    )
    assert resp.status_code == 400


def test_register_validation(channel_server):
    """Missing source on register returns 400."""
    resp = httpx.post(
        f"http://127.0.0.1:{PORT}/register",
        json={"description": "no source"},
    )
    assert resp.status_code == 400


def test_not_found(channel_server):
    """Unknown routes return 404."""
    resp = httpx.get(f"http://127.0.0.1:{PORT}/nonexistent")
    assert resp.status_code == 404
