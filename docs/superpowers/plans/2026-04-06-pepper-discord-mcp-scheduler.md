# Pepper Discord MCP + Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Pepper outbound Discord capabilities (send messages, read channels, react) and a scheduler for proactive tasks (heartbeat, briefing, reflection), all managed via MCP tools.

**Architecture:** A single Python process serves as both a Discord bot and an MCP server. Claude Code spawns it via `.mcp.json`. It runs the Discord client, an APScheduler 4.x instance, and an SSE listener in one async event loop. The FastMCP lifespan starts Discord and the scheduler on startup. APScheduler persists jobs to SQLite. Default jobs (heartbeat, briefing, reflection) are seeded from `jobs.yaml` on first run.

**Tech Stack:** Python 3.12, discord.py 2.7+, mcp (Python SDK), APScheduler 4.x, SQLAlchemy (SQLite), httpx, PyYAML, uv

**Spec:** `docs/superpowers/specs/2026-04-06-pepper-discord-mcp-scheduler-design.md`

**Working directory:** `E:\workspaces\ai\pepper` (main branch)

---

## File Structure

```
integrations/discord/
  pyproject.toml          # Updated: add mcp, apscheduler, sqlalchemy, pyyaml
  mcp_server.py           # NEW: Entry point — FastMCP server with lifespan
  bot.py                  # MODIFIED: refactor to be importable (no standalone main)
  discord_tools.py        # NEW: Discord MCP tool implementations
  scheduler.py            # NEW: APScheduler setup + job execution
  scheduler_tools.py      # NEW: Scheduler MCP tool implementations
  embeds.py               # Existing (no changes)
  config.py               # MODIFIED: add scheduler config vars
  jobs.yaml               # NEW: Default job seed config

.mcp.json                 # MODIFIED: add pepper-discord server
scripts/start-pepper.sh   # MODIFIED: simplify (Claude Code spawns bot now)
scripts/start-pepper.bat  # MODIFIED: simplify
Memory/OPERATIONS.md      # MODIFIED: add Discord Channels section

tests/
  test_discord_tools.py   # NEW: Discord MCP tool tests
  test_scheduler_tools.py # NEW: Scheduler MCP tool tests
  test_scheduler.py       # NEW: Scheduler core tests
```

---

### Task 1: Update Dependencies

**Files:**
- Modify: `integrations/discord/pyproject.toml`

- [ ] **Step 1: Update pyproject.toml**

Replace the contents of `integrations/discord/pyproject.toml`:

```toml
[project]
name = "pepper-discord"
version = "0.2.0"
description = "Pepper Discord integration — bot, MCP server, and scheduler"
requires-python = ">=3.12"
dependencies = [
    "discord.py>=2.7.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.2.0",
    "mcp>=1.0.0",
    "apscheduler>=4.0.0a1",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.20.0",
    "pyyaml>=6.0.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.0",
    "pytest-asyncio>=0.24.0",
]
```

- [ ] **Step 2: Install dependencies**

```bash
cd integrations/discord && uv sync && cd ../..
```

- [ ] **Step 3: Commit**

```bash
git add integrations/discord/pyproject.toml integrations/discord/uv.lock
git commit -m "feat: add mcp, apscheduler, sqlalchemy, pyyaml deps to Discord integration"
```

---

### Task 2: Refactor bot.py to Be Importable

**Files:**
- Modify: `integrations/discord/bot.py`

The current `bot.py` has a `main()` that calls `client.run()` which blocks and owns the event loop. We need to refactor it so the Discord client can be started from `mcp_server.py` using `client.start()` (async, non-blocking).

- [ ] **Step 1: Refactor bot.py**

Replace the contents of `integrations/discord/bot.py`:

