# Pepper Foundation Design Spec

**Date:** 2026-04-04
**Scope:** Phase 0 (Environment), Phase 1 (Vault), Phase 2 (Hooks), Phase 3 (pyqmd)
**Approach:** B — Thin hooks + OPERATIONS.md teaches self-sufficiency

---

## Design Principles

1. **Claude Code is the runtime.** Scheduled tasks spawn short-lived Claude Code sessions via `claude -p`. No Agent SDK.
2. **Python for determinism, Claude for reasoning.** Python handles API calls, file I/O, indexing, notifications. Claude handles judgment — what's important, what to say, what to curate.
3. **Progressive disclosure.** Tier 1 context always loaded (~5 small files + recent summaries). Everything else retrieved on demand via pyqmd or file reads.
4. **Local files are king.** Markdown for memory, Python for logic, JSON for state. Obsidian is just the viewer.
5. **One brain, one agent.** Single Claude Code workspace. Not a swarm.

---

## Phase 0: Environment

### Dependencies (`pyproject.toml` via `uv`)

**Core:**
- `pyqmd` — hybrid RAG engine
- `filelock` — cross-platform file locking
- `plyer` — cross-platform notifications (later phases)
- `typer` — CLI framework
- `rich` — CLI output formatting
- `pyyaml` — YAML parsing
- `python-dotenv` — .env loading
- `watchdog` — file system watching (pyqmd file watcher)

**Dev:**
- `pytest`
- `pytest-asyncio`
- `ruff`

### `.env` (gitignored)

```
CLAUDE_CODE_GIT_BASH_PATH=E:\Program Files\Git\bin\bash.exe
```

Additional keys (Google OAuth, Microsoft, Discord, GitHub) added as integrations are built in later phases.

### `.gitignore` additions

```
.env
Memory/.obsidian/
.claude/data/
__pycache__/
*.lock
```

### Setup Commands

```bash
cd E:\workspaces\ai\pepper
uv init
uv python pin 3.12
uv add pyqmd filelock plyer typer rich pyyaml python-dotenv watchdog
uv add --dev pytest pytest-asyncio ruff
```

---

## Phase 1: Vault Structure

### Directory Layout

```
Memory/
  IDENTITY.md              # Agent name, emoji, role
  SOUL.md                  # Personality, boundaries, priorities
  USER.md                  # Jeff's profile, platforms, preferences
  MEMORY.md                # Curated long-term memory (reflection script only)
  OPERATIONS.md            # Vault map, tool usage, conventions (evolves)
  HEARTBEAT.md             # Plain-English monitoring checklist
  HABITS.md                # Daily pillars and habit tracking
  TASKS.md                 # Global task inbox
  daily/
    raw/                   # Append-only session logs
      2026-04-04.md
    summaries/             # Curated daily summaries with pointers
      2026-04-04.md
  weekly/
    2026-W14.md            # Weekly summary
  monthly/
    2026-04.md             # Monthly summary
  quarterly/
    2026-Q2.md             # Quarterly summary
  yearly/
    2026.md                # Yearly summary
  projects/
    niwc-atlantic/
      STATUS.md            # Org-level context
      friday/
        STATUS.md          # Project status, priority, cadence
        notes.md
        tasks.md
      jazz/
        STATUS.md
        notes.md
        tasks.md
    pepper/
      STATUS.md
      notes.md
      tasks.md
    phd-embedded-ai/
      STATUS.md
      notes.md
      tasks.md
  meetings/
  research/
  clients/
  content/
  team/
  tasks/                   # Overflow task files when TASKS.md gets too large
  drafts/
    active/                # Auto-generated reply drafts awaiting review
    sent/                  # Real replies captured (voice-matching corpus)
    expired/               # Stale drafts (auto-archived after 24h)
```

### Tier 1 Files (Always Loaded by SessionStart Hook)

| File | Purpose | Updated by |
|---|---|---|
| IDENTITY.md | Name, emoji, role | User (manually) |
| SOUL.md | Personality, boundaries, priorities | User + self-improve skill |
| USER.md | Jeff's profile, platforms, preferences | User (manually) |
| MEMORY.md | Curated long-term memory | Reflection script (3 AM) only |
| OPERATIONS.md | Vault map, tools, conventions | User + self-improve skill |

