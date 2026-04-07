# Pepper Start/Stop/Status CLI Commands Design

**Date:** 2026-04-07
**Status:** Approved

## Problem

After `pepper init`, users must manually `cd ~/.pepper && claude` to run Pepper. There's no way to launch Pepper from anywhere, run her in the background for headless operation (Discord bot, scheduled tasks), or check if she's running.

## Solution

Add `pepper start`, `pepper stop`, and `pepper status` commands to the CLI. `pepper start` auto-updates the runtime config before launching, eliminating the need to manually re-run `pepper init` after package updates.

## Commands

### `pepper start` (interactive, default)

1. Call `generate_runtime()` silently — refreshes config/skills/hooks, preserves vault
2. Launch `claude` with cwd set to `~/.pepper/`
3. Takes over the terminal (interactive session)

### `pepper start --background`

1. Call `generate_runtime()` silently
2. Spawn `claude --dangerously-skip-permissions -p "You are Pepper. Monitor Discord and handle scheduled tasks."` detached from the terminal
3. Write PID to `~/.pepper/.pid`
4. Print "Pepper started (PID: 12345)"

### `pepper stop`

1. Read `~/.pepper/.pid`
2. If PID file missing or process not alive: print "Pepper is not running"
3. Kill the process tree (Claude Code + child MCP servers)
4. Remove the PID file
5. Print "Pepper stopped"

### `pepper status`

1. Check if `~/.pepper/.pid` exists
2. Check if the PID is alive
3. Print "Pepper is running (PID: 12345)" or "Pepper is not running"

## Auto-Update Behavior

`pepper start` always calls `generate_runtime()` before launching. This means:

- After `uv sync` (package update), the next `pepper start` automatically refreshes templates, skills, hook references, and MCP config
- Vault files (Memory/) are never overwritten
- No separate `pepper init` step needed after updates
- `pepper init` still exists for first-time setup and `--migrate`

## PID File

- Location: `~/.pepper/.pid`
- Contains: single line with the process ID
- Created by: `pepper start --background`
- Removed by: `pepper stop`
- Checked by: `pepper status`, `pepper stop`

## Process Tree Cleanup

On `pepper stop`, the entire process tree must be killed — Claude Code spawns MCP server child processes that would be orphaned if only the parent is killed. On Windows, `taskkill /F /T /PID` handles this. On Unix, kill the process group or walk the tree.

## Files

- Modify: `src/pepper/cli.py` — replace stubs with implementations
- Create: `tests/test_cli.py` — test validation, PID file management, auto-init
