# Pepper MVP: Channel Server + Discord Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Pepper a nervous system — a production channel server that routes messages between integrations and Pepper's Claude Code session, with Discord as the first integration.

**Architecture:** The channel server (TypeScript/Bun) is an MCP server that Claude Code spawns. It accepts HTTP POSTs from external integrations, pushes them into the session, and routes replies back via filtered SSE streams. The Discord bot (Python/discord.py) is a standalone process that bridges Discord to the channel server. Launch scripts tie everything together.

**Tech Stack:** TypeScript/Bun (channel server), Python 3.12/discord.py/httpx (Discord bot), uv (Python package management)

**Spec:** `docs/superpowers/specs/2026-04-06-pepper-mvp-channel-discord-design.md`

**Working directory:** `E:\workspaces\ai\pepper` (main branch, no worktrees)

---

## File Structure

```
# Channel Server (evolve existing POC)
channel/
  pepper-channel.ts          # Production channel server (replace POC)
  package.json               # Already exists, no changes needed

# Discord Bot (new)
integrations/
  discord/
    pyproject.toml           # uv project: discord.py, httpx, python-dotenv
    .python-version          # 3.12
    bot.py                   # Main bot process
    embeds.py                # Embed formatting helpers
    config.py                # Config loading
    .env.example             # Template for DISCORD_BOT_TOKEN

# Launch Scripts (new)
scripts/
  start-pepper.sh            # Linux/Mac/Git Bash
  start-pepper.bat           # Windows
  stop-pepper.sh
  stop-pepper.bat

# Tests
tests/
  test_channel_routing.py    # Channel server HTTP tests
  test_discord_embeds.py     # Embed formatting tests

# Config updates
.gitignore                   # Add integrations/**/.env, .pids/
```

---

### Task 1: Update .gitignore for New Directories

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add ignore patterns**

Add these lines to `.gitignore`:

```
# Integration secrets
integrations/**/.env

# PID files for launch scripts
.pids/

# Bun lockfile
channel/bun.lockb

# Node modules
channel/node_modules/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add gitignore patterns for integrations and launch scripts"
```

---

### Task 2: Production Channel Server

**Files:**
- Modify: `channel/pepper-channel.ts` (replace POC)

- [ ] **Step 1: Write the production channel server**

Replace `channel/pepper-channel.ts` with the production version. Key changes from POC:
- JSON body on POST /message (not raw text with headers)
- Routing table: maps chat_id -> source
- Filtered SSE: GET /events?source=discord
- Registration endpoint: POST /register
- Enhanced health endpoint
- Metadata passthrough on replies (reactions, embeds, type)
- Route TTL cleanup (24h default)

