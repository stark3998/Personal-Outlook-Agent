# Architecture — personal-outlook-agent

Local-first Outlook automation platform for macOS. The MCP server is **one interface** to the
platform, not the platform itself. All interfaces (MCP, REST, CLI) call the **same application
services**; business logic lives in the service/domain layers, never in the interface or provider
layers.

## Layered overview

```
CLIENTS  (Claude Desktop · VS Code MCP · Claude Code · CLI · future web app)
   │  MCP (stdio) / REST (HTTP) / CLI
   ▼
INTERFACE LAYER            src/outlook_agent/{mcp,api,cli}
   │  thin adapters — no business logic, no AppleScript
   ▼
APPLICATION SERVICES       src/outlook_agent/services
   │  MailService · ThreadService · DiagnosticsService · (Draft/Action/Calendar/… later)
   ▼
DOMAIN + POLICY            src/outlook_agent/{domain,security}
   │  Pydantic models · capabilities · approvals · audit · sanitization
   ▼
PROVIDER INTERFACES        src/outlook_agent/providers/base.py
   │  OutlookProvider Protocol (provider-agnostic)
   ▼
OUTLOOK PROVIDERS          src/outlook_agent/providers/outlook/{applescript,ui}
   │  AppleScript primary · UI scripting fallback
   ▼
MICROSOFT OUTLOOK (macOS)
```

### Non-negotiable boundaries

1. MCP tools and REST routes **must not** execute AppleScript. They call services only.
2. AppleScript is confined to `providers/outlook/applescript/`.
3. Application services depend on the `OutlookProvider` **interface**, never a concrete provider.
4. The LLM (`FoundryLLMProvider`) sits behind an `LLMProvider` interface in `intelligence/`.
   The Outlook provider **never** imports the intelligence layer.
5. Every write/destructive operation flows through `ActionService` (prepare → confirm).
6. Email content is **untrusted**; it is data to reason over, never instructions to execute.

## Request flow — read-only vertical slice

```
VS Code / Claude Desktop ──stdio──► FastMCP tool
                                        │
curl / browser ──HTTP──► FastAPI route ─┤
                                        │
outlook-agent CLI ──────────────────────┤
                                        ▼
                              MailService / ThreadService / DiagnosticsService
                                        ▼
                              OutlookProvider (interface)
                                        ▼
                              OutlookAppleScriptProvider
                                        ▼
                              AppleScriptExecutor  ──►  osascript  ──►  Microsoft Outlook
```

The three interfaces are **peers**; none is privileged. The web app (future) is just another
client of the same services and REST API — it does not need to understand MCP.

## Module map

| Path | Responsibility |
|------|----------------|
| `outlook_agent/config.py` | Pydantic-settings configuration (env-driven, 12-factor). |
| `outlook_agent/main.py` | Composition root / DI wiring; builds providers + services. |
| `outlook_agent/domain/` | Pure Pydantic v2 models + capability + diagnostics types. No I/O. |
| `outlook_agent/providers/base.py` | `OutlookProvider` Protocol + capability contract. |
| `outlook_agent/providers/outlook/applescript/` | `executor.py`, `scripts.py`, `parsers.py`, `provider.py`. Only place `osascript` runs (macOS). |
| `outlook_agent/providers/outlook/com/` | `executor.py`, `provider.py`. Only place `win32com` runs (Windows classic Outlook). |
| `outlook_agent/providers/outlook/ui/` | Deferred New-Outlook UI fallback. |
| `outlook_agent/providers/outlook/factory.py` | Selects/combines providers, aggregates capabilities. |
| `outlook_agent/services/` | Application services; provider-agnostic orchestration. |
| `outlook_agent/security/` | Policy, approvals, audit, sanitization, secrets (Keychain). |
| `outlook_agent/intelligence/` | `LLMProvider` + `FoundryLLMProvider` + prompt tasks (deferred). |
| `outlook_agent/storage/` | SQLite cache/index + FTS (deferred; Outlook stays source of truth). |
| `outlook_agent/api/` | FastAPI app, dependencies, thin routers. |
| `outlook_agent/mcp/` | FastMCP server, stable tool schemas, thin tools. |
| `outlook_agent/cli/` | Typer CLI over the same services; JSON-first output. |