```python
"""Pepper Discord bot — bridges Discord to the channel server.

Listens for messages in DMs and channels the bot is in.
Posts them to the channel server. Reads replies from the SSE stream
and sends them back to Discord.

This module is imported by mcp_server.py. Do not run directly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import discord
import httpx

from config import CHANNEL_URL
from embeds import build_embed

log = logging.getLogger("pepper-discord")

# --- Discord client setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Track pending messages so we can hold typing indicators
pending_chat_ids: dict[str, discord.abc.Messageable] = {}


def make_chat_id(message: discord.Message) -> str:
    """Build a chat_id from a Discord message."""
    if message.guild:
        return f"discord-{message.guild.id}-{message.channel.id}-{message.id}"
    return f"discord-dm-{message.channel.id}-{message.id}"


@client.event
async def on_ready():
    """Register with the channel server on startup."""
    log.info(f"Logged in as {client.user} (id: {client.user.id})")
    async with httpx.AsyncClient() as http:
        try:
            await http.post(
                f"{CHANNEL_URL}/register",
                json={"source": "discord", "description": f"Discord bot: {client.user.name}"},
            )
            log.info("Registered with channel server")
        except httpx.ConnectError:
            log.warning("Channel server not reachable — will retry on first message")


@client.event
async def on_message(message: discord.Message):
    """Forward Discord messages to the channel server."""
    if message.author == client.user:
        return
    if message.author.bot:
        return

    chat_id = make_chat_id(message)
    is_dm = message.guild is None

    payload = {
        "source": "discord",
        "chat_id": chat_id,
        "sender": message.author.display_name,
        "content": message.content,
        "metadata": {
            "guild_id": str(message.guild.id) if message.guild else "",
            "channel_id": str(message.channel.id),
            "message_id": str(message.id),
            "is_dm": str(is_dm),
            "author_id": str(message.author.id),
        },
    }

    pending_chat_ids[chat_id] = message.channel

    async with httpx.AsyncClient() as http:
        try:
            async with message.channel.typing():
                resp = await http.post(
                    f"{CHANNEL_URL}/message",
                    json=payload,
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    log.error(f"Channel server error: {resp.status_code} {resp.text}")
        except httpx.ConnectError:
            log.error("Channel server unreachable")
            await message.channel.send("I'm having trouble connecting right now. Try again in a moment.")


async def listen_for_replies():
    """Connect to the channel server SSE stream and relay replies to Discord."""
    backoff = 1.0
    max_backoff = 30.0

    while True:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as http:
                async with http.stream("GET", f"{CHANNEL_URL}/events?source=discord") as resp:
                    backoff = 1.0
                    log.info("Connected to channel server SSE stream")

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue
                        await handle_reply(data)

        except (httpx.ConnectError, httpx.ReadError) as e:
            log.warning(f"SSE connection lost: {e}. Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def handle_reply(data: dict[str, Any]):
    """Process a reply from the channel server and send it to Discord."""
    chat_id = data.get("chat_id", "")
    text = data.get("text", "")
    metadata = data.get("metadata", {})

    parts = chat_id.split("-")
    try:
        if parts[0] == "discord" and parts[1] == "dm":
            channel_id = int(parts[2])
        elif parts[0] == "discord":
            channel_id = int(parts[2])
        else:
            log.warning(f"Unknown chat_id format: {chat_id}")
            return
    except (IndexError, ValueError):
        log.warning(f"Could not parse chat_id: {chat_id}")
        return

    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            log.warning(f"Channel {channel_id} not found")
            return

    pending_chat_ids.pop(chat_id, None)

    reply_type = metadata.get("type", "message")
    reactions = metadata.get("reactions", [])

    original_message_id = None
    try:
        if parts[0] == "discord" and parts[1] == "dm":
            original_message_id = int(parts[3])
        elif parts[0] == "discord":
            original_message_id = int(parts[3])
    except (IndexError, ValueError):
        pass

    if reactions and original_message_id:
        try:
            original = await channel.fetch_message(original_message_id)
            for emoji_name in reactions:
                emoji = _resolve_emoji(emoji_name)
                if emoji:
                    await original.add_reaction(emoji)
        except discord.NotFound:
            log.warning(f"Original message {original_message_id} not found for reactions")

    if reply_type == "reaction":
        return

    embed_data = metadata.get("embed")
    embed = build_embed(embed_data)

    if text:
        if len(text) <= 2000:
            await channel.send(text, embed=embed)
        else:
            for i in range(0, len(text), 2000):
                chunk = text[i:i + 2000]
                chunk_embed = embed if i + 2000 >= len(text) else None
                await channel.send(chunk, embed=chunk_embed)
    elif embed:
        await channel.send(embed=embed)


EMOJI_MAP = {
    "thumbs_up": "\U0001f44d",
    "thumbs_down": "\U0001f44e",
    "eyes": "\U0001f440",
    "fire": "\U0001f525",
    "heart": "\u2764\ufe0f",
    "check": "\u2705",
    "white_check_mark": "\u2705",
    "x": "\u274c",
    "warning": "\u26a0\ufe0f",
    "rocket": "\U0001f680",
    "thinking": "\U0001f914",
    "wave": "\U0001f44b",
    "star": "\u2b50",
    "bulb": "\U0001f4a1",
    "memo": "\U0001f4dd",
    "clock": "\U0001f570\ufe0f",
    "pin": "\U0001f4cc",
}


def _resolve_emoji(name: str) -> str | None:
    """Resolve an emoji name to a unicode character."""
    return EMOJI_MAP.get(name, name if len(name) <= 2 else None)


async def keep_typing():
    """Refresh typing indicators for pending messages."""
    while True:
        await asyncio.sleep(8)
        for chat_id, channel in list(pending_chat_ids.items()):
            try:
                await channel.typing()
            except Exception:
                pending_chat_ids.pop(chat_id, None)


async def start_bot(token: str):
    """Start the Discord bot as an async task.

    Call this from the MCP server lifespan. Uses client.start()
    which is the async version of client.run().
    """
    log.info("Starting Discord bot...")
    asyncio.create_task(listen_for_replies())
    asyncio.create_task(keep_typing())
    await client.start(token)
```

Key changes from the original:
- Removed `main()` and `if __name__ == "__main__"` block
- Removed `on_connect` event handler (background tasks now started in `start_bot()`)
- Removed `DISCORD_BOT_TOKEN` import (token passed as parameter to `start_bot()`)
- Added `start_bot(token)` async function as the entry point
- `logging.basicConfig` removed (configured in mcp_server.py instead)

- [ ] **Step 2: Commit**

```bash
git add integrations/discord/bot.py
git commit -m "refactor: make bot.py importable with async start_bot() entry point"
```

---

### Task 3: Discord MCP Tools

**Files:**
- Create: `integrations/discord/discord_tools.py`
- Create: `tests/test_discord_tools.py`

- [ ] **Step 1: Write tests**

Create `tests/test_discord_tools.py`:

