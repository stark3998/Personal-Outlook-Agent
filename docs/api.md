# REST API reference

The FastAPI app is served by `outlook-agent-api` (uvicorn) on
`http://127.0.0.1:8765` by default. Interactive OpenAPI docs are at `/docs`.

All routes are thin: they resolve request context and delegate to the shared application
services. Responses are Pydantic models serialized to JSON.

## Conventions

- Message identity requires context: `account_id`, `folder_id`, and `item_id` (Outlook ids
  are numeric and provider-scoped, not globally unique).
- Every request/response carries an `x-correlation-id` header (generated if absent).
- Gated operations return an **`ApprovalToken`**; execution happens via
  `POST /api/v1/actions/{id}/confirm`.

## Error responses

| Status | Meaning |
|--------|---------|
| `501` | `capability_unavailable` — the active provider does not support the operation |
| `503` | Outlook not available / not running (`not_available`, `not_installed`, `not_running`) |
| `502` | Provider execution error (AppleScript/COM) |
| `403` | Invalid approval token |
| `404` | Unknown action id |
| `409` | Action already resolved |
| `410` | Action expired or stale (target changed) |

## Health & diagnostics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/api/v1/diagnostics` | Structured diagnostic report (install/running/permissions/capabilities/access checks) |

## Mail (read)

| Method | Path | Query |
|--------|------|-------|
| GET | `/api/v1/accounts` | — |
| GET | `/api/v1/folders` | `account_id?` |
| GET | `/api/v1/mail` | `account_id`, `folder_id`, `limit?`, `offset?` |
| GET | `/api/v1/mail/search` | `q`, `account_id?`, `folder_id?`, `limit?` |
| GET | `/api/v1/mail/{item_id}` | `account_id`, `folder_id`, `conversation_id?` |
| GET | `/api/v1/threads/{conversation_id}` | `account_id?` |

## Drafts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/drafts` | `account_id`, `limit?` |
| POST | `/api/v1/drafts` | body `DraftInput`; `account_id` query |
| GET | `/api/v1/drafts/{draft_id}` | `account_id` |
| POST | `/api/v1/drafts/reply` | `account_id`, `folder_id`, `item_id`, `reply_all?`, `body?` — creates a reply draft |
| POST | `/api/v1/drafts/{draft_id}/send` | Returns an `ApprovalToken` (gated) |

## Actions (approval flow)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/actions/pending` | List actions awaiting confirmation |
| POST | `/api/v1/actions/{action_id}/confirm` | body `{ token, authorized_by? }` → executes |
| POST | `/api/v1/actions/{action_id}/cancel` | 204 on success |

## Calendar

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/calendar/calendars` | `account_id?` |
| GET | `/api/v1/calendar/events` | `account_id`, `limit?` |
| GET | `/api/v1/calendar/events/{event_id}` | `account_id` |
| POST | `/api/v1/calendar/events` | body `CalendarEventInput` → `ApprovalToken` (gated) |

## Contacts / Tasks / Notes

| Method | Path | Query |
|--------|------|-------|
| GET | `/api/v1/contacts` | `account_id`, `q?`, `limit?` |
| GET | `/api/v1/tasks` | `account_id`, `q?`, `limit?` |
| GET | `/api/v1/notes` | `account_id`, `q?`, `limit?` |

## Agent intelligence

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/agent/summarize/email` | `account_id`, `folder_id`, `item_id` |
| GET | `/api/v1/agent/summarize/thread` | `conversation_id`, `account_id?` |
| GET | `/api/v1/agent/summarize/inbox` | `account_id`, `folder_id`, `limit?` |
| GET | `/api/v1/agent/action-items` | `account_id`, `folder_id`, `item_id` |
| GET | `/api/v1/agent/unanswered` | `account_id`, `folder_id`, `limit?` |
| GET | `/api/v1/agent/followups` | `account_id`, `sent_folder_id`, `limit?` |
| GET | `/api/v1/agent/promised-actions` | `account_id`, `sent_folder_id`, `limit?` |
| GET | `/api/v1/agent/meeting-prep` | `account_id`, `event_id` |
| POST | `/api/v1/agent/prepare-reply` | body `{ account_id, folder_id, item_id, instructions, create_draft? }` — returns a proposal, never sends |

## Example: gated send

```bash
# 1. create a draft
curl -X POST 'http://127.0.0.1:8765/api/v1/drafts?account_id=1' \
  -H 'content-type: application/json' \
  -d '{"subject":"Hi","body":{"text":"Hello"},"to":[{"address":"a@example.com"}]}'

# 2. prepare a gated send  → returns { action_id, token, ... }
curl -X POST 'http://127.0.0.1:8765/api/v1/drafts/<DRAFT_ID>/send?account_id=1'

# 3. confirm to actually send
curl -X POST 'http://127.0.0.1:8765/api/v1/actions/<ACTION_ID>/confirm' \
  -H 'content-type: application/json' -d '{"token":"<TOKEN>"}'
```
