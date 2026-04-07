# Move Discord Integration into Pepper Package Design

**Date:** 2026-04-07
**Status:** Approved

## Problem

The Discord MCP server lives in `integrations/discord/` as a separate uv project. The generated `.mcp.json` references it via `uv --directory <path>`, but `pepper init` doesn't know the repo path, leaving the path empty and breaking the Discord connection.

## Solution

Move the Discord integration into `src/pepper/integrations/discord/` as part of the installable pepper package. Add a `pepper-discord` entry point so `.mcp.json` can reference it by command name, same pattern as `pepper-channel`.

## Changes

### 1. Move files

Move `integrations/discord/*.py` and `integrations/discord/jobs.yaml` into `src/pepper/integrations/discord/`. Add `__init__.py` files for the package.

### 2. Merge dependencies

Move these from the `dev` dependency group to main `dependencies` in `pyproject.toml`:
- `discord.py>=2.7.0` (replaces `discord-py>=2.0`)
- `apscheduler>=4.0.0a5`
- `sqlalchemy>=2.0.0`
- `aiosqlite>=0.20.0`

These overlap and stay as-is: `httpx`, `mcp`, `pyyaml`, `python-dotenv`

Remove the duplicates from the `dev` group.

### 3. Add entry point

```toml
[project.scripts]
pepper-discord = "pepper.integrations.discord.mcp_server:run"
```

The `mcp_server.py` currently calls `mcp.run(transport="stdio")` in the `if __name__` block. Needs a `run()` function wrapper for the entry point.

### 4. Fix internal imports

The Discord modules use bare imports (`from bot import client`, `from config import DISCORD_BOT_TOKEN`). These need to become package-relative imports (`from pepper.integrations.discord.bot import client` or relative `from .bot import client`).

### 5. Update .mcp.json template

Replace the `pepper-discord` entry:
```json
{
  "mcpServers": {
    "pepper-channel": { "command": "pepper-channel" },
    "pepper-discord": { "command": "pepper-discord" }
  }
}
```

Remove the `discord_integration_path` template variable from the template and the generator.

### 6. Update tests

Update Discord test imports from bare module names to `pepper.integrations.discord.*`.

### 7. Clean up

Remove `integrations/discord/` (the old separate project with its own pyproject.toml and uv.lock).

## Files

- Move: `integrations/discord/*.py` -> `src/pepper/integrations/discord/`
- Move: `integrations/discord/jobs.yaml` -> `src/pepper/integrations/discord/`
- Create: `src/pepper/integrations/__init__.py`
- Create: `src/pepper/integrations/discord/__init__.py`
- Modify: `pyproject.toml` — deps and entry point
- Modify: `src/pepper/init/templates/mcp.json.j2` — simplify
- Modify: `src/pepper/init/generator.py` — remove discord_integration_path param
- Modify: `src/pepper/cli.py` — remove discord_integration_path if referenced
- Modify: `tests/test_discord_*.py` — update imports
- Modify: `tests/test_scheduler*.py` — update imports
- Delete: `integrations/discord/` (old separate project)
