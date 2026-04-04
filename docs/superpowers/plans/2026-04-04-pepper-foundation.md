# Pepper Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation for Pepper — environment, vault, hooks, pyqmd — so that every Claude Code session in this workspace has persistent memory and context.

**Architecture:** Thin hooks inject Tier 1 files (IDENTITY.md, SOUL.md, USER.md, MEMORY.md, OPERATIONS.md) + recent summaries at SessionStart. PreCompact and SessionEnd hooks append to daily raw logs with filelock. `spawn_session.py` wraps Claude Code CLI for scheduled invocations. pyqmd provides hybrid RAG search with a file watcher daemon.

**Tech Stack:** Python 3.12, uv, pyqmd, filelock, python-dotenv, watchdog, Claude Code CLI

**Spec:** `docs/superpowers/specs/2026-04-04-pepper-foundation-design.md`

---

## File Structure

```
# Phase 0: Environment
pyproject.toml                    # Project metadata + deps (uv)
.python-version                   # Python version pin
.env                              # Environment variables (gitignored)
.gitignore                        # Updated with new ignore patterns

# Phase 1: Vault
Memory/IDENTITY.md                # Agent name, emoji, role
Memory/SOUL.md                    # Personality, boundaries, priorities
Memory/USER.md                    # Jeff's profile, platforms, preferences
Memory/MEMORY.md                  # Curated long-term memory
Memory/OPERATIONS.md              # Vault map, tools, conventions
Memory/HEARTBEAT.md               # Plain-English monitoring checklist
Memory/HABITS.md                  # Daily pillars and habit tracking
Memory/TASKS.md                   # Global task inbox
Memory/daily/raw/.gitkeep         # Append-only session logs
Memory/daily/summaries/.gitkeep   # Curated daily summaries
Memory/weekly/.gitkeep            # Weekly summaries
Memory/monthly/.gitkeep           # Monthly summaries
Memory/quarterly/.gitkeep         # Quarterly summaries
Memory/yearly/.gitkeep            # Yearly summaries
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

# Phase 2: Hooks
.claude/hooks/session_start_context.py   # SessionStart hook
.claude/hooks/pre_compact_flush.py       # PreCompact hook
.claude/hooks/session_end_flush.py       # SessionEnd hook
.claude/hooks/shared.py                  # Shared utilities (vault path, daily log helpers)
.claude/scripts/spawn_session.py         # Claude Code CLI spawner
.claude/scripts/reflect.py               # Daily reflection skeleton
.claude/settings.json                    # Hook configuration

# Tests
tests/__init__.py
tests/conftest.py                        # Shared fixtures (temp vault, mock stdin)
tests/test_session_start.py
tests/test_pre_compact.py
tests/test_session_end.py
tests/test_shared.py
tests/test_spawn.py
tests/test_pyqmd_integration.py
tests/test_integration.py
```

---

### Task 1: Initialize uv Environment

**Files:**
- Create: `pyproject.toml` (via `uv init`)
- Create: `.python-version` (via `uv python pin`)
- Create: `.env`
- Modify: `.gitignore`

- [ ] **Step 1: Initialize uv project**

Run:
```bash
cd E:\workspaces\ai\pepper
uv init
uv python pin 3.12
```

Expected: `pyproject.toml` and `.python-version` created.

- [ ] **Step 2: Add core dependencies**

Run:
```bash
uv add filelock python-dotenv typer rich pyyaml watchdog
uv add --dev pytest ruff
```

Note: `pyqmd` is added in Task 10 (Phase 3). `plyer` is deferred to later phases.

Expected: `pyproject.toml` updated, `uv.lock` created.

- [ ] **Step 3: Create `.env`**

Create `.env` at project root:
```
CLAUDE_CODE_GIT_BASH_PATH=E:\Program Files\Git\bin\bash.exe
```

- [ ] **Step 4: Update `.gitignore`**

Add these lines to the existing `.gitignore`:
```
# Obsidian internals
Memory/.obsidian/

# Filelock lockfiles
*.lock

# uv
.venv/
```

Note: `.env`, `__pycache__/`, `.claude/data/` are already in the existing `.gitignore`.

- [ ] **Step 5: Verify environment works**

Run:
```bash
uv run python -c "import filelock; import dotenv; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .python-version .env.example .gitignore
git commit -m "feat: initialize uv environment with core dependencies"
```

Note: Commit `.env.example` (a copy of `.env` with placeholder values), not `.env` itself.

---

### Task 2: Create Vault — Tier 1 Files

**Files:**
- Create: `Memory/IDENTITY.md`
- Create: `Memory/SOUL.md`
- Create: `Memory/USER.md`
- Create: `Memory/MEMORY.md`
- Create: `Memory/OPERATIONS.md`

- [ ] **Step 1: Create Memory directory and IDENTITY.md**

Create `Memory/IDENTITY.md`:
```markdown
# Identity

**Name:** Pepper
**Emoji:** 🌶️
**Role:** Second Brain & Executive Assistant
**Created by:** Jeff Richley
```

- [ ] **Step 2: Create SOUL.md**

Create `Memory/SOUL.md`:
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

- [ ] **Step 3: Create USER.md**

Create `Memory/USER.md`:
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

- [ ] **Step 4: Create MEMORY.md**

Create `Memory/MEMORY.md`:
```markdown
# Memory

## Active Projects
- Pepper: Building AI Second Brain on Claude Code (Active, High priority)
- FRIDAY: [fill in] (NIWC Atlantic)
- JAZZ: [fill in] (NIWC Atlantic)
- PhD Embedded AI: [fill in]

## Meeting Decisions

## Research Notes

## Client/Customer Context

## Personal Goals & Habits

## Content Ideas

## Team Context
```

- [ ] **Step 5: Create OPERATIONS.md**

Create `Memory/OPERATIONS.md`:
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

- [ ] **Step 6: Commit**

