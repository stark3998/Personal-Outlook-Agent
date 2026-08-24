# AppleScript provider

The AppleScript provider is the only component that runs `osascript`. It targets the
**Classic** Outlook for Mac dictionary (Outlook 16.x). This document covers how it works,
what was found during live testing, and known Outlook 16 compatibility quirks.

## Requirements

- **Classic Outlook** (not New Outlook). See [New Outlook detection](#new-outlook-detection).
- **Automation permission**: System Settings → Privacy & Security → Automation →
  check the box next to Microsoft Outlook for the terminal/app running the agent.

## Execution model

- Source is passed on **stdin** to `osascript` — no shell interpolation, no argv length limit.
- Execution is async via `asyncio.to_thread` wrapping a blocking `subprocess.run`.
- Two timeouts: 30 s (default) and 120 s (large scan — folder/message enumeration).
- `shutil.which("osascript")` guards non-macOS hosts so the rest of the platform still
  imports and runs tests on any OS.
- Failures are classified as `not_running`, `permission_denied`, `timeout`, or `unknown`.

## Serialization

Scripts **emit JSON** (built with a `jsonEscape` handler in `scripts.py`); Python parses
the output in `parsers.py`. This avoids delimiter corruption from message bodies. Dates are
emitted as `YYYY-MM-DDTHH:MM:SS` (local time, no timezone offset) — timezone-aware handling
is a future enhancement.

## Identity model

- Item and folder IDs are **numeric and provider-scoped** — not globally unique, not
  guaranteed stable across sessions.
- `conversation_id` drives threading (no RFC References/In-Reply-To on Mac).
- Exchange Online accounts use high folder IDs (e.g. 108 = Inbox, 107 = Drafts, 111 = Sent
  Items); local "On My Computer" folders use IDs 1–12.

## New Outlook detection

New Outlook for Mac uses a React Native/Electron engine and **does not expose the
AppleScript dictionary** that Classic Outlook provides. If New Outlook is running, the
agent will detect it and block all Outlook operations.

Detection reads the macOS defaults key written by Outlook itself:

```bash
defaults read com.microsoft.Outlook IsRunningNewOutlook
# 1 = New Outlook active, key absent or 0 = Classic Outlook
```

This is checked in `executor.py:is_new_outlook()` and surfaces in `probe_outlook()` as
`mode = "new"` or `mode = "classic"`. The diagnostics service treats `mode = "new"` as a
critical failure with a remediation message.

**Remediation:** In Outlook, choose **Help → Revert to Legacy Outlook** (macOS). After
switching, restart the agent.

## Outlook 16 compatibility issues (found during live testing)

The following issues were discovered and fixed when running against Classic Outlook 16.112.1
with an Exchange Online account. See also [troubleshooting.md](troubleshooting.md).

### 1. `conversation id` — reserved keyword conflict

`id` is a reserved AppleScript keyword. Using `conversation id of m` at the top level of a
script causes a parser error:

```applescript
-- FAILS: "Expected ',' but found class name"
set mConv to (conversation id of m) as string
```

**Fix:** wrap in a `tell m` block so AppleScript resolves `id` in the message's own
namespace:

```applescript
tell m
    try
        set mConv to conversation id as string
    end try
end tell
```

Note: `whose conversation id is X` (the filter form) works fine at top level — the conflict
only arises when reading the property into a variable.

### 2. `has attachment` — class name conflict

`has attachment of m` also triggers a class-name conflict in Outlook 16:

```applescript
-- FAILS in Outlook 16
set mHasAttach to (has attachment of m)
```

**Fix:** count the attachments collection instead:

```applescript
set mHasAttach to (count of attachments of m) > 0
```

### 3. `folder type` — cannot be coerced to integer

In Outlook 16, `folder type` returns an AppleScript type constant that cannot be compared
as an integer. The following pattern always returns `false`:

```applescript
-- Does NOT work in Outlook 16 (always false)
if (folder type of f) is 10 then ...
-- Also fails:
if (folder type of f as integer) is 10 then ...
```

**Impact:** any code that uses `folder type` comparisons to locate special folders
(Drafts = 10, Junk = 12, etc.) silently finds nothing.

**Workaround used for Inbox detection:** fall back to name matching —
`f.name.lower() == "inbox"` — when the `folder type`-based lookup returns nothing.

**Workaround used for drafts:** use the `outgoing messages` collection instead of searching
for a folder with `folder type = 10`:

```applescript
tell application "Microsoft Outlook"
    repeat with d in outgoing messages
        -- each d is an unsent draft
    end repeat
end tell
```

### 4. Exchange folder IDs differ from local IDs

Classic Outlook's special folder type constants (Inbox=1, Drafts=10, etc.) are for
"On My Computer" local folders. Exchange Online account folders have different numeric IDs
(observed: Inbox=108, Drafts=107, Sent Items=111). Do not hardcode folder IDs.

## Script structure

| File | Contents |
|------|----------|
| `executor.py` | `AppleScriptExecutor` — runs scripts, classifies errors, detects New Outlook |
| `scripts.py` | Read-only scripts: list accounts/folders/emails, search, get email, threads |
| `scripts_write.py` | Write scripts: create/send/delete draft, reply, forward, move, organize |
| `scripts_pim.py` | PIM scripts: calendar events, contacts, tasks, notes |
| `parsers.py` | JSON output → domain model parsing |
| `provider.py` | `OutlookAppleScriptProvider` — implements `OutlookProvider` protocol |

## Known limitations

- `folder type` comparison broken in Outlook 16 — affects `move_to_special_script` (junk
  mail routing) and any special-folder lookup beyond Inbox.
- Dates have no timezone info — all times are local to the Mac running the agent.
- Attachment download is not yet implemented (`mail.attachments` capability is advertised
  but the download path is a stub).
- `conversation id` filtering (`whose conversation id is X`) works; reading the property
  into a variable requires the `tell m` block workaround.
