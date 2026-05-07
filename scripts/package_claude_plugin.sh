#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_ROOT="$ROOT/plugins/claude/oneshot"
DIST_DIR="$ROOT/dist/claude"
ZIP_PATH="$DIST_DIR/oneshot-claude-plugin-0.1.0.zip"
PLUGIN_PATH="$DIST_DIR/oneshot-claude-plugin-0.1.0.plugin"

mkdir -p "$DIST_DIR"
rm -f "$ZIP_PATH" "$PLUGIN_PATH"

(
  cd "$PLUGIN_ROOT"
  zip -r "$ZIP_PATH" . \
    -x '*.DS_Store' \
    -x '__MACOSX/*' \
    -x '*.git*'
)

cp "$ZIP_PATH" "$PLUGIN_PATH"
unzip -t "$ZIP_PATH" >/dev/null
unzip -t "$PLUGIN_PATH" >/dev/null

echo "Built $ZIP_PATH"
echo "Built $PLUGIN_PATH"