**Size constraint:** Tier 1 files must stay small. If any exceeds ~200 lines, it needs pruning or restructuring. MEMORY.md especially — the reflection script curates it.

SessionStart also injects the last 1-2 daily summaries and the most recent weekly summary.

### IDENTITY.md

```markdown
# Identity

**Name:** Pepper
**Emoji:** 🌶️
**Role:** Second Brain & Executive Assistant
**Created by:** Jeff Richley
```

Change the name here and it propagates everywhere. Every component reads IDENTITY.md, never hardcodes the name.

### SOUL.md

```markdown
# Soul

## Personality
[Voice, tone, communication style — customize to your liking]

## Behavioral Rules

### Proactivity Level: Assistant
- Act on low-risk items: log notes, organize files, auto-detect habits
- Ask permission for high-risk actions

### Hard Boundaries
- NEVER send emails or messages without explicit permission
- NEVER access financial data or make purchases
- NEVER delete anything without explicit permission

### Priorities
1. Track todos and deadlines — remind before due dates
2. Track all current projects — surface stalled work
3. Be a proactive executive assistant
4. Keep Jeff organized
5. Proactively manage systems and self-improve
```

### USER.md

```markdown
# User Profile

## About
- **Name:** Jeff Richley
- **Role:** CEO, AI Researcher, PhD candidate (Embedded AI in Robots)
- **Timezone:** Eastern

## Platforms
- Email: Gmail, Outlook
- Calendar: Google Calendar
- Chat: Discord
- Notes: Obsidian, Google Docs
- Storage: Google Drive, OneDrive
- Code: GitHub

## Drafting Criteria
- Draft replies to: direct questions, action items, meeting follow-ups
- Skip: newsletters, automated notifications, CC-only threads
```

### OPERATIONS.md

```markdown
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

## Spawning Sessions
- Scheduled tasks use: `uv run python .claude/scripts/spawn_session.py`
- Hooks fire on spawned sessions (SessionStart injects Tier 1 context)

## Reflection Schedule
- **Daily:** 3 AM ET — summarize raw logs → `daily/summaries/`
- **Weekly:** Sunday 3 AM ET — summarize daily summaries → `weekly/`
- **Monthly:** 1st of month 3 AM ET → `monthly/`
- **Quarterly/Yearly:** same pattern
- All configurable by editing this file
```

### HEARTBEAT.md

```markdown
# Heartbeat Checklist

## Every Check (30 min)
- [ ] Any meetings starting in the next 2 hours? Alert me 15 min before.
- [ ] Any tasks overdue or due today? Surface them.
- [ ] Any important unread emails in Gmail or Outlook?
- [ ] Any unread Discord @mentions?
- [ ] Any GitHub PRs requesting my review or CI failures?

## Morning (first check of the day)
- [ ] Reset yesterday's habits to History, create fresh checklist
- [ ] Generate daily briefing: today's calendar, due tasks, overnight messages
- [ ] Push briefing as notification

## Evening (last check of the day)
- [ ] Nudge for any unchecked habit pillars
- [ ] Summarize what happened today

## Weekly (Monday morning)
- [ ] Project digest: what moved, what's stuck, what needs attention
- [ ] Review stalled projects (no activity in 7+ days)
```

### Project STATUS.md Template

```markdown
# [Project Name]

**Status:** Active
**Priority:** High
**Cadence:** Daily
**Org:** [Organization name, if applicable]
**One-liner:** [What this project is]
**Started:** YYYY-MM-DD

## Workstreams

### [Workstream Name]
**Current focus:** What's happening now
**Blockers:** What's stuck
**Next steps:**
- [ ] Immediate actions

## Key Links
- Repo: [url]
- Docs: [url]
```

### Daily Summary Template

```markdown
# YYYY-MM-DD Summary

## Key Accomplishments
- [What was done] → [pointer to source](relative/path.md)

## Decisions Made
- [Decision] → [pointer to context](relative/path.md)

## Open Items
- [What's unresolved] → [pointer](relative/path.md)

## Active Focus
- [Project]: [current work] → [project status](projects/org/project/STATUS.md)

## Tomorrow
- [What carries forward]
```

### TASKS.md

