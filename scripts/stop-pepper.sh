#!/usr/bin/env bash
# Stop Pepper: kill all managed processes
PEPPER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_DIR="$PEPPER_DIR/.pids"

echo "Stopping Pepper..."

for pidfile in "$PID_DIR"/*.pid; do
    [ -f "$pidfile" ] || continue
    PID=$(cat "$pidfile")
    NAME=$(basename "$pidfile" .pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        echo "  Stopped $NAME (PID: $PID)"
    else
        echo "  $NAME already stopped"
    fi
    rm -f "$pidfile"
done

echo "Pepper stopped."
