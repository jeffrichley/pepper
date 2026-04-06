# Pepper Google Integration Skill + CLI

## Goal

Give Pepper access to Google Workspace services through a single skill and CLI tool (`pg`). Starting with Calendar, designed to grow into Gmail, Drive, Docs, etc. Uses `google-api-python-client` so all Google APIs follow the same patterns.

## Architecture

```
Claude Code (Pepper's session)
  │
  └── Skill: .claude/skills/google/
        │
        ├── SKILL.md (loaded into context, teaches Pepper workflows)
        │     └── Dynamic context: !`pg calendar events --today --json`
        │
        ├── references/ (loaded on demand)
        │     └── calendar.md
        │
        └── scripts/ (uv project, executed via Bash)
              ├── pg.py          ← typer CLI entry point
              ├── auth.py        ← OAuth2 + token management
              └── calendar.py    ← Calendar subcommands
```

Pepper invokes the CLI via Bash: `pg calendar events --today --json`. The skill's SKILL.md teaches her when and how.

## CLI Tool: `pg` (pepper-google)

### Auth Commands

**pg auth login**
- Opens browser for OAuth2 consent flow
- Uses `client_secret.json` from the Google Cloud project
- Stores token at `~/.pepper/google/token.json`
- Scopes requested: `calendar.readonly`, `calendar.events` (expand as services are added)

**pg auth status**
- Prints auth state: authenticated, expired, or not configured
- Shows which scopes are granted
- Shows token expiry time

### Calendar Commands

**pg calendar events**

List calendar events for a time range.

```
pg calendar events --today --json
pg calendar events --date 2026-04-07 --json
pg calendar events --week --json
pg calendar events --start 2026-04-07 --end 2026-04-14 --json
```

Options:
- `--today` — today's events (default if no range specified)
- `--date DATE` — events for a specific date
- `--week` — events for the current week (Monday to Sunday)
- `--start DATE --end DATE` — custom range
- `--calendar CALENDAR_ID` — specific calendar (default: primary)
- `--json` — JSON output for Claude; rich terminal output by default
- `--max N` — maximum number of events (default: 50)

JSON output format:
```json
[
  {
    "id": "abc123",
    "summary": "Team standup",
    "start": "2026-04-07T09:00:00-04:00",
    "end": "2026-04-07T09:30:00-04:00",
    "location": "Zoom",
    "attendees": ["bob@example.com", "alice@example.com"],
    "status": "confirmed",
    "html_link": "https://calendar.google.com/event?eid=abc123"
  }
]
```

**pg calendar freebusy**

Find free/busy blocks for a date range.

```
pg calendar freebusy --today --json
pg calendar freebusy --date tomorrow --json
pg calendar freebusy --start 2026-04-07 --end 2026-04-08 --json
```

JSON output format:
```json
{
  "busy": [
    {"start": "2026-04-07T09:00:00-04:00", "end": "2026-04-07T09:30:00-04:00"},
    {"start": "2026-04-07T14:00:00-04:00", "end": "2026-04-07T15:00:00-04:00"}
  ],
  "free": [
    {"start": "2026-04-07T08:00:00-04:00", "end": "2026-04-07T09:00:00-04:00"},
    {"start": "2026-04-07T09:30:00-04:00", "end": "2026-04-07T14:00:00-04:00"},
    {"start": "2026-04-07T15:00:00-04:00", "end": "2026-04-07T18:00:00-04:00"}
  ]
}
```

Free slots are computed from busy blocks within working hours (configurable, default 8AM-6PM ET).

**pg calendar create**

Create a calendar event.

```
pg calendar create "Team standup" --start "2026-04-07 09:00" --end "2026-04-07 09:30"
pg calendar create "Lunch with Bob" --start "2026-04-07 12:00" --duration 60
pg calendar create "All day review" --date 2026-04-07
```

Options:
- `--start DATETIME` — start time
- `--end DATETIME` — end time
- `--duration MINUTES` — alternative to --end
- `--date DATE` — all-day event
- `--location TEXT` — location or link
- `--description TEXT` — event description
- `--attendees EMAIL,...` — comma-separated attendee emails
- `--calendar CALENDAR_ID` — target calendar (default: primary)
- `--json` — return created event as JSON

**pg calendar delete**

Delete a calendar event.

```
pg calendar delete EVENT_ID
```

**pg calendar calendars**

List available calendars.

```
pg calendar calendars --json
```

## OAuth2 Implementation

### Client Credentials

The Google Cloud project "pepper-491921" already has OAuth2 client credentials configured as an "installed" (desktop) application. The `client_secret.json` is stored at `C:\Users\jeffr\.openclaw\workspace\secrets\client_secret.json`.

