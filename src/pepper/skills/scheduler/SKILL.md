---
name: scheduler
description: Manage Pepper's scheduled jobs. Use when user mentions scheduling, recurring tasks, cron, timers, reminders, briefings, heartbeats, or automated prompts.
---

# Scheduler

Pepper's scheduler runs as its own MCP server (`pepper-scheduler`). It fires jobs on a schedule — either by sending a prompt to the channel server (which wakes Pepper up) or by calling a Python function directly.

Jobs persist to SQLite (`~/.pepper/scheduler.db`). They survive restarts.

## Tools

| Tool | What it does |
|------|-------------|
| `create_job` | Create a new scheduled job |
| `update_job` | Change schedule, prompt, or channel hint on an existing job |
| `delete_job` | Remove a job permanently |
| `list_jobs` | Show all jobs with next run times |
| `pause_job` | Stop a job from firing (keeps definition) |
| `resume_job` | Unpause a paused job |

## create_job

```json
{
  "name": "daily_standup_reminder",
  "trigger": "cron",
  "schedule": { "hour": 8, "minute": 45 },
  "prompt": "Remind Jeff about standup in 15 minutes. Send a Discord message to #pepper-chat.",
  "channel_hint": "#pepper-chat",
  "timezone": "US/Eastern"
}
```

**Parameters:**

- `name` — Unique identifier, snake_case. This is also the job ID in the database.
- `trigger` — Either `"interval"` or `"cron"`.
- `schedule` — Depends on trigger type (see below).
- `prompt` — The full prompt sent to Pepper when the job fires. Be specific about what Pepper should do and where to send output.
- `channel_hint` — Optional. Suggests which Discord channel is relevant. Does not control routing — the prompt should explicitly say where to send messages.
- `timezone` — For cron triggers. Default: `US/Eastern`.

### Interval schedules

Fire every N time units. At least one field required.

```json
{ "hours": 1 }
{ "minutes": 30 }
{ "seconds": 300 }
{ "hours": 2, "minutes": 30 }
```

### Cron schedules

Fire at specific times. Uses standard cron field names.

```json
{ "hour": 7, "minute": 0 }
{ "hour": 9, "minute": 0, "day_of_week": "mon-fri" }
{ "hour": 0, "minute": 0, "day": 1 }
{ "hour": 22, "minute": 0, "day_of_week": "sun" }
```

**Fields:** `hour`, `minute`, `day_of_week`, `day`, `month`. All optional except you need at least `hour` or `minute` to be useful.

**day_of_week values:** `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`. Ranges work: `mon-fri`.

## update_job

Only pass the fields you want to change. Everything else stays the same.

```json
{
  "name": "heartbeat",
  "schedule": { "minutes": 15 },
  "prompt": "Quick status check. Only message Discord if something needs attention."
}
```

## Examples

### Every-30-minute heartbeat

```json
{
  "name": "heartbeat",
  "trigger": "interval",
  "schedule": { "minutes": 30 },
  "prompt": "Heartbeat check: Review pending tasks in Memory/TASKS.md, scan project statuses for anything that needs attention. If anything is noteworthy, send it to the appropriate Discord channel using send_discord_message. Check Memory/OPERATIONS.md for channel mappings.",
  "channel_hint": "#pepper-chat"
}
```

### Morning briefing at 7 AM Eastern

```json
{
  "name": "morning_briefing",
  "trigger": "cron",
  "schedule": { "hour": 7, "minute": 0 },
  "prompt": "Morning briefing for Jeff. Check project statuses, scan for upcoming deadlines this week, summarize yesterday's activity from daily logs, and list today's priorities. Send the briefing to the pepper-chat Discord channel using send_discord_message with a rich embed.",
  "channel_hint": "#pepper-chat",
  "timezone": "US/Eastern"
}
```

### Weekday-only reminder

```json
{
  "name": "eod_reflection",
  "trigger": "cron",
  "schedule": { "hour": 17, "minute": 0, "day_of_week": "mon-fri" },
  "prompt": "End-of-day reflection: What did Jeff accomplish today? What's carrying over to tomorrow? Write a brief summary to Memory/daily/summaries/ and send a short version to #pepper-chat.",
  "channel_hint": "#pepper-chat",
  "timezone": "US/Eastern"
}
```

### Weekly review on Sunday evening

```json
{
  "name": "weekly_review",
  "trigger": "cron",
  "schedule": { "hour": 20, "minute": 0, "day_of_week": "sun" },
  "prompt": "Weekly review: Summarize this week's daily summaries into a weekly rollup. Highlight wins, blockers, and priorities for next week. Write to Memory/weekly/ and send a summary embed to #pepper-chat.",
  "channel_hint": "#pepper-chat",
  "timezone": "US/Eastern"
}
```

### First of the month recap

```json
{
  "name": "monthly_recap",
  "trigger": "cron",
  "schedule": { "hour": 8, "minute": 0, "day": 1 },
  "prompt": "Monthly recap: Roll up the weekly summaries from last month. Identify trends, completed projects, and what's in flight. Write to Memory/monthly/ and send a summary to #pepper-chat.",
  "channel_hint": "#pepper-chat",
  "timezone": "US/Eastern"
}
```

### Pause and resume

```json
// Pause the heartbeat while Jeff is on vacation
{ "name": "heartbeat" }  // -> pause_job

// Resume when he's back
{ "name": "heartbeat" }  // -> resume_job
```

## Writing good prompts

The `prompt` field is the full instruction Pepper receives when the job fires. It needs to be self-contained because Pepper may not have recent conversation context.

**Do:**
- Say exactly what to check and where (`Memory/TASKS.md`, `Memory/daily/raw/`)
- Say where to send output (`send_discord_message` to `#pepper-chat`)
- Say what format to use (embed, plain text, brief vs detailed)
- Include the job's purpose so Pepper understands intent

**Don't:**
- Assume Pepper remembers prior context — each firing is independent
- Leave output destination vague ("send it somewhere")
- Write one-word prompts ("check") — be specific

## Default seed jobs

These are defined in `jobs.yaml` and auto-seeded on first run:

| Job | Trigger | Schedule | Purpose |
|-----|---------|----------|---------|
| `heartbeat` | interval | 30 min | Review tasks, alert if anything needs attention |
| `morning_briefing` | cron | 7:00 AM ET | Daily priorities and deadlines |
| `nightly_reflection` | cron | 3:00 AM ET | Summarize the day's raw logs |
| `attachment_cleanup` | cron | 4:00 AM ET | Clean old attachment files (function job) |

Seed jobs are only created if they don't already exist. Modifying or deleting them via tools is permanent — they won't be re-seeded.

## How it works under the hood

1. Scheduler fires a job on schedule
2. For prompt jobs: POSTs to `pepper-channel` HTTP endpoint (`/message`)
3. Channel server sends an MCP notification to Claude Code
4. Claude Code wakes up and processes the prompt
5. Pepper uses Discord tools (or any other tools) to act on the prompt

Function jobs (`type: function` in jobs.yaml) skip steps 2-4 and call Python directly. These are for maintenance tasks like cleanup that don't need Pepper's reasoning.