```python
"""Tests for Discord MCP tool implementations."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "discord"))


@pytest.fixture
def mock_client():
    """Mock Discord client with channels."""
    client = MagicMock()

    channel = AsyncMock()
    channel.id = 123456
    channel.name = "pepper-chat"
    channel.topic = "Pepper's home"
    channel.type = MagicMock()
    channel.type.name = "text"
    channel.guild = MagicMock()
    channel.guild.id = 999
    channel.guild.name = "Test Guild"
    channel.send = AsyncMock()
    channel.typing = MagicMock(return_value=AsyncMock())

    dm_channel = AsyncMock()
    dm_channel.id = 789
    dm_channel.name = "DM"
    dm_channel.type = MagicMock()
    dm_channel.type.name = "private"
    dm_channel.guild = None
    dm_channel.send = AsyncMock()

    def get_channel(cid):
        if cid == 123456:
            return channel
        if cid == 789:
            return dm_channel
        return None

    client.get_channel = get_channel
    client.get_all_channels = MagicMock(return_value=[channel])
    client.private_channels = [dm_channel]
    client.guilds = [channel.guild]

    return client, channel, dm_channel


@pytest.mark.asyncio
async def test_send_discord_message(mock_client):
    """send_discord_message sends text to correct channel."""
    client, channel, _ = mock_client

    from discord_tools import send_discord_message_impl

    result = await send_discord_message_impl(client, "123456", text="Hello!")
    channel.send.assert_called_once_with("Hello!", embed=None)
    assert result["status"] == "sent"


@pytest.mark.asyncio
async def test_send_discord_message_not_found(mock_client):
    """send_discord_message returns error for unknown channel."""
    client, _, _ = mock_client
    client.fetch_channel = AsyncMock(side_effect=Exception("Not found"))

    from discord_tools import send_discord_message_impl

    result = await send_discord_message_impl(client, "999999", text="Hello!")
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_list_channels(mock_client):
    """list_channels returns all visible channels."""
    client, channel, _ = mock_client

    from discord_tools import list_channels_impl

    result = await list_channels_impl(client)
    assert len(result) >= 1
    assert result[0]["name"] == "pepper-chat"


@pytest.mark.asyncio
async def test_add_reaction(mock_client):
    """add_reaction adds emoji to a message."""
    client, channel, _ = mock_client
    message = AsyncMock()
    channel.fetch_message = AsyncMock(return_value=message)

    from discord_tools import add_reaction_impl

    result = await add_reaction_impl(client, "123456", "111", "thumbs_up")
    message.add_reaction.assert_called_once()
    assert result["status"] == "reacted"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_discord_tools.py -v
```

Expected: FAIL (discord_tools module not found).

- [ ] **Step 3: Write discord_tools.py**

Create `integrations/discord/discord_tools.py`:

```python
"""Discord MCP tool implementations.

These are the raw async functions. The MCP tool decorators
are in mcp_server.py which calls these.
"""

from __future__ import annotations

import logging
from typing import Any

import discord

from embeds import build_embed

log = logging.getLogger("pepper-discord")

EMOJI_MAP = {
    "thumbs_up": "\U0001f44d",
    "thumbs_down": "\U0001f44e",
    "eyes": "\U0001f440",
    "fire": "\U0001f525",
    "heart": "\u2764\ufe0f",
    "check": "\u2705",
    "white_check_mark": "\u2705",
    "x": "\u274c",
    "warning": "\u26a0\ufe0f",
    "rocket": "\U0001f680",
    "thinking": "\U0001f914",
    "wave": "\U0001f44b",
    "star": "\u2b50",
    "bulb": "\U0001f4a1",
    "memo": "\U0001f4dd",
    "clock": "\U0001f570\ufe0f",
    "pin": "\U0001f4cc",
}


def _resolve_emoji(name: str) -> str | None:
    """Resolve an emoji name to a unicode character."""
    return EMOJI_MAP.get(name, name if len(name) <= 2 else None)


async def send_discord_message_impl(
    client: discord.Client,
    channel_id: str,
    text: str = "",
    embed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Send a message to a Discord channel."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"status": "error", "message": f"Channel {channel_id} not found"}

    discord_embed = build_embed(embed)

    if text and len(text) > 2000:
        for i in range(0, len(text), 2000):
            chunk = text[i:i + 2000]
            chunk_embed = discord_embed if i + 2000 >= len(text) else None
            await channel.send(chunk, embed=chunk_embed)
    elif text:
        await channel.send(text, embed=discord_embed)
    elif discord_embed:
        await channel.send(embed=discord_embed)
    else:
        return {"status": "error", "message": "Either text or embed is required"}

    return {"status": "sent", "channel_id": channel_id}


async def add_reaction_impl(
    client: discord.Client,
    channel_id: str,
    message_id: str,
    emoji: str,
) -> dict[str, str]:
    """Add a reaction to a Discord message."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"status": "error", "message": f"Channel {channel_id} not found"}

    try:
        message = await channel.fetch_message(int(message_id))
    except Exception:
        return {"status": "error", "message": f"Message {message_id} not found"}

    resolved = _resolve_emoji(emoji)
    if not resolved:
        return {"status": "error", "message": f"Unknown emoji: {emoji}"}

    await message.add_reaction(resolved)
    return {"status": "reacted", "emoji": emoji}


async def send_typing_impl(
    client: discord.Client,
    channel_id: str,
) -> dict[str, str]:
    """Show typing indicator in a channel."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"status": "error", "message": f"Channel {channel_id} not found"}

    await channel.typing()
    return {"status": "typing", "channel_id": channel_id}


async def list_channels_impl(
    client: discord.Client,
    guild_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all channels the bot can see."""
    channels = []

    for guild in client.guilds:
        if guild_id and str(guild.id) != guild_id:
            continue
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                channels.append({
                    "id": str(channel.id),
                    "name": channel.name,
                    "type": str(channel.type),
                    "topic": getattr(channel, "topic", None) or "",
                    "guild_id": str(guild.id),
                    "guild_name": guild.name,
                })

    return channels


async def get_recent_messages_impl(
    client: discord.Client,
    channel_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent messages from a channel."""
    limit = min(limit, 50)

    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return []

    messages = []
    async for msg in channel.history(limit=limit):
        messages.append({
            "id": str(msg.id),
            "author": msg.author.display_name,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
        })

    return messages


async def get_channel_info_impl(
    client: discord.Client,
    channel_id: str,
) -> dict[str, Any]:
    """Get detailed info about a channel."""
    channel = client.get_channel(int(channel_id))
    if channel is None:
        try:
            channel = await client.fetch_channel(int(channel_id))
        except Exception:
            return {"error": f"Channel {channel_id} not found"}

    info = {
        "id": str(channel.id),
        "name": getattr(channel, "name", "DM"),
        "type": str(channel.type),
        "topic": getattr(channel, "topic", None) or "",
    }

    if hasattr(channel, "guild") and channel.guild:
        info["guild_id"] = str(channel.guild.id)
        info["guild_name"] = channel.guild.name
        info["member_count"] = channel.guild.member_count

    return info
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_discord_tools.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add integrations/discord/discord_tools.py tests/test_discord_tools.py
git commit -m "feat: add Discord MCP tool implementations with tests"
```

