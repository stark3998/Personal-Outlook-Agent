# Configuration

All settings are environment-driven (12-factor). Copy `.env.example` to `.env`, fill in
your values, and never commit `.env` to source control.

## Loading

Settings are loaded by `pydantic-settings` (`config.py:Settings`). The `OUTLOOK_AGENT_`
prefix applies to all application settings. Foundry/Azure OpenAI vars use the `FOUNDRY_`
prefix (no `OUTLOOK_AGENT_` required, though the prefixed forms also work).

## Application settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `OUTLOOK_AGENT_PROVIDER` | `auto` | Outlook provider: `auto`, `applescript`, `com`, `ui` |
| `OUTLOOK_AGENT_APPLESCRIPT_TIMEOUT` | `30.0` | Seconds before an AppleScript call times out |
| `OUTLOOK_AGENT_APPLESCRIPT_LARGE_TIMEOUT` | `120.0` | Timeout for folder/message enumeration scans |
| `OUTLOOK_AGENT_APPROVAL_STORE` | `memory` | Where prepared actions are persisted: `memory` or `sqlite` |
| `OUTLOOK_AGENT_DATABASE_URL` | `sqlite:///outlook_agent.db` | SQLite database path (used when `approval_store=sqlite`) |
| `OUTLOOK_AGENT_API_HOST` | `127.0.0.1` | FastAPI listen address |
| `OUTLOOK_AGENT_API_PORT` | `8765` | FastAPI listen port |
| `OUTLOOK_AGENT_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `OUTLOOK_AGENT_LOG_JSON` | `true` | Emit structured JSON logs (`true`) or plain text (`false`) |

## Foundry / Azure OpenAI settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `FOUNDRY_ENDPOINT` | — | Azure OpenAI resource endpoint, e.g. `https://<name>.openai.azure.com` |
| `FOUNDRY_DEPLOYMENT` | — | Model deployment name (e.g. `gpt-4o`) |
| `FOUNDRY_API_VERSION` | `2024-10-21` | Azure OpenAI API version. `2024-12-01-preview` is verified to work. |
| `FOUNDRY_API_KEY` | — | API key auth. Takes precedence over access token. |
| `FOUNDRY_ACCESS_TOKEN` | — | Bearer token auth. Used when `FOUNDRY_API_KEY` is absent. |

Both `FOUNDRY_*` and `OUTLOOK_AGENT_FOUNDRY_*` forms are accepted. If neither key nor
token is provided, intelligence endpoints return `503 llm_unavailable` and non-AI features
continue to work normally.

## Example `.env`

```dotenv
# Outlook provider (leave as auto on most systems)
OUTLOOK_AGENT_PROVIDER=auto

# Persist action approvals across restarts
OUTLOOK_AGENT_APPROVAL_STORE=sqlite
OUTLOOK_AGENT_DATABASE_URL=sqlite:///outlook_agent.db

# REST API
OUTLOOK_AGENT_API_HOST=127.0.0.1
OUTLOOK_AGENT_API_PORT=8765

# Foundry / Azure OpenAI
FOUNDRY_ENDPOINT=https://your-resource.openai.azure.com
FOUNDRY_DEPLOYMENT=gpt-4o
FOUNDRY_API_VERSION=2024-12-01-preview
FOUNDRY_API_KEY=your-api-key-here
```

## Secrets management

- `.env` is git-ignored. `.env.example` documents the knobs without values.
- On macOS, store secrets in the Keychain and export them to the shell before launching the
  agent (e.g. via a `launchd` plist with `EnvironmentVariables`).
- Structured logs never contain credentials, email bodies, or attachment contents.
- The action approval system stores tokens in SQLite (when configured) — the database file
  is local-only and not transmitted anywhere.