```bash
git add Memory/IDENTITY.md Memory/SOUL.md Memory/USER.md Memory/MEMORY.md Memory/OPERATIONS.md
git commit -m "feat: create Tier 1 vault files (identity, soul, user, memory, operations)"
```

---

### Task 3: Create Vault — Remaining Structure

**Files:**
- Create: `Memory/HEARTBEAT.md`
- Create: `Memory/HABITS.md`
- Create: `Memory/TASKS.md`
- Create: all `.gitkeep` files for empty directories
- Create: all project STATUS.md, notes.md, tasks.md files

- [ ] **Step 1: Create HEARTBEAT.md**

Create `Memory/HEARTBEAT.md`:
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

- [ ] **Step 2: Create HABITS.md**

Create `Memory/HABITS.md`:
```markdown
# Habits

## Today (2026-04-04)
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
```

- [ ] **Step 3: Create TASKS.md**

Create `Memory/TASKS.md`:
```markdown
# Tasks

## Inbox
- [ ] New tasks land here first

## This Week

## Backlog

## Completed
```

- [ ] **Step 4: Create directory structure with .gitkeep files**

Run:
```bash
cd E:\workspaces\ai\pepper
mkdir -p Memory/daily/raw Memory/daily/summaries Memory/weekly Memory/monthly Memory/quarterly Memory/yearly
mkdir -p Memory/meetings Memory/research Memory/clients Memory/content Memory/team Memory/tasks
mkdir -p Memory/drafts/active Memory/drafts/sent Memory/drafts/expired
touch Memory/daily/raw/.gitkeep Memory/daily/summaries/.gitkeep
touch Memory/weekly/.gitkeep Memory/monthly/.gitkeep Memory/quarterly/.gitkeep Memory/yearly/.gitkeep
touch Memory/meetings/.gitkeep Memory/research/.gitkeep Memory/clients/.gitkeep
touch Memory/content/.gitkeep Memory/team/.gitkeep Memory/tasks/.gitkeep
touch Memory/drafts/active/.gitkeep Memory/drafts/sent/.gitkeep Memory/drafts/expired/.gitkeep
```

- [ ] **Step 5: Create Pepper project STATUS.md**

Create `Memory/projects/pepper/STATUS.md`:
```markdown
# Pepper

**Status:** Active
**Priority:** High
**Cadence:** Daily
**One-liner:** AI Second Brain built on Claude Code
**Started:** 2026-04-03

## Workstreams

### Foundation
**Current focus:** Building vault, hooks, pyqmd integration
**Blockers:** None
**Next steps:**
- [ ] Implement hooks
- [ ] Set up pyqmd with file watcher

## Key Links
- Repo: https://github.com/jeffrichley/pepper
```

Create `Memory/projects/pepper/notes.md`:
```markdown
# Pepper — Notes
```

Create `Memory/projects/pepper/tasks.md`:
```markdown
# Pepper — Tasks

- [ ] Complete foundation implementation #project/pepper 📅 2026-04-11 ⏫
```

- [ ] **Step 6: Create NIWC Atlantic project structure**

Create `Memory/projects/niwc-atlantic/STATUS.md`:
```markdown
# NIWC Atlantic

**Role:** [Your role at NIWC]
**Notes:** Organization-level context spanning FRIDAY and JAZZ projects
```

Create `Memory/projects/niwc-atlantic/friday/STATUS.md`:
```markdown
# FRIDAY

**Status:** Active
**Priority:** High
**Cadence:** Daily
**Org:** NIWC Atlantic
**One-liner:** [Fill in]
**Started:** [Fill in]

## Workstreams

### [Workstream Name]
**Current focus:** [Fill in]
**Blockers:** [Fill in]
**Next steps:**
- [ ] [Fill in]

## Key Links
```

Create `Memory/projects/niwc-atlantic/friday/notes.md`:
```markdown
# FRIDAY — Notes
```

Create `Memory/projects/niwc-atlantic/friday/tasks.md`:
```markdown
# FRIDAY — Tasks
```

Create `Memory/projects/niwc-atlantic/jazz/STATUS.md`:
```markdown
# JAZZ

**Status:** Active
**Priority:** High
**Cadence:** Daily
**Org:** NIWC Atlantic
**One-liner:** [Fill in]
**Started:** [Fill in]

## Workstreams

### [Workstream Name]
**Current focus:** [Fill in]
**Blockers:** [Fill in]
**Next steps:**
- [ ] [Fill in]

## Key Links
```

Create `Memory/projects/niwc-atlantic/jazz/notes.md`:
```markdown
# JAZZ — Notes
```

Create `Memory/projects/niwc-atlantic/jazz/tasks.md`:
```markdown
# JAZZ — Tasks
```

- [ ] **Step 7: Create PhD project structure**

Create `Memory/projects/phd-embedded-ai/STATUS.md`:
```markdown
# PhD — Embedded AI in Robots

**Status:** Active
**Priority:** High
**Cadence:** Weekly
**One-liner:** PhD research in Embedded AI in Robots
**Started:** [Fill in]

## Workstreams

### [Current Research Thread]
**Current focus:** [Fill in]
**Blockers:** [Fill in]
**Next steps:**
- [ ] [Fill in]

## Key Links
```

Create `Memory/projects/phd-embedded-ai/notes.md`:
```markdown
# PhD Embedded AI — Notes
```

Create `Memory/projects/phd-embedded-ai/tasks.md`:
```markdown
# PhD Embedded AI — Tasks
```

- [ ] **Step 8: Commit**

```bash
git add Memory/
git commit -m "feat: create full vault structure with projects, daily logs, and templates"
```

---

### Task 4: Hook Shared Utilities

**Files:**
- Create: `.claude/hooks/shared.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_shared.py`

- [ ] **Step 1: Write tests for shared utilities**

Create `tests/__init__.py` (empty file).