---

### Task 4: Scheduler Core

**Files:**
- Create: `integrations/discord/scheduler.py`
- Create: `integrations/discord/jobs.yaml`
- Modify: `integrations/discord/config.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Update config.py**

Replace `integrations/discord/config.py`:

```python
"""Configuration for the Pepper Discord integration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the bot directory
INTEGRATION_DIR = Path(__file__).parent
load_dotenv(INTEGRATION_DIR / ".env")

DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_URL: str = os.environ.get("PEPPER_CHANNEL_URL", "http://localhost:8788")
SCHEDULER_DB: str = os.environ.get(
    "PEPPER_SCHEDULER_DB",
    str(INTEGRATION_DIR / "scheduler.db"),
)
JOBS_YAML: Path = INTEGRATION_DIR / "jobs.yaml"
TIMEZONE: str = os.environ.get("PEPPER_TIMEZONE", "US/Eastern")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN is not set. "
        "Copy .env.example to .env and add your bot token."
    )
```

- [ ] **Step 2: Create jobs.yaml**

Create `integrations/discord/jobs.yaml`:

```yaml
heartbeat:
  trigger: interval
  schedule:
    minutes: 30
  prompt: >
    Heartbeat check: Review pending tasks in Memory/TASKS.md, scan project
    statuses for anything that needs attention. If anything is noteworthy,
    send it to the appropriate Discord channel using send_discord_message.
    Check Memory/OPERATIONS.md for channel mappings.
  channel_hint: "#pepper-chat"

morning_briefing:
  trigger: cron
  schedule:
    hour: 7
    minute: 0
  prompt: >
    Morning briefing for Jeff. Check project statuses, scan for upcoming
    deadlines this week, summarize yesterday's activity from daily logs,
    and list today's priorities. Send the briefing to the pepper-chat
    Discord channel using send_discord_message with a rich embed.
  channel_hint: "#pepper-chat"

nightly_reflection:
  trigger: cron
  schedule:
    hour: 3
    minute: 0
  prompt: >
    Nightly reflection: Summarize today's raw logs from Memory/daily/raw/
    into a daily summary. Write it to Memory/daily/summaries/ with pointer
    links to raw entries. Identify patterns, decisions made, and open loops.
    Send a brief summary to pepper-chat Discord channel.
  channel_hint: "#pepper-chat"
```

- [ ] **Step 3: Write scheduler tests**

Create `tests/test_scheduler.py`:

```python
"""Tests for scheduler core functionality."""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "discord"))

JOBS_YAML = Path(__file__).parent.parent / "integrations" / "discord" / "jobs.yaml"


def test_jobs_yaml_loads():
    """jobs.yaml is valid YAML with expected structure."""
    with open(JOBS_YAML) as f:
        jobs = yaml.safe_load(f)

    assert isinstance(jobs, dict)
    assert "heartbeat" in jobs
    assert "morning_briefing" in jobs
    assert "nightly_reflection" in jobs


def test_jobs_yaml_required_fields():
    """Each job has trigger, schedule, and prompt."""
    with open(JOBS_YAML) as f:
        jobs = yaml.safe_load(f)

    for name, job in jobs.items():
        assert "trigger" in job, f"Job {name} missing trigger"
        assert "schedule" in job, f"Job {name} missing schedule"
        assert "prompt" in job, f"Job {name} missing prompt"
        assert job["trigger"] in ("interval", "cron", "once"), f"Job {name} has invalid trigger"


def test_load_seed_jobs():
    """load_seed_jobs returns parsed job definitions."""
    from scheduler import load_seed_jobs

    jobs = load_seed_jobs(JOBS_YAML)
    assert len(jobs) == 3
    assert "heartbeat" in jobs
    assert jobs["heartbeat"]["trigger"] == "interval"
    assert jobs["heartbeat"]["schedule"]["minutes"] == 30


@pytest.mark.asyncio
async def test_execute_job_posts_to_channel():
    """Job execution POSTs to the channel server."""
    from unittest.mock import AsyncMock, patch

    from scheduler import execute_job

    with patch("scheduler.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock()
        mock_client_cls.return_value = mock_client

        await execute_job("heartbeat", "Check stuff", "#pepper-chat")

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["source"] == "scheduler"
        assert "heartbeat" in payload["chat_id"]
        assert payload["content"] == "Check stuff"
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest tests/test_scheduler.py -v
```

Expected: First two PASS (YAML tests), last two FAIL (scheduler module not found).

- [ ] **Step 5: Write scheduler.py**

Create `integrations/discord/scheduler.py`:

```python
"""APScheduler setup and job execution.