```markdown
# Tasks

## Inbox
- [ ] New tasks land here first

## This Week
- [ ] Task description #project/name 📅 YYYY-MM-DD ⏫

## Backlog
- [ ] Lower priority items

## Completed
- [x] Done items ✅ YYYY-MM-DD
```

### HABITS.md

```markdown
# Habits

## Today (YYYY-MM-DD)
- [ ] Main Project — Ship one meaningful thing on your primary startup
- [ ] Research — Read, write, or experiment on PhD/AI research
- [ ] Relationships — Reach out to someone, reply thoughtfully, or meet up
- [ ] Health — Exercise, walk, or intentional rest
- [ ] Side Project — Touch one side project or learn something new

## Auto-Detection Rules
- Main Project: auto-check if git commit detected in primary repo
- Research: auto-check if research/ folder modified or paper note created
- Relationships: self-report only
- Health: self-report only
- Side Project: auto-check if git commit in non-primary repo

## History
### YYYY-MM-DD
- [x] Main Project
- [ ] Research
- [x] Relationships
- [x] Health
- [ ] Side Project
```

---

## Phase 2: Hooks

### Architecture

Three thin hooks. Python handles deterministic work. stdout JSON injects context or nudges Claude.

```
.claude/
  hooks/
    session-start-context.py
    pre-compact-flush.py
    session-end-flush.py
  scripts/
    spawn_session.py
  settings.json
```

### `.claude/settings.json`

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/session-start-context.py",
        "timeout": 10
      }]
    }],
    "PreCompact": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/pre-compact-flush.py",
        "timeout": 15
      }]
    }],
    "SessionEnd": [{
      "matcher": ".*",
      "hooks": [{
        "type": "command",
        "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/session-end-flush.py",
        "timeout": 15
      }]
    }]
  }
}
```

### SessionStart Hook (`session-start-context.py`)

**Input:** JSON on stdin with `session_id`, `transcript_path`, `cwd`, `hook_event_name`

**Behavior:**
1. Read Tier 1 files: IDENTITY.md, SOUL.md, USER.md, MEMORY.md, OPERATIONS.md
2. Read last 1-2 daily summary files from `daily/summaries/` (most recent by filename sort)
3. Read most recent weekly summary from `weekly/`
4. Skip any missing files without error
5. Concatenate with `---` separators between sections
6. Return as `systemMessage` in stdout JSON

**Output:**
```json
{
  "systemMessage": "# IDENTITY.md\n...\n\n---\n\n# SOUL.md\n...\n\n---\n\n# Recent Summary (2026-04-04)\n..."
}
```

**Performance target:** <100ms (reading ~7 small files)

### PreCompact Hook (`pre-compact-flush.py`)

**Input:** JSON on stdin with `transcript_path`

**Behavior:**
1. Read transcript from `transcript_path`
2. Acquire `filelock` on `daily/raw/YYYY-MM-DD.md.lock`
3. Append transcript to `daily/raw/YYYY-MM-DD.md` with header: `## HH:MM [pre-compact] (session: <id>)`
4. Release lock
5. Return systemMessage nudging Claude

**Output:**
```json
{
  "systemMessage": "Context is about to be compacted. If you have any unsaved decisions, facts, or action items from this conversation, write them to the daily log now using: Memory/daily/raw/YYYY-MM-DD.md"
}
```

### SessionEnd Hook (`session-end-flush.py`)

**Input:** JSON on stdin with `session_id`, `transcript_path`

**Behavior:**
1. Read transcript from `transcript_path`
2. Check if `daily/raw/YYYY-MM-DD.md` already contains an entry with this `session_id` (dedup — PreCompact may have already fired)
3. If no existing entry: acquire filelock, append with `## HH:MM [session-end] (session: <id>)` header
4. Release lock

**Output:** Empty JSON `{}` (no systemMessage needed — session is ending)

### Spawn Utility (`.claude/scripts/spawn_session.py`)