Create `tests/conftest.py`:
```python
"""Shared test fixtures for Pepper foundation tests."""

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault with Tier 1 files for testing."""
    vault = tmp_path / "Memory"
    vault.mkdir()

    (vault / "IDENTITY.md").write_text("# Identity\n\n**Name:** TestBot\n**Emoji:** 🤖\n**Role:** Test Agent\n**Created by:** Test\n")
    (vault / "SOUL.md").write_text("# Soul\n\n## Personality\nTest personality.\n\n## Behavioral Rules\nBe helpful.\n")
    (vault / "USER.md").write_text("# User Profile\n\n## About\n- **Name:** Tester\n- **Timezone:** UTC\n")
    (vault / "MEMORY.md").write_text("# Memory\n\n## Active Projects\n- Test project\n")
    (vault / "OPERATIONS.md").write_text("# Operations\n\n## Vault\n- **Location:** Memory/\n")

    # Create daily summaries directory with a summary file
    summaries = vault / "daily" / "summaries"
    summaries.mkdir(parents=True)
    (summaries / "2026-04-04.md").write_text("# 2026-04-04 Summary\n\n## Key Accomplishments\n- Set up test vault\n")

    # Create raw directory
    raw = vault / "daily" / "raw"
    raw.mkdir(parents=True)

    # Create weekly directory with a summary
    weekly = vault / "weekly"
    weekly.mkdir()
    (weekly / "2026-W14.md").write_text("# Week 14 Summary\n\n## Highlights\n- Testing week\n")

    return vault


@pytest.fixture
def mock_stdin_data():
    """Create mock stdin JSON data for hooks."""
    def _make(session_id="test-session-123", transcript_path=None, hook_event="SessionStart"):
        data = {
            "session_id": session_id,
            "transcript_path": transcript_path or "",
            "cwd": os.getcwd(),
            "hook_event_name": hook_event,
        }
        return json.dumps(data)
    return _make


@pytest.fixture
def temp_transcript(tmp_path):
    """Create a temporary transcript file."""
    transcript = tmp_path / "transcript.txt"
    transcript.write_text(
        "User: What is the status of the Pepper project?\n"
        "Assistant: The Pepper project is in the foundation phase.\n"
        "User: Great, let's proceed with hooks.\n"
        "Assistant: I'll start implementing the SessionStart hook.\n"
    )
    return transcript
```

Create `tests/test_shared.py`:
```python
"""Tests for hook shared utilities."""

from pathlib import Path

from pepper_hooks.shared import (
    get_vault_path,
    read_tier1_files,
    get_daily_log_path,
    append_to_daily_log,
    read_recent_summaries,
)


def test_get_vault_path():
    vault = get_vault_path()
    assert vault.name == "Memory"


def test_read_tier1_files_all_present(temp_vault):
    result = read_tier1_files(temp_vault)
    assert "# Identity" in result
    assert "TestBot" in result
    assert "# Soul" in result
    assert "# User Profile" in result
    assert "# Memory" in result
    assert "# Operations" in result
    assert "---" in result  # separators


def test_read_tier1_files_missing_file(temp_vault):
    (temp_vault / "SOUL.md").unlink()
    result = read_tier1_files(temp_vault)
    assert "# Identity" in result
    assert "# Soul" not in result
    assert "# User Profile" in result


def test_read_tier1_files_empty_file(temp_vault):
    (temp_vault / "SOUL.md").write_text("")
    result = read_tier1_files(temp_vault)
    assert "# Identity" in result
    assert "# User Profile" in result


def test_get_daily_log_path(temp_vault):
    path = get_daily_log_path(temp_vault)
    assert path.parent.name == "raw"
    assert path.suffix == ".md"
    assert path.stem.count("-") == 2  # YYYY-MM-DD


def test_append_to_daily_log(temp_vault):
    log_path = get_daily_log_path(temp_vault)
    append_to_daily_log(
        vault_path=temp_vault,
        content="Test content here",
        source="session",
        session_id="abc-123",
    )
    text = log_path.read_text()
    assert "[session]" in text
    assert "(session: abc-123)" in text
    assert "Test content here" in text


def test_append_to_daily_log_creates_file(temp_vault):
    log_path = get_daily_log_path(temp_vault)
    assert not log_path.exists()
    append_to_daily_log(
        vault_path=temp_vault,
        content="First entry",
        source="session",
        session_id="first-123",
    )
    assert log_path.exists()


def test_append_to_daily_log_appends_not_overwrites(temp_vault):
    append_to_daily_log(temp_vault, "First", "session", "s1")
    append_to_daily_log(temp_vault, "Second", "session", "s2")
    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()
    assert "First" in text
    assert "Second" in text


def test_daily_log_has_session_id(temp_vault):
    append_to_daily_log(temp_vault, "Content", "pre-compact", "sess-xyz")
    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()
    assert "(session: sess-xyz)" in text


def test_read_recent_summaries(temp_vault):
    result = read_recent_summaries(temp_vault, daily_count=1, include_weekly=True)
    assert "2026-04-04 Summary" in result
    assert "Week 14 Summary" in result


def test_read_recent_summaries_empty_dir(temp_vault):
    # Remove all summaries
    for f in (temp_vault / "daily" / "summaries").iterdir():
        f.unlink()
    for f in (temp_vault / "weekly").iterdir():
        f.unlink()
    result = read_recent_summaries(temp_vault, daily_count=1, include_weekly=True)
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_shared.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'pepper_hooks'`

- [ ] **Step 3: Write shared utilities implementation**

Create `.claude/hooks/__init__.py` (empty file).

