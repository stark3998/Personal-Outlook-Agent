#!/usr/bin/env bash
# Register the MCP server with Claude Code.
set -euo pipefail
claude mcp add outlook -- outlook-agent-mcp
echo "Registered 'outlook' MCP server with Claude Code."
