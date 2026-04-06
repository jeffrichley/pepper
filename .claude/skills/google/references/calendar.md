# Google Calendar Reference

## pg CLI Command Reference

### pg auth login
Opens browser for OAuth2 consent. Stores token at `~/.pepper/google/token.json`.

### pg auth status [--json]
Check authentication state. Returns: authenticated, expired, not_configured, or error.

### pg calendar events [options] [--json]
| Option | Description |
|--------|-------------|
| `--today` | Today's events (default) |
| `--date DATE` | Events for YYYY-MM-DD |
| `--week` | Monday through Sunday |
| `--start DATE --end DATE` | Custom range |
| `--calendar ID` | Calendar ID (default: primary) |
| `--max N` | Max results (default: 50) |

### pg calendar freebusy [options] [--json]
| Option | Description |
|--------|-------------|
| `--today` | Today (default) |
| `--date DATE` | Specific date or "tomorrow" |
| `--start DATE --end DATE` | Custom range |
| `--calendar ID` | Calendar ID |

Free blocks computed within working hours (default 8AM-6PM ET).

### pg calendar create SUMMARY [options] [--json]
| Option | Description |
|--------|-------------|
| `--start DATETIME` | Start (YYYY-MM-DD HH:MM) |
| `--end DATETIME` | End time |
| `--duration MINUTES` | Alternative to --end |
| `--date DATE` | All-day event |
| `--location TEXT` | Location |
| `--description TEXT` | Description |
| `--attendees EMAIL,...` | Comma-separated |
| `--calendar ID` | Calendar ID |

### pg calendar delete EVENT_ID [--calendar ID]
Delete an event by ID.

### pg calendar calendars [--json]
List all calendars.

## Date/Time Formats
- Dates: `YYYY-MM-DD` (e.g., 2026-04-07)
- Times: `YYYY-MM-DD HH:MM` (e.g., 2026-04-07 10:00)
- RFC3339: `2026-04-07T10:00:00-04:00`
- All times default to US/Eastern timezone

## Common Errors
| Error | Cause | Fix |
|-------|-------|-----|
| "Not authenticated" | No token | `pg auth login` |
| "Token expired" | Refresh failed | `pg auth login` |
| 403 Forbidden | Scope missing | `pg auth login` (re-consent) |
| 404 Not Found | Event deleted | Inform user |
| 429 Rate Limit | Too many requests | Wait 60s, retry |

## JSON Output Format

### Events
```json
[{"id": "...", "summary": "...", "start": "...", "end": "...", "all_day": false, "location": "...", "attendees": [...], "status": "...", "html_link": "..."}]
```

### Free/Busy
```json
{"busy": [{"start": "...", "end": "..."}], "free": [{"start": "...", "end": "..."}]}
```