Create `.claude/hooks/shared.py`:
```python
"""Shared utilities for Pepper hooks.

Provides vault path resolution, Tier 1 file reading, daily log management,
and summary reading. All file operations use filelock for concurrency safety.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

# Tier 1 files loaded on every SessionStart
TIER_1_FILES = [
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "MEMORY.md",
    "OPERATIONS.md",
]


def get_vault_path() -> Path:
    """Return the absolute path to the Memory vault.

    Resolves relative to the project root (three levels up from this file:
    .claude/hooks/shared.py -> project root -> Memory/).
    """
    project_root = Path(__file__).parent.parent.parent
    return project_root / "Memory"


def read_tier1_files(vault_path: Path) -> str:
    """Read and concatenate all Tier 1 files with separators.

    Skips missing or empty files without error.

    Args:
        vault_path: Path to the Memory vault directory.

    Returns:
        Concatenated content with --- separators between files.
    """
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
    """Append a timestamped entry to today's raw daily log.

    Uses filelock to prevent corruption from concurrent writes.

    Args:
        vault_path: Path to the Memory vault directory.
        content: The text content to append.
        source: Entry source tag (session, pre-compact, session-end, heartbeat).
        session_id: Session identifier for deduplication.
    """
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
    """Check if a session ID already has an entry in today's daily log.

    Used by SessionEnd to deduplicate against PreCompact.

    Args:
        vault_path: Path to the Memory vault directory.
        session_id: Session identifier to check for.

    Returns:
        True if the session ID is found in today's log.
    """
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
    """Read the most recent daily summaries and optional weekly summary.

    Args:
        vault_path: Path to the Memory vault directory.
        daily_count: Number of most recent daily summaries to read.
        include_weekly: Whether to include the most recent weekly summary.

    Returns:
        Concatenated summary content, or empty string if none found.
    """
    parts = []

    # Read recent daily summaries (sorted by filename descending)
    summaries_dir = vault_path / "daily" / "summaries"
    if summaries_dir.exists():
        summary_files = sorted(summaries_dir.glob("*.md"), reverse=True)[:daily_count]
        for f in summary_files:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                parts.append(f"# Recent Summary ({f.stem})\n{content}")

    # Read most recent weekly summary
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

- [ ] **Step 4: Register the hooks package for import**

Add to `pyproject.toml` under `[tool.uv]` or create a `src` layout. The simplest approach: add the hooks directory to the Python path. Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = [".claude/hooks"]
```

This ensures test files can `from shared import ...` directly.

Update `tests/test_shared.py` — change the import line at the top:
```python
from shared import (
    get_vault_path,
    read_tier1_files,
    get_daily_log_path,
    append_to_daily_log,
    read_recent_summaries,
)
```

Also update `pyproject.toml` to include the pytest configuration:
```toml
[tool.pytest.ini_options]
pythonpath = [".claude/hooks"]
markers = ["slow: tests that invoke real Claude Code sessions (cost API tokens)"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_shared.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/shared.py .claude/hooks/__init__.py tests/ pyproject.toml
git commit -m "feat: add hook shared utilities with vault reading and daily log management"
```

---

### Task 5: SessionStart Hook

**Files:**
- Create: `.claude/hooks/session_start_context.py`
- Create: `tests/test_session_start.py`

- [ ] **Step 1: Write tests for SessionStart hook**

Create `tests/test_session_start.py`:
```python
"""Tests for SessionStart hook."""

import json
import subprocess
import sys
from pathlib import Path


def test_session_start_output_is_valid_json(temp_vault, mock_stdin_data):
    """Hook output must be valid JSON with systemMessage key."""
    result = _run_hook(temp_vault, mock_stdin_data())
    data = json.loads(result)
    assert "systemMessage" in data


def test_session_start_includes_all_tier1(temp_vault, mock_stdin_data):
    """All 5 Tier 1 files should appear in the systemMessage."""
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "# Identity" in msg or "# IDENTITY.md" in msg
    assert "TestBot" in msg
    assert "# Soul" in msg or "# SOUL.md" in msg
    assert "# User Profile" in msg or "# USER.md" in msg
    assert "# Memory" in msg or "# MEMORY.md" in msg
    assert "# Operations" in msg or "# OPERATIONS.md" in msg


def test_session_start_includes_recent_summary(temp_vault, mock_stdin_data):
    """Recent daily summary should be injected."""
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "2026-04-04 Summary" in msg


def test_session_start_includes_weekly_summary(temp_vault, mock_stdin_data):
    """Most recent weekly summary should be injected."""
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "Week 14 Summary" in msg


def test_session_start_missing_file_resilience(temp_vault, mock_stdin_data):
    """Hook should work even if a Tier 1 file is missing."""
    (temp_vault / "SOUL.md").unlink()
    result = _run_hook(temp_vault, mock_stdin_data())
    msg = json.loads(result)["systemMessage"]
    assert "TestBot" in msg  # IDENTITY.md still present
    assert "Soul" not in msg  # SOUL.md gone


def test_session_start_empty_file(temp_vault, mock_stdin_data):
    """Hook should handle empty Tier 1 files gracefully."""
    (temp_vault / "SOUL.md").write_text("")
    result = _run_hook(temp_vault, mock_stdin_data())
    data = json.loads(result)
    assert "systemMessage" in data


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    """Run the session start hook as a subprocess, pointing at a temp vault."""
    hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "session_start_context.py"
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_data,
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "PEPPER_VAULT_PATH": str(vault_path),
        },
    )
    assert result.returncode == 0, f"Hook failed: {result.stderr}"
    return result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_session_start.py -v
```

Expected: FAIL — hook file does not exist.

- [ ] **Step 3: Write SessionStart hook implementation**

