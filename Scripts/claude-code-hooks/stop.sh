#!/bin/bash
# Perch Stop hook — marks the session idle once Claude finishes responding.
# Reference: https://code.claude.com/docs/en/hooks#stop
set -euo pipefail

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
  echo "$PPID"
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
