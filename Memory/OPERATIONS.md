# Operations

## Vault
- **Location:** Memory/
- **Search:** `uv run qmd search vault "query"` for semantic search
- **Narrow search:** `uv run qmd search vault "query" --path-prefix projects/niwc`
- **File watcher:** pyqmd auto-indexes on file changes (no manual reindexing needed)

## Directory Map
- `daily/raw/` — append-only session logs (written by hooks)
- `daily/summaries/` — curated daily summaries with pointers (written by reflection at 3 AM)
- `weekly/` — weekly summaries (written Sunday 3 AM)
- `monthly/` — monthly summaries (written 1st of month)
- `quarterly/` — quarterly summaries
- `yearly/` — yearly summaries
- `projects/` — org/project hierarchy (see below)
- `meetings/` — meeting notes and decisions
- `research/` — PhD and AI research
- `clients/` — client/customer info
- `content/` — content ideas and drafts
- `team/` — team context
- `drafts/active/` — auto-generated reply drafts
- `drafts/sent/` — real replies (voice-matching corpus)

## Projects
- Each organization gets a folder: `projects/niwc-atlantic/`
- Each project within an org gets a subfolder: `projects/niwc-atlantic/friday/`
- Standalone projects go directly in `projects/`: `projects/pepper/`
- Every project has a `STATUS.md` with: Status, Priority, Cadence, Current Focus, Blockers, Next Steps
- Tags: `#niwc/friday`, `#niwc/jazz`, `#project/pepper`

## Project STATUS.md Fields
- **Status:** Active | Paused | Archived
- **Priority:** High | Medium | Low
- **Cadence:** Daily | Weekly | Monthly | None
- Morning briefing includes Active projects matching today's cadence

## Daily Log Format
Entries use: `## HH:MM [source] (session: <id>)` where source is `session`, `pre-compact`, `session-end`, or `heartbeat`. The session ID enables deduplication between PreCompact and SessionEnd hooks.

## Task Conventions
- Due date: `📅 YYYY-MM-DD`
- Priority: `⏫` high, `🔼` medium, `🔽` low
- Project tag: `#project/name`
- Global inbox: `Memory/TASKS.md`
- Per-project tasks: `projects/{org}/{project}/tasks.md`

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

## Spawning Sessions
- Scheduled tasks use: `uv run python .claude/scripts/spawn_session.py`
- Hooks do NOT fire on spawned sessions (`claude -p` is non-interactive)
- Spawned sessions get Tier 1 context via CLAUDE.md (loaded automatically)
- For additional context, use `--append-system-prompt` in the spawn script

## Reflection Schedule
- **Daily:** 3 AM ET — summarize raw logs → `daily/summaries/`
- **Weekly:** Sunday 3 AM ET — summarize daily summaries → `weekly/`
- **Monthly:** 1st of month 3 AM ET → `monthly/`
- **Quarterly/Yearly:** same pattern
- All configurable by editing this file