Create `.claude/hooks/session_start_context.py`:
```python
"""SessionStart hook: inject Tier 1 context into every Claude Code session.

Reads IDENTITY.md, SOUL.md, USER.md, MEMORY.md, OPERATIONS.md,
plus recent daily summaries and the latest weekly summary.
Outputs JSON with systemMessage to stdout.

Env override: PEPPER_VAULT_PATH (for testing)
"""

import json
import os
import sys
from pathlib import Path

# Allow importing shared utilities
sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    get_vault_path,
    read_tier1_files,
    read_recent_summaries,
    read_stdin,
    write_stdout,
)


def main():
    # Read hook input (we don't use it for SessionStart, but consume stdin)
    try:
        read_stdin()
    except (json.JSONDecodeError, EOFError):
        pass

    # Allow vault path override for testing
    vault_override = os.environ.get("PEPPER_VAULT_PATH")
    vault = Path(vault_override) if vault_override else get_vault_path()

    # Read Tier 1 files
    tier1_content = read_tier1_files(vault)

    # Read recent summaries
    summaries = read_recent_summaries(vault, daily_count=2, include_weekly=True)

    # Combine
    parts = [tier1_content]
    if summaries:
        parts.append(summaries)

    system_message = "\n\n---\n\n".join(parts)

    write_stdout({"systemMessage": system_message})


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_session_start.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/session_start_context.py tests/test_session_start.py
git commit -m "feat: implement SessionStart hook with Tier 1 context injection"
```

---

### Task 6: PreCompact Hook

**Files:**
- Create: `.claude/hooks/pre_compact_flush.py`
- Create: `tests/test_pre_compact.py`

- [ ] **Step 1: Write tests for PreCompact hook**

Create `tests/test_pre_compact.py`:
```python
"""Tests for PreCompact hook."""

import json
import subprocess
import sys
from pathlib import Path


def test_pre_compact_appends_transcript(temp_vault, mock_stdin_data, temp_transcript):
    """Hook should append transcript content to daily raw log."""
    stdin = mock_stdin_data(
        session_id="compact-sess-1",
        transcript_path=str(temp_transcript),
        hook_event="PreCompact",
    )
    _run_hook(temp_vault, stdin)

    log_files = list((temp_vault / "daily" / "raw").glob("*.md"))
    assert len(log_files) == 1
    text = log_files[0].read_text()
    assert "What is the status of the Pepper project?" in text
    assert "[pre-compact]" in text
    assert "(session: compact-sess-1)" in text


def test_pre_compact_returns_nudge(temp_vault, mock_stdin_data, temp_transcript):
    """Hook should return a systemMessage nudging Claude to save context."""
    stdin = mock_stdin_data(
        transcript_path=str(temp_transcript),
        hook_event="PreCompact",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert "systemMessage" in data
    assert "compacted" in data["systemMessage"].lower() or "unsaved" in data["systemMessage"].lower()


def test_pre_compact_creates_log_file(temp_vault, mock_stdin_data, temp_transcript):
    """Hook should create the daily log file if it doesn't exist."""
    log_dir = temp_vault / "daily" / "raw"
    assert len(list(log_dir.glob("*.md"))) == 0
    stdin = mock_stdin_data(
        transcript_path=str(temp_transcript),
        hook_event="PreCompact",
    )
    _run_hook(temp_vault, stdin)
    assert len(list(log_dir.glob("*.md"))) == 1


def test_pre_compact_no_transcript(temp_vault, mock_stdin_data):
    """Hook should handle missing transcript gracefully."""
    stdin = mock_stdin_data(
        transcript_path="/nonexistent/path.txt",
        hook_event="PreCompact",
    )
    result = _run_hook(temp_vault, stdin)
    # Should still return valid JSON (with nudge, no transcript content)
    data = json.loads(result)
    assert "systemMessage" in data


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    """Run the pre-compact hook as a subprocess."""
    hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "pre_compact_flush.py"
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_data,
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "PEPPER_VAULT_PATH": str(vault_path),
        },
    )
    assert result.returncode == 0, f"Hook failed: {result.stderr}"
    return result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_pre_compact.py -v
```

Expected: FAIL — hook file does not exist.

- [ ] **Step 3: Write PreCompact hook implementation**

Create `.claude/hooks/pre_compact_flush.py`:
```python
"""PreCompact hook: save transcript to daily log and nudge Claude.

1. Reads transcript from transcript_path
2. Appends raw transcript to daily/raw/YYYY-MM-DD.md with filelock
3. Returns systemMessage nudging Claude to save unsaved context

Env override: PEPPER_VAULT_PATH (for testing)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    get_vault_path,
    append_to_daily_log,
    read_stdin,
    write_stdout,
)


def main():
    hook_input = read_stdin()
    session_id = hook_input.get("session_id", "unknown")
    transcript_path = hook_input.get("transcript_path", "")

    vault_override = os.environ.get("PEPPER_VAULT_PATH")
    vault = Path(vault_override) if vault_override else get_vault_path()

    # Read and append transcript if available
    if transcript_path and Path(transcript_path).exists():
        transcript = Path(transcript_path).read_text(encoding="utf-8")
        append_to_daily_log(
            vault_path=vault,
            content=transcript,
            source="pre-compact",
            session_id=session_id,
        )

    # Always return the nudge message
    write_stdout({
        "systemMessage": (
            "Context is about to be compacted. If you have any unsaved decisions, "
            "facts, or action items from this conversation, write them to the daily "
            f"log now using: Memory/daily/raw/{__import__('datetime').datetime.now().strftime('%Y-%m-%d')}.md"
        )
    })


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_pre_compact.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/pre_compact_flush.py tests/test_pre_compact.py
git commit -m "feat: implement PreCompact hook with transcript dump and nudge"
```

---

### Task 7: SessionEnd Hook

**Files:**
- Create: `.claude/hooks/session_end_flush.py`
- Create: `tests/test_session_end.py`

- [ ] **Step 1: Write tests for SessionEnd hook**

