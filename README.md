# Personal Outlook Agent

A **local-first Outlook automation platform** for macOS and Windows. It exposes your
desktop Outlook (mail, threads, drafts, calendar, contacts, tasks, notes) and an AI agent
layer through **three equal interfaces** — an **MCP server**, a **REST API**, and a
**CLI** — all sharing the exact same application services.

> **Status:** Milestones 0–14 implemented plus composite agent tools, persistent
> approvals, structured logging, and a Windows COM provider. Live-verified on macOS
> (Classic Outlook 16.112.1 + Exchange Online). Quality gates: 125 tests, 89% coverage,
> `mypy --strict` clean, `ruff` clean.

---

## Features

- **Cross-platform desktop Outlook** — Classic Outlook for macOS (AppleScript) or Windows
  (COM), auto-selected by platform.
- **Three interfaces, one brain** — FastMCP, FastAPI, and Typer CLI all call the same
  underlying services; no interface is more authoritative than another.
- **Safe by construction** — every write or destructive operation flows through a two-step
  prepare → confirm ActionService before anything touches Outlook.
- **AI agent layer** — summaries, action-item extraction, reply proposals, inbox digests,
  unanswered/follow-up detection, and meeting prep — powered by Azure OpenAI / Microsoft
  Foundry.
- **Prompt-injection aware** — email content is treated as untrusted data and never
  promoted to agent instructions.
- **Local SQLite index** — FTS5 full-text search with on-demand and incremental sync.
- **Production hygiene** — Pydantic v2, structured logging, `mypy --strict`, `ruff`, 89%
  test coverage, GitHub Actions CI.

---

## Requirements

- **Python 3.13+** and **[uv](https://github.com/astral-sh/uv)**
- **macOS:** Classic Outlook (not New Outlook). Grant Automation permission in
  **System Settings → Privacy & Security → Automation**.
  > New Outlook for Mac is **not supported** (React Native engine, no AppleScript
  > dictionary). Use **Help → Revert to Legacy Outlook** if needed.
- **Windows:** Classic Outlook with `pywin32` (auto-installed).

---

## Quickstart

### macOS

```bash
bash scripts/setup_mac.sh
source .venv/bin/activate
cp .env.example .env        # fill in FOUNDRY_* credentials
outlook-agent diagnostics   # structured health check
```

### Windows

```powershell
uv venv --python 3.13 && uv pip install -e ".[dev]"
.venv\Scripts\activate
cp .env.example .env
outlook-agent diagnostics
```

Copy `.env.example` to `.env` and set your credentials. All app settings use the
`OUTLOOK_AGENT_` prefix; Foundry/Azure OpenAI uses `FOUNDRY_*` vars. See
[docs/configuration.md](docs/configuration.md).

---

## Running the Three Interfaces

```bash
# FastAPI — http://127.0.0.1:8765  (OpenAPI docs at /docs)
outlook-agent-api

# FastMCP stdio server (for MCP clients)
outlook-agent-mcp

# CLI — JSON-first output
outlook-agent --help
```

All three interfaces share identical business logic. See [docs/api.md](docs/api.md),
[docs/mcp.md](docs/mcp.md), and [docs/cli.md](docs/cli.md) for full references.

---

## MCP Client Setup

| Client | Steps |
| ------ | ----- |
| **VS Code** | Copy `configs/vscode.mcp.json.example` to `.vscode/mcp.json` |
| **Claude Desktop** | Merge `configs/claude_desktop.json.example` into `claude_desktop_config.json` |
| **Claude Code** | Run `bash scripts/install_claude_mcp.sh` |

Full MCP tool catalog (28 tools) and client configuration details are in
[docs/mcp.md](docs/mcp.md).

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/architecture.md](docs/architecture.md) | Layered design, module map, identity model, milestone roadmap |
| [docs/configuration.md](docs/configuration.md) | All env vars, Foundry setup, secrets handling |
| [docs/apple-script.md](docs/apple-script.md) | macOS AppleScript provider — how it works, known quirks, Outlook 16 compatibility |
| [docs/windows-com.md](docs/windows-com.md) | Windows COM provider notes |
| [docs/connectors.md](docs/connectors.md) | Provider abstraction, Foundry LLM connector, adding a new provider |
| [docs/api.md](docs/api.md) | Full REST endpoint reference |
| [docs/mcp.md](docs/mcp.md) | MCP tool catalog (28 tools) and client setup |
| [docs/cli.md](docs/cli.md) | CLI command reference |
| [docs/capabilities.md](docs/capabilities.md) | Capability keys and gating |
| [docs/security.md](docs/security.md) | Trust model, gated-action flow, secrets, logging |
| [docs/development.md](docs/development.md) | Dev setup, conventions, adding a capability, CI |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Live testing findings, known Outlook 16 quirks and fixes |

---

## License

[MIT](LICENSE)
