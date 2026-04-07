# Move Discord Integration into Package — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Discord integration from `integrations/discord/` into `src/pepper/integrations/discord/` as an installable package with a `pepper-discord` entry point.

**Architecture:** Copy Discord source files into the pepper package, convert bare imports to relative imports, merge dependencies into the main pyproject.toml, add a `pepper-discord` entry point, simplify the `.mcp.json` template, and update all tests.

**Tech Stack:** Python 3.12, uv, discord.py, apscheduler, sqlalchemy, aiosqlite, mcp

---

### Task 1: Move Discord files into the package

**Files:**
- Create: `src/pepper/integrations/__init__.py`
- Create: `src/pepper/integrations/discord/__init__.py`
- Move: `integrations/discord/bot.py` -> `src/pepper/integrations/discord/bot.py`
- Move: `integrations/discord/config.py` -> `src/pepper/integrations/discord/config.py`
- Move: `integrations/discord/discord_tools.py` -> `src/pepper/integrations/discord/discord_tools.py`
- Move: `integrations/discord/embeds.py` -> `src/pepper/integrations/discord/embeds.py`
- Move: `integrations/discord/mcp_server.py` -> `src/pepper/integrations/discord/mcp_server.py`
- Move: `integrations/discord/scheduler.py` -> `src/pepper/integrations/discord/scheduler.py`
- Move: `integrations/discord/scheduler_tools.py` -> `src/pepper/integrations/discord/scheduler_tools.py`
- Move: `integrations/discord/jobs.yaml` -> `src/pepper/integrations/discord/jobs.yaml`

- [ ] **Step 1: Create package directories and copy files**

```bash
mkdir -p src/pepper/integrations/discord
touch src/pepper/integrations/__init__.py
touch src/pepper/integrations/discord/__init__.py
cp integrations/discord/bot.py src/pepper/integrations/discord/
cp integrations/discord/config.py src/pepper/integrations/discord/
cp integrations/discord/discord_tools.py src/pepper/integrations/discord/
cp integrations/discord/embeds.py src/pepper/integrations/discord/
cp integrations/discord/mcp_server.py src/pepper/integrations/discord/
cp integrations/discord/scheduler.py src/pepper/integrations/discord/
cp integrations/discord/scheduler_tools.py src/pepper/integrations/discord/
cp integrations/discord/jobs.yaml src/pepper/integrations/discord/
```

- [ ] **Step 2: Commit the raw copy (before import changes)**

```bash
git add src/pepper/integrations/
git commit -m "chore: copy Discord integration files into package"
```

---

### Task 2: Convert bare imports to relative imports

All Discord modules use bare imports like `from config import CHANNEL_URL`. These must become relative imports since the modules are now inside a package.

**Files:**
- Modify: `src/pepper/integrations/discord/bot.py`
- Modify: `src/pepper/integrations/discord/discord_tools.py`
- Modify: `src/pepper/integrations/discord/mcp_server.py`
- Modify: `src/pepper/integrations/discord/scheduler.py`
- Modify: `src/pepper/integrations/discord/scheduler_tools.py`

- [ ] **Step 1: Fix imports in bot.py**

Replace:
```python
from config import CHANNEL_URL
from embeds import build_embed
```
With:
```python
from .config import CHANNEL_URL
from .embeds import build_embed
```

- [ ] **Step 2: Fix imports in discord_tools.py**

Replace:
```python
from embeds import build_embed
```
With:
```python
from .embeds import build_embed
```

- [ ] **Step 3: Fix imports in mcp_server.py**

Replace:
```python
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
```
With:
```python
from .bot import client, start_bot
from .config import DISCORD_BOT_TOKEN, JOBS_YAML
from .discord_tools import (
    add_reaction_impl,
    get_channel_info_impl,
    get_recent_messages_impl,
    list_channels_impl,
    send_discord_message_impl,
    send_typing_impl,
)
from .scheduler import create_scheduler, seed_default_jobs
from .scheduler_tools import (
    create_job_impl,
    delete_job_impl,
    list_jobs_impl,
    pause_job_impl,
    resume_job_impl,
    update_job_impl,
)
```

