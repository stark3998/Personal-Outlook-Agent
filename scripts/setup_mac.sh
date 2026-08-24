#!/usr/bin/env bash
# Set up the personal-outlook-agent dev environment on macOS using uv.
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

uv venv --python 3.13
uv pip install -e ".[dev]"

echo "Done. Activate with: source .venv/bin/activate"
echo "Then run: outlook-agent diagnostics"
