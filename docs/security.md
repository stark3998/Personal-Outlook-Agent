# Security

## Trust boundaries

| Trusted | Untrusted |
|---------|-----------|
| User instructions | Email bodies |
| Application policy | Attachments |
| System configuration | Links, signatures, quoted replies |
| | External web content |

Instructions found **inside** an email are never treated as agent instructions. Untrusted
content is never injected into system/developer prompts and can never directly trigger a
tool. The agent may reason over email content, but every write/destructive operation must
still pass through policy and the `ActionService` (Milestone 6).

## Secrets

- No secrets in source, Git, committed `.env`, or logs.
- Use macOS Keychain for local secrets; `.env.example` documents configuration only.
- Foundry credentials are read from the environment at runtime (Milestone 9).

## AppleScript safety

- Scripts are passed to `osascript` on **stdin**; we never build shell command strings.
- All interpolated values pass through a single escaping helper (`escape` / `quote`).
- The executor classifies failures (`not_running`, `permission_denied`, `timeout`,
  `not_available`, `unknown`) so callers can surface actionable errors instead of leaking
  raw output.

## Logging & observability

- Structured logs with correlation IDs (per request/operation).
- Never logged: email bodies, credentials, OAuth tokens, attachment contents, secrets.
- Audit events (Milestone 6) record operation, target, approval, result, and timestamps.

## Destructive operations

All write/destructive operations (send, reply, move, delete, archive, junk, calendar
writes, folder deletes) are gated by the `ActionService` prepare → confirm flow with a
target-state hash to reject stale actions. The LLM cannot bypass the `ActionService`.
