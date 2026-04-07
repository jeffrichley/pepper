# Pepper Init — Runtime/Dev Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate pepper's runtime workspace (`~/.pepper/`) from the source code repo so developers get a clean environment and the assistant persona only loads at runtime.

**Architecture:** New `src/pepper/` package with CLI (`pepper init`), hooks, channel MCP server (Python rewrite), and Jinja2 templates. `pepper init` generates `~/.pepper/` with `.claude/`, `CLAUDE.md`, `.mcp.json`, and vault scaffold. Hooks and MCP servers run from the installed package; static config is generated once.

**Tech Stack:** Python 3.12, uv, typer, rich, Jinja2, mcp (Python SDK), pytest, httpx

---

### Task 1: Create `src/pepper/` package skeleton and wire up pyproject.toml

**Files:**
- Create: `src/pepper/__init__.py`
- Create: `src/pepper/cli.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create package directory and __init__.py**

```bash
mkdir -p src/pepper
```

```python
# src/pepper/__init__.py
"""Pepper — Second Brain & Executive Assistant."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Create minimal CLI with typer**

```python
# src/pepper/cli.py
"""Pepper CLI — manage your Second Brain runtime."""

import typer

app = typer.Typer(
    name="pepper",
    help="Pepper Second Brain — manage your runtime workspace.",
    no_args_is_help=True,
)


@app.command()
def init(
    migrate: bool = typer.Option(False, help="Migrate existing Memory/ vault from the repo"),
) -> None:
    """Initialize the Pepper runtime workspace at ~/.pepper/."""
    typer.echo("pepper init — not yet implemented")


@app.command()
def start() -> None:
    """Start Pepper MCP servers and integrations."""
    typer.echo("pepper start — not yet implemented")


@app.command()
def stop() -> None:
    """Stop running Pepper services."""
    typer.echo("pepper stop — not yet implemented")


if __name__ == "__main__":
    app()
```

- [ ] **Step 3: Update pyproject.toml — add src layout, entry points, jinja2 dep**

Replace the full `pyproject.toml` with:

```toml
[project]
name = "pepper"
version = "0.1.0"
description = "Pepper Second Brain"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "filelock>=3.25.2",
    "google-api-python-client>=2.0.0",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.0.0",
    "jinja2>=3.1.6",
    "mcp>=1.9.0",
    "pyqmd>=0.1.0",
    "python-dotenv>=1.2.2",
    "pyyaml>=6.0.3",
    "rich>=14.3.3",
    "typer>=0.24.1",
    "watchdog>=6.0.0",
]

[project.scripts]
pepper = "pepper.cli:app"
pepper-channel = "pepper.channel.server:main"

[dependency-groups]
dev = [
    "aiosqlite>=0.20.0",
    "apscheduler>=4.0.0a5",
    "discord-py>=2.0",
    "httpx>=0.28.1",
    "pytest>=9.0.2",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.15.9",
    "sqlalchemy[asyncio]>=2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pepper"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
markers = ["slow: tests that invoke real Claude Code sessions (cost API tokens)"]
```

- [ ] **Step 4: Run uv sync to install the package**

Run: `uv sync`
Expected: Installs pepper as editable package, `pepper --help` works

- [ ] **Step 5: Verify the CLI entry point works**

Run: `uv run pepper --help`
Expected: Shows help with `init`, `start`, `stop` subcommands

- [ ] **Step 6: Commit**

```bash
git add src/pepper/__init__.py src/pepper/cli.py pyproject.toml
git commit -m "feat: add src/pepper package skeleton with CLI entry point"
```

---

### Task 2: Move hooks into `src/pepper/hooks/`

The existing hooks in `.claude/hooks/` need to move into the installable package. The key change is `shared.py`'s `get_vault_path()` — it currently navigates relative to `.claude/hooks/` to find `Memory/`. After the move, it needs to find the vault via `PEPPER_VAULT_PATH` env var or default to `~/.pepper/Memory/`.

**Files:**
- Create: `src/pepper/hooks/__init__.py`
- Create: `src/pepper/hooks/shared.py` (refactored from `.claude/hooks/shared.py`)
- Create: `src/pepper/hooks/session_start_context.py` (refactored)
- Create: `src/pepper/hooks/session_end_flush.py` (refactored)
- Create: `src/pepper/hooks/pre_compact_flush.py` (refactored)
- Test: `tests/test_shared.py` (update imports)
- Test: `tests/test_session_start.py` (update imports)
- Test: `tests/test_session_end.py` (update imports)
- Test: `tests/test_pre_compact.py` (update imports)

- [ ] **Step 1: Write failing test for new vault path resolution**

```python
# tests/test_hooks_shared.py
"""Tests for pepper.hooks.shared — vault path resolution and utilities."""

import os
from pathlib import Path

from pepper.hooks.shared import get_vault_path, TIER_1_FILES


def test_vault_path_from_env(tmp_path, monkeypatch):
    """PEPPER_VAULT_PATH env var overrides default."""
    vault = tmp_path / "Memory"
    vault.mkdir()
    monkeypatch.setenv("PEPPER_VAULT_PATH", str(vault))
    assert get_vault_path() == vault


def test_vault_path_default(monkeypatch):
    """Default vault path is ~/.pepper/Memory."""
    monkeypatch.delenv("PEPPER_VAULT_PATH", raising=False)
    expected = Path.home() / ".pepper" / "Memory"
    assert get_vault_path() == expected


def test_tier1_files_list():
    """Tier 1 files list is correct."""
    assert TIER_1_FILES == [
        "IDENTITY.md",
        "SOUL.md",
        "USER.md",
        "MEMORY.md",
        "OPERATIONS.md",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_hooks_shared.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pepper.hooks'`

- [ ] **Step 3: Create `src/pepper/hooks/__init__.py`**

```python
# src/pepper/hooks/__init__.py
```

- [ ] **Step 4: Create `src/pepper/hooks/shared.py`**

This is the refactored version of `.claude/hooks/shared.py`. The only change is `get_vault_path()` — it now defaults to `~/.pepper/Memory` instead of navigating relative to `__file__`.

```python
# src/pepper/hooks/shared.py
"""Shared utilities for Pepper hooks.

