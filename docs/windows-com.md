# Windows COM provider

`OutlookCOMProvider` drives **classic** Outlook for Windows through the COM Object Model
via `pywin32`. It is the only package that touches `win32com`, mirroring the isolation of
the AppleScript provider.

## Execution

- All COM work runs on a worker thread that calls `pythoncom.CoInitialize()` for that
  thread (respecting COM apartment threading), so the async services never block.
- `win32com`/`pythoncom` are imported lazily and guarded, so the rest of the platform
  imports and tests on any OS.
- Failures are classified into actionable categories: `not_available` (pywin32 missing or
  not Windows), `not_installed` (Outlook COM server not registered), `not_running`,
  `permission_denied`, `unknown`.

## Identity mapping

| Domain field | COM value |
|--------------|-----------|
| `account_id` | Store `StoreID` (a mailbox/store is the account unit) |
| `folder_id` | `MAPIFolder.EntryID` |
| `item_id` | item `EntryID` |
| `conversation_id` | `MailItem.ConversationID` |
| `message_id` | Internet Message-ID via `PropertyAccessor` (PR_INTERNET_MESSAGE_ID) |

Items are resolved with `namespace.GetItemFromID(item_id, account_id)` and folders with
`namespace.GetFolderFromID(folder_id, account_id)`. Ids are not globally unique — always
carry the surrounding context.

## Coverage

The provider implements the full surface: mail reads, drafts (create/get/list/update/
delete), reply/forward, send, organization (read/flag/categories/move/delete/junk), folder
management, calendar (list/get/create/update/delete/RSVP), and contacts/tasks/notes.

## Known limitations

- **Archive** — Outlook for Windows has no universal COM "archive" verb; the provider
  moves the item to a folder named "Archive" if one exists, else raises.
- Default-folder detection uses `GetDefaultFolder`, so special-folder typing is precise for
  the default store; secondary stores may report `UNKNOWN` special types.
- New Outlook exposes a reduced/unavailable COM surface — use classic Outlook, or the
  (deferred) UI provider.

## Verifying on a Windows machine

```powershell
setx OUTLOOK_AGENT_PROVIDER com   # or leave as auto
outlook-agent diagnostics         # confirms installed/running/permissions + access checks
outlook-agent accounts
outlook-agent folders --account-id <StoreID>
outlook-agent search "Entra" --limit 5
```

If diagnostics reports `not_installed`, classic Outlook is not registered as a COM server
on that machine (e.g. only New Outlook is present).
