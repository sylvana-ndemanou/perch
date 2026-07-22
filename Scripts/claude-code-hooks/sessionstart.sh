#!/bin/bash
# Perch SessionStart hook — registers this Claude Code session so Perch can
# see it in the menu bar. Reads the JSON Claude Code sends on stdin per
# https://code.claude.com/docs/en/hooks#sessionstart
set -euo pipefail

# Walk up the process tree to find the actual `claude` process, rather than
# assuming a fixed number of hops — shells can exec-replace themselves or
# fork an extra layer depending on how Claude Code spawns command hooks, so
# a bare $PPID isn't reliable on its own.
find_claude_pid() {
  local pid=$$
  for _ in $(seq 1 6); do
    local ppid
    ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    [ -z "$ppid" ] && break
    local comm
    comm=$(ps -o comm= -p "$ppid" 2>/dev/null || true)
    if echo "$comm" | grep -qi 'claude'; then
      echo "$ppid"
      return 0
    fi
    pid="$ppid"
  done
  echo "$PPID" # best-effort fallback
}

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')
CWD=$(echo "$INPUT" | jq -r '.cwd')
PROJECT_NAME=$(basename "$CWD")
CLAUDE_PID=$(find_claude_pid)

PERCH_DIR="$HOME/Library/Application Support/Perch"
SESSIONS_DIR="$PERCH_DIR/sessions"
mkdir -p "$SESSIONS_DIR"

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
jq -n --arg projectName "$PROJECT_NAME" --arg updatedAt "$NOW" --argjson pid "$CLAUDE_PID" \
  '{projectName: $projectName, status: "idle", lastTool: null, updatedAt: $updatedAt, pid: $pid}' \
  > "$SESSIONS_DIR/${SESSION_ID}.json"

exit 0
