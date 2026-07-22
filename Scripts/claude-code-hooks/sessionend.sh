#!/bin/bash
# Perch SessionEnd hook — removes the session from Perch once it terminates.
# Reference: https://code.claude.com/docs/en/hooks#sessionend
set -euo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')

PERCH_DIR="$HOME/Library/Application Support/Perch"
rm -f "$PERCH_DIR/sessions/${SESSION_ID}.json" \
      "$PERCH_DIR/pending/${SESSION_ID}.json" \
      "$PERCH_DIR/decisions/${SESSION_ID}.json"

exit 0