## Domain identity model

Outlook item and folder IDs are **numeric and not globally unique** — they are scoped to a
mailbox and can change. Every addressable object therefore carries enough context to be resolved
unambiguously:

```
EmailRef = (provider, account_id, folder_id, item_id)
         + stable hints: message_id, conversation_id
```

We never assume a bare `item_id` identifies a message across accounts or over time. `message_id`
(RFC 5322) is preserved when available for cross-provider correlation.

## Provider abstraction & capabilities

`OutlookProvider` is a `typing.Protocol`. Providers advertise a `ProviderCapabilities` set using
dotted keys (`mail.read`, `mail.search`, `mail.thread`, `calendar.read`, …). Services check
capabilities before calling and surface `CapabilityUnavailable` rather than crashing — this is how
we cope with classic vs New Outlook differences without leaking provider internals into tool
schemas.

## AppleScript strategy (from upstream research)

- Scripts are passed to `osascript` on **stdin** (no shell interpolation, no arg-length limit).
- All interpolated values are escaped (`\`, `"`, newlines) via a single `escape` helper.
- Scripts **emit JSON** where practical so parsing is robust against body text; delimiter parsing
  is avoided.
- The executor classifies failures (`not_running`, `permission_denied`, `timeout`, `unknown`) and
  guards for non-macOS via `shutil.which("osascript")`.
- Batch multiple reads into a single `osascript` call instead of one process per message.

## Security model

- **Trusted:** user instructions, application policy, system configuration.
- **Untrusted:** email bodies, attachments, links, signatures, quoted replies, external web.
- Untrusted content is never injected into system/developer prompts and can never directly trigger
  a tool. Write/destructive operations always pass through policy + `ActionService`.
- Secrets live in macOS Keychain / env, never in source, Git, or logs. `.env.example` only.
- Structured logs carry correlation IDs but **never** bodies, credentials, tokens, or attachment
  contents.

## Intelligence isolation (Foundry)

`LLMProvider` exposes `summarize / classify / extract / generate_reply`. `FoundryLLMProvider`
implements it against Microsoft Foundry (`FOUNDRY_ENDPOINT`, `FOUNDRY_DEPLOYMENT`,
`FOUNDRY_API_VERSION`). Intelligence services (`summarization`,
`reply_generation`, `extraction`) consume domain models produced by the Outlook services — the
Outlook provider has zero knowledge of Foundry.

## Milestone roadmap (implementation order)

| M | Scope | Status |
|---|-------|--------|
| 0 | Upstream research matrix + this document | ✅ |
| 1 | Skeleton, `pyproject.toml` (uv), config, domain models, provider interfaces | ✅ (this change) |
| 2 | AppleScript executor + diagnostics | ✅ (this change) |
| 3 | list accounts/folders/emails, search, get email, get thread (read-only) | ✅ (this change) |
| 4 | FastMCP + FastAPI + CLI wiring over shared services | ✅ (this change) |
| 5 | Drafts, reply, reply-all, forward | ✅ |
| 6 | ActionService, approvals, audit | ✅ |
| 7 | Send, organization, folder management | ✅ |
| 8 | Calendar, contacts, tasks, notes | ✅ |
| 9 | Microsoft Foundry, summarization, extraction, reply generation | ✅ |
| 10 | Composite agent tools | ✅ |
| 11 | SQLite cache + FTS5 | ✅ |
| 12 | Sync engine | ✅ |
| 13 | New Outlook UI provider | 🧩 placeholder |
| 14 | Enhanced diagnostics, packaging, launchd, web-app support | ✅ |

Everything AppleScript-backed (Milestones 5, 7, 8, 12) is implemented but **requires
live-Mac verification**; the write/PIM AppleScript in `scripts_write.py` / `scripts_pim.py`
and the corresponding provider methods have been exercised only against the in-memory fake
provider. The New Outlook UI provider (Milestone 13) is an isolated placeholder that
advertises no capabilities.
