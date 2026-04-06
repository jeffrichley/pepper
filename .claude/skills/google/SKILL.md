---
name: google
description: Google Workspace integration for calendar, email, and documents. Use when user mentions calendar, schedule, meetings, availability, events, free time, or booking. Handles event lookup, scheduling, free/busy queries, and event creation. Do NOT use for general web search or non-Google questions.
allowed-tools: Bash(uv --directory * run python pg.py *) Read
metadata:
  author: Pepper
  version: "1.0"
---

# Google Workspace

Pepper's Google integration. Currently supports Calendar. Gmail and Drive coming soon.

## Setup Check

If any command below returns an error about authentication, guide the user:
1. Run: `uv --directory $CLAUDE_PROJECT_DIR/.claude/skills/google/scripts run python pg.py auth login`
2. This opens a browser for Google OAuth consent
3. After approval, the token is saved at `~/.pepper/google/token.json`

## Current Context

**Today's calendar:**
```!
uv --directory $CLAUDE_PROJECT_DIR/.claude/skills/google/scripts run python pg.py calendar events --today --json 2>/dev/null || echo "GOOGLE_NOT_CONFIGURED"
```

If the output above is `GOOGLE_NOT_CONFIGURED`, tell the user to run `pg auth login` first.

## Calendar Commands

All commands run via:
`uv --directory $CLAUDE_PROJECT_DIR/.claude/skills/google/scripts run python pg.py calendar [subcommand]`

### Reading Events
- Today: `pg.py calendar events --today --json`
- Specific date: `pg.py calendar events --date 2026-04-07 --json`
- This week: `pg.py calendar events --week --json`
- Date range: `pg.py calendar events --start 2026-04-07 --end 2026-04-14 --json`

### Finding Free Time
- Today: `pg.py calendar freebusy --today --json`
- Tomorrow: `pg.py calendar freebusy --date tomorrow --json`

### Creating Events
CRITICAL: Never create an event without explicit user confirmation. Always show what you plan to create and wait for approval.

- Timed: `pg.py calendar create "Meeting" --start "2026-04-07 10:00" --end "2026-04-07 11:00" --json`
- With duration: `pg.py calendar create "Lunch" --start "2026-04-07 12:00" --duration 60 --json`
- All day: `pg.py calendar create "Review day" --date 2026-04-07 --json`

### Deleting Events
CRITICAL: Never delete without explicit user confirmation.

- `pg.py calendar delete EVENT_ID`

### Listing Calendars
- `pg.py calendar calendars --json`

## Workflow Guidelines

- When asked about schedule: fetch events first, then summarize
- When asked to schedule something: check freebusy first, suggest times, get confirmation, then create
- For morning briefings: fetch today's events and format as a summary
- When sending calendar info to Discord: use rich embeds with fields for each event
- Check `references/calendar.md` for detailed API patterns and error handling

## Error Handling

- "Not authenticated": Direct user to `pg auth login`
- "Token expired": The CLI auto-refreshes. If it fails, direct to `pg auth login`
- API quota errors: Wait 60 seconds, retry once
- 404 on event: Event was deleted or calendar changed, inform user
