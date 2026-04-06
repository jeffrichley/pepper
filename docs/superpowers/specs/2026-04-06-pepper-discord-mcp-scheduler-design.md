# Pepper Discord MCP + Scheduler Design

## Goal

Give Pepper outbound Discord capabilities (send messages, read channels, react) and a scheduler for proactive tasks (heartbeat, morning briefing, nightly reflection). Pepper manages her own scheduled jobs through MCP tools.

## Architecture

```
Claude Code (Pepper's session)
  │
  ├── Channel Server (MCP, TypeScript/Bun)
  │     └── Inbound: external messages pushed into session
  │
  └── Discord Integration (MCP, Python)
        ├── Discord Client (discord.py)
        │     ├── on_message → POST to channel server
        │     └── typing indicator management
        ├── Discord MCP Tools
        │     ├── send_discord_message
        │     ├── add_reaction
        │     ├── send_typing
        │     ├── list_channels
        │     ├── get_recent_messages
        │     └── get_channel_info
        ├── Scheduler MCP Tools
        │     ├── create_job
        │     ├── update_job
        │     ├── delete_job
        │     ├── list_jobs
        │     ├── pause_job
        │     └── resume_job
        ├── SSE Listener
        │     └── channel server replies → Discord
        └── Scheduler (APScheduler 4.x)
              ├── persists jobs to jobs.yaml
              └── POSTs prompts to channel server on schedule
```

**One process.** The Discord bot evolves into Pepper's main integration process. It runs the Discord client, MCP server, SSE listener, and scheduler in one async event loop sharing one Discord connection.

**Two MCP servers in Pepper's session:**
1. `pepper-channel` (TypeScript) — pushes inbound messages into the session
2. `pepper-discord` (Python) — outbound Discord tools + scheduler tools

Claude Code spawns both as subprocesses via `.mcp.json`.

## Discord MCP Tools

### Outbound

**send_discord_message**
```json
{
  "name": "send_discord_message",
  "inputSchema": {
    "type": "object",
    "properties": {
      "channel_id": { "type": "string", "description": "Discord channel ID" },
      "text": { "type": "string", "description": "Message text (markdown supported)" },
      "embed": {
        "type": "object",
        "description": "Optional rich embed: title, description, color (int), fields (array of {name, value, inline})"
      }
    },
    "required": ["channel_id"]
  }
}
```

Sends a message to any Discord channel or DM. Supports text, embeds, or both. Handles the 2000-char limit by splitting into chunks automatically.

**add_reaction**
```json
{
  "name": "add_reaction",
  "inputSchema": {
    "type": "object",
    "properties": {
      "channel_id": { "type": "string" },
      "message_id": { "type": "string" },
      "emoji": { "type": "string", "description": "Emoji name (thumbs_up, fire, etc.) or unicode character" }
    },
    "required": ["channel_id", "message_id", "emoji"]
  }
}
```

**send_typing**
```json
{
  "name": "send_typing",
  "inputSchema": {
    "type": "object",
    "properties": {
      "channel_id": { "type": "string" }
    },
    "required": ["channel_id"]
  }
}
```

### Inbound/Read

**list_channels**
```json
{
  "name": "list_channels",
  "inputSchema": {
    "type": "object",
    "properties": {
      "guild_id": { "type": "string", "description": "Optional: filter to a specific server" }
    }
  }
}
```

Returns a list of channels Pepper has access to: `[{ id, name, type, topic, guild_id, guild_name }]`.

**get_recent_messages**
```json
{
  "name": "get_recent_messages",
  "inputSchema": {
    "type": "object",
    "properties": {
      "channel_id": { "type": "string" },
      "limit": { "type": "integer", "description": "Number of messages (default 10, max 50)" }
    },
    "required": ["channel_id"]
  }
}
```

Returns recent messages: `[{ id, author, content, timestamp, attachments }]`.

**get_channel_info**
```json
{
  "name": "get_channel_info",
  "inputSchema": {
    "type": "object",
    "properties": {
      "channel_id": { "type": "string" }
    },
    "required": ["channel_id"]
  }
}
```

Returns channel details: `{ id, name, topic, type, guild_id, guild_name, member_count }`.

## Scheduler MCP Tools

**create_job**
```json
{
  "name": "create_job",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": { "type": "string", "description": "Unique job identifier (snake_case)" },
      "trigger": { "type": "string", "enum": ["interval", "cron", "once"], "description": "Trigger type" },
      "schedule": {
        "type": "object",
        "description": "For interval: {minutes, hours, seconds}. For cron: {hour, minute, day_of_week, day, month}. For once: {run_at: ISO datetime}"
      },
      "prompt": { "type": "string", "description": "The prompt to send to the channel server when this job fires" },
      "channel_hint": { "type": "string", "description": "Optional: suggested Discord channel name for context" },
      "timezone": { "type": "string", "description": "Timezone (default: US/Eastern)" }
    },
    "required": ["name", "trigger", "schedule", "prompt"]
  }
}
```

**update_job**
```json
{
  "name": "update_job",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" },
      "schedule": { "type": "object" },
      "prompt": { "type": "string" },
      "channel_hint": { "type": "string" },
      "timezone": { "type": "string" }
    },
    "required": ["name"]
  }
}
```

