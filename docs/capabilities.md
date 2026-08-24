# Capabilities

Providers advertise dotted capability keys via `ProviderCapabilities`. Services check a
capability before dispatching and raise `CapabilityUnavailable` (HTTP 501) when it is not
supported — this keeps classic-vs-New-Outlook differences out of the MCP/REST schemas.

## Keys

| Key | Meaning | AppleScript (macOS) | COM (Windows) |
|-----|---------|---------------------|---------------|
| `mail.read` | List/get messages | ✅ live-verified | ✅ |
| `mail.search` | Search messages | ✅ live-verified | ✅ |
| `mail.thread` | Reconstruct conversations | ✅ live-verified | ✅ |
| `folders.read` | List folders | ✅ live-verified | ✅ |
| `mail.attachments` | List/download attachments | ✅ implemented | ✅ |
| `mail.draft` | Draft CRUD | ✅ live-verified | ✅ |
| `mail.reply` | Reply/reply-all/forward | ✅ live-verified | ✅ |
| `mail.send` | Send (gated) | ✅ live-verified | ✅ |
| `mail.move` / `mail.delete` | Organization | ✅ implemented | ✅ |
| `folders.write` | Folder CRUD | ✅ implemented | ✅ |
| `calendar.read` / `calendar.write` | Calendar | ✅ implemented | ✅ |
| `contacts.read` | Contacts | ✅ implemented | ✅ |
| `tasks.read` | Tasks | ✅ implemented | ✅ |
| `notes.read` | Notes | ✅ implemented | ✅ |

**live-verified** = exercised against a real Exchange Online account (Classic Outlook
16.112.1, macOS). Includes fixes discovered and applied during testing — see
[troubleshooting.md](troubleshooting.md) for the full list of issues and fixes.

**implemented** = AppleScript written and unit-tested; not explicitly exercised in the live
session but follows the same patterns as verified operations.

The AppleScript provider reports the full capability set only when `osascript` is
available (macOS) **and** Classic Outlook is running. If New Outlook is detected, the
provider reports an empty set and diagnostics flag the environment as unsupported. See
[apple-script.md](apple-script.md) for New Outlook detection details.