```typescript
#!/usr/bin/env bun
/**
 * Pepper Channel Server — production message router
 *
 * MCP channel server that routes messages between external integrations
 * and Pepper's Claude Code session. Single port, routing by source metadata.
 */
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js'

// --- Configuration ---
const PORT = parseInt(process.env.PEPPER_CHANNEL_PORT ?? '8788')
const ROUTE_TTL_MS = parseInt(process.env.PEPPER_ROUTE_TTL_HOURS ?? '24') * 60 * 60 * 1000
const startTime = Date.now()

// --- Routing table: chat_id -> { source, timestamp } ---
const routes = new Map<string, { source: string; ts: number }>()

function cleanExpiredRoutes() {
  const now = Date.now()
  for (const [id, entry] of routes) {
    if (now - entry.ts > ROUTE_TTL_MS) routes.delete(id)
  }
}

// Run cleanup every hour
setInterval(cleanExpiredRoutes, 60 * 60 * 1000)

// --- Registered integrations ---
const registrations = new Map<string, { description: string; ts: number }>()

// --- SSE listeners: source -> Set<emit function> ---
type Emitter = (chunk: string) => void
const sseListeners = new Map<string, Set<Emitter>>()
const globalListeners = new Set<Emitter>()

function emitToSource(source: string, data: object) {
  const json = JSON.stringify(data)
  const chunk = `data: ${json}\n\n`

  // Send to source-specific listeners
  const sourceListeners = sseListeners.get(source)
  if (sourceListeners) {
    for (const emit of sourceListeners) emit(chunk)
  }

  // Send to global listeners (no filter)
  for (const emit of globalListeners) emit(chunk)
}

// --- MCP Server ---
const mcp = new Server(
  { name: 'pepper-channel', version: '1.0.0' },
  {
    capabilities: {
      experimental: { 'claude/channel': {} },
      tools: {},
    },
    instructions:
      'Messages arrive as <channel source="pepper-channel" chat_id="..." sender="..." integration="...">. ' +
      'These are from external systems (Discord, email, heartbeat) talking to you. ' +
      'Reply with the reply tool, passing the chat_id from the tag. ' +
      'You can include metadata in your reply: reactions (array of emoji names), ' +
      'type ("message" or "reaction" for reaction-only), and embed (object with title, description, color, fields). ' +
      'Treat each message as a task or conversation to handle.',
  },
)

// --- Reply tool ---
mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: 'reply',
    description: 'Send a reply back through the channel to the integration that sent the message',
    inputSchema: {
      type: 'object',
      properties: {
        chat_id: { type: 'string', description: 'The conversation to reply in (from the channel tag)' },
        text: { type: 'string', description: 'The message to send' },
        metadata: {
          type: 'object',
          description: 'Optional: reactions (emoji array), type ("message"|"reaction"), embed (object with title/description/color/fields)',
          properties: {
            reactions: { type: 'array', items: { type: 'string' }, description: 'Emoji names to react with' },
            type: { type: 'string', enum: ['message', 'reaction'], description: 'Reply type: message (default) or reaction-only' },
            embed: {
              type: 'object',
              description: 'Rich embed with title, description, color (int), fields (array of {name, value, inline})',
            },
          },
        },
      },
      required: ['chat_id'],
    },
  }],
}))

mcp.setRequestHandler(CallToolRequestSchema, async req => {
  if (req.params.name === 'reply') {
    const { chat_id, text, metadata } = req.params.arguments as {
      chat_id: string
      text?: string
      metadata?: { reactions?: string[]; type?: string; embed?: object }
    }

    const route = routes.get(chat_id)
    const source = route?.source ?? 'unknown'

    const reply = {
      chat_id,
      text: text ?? '',
      metadata: metadata ?? {},
      source,
      ts: new Date().toISOString(),
    }

    emitToSource(source, reply)

    return { content: [{ type: 'text', text: 'sent' }] }
  }
  throw new Error(`unknown tool: ${req.params.name}`)
})

await mcp.connect(new StdioServerTransport())

// --- HTTP Server ---
Bun.serve({
  port: PORT,
  hostname: '127.0.0.1',
  idleTimeout: 0,
  async fetch(req) {
    const url = new URL(req.url)

    // GET /health
    if (req.method === 'GET' && url.pathname === '/health') {
      cleanExpiredRoutes()
      return new Response(JSON.stringify({
        status: 'ok',
        port: PORT,
        registered_sources: Array.from(registrations.keys()),
        routing_table_size: routes.size,
        uptime_seconds: Math.floor((Date.now() - startTime) / 1000),
      }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // GET /events?source=discord — filtered SSE stream
    if (req.method === 'GET' && url.pathname === '/events') {
      const source = url.searchParams.get('source')
      const stream = new ReadableStream({
        start(ctrl) {
          ctrl.enqueue(': connected\n\n')
          const emit = (chunk: string) => ctrl.enqueue(chunk)

          if (source) {
            if (!sseListeners.has(source)) sseListeners.set(source, new Set())
            sseListeners.get(source)!.add(emit)
            req.signal.addEventListener('abort', () => {
              sseListeners.get(source)?.delete(emit)
            })
          } else {
            globalListeners.add(emit)
            req.signal.addEventListener('abort', () => globalListeners.delete(emit))
          }
        },
      })
      return new Response(stream, {
        headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
      })
    }

    // POST /register
    if (req.method === 'POST' && url.pathname === '/register') {
      const body = await req.json() as { source: string; description?: string }
      if (!body.source) {
        return new Response(JSON.stringify({ error: 'source is required' }), { status: 400 })
      }
      registrations.set(body.source, {
        description: body.description ?? '',
        ts: Date.now(),
      })
      return new Response(JSON.stringify({ status: 'registered', source: body.source }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // POST /message — main inbound endpoint
    if (req.method === 'POST' && url.pathname === '/message') {
      const body = await req.json() as {
        source: string
        chat_id: string
        sender?: string
        content: string
        metadata?: Record<string, string>
      }

      if (!body.source || !body.content || !body.chat_id) {
        return new Response(JSON.stringify({ error: 'source, chat_id, and content are required' }), { status: 400 })
      }

      // Store route for reply routing
      routes.set(body.chat_id, { source: body.source, ts: Date.now() })

      // Build meta attributes for the channel tag
      const meta: Record<string, string> = {
        chat_id: body.chat_id,
        sender: body.sender ?? 'unknown',
        integration: body.source,
      }
      if (body.metadata) {
        for (const [k, v] of Object.entries(body.metadata)) {
          meta[k] = String(v)
        }
      }

      await mcp.notification({
        method: 'notifications/claude/channel',
        params: {
          content: body.content,
          meta,
        },
      })

      return new Response(JSON.stringify({ status: 'queued', chat_id: body.chat_id }), {
        headers: { 'Content-Type': 'application/json' },
      })
    }

    return new Response(JSON.stringify({ error: 'not found' }), { status: 404 })
  },
})

console.error(`Pepper channel server v1.0.0 listening on http://127.0.0.1:${PORT}`)
```

- [ ] **Step 2: Test the channel server manually**

Start Claude Code with the channel:
```bash
claude --dangerously-load-development-channels server:pepper-channel
```

In another terminal, register and send a message:
```bash
curl.exe -X POST http://localhost:8788/register -H "Content-Type: application/json" -d "{\"source\": \"test\", \"description\": \"manual test\"}"
curl.exe -X POST http://localhost:8788/message -H "Content-Type: application/json" -d "{\"source\": \"test\", \"chat_id\": \"test-1\", \"sender\": \"jeff\", \"content\": \"Hello Pepper, what is your name?\"}"
curl.exe http://localhost:8788/health
```

Expected: Message arrives in Pepper's session, health shows "test" in registered_sources.

- [ ] **Step 3: Commit**

```bash
git add channel/pepper-channel.ts
git commit -m "feat: production channel server with routing, SSE filtering, and registration"
```

---

### Task 3: Channel Server Automated Tests

**Files:**
- Create: `tests/test_channel_routing.py`

- [ ] **Step 1: Write channel server HTTP tests**

These tests start the channel server as a subprocess and test it via HTTP. They don't need Claude Code — they test the HTTP layer independently.

```python
"""Tests for the channel server HTTP endpoints.

Starts pepper-channel.ts as a standalone Bun process (no Claude Code)
and tests the HTTP API. The MCP connection will fail (no stdio parent),
but the HTTP server starts independently.
"""

