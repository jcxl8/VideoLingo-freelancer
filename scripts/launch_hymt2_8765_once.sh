#!/usr/bin/env bash
set -euo pipefail

PORT="${HYMT2_PORT:-8765}"
PID_FILE="/tmp/hymt2-8765.pid"
LOG_FILE="/tmp/hymt2-8765.log"
ERR_FILE="/tmp/hymt2-8765.err"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_SCRIPT="$SCRIPT_DIR/start_hymt2_8765.sh"

if /usr/sbin/lsof -nP -iTCP:${PORT} -sTCP:LISTEN >/dev/null 2>&1; then
  exit 0
fi

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && /bin/ps -p "$old_pid" >/dev/null 2>&1; then
    /bin/kill "$old_pid" >/dev/null 2>&1 || true
  fi
fi

/usr/bin/nohup "$START_SCRIPT" > "$LOG_FILE" 2> "$ERR_FILE" &
echo $! > "$PID_FILE"