Loads default jobs from jobs.yaml, persists state to SQLite,
and executes jobs by POSTing prompts to the channel server.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import create_async_engine

from config import CHANNEL_URL, SCHEDULER_DB, TIMEZONE

log = logging.getLogger("pepper-scheduler")


def load_seed_jobs(yaml_path: Path) -> dict[str, Any]:
    """Load job definitions from a YAML file."""
    if not yaml_path.exists():
        log.warning(f"Jobs file not found: {yaml_path}")
        return {}

    with open(yaml_path) as f:
        return yaml.safe_load(f) or {}


def build_trigger(job_def: dict[str, Any]):
    """Build an APScheduler trigger from a job definition."""
    trigger_type = job_def["trigger"]
    schedule = job_def["schedule"]

    if trigger_type == "interval":
        return IntervalTrigger(
            hours=schedule.get("hours", 0),
            minutes=schedule.get("minutes", 0),
            seconds=schedule.get("seconds", 0),
        )
    elif trigger_type == "cron":
        return CronTrigger(
            hour=schedule.get("hour"),
            minute=schedule.get("minute", 0),
            day_of_week=schedule.get("day_of_week"),
            day=schedule.get("day"),
            month=schedule.get("month"),
            timezone=job_def.get("timezone", TIMEZONE),
        )
    else:
        raise ValueError(f"Unknown trigger type: {trigger_type}")