import json
import subprocess
import time
from pathlib import Path

import httpx
import pytest

CHANNEL_DIR = Path(__file__).parent.parent / "channel"
PORT = 18788  # Use a non-default port to avoid conflicts


@pytest.fixture(scope="module")
def channel_server():
    """Start the channel server on a test port."""
    proc = subprocess.Popen(
        ["bun", "run", "pepper-channel.ts"],
        cwd=str(CHANNEL_DIR),
        env={"PEPPER_CHANNEL_PORT": str(PORT), "PATH": subprocess.os.environ["PATH"]},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    for _ in range(30):
        try:
            httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=1.0)
            break
        except httpx.ConnectError:
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
```

- [ ] **Step 2: Add httpx to root dev dependencies**

```bash
uv add --dev httpx
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_channel_routing.py -v -m slow
```

Expected: All 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_channel_routing.py pyproject.toml uv.lock
git commit -m "test: add channel server HTTP endpoint tests"
```

---

### Task 4: Discord Bot — Project Setup

**Files:**
- Create: `integrations/discord/pyproject.toml`
- Create: `integrations/discord/.python-version`
- Create: `integrations/discord/.env.example`

- [ ] **Step 1: Create the Discord bot uv project**

```bash
mkdir -p integrations/discord
```

Create `integrations/discord/pyproject.toml`:

```toml
[project]
name = "pepper-discord"
version = "0.1.0"
description = "Pepper Discord bot — bridges Discord to the channel server"
requires-python = ">=3.12"
dependencies = [
    "discord.py>=2.7.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.2.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.0",
]
```

Create `integrations/discord/.python-version`:

```
3.12
```

Create `integrations/discord/.env.example`:

```
DISCORD_BOT_TOKEN=your-bot-token-here
PEPPER_CHANNEL_URL=http://localhost:8788
```

- [ ] **Step 2: Install dependencies**

```bash
cd integrations/discord && uv sync && cd ../..
```

