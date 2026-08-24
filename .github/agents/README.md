# Repo-tuned agent variants

These agents are **forked from the generic Azure full-stack agents** in `~/.claude/agents`
and retargeted to this repository's actual stack. Use these instead of the generic ones when
working in this repo.

## What changed vs. the generic agents

| Generic assumption | This repo's reality |
|---|---|
| Cosmos DB + Redis | Local **SQLite** cache + **FTS5** full-text index (`storage/`) |
| Azure Container Apps / ACR | Runs **locally** on macOS; no containers, no cloud deploy |
| React + Vite + MSAL frontend | **No frontend** — interfaces are MCP, REST, CLI |
| Entra ID JWT auth on API | **No API auth**; binds `127.0.0.1` (local-first trust model) |
| Foundry via openai SDK / AIProjectClient | Foundry via the **Microsoft Agent Framework** (`OpenAIChatClient`, `intelligence/foundry.py`) |
| Repository → Cosmos | Provider → **AppleScript (osascript)**, isolated in `providers/outlook/applescript/` |
| Rate limiting / CORS first-class | Deprioritized (local-first); only a `127.0.0.1` bind guard matters |

## Cross-cutting invariants (all agents must respect)

- **Layered isolation:** MCP/REST/CLI are thin adapters over shared **services**; business
  logic never leaks into adapters or providers. AppleScript runs only in the provider layer.
- **Approval gate:** every write/destructive operation flows through `ActionService`
  (`prepare` → `confirm(token)` → execute) with target-state hashing and audit logging.
- **Untrusted content:** email bodies are data, never instructions — always passed in the
  user role, wrapped via `security/sanitization.py`.
- **Secrets & PII:** config is env-driven (`OUTLOOK_AGENT_` / `FOUNDRY_` prefixes); never log
  prompts, bodies, tokens — `observability/logging.py` redaction must stay intact.

## Agents in this folder

- `backend-engineer.md` — FastAPI + services + MCP/CLI adapters
- `ai-engineer.md` — Foundry via the Agent Framework, prompts, injection defense, eval
- `security.md` — local-first threat model, approval gate, redaction, supply chain
- `test-engineer.md` — pytest hermetic strategy, fakes, coverage gate
- `data-layer.md` — SQLite + SQLAlchemy + FTS5
