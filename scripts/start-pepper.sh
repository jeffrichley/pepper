#!/usr/bin/env bash
# Start Pepper: Claude Code session with channel + Discord bot
set -e

PEPPER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$PEPPER_DIR/.pids"
mkdir -p "$PID_DIR"

echo "Starting Pepper..."

# Start Claude Code with the channel
cd "$PEPPER_DIR"
claude --dangerously-load-development-channels server:pepper-channel &
CLAUDE_PID=$!
echo $CLAUDE_PID > "$PID_DIR/claude.pid"
echo "  Claude Code started (PID: $CLAUDE_PID)"

# Wait for channel server to be ready
echo -n "  Waiting for channel server"
for i in $(seq 1 30); do
    if curl -s http://localhost:8788/health > /dev/null 2>&1; then
        echo " ready!"
        break
    fi
    echo -n "."
    sleep 1
done

if ! curl -s http://localhost:8788/health > /dev/null 2>&1; then
    echo " FAILED"
    echo "Channel server did not start. Check Claude Code logs."
    kill $CLAUDE_PID 2>/dev/null
    exit 1
fi

# Start Discord bot
cd "$PEPPER_DIR/integrations/discord"
uv run python bot.py &
DISCORD_PID=$!
echo $DISCORD_PID > "$PID_DIR/discord.pid"
echo "  Discord bot started (PID: $DISCORD_PID)"

echo ""
echo "Pepper is running!"
echo "  Channel server: http://localhost:8788"
echo "  Discord bot: PID $DISCORD_PID"
echo ""
echo "Stop with: $PEPPER_DIR/scripts/stop-pepper.sh"

# Wait for either process to exit
wait -n $CLAUDE_PID $DISCORD_PID 2>/dev/null || true
echo "A process exited. Shutting down..."
"$PEPPER_DIR/scripts/stop-pepper.sh"