```python
"""Spawn a short-lived Claude Code session with a prompt.

Hooks fire automatically (SessionStart injects Tier 1 context).
Used by heartbeat, reflection, and other scheduled tasks.
"""

import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def spawn(prompt: str, append_context: str = "", timeout: int = 120) -> str:
    """Spawn a Claude Code session and return its text output.

    Args:
        prompt: The task for Claude to perform.
        append_context: Additional system prompt context (appended to default).
        timeout: Maximum seconds before killing the session.

    Returns:
        Claude's text response.

    Raises:
        RuntimeError: If the session exits with a non-zero code.
        subprocess.TimeoutExpired: If the session exceeds the timeout.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "text"]
    if append_context:
        cmd += ["--append-system-prompt", append_context]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ},
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Spawn failed (exit {result.returncode}): {result.stderr}")
    return result.stdout


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: spawn_session.py 'prompt'")
        sys.exit(1)
    print(spawn(sys.argv[1]))
```

### Reflection Script (`.claude/scripts/reflect.py`)

**Not fully implemented in foundation — just the daily reflection skeleton.**

Runs at 3 AM ET. Uses `spawn_session.py` to invoke Claude Code.

**Behavior:**
1. Python reads today's raw daily log (`daily/raw/YYYY-MM-DD.md`)
2. Python reads all `projects/*/STATUS.md` and `projects/*/*/STATUS.md` files
3. Python compiles this into a context string
4. Calls `spawn()` with prompt: "You are running the nightly reflection. Summarize today's activity. Write the summary to `Memory/daily/summaries/YYYY-MM-DD.md` using the daily summary template. Update `Memory/MEMORY.md` with anything worth keeping long-term. Include relative-link pointers to source files for each item."
5. Claude writes the summary file and updates MEMORY.md

**Weekly/monthly/quarterly/yearly:** Same pattern, different inputs and outputs. Implemented in later phases.

---

## Phase 3: pyqmd Setup + File Watcher

### Collection Setup

One collection covers the entire vault:

```bash
uv run qmd add vault Memory/ --description "Pepper's memory vault"
uv run qmd index vault
```

### Search Patterns

```bash
# Broad search
uv run qmd search vault "FRIDAY deadline"

# Narrow by path prefix
uv run qmd search vault "FRIDAY deadline" --path-prefix projects/niwc
uv run qmd search vault "accomplishments" --path-prefix weekly
uv run qmd search vault "draft reply tone" --path-prefix drafts/sent
```

### pyqmd Improvements Required

**Foundation blockers (must have):**

