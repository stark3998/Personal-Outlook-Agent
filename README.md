# Personal Outlook Agent

A **local-first Outlook automation platform** for macOS and Windows. It exposes your
desktop Outlook (mail, threads, drafts, calendar, contacts, tasks, notes) and an AI agent
layer through **three equal interfaces** — an **MCP server**, a **REST API**, and a
**CLI** — all sharing the exact same application services.

The MCP server is *one interface to the platform*, not the platform itself. Business logic
lives in provider-agnostic services; Outlook access is isolated behind a provider
abstraction (AppleScript on macOS, COM on Windows); and the LLM (Microsoft Foundry) sits
behind its own `LLMProvider` interface, never coupled to Outlook.

> **Status:** Milestones 0–14 implemented plus composite agent tools, persistent
> approvals, structured logging, and a Windows COM provider. Quality gates are green:
> **125 tests, 89% coverage, `mypy --strict` clean, `ruff` clean.** AppleScript/COM
> providers are code-complete and unit-covered via fakes; they require a live classic
> Outlook install for end-to-end verification.

---

## Table of contents

- [Highlights](#highlights)
- [Architecture](#architecture)
- [Connectors & providers](#connectors--providers)
- [Installation & setup](#installation--setup)
- [Configuration](#configuration)
- [Running the interfaces](#running-the-interfaces)
- [MCP integration](#mcp-integration)
- [Feature catalog](#feature-catalog)
- [The approval (gated-action) flow](#the-approval-gated-action-flow)
- [AI intelligence (Microsoft Foundry)](#ai-intelligence-microsoft-foundry)
- [Local cache, search & sync](#local-cache-search--sync)
- [Security model](#security-model)
- [Observability](#observability)
- [Testing, quality & CI](#testing-quality--ci)
- [Project layout](#project-layout)
- [Documentation index](#documentation-index)
- [Roadmap](#roadmap)
- [License](#license)

---

## Highlights

- **Cross-platform desktop Outlook** — classic Outlook for **macOS** (AppleScript) or
  **Windows** (COM), auto-selected by platform behind one interface.
- **Three interfaces, one brain** — FastMCP, FastAPI, and a Typer CLI all call the same
  services. No business logic or Outlook calls live in the interface layer.
- **Safe by construction** — every write/destructive operation (send, delete, move, junk,
  folder delete/empty, calendar writes) flows through a centralized **ActionService**
  with a two-step *prepare → confirm* handshake, approval tokens, target-state hashing to
  reject stale actions, and an audit trail.
- **AI agent layer** — summaries, action-item extraction, reply proposals (never
  auto-sent), inbox digests, unanswered/follow-up detection, promised-action detection,
  and meeting prep — powered by Microsoft Foundry behind an `LLMProvider` interface.
- **Prompt-injection aware** — email bodies, attachments, and signatures are treated as
  untrusted data and can never become agent instructions or trigger tools.
- **Local index** — SQLite cache with **FTS5** full-text search and on-demand /
  incremental sync. Outlook remains the source of truth.
- **Production hygiene** — Pydantic v2 domain models, structured logging with correlation
  IDs and secret redaction, `mypy --strict`, `ruff`, 89% test coverage, GitHub Actions CI.

---

## Architecture

```
CLIENTS        Claude Desktop · VS Code · Claude Code · curl/browser · future web app
                 │  MCP (stdio)        │  REST (HTTP)        │  CLI
                 ▼                     ▼                     ▼
INTERFACE      FastMCP tools       FastAPI routers       Typer commands   ← thin adapters
                 └───────────────────────┬───────────────────────┘         (no business logic,
                                         ▼                                   no Outlook calls)
SERVICES       Mail · Thread · Draft · Folder · Calendar · Contact · Task · Note ·
               Action · Intelligence · Sync · Diagnostics
                                         ▼
DOMAIN+POLICY  Pydantic models · capability system · approvals · audit · sanitization
                                         ▼
PROVIDER API   OutlookProvider (Protocol)               LLMProvider (Protocol)
                                         ▼                        ▼
PROVIDERS      AppleScript (macOS) · COM (Windows) ·     FoundryLLMProvider
               UI-scripting (placeholder)
                                         ▼
               Microsoft Outlook (desktop)              Microsoft Foundry
```

**Non-negotiable boundaries**

1. MCP tools and REST routes never execute AppleScript/COM — they call services only.
2. Outlook access is confined to the provider packages.
3. Services depend on the `OutlookProvider` **interface**, never a concrete provider.
4. The Outlook providers never import the intelligence layer; the LLM stays behind
   `LLMProvider`.
5. Every write/destructive op passes through `ActionService`.
6. Email content is untrusted data — never instructions.

See [docs/architecture.md](docs/architecture.md) for the full design and
[docs/research/UPSTREAM_MATRIX.md](docs/research/UPSTREAM_MATRIX.md) for the upstream
research that informed it.

---

## Connectors & providers

The platform connects to three kinds of external systems, each isolated behind an
interface so the core stays portable.

| Connector | Interface | Implementation | Platform | Docs |
|-----------|-----------|----------------|----------|------|
| **Outlook (macOS)** | `OutlookProvider` | `OutlookAppleScriptProvider` (via `osascript`) | macOS + classic Outlook | [docs/apple-script.md](docs/apple-script.md) |
| **Outlook (Windows)** | `OutlookProvider` | `OutlookCOMProvider` (via `win32com`) | Windows + classic Outlook | [docs/windows-com.md](docs/windows-com.md) |
| **New Outlook (UI)** | `OutlookProvider` | `OutlookUIScriptingProvider` *(placeholder)* | macOS/Windows New Outlook | — |
| **LLM** | `LLMProvider` | `FoundryLLMProvider` (Microsoft Foundry, OpenAI-compatible chat) | any | [docs/connectors.md](docs/connectors.md) |
| **MCP clients** | MCP (stdio) | FastMCP server | Claude Desktop / VS Code / Claude Code | [docs/mcp.md](docs/mcp.md) |

Provider selection is controlled by `OUTLOOK_AGENT_PROVIDER` (`auto` → COM on Windows,
AppleScript on macOS; or force `com` / `applescript`).

---

## Installation & setup

**Requirements**

- Python **3.13+** and [uv](https://docs.astral.sh/uv/).
- For live Outlook access: **classic** Microsoft Outlook installed and launched once.
  - macOS: grant **Automation** permission (System Settings → Privacy & Security → Automation).
  - Windows: `pywin32` (installed automatically) and Outlook registered as a COM server.

> The codebase and its test suite run on **any OS**; live Outlook access requires the
> matching platform.

### macOS

```bash
bash scripts/setup_mac.sh          # installs uv (if needed), creates .venv, editable install
source .venv/bin/activate
outlook-agent diagnostics          # structured health report (JSON)
```

### Windows / any OS (manual)

```powershell
uv venv --python 3.13
uv pip install -e ".[dev]"
.venv\Scripts\activate
outlook-agent diagnostics
```

`diagnostics` reports installation, running state, permissions, provider capabilities, and
live access checks — with actionable remediation for anything that fails.

---

## Configuration

Configuration is environment-driven (12-factor). Copy `.env.example` to `.env` (git-ignored)
and adjust. All app settings use the `OUTLOOK_AGENT_` prefix.

| Variable | Default | Purpose |
|----------|---------|---------|
| `OUTLOOK_AGENT_PROVIDER` | `auto` | `auto` / `applescript` / `com` / `ui` |
| `OUTLOOK_AGENT_APPLESCRIPT_TIMEOUT` | `30` | Per-call osascript timeout (s) |
| `OUTLOOK_AGENT_APPLESCRIPT_LARGE_TIMEOUT` | `120` | Large-scan timeout (s) |
| `OUTLOOK_AGENT_APPROVAL_STORE` | `memory` | `memory` or `sqlite` (share gated actions across CLI/API + survive restarts) |
| `OUTLOOK_AGENT_DATABASE_URL` | `sqlite:///outlook_agent.db` | Cache / approval store DB |
| `OUTLOOK_AGENT_API_HOST` / `_PORT` | `127.0.0.1` / `8765` | REST bind address |
| `OUTLOOK_AGENT_LOG_LEVEL` / `_LOG_JSON` | `INFO` / `true` | Structured logging |
| `OUTLOOK_LIVE_TESTS` | `false` | Opt-in, read-only live Outlook tests |

**Microsoft Foundry** (LLM) — do **not** commit real values:

| Variable | Purpose |
|----------|---------|
| `FOUNDRY_ENDPOINT` | Foundry resource endpoint |
| `FOUNDRY_DEPLOYMENT` | Model deployment name |
| `FOUNDRY_API_VERSION` | API version (default `2024-10-21`) |
| `FOUNDRY_AUTH_MODE` | `default` |
| `FOUNDRY_API_KEY` *or* `FOUNDRY_ACCESS_TOKEN` | Credential (key or bearer token) |

Secrets belong in the macOS Keychain or environment — never in source, Git, or logs.

---

## Running the interfaces

```bash
outlook-agent-api      # FastAPI (uvicorn) on http://127.0.0.1:8765  — OpenAPI at /docs
outlook-agent-mcp      # FastMCP server over stdio (for MCP clients)
outlook-agent ...      # CLI (JSON-first output)
```

All three build the same `Container` (composition root in `main.py`) and call the same
services. See [docs/api.md](docs/api.md), [docs/mcp.md](docs/mcp.md), and
[docs/cli.md](docs/cli.md) for full references.

---

## MCP integration

The MCP server runs locally over **stdio** — no Microsoft connectors or cloud auth
required. Read tools are safe to auto-allow; write/gated tools should always prompt.

- **VS Code:** copy [configs/vscode.mcp.json.example](configs/vscode.mcp.json.example) to
  `.vscode/mcp.json`.
- **Claude Desktop:** merge [configs/claude_desktop.json.example](configs/claude_desktop.json.example)
  into `claude_desktop_config.json`.
- **Claude Code:** `bash scripts/install_claude_mcp.sh` (runs `claude mcp add`).

### MCP tool catalog (28 tools)

| Category | Tools |
|----------|-------|
| **Diagnostics** | `outlook_diagnostics` |
| **Read** | `outlook_list_accounts`, `outlook_list_folders`, `outlook_list_emails`, `outlook_search_emails`, `outlook_get_email`, `outlook_get_thread` |
| **Drafts** | `outlook_list_drafts`, `outlook_create_draft`, `outlook_reply` |
| **Gated writes** | `outlook_prepare_send`, `outlook_prepare_delete`, `outlook_prepare_move` |
| **Direct organize** | `outlook_mark_read` |
| **Approvals** | `outlook_pending_actions`, `outlook_confirm_action`, `outlook_cancel_action` |
| **PIM** | `outlook_list_events`, `outlook_list_contacts`, `outlook_list_tasks` |
| **Agent** | `agent_summarize_email`, `agent_summarize_inbox`, `agent_extract_action_items`, `agent_prepare_reply`, `agent_find_unanswered`, `agent_find_followups`, `agent_find_promised_actions`, `agent_meeting_prep` |

Example prompt to an MCP client: *"Search my Outlook for emails about Entra, open the most
recent one, and draft a reply confirming attendance — don't send it."*

---

## Feature catalog

| Area | Capabilities |
|------|--------------|
| **Mail read** | List accounts/folders, list & paginate messages, search, full message (body text + HTML), attachments metadata |
| **Threads** | Conversation reconstruction from `conversation_id` + subject normalization + participants + ordering |
| **Drafts** | Create / read / list / update / delete; reply / reply-all / forward (as drafts — never auto-send) |
| **Send** | Gated send of a draft (approval required) |
| **Organization** | Mark read/unread, flag/clear flag, set categories (direct); move / archive / delete / junk (gated) |
| **Folders** | List; create / rename (direct); move / delete / empty (gated) |
| **Calendar** | List calendars & events, get event; create / update / delete / RSVP (gated) |
| **Contacts / Tasks / Notes** | List / search / get |
| **Agent intelligence** | Summarize email/thread/inbox, extract action items, find unanswered & follow-ups, detect promised actions, meeting prep, propose replies |
| **Platform** | Structured diagnostics, capability detection, provider auto-selection |

Which operations are available at runtime is governed by the **capability system** — see
[docs/capabilities.md](docs/capabilities.md). Services check a capability before dispatch
and return `CapabilityUnavailable` (HTTP 501) rather than failing opaquely, so
classic-vs-New-Outlook differences never leak into tool schemas.

---

## The approval (gated-action) flow

Destructive and outbound operations are never executed directly. They follow a
**prepare → confirm** handshake enforced by the `ActionService`:

```
prepare_*  ──▶  ApprovalToken { action_id, token, risk_level, summary, expires_at }
                │
confirm(action_id, token)
   1. validate action id + token (constant-time)
   2. check expiry (risk-scaled TTL)
   3. re-read target, compare state hash  → reject if changed (stale)
   4. execute via the bound provider
   5. record audit event
```

- Risk levels: `SEND`/`REPLY`=HIGH, `DELETE`/`FOLDER_EMPTY`=CRITICAL, etc. — CRITICAL
  actions have the shortest confirmation window.
- The LLM can only *propose* actions; it can never confirm one.
- Approval + audit state is in-memory by default, or **persistent SQLite**
  (`OUTLOOK_AGENT_APPROVAL_STORE=sqlite`) so the CLI and API share the same pending
  actions and they survive restarts.

REST: `GET /api/v1/actions/pending`, `POST /api/v1/actions/{id}/confirm`,
`POST /api/v1/actions/{id}/cancel`. CLI: `pending`, `confirm`, `cancel`.

---

## AI intelligence (Microsoft Foundry)

The `IntelligenceService` composes the LLM with Outlook services to provide agent tools.
The LLM is reached only through the `LLMProvider` interface; `FoundryLLMProvider` calls the
OpenAI-compatible chat-completions surface of a Foundry deployment.

- **Never auto-sends** — reply generation returns an explicit `ProposedReply` (and
  optionally a saved draft).
- **Untrusted content** is wrapped with sanitization delimiters and passed only in the
  user role; injection phrasing is flagged.
- Configuration via `FOUNDRY_*` env vars (see above). See
  [docs/connectors.md](docs/connectors.md).

Agent capabilities: `summarize_email`, `summarize_thread`, `summarize_inbox`,
`extract_action_items`, `find_unanswered`, `find_followups`, `find_promised_actions`,
`meeting_prep`, `prepare_reply`.

---

## Local cache, search & sync

- **SQLite cache + FTS5** index over subject/sender/body for fast local search. Outlook
  remains the source of truth; the cache is rebuildable.
- **On-demand sync** (`outlook-agent sync ...`) and **incremental sync**
  (`--incremental`, optional `--detect-deletions`) that only re-caches messages newer than
  the last run and prunes deletions.
- Background sync via a **launchd** agent — see
  [configs/launchd.sync.plist.example](configs/launchd.sync.plist.example).

---

## Security model

| Trusted | Untrusted |
|---------|-----------|
| User instructions, app policy, system config | Email bodies, attachments, links, signatures, quoted replies, external web |

- Instructions inside an email are **never** treated as agent instructions and can never
  directly trigger a tool.
- Secrets live in the macOS Keychain / environment — never in source, Git, or logs.
- Structured logs carry correlation IDs but never bodies, credentials, tokens, or
  attachment contents (enforced by a redaction processor).
- All destructive operations are gated (see above). Full details in
  [docs/security.md](docs/security.md).

---

## Observability

- **structlog**-based structured logging with per-request **correlation IDs**
  (`x-correlation-id` header) and automatic **secret redaction**.
- The `ActionService` emits `action_prepared` / `action_confirmed` events.
- An append-only **audit log** (in-memory or SQLite) records operation, target, approval,
  result, and timestamps — metadata only.

---

## Testing, quality & CI

```bash
uv pip install -e ".[dev]"
pytest                                   # hermetic unit + integration (no Outlook needed)
pytest --cov=outlook_agent               # with the 80% coverage gate
ruff check . && ruff format --check .    # lint + format
mypy src                                 # strict typing
```

- **125 tests / 89% coverage**, `mypy --strict` clean, `ruff` clean.
- Live Outlook tests are **opt-in** (`OUTLOOK_LIVE_TESTS=true`) and **read-only** —
  automated tests never send or delete mail.
- GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs ruff (lint +
  format), `mypy --strict`, pytest with coverage, and a `pip-audit` dependency scan.
- Live-only provider modules (AppleScript/COM executors + providers) are excluded from the
  coverage gate and verified on-device.

---

## Project layout

```
src/outlook_agent/
  main.py            composition root (Container) + API entry point
  config.py          env-driven settings
  domain/            Pydantic models, enums, capabilities, diagnostics, actions
  providers/
    base.py          OutlookProvider protocol + capability errors
    outlook/
      applescript/   executor, scripts, parsers, provider  (macOS, osascript-isolated)
      com/           executor, provider                     (Windows, win32com-isolated)
      ui/            New Outlook UI fallback (placeholder)
      factory.py     platform-based provider selection
  services/          Mail · Thread · Draft · Folder · Calendar · Contact/Task/Note ·
                     Action · Intelligence · Sync · Diagnostics · handlers
  intelligence/      LLMProvider · FoundryLLMProvider · prompts
  security/          policy · approvals · audit · sanitization
  storage/           SQLite database · models · FTS5 · repositories · sync helpers
  observability/     structured logging (correlation IDs, redaction)
  api/               FastAPI app, dependencies, thin routers
  mcp/               FastMCP server, thin tools
  cli/               Typer CLI (JSON-first)
tests/               unit · integration · eval (opt-in)
docs/                architecture, security, capabilities, apple-script, windows-com,
                     api, mcp, cli, connectors, development, research/
configs/             Claude Desktop / VS Code MCP examples, launchd plist
scripts/             setup_mac.sh, doctor.sh, install_claude_mcp.sh
```

---

## Documentation index

| Doc | Contents |
|-----|----------|
| [docs/architecture.md](docs/architecture.md) | Layered design, boundaries, identity model, roadmap |
| [docs/api.md](docs/api.md) | Full REST endpoint reference |
| [docs/mcp.md](docs/mcp.md) | MCP tool catalog + client setup |
| [docs/cli.md](docs/cli.md) | CLI command reference |
| [docs/connectors.md](docs/connectors.md) | Microsoft Foundry LLM connector + provider connectors |
| [docs/capabilities.md](docs/capabilities.md) | Capability keys and gating |
| [docs/apple-script.md](docs/apple-script.md) | macOS AppleScript provider notes |
| [docs/windows-com.md](docs/windows-com.md) | Windows COM provider notes |
| [docs/security.md](docs/security.md) | Trust model, approvals, redaction |
| [docs/development.md](docs/development.md) | Setup, conventions, adding a capability |
| [docs/research/UPSTREAM_MATRIX.md](docs/research/UPSTREAM_MATRIX.md) | Upstream research & decisions |

---

## Roadmap

Implemented: read path, drafts/reply/forward, gated send/organize/folder/calendar writes,
contacts/tasks/notes, ActionService (approvals + audit), Microsoft Foundry intelligence +
composite agent tools, SQLite cache + FTS5, on-demand & incremental sync, Windows COM
provider, structured logging, persistent approvals.

Remaining: live verification against real classic Outlook (macOS + Windows), a full New
Outlook UI provider, and an optional web UI (the backend is already web-ready).

---

## License

MIT — see [LICENSE](LICENSE).
