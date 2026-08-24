# personal-outlook-agent

Local-first Outlook automation platform for macOS. The MCP server is **one interface** to
the platform — REST and CLI call the exact same application services. AppleScript is
isolated inside the provider layer; the LLM (Microsoft Foundry) is isolated behind an
`LLMProvider` interface.

> Status: **Milestones 0–14 implemented.** Read path, drafts/reply/forward, gated
> send/delete/move/junk, folder management, calendar/contacts/tasks/notes, the
> ActionService approval+audit engine, Microsoft Foundry intelligence (summaries,
> action-item extraction, reply proposals), a SQLite cache + FTS5 index, and on-demand sync
> are all exposed over MCP, REST, and CLI. **All AppleScript-backed write/PIM operations
> require live-Mac verification** (they have been exercised only against an in-memory fake
> provider so far). The New Outlook UI provider is an isolated placeholder. See
> [docs/architecture.md](docs/architecture.md).

## Architecture at a glance

```
Clients (Claude Desktop / VS Code / CLI / web)
  → Interface (FastMCP · FastAPI · CLI)     ← thin, no business logic
  → Application services                    ← MailService · ThreadService · DiagnosticsService
  → Domain + policy (Pydantic, capabilities)
  → Provider interface (OutlookProvider)
  → OutlookAppleScriptProvider → osascript → Microsoft Outlook
```

See [docs/architecture.md](docs/architecture.md) and the research in
[docs/research/UPSTREAM_MATRIX.md](docs/research/UPSTREAM_MATRIX.md).

## Requirements

- **macOS** with classic Microsoft Outlook (AppleScript provider), or **Windows** with
  classic Microsoft Outlook (COM provider). The provider is auto-selected by platform
  (`OUTLOOK_AGENT_PROVIDER=auto`); force one with `com` or `applescript`.
- Python 3.13+, [uv](https://docs.astral.sh/uv/).
- macOS: Automation permission for Outlook. Windows: `pywin32` (installed automatically)
  and Outlook registered as a COM server.

> The codebase imports and its test suite runs on any OS; live Outlook access requires the
> matching platform (macOS `osascript` or Windows COM).

## Quickstart

```bash
bash scripts/setup_mac.sh          # uv venv + editable install
source .venv/bin/activate
outlook-agent diagnostics          # structured health report (JSON)
```

### Run the interfaces

```bash
outlook-agent-api                  # FastAPI on http://127.0.0.1:8765
outlook-agent-mcp                  # FastMCP over stdio (for MCP clients)

outlook-agent accounts
outlook-agent folders --account-id 1
outlook-agent search "Entra" --limit 10
outlook-agent read 100 --account-id 1 --folder-id 10
outlook-agent thread 900
```

### REST endpoints (read-only slice)

| Method | Path |
|--------|------|
| GET | `/health` |
| GET | `/api/v1/diagnostics` |
| GET | `/api/v1/accounts` |
| GET | `/api/v1/folders` |
| GET | `/api/v1/mail?account_id=&folder_id=` |
| GET | `/api/v1/mail/search?q=` |
| GET | `/api/v1/mail/{item_id}?account_id=&folder_id=` |
| GET | `/api/v1/threads/{conversation_id}` |

## MCP clients

- **VS Code:** copy [configs/vscode.mcp.json.example](configs/vscode.mcp.json.example) to
  `.vscode/mcp.json`.
- **Claude Desktop:** merge [configs/claude_desktop.json.example](configs/claude_desktop.json.example)
  into `claude_desktop_config.json`, or run `bash scripts/install_claude_mcp.sh` for Claude Code.

Read tools may be auto-allowed; write/send/delete tools (future milestones) must always
prompt for approval.

## Development

```bash
uv pip install -e ".[dev]"
pytest                 # unit + integration (hermetic; no Outlook required)
ruff check .
mypy src
```

Live Outlook tests are opt-in and **read-only**: set `OUTLOOK_LIVE_TESTS=true`. Automated
tests never send or delete mail.

## Security

Email content is untrusted data, never instructions. Secrets live in macOS Keychain / env,
never in Git. Logs never contain bodies, tokens, or attachment contents. See
[docs/security.md](docs/security.md).

## License

MIT.