- [ ] **Step 3: Commit**

```bash
git add integrations/discord/pyproject.toml integrations/discord/.python-version integrations/discord/.env.example integrations/discord/uv.lock
git commit -m "feat: initialize Discord bot uv project with dependencies"
```

---

### Task 5: Discord Bot — Config Module

**Files:**
- Create: `integrations/discord/config.py`

- [ ] **Step 1: Write config module**

```python
"""Configuration for the Pepper Discord bot."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the bot directory
load_dotenv(Path(__file__).parent / ".env")

DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_URL: str = os.environ.get("PEPPER_CHANNEL_URL", "http://localhost:8788")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN is not set. "
        "Copy .env.example to .env and add your bot token."
    )
```

- [ ] **Step 2: Commit**

```bash
git add integrations/discord/config.py
git commit -m "feat: add Discord bot config module"
```

---

### Task 6: Discord Bot — Embed Helpers

**Files:**
- Create: `integrations/discord/embeds.py`
- Create: `tests/test_discord_embeds.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_discord_embeds.py`:

```python
"""Tests for Discord embed formatting helpers."""

import sys
from pathlib import Path

# Add the discord integration to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "discord"))


def test_build_embed_basic():
    """Build an embed with title and description."""
    from embeds import build_embed

    embed_data = {
        "title": "Daily Briefing",
        "description": "Here's what's happening today.",
        "color": 3447003,
    }
    embed = build_embed(embed_data)
    assert embed.title == "Daily Briefing"
    assert embed.description == "Here's what's happening today."
    assert embed.color.value == 3447003


def test_build_embed_with_fields():
    """Build an embed with fields."""
    from embeds import build_embed

    embed_data = {
        "title": "Status",
        "fields": [
            {"name": "Calendar", "value": "3 meetings", "inline": True},
            {"name": "Email", "value": "5 unread", "inline": True},
        ],
    }
    embed = build_embed(embed_data)
    assert len(embed.fields) == 2
    assert embed.fields[0].name == "Calendar"
    assert embed.fields[0].value == "3 meetings"
    assert embed.fields[0].inline is True


def test_build_embed_empty():
    """Empty embed data returns a basic embed."""
    from embeds import build_embed

    embed = build_embed({})
    assert embed.title is None
    assert embed.description is None


def test_build_embed_none():
    """None input returns None."""
    from embeds import build_embed

    assert build_embed(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_discord_embeds.py -v
```

Expected: FAIL (embeds module not found or build_embed not defined).

- [ ] **Step 3: Write the embed helpers**

Create `integrations/discord/embeds.py`:

```python
"""Rich embed formatting helpers for Discord messages."""

from __future__ import annotations

from typing import Any

import discord


def build_embed(data: dict[str, Any] | None) -> discord.Embed | None:
    """Convert a metadata embed dict to a discord.Embed.

    Args:
        data: Dict with optional keys: title, description, color, fields.
              fields is a list of {name, value, inline} dicts.
              Returns None if data is None.
    """
    if data is None:
        return None

    embed = discord.Embed(
        title=data.get("title"),
        description=data.get("description"),
        color=discord.Color(data["color"]) if "color" in data else None,
    )

    for field in data.get("fields", []):
        embed.add_field(
            name=field["name"],
            value=field["value"],
            inline=field.get("inline", False),
        )

    return embed
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_discord_embeds.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add integrations/discord/embeds.py tests/test_discord_embeds.py
git commit -m "feat: add Discord embed formatting helpers with tests"
```

---

### Task 7: Discord Bot — Main Bot Process

**Files:**
- Create: `integrations/discord/bot.py`

- [ ] **Step 1: Write the Discord bot**