async def execute_job(name: str, prompt: str, channel_hint: str = ""):
    """Execute a scheduled job by POSTing to the channel server."""
    chat_id = f"scheduler-{name}-{int(time.time())}"

    payload = {
        "source": "scheduler",
        "chat_id": chat_id,
        "sender": "scheduler",
        "content": prompt,
        "metadata": {
            "job_name": name,
            "channel_hint": channel_hint,
        },
    }

    async with httpx.AsyncClient() as http:
        try:
            resp = await http.post(
                f"{CHANNEL_URL}/message",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 200:
                log.info(f"Job {name} fired (chat_id: {chat_id})")
            else:
                log.error(f"Job {name} failed: {resp.status_code} {resp.text}")
        except httpx.ConnectError:
            log.error(f"Job {name}: channel server unreachable")


async def create_scheduler() -> AsyncScheduler:
    """Create and configure the APScheduler instance."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{SCHEDULER_DB}")
    data_store = SQLAlchemyDataStore(engine)
    scheduler = AsyncScheduler(data_store=data_store)
    return scheduler


async def seed_default_jobs(scheduler: AsyncScheduler, yaml_path: Path):
    """Seed default jobs from YAML if they don't already exist."""
    existing = await scheduler.get_schedules()
    existing_ids = {s.id for s in existing}

    seed_jobs = load_seed_jobs(yaml_path)

    for name, job_def in seed_jobs.items():
        if name in existing_ids:
            log.debug(f"Job {name} already exists, skipping seed")
            continue

        trigger = build_trigger(job_def)
        prompt = job_def["prompt"]
        channel_hint = job_def.get("channel_hint", "")

        await scheduler.add_schedule(
            execute_job,
            trigger,
            id=name,
            args=[name, prompt, channel_hint],
        )
        log.info(f"Seeded job: {name}")
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_scheduler.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add integrations/discord/scheduler.py integrations/discord/jobs.yaml integrations/discord/config.py tests/test_scheduler.py
git commit -m "feat: add scheduler core with APScheduler, job seeding, and channel server execution"
```

---

### Task 5: Scheduler MCP Tools

**Files:**
- Create: `integrations/discord/scheduler_tools.py`
- Create: `tests/test_scheduler_tools.py`

- [ ] **Step 1: Write tests**

Create `tests/test_scheduler_tools.py`:

```python
"""Tests for scheduler MCP tool implementations."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "discord"))


@pytest.fixture
def mock_scheduler():
    """Mock APScheduler."""
    scheduler = AsyncMock()

    # Mock existing schedules
    schedule1 = MagicMock()
    schedule1.id = "heartbeat"
    schedule1.trigger = MagicMock()
    schedule1.trigger.__str__ = lambda self: "interval[0:30:00]"
    schedule1.next_fire_time = None
    schedule1.args = ["heartbeat", "Check stuff", "#pepper-chat"]
    schedule1.paused = False

    scheduler.get_schedules = AsyncMock(return_value=[schedule1])
    scheduler.get_schedule = AsyncMock(return_value=schedule1)

    return scheduler


@pytest.mark.asyncio
async def test_list_jobs(mock_scheduler):
    """list_jobs returns all scheduled jobs."""
    from scheduler_tools import list_jobs_impl

    result = await list_jobs_impl(mock_scheduler)
    assert len(result) == 1
    assert result[0]["name"] == "heartbeat"


@pytest.mark.asyncio
async def test_create_job(mock_scheduler):
    """create_job adds a new schedule."""
    from scheduler_tools import create_job_impl

    result = await create_job_impl(
        mock_scheduler,
        name="test_job",
        trigger="interval",
        schedule={"minutes": 10},
        prompt="Test prompt",
    )
    assert result["status"] == "created"
    mock_scheduler.add_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_delete_job(mock_scheduler):
    """delete_job removes a schedule."""
    from scheduler_tools import delete_job_impl

    result = await delete_job_impl(mock_scheduler, "heartbeat")
    assert result["status"] == "deleted"
    mock_scheduler.remove_schedule.assert_called_once_with("heartbeat")


@pytest.mark.asyncio
async def test_pause_job(mock_scheduler):
    """pause_job pauses a schedule."""
    from scheduler_tools import pause_job_impl

    result = await pause_job_impl(mock_scheduler, "heartbeat")
    assert result["status"] == "paused"
    mock_scheduler.pause_schedule.assert_called_once_with("heartbeat")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_scheduler_tools.py -v
```

Expected: FAIL (scheduler_tools not found).

- [ ] **Step 3: Write scheduler_tools.py**

Create `integrations/discord/scheduler_tools.py`:

```python
"""Scheduler MCP tool implementations.

These are the raw async functions. The MCP tool decorators
are in mcp_server.py which calls these.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler import AsyncScheduler

from scheduler import build_trigger, execute_job

log = logging.getLogger("pepper-scheduler")


async def list_jobs_impl(scheduler: AsyncScheduler) -> list[dict[str, Any]]:
    """List all scheduled jobs with their details."""
    schedules = await scheduler.get_schedules()
    result = []

    for s in schedules:
        job_info = {
            "name": s.id,
            "trigger": str(s.trigger),
            "next_run": s.next_fire_time.isoformat() if s.next_fire_time else None,
            "paused": getattr(s, "paused", False),
        }
        if s.args and len(s.args) >= 2:
            job_info["prompt"] = s.args[1]
        if s.args and len(s.args) >= 3:
            job_info["channel_hint"] = s.args[2]
        result.append(job_info)

    return result


async def create_job_impl(
    scheduler: AsyncScheduler,
    name: str,
    trigger: str,
    schedule: dict[str, Any],
    prompt: str,
    channel_hint: str = "",
    timezone: str = "US/Eastern",
) -> dict[str, str]:
    """Create a new scheduled job."""
    job_def = {
        "trigger": trigger,
        "schedule": schedule,
        "timezone": timezone,
    }

    try:
        apscheduler_trigger = build_trigger(job_def)
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    await scheduler.add_schedule(
        execute_job,
        apscheduler_trigger,
        id=name,
        args=[name, prompt, channel_hint],
    )

    log.info(f"Created job: {name}")
    return {"status": "created", "name": name}


async def update_job_impl(
    scheduler: AsyncScheduler,
    name: str,
    schedule: dict[str, Any] | None = None,
    prompt: str | None = None,
    channel_hint: str | None = None,
    timezone: str | None = None,
) -> dict[str, str]:
    """Update an existing job. Removes and re-creates it."""
    try:
        existing = await scheduler.get_schedule(name)
    except Exception:
        return {"status": "error", "message": f"Job {name} not found"}

    # Get current values
    current_prompt = existing.args[1] if existing.args and len(existing.args) >= 2 else ""
    current_hint = existing.args[2] if existing.args and len(existing.args) >= 3 else ""

    # Remove old
    await scheduler.remove_schedule(name)

    # Build new trigger if schedule changed
    if schedule:
        # Determine trigger type from existing trigger string
        trigger_str = str(existing.trigger)
        trigger_type = "interval" if "interval" in trigger_str.lower() else "cron"
        job_def = {
            "trigger": trigger_type,
            "schedule": schedule,
            "timezone": timezone or "US/Eastern",
        }
        new_trigger = build_trigger(job_def)
    else:
        new_trigger = existing.trigger

    await scheduler.add_schedule(
        execute_job,
        new_trigger,
        id=name,
        args=[name, prompt or current_prompt, channel_hint or current_hint],
    )

    log.info(f"Updated job: {name}")
    return {"status": "updated", "name": name}


async def delete_job_impl(
    scheduler: AsyncScheduler,
    name: str,
) -> dict[str, str]:
    """Delete a scheduled job."""
    await scheduler.remove_schedule(name)
    log.info(f"Deleted job: {name}")
    return {"status": "deleted", "name": name}


async def pause_job_impl(
    scheduler: AsyncScheduler,
    name: str,
) -> dict[str, str]:
    """Pause a scheduled job."""
    await scheduler.pause_schedule(name)
    log.info(f"Paused job: {name}")
    return {"status": "paused", "name": name}


async def resume_job_impl(
    scheduler: AsyncScheduler,
    name: str,
) -> dict[str, str]:
    """Resume a paused job."""
    await scheduler.unpause_schedule(name, resume_from="now")
    log.info(f"Resumed job: {name}")
    return {"status": "resumed", "name": name}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_scheduler_tools.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add integrations/discord/scheduler_tools.py tests/test_scheduler_tools.py
git commit -m "feat: add scheduler MCP tool implementations with tests"
```

---

### Task 6: MCP Server Entry Point

**Files:**
- Create: `integrations/discord/mcp_server.py`

This is the main entry point that ties everything together. Claude Code spawns it via `.mcp.json`.

- [ ] **Step 1: Write mcp_server.py**

Create `integrations/discord/mcp_server.py`:

```python
"""Pepper Discord MCP Server.

Entry point spawned by Claude Code via .mcp.json.
Runs the Discord bot, scheduler, and SSE listener in one process.
Exposes Discord and scheduler tools via MCP over stdio.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (stdout is used by MCP stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("pepper-mcp")

# Import integration modules
from bot import client, start_bot
from config import DISCORD_BOT_TOKEN, JOBS_YAML
from discord_tools import (
    add_reaction_impl,
    get_channel_info_impl,
    get_recent_messages_impl,
    list_channels_impl,
    send_discord_message_impl,
    send_typing_impl,
)
from scheduler import create_scheduler, seed_default_jobs
from scheduler_tools import (
    create_job_impl,
    delete_job_impl,
    list_jobs_impl,
    pause_job_impl,
    resume_job_impl,
    update_job_impl,
)

# Global scheduler reference (set in lifespan)
_scheduler = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Start Discord bot and scheduler on MCP server startup."""
    global _scheduler

    log.info("Starting Pepper Discord integration...")

    # Create and start scheduler
    _scheduler = await create_scheduler()
    async with _scheduler:
        await seed_default_jobs(_scheduler, JOBS_YAML)
        await _scheduler.start_in_background()
        log.info("Scheduler started")

        # Start Discord bot as a background task
        bot_task = asyncio.create_task(start_bot(DISCORD_BOT_TOKEN))
        log.info("Discord bot starting...")

        yield

        # Shutdown
        log.info("Shutting down...")
        client.clear()
        bot_task.cancel()


# Create the MCP server
mcp = FastMCP(
    "pepper-discord",
    lifespan=lifespan,
)


# --- Discord Tools ---


@mcp.tool()
async def send_discord_message(
    channel_id: str,
    text: str = "",
    embed: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Send a message to a Discord channel. Supports text, rich embeds, or both.

    Args:
        channel_id: The Discord channel ID to send to.
        text: Message text (markdown supported). Optional if embed is provided.
        embed: Optional rich embed with title, description, color (int), fields.
    """
    return await send_discord_message_impl(client, channel_id, text, embed)


@mcp.tool()
async def add_reaction(
    channel_id: str,
    message_id: str,
    emoji: str,
) -> dict[str, str]:
    """Add a reaction to a Discord message.

    Args:
        channel_id: The channel containing the message.
        message_id: The message to react to.
        emoji: Emoji name (thumbs_up, fire, rocket, etc.) or unicode character.
    """
    return await add_reaction_impl(client, channel_id, message_id, emoji)


@mcp.tool()
async def send_typing(channel_id: str) -> dict[str, str]:
    """Show typing indicator in a Discord channel.

    Args:
        channel_id: The channel to show typing in.
    """
    return await send_typing_impl(client, channel_id)


@mcp.tool()
async def list_channels(guild_id: str | None = None) -> list[dict[str, Any]]:
    """List all Discord channels the bot can see.

    Args:
        guild_id: Optional guild/server ID to filter by.
    """
    return await list_channels_impl(client, guild_id)


@mcp.tool()
async def get_recent_messages(
    channel_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch recent messages from a Discord channel.

    Args:
        channel_id: The channel to read from.
        limit: Number of messages to fetch (default 10, max 50).
    """
    return await get_recent_messages_impl(client, channel_id, limit)


@mcp.tool()
async def get_channel_info(channel_id: str) -> dict[str, Any]:
    """Get detailed information about a Discord channel.

    Args:
        channel_id: The channel to inspect.
    """
    return await get_channel_info_impl(client, channel_id)


# --- Scheduler Tools ---


@mcp.tool()
async def create_job(
    name: str,
    trigger: str,
    schedule: dict[str, Any],
    prompt: str,
    channel_hint: str = "",
    timezone: str = "US/Eastern",
) -> dict[str, str]:
    """Create a new scheduled job.

    Args:
        name: Unique job identifier (snake_case).
        trigger: Trigger type: "interval" or "cron".
        schedule: For interval: {minutes, hours, seconds}. For cron: {hour, minute, day_of_week, day, month}.
        prompt: The prompt to send to Pepper when this job fires.
        channel_hint: Optional suggested Discord channel for context.
        timezone: Timezone for cron triggers (default: US/Eastern).
    """
    return await create_job_impl(_scheduler, name, trigger, schedule, prompt, channel_hint, timezone)


@mcp.tool()
async def update_job(
    name: str,
    schedule: dict[str, Any] | None = None,
    prompt: str | None = None,
    channel_hint: str | None = None,
    timezone: str | None = None,
) -> dict[str, str]:
    """Update an existing scheduled job.

    Args:
        name: Job identifier to update.
        schedule: New schedule (optional).
        prompt: New prompt (optional).
        channel_hint: New channel hint (optional).
        timezone: New timezone (optional).
    """
    return await update_job_impl(_scheduler, name, schedule, prompt, channel_hint, timezone)


@mcp.tool()
async def delete_job(name: str) -> dict[str, str]:
    """Delete a scheduled job.

    Args:
        name: Job identifier to delete.
    """
    return await delete_job_impl(_scheduler, name)


@mcp.tool()
async def list_jobs() -> list[dict[str, Any]]:
    """List all scheduled jobs with their schedules and next run times."""
    return await list_jobs_impl(_scheduler)


@mcp.tool()
async def pause_job(name: str) -> dict[str, str]:
    """Pause a scheduled job (stops firing but keeps the definition).

    Args:
        name: Job identifier to pause.
    """
    return await pause_job_impl(_scheduler, name)


@mcp.tool()
async def resume_job(name: str) -> dict[str, str]:
    """Resume a paused job.

    Args:
        name: Job identifier to resume.
    """
    return await resume_job_impl(_scheduler, name)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

- [ ] **Step 2: Commit**

```bash
git add integrations/discord/mcp_server.py
git commit -m "feat: add MCP server entry point with Discord and scheduler tools"
```

---

### Task 7: Config Updates

**Files:**
- Modify: `.mcp.json`
- Modify: `scripts/start-pepper.sh`
- Modify: `scripts/start-pepper.bat`
- Modify: `Memory/OPERATIONS.md`
- Modify: `integrations/discord/.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Update .mcp.json**

Replace `.mcp.json`:

```json
{
  "mcpServers": {
    "pepper-channel": {
      "command": "bun",
      "args": ["./channel/pepper-channel.ts"]
    },
    "pepper-discord": {
      "command": "uv",
      "args": ["--directory", "./integrations/discord", "run", "python", "mcp_server.py"]
    }
  }
}
```

- [ ] **Step 2: Update start-pepper.sh**

Replace `scripts/start-pepper.sh`:

```bash
#!/usr/bin/env bash
# Start Pepper: Claude Code session with channel and Discord MCP servers
#
# Claude Code spawns both MCP servers (pepper-channel and pepper-discord)
# automatically via .mcp.json. This script just starts Claude Code.
set -e

PEPPER_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting Pepper..."
echo "  Claude Code will spawn:"
echo "    - pepper-channel (TypeScript, message router)"
echo "    - pepper-discord (Python, Discord bot + scheduler)"
echo ""

cd "$PEPPER_DIR"
exec claude --dangerously-load-development-channels server:pepper-channel
```

- [ ] **Step 3: Update start-pepper.bat**

Replace `scripts/start-pepper.bat`:

```batch
@echo off
REM Start Pepper: Claude Code session with channel and Discord MCP servers
REM Claude Code spawns both MCP servers automatically via .mcp.json.

set PEPPER_DIR=%~dp0..

echo Starting Pepper...
echo   Claude Code will spawn:
echo     - pepper-channel (TypeScript, message router)
echo     - pepper-discord (Python, Discord bot + scheduler)
echo.

if not defined CLAUDE_CODE_GIT_BASH_PATH (
    set CLAUDE_CODE_GIT_BASH_PATH=E:\Program Files\Git\bin\bash.exe
)

cd /d "%PEPPER_DIR%"
claude --dangerously-load-development-channels server:pepper-channel
```

- [ ] **Step 4: Update OPERATIONS.md**

Add the following section to `Memory/OPERATIONS.md` before the `## Spawning Sessions` section:

```markdown
## Discord Channels
- #pepper-chat (1488680018077945978) — Pepper's home: briefings, system messages, proactive updates
- #job-niwc (1488702541267996772) — NIWC Atlantic work, deadlines, WAR reports
- #business-etsy (1488685331720048700) — Daku Press Etsy operations
- #business-chrona (1488718518248673423) — Chrona Network projects
- #ideas (1488713028831543378) — Idea capture and brainstorming
- #general (1229523821820772396) — General discussion

When sending proactive messages, choose the channel that matches the topic.
Use #pepper-chat for general briefings and system messages.
Use list_channels() to discover new channels not listed here.
Update this section when channels are added or repurposed.
```

- [ ] **Step 5: Update .env.example**

Replace `integrations/discord/.env.example`:

```
DISCORD_BOT_TOKEN=your-bot-token-here
PEPPER_CHANNEL_URL=http://localhost:8788
PEPPER_TIMEZONE=US/Eastern
```

- [ ] **Step 6: Add scheduler.db to .gitignore**

Append to `.gitignore`:

```
# Scheduler database
integrations/discord/scheduler.db
```

- [ ] **Step 7: Remove stop scripts and .pids references**

The stop scripts and .pids directory are no longer needed — Claude Code manages the MCP server processes. Delete:

```bash
rm scripts/stop-pepper.sh scripts/stop-pepper.bat
```

- [ ] **Step 8: Commit**

```bash
git add .mcp.json scripts/ Memory/OPERATIONS.md integrations/discord/.env.example .gitignore
git commit -m "feat: wire up Discord MCP server, simplify launch scripts, add channel registry"
```

---

### Task 8: Integration Test

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/test_discord_embeds.py tests/test_discord_tools.py tests/test_scheduler.py tests/test_scheduler_tools.py -v
```

Expected: All tests PASS.

- [ ] **Step 2: Manual integration test**

Start Pepper:
```bash
scripts/start-pepper.sh
```

Verify in the Claude Code session:
1. Type `/mcp` — should show both `pepper-channel` and `pepper-discord` servers
2. Ask Pepper: "List my Discord channels" — should call `list_channels()` and return the channel list
3. Ask Pepper: "Send a message to #pepper-chat saying 'Hello from Pepper!'" — should call `send_discord_message()`
4. Ask Pepper: "What jobs are scheduled?" — should call `list_jobs()` and show heartbeat, morning_briefing, nightly_reflection
5. Ask Pepper: "Create a job called test_reminder that runs every 5 minutes with the prompt 'Just checking in'" — should call `create_job()`
6. Ask Pepper: "Delete the test_reminder job" — should call `delete_job()`
7. DM the bot on Discord — should still work through the channel server

- [ ] **Step 3: Final commit and push**

```bash
git add -A
git commit -m "feat: Pepper Discord MCP + Scheduler complete"
git push origin main
```