- [ ] **Step 4: Fix imports in scheduler.py**

Replace:
```python
from config import CHANNEL_URL, SCHEDULER_DB, TIMEZONE
```
With:
```python
from .config import CHANNEL_URL, SCHEDULER_DB, TIMEZONE
```

- [ ] **Step 5: Fix imports in scheduler_tools.py**

Replace:
```python
from scheduler import build_trigger, execute_job
```
With:
```python
from .scheduler import build_trigger, execute_job
```

- [ ] **Step 6: Add a `run()` entry point to mcp_server.py**

The current `mcp_server.py` has `mcp.run(transport="stdio")` inside `if __name__ == "__main__"`. Add a function for the entry point:

At the bottom of `src/pepper/integrations/discord/mcp_server.py`, replace:
```python
if __name__ == "__main__":
    mcp.run(transport="stdio")
```
With:
```python
def run():
    """Entry point for pepper-discord command."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
```

- [ ] **Step 7: Verify the module can be imported**

Run: `uv run python -c "from pepper.integrations.discord.mcp_server import run; print('ok')"`
Expected: `ok`

Note: This may fail due to `config.py` raising RuntimeError if DISCORD_BOT_TOKEN is not set. That's expected — it will work at runtime when the env var is set. If it fails, temporarily set the env var: `DISCORD_BOT_TOKEN=test uv run python -c "from pepper.integrations.discord.mcp_server import run; print('ok')"`

- [ ] **Step 8: Commit**

```bash
git add src/pepper/integrations/discord/
git commit -m "refactor: convert Discord imports to relative package imports"
```

---

### Task 3: Update pyproject.toml — merge deps and add entry point

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add Discord dependencies to main deps**

Add these to the `dependencies` list in `pyproject.toml` (some may already be there as dev deps):
```
"discord.py>=2.7.0",
"apscheduler>=4.0.0a5",
"sqlalchemy>=2.0.0",
"aiosqlite>=0.20.0",
```

- [ ] **Step 2: Add the pepper-discord entry point**

In the `[project.scripts]` section, add:
```toml
pepper-discord = "pepper.integrations.discord.mcp_server:run"
```

- [ ] **Step 3: Remove duplicates from dev deps**

Remove from the `[dependency-groups] dev` list:
- `"aiosqlite>=0.20.0"` (now in main deps)
- `"apscheduler>=4.0.0a5"` (now in main deps)
- `"discord-py>=2.0"` (replaced by `"discord.py>=2.7.0"` in main deps)
- `"sqlalchemy[asyncio]>=2.0"` (replaced by `"sqlalchemy>=2.0.0"` in main deps — keep `[asyncio]` if needed, but `aiosqlite` handles async)

- [ ] **Step 4: Run uv sync**

Run: `uv sync`
Expected: Dependencies resolve and install

- [ ] **Step 5: Verify entry point**

Run: `DISCORD_BOT_TOKEN=test uv run pepper-discord --help 2>&1 || echo "entry point exists"`

The command will likely fail (MCP server expects stdio), but the important thing is the entry point resolves.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add pepper-discord entry point, merge Discord deps to main"
```

---

### Task 4: Update .mcp.json template and generator

**Files:**
- Modify: `src/pepper/init/templates/mcp.json.j2`
- Modify: `src/pepper/init/generator.py`

- [ ] **Step 1: Simplify the mcp.json template**

Replace the content of `src/pepper/init/templates/mcp.json.j2` with:

```json
{
  "mcpServers": {
    "pepper-channel": {
      "command": "pepper-channel"
    },
    "pepper-discord": {
      "command": "pepper-discord"
    }
  }
}
```

No more Jinja2 variables — it's now a static file.

- [ ] **Step 2: Remove discord_integration_path from the generator**

In `src/pepper/init/generator.py`, remove the `discord_integration_path` parameter from `generate_runtime()`:

Change the signature from:
```python
def generate_runtime(
    runtime_path: Path | None = None,
    discord_integration_path: str = "",
    migrate_from: Path | None = None,
) -> Path:
```
To:
```python
def generate_runtime(
    runtime_path: Path | None = None,
    migrate_from: Path | None = None,
) -> Path:
```

And change the .mcp.json rendering from:
```python
    (runtime_path / ".mcp.json").write_text(
        template.render(discord_integration_path=discord_integration_path)
    )
