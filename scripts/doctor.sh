#!/usr/bin/env bash
# Show the health and process status of all outlook-agent components.
set -euo pipefail

VENV_BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.venv/bin"

echo "=== Outlook Agent — Status ==="
echo ""

# --- Process status ---
echo "-- Processes --"

if pgrep -qf "outlook-agent-mcp" 2>/dev/null; then
  echo "  MCP server    : running  (pid $(pgrep -f 'outlook-agent-mcp' | head -1))"
else
  echo "  MCP server    : not running  (Claude Desktop starts/stops it automatically)"
fi

if pgrep -qf "outlook-agent-api\|uvicorn.*outlook_agent" 2>/dev/null; then
  echo "  REST API      : running  (pid $(pgrep -f 'outlook-agent-api|uvicorn.*outlook_agent' | head -1))"
else
  echo "  REST API      : not running"
fi

if launchctl list 2>/dev/null | grep -q "com.personal.outlook-agent.api"; then
  echo "  launchd (api) : loaded"
else
  echo "  launchd (api) : not loaded"
fi

if launchctl list 2>/dev/null | grep -q "com.personal.outlook-agent.sync"; then
  echo "  launchd (sync): loaded"
else
  echo "  launchd (sync): not loaded"
fi

echo ""

# --- Diagnostics ---
echo "-- Diagnostics --"
"$VENV_BIN/outlook-agent" diagnostics 2>&1
