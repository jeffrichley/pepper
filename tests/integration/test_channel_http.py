"""Tests for pepper.channel.server -- HTTP endpoints."""

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from pepper.channel.router import Router
from pepper.channel.server import create_http_app


@pytest.fixture
def router():
    return Router(ttl_seconds=3600)


@pytest.fixture
def server_url(router):
    """Start the HTTP server in a background thread on a free port."""
    app = create_http_app(router)

    # Find a free port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(30):
        try:
            httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            time.sleep(0.1)
    else:
        pytest.fail("Server did not start")

    yield f"http://127.0.0.1:{port}"


def test_health(server_url):
    # Arrange - server is running via fixture

    # Act - request the health endpoint
    resp = httpx.get(f"{server_url}/health")

    # Assert - returns 200 with ok status
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_register(server_url):
    # Arrange - server is running via fixture

    # Act - register a test source
    resp = httpx.post(
        f"{server_url}/register", json={"source": "test-bot", "description": "Test"}
    )

    # Assert - registration succeeds and source appears in health
    assert resp.status_code == 200
    assert resp.json()["status"] == "registered"
    health = httpx.get(f"{server_url}/health").json()
    assert "test-bot" in health["registered_sources"]


def test_post_message(server_url):
    # Arrange - server is running via fixture

    # Act - post a message
    resp = httpx.post(
        f"{server_url}/message",
        json={
            "source": "test-bot",
            "chat_id": "msg-1",
            "sender": "tester",
            "content": "Hello",
        },
    )

    # Assert - message is queued
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_message_validation(server_url):
    # Arrange - server is running via fixture

    # Act - post a message with missing required fields
    resp = httpx.post(f"{server_url}/message", json={"source": "test-bot"})

    # Assert - returns 400 for invalid message
    assert resp.status_code == 400


def test_register_validation(server_url):
    # Arrange - server is running via fixture

    # Act - register without a source field
    resp = httpx.post(f"{server_url}/register", json={"description": "no source"})

    # Assert - returns 400 for missing source
    assert resp.status_code == 400


def test_not_found(server_url):
    # Arrange - server is running via fixture

    # Act - request an unknown endpoint
    resp = httpx.get(f"{server_url}/nonexistent")

    # Assert - returns 404
    assert resp.status_code == 404
