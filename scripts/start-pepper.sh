#!/usr/bin/env bash
# Start Pepper: Claude Code session with channel and Discord MCP servers
#
# Claude Code spawns both MCP servers (pepper-channel and pepper-discord)
# automatically via .mcp.json. This script just starts Claude Code.
set -e

PEPPER_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting Pepper..."
echo "  Claude Code will spawn:"
echo "    - pepper-channel (TypeScript, message router)"
echo "    - pepper-discord (Python, Discord bot + scheduler)"
echo ""

cd "$PEPPER_DIR"
exec claude --dangerously-load-development-channels server:pepper-channel