Create `tests/test_session_end.py`:
```python
"""Tests for SessionEnd hook."""

import json
import subprocess
import sys
from pathlib import Path

from shared import append_to_daily_log


def test_session_end_appends_transcript(temp_vault, mock_stdin_data, temp_transcript):
    """Hook should append transcript to daily log."""
    stdin = mock_stdin_data(
        session_id="end-sess-1",
        transcript_path=str(temp_transcript),
        hook_event="SessionEnd",
    )
    _run_hook(temp_vault, stdin)
    log_files = list((temp_vault / "daily" / "raw").glob("*.md"))
    assert len(log_files) == 1
    text = log_files[0].read_text()
    assert "[session-end]" in text
    assert "(session: end-sess-1)" in text


def test_session_end_dedup_after_precompact(temp_vault, mock_stdin_data, temp_transcript):
    """If PreCompact already logged this session, SessionEnd should skip."""
    # Simulate PreCompact having already run for this session
    append_to_daily_log(
        vault_path=temp_vault,
        content="Pre-compact transcript dump",
        source="pre-compact",
        session_id="dedup-sess-1",
    )

    stdin = mock_stdin_data(
        session_id="dedup-sess-1",
        transcript_path=str(temp_transcript),
        hook_event="SessionEnd",
    )
    _run_hook(temp_vault, stdin)

    log_path = list((temp_vault / "daily" / "raw").glob("*.md"))[0]
    text = log_path.read_text()
    # Should have pre-compact entry but NOT session-end (dedup)
    assert text.count("(session: dedup-sess-1)") == 1
    assert "[pre-compact]" in text
    assert "[session-end]" not in text


def test_session_end_returns_empty_json(temp_vault, mock_stdin_data, temp_transcript):
    """SessionEnd should return empty JSON (no systemMessage needed)."""
    stdin = mock_stdin_data(
        session_id="end-sess-2",
        transcript_path=str(temp_transcript),
        hook_event="SessionEnd",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert data == {}


def test_session_end_no_transcript(temp_vault, mock_stdin_data):
    """Hook should handle missing transcript gracefully."""
    stdin = mock_stdin_data(
        session_id="end-sess-3",
        transcript_path="/nonexistent/path.txt",
        hook_event="SessionEnd",
    )
    result = _run_hook(temp_vault, stdin)
    data = json.loads(result)
    assert data == {}


def _run_hook(vault_path: Path, stdin_data: str) -> str:
    """Run the session end hook as a subprocess."""
    hook_path = Path(__file__).parent.parent / ".claude" / "hooks" / "session_end_flush.py"
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=stdin_data,
        capture_output=True,
        text=True,
        env={
            **__import__("os").environ,
            "PEPPER_VAULT_PATH": str(vault_path),
        },
    )
    assert result.returncode == 0, f"Hook failed: {result.stderr}"
    return result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_session_end.py -v
```

Expected: FAIL — hook file does not exist.

- [ ] **Step 3: Write SessionEnd hook implementation**

Create `.claude/hooks/session_end_flush.py`:
```python
"""SessionEnd hook: append transcript to daily log (with dedup).

1. Checks if this session was already logged by PreCompact
2. If not, appends transcript to daily/raw/YYYY-MM-DD.md with filelock
3. Returns empty JSON (session is ending, no systemMessage needed)

Env override: PEPPER_VAULT_PATH (for testing)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from shared import (
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

    vault_override = os.environ.get("PEPPER_VAULT_PATH")
    vault = Path(vault_override) if vault_override else get_vault_path()

    # Only append if PreCompact didn't already log this session
    if transcript_path and Path(transcript_path).exists():
        if not session_already_logged(vault, session_id):
            transcript = Path(transcript_path).read_text(encoding="utf-8")
            append_to_daily_log(
                vault_path=vault,
                content=transcript,
                source="session-end",
                session_id=session_id,
            )

    # Empty output — session is ending
    write_stdout({})


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_session_end.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/session_end_flush.py tests/test_session_end.py
git commit -m "feat: implement SessionEnd hook with deduplication"
```

---

### Task 8: Hook Configuration (settings.json)

**Files:**
- Create: `.claude/settings.json`

- [ ] **Step 1: Create settings.json**

Create `.claude/settings.json`:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/session_start_context.py",
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
            "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/pre_compact_flush.py",
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
            "command": "uv run python $CLAUDE_PROJECT_DIR/.claude/hooks/session_end_flush.py",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Verify hooks are recognized**

Start a new Claude Code session in the Pepper workspace and run `/hooks` to verify all three hooks are loaded.

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: configure SessionStart, PreCompact, and SessionEnd hooks"
```

---

### Task 9: Spawn Utility

**Files:**
- Create: `.claude/scripts/spawn_session.py`
- Create: `.claude/scripts/reflect.py`
- Create: `tests/test_spawn.py`

- [ ] **Step 1: Write tests for spawn utility**

Create `tests/test_spawn.py`:
```python
"""Tests for spawn_session utility.

NOTE: These tests invoke real Claude Code sessions. They require:
- Claude Code CLI installed and authenticated
- CLAUDE_CODE_GIT_BASH_PATH set in .env
- Network access to Anthropic API

These are integration tests — they're slower and cost API tokens.
Mark them to run only when explicitly requested.
"""

import subprocess
import sys

import pytest

# Add scripts to path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / ".claude" / "scripts"))


@pytest.mark.slow
def test_spawn_basic():
    """Spawn a session and get a text response."""
    from spawn_session import spawn

    result = spawn("Respond with exactly the word: PONG")
    assert "PONG" in result


@pytest.mark.slow
def test_spawn_with_context():
    """Spawn with appended system prompt."""
    from spawn_session import spawn

    result = spawn(
        "What is your name? Respond with just the name.",
        append_context="Your name is Pepper. Only respond with the name Pepper.",
    )
    assert "Pepper" in result


@pytest.mark.slow
def test_spawn_reads_vault():
    """Spawn can read vault files."""
    from spawn_session import spawn

    result = spawn("Read Memory/IDENTITY.md and tell me only the agent's name.")
    assert "Pepper" in result


@pytest.mark.slow
def test_spawn_timeout():
    """Spawn should raise on timeout."""
    from spawn_session import spawn

    with pytest.raises(subprocess.TimeoutExpired):
        spawn("Write a 10000 word essay about the history of computing", timeout=5)