```
To:
```python
    (runtime_path / ".mcp.json").write_text(template.render())
```

Also update the docstring to remove the `discord_integration_path` arg.

- [ ] **Step 3: Run init tests to verify nothing broke**

Run: `uv run pytest tests/test_init.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/pepper/init/templates/mcp.json.j2 src/pepper/init/generator.py
git commit -m "refactor: simplify mcp.json template, remove discord_integration_path"
```

---

### Task 5: Update Discord tests

**Files:**
- Modify: `tests/test_discord_embeds.py`
- Modify: `tests/test_discord_tools.py`
- Modify: `tests/test_scheduler.py`
- Modify: `tests/test_scheduler_tools.py`

All four files have `sys.path.insert(0, str(Path(__file__).parent.parent / "integrations" / "discord"))` and use bare imports. Replace with package imports.

- [ ] **Step 1: Update test_discord_embeds.py**

Remove the `sys.path.insert` line and the `sys`/`Path` imports if unused. Change all `from embeds import build_embed` to `from pepper.integrations.discord.embeds import build_embed`. Since tests use deferred imports inside test functions, update each one.

Read the file, remove the sys.path line, and change:
```python
from embeds import build_embed
```
To:
```python
from pepper.integrations.discord.embeds import build_embed
```
In every test function where it appears.

- [ ] **Step 2: Update test_discord_tools.py**

Remove `sys.path.insert` line. Replace:
```python
from discord_tools import (...)
```
With:
```python
from pepper.integrations.discord.discord_tools import (...)
```

Also replace any `from embeds import ...` with `from pepper.integrations.discord.embeds import ...`.

- [ ] **Step 3: Update test_scheduler.py**

Remove `sys.path.insert` line. Replace:
```python
from scheduler import load_seed_jobs, build_trigger, execute_job
```
With:
```python
from pepper.integrations.discord.scheduler import load_seed_jobs, build_trigger, execute_job
```

Also update any references to `JOBS_YAML` path — the `jobs.yaml` file is now at `src/pepper/integrations/discord/jobs.yaml`. If the test references the old path, update it. Check if the test uses a fixture path or the real file.

- [ ] **Step 4: Update test_scheduler_tools.py**

Remove `sys.path.insert` line. Replace:
```python
from scheduler_tools import (...)
from scheduler import execute_job
```
With:
```python
from pepper.integrations.discord.scheduler_tools import (...)
from pepper.integrations.discord.scheduler import execute_job
```

- [ ] **Step 5: Run all Discord and scheduler tests**

Run: `uv run pytest tests/test_discord_embeds.py tests/test_discord_tools.py tests/test_scheduler.py tests/test_scheduler_tools.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_discord_embeds.py tests/test_discord_tools.py tests/test_scheduler.py tests/test_scheduler_tools.py
git commit -m "refactor: update Discord test imports for package structure"
```

---

### Task 6: Remove old integration directory

**Files:**
- Delete: `integrations/discord/` (entire directory)

- [ ] **Step 1: Remove the old directory**

```bash
rm -rf integrations/discord/
```

If `integrations/` is now empty, remove it too:
```bash
rmdir integrations/ 2>/dev/null || true
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest tests/ -v --ignore=tests/test_spawn.py --ignore=tests/test_pyqmd_integration.py`
Expected: All PASS (99+ tests)

- [ ] **Step 3: Regenerate the runtime to verify the new .mcp.json**

Run: `uv run pepper init`

Then check:
Run: `cat ~/.pepper/.mcp.json`
Expected: Shows `"pepper-discord": { "command": "pepper-discord" }` — no more `uv --directory` path.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove old integrations/discord directory"
```