**delete_job**
```json
{
  "name": "delete_job",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" }
    },
    "required": ["name"]
  }
}
```

**list_jobs**
```json
{
  "name": "list_jobs",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

Returns all jobs with their schedules, next run time, and status (active/paused): `[{ name, trigger, schedule, prompt, channel_hint, next_run, status }]`.

**pause_job / resume_job**
```json
{
  "name": "pause_job",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": { "type": "string" }
    },
    "required": ["name"]
  }
}
```

Same schema for `resume_job`.

## Scheduler Internals

**APScheduler 4.x** runs in the bot's async event loop. Jobs are persisted to `integrations/discord/jobs.yaml` so they survive restarts.

**Job execution:** When a job fires, the scheduler POSTs to the channel server:

```json
{
  "source": "scheduler",
  "chat_id": "scheduler-{job_name}-{timestamp}",
  "sender": "scheduler",
  "content": "{prompt from job config}",
  "metadata": {
    "job_name": "heartbeat",
    "channel_hint": "#pepper-chat"
  }
}
```

Pepper receives this in her session, does whatever the prompt asks, and uses the Discord MCP tools to send results to the appropriate channel.

**Default jobs** seeded on first run:

```yaml
heartbeat:
  trigger: interval
  schedule:
    minutes: 30
  prompt: >
    Heartbeat check: Review pending tasks, scan project statuses for
    anything that needs attention. If anything is noteworthy, send it
    to the appropriate Discord channel using send_discord_message.
    Check OPERATIONS.md for channel mappings.
  channel_hint: "#pepper-chat"
  timezone: US/Eastern

morning_briefing:
  trigger: cron
  schedule:
    hour: 7
    minute: 0
  prompt: >
    Morning briefing for Jeff. Check project statuses, scan for
    upcoming deadlines this week, summarize yesterday's activity
    from daily logs, and list today's priorities. Send the briefing
    to #pepper-chat using send_discord_message with a rich embed.
  channel_hint: "#pepper-chat"
  timezone: US/Eastern

nightly_reflection:
  trigger: cron
  schedule:
    hour: 3
    minute: 0
  prompt: >
    Nightly reflection: Summarize today's raw logs from daily/raw/
    into a daily summary. Write it to daily/summaries/YYYY-MM-DD.md
    with pointer links to raw entries. Identify patterns, decisions
    made, and open loops. Send a brief summary to #pepper-chat.
  channel_hint: "#pepper-chat"
  timezone: US/Eastern
```

## Channel Registry

Add to `Memory/OPERATIONS.md` under a new `## Discord Channels` section:

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

This is a Tier 1 file — loaded every session. Pepper reads it to know where to send things and maintains it herself over time.

## MCP Transport

The Discord integration process communicates with Claude Code over **stdio** (standard MCP transport). Claude Code spawns it as a subprocess.

**Problem:** The current bot.py is launched by the start script as a standalone process, not by Claude Code. For MCP to work over stdio, Claude Code needs to spawn it.

**Solution:** Split the Discord integration into two entry points:

1. `mcp_server.py` — MCP server over stdio. Claude Code spawns this. It starts the Discord client, scheduler, and SSE listener internally.
2. The start script no longer starts bot.py separately. Instead, `.mcp.json` registers `pepper-discord` and Claude Code spawns it automatically.

Updated `.mcp.json`:
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

The start script simplifies to just launching Claude Code. Both MCP servers start automatically as subprocesses.

## Updated Start Script

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")/.."
claude --dangerously-load-development-channels server:pepper-channel
```

That's it. Claude Code spawns both MCP servers. The Discord bot, scheduler, and SSE listener all start inside the `pepper-discord` MCP server process.

## File Structure

```
integrations/
  discord/
    pyproject.toml          # Add: apscheduler, mcp SDK
    mcp_server.py           # MCP server entry point (spawned by Claude Code)
    bot.py                  # Discord client + event handlers (imported by mcp_server)
    discord_tools.py        # Discord MCP tool implementations
    scheduler_tools.py      # Scheduler MCP tool implementations
    scheduler.py            # APScheduler setup and job execution
    embeds.py               # Existing embed helpers
    config.py               # Existing config module
    jobs.yaml               # Persisted job definitions
    .env                    # Bot token (gitignored)
    .env.example            # Template
```

## Dependencies (additions to pyproject.toml)

```toml
dependencies = [
    "discord.py>=2.7.0",
    "httpx>=0.28.0",
    "python-dotenv>=1.2.0",
    "apscheduler>=4.0.0",
    "mcp>=1.0.0",
    "pyyaml>=6.0.0",
]
```

## Security

- MCP server runs locally, spawned by Claude Code over stdio
- Discord bot token in .env, gitignored
- Channel server still localhost-only
- Scheduler jobs can only POST to the local channel server

## Testing

- Discord MCP tools: mock discord.py client, verify tool calls produce correct API calls
- Scheduler tools: create/update/delete/list jobs, verify jobs.yaml persistence
- Scheduler execution: mock httpx, verify POST to channel server with correct payload
- Integration: start MCP server, call tools via MCP protocol, verify responses

## Out of Scope

- Voice channels
- File attachments in Discord
- Slash commands
- Permission relay from Discord
- Remote channel server access
- Multi-guild management (single guild for MVP)