```

- [ ] **Step 2: Write spawn utility**

Create `.claude/scripts/spawn_session.py`:
```python
"""Spawn a short-lived Claude Code session with a prompt.

Hooks fire automatically (SessionStart injects Tier 1 context).
Used by heartbeat, reflection, and other scheduled tasks.
"""

import os
import subprocess
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

- [ ] **Step 3: Write reflection skeleton**

Create `.claude/scripts/reflect.py`:
```python
"""Daily reflection script — runs at 3 AM ET.

Gathers today's raw daily log and project statuses,
then spawns a Claude Code session to write a curated summary.

Usage:
    uv run python .claude/scripts/reflect.py
    uv run python .claude/scripts/reflect.py --date 2026-04-04
"""

import glob
from datetime import datetime
from pathlib import Path

import typer

from spawn_session import spawn

PROJECT_ROOT = Path(__file__).parent.parent.parent
VAULT = PROJECT_ROOT / "Memory"

app = typer.Typer()


@app.command()
def reflect(date: str = typer.Option(None, help="Date to reflect on (YYYY-MM-DD). Defaults to today.")):
    """Run the daily reflection: summarize raw logs and update MEMORY.md."""
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    raw_log = VAULT / "daily" / "raw" / f"{target_date}.md"

    if not raw_log.exists():
        typer.echo(f"No raw log found for {target_date}. Nothing to reflect on.")
        raise typer.Exit()

    # Gather context
    raw_content = raw_log.read_text(encoding="utf-8")

    # Gather all project statuses
    status_files = glob.glob(str(VAULT / "projects" / "*" / "STATUS.md"))
    status_files += glob.glob(str(VAULT / "projects" / "*" / "*" / "STATUS.md"))
    project_context = ""
    for sf in sorted(status_files):
        project_context += f"\n\n---\n\n# {Path(sf).relative_to(VAULT)}\n"
        project_context += Path(sf).read_text(encoding="utf-8")

    # Build the prompt
    prompt = f"""You are running the nightly reflection for {target_date}.

## Raw Daily Log
{raw_content}

## Project Statuses
{project_context}

## Your Task
1. Write a daily summary to `Memory/daily/summaries/{target_date}.md` using this template:
   - Key Accomplishments (with relative-link pointers to source files)
   - Decisions Made (with pointers)
   - Open Items (with pointers)
   - Active Focus (projects + current work)
   - Tomorrow (what carries forward)
2. Update `Memory/MEMORY.md` with anything worth keeping long-term.
3. Include relative-link pointers to source files for each item.
"""

    typer.echo(f"Reflecting on {target_date}...")
    result = spawn(prompt, timeout=180)
    typer.echo(result)
    typer.echo(f"Reflection complete for {target_date}.")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run spawn tests (slow tests)**

Run:
```bash
uv run pytest tests/test_spawn.py -v -m slow
```

The `slow` marker is already configured in `pyproject.toml` (added in Task 4).

Expected: All 4 tests PASS (these are real API calls — each takes 5-30 seconds).

- [ ] **Step 5: Commit**

```bash
git add .claude/scripts/spawn_session.py .claude/scripts/reflect.py tests/test_spawn.py pyproject.toml
git commit -m "feat: add spawn utility and daily reflection skeleton"
```

---

### Task 10: pyqmd Collection Setup

**Files:**
- No new files in this repo — pyqmd is an external dependency

- [ ] **Step 1: Add pyqmd dependency**

Run:
```bash
uv add pyqmd
```

- [ ] **Step 2: Create the vault collection**

Run:
```bash
uv run qmd add vault Memory/ --description "Pepper's memory vault"
```

Expected: Collection "vault" registered.

- [ ] **Step 3: Index the vault**

Run:
```bash
uv run qmd index vault
```

Expected: All markdown files in Memory/ indexed. Should see output listing files processed.

- [ ] **Step 4: Test search works**

Run:
```bash
uv run qmd search vault "executive assistant"
```

Expected: Results from IDENTITY.md and/or SOUL.md (which mention "Executive Assistant").

- [ ] **Step 5: Commit**

```bash
git add uv.lock pyproject.toml
git commit -m "feat: add pyqmd and create vault collection"
```

---

### Task 11: pyqmd File Watcher (`qmd watch`)

**NOTE:** This task modifies the pyqmd library at `E:\workspaces\ai\pyqmd` (or wherever it's cloned), NOT the Pepper repo.

**Files (in pyqmd repo):**
- Create: `pyqmd/cli/watch.py` (or add to existing CLI)
- Create: `tests/test_watch.py`

- [ ] **Step 1: Write tests for file watcher**

Create `tests/test_pyqmd_integration.py` in the **Pepper** repo:
```python
"""Tests for pyqmd integration with Pepper vault.

These test that pyqmd is properly configured and can search vault content.
The file watcher tests require pyqmd to have the `qmd watch` command implemented.
"""

import subprocess
import time
from pathlib import Path

import pytest

VAULT = Path(__file__).parent.parent / "Memory"


@pytest.mark.slow
def test_qmd_index_completes():
    """qmd index vault should complete without error."""
    result = subprocess.run(
        ["uv", "run", "qmd", "index", "vault"],
        capture_output=True,
        text=True,
        cwd=str(VAULT.parent),
    )
    assert result.returncode == 0, f"Index failed: {result.stderr}"


@pytest.mark.slow
def test_qmd_search_returns_results():
    """Searching for known content should return results."""
    # First index
    subprocess.run(["uv", "run", "qmd", "index", "vault"], capture_output=True, cwd=str(VAULT.parent))

    result = subprocess.run(
        ["uv", "run", "qmd", "search", "vault", "executive assistant"],
        capture_output=True,
        text=True,
        cwd=str(VAULT.parent),
    )
    assert result.returncode == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.slow
