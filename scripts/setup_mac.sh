#!/usr/bin/env bash
# Set up the personal-outlook-agent dev environment on macOS using uv.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Source the env file so uv is on PATH for the rest of this script
  # shellcheck source=/dev/null
  source "$HOME/.local/bin/env"
fi

# Resolve uv via PATH or the default install location
UV_BIN="$(command -v uv 2>/dev/null || echo "$HOME/.local/bin/uv")"

if [[ -d .venv ]]; then
  echo "Virtual environment already exists — skipping creation."
else
  "$UV_BIN" venv --python 3.13
fi

"$UV_BIN" pip install -e ".[dev]"

echo ""
echo "Done. Activate with:"
echo "  source .venv/bin/activate"
echo ""
echo "Then verify your setup:"
echo "  outlook-agent diagnostics"