```python
"""Pepper Discord bot — bridges Discord to the channel server.

Listens for messages in DMs and channels the bot is in.
Posts them to the channel server. Reads replies from the SSE stream
and sends them back to Discord.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import discord
import httpx

from config import CHANNEL_URL, DISCORD_BOT_TOKEN
from embeds import build_embed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
    # Ignore our own messages
    if message.author == client.user:
        return

    # Ignore bot messages
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

    # Track the channel for typing indicator
    pending_chat_ids[chat_id] = message.channel

    async with httpx.AsyncClient() as http:
        try:
            # Show typing while sending
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
                    backoff = 1.0  # Reset on successful connection
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

    # Parse chat_id to find the channel
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
        # Try fetching it (might be a DM channel not in cache)
        try:
            channel = await client.fetch_channel(channel_id)
        except discord.NotFound:
            log.warning(f"Channel {channel_id} not found")
            return

    # Remove from pending (stop typing indicator tracking)
    pending_chat_ids.pop(chat_id, None)

    # Handle reactions
    reply_type = metadata.get("type", "message")
    reactions = metadata.get("reactions", [])

    # Try to find the original message for reactions
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

    # If reaction-only, we're done
    if reply_type == "reaction":
        return

    # Build and send the reply
    embed_data = metadata.get("embed")
    embed = build_embed(embed_data)

    if text:
        # Discord has a 2000 char limit per message
        if len(text) <= 2000:
            await channel.send(text, embed=embed)
        else:
            # Split into chunks
            for i in range(0, len(text), 2000):
                chunk = text[i:i + 2000]
                # Only attach embed to the last chunk
                chunk_embed = embed if i + 2000 >= len(text) else None
                await channel.send(chunk, embed=chunk_embed)
    elif embed:
        await channel.send(embed=embed)


# Common emoji name -> unicode mapping
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
        await asyncio.sleep(8)  # Discord typing expires after 10s
        for chat_id, channel in list(pending_chat_ids.items()):
            try:
                await channel.typing()
            except Exception:
                pending_chat_ids.pop(chat_id, None)


@client.event
async def on_connect():
    """Start background tasks after connecting."""
    client.loop.create_task(listen_for_replies())
    client.loop.create_task(keep_typing())


def main():
    """Entry point."""
    log.info("Starting Pepper Discord bot...")
    client.run(DISCORD_BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add integrations/discord/bot.py
git commit -m "feat: add Discord bot with message bridging, embeds, reactions, and typing"
```

---

### Task 8: Launch Scripts

**Files:**
- Create: `scripts/start-pepper.sh`
- Create: `scripts/start-pepper.bat`
- Create: `scripts/stop-pepper.sh`
- Create: `scripts/stop-pepper.bat`

- [ ] **Step 1: Write start-pepper.sh**

```bash
#!/usr/bin/env bash
# Start Pepper: Claude Code session with channel + Discord bot
set -e

PEPPER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$PEPPER_DIR/.pids"
mkdir -p "$PID_DIR"

echo "Starting Pepper..."

# Start Claude Code with the channel
cd "$PEPPER_DIR"
claude --dangerously-load-development-channels server:pepper-channel &
CLAUDE_PID=$!
echo $CLAUDE_PID > "$PID_DIR/claude.pid"
echo "  Claude Code started (PID: $CLAUDE_PID)"

# Wait for channel server to be ready
echo -n "  Waiting for channel server"
for i in $(seq 1 30); do
    if curl -s http://localhost:8788/health > /dev/null 2>&1; then
        echo " ready!"
        break
    fi
    echo -n "."
    sleep 1
done

if ! curl -s http://localhost:8788/health > /dev/null 2>&1; then
    echo " FAILED"
    echo "Channel server did not start. Check Claude Code logs."
    kill $CLAUDE_PID 2>/dev/null
    exit 1
fi

# Start Discord bot
cd "$PEPPER_DIR/integrations/discord"
uv run python bot.py &
DISCORD_PID=$!
echo $DISCORD_PID > "$PID_DIR/discord.pid"
echo "  Discord bot started (PID: $DISCORD_PID)"

echo ""
echo "Pepper is running!"
echo "  Channel server: http://localhost:8788"
echo "  Discord bot: PID $DISCORD_PID"
echo ""
echo "Stop with: $PEPPER_DIR/scripts/stop-pepper.sh"

# Wait for either process to exit
wait -n $CLAUDE_PID $DISCORD_PID 2>/dev/null || true
echo "A process exited. Shutting down..."
"$PEPPER_DIR/scripts/stop-pepper.sh"
```

- [ ] **Step 2: Write stop-pepper.sh**

```bash
#!/usr/bin/env bash
# Stop Pepper: kill all managed processes
PEPPER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$PEPPER_DIR/.pids"

echo "Stopping Pepper..."

for pidfile in "$PID_DIR"/*.pid; do
    [ -f "$pidfile" ] || continue
    PID=$(cat "$pidfile")
    NAME=$(basename "$pidfile" .pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        echo "  Stopped $NAME (PID: $PID)"
    else
        echo "  $NAME already stopped"
    fi
    rm -f "$pidfile"
done

echo "Pepper stopped."
```

