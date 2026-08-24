# Capabilities

Providers advertise dotted capability keys via `ProviderCapabilities`. Services check a
capability before dispatching and raise `CapabilityUnavailable` (HTTP 501) when it is not
supported — this keeps classic-vs-New-Outlook differences out of the MCP/REST schemas.

## Keys

| Key | Meaning | Slice |
|-----|---------|-------|
| `mail.read` | List/get messages | ✅ |
| `mail.search` | Search messages | ✅ |
| `mail.thread` | Reconstruct conversations | ✅ |
| `folders.read` | List folders | ✅ |
| `mail.attachments` | List/download attachments | later |
| `mail.draft` | Draft CRUD | later |
| `mail.reply` | Reply/reply-all/forward | later |
| `mail.send` | Send | later |
| `mail.move` / `mail.delete` | Organization | later |
| `folders.write` | Folder CRUD | later |
| `calendar.read` / `calendar.write` | Calendar | later |
| `contacts.read` / `tasks.read` / `notes.read` | PIM reads | later |

The AppleScript provider reports the read capabilities above only when `osascript` is
available (i.e. on macOS); otherwise it reports an empty set and diagnostics flag the
environment as unhealthy.
