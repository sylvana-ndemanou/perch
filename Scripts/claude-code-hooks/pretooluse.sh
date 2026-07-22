#!/bin/bash
# Perch PreToolUse hook — pauses a gated tool call until you approve or deny
# it from the Perch menu bar. Register this on the tools you want Perch to
# gate (Bash/Edit/Write/NotebookEdit by default — see README); Read/Glob/Grep
# etc. are normally left out since they don't need approval anyway.
#
# Reference: https://code.claude.com/docs/en/hooks#pretooluse
# Command hooks default to a 600s timeout, so this polls for up to ~575s
# before falling through to Claude Code's own permission flow.
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
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')
CWD=$(echo "$INPUT" | jq -r '.cwd')
PROJECT_NAME=$(basename "$CWD")
CLAUDE_PID=$(find_claude_pid)

SUMMARY=$(echo "$INPUT" | jq -r '
  if .tool_input.command then .tool_input.command
  elif .tool_input.file_path then .tool_input.file_path
  else (.tool_input | tostring)
  end
')

PERCH_DIR="$HOME/Library/Application Support/Perch"
SESSIONS_DIR="$PERCH_DIR/sessions"
PENDING_DIR="$PERCH_DIR/pending"
DECISIONS_DIR="$PERCH_DIR/decisions"
mkdir -p "$SESSIONS_DIR" "$PENDING_DIR" "$DECISIONS_DIR"

SESSION_FILE="$SESSIONS_DIR/${SESSION_ID}.json"
PENDING_FILE="$PENDING_DIR/${SESSION_ID}.json"
DECISION_FILE="$DECISIONS_DIR/${SESSION_ID}.json"

# Clear any stale decision left over from a previous request on this session
rm -f "$DECISION_FILE"

write_session_status() {
  local status="$1"
  local now
  now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  jq -n --arg projectName "$PROJECT_NAME" --arg updatedAt "$now" --arg tool "$TOOL_NAME" --arg status "$status" --argjson pid "$CLAUDE_PID" \
    '{projectName: $projectName, status: $status, lastTool: $tool, updatedAt: $updatedAt, pid: $pid}' \
    > "$SESSION_FILE"
}

write_session_status "awaitingInput"
jq -n --arg toolName "$TOOL_NAME" --arg summary "$SUMMARY" \
  '{toolName: $toolName, summary: $summary}' > "$PENDING_FILE"

for _ in $(seq 1 1150); do
  if [ -f "$DECISION_FILE" ]; then
    DECISION=$(jq -r '.decision' "$DECISION_FILE")
    REASON=$(jq -r '.reason // "Denied from Perch"' "$DECISION_FILE")
    rm -f "$DECISION_FILE" "$PENDING_FILE"
    write_session_status "working"

    if [ "$DECISION" = "deny" ]; then
      jq -n --arg reason "$REASON" \
        '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $reason}}'
    else
      jq -n '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "allow"}}'
    fi
    exit 0
  fi
  sleep 0.5
done

# Timed out waiting on a decision — clean up and let Claude Code's normal
# permission flow (or your permission mode) decide instead.
rm -f "$PENDING_FILE"
exit 0