- [ ] **Step 3: Write start-pepper.bat**

```batch
@echo off
REM Start Pepper: Claude Code session with channel + Discord bot

set PEPPER_DIR=%~dp0..
set PID_DIR=%PEPPER_DIR%\.pids
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

echo Starting Pepper...

REM Set Git Bash path for Claude Code
if not defined CLAUDE_CODE_GIT_BASH_PATH (
    set CLAUDE_CODE_GIT_BASH_PATH=E:\Program Files\Git\bin\bash.exe
)

REM Start Claude Code with channel
cd /d "%PEPPER_DIR%"
start /B "" claude --dangerously-load-development-channels server:pepper-channel

REM Wait for channel server
echo   Waiting for channel server...
:wait_loop
timeout /t 1 /nobreak >nul
curl.exe -s http://localhost:8788/health >nul 2>&1
if errorlevel 1 goto wait_loop
echo   Channel server ready!

REM Start Discord bot
cd /d "%PEPPER_DIR%\integrations\discord"
start /B "" uv run python bot.py

echo.
echo Pepper is running!
echo   Channel server: http://localhost:8788
echo.
echo Stop with: Ctrl+C or close this window
pause
```

- [ ] **Step 4: Write stop-pepper.bat**

```batch
@echo off
REM Stop Pepper: kill all managed processes
echo Stopping Pepper...
taskkill /IM claude.exe /F 2>nul
taskkill /IM python.exe /F 2>nul
echo Pepper stopped.
```

- [ ] **Step 5: Make scripts executable**

```bash
chmod +x scripts/start-pepper.sh scripts/stop-pepper.sh
```

- [ ] **Step 6: Commit**

```bash
git add scripts/
git commit -m "feat: add launch and stop scripts for Pepper (Linux + Windows)"
```

---

### Task 9: Discord Bot Setup Documentation

**Files:**
- Create: `integrations/discord/README.md`

- [ ] **Step 1: Write setup instructions**

```markdown
# Pepper Discord Bot

Bridges Discord messages to Pepper's channel server.

## Discord Developer Portal Setup

1. Go to https://discord.com/developers/applications
2. Click **New Application**, name it "Pepper" (or your preferred name)
3. Go to **Bot** section:
   - Click **Reset Token** and copy the token
   - Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. Go to **OAuth2 > URL Generator**:
   - Scopes: select `bot`
   - Bot Permissions: select:
     - Send Messages
     - Send Messages in Threads
     - Read Message History
     - Add Reactions
     - View Channels
   - Copy the generated URL and open it to add the bot to your server

## Configuration

```bash
cp .env.example .env
# Edit .env and add your bot token:
# DISCORD_BOT_TOKEN=your-token-here
```

## Running

The bot is started automatically by the launch script:

```bash
# From the pepper root directory:
./scripts/start-pepper.sh
```

Or run standalone for testing:

```bash
cd integrations/discord
uv run python bot.py
```

## How It Works

- The bot listens for messages in all channels it's been added to, plus DMs
- Messages are forwarded to the channel server at localhost:8788
- Replies from Pepper come back via SSE stream and are sent to Discord
- The bot shows a typing indicator while Pepper is thinking
- Pepper can react to messages and send rich embeds
```

- [ ] **Step 2: Commit**

```bash
git add integrations/discord/README.md
git commit -m "docs: add Discord bot setup instructions"
```

---

### Task 10: End-to-End Integration Test

- [ ] **Step 1: Manual end-to-end test**

1. Create your `.env` file:
```bash
cd integrations/discord
cp .env.example .env
# Edit .env with your bot token
```

2. Start Pepper:
```bash
./scripts/start-pepper.sh
```

3. In Discord, DM the bot: "What is your name?"

Expected:
- Typing indicator appears
- Pepper replies with her name (Pepper)
- Reply appears in Discord

4. In a Discord channel the bot is in, send: "Give me a thumbs up"

Expected:
- Pepper reacts to your message with a thumbs up emoji

5. Check health:
```bash
curl.exe http://localhost:8788/health
```

Expected: Shows "discord" in registered_sources, routing_table_size > 0.

6. Stop Pepper:
```bash
./scripts/stop-pepper.sh
```

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "feat: Pepper MVP complete — channel server, Discord bot, launch scripts"
git push origin main
```