The CLI reads the client secret from a configurable location:
- Default: `~/.pepper/google/client_secret.json`
- Override: `PG_CLIENT_SECRET` env var

On first setup, the user copies the client_secret.json to `~/.pepper/google/`.

### Token Storage

- Location: `~/.pepper/google/token.json`
- Contains: access_token, refresh_token, expiry, scopes
- Auto-refreshes expired access tokens using the refresh token
- If refresh fails (revoked), prints clear message directing user to `pg auth login`

### Scopes

Starting scopes for Calendar:
- `https://www.googleapis.com/auth/calendar.readonly` — read events and calendars
- `https://www.googleapis.com/auth/calendar.events` — create/modify/delete events

Future services add their scopes incrementally. Token is re-created when new scopes are needed.

## Skill: `.claude/skills/google/`

### SKILL.md

```yaml
---
name: google
description: Google Workspace integration for calendar, email, and documents. Use when user mentions calendar, schedule, meetings, availability, email, Gmail, inbox, Drive, or Google Docs. Handles event lookup, scheduling, free/busy queries, and email triage.
allowed-tools: Bash(pg *) Bash(uv --directory * run python pg.py *) Read
metadata:
  author: Pepper
  version: "1.0"
  mcp-server: none
---
```

### Dynamic Context

The SKILL.md pre-loads today's agenda when the skill loads:

```markdown
## Current Context

**Today's calendar:**
```!
uv --directory $CLAUDE_PROJECT_DIR/.claude/skills/google/scripts run python pg.py calendar events --today --json 2>/dev/null || echo "GOOGLE_NOT_CONFIGURED"
```
```

If output is `GOOGLE_NOT_CONFIGURED`, the skill's error handling section tells Pepper to guide the user through `pg auth login`.

### Workflow Instructions

The SKILL.md includes:

1. **Reading calendar** — when to check, how to format results, when to send to Discord
2. **Scheduling** — confirmation required before creating events, check freebusy first
3. **Morning briefing integration** — how to format calendar data for the daily Discord embed
4. **Error handling** — auth failures, API errors, rate limits
5. **Confirmation gates** — never create/modify/delete without explicit user confirmation

### References

`references/calendar.md` contains:
- Full `pg calendar` command reference with all flags
- Common date/time format patterns
- API rate limits and quotas
- Error codes and recovery steps
- Example workflows (multi-step: check free, propose time, create event)

## File Structure

```
.claude/skills/google/
  SKILL.md                          # Skill instructions + dynamic context
  references/
    calendar.md                     # Calendar command reference + patterns

.claude/skills/google/scripts/
  pyproject.toml                    # uv project
  pg.py                             # Main CLI entry point (typer app)
  auth.py                           # OAuth2 flow + token management
  calendar.py                       # Calendar subcommands

~/.pepper/
  google/
    client_secret.json              # OAuth2 client credentials (copied once)
    token.json                      # OAuth2 token (auto-managed)
```

## Dependencies (scripts/pyproject.toml)

```toml
[project]
name = "pepper-google"
version = "0.1.0"
description = "Pepper Google Workspace CLI"
requires-python = ">=3.12"
dependencies = [
    "google-api-python-client>=2.0.0",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.0",
]
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PG_CLIENT_SECRET` | `~/.pepper/google/client_secret.json` | OAuth2 client credentials |
| `PG_TOKEN_PATH` | `~/.pepper/google/token.json` | OAuth2 token storage |
| `PG_TIMEZONE` | `US/Eastern` | Default timezone for date parsing |
| `PG_WORKING_HOURS_START` | `08:00` | Start of working hours (for freebusy) |
| `PG_WORKING_HOURS_END` | `18:00` | End of working hours (for freebusy) |

## Testing

- `auth.py`: Test token loading, refresh logic, scope checking (mock Google API)
- `calendar.py`: Test event parsing, freebusy computation, date range building (mock API responses)
- `pg.py`: Test CLI argument parsing (typer testing patterns)
- Integration: `pg calendar events --today --json` returns valid JSON (requires real auth, marked slow)

## Security

- `client_secret.json` and `token.json` stored outside repo at `~/.pepper/google/`
- No credentials in the skill directory or repo
- `allowed-tools` restricts Bash to only `pg` commands
- Write operations (create, delete) require explicit user confirmation in SKILL.md

## Out of Scope (for this iteration)

- Gmail subcommands (next iteration)
- Drive subcommands (future)
- Service account auth (only desktop/installed app flow for now)
- Multi-user / multi-account support
- Webhook subscriptions for real-time calendar changes