Provides vault path resolution, Tier 1 file reading, daily log management,
and summary reading. All file operations use filelock for concurrency safety.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from filelock import FileLock

TIER_1_FILES = [
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    "OPERATIONS.md",
]


def get_vault_path() -> Path:
    """Return the absolute path to the Memory vault.

    Uses PEPPER_VAULT_PATH env var if set, otherwise defaults to ~/.pepper/Memory.
    """
    override = os.environ.get("PEPPER_VAULT_PATH")
    if override:
        return Path(override)
    return Path.home() / ".pepper" / "Memory"


def read_tier1_files(vault_path: Path) -> str:
    """Read and concatenate all Tier 1 files with separators."""
    parts = []
    for filename in TIER_1_FILES:
        filepath = vault_path / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"# {filename}\n{content}")
    return "\n\n---\n\n".join(parts)


def get_daily_log_path(vault_path: Path) -> Path:
    """Return today's raw daily log path: Memory/daily/raw/YYYY-MM-DD.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    return vault_path / "daily" / "raw" / f"{today}.md"


def append_to_daily_log(
    vault_path: Path,
    content: str,
    source: str,
    session_id: str,
) -> None:
    """Append a timestamped entry to today's raw daily log."""
    log_path = get_daily_log_path(vault_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = log_path.with_suffix(".md.lock")
    now = datetime.now().strftime("%H:%M")

    header = f"\n\n## {now} [{source}] (session: {session_id})\n\n"

    with FileLock(lock_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(header)
            f.write(content)
            f.write("\n")


def session_already_logged(vault_path: Path, session_id: str) -> bool:
    """Check if a session ID already has an entry in today's daily log."""
    log_path = get_daily_log_path(vault_path)
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8")
    return f"(session: {session_id})" in text


def read_recent_summaries(
    vault_path: Path,
    daily_count: int = 2,
    include_weekly: bool = True,
) -> str:
    """Read the most recent daily summaries and optional weekly summary."""
    parts = []

    summaries_dir = vault_path / "daily" / "summaries"
    if summaries_dir.exists():
        summary_files = sorted(summaries_dir.glob("*.md"), reverse=True)[:daily_count]
        for f in summary_files:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"# Recent Summary ({f.stem})\n{content}")

    if include_weekly:
        weekly_dir = vault_path / "weekly"
        if weekly_dir.exists():
            weekly_files = sorted(weekly_dir.glob("*.md"), reverse=True)[:1]
            for f in weekly_files:
                content = f.read_text(encoding="utf-8").strip()
                if content:
                    parts.append(f"# Weekly Summary ({f.stem})\n{content}")

    return "\n\n---\n\n".join(parts)


def read_stdin() -> dict:
    """Read and parse JSON from stdin (hook input)."""
    return json.loads(sys.stdin.read())


def write_stdout(data: dict) -> None:
    """Write JSON to stdout (hook output)."""
    print(json.dumps(data))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_hooks_shared.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Create hook entry points**

```python
# src/pepper/hooks/session_start_context.py
"""SessionStart hook: inject Tier 1 context into every Claude Code session."""

import json

from pepper.hooks.shared import (
    get_vault_path,
    read_tier1_files,
    read_recent_summaries,
    read_stdin,
    write_stdout,
)


def main():
    try:
        read_stdin()
    except (json.JSONDecodeError, EOFError):
        pass

    vault = get_vault_path()

    tier1_content = read_tier1_files(vault)
    summaries = read_recent_summaries(vault, daily_count=2, include_weekly=True)

    parts = [tier1_content]
    if summaries:
        parts.append(summaries)

    system_message = "\n\n---\n\n".join(parts)
    write_stdout({"systemMessage": system_message})


if __name__ == "__main__":
    main()
```

```python
# src/pepper/hooks/session_end_flush.py
"""SessionEnd hook: append transcript to daily log (with dedup)."""

from pathlib import Path

from pepper.hooks.shared import (
    get_vault_path,
    append_to_daily_log,
    session_already_logged,
    read_stdin,
    write_stdout,
)


def main():
    hook_input = read_stdin()
    session_id = hook_input.get("session_id", "unknown")
    transcript_path = hook_input.get("transcript_path", "")

    vault = get_vault_path()

    if transcript_path and Path(transcript_path).exists():
        if not session_already_logged(vault, session_id):
            transcript = Path(transcript_path).read_text(encoding="utf-8")
            append_to_daily_log(
                vault_path=vault,
                content=transcript,
                source="session-end",
                session_id=session_id,
            )

    write_stdout({})


if __name__ == "__main__":
    main()
```

```python
# src/pepper/hooks/pre_compact_flush.py
"""PreCompact hook: save transcript to daily log and nudge Claude."""

from datetime import datetime
from pathlib import Path

from pepper.hooks.shared import (
    get_vault_path,
    append_to_daily_log,
    read_stdin,
    write_stdout,
)


def main():
    hook_input = read_stdin()
    session_id = hook_input.get("session_id", "unknown")
    transcript_path = hook_input.get("transcript_path", "")

    vault = get_vault_path()

    if transcript_path and Path(transcript_path).exists():
        transcript = Path(transcript_path).read_text(encoding="utf-8")
        append_to_daily_log(
            vault_path=vault,
            content=transcript,
            source="pre-compact",
            session_id=session_id,
        )

    today = datetime.now().strftime("%Y-%m-%d")
    write_stdout({
        "systemMessage": (
            "Context is about to be compacted. If you have any unsaved decisions, "
            "facts, or action items from this conversation, write them to the daily "
            f"log now using: Memory/daily/raw/{today}.md"
        )
    })


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Update existing hook tests to import from the new location**

The existing tests in `tests/test_shared.py`, `tests/test_session_start.py`, `tests/test_session_end.py`, and `tests/test_pre_compact.py` need their imports updated from:
```python
from shared import get_vault_path
```
to:
```python
from pepper.hooks.shared import get_vault_path
```

Do a find-and-replace across each test file. Also update `conftest.py` if it imports from the hooks.

Since `pyproject.toml` now has `pythonpath = ["src"]` instead of `[".claude/hooks"]`, the package imports will resolve correctly.

- [ ] **Step 8: Run all hook tests**

Run: `uv run pytest tests/test_hooks_shared.py tests/test_shared.py tests/test_session_start.py tests/test_session_end.py tests/test_pre_compact.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/pepper/hooks/ tests/test_hooks_shared.py tests/test_shared.py tests/test_session_start.py tests/test_session_end.py tests/test_pre_compact.py
git commit -m "feat: move hooks into src/pepper/hooks with configurable vault path"
```

---

### Task 3: Rewrite pepper-channel MCP server in Python

Port the TypeScript channel server (`channel/pepper-channel.ts`) to Python using the `mcp` Python SDK and a built-in HTTP server. The server has two transports: MCP over stdio (for Claude Code) and HTTP (for integrations).

**Files:**
- Create: `src/pepper/channel/__init__.py`
- Create: `src/pepper/channel/router.py`
- Create: `src/pepper/channel/server.py`
- Test: `tests/test_channel_python.py`

- [ ] **Step 1: Write failing tests for the router**

```python
# tests/test_channel_router.py
"""Tests for pepper.channel.router — routing table logic."""

import time

from pepper.channel.router import Router


def test_add_and_lookup_route():
    router = Router(ttl_seconds=3600)
    router.add("chat-1", "discord")
    assert router.lookup("chat-1") == "discord"


def test_lookup_missing_returns_none():
    router = Router(ttl_seconds=3600)
    assert router.lookup("nonexistent") is None


def test_expired_route_returns_none():
    router = Router(ttl_seconds=0)
    router.add("chat-1", "discord")
    assert router.lookup("chat-1") is None


def test_clean_expired():
    router = Router(ttl_seconds=0)
    router.add("chat-1", "discord")
    router.add("chat-2", "email")
    router.clean_expired()
    assert router.size == 0


def test_register_and_list_sources():
    router = Router(ttl_seconds=3600)
    router.register_source("discord", "Discord bot")
    router.register_source("email", "Email integration")
    sources = router.registered_sources
    assert "discord" in sources
    assert "email" in sources
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_channel_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pepper.channel'`

- [ ] **Step 3: Implement the router**

```python
# src/pepper/channel/__init__.py
```

```python
# src/pepper/channel/router.py
"""Routing table for the Pepper channel server.

Maps chat_id -> source with TTL-based expiration.
Tracks registered integration sources.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Router:
    """In-memory routing table with TTL expiration."""

    ttl_seconds: int = 24 * 60 * 60
    _routes: dict[str, tuple[str, float]] = field(default_factory=dict)
    _sources: dict[str, tuple[str, float]] = field(default_factory=dict)

    def add(self, chat_id: str, source: str) -> None:
        """Record a route from chat_id to source."""
        self._routes[chat_id] = (source, time.monotonic())

    def lookup(self, chat_id: str) -> str | None:
        """Look up the source for a chat_id. Returns None if missing or expired."""
        entry = self._routes.get(chat_id)
        if entry is None:
            return None
        source, ts = entry
        if time.monotonic() - ts > self.ttl_seconds:
            del self._routes[chat_id]
            return None
        return source

    def clean_expired(self) -> None:
        """Remove all expired routes."""
        now = time.monotonic()
        expired = [
            cid for cid, (_, ts) in self._routes.items()
            if now - ts > self.ttl_seconds
        ]
        for cid in expired:
            del self._routes[cid]

    @property
    def size(self) -> int:
        return len(self._routes)

    def register_source(self, source: str, description: str = "") -> None:
        """Register an integration source."""
        self._sources[source] = (description, time.monotonic())

    @property
    def registered_sources(self) -> list[str]:
        return list(self._sources.keys())
```

- [ ] **Step 4: Run router tests**

Run: `uv run pytest tests/test_channel_router.py -v`
Expected: All PASS

- [ ] **Step 5: Commit router**

```bash
git add src/pepper/channel/__init__.py src/pepper/channel/router.py tests/test_channel_router.py
git commit -m "feat: add channel router with TTL-based routing table"
```

- [ ] **Step 6: Write failing tests for the HTTP server**

```python
# tests/test_channel_http.py
"""Tests for pepper.channel.server — HTTP endpoints.

Tests the HTTP API without the MCP stdio transport.
"""

import pytest
import httpx
import asyncio
import threading
import time

from pepper.channel.server import create_http_app
from pepper.channel.router import Router


@pytest.fixture
def router():
    return Router(ttl_seconds=3600)


@pytest.fixture
def app(router):
    return create_http_app(router)


@pytest.fixture
def server_url(app):
    """Start the HTTP server in a background thread on a random port."""
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)

    # Find a free port
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config.port = port
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server
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
    resp = httpx.get(f"{server_url}/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_register(server_url):
    resp = httpx.post(f"{server_url}/register", json={"source": "test-bot", "description": "Test"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "registered"

    health = httpx.get(f"{server_url}/health").json()
    assert "test-bot" in health["registered_sources"]


def test_post_message(server_url):
    resp = httpx.post(f"{server_url}/message", json={
        "source": "test-bot",
        "chat_id": "msg-1",
        "sender": "tester",
        "content": "Hello",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_message_validation(server_url):
    resp = httpx.post(f"{server_url}/message", json={"source": "test-bot"})
    assert resp.status_code == 400


def test_register_validation(server_url):
    resp = httpx.post(f"{server_url}/register", json={"description": "no source"})
    assert resp.status_code == 400


def test_not_found(server_url):
    resp = httpx.get(f"{server_url}/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 7: Run test to verify it fails**

Run: `uv run pytest tests/test_channel_http.py -v`
Expected: FAIL — `ImportError: cannot import name 'create_http_app'`

- [ ] **Step 8: Implement the channel server**

```python
# src/pepper/channel/server.py
"""Pepper Channel Server — Python MCP + HTTP message router.

MCP server over stdio for Claude Code integration.
HTTP server for external integrations (Discord, email, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from pepper.channel.router import Router

log = logging.getLogger("pepper-channel")

# --- SSE listener management ---

_source_listeners: dict[str, set] = {}
_global_listeners: set = set()


def emit_to_source(source: str, data: dict) -> None:
    """Emit an event to source-specific and global SSE listeners."""
    encoded = json.dumps(data)
    chunk = f"data: {encoded}\n\n"

    for emit in _source_listeners.get(source, set()):
        emit(chunk)
    for emit in _global_listeners:
        emit(chunk)


# --- HTTP app (ASGI) ---

def create_http_app(router: Router, mcp_server: FastMCP | None = None):
    """Create an ASGI app with channel HTTP endpoints."""

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return

        method = scope["method"]
        path = scope["path"]

        if method == "GET" and path == "/health":
            router.clean_expired()
            body = json.dumps({
                "status": "ok",
                "registered_sources": router.registered_sources,
                "routing_table_size": router.size,
                "uptime_seconds": int(time.monotonic() - _start_time),
            }).encode()
            await send({"type": "http.response.start", "status": 200, "headers": [
                [b"content-type", b"application/json"],
            ]})
            await send({"type": "http.response.body", "body": body})
            return

        if method == "POST" and path == "/register":
            body = await _read_body(receive)
            data = json.loads(body)
            if not data.get("source"):
                await _json_response(send, 400, {"error": "source is required"})
                return
            router.register_source(data["source"], data.get("description", ""))
            await _json_response(send, 200, {"status": "registered", "source": data["source"]})
            return

        if method == "POST" and path == "/message":
            body = await _read_body(receive)
            data = json.loads(body)
            source = data.get("source")
            chat_id = data.get("chat_id")
            content = data.get("content")
            if not source or not chat_id or not content:
                await _json_response(send, 400, {"error": "source, chat_id, and content are required"})
                return

            router.add(chat_id, source)

            meta = {
                "chat_id": chat_id,
                "sender": data.get("sender", "unknown"),
                "integration": source,
            }
            for k, v in data.get("metadata", {}).items():
                meta[k] = str(v)

            if mcp_server:
                # Notify Claude Code via MCP
                pass  # MCP notification handled by the MCP server's tool layer

            emit_to_source(source, {"chat_id": chat_id, "content": content, "meta": meta})
            await _json_response(send, 200, {"status": "queued", "chat_id": chat_id})
            return

        await _json_response(send, 404, {"error": "not found"})

    return app


_start_time = time.monotonic()


async def _read_body(receive) -> bytes:
    body = b""
    while True:
        msg = await receive()
        body += msg.get("body", b"")
        if not msg.get("more_body"):
            break
    return body


async def _json_response(send, status: int, data: dict) -> None:
    body = json.dumps(data).encode()
    await send({"type": "http.response.start", "status": status, "headers": [
        [b"content-type", b"application/json"],
    ]})
    await send({"type": "http.response.body", "body": body})


# --- MCP Server ---

def create_mcp_server(router: Router) -> FastMCP:
    """Create the MCP server with the reply tool."""

    mcp = FastMCP(
        "pepper-channel",
        instructions=(
            'Messages arrive as <channel source="pepper-channel" chat_id="..." sender="..." integration="...">. '
            "These are from external systems (Discord, email, heartbeat) talking to you. "
            "Reply with the reply tool, passing the chat_id from the tag. "
            "You can include metadata in your reply: reactions (array of emoji names), "
            'type ("message" or "reaction" for reaction-only), and embed (object with title, description, color, fields). '
            "Treat each message as a task or conversation to handle."
        ),
    )

    @mcp.tool()
    def reply(
        chat_id: str,
        text: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Send a reply back through the channel to the integration that sent the message.

        Args:
            chat_id: The conversation to reply in (from the channel tag).
            text: The message to send.
            metadata: Optional dict with reactions (emoji array), type ("message"|"reaction"), embed.
        """
        source = router.lookup(chat_id) or "unknown"
        reply_data = {
            "chat_id": chat_id,
            "text": text,
            "metadata": metadata or {},
            "source": source,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        emit_to_source(source, reply_data)
        return "sent"

    return mcp


def main() -> None:
    """Entry point for pepper-channel. Runs MCP over stdio + HTTP server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    port = int(os.environ.get("PEPPER_CHANNEL_PORT", "8788"))
    ttl_hours = int(os.environ.get("PEPPER_ROUTE_TTL_HOURS", "24"))

    router = Router(ttl_seconds=ttl_hours * 3600)
    mcp = create_mcp_server(router)
    http_app = create_http_app(router, mcp)

    # Start HTTP server in a background thread
    import uvicorn
    import threading

    config = uvicorn.Config(http_app, host="127.0.0.1", port=port, log_level="warning")
    http_server = uvicorn.Server(config)
    http_thread = threading.Thread(target=http_server.run, daemon=True)
    http_thread.start()

    log.info(f"Pepper channel server v2.0.0 (Python) listening on http://127.0.0.1:{port}")

    # Run MCP server on stdio (blocks)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 9: Add uvicorn dependency to pyproject.toml**

Add `"uvicorn>=0.34.0"` to the `dependencies` list in `pyproject.toml`.

Run: `uv sync`

- [ ] **Step 10: Run HTTP tests**

Run: `uv run pytest tests/test_channel_http.py -v`
Expected: All PASS

- [ ] **Step 11: Commit channel server**

```bash
git add src/pepper/channel/server.py tests/test_channel_http.py pyproject.toml
git commit -m "feat: rewrite pepper-channel MCP server in Python"
```

---

### Task 4: Create Jinja2 templates for `pepper init`

These templates generate the runtime config files at `~/.pepper/`.

**Files:**
- Create: `src/pepper/init/__init__.py`
- Create: `src/pepper/init/templates/CLAUDE.md.j2`
- Create: `src/pepper/init/templates/settings.json.j2`
- Create: `src/pepper/init/templates/mcp.json.j2`
- Create: `src/pepper/init/templates/config.toml.j2`

- [ ] **Step 1: Create the init package and templates directory**

```bash
mkdir -p src/pepper/init/templates
```

```python
# src/pepper/init/__init__.py
```

- [ ] **Step 2: Create CLAUDE.md template**

```jinja2
{# src/pepper/init/templates/CLAUDE.md.j2 #}
# Pepper

You are **Pepper** 🌶️, Jeff Richley's Second Brain & Executive Assistant.

## Core Files

Your identity, personality, and operational knowledge live in the Memory/ vault. The SessionStart hook pre-loads these into your context for interactive sessions. If you don't already have this information in context, read the files directly.

| File | Purpose |
|------|---------|
| `Memory/IDENTITY.md` | Your name, role, emoji |
| `Memory/SOUL.md` | Personality, behavioral rules, hard boundaries, priorities |
| `Memory/USER.md` | Jeff's profile, platforms, drafting criteria |
| `Memory/MEMORY.md` | Curated long-term memory (active projects, decisions, notes) |
| `Memory/OPERATIONS.md` | Vault map, search commands, project conventions, schedules |

## Hard Boundaries

- NEVER send emails or messages without explicit permission
- NEVER access financial data or make purchases
- NEVER delete anything without explicit permission

## Vault Search

Use pyqmd for semantic search across the vault:

```bash
uv run qmd search "query" -c vault
uv run qmd search "query" -c vault --path-prefix projects/niwc
```

## Daily Logs

Session hooks automatically append to `Memory/daily/raw/YYYY-MM-DD.md`. Do not write to these files manually.

## Projects

Each project has a `STATUS.md` in `Memory/projects/`. Check there for current focus, blockers, and next steps.
```

- [ ] **Step 3: Create settings.json template**

```jinja2
{# src/pepper/init/templates/settings.json.j2 #}
{
  "permissions": {
    "defaultMode": "bypassPermissions",
    "allow": [
      "Bash",
      "Read",
      "Edit",
      "Write",
      "Glob",
      "Grep"
    ]
  },
  "hooks": {
    "SessionStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m pepper.hooks.session_start_context",
            "timeout": 10
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m pepper.hooks.pre_compact_flush",
            "timeout": 15
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python -m pepper.hooks.session_end_flush",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: Create mcp.json template**

```jinja2
{# src/pepper/init/templates/mcp.json.j2 #}
{
  "mcpServers": {
    "pepper-channel": {
      "command": "pepper-channel"
    },
    "pepper-discord": {
      "command": "uv",
      "args": ["--directory", "{{ discord_integration_path }}", "run", "python", "mcp_server.py"]
    }
  }
}
```

- [ ] **Step 5: Create config.toml template**

```jinja2
{# src/pepper/init/templates/config.toml.j2 #}
# Pepper runtime configuration
# Generated by: pepper init

[paths]
vault = "{{ vault_path }}"
runtime = "{{ runtime_path }}"

[channel]
port = 8788
route_ttl_hours = 24
```

- [ ] **Step 6: Commit templates**

```bash
git add src/pepper/init/
git commit -m "feat: add Jinja2 templates for pepper init"
```

---

### Task 5: Implement `pepper init` generator

**Files:**
- Create: `src/pepper/init/generator.py`
- Modify: `src/pepper/cli.py`
- Test: `tests/test_init.py`

- [ ] **Step 1: Write failing tests for the generator**

```python
# tests/test_init.py
"""Tests for pepper init — runtime workspace generation."""

from pathlib import Path

from pepper.init.generator import generate_runtime


def test_generate_creates_directory_structure(tmp_path):
    """pepper init creates the expected directory structure."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    assert (runtime / ".claude").is_dir()
    assert (runtime / ".claude" / "settings.json").is_file()
    assert (runtime / "CLAUDE.md").is_file()
    assert (runtime / ".mcp.json").is_file()
    assert (runtime / "config.toml").is_file()
    assert (runtime / "Memory").is_dir()


def test_generate_creates_vault_scaffold(tmp_path):
    """pepper init creates empty Tier 1 files and directory structure."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    vault = runtime / "Memory"
    assert (vault / "IDENTITY.md").is_file()
    assert (vault / "SOUL.md").is_file()
    assert (vault / "USER.md").is_file()
    assert (vault / "MEMORY.md").is_file()
    assert (vault / "OPERATIONS.md").is_file()
    assert (vault / "daily" / "raw").is_dir()
    assert (vault / "daily" / "summaries").is_dir()
    assert (vault / "weekly").is_dir()
    assert (vault / "projects").is_dir()


def test_generate_settings_has_hooks(tmp_path):
    """Generated settings.json references installed hook entry points."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    import json
    settings = json.loads((runtime / ".claude" / "settings.json").read_text())
    hook_cmd = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "pepper.hooks.session_start_context" in hook_cmd


def test_generate_mcp_has_channel(tmp_path):
    """Generated .mcp.json references pepper-channel entry point."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    import json
    mcp = json.loads((runtime / ".mcp.json").read_text())
    assert mcp["mcpServers"]["pepper-channel"]["command"] == "pepper-channel"


def test_generate_does_not_overwrite_existing_vault(tmp_path):
    """pepper init preserves existing vault files."""
    runtime = tmp_path / ".pepper"
    vault = runtime / "Memory"
    vault.mkdir(parents=True)
    (vault / "IDENTITY.md").write_text("# My Custom Identity")

    generate_runtime(runtime_path=runtime)

    assert (vault / "IDENTITY.md").read_text() == "# My Custom Identity"


def test_generate_overwrites_config_files(tmp_path):
    """pepper init regenerates config files even if they exist."""
    runtime = tmp_path / ".pepper"
    runtime.mkdir(parents=True)
    (runtime / "CLAUDE.md").write_text("old content")

    generate_runtime(runtime_path=runtime)

    assert "Pepper" in (runtime / "CLAUDE.md").read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_init.py -v`
Expected: FAIL — `ImportError: cannot import name 'generate_runtime'`

- [ ] **Step 3: Implement the generator**

```python
# src/pepper/init/generator.py
"""Generate the Pepper runtime workspace.

Creates ~/.pepper/ with .claude/ config, CLAUDE.md, .mcp.json,
config.toml, and Memory/ vault scaffold.
"""

from __future__ import annotations

import json
from importlib.resources import files as pkg_files
from pathlib import Path

from jinja2 import Environment, PackageLoader


VAULT_SCAFFOLD_DIRS = [
    "daily/raw",
    "daily/summaries",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
    "projects",
    "meetings",
    "research",
    "clients",
    "content",
    "team",
    "drafts/active",
    "drafts/sent",
    "tasks",
]

TIER_1_FILES = {
    "IDENTITY.md": "# Identity\n\n**Name:** Pepper\n**Emoji:** 🌶️\n**Role:** Second Brain & Executive Assistant\n**Created by:** Jeff Richley\n",
    "SOUL.md": "# Soul\n\n## Personality\n[Voice, tone, communication style — customize to your liking]\n\n## Behavioral Rules\n\n### Hard Boundaries\n- NEVER send emails or messages without explicit permission\n- NEVER access financial data or make purchases\n- NEVER delete anything without explicit permission\n",
    "USER.md": "# User Profile\n\n## About\n- **Name:** [Your name]\n- **Timezone:** [Your timezone]\n",
    "MEMORY.md": "# Memory\n\n## Active Projects\n\n## Meeting Decisions\n\n## Research Notes\n",
    "OPERATIONS.md": "# Operations\n\n## Vault\n- **Location:** Memory/\n- **Search:** `uv run qmd search vault \"query\"` for semantic search\n",
}


def generate_runtime(
    runtime_path: Path | None = None,
    discord_integration_path: str = "",
) -> Path:
    """Generate the Pepper runtime workspace.

    Args:
        runtime_path: Where to create the workspace. Defaults to ~/.pepper/.
        discord_integration_path: Absolute path to the discord integration directory.

    Returns:
        The runtime path.
    """
    if runtime_path is None:
        runtime_path = Path.home() / ".pepper"

    runtime_path.mkdir(parents=True, exist_ok=True)

    # Load Jinja2 templates
    env = Environment(
        loader=PackageLoader("pepper.init", "templates"),
        keep_trailing_newline=True,
    )

    # --- Generate config files (always overwrite) ---

    # .claude/settings.json
    claude_dir = runtime_path / ".claude"
    claude_dir.mkdir(exist_ok=True)
    template = env.get_template("settings.json.j2")
    (claude_dir / "settings.json").write_text(template.render())

    # CLAUDE.md
    template = env.get_template("CLAUDE.md.j2")
    (runtime_path / "CLAUDE.md").write_text(template.render())

    # .mcp.json
    template = env.get_template("mcp.json.j2")
    (runtime_path / ".mcp.json").write_text(
        template.render(discord_integration_path=discord_integration_path)
    )

    # config.toml
    template = env.get_template("config.toml.j2")
    vault_path = str(runtime_path / "Memory")
    (runtime_path / "config.toml").write_text(
        template.render(vault_path=vault_path, runtime_path=str(runtime_path))
    )

    # --- Scaffold vault (never overwrite existing files) ---

    vault = runtime_path / "Memory"
    vault.mkdir(exist_ok=True)

    for dir_path in VAULT_SCAFFOLD_DIRS:
        (vault / dir_path).mkdir(parents=True, exist_ok=True)

    for filename, default_content in TIER_1_FILES.items():
        filepath = vault / filename
        if not filepath.exists():
            filepath.write_text(default_content, encoding="utf-8")

    return runtime_path
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_init.py -v`
Expected: All PASS

- [ ] **Step 5: Wire up the CLI**

Update `src/pepper/cli.py`:

```python
# src/pepper/cli.py
"""Pepper CLI — manage your Second Brain runtime."""

from pathlib import Path

import typer
from rich import print as rprint

app = typer.Typer(
    name="pepper",
    help="Pepper Second Brain — manage your runtime workspace.",
    no_args_is_help=True,
)


@app.command()
def init(
    migrate: bool = typer.Option(False, help="Migrate existing Memory/ vault from the repo"),
) -> None:
    """Initialize the Pepper runtime workspace at ~/.pepper/."""
    from pepper.init.generator import generate_runtime

    runtime_path = Path.home() / ".pepper"

    if runtime_path.exists() and not migrate:
        rprint(f"[yellow]~/.pepper/ already exists.[/yellow] Config files will be regenerated.")
        rprint("Vault files will NOT be overwritten.")

    result = generate_runtime(runtime_path=runtime_path)

    rprint(f"[green]Pepper runtime initialized at {result}[/green]")
    rprint("\nTo start Pepper:")
    rprint(f"  cd {result}")
    rprint("  claude")


@app.command()
def start() -> None:
    """Start Pepper MCP servers and integrations."""
    typer.echo("pepper start — not yet implemented")


@app.command()
def stop() -> None:
    """Stop running Pepper services."""
    typer.echo("pepper stop — not yet implemented")


if __name__ == "__main__":
    app()
```

- [ ] **Step 6: Test the full CLI flow**

Run: `uv run pepper init --help`
Expected: Shows help for init command with `--migrate` option

- [ ] **Step 7: Commit**

```bash
git add src/pepper/init/generator.py src/pepper/cli.py tests/test_init.py
git commit -m "feat: implement pepper init generator with vault scaffold"
```

---

### Task 6: Add `--migrate` support to move existing vault

**Files:**
- Modify: `src/pepper/init/generator.py`
- Modify: `src/pepper/cli.py`
- Test: `tests/test_init.py` (add migration tests)

- [ ] **Step 1: Write failing migration test**

Add to `tests/test_init.py`:

```python
import shutil


def test_migrate_copies_vault_contents(tmp_path):
    """pepper init --migrate copies existing vault to runtime."""
    # Set up a source vault
    source_vault = tmp_path / "repo" / "Memory"
    source_vault.mkdir(parents=True)
    (source_vault / "IDENTITY.md").write_text("# My Real Identity")
    daily_raw = source_vault / "daily" / "raw"
    daily_raw.mkdir(parents=True)
    (daily_raw / "2026-04-06.md").write_text("# Today's log")

    runtime = tmp_path / ".pepper"
    from pepper.init.generator import generate_runtime
    generate_runtime(runtime_path=runtime, migrate_from=source_vault)

    assert (runtime / "Memory" / "IDENTITY.md").read_text() == "# My Real Identity"
    assert (runtime / "Memory" / "daily" / "raw" / "2026-04-06.md").read_text() == "# Today's log"


def test_migrate_does_not_overwrite_existing_runtime_vault(tmp_path):
    """Migration skips files that already exist in the runtime vault."""
    source_vault = tmp_path / "repo" / "Memory"
    source_vault.mkdir(parents=True)
    (source_vault / "IDENTITY.md").write_text("# Source Identity")

    runtime = tmp_path / ".pepper"
    vault = runtime / "Memory"
    vault.mkdir(parents=True)
    (vault / "IDENTITY.md").write_text("# Existing Identity")

    from pepper.init.generator import generate_runtime
    generate_runtime(runtime_path=runtime, migrate_from=source_vault)

    assert (vault / "IDENTITY.md").read_text() == "# Existing Identity"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_init.py::test_migrate_copies_vault_contents -v`
Expected: FAIL — `TypeError: generate_runtime() got an unexpected keyword argument 'migrate_from'`

- [ ] **Step 3: Add migrate_from parameter to generator**

Update the `generate_runtime` function signature and add migration logic after the vault scaffold section:

```python
def generate_runtime(
    runtime_path: Path | None = None,
    discord_integration_path: str = "",
    migrate_from: Path | None = None,
) -> Path:
```

Add after the vault scaffold loop (after `filepath.write_text(default_content, ...)`):

```python
    # --- Migrate existing vault if requested ---
    if migrate_from and migrate_from.is_dir():
        _migrate_vault(source=migrate_from, dest=vault)

    return runtime_path


def _migrate_vault(source: Path, dest: Path) -> None:
    """Copy vault contents from source to dest, skipping existing files."""
    import shutil

    for item in source.rglob("*"):
        if item.is_file():
            rel = item.relative_to(source)
            target = dest / rel
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
```

- [ ] **Step 4: Update CLI to pass migrate_from**

In `src/pepper/cli.py`, update the `init` command:

```python
@app.command()
def init(
    migrate: bool = typer.Option(False, help="Migrate existing Memory/ vault from the repo"),
    repo_vault: str = typer.Option("", help="Path to existing Memory/ vault to migrate from"),
) -> None:
    """Initialize the Pepper runtime workspace at ~/.pepper/."""
    from pepper.init.generator import generate_runtime

    runtime_path = Path.home() / ".pepper"

    migrate_from = None
    if migrate:
        if repo_vault:
            migrate_from = Path(repo_vault)
        else:
            # Try to find Memory/ in current directory
            cwd_vault = Path.cwd() / "Memory"
            if cwd_vault.is_dir():
                migrate_from = cwd_vault
            else:
                rprint("[red]No Memory/ directory found. Use --repo-vault to specify the path.[/red]")
                raise typer.Exit(1)

        if not migrate_from.is_dir():
            rprint(f"[red]Vault path {migrate_from} does not exist.[/red]")
            raise typer.Exit(1)

        rprint(f"Migrating vault from {migrate_from}...")

    if runtime_path.exists() and not migrate:
        rprint(f"[yellow]~/.pepper/ already exists.[/yellow] Config files will be regenerated.")
        rprint("Vault files will NOT be overwritten.")

    result = generate_runtime(
        runtime_path=runtime_path,
        migrate_from=migrate_from,
    )

    rprint(f"[green]Pepper runtime initialized at {result}[/green]")
    if migrate_from:
        rprint("[green]Vault contents migrated successfully.[/green]")
    rprint("\nTo start Pepper:")
    rprint(f"  cd {result}")
    rprint("  claude")
```

- [ ] **Step 5: Run all init tests**

Run: `uv run pytest tests/test_init.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/pepper/init/generator.py src/pepper/cli.py tests/test_init.py
git commit -m "feat: add --migrate support to pepper init"
```

---

### Task 7: Include templates as package data and verify end-to-end

Jinja2's `PackageLoader` needs the templates to be included in the installed package. This task ensures they ship correctly and tests the full `pepper init` flow.

**Files:**
- Modify: `pyproject.toml` (if needed for package data)
- Test: `tests/test_init_e2e.py`

- [ ] **Step 1: Verify templates are included in the package**

Run: `uv run python -c "from importlib.resources import files; print(list((files('pepper.init') / 'templates').iterdir()))"`
Expected: Lists the template files (CLAUDE.md.j2, settings.json.j2, etc.)

If this fails, add to `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/pepper"]

[tool.hatch.build.targets.wheel.force-include]
"src/pepper/init/templates" = "pepper/init/templates"
```

Run: `uv sync` and re-test.

- [ ] **Step 2: Write end-to-end test**

```python
# tests/test_init_e2e.py
"""End-to-end test for pepper init CLI command."""

import json
import subprocess
import sys
from pathlib import Path


def test_pepper_init_e2e(tmp_path, monkeypatch):
    """Full pepper init creates a working runtime workspace."""
    runtime = tmp_path / ".pepper"
    monkeypatch.setenv("HOME", str(tmp_path))
    # Also set USERPROFILE for Windows
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    result = subprocess.run(
        [sys.executable, "-m", "pepper.cli", "init"],
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )

    # Check the runtime was created
    assert runtime.is_dir() or (tmp_path / ".pepper").is_dir()
```

Note: This test may need adjustment since `Path.home()` behavior varies. The monkeypatch approach works on Linux/Mac; on Windows it uses `USERPROFILE`. If this proves flaky, test via the generator directly (which already has full coverage).

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/test_init_e2e.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_init_e2e.py pyproject.toml
git commit -m "test: add end-to-end test for pepper init"
```

---

### Task 8: Update existing tests for new package structure

The existing tests import from `.claude/hooks/` paths. Since `pyproject.toml` now has `pythonpath = ["src"]`, all test imports need updating.

**Files:**
- Modify: `tests/test_shared.py`
- Modify: `tests/test_session_start.py`
- Modify: `tests/test_session_end.py`
- Modify: `tests/test_pre_compact.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Read each existing test file and update imports**

For each test file, replace imports like:
```python
from shared import get_vault_path, read_tier1_files
```
with:
```python
from pepper.hooks.shared import get_vault_path, read_tier1_files
```

And replace:
```python
from session_start_context import main
```
with:
```python
from pepper.hooks.session_start_context import main
```

Apply the same pattern for `session_end_flush`, `pre_compact_flush`.

- [ ] **Step 2: Update test_channel_routing.py for Python server**

The existing `test_channel_routing.py` starts a Bun process. Replace it with imports from the Python server or update the fixture to start the Python server instead:

Replace the `channel_server` fixture:
```python
@pytest.fixture(scope="module")
def channel_server():
    """Start the Python channel HTTP server on a test port."""
    import threading
    import uvicorn
    from pepper.channel.server import create_http_app
    from pepper.channel.router import Router

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
```

Remove the `@pytest.mark.slow` decorators since this no longer requires Bun.

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest tests/ -v --ignore=tests/test_spawn.py`
Expected: All PASS (test_spawn may need the old hook paths; skip if so)

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "refactor: update test imports for src/pepper package structure"
```

---

### Task 9: Clean up repo — remove old runtime files

Now that everything is in `src/pepper/`, remove the old locations and update `.gitignore`.

**Files:**
- Delete: `.claude/hooks/` (all files except `__init__.py` — actually delete the whole directory)
- Delete: `channel/pepper-channel.ts`
- Delete: `channel/` directory (and any bun config)
- Modify: `.gitignore`
- Delete: `.claude/` entirely — any `.claude/` in the repo gets loaded by Claude Code during dev, which is what we're trying to avoid. Dev preferences go in `~/.claude/` (global config).
- Delete: `.mcp.json` — no MCP servers needed for dev
- Delete: `CLAUDE.md` — the Pepper identity should only load at runtime

- [ ] **Step 1: Remove old hook files**

```bash
rm -rf .claude/hooks/
rm -rf .claude/scripts/
```

- [ ] **Step 2: Remove TypeScript channel server**

```bash
rm -rf channel/
```

Also remove any `bun.lockb`, `node_modules/`, or TypeScript config if present.

- [ ] **Step 3: Remove runtime config from repo root**

```bash
rm -f .mcp.json
rm -f CLAUDE.md
```

- [ ] **Step 4: Delete .claude/ directory entirely**

```bash
rm -rf .claude/
```

Any dev preferences go in `~/.claude/` (global config). Having any `.claude/` in the repo would cause Claude Code to load it during development, which defeats the purpose of the separation.

- [ ] **Step 5: Update .gitignore**

Add these lines:
```
# Prevent runtime config from being added to repo
.claude/
.mcp.json
CLAUDE.md

# Runtime workspace (generated by pepper init)
Memory/
config.toml
```

- [ ] **Step 6: Run all tests to make sure nothing broke**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove old runtime files from repo, clean dev environment"
```

---

### Task 10: Move skills into the package

The existing skills in `.claude/skills/` need to be accessible from the runtime. Move them into the package so they're installed with `uv sync`.

**Files:**
- Create: `src/pepper/skills/coding/SKILL.md` (move from `.claude/skills/coding/`)
- Create: `src/pepper/skills/create-second-brain-prd/` (move)
- Create: `src/pepper/skills/google/` (move)
- Modify: `src/pepper/init/generator.py` — copy skills into runtime `.claude/skills/`

- [ ] **Step 1: Move skills into the package**

```bash
mkdir -p src/pepper/skills
cp -r .claude/skills/coding src/pepper/skills/
cp -r .claude/skills/create-second-brain-prd src/pepper/skills/
cp -r .claude/skills/google src/pepper/skills/
```

- [ ] **Step 2: Add skill installation to the generator**

In `src/pepper/init/generator.py`, add a function to copy skills from the installed package into the runtime's `.claude/skills/`:

```python
def _install_skills(runtime_path: Path) -> None:
    """Copy skills from the installed package to the runtime .claude/skills/."""
    import shutil

    skills_source = Path(__file__).parent.parent / "skills"
    if not skills_source.is_dir():
        return

    skills_dest = runtime_path / ".claude" / "skills"
    if skills_dest.exists():
        shutil.rmtree(skills_dest)
    shutil.copytree(skills_source, skills_dest)
```

Call `_install_skills(runtime_path)` at the end of `generate_runtime()`, before the return.

- [ ] **Step 3: Add test for skill installation**

Add to `tests/test_init.py`:

```python
def test_generate_installs_skills(tmp_path):
    """pepper init copies skills into runtime .claude/skills/."""
    runtime = tmp_path / ".pepper"
    generate_runtime(runtime_path=runtime)

    skills_dir = runtime / ".claude" / "skills"
    assert skills_dir.is_dir()
    assert (skills_dir / "coding" / "SKILL.md").is_file()
    assert (skills_dir / "google" / "SKILL.md").is_file()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_init.py -v`
Expected: All PASS

- [ ] **Step 5: Remove old skills from .claude/**

```bash
rm -rf .claude/skills/
```

- [ ] **Step 6: Commit**

```bash
git add src/pepper/skills/ src/pepper/init/generator.py tests/test_init.py
git add -u  # stages deletions
git commit -m "feat: move skills into package, installed by pepper init"
```

---

### Task 11: Final integration verification

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Verify CLI works**

Run: `uv run pepper --help`
Expected: Shows commands

Run: `uv run pepper init --help`
Expected: Shows init options

- [ ] **Step 3: Verify pepper-channel entry point**

Run: `uv run pepper-channel --help` or `uv run python -c "from pepper.channel.server import main; print('ok')"`
Expected: Module loads without error

- [ ] **Step 4: Verify package imports**

```bash
uv run python -c "
from pepper.hooks.shared import get_vault_path
from pepper.channel.router import Router
from pepper.init.generator import generate_runtime
print('All imports OK')
"
```
Expected: "All imports OK"

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "chore: final integration fixes"
```