1. **`qmd watch` command** — file watcher daemon
   - Uses `watchdog` library to monitor a collection's directory recursively
   - Debounce: 2-second window (batch rapid edits before triggering re-index)
   - Ignore patterns: `.obsidian/`, `.git/`, `*.lock`, `*.tmp`, `~*`
   - On change: re-index only changed files (pyqmd's incremental indexing via SHA-256 hashing)
   - Logging: stdout for activity, stderr for errors
   - Graceful shutdown on SIGINT/SIGTERM
   - Invocation: `uv run qmd watch vault`

2. **`--path-prefix` filter on search** — restrict results to files under a given path prefix
   - Filter applied after retrieval (post-search filtering on chunk metadata)
   - Example: `qmd search vault "query" --path-prefix projects/niwc`

**Quality improvements (should have, can parallel):**

3. **Increase default chunk size** — 800 chars → 1600 chars (~400 tokens)
4. **Fix FTS index recreation** — create index once during `store()`, not on every `search_text()` call

---

## Testing Plan

### Hook Tests

| # | Test | Validates |
|---|---|---|
| 1 | Start session, verify all 5 Tier 1 files appear in context | SessionStart basic functionality |
| 2 | Delete one Tier 1 file, start session, verify hook still works | Missing file resilience |
| 3 | Create empty Tier 1 file, start session, verify no crash | Empty file handling |
| 4 | Set MEMORY.md to 500 lines, verify hook completes within timeout | Large file performance |
| 5 | Trigger compaction, verify raw transcript in `daily/raw/YYYY-MM-DD.md` | PreCompact write |
| 6 | Trigger compaction, verify systemMessage contains nudge text | PreCompact nudge |
| 7 | Two processes write to same daily log simultaneously | PreCompact filelock |
| 8 | End session, verify transcript in daily log | SessionEnd write |
| 9 | Trigger PreCompact then SessionEnd in same session | SessionEnd dedup |
| 10 | End session, verify filelock acquired | SessionEnd filelock |

### Spawn Tests

| # | Test | Validates |
|---|---|---|
| 11 | `spawn("Say hello")` returns text | Basic spawn |
| 12 | `spawn("What is your name?", append_context="Your name is Pepper")` | System prompt injection |
| 13 | `spawn("Read Memory/IDENTITY.md and tell me the agent name")` — with hooks active | Hooks fire in spawned session |
| 14 | `spawn("sleep 999", timeout=5)` raises `TimeoutExpired` | Timeout handling |
| 15 | `spawn("List files in Memory/")` returns vault files | Vault access |

### pyqmd Tests

| # | Test | Validates |
|---|---|---|
| 16 | `qmd index vault` completes without error | Index creation |
| 17 | Add a file to Memory/, index, search for its content | Search returns results |
| 18 | Modify a file while `qmd watch` is running, search for new content | File watcher detects changes |
| 19 | Modify a file in `.obsidian/`, verify NOT re-indexed | Ignore patterns |
| 20 | Search with `--path-prefix projects/` returns only project files | Path prefix filtering |

### Integration Tests

| # | Test | Validates |
|---|---|---|
| 21 | Start session → do work → trigger compaction → end session → check daily log | Full hook lifecycle |
| 22 | `spawn_session.py` + hooks: Claude reads vault file, returns correct answer | Spawn + hooks end-to-end |
| 23 | Two processes append to daily log concurrently via filelock | Concurrent write safety |

---

## File Manifest

Files created by this foundation spec:

```
# Phase 0
pyproject.toml
.env
.python-version

# Phase 1
Memory/IDENTITY.md
Memory/SOUL.md
Memory/USER.md
Memory/MEMORY.md
Memory/OPERATIONS.md
Memory/HEARTBEAT.md
Memory/HABITS.md
Memory/TASKS.md
Memory/daily/raw/.gitkeep
Memory/daily/summaries/.gitkeep
Memory/weekly/.gitkeep
Memory/monthly/.gitkeep
Memory/quarterly/.gitkeep
Memory/yearly/.gitkeep
Memory/projects/pepper/STATUS.md
Memory/projects/pepper/notes.md
Memory/projects/pepper/tasks.md
Memory/projects/niwc-atlantic/STATUS.md
Memory/projects/niwc-atlantic/friday/STATUS.md
Memory/projects/niwc-atlantic/friday/notes.md
Memory/projects/niwc-atlantic/friday/tasks.md
Memory/projects/niwc-atlantic/jazz/STATUS.md
Memory/projects/niwc-atlantic/jazz/notes.md
Memory/projects/niwc-atlantic/jazz/tasks.md
Memory/projects/phd-embedded-ai/STATUS.md
Memory/projects/phd-embedded-ai/notes.md
Memory/projects/phd-embedded-ai/tasks.md
Memory/meetings/.gitkeep
Memory/research/.gitkeep
Memory/clients/.gitkeep
Memory/content/.gitkeep
Memory/team/.gitkeep
Memory/tasks/.gitkeep
Memory/drafts/active/.gitkeep
Memory/drafts/sent/.gitkeep
Memory/drafts/expired/.gitkeep

# Phase 2
.claude/hooks/session-start-context.py
.claude/hooks/pre-compact-flush.py
.claude/hooks/session-end-flush.py
.claude/scripts/spawn_session.py
.claude/scripts/reflect.py
.claude/settings.json

# Phase 3
# (pyqmd improvements are changes to the pyqmd library, not this repo)

# Tests
tests/test_hooks.py
tests/test_spawn.py
tests/test_pyqmd_integration.py
tests/test_integration.py
```

---

## Out of Scope (Backlog)

- Integrations (Gmail, Outlook, Calendar, Discord, Drive, OneDrive, GitHub)
- Skills (executive-assistant, project-tracker, research-assistant, self-improve, rememberall)
- Heartbeat monitoring
- Draft management
- Discord bot chat interface
- Security hardening (sanitize, guardrails, credential isolation)
- Deployment (OS scheduler setup)
- OpenClaw data migration
- CAC card authentication
- Teams / Zoom integration
- Multi-agent orchestrator
- Weekly/monthly/quarterly/yearly reflection scripts (daily only in foundation)
