# Development

## Setup

```bash
bash scripts/setup_mac.sh      # or: uv venv --python 3.13 && uv pip install -e ".[dev]"
source .venv/bin/activate
```

## Layout

```
src/outlook_agent/
  config.py         settings (env-driven)
  main.py           composition root (Container) + API entry point
  domain/           Pydantic models, enums, capabilities, diagnostics
  providers/        base.py (interface) + outlook/applescript (osascript-isolated)
  services/         MailService · ThreadService · DiagnosticsService
  api/              FastAPI app + thin routers
  mcp/              FastMCP server + thin tools
  cli/              Typer CLI (JSON-first)
tests/
  unit/  integration/  (hermetic; live/ is opt-in, read-only)
```

## Quality gates

```bash
pytest                 # unit + integration
ruff check .           # lint
mypy src               # types
```

## Adding a capability (pattern)

1. Extend the `OutlookProvider` protocol in `providers/base.py`.
2. Implement it in `providers/outlook/applescript/` (script in `scripts.py`, parse in
   `parsers.py`, method in `provider.py`) and advertise the capability.
3. Add orchestration to the relevant service (never in the interface layer).
4. Expose it through MCP, REST, and CLI — thin adapters only.
5. Write/destructive operations must route through `ActionService` (Milestone 6).

## Conventions

- Interfaces contain no business logic and never run AppleScript.
- Services depend on the `OutlookProvider` interface, never a concrete provider.
- Keep MCP tool schemas stable even when provider internals change.
- Email content is untrusted; never feed it into system prompts.
