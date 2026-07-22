#!/bin/bash
# Builds Perch in release mode and installs it as a `perch` command, so you
# can launch it with just `perch` instead of `swift build && swift run Perch`
# every time.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Building Perch (release)…"
swift build -c release

BIN_SRC=".build/release/Perch"
DEST_DIR="/usr/local/bin"
BIN_DEST="$DEST_DIR/perch"

if [ ! -f "$BIN_SRC" ]; then
  echo "error: build succeeded but $BIN_SRC wasn't found — check the swift build output above." >&2
  exit 1
fi

if [ -w "$DEST_DIR" ] || [ -w "$(dirname "$DEST_DIR")" ]; then
  cp "$BIN_SRC" "$BIN_DEST"
else
  echo "No write access to $DEST_DIR, trying with sudo…"
  sudo cp "$BIN_SRC" "$BIN_DEST"
fi

echo "✓ Installed → $BIN_DEST"
echo "Run it anytime with: perch"
echo
echo "Re-run this script after pulling changes to update the installed binary."
