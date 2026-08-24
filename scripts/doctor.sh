#!/usr/bin/env bash
# Show the health and process status of all outlook-agent components.
# Usage: doctor.sh [--reload]
#   --reload  Restart any loaded launchd services, then show status.
set -euo pipefail

VENV_BIN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.venv/bin"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
API_PLIST="$LAUNCH_AGENTS_DIR/com.personal.outlook-agent.api.plist"
SYNC_PLIST="$LAUNCH_AGENTS_DIR/com.personal.outlook-agent.sync.plist"

reload_service() {
  local label="$1"
  local plist="$2"
  if launchctl list 2>/dev/null | grep -q "$label"; then
    echo "  Reloading $label ..."
    launchctl unload "$plist" 2>/dev/null && launchctl load "$plist" && echo "  OK"
  else
    echo "  $label not loaded — skipping"
  fi
}

if [[ "${1:-}" == "--reload" ]]; then
  echo "=== Outlook Agent — Reload ==="
  echo ""
  reload_service "com.personal.outlook-agent.api"  "$API_PLIST"
  reload_service "com.personal.outlook-agent.sync" "$SYNC_PLIST"
  echo ""
fi

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