def test_qmd_search_new_file():
    """A newly created and indexed file should be searchable."""
    test_file = VAULT / "research" / "test_search_file.md"
    try:
        test_file.write_text("# Quantum Entanglement in Robotic Systems\n\nThis is a unique test document about quantum robotics.\n")
        subprocess.run(["uv", "run", "qmd", "index", "vault"], capture_output=True, cwd=str(VAULT.parent))

        result = subprocess.run(
            ["uv", "run", "qmd", "search", "vault", "quantum entanglement robotics"],
            capture_output=True,
            text=True,
            cwd=str(VAULT.parent),
        )
        assert "quantum" in result.stdout.lower() or "robotics" in result.stdout.lower()
    finally:
        if test_file.exists():
            test_file.unlink()
```

- [ ] **Step 2: Implement `qmd watch` in pyqmd**

This is a separate task in the pyqmd repo. The implementation should:
- Add a `watch` subcommand to the CLI
- Use `watchdog` to monitor the collection's directory
- Debounce changes (2-second window)
- Ignore patterns: `.obsidian/`, `.git/`, `*.lock`, `*.tmp`, `~*`
- On change: call the existing incremental index function
- Log to stdout
- Handle SIGINT/SIGTERM for clean shutdown

Refer to the spec at `docs/superpowers/specs/2026-04-04-pepper-foundation-design.md`, Phase 3 section, for full requirements.

- [ ] **Step 3: Implement `--path-prefix` filter in pyqmd**

Add a `--path-prefix` option to the `qmd search` command that filters results to files under the given path prefix. This is post-search filtering on chunk metadata — filter chunks whose `source_file` starts with the prefix.

- [ ] **Step 4: Run pyqmd integration tests**

Run:
```bash
uv run pytest tests/test_pyqmd_integration.py -v -m slow
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit (in Pepper repo)**

```bash
git add tests/test_pyqmd_integration.py
git commit -m "test: add pyqmd integration tests for vault search"
```

---

### Task 12: Concurrent Write Safety Tests

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_integration.py`:
```python
"""Integration tests for the full foundation.

Tests concurrent writes, hook lifecycle, and spawn + hooks end-to-end.
"""

import threading
from pathlib import Path

from shared import append_to_daily_log, get_daily_log_path


def test_concurrent_daily_log_writes(temp_vault):
    """Two threads writing to the same daily log should not corrupt it."""
    results = {"errors": []}

    def write_entries(prefix: str, count: int):
        try:
            for i in range(count):
                append_to_daily_log(
                    vault_path=temp_vault,
                    content=f"{prefix} entry {i}",
                    source="session",
                    session_id=f"{prefix}-{i}",
                )
        except Exception as e:
            results["errors"].append(str(e))

    t1 = threading.Thread(target=write_entries, args=("thread1", 10))
    t2 = threading.Thread(target=write_entries, args=("thread2", 10))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results["errors"]) == 0, f"Errors: {results['errors']}"

    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()

    # All 20 entries should be present
    for i in range(10):
        assert f"thread1 entry {i}" in text
        assert f"thread2 entry {i}" in text


def test_filelock_prevents_partial_writes(temp_vault):
    """Verify that filelock ensures atomic appends."""
    barrier = threading.Barrier(2)
    results = {"texts": []}

    def write_with_barrier(session_id: str):
        barrier.wait()  # Both threads start simultaneously
        append_to_daily_log(
            vault_path=temp_vault,
            content=f"Content from {session_id}",
            source="session",
            session_id=session_id,
        )

    t1 = threading.Thread(target=write_with_barrier, args=("simultaneous-1",))
    t2 = threading.Thread(target=write_with_barrier, args=("simultaneous-2",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    log_path = get_daily_log_path(temp_vault)
    text = log_path.read_text()

    # Both entries should be complete (not interleaved)
    assert "(session: simultaneous-1)" in text
    assert "(session: simultaneous-2)" in text
    assert "Content from simultaneous-1" in text
    assert "Content from simultaneous-2" in text
```

- [ ] **Step 2: Run integration tests**

Run:
```bash
uv run pytest tests/test_integration.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 3: Run the full test suite**

Run:
```bash
uv run pytest tests/ -v --ignore=tests/test_spawn.py --ignore=tests/test_pyqmd_integration.py
```

Expected: All unit tests PASS (excludes slow tests that need Claude API).

Then run slow tests:
```bash
uv run pytest tests/ -v -m slow
```

Expected: All slow tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add concurrent write safety and integration tests"
```

---

### Task 13: Final Verification

- [ ] **Step 1: Run full test suite**

Run:
```bash
uv run pytest tests/ -v
```

Expected: All tests PASS (slow tests skipped unless `-m slow` specified).

- [ ] **Step 2: Verify hooks in a live session**

Open a new Claude Code session in `E:\workspaces\ai\pepper`. Verify:
1. SessionStart hook fires — ask Claude "What is your name according to IDENTITY.md?" (should know it's Pepper without you reading the file)
2. Tier 1 context is present — ask "What are your hard boundaries?" (should list the three from SOUL.md)
3. Operations context is present — ask "Where are daily logs stored?" (should say `daily/raw/`)

- [ ] **Step 3: Verify spawn utility**

Run:
```bash
uv run python .claude/scripts/spawn_session.py "Read Memory/IDENTITY.md and tell me the agent name"
```

Expected: Response containing "Pepper".

- [ ] **Step 4: Verify reflection script**

Create a test raw daily log entry, then run reflection:
```bash
uv run python .claude/scripts/reflect.py --date $(date +%Y-%m-%d)
```

Expected: Summary file created at `Memory/daily/summaries/YYYY-MM-DD.md`.

- [ ] **Step 5: Verify pyqmd search**

Run:
```bash
uv run qmd search vault "proactive executive assistant"
```

Expected: Results from SOUL.md or IDENTITY.md.

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: Pepper foundation complete — vault, hooks, spawn, pyqmd"
```
