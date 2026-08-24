# Troubleshooting

This document records issues found during live testing on macOS (Classic Outlook 16.112.1,
Exchange Online account) and the fixes applied. Each entry includes the symptom, root cause,
and what was changed.

---

## New Outlook for Mac not supported

**Symptom:** Diagnostics fail with "No Exchange accounts found" or message count is 0.
Running `defaults read com.microsoft.Outlook IsRunningNewOutlook` returns `1`.

**Root cause:** New Outlook uses a React Native/Electron engine and does not expose the
AppleScript dictionary that Classic Outlook provides. `exchange accounts`, message
enumeration, and folder properties are all absent.

**Fix:** The agent now detects New Outlook via the `IsRunningNewOutlook` defaults key. When
detected, diagnostics report `outlook_mode: FAIL` with a remediation message and all
Outlook operations are blocked.

**Resolution for users:** Choose **Help → Revert to Legacy Outlook** in Outlook, then
restart the agent. Grant Automation permission if prompted (System Settings → Privacy &
Security → Automation).

---

## Diagnostics: "message_access" fails even on Classic Outlook

**Symptom:** After switching to Classic Outlook, `outlook-agent diagnostics` still shows
`message_access: FAIL`.

**Root cause:** The Inbox detection logic used `folder type` comparison
(`special_type == SpecialFolderType.INBOX`). In Outlook 16, `folder type` returns a type
constant that cannot be compared as an integer, so it always evaluates as 0/unknown.

**Fix:** Added a name-based fallback — if no folder is found via `folder type`, look for a
folder named `"inbox"` (case-insensitive) that has a non-empty `account_id`. Applied in
`services/diagnostics.py`.

---

## AppleScript: `conversation id of m` — syntax error

**Symptom:** Scripts that read `conversation id` crash with
`Expected ',' but found class name`.

**Root cause:** `id` is a reserved AppleScript keyword. `(conversation id of m) as string`
is parsed as `(conversation [id]) of m`, where `id` is treated as a class name rather than
part of the property name.

**Fix:** Wrap in a `tell m` block so `id` resolves in the message's own namespace:

```applescript
tell m
    try
        set mConv to conversation id as string
    end try
end tell
```

Applied everywhere `conversation id` is read into a variable (both `scripts.py`
`_summary_object_builder()` and `get_email_script()`). Filter form (`whose conversation id
is X`) is unaffected and was left as-is.

---

## AppleScript: `has attachment of m` — syntax error

**Symptom:** Scripts that check `has attachment of m` produce an error similar to the
`conversation id` issue.

**Root cause:** Same class-name resolution conflict in Outlook 16.

**Fix:** Replace `(has attachment of m)` with `(count of attachments of m) > 0`. Applied
with `replace_all=True` across `scripts.py`.

---

## `folder type` comparison always returns false

**Symptom:** Special folder lookups (Drafts, Junk, Inbox) find nothing; draft listing
returns an empty list.

**Root cause:** In Outlook 16, `folder type of f` returns a type constant that cannot be
coerced to an integer. All `if (folder type of f) is N` comparisons silently fail.

**Fix (drafts):** Replaced `list_drafts_script` — instead of scanning mail folders for
`folder type = 10` (Drafts), iterate `outgoing messages` which is the correct AppleScript
collection for unsent messages:

```applescript
tell application "Microsoft Outlook"
    repeat with d in outgoing messages
        -- d is a draft (outgoing message)
    end repeat
end tell
```

**Fix (Inbox):** Name-based fallback described above.

**Remaining exposure:** `move_to_special_script` (used for junk mail routing) still uses
`folder type` comparison and may not find the target folder on Outlook 16. Workaround:
pass the folder ID explicitly via `move_message` instead of relying on special-folder
lookup.

---

## Foundry LLM: "Foundry is not configured"

**Symptom:** All intelligence endpoints return `503 llm_unavailable` even with `FOUNDRY_*`
vars set in `.env`.

**Root cause:** `pydantic-settings` only injects `.env` values for fields declared in the
`Settings` model. `FOUNDRY_*` vars were absent from `Settings`, so they were never loaded
into `os.environ` and `FoundryConfig`'s `os.getenv()` fallbacks always returned empty.

**Fix:** Added `foundry_endpoint`, `foundry_deployment`, `foundry_api_version`,
`foundry_api_key`, and `foundry_access_token` to `Settings` using `AliasChoices` so both
`FOUNDRY_ENDPOINT` and `OUTLOOK_AGENT_FOUNDRY_ENDPOINT` work:

```python
foundry_endpoint: str = Field(
    default="",
    validation_alias=AliasChoices("FOUNDRY_ENDPOINT", "OUTLOOK_AGENT_FOUNDRY_ENDPOINT"),
)
```

`build_container()` in `main.py` now passes these values explicitly to `FoundryConfig`.

---

## Foundry LLM: "API version not supported" (Responses API)

**Symptom:** Intelligence calls fail with `400 BadRequest: API version not supported` or
`model_not_found`.

**Root cause:** The Agent Framework SDK's `OpenAIChatClient` (v1.14.0) targets the newer
Responses API (`POST /openai/deployments/{model}/responses`). Some Azure OpenAI resources
(including `codex-jay-resource.openai.azure.com`) do not support this endpoint.

**Fix:** Replaced Agent Framework usage entirely with `openai.AsyncAzureOpenAI` calling
`chat.completions.create()` directly. The chat completions endpoint is universally available
on all Azure OpenAI resources.

```python
client = openai.AsyncAzureOpenAI(
    azure_endpoint=cfg.endpoint,
    api_key=cfg.api_key,
    api_version=cfg.api_version,
)
response = await client.chat.completions.create(
    model=cfg.deployment,
    messages=[...],
    temperature=0.2,
)
```

API version `2024-12-01-preview` is verified to work on the tested resource.

---

## Draft listing returns empty list

**Symptom:** `outlook-agent drafts` or `GET /drafts` returns `[]` even after creating a
reply draft.

**Root cause:** Reply drafts created via `reply to m` land in Outlook's "Temporary Items"
folder, not the typed Drafts folder. The old `list_drafts_script` searched mail folders for
`folder type = 10` which was both broken (see `folder type` issue above) and wrong for
Exchange-based reply drafts.

**Fix:** Rewrote `list_drafts_script` to iterate `outgoing messages` (the correct AppleScript
collection for unsent messages regardless of which folder they live in).

---

## Reply draft body text not appearing in the compose window

**Symptom:** Calling the draft-reply tool opens a compose window in Outlook, but the
AI-generated text is not visible in the window. The reply area appears blank or shows only
the quoted original message.

**Root cause:** `reply to m` creates a rich-text (HTML) compose window. Outlook renders the
HTML `content` property — not `plain text content` — in the compose area. Setting only
`plain text content` updates the internal text/plain part of the message but the visible
compose window still shows the HTML version, which was not updated.

**Fix:** Changed `reply_draft_script` to set `content` (HTML) instead of `plain text
content`. The AI body is injected as `<p>body</p><hr/>` prepended to the existing reply
HTML. Falls back to `plain text content` if the `content` property is unavailable.

---

## Reply draft not saved to Exchange Drafts folder

**Symptom:** After calling the draft-reply tool, the draft appears as an open compose
window in Outlook but is not visible in the Drafts folder in the sidebar.

**Root cause:** `reply to m` creates an outgoing message (compose window) in the
`outgoing messages` collection. This is separate from the Exchange Drafts mail folder
(folder ID 107 on Exchange Online). The agent was returning the outgoing message ID without
saving to Exchange Drafts.

**Fix:** After setting the body, `reply_draft_script` now does:
```applescript
move newMsg to draftFolder  -- draftFolder = Exchange Drafts folder found by name
```
The moved message gets a new ID (as a regular mail message in the Drafts folder). The script
finds that ID by matching subject, then returns it. The compose window remains open for the
user to review.

**Note:** `close`, `save`, and `delete` do not work on `outgoing message` objects in
Outlook 16 AppleScript — the compose window cannot be dismissed programmatically.

---

## `outlook-agent folders --account-id` returns empty list

**Symptom:** `outlook-agent folders --account-id 1` returns `[]` even though folders exist.

**Root cause:** The account filter in `list_folders_script` used `return` to skip
non-matching folders. In AppleScript, `return` exits the **entire program**, not just the
loop iteration — so the script exits immediately after the first folder is processed.

**Fix:** Rewrote the filter to use an `if/then/end-if` block wrapping the entire
object-building section, so non-matching iterations are properly skipped and the loop
continues.

---

## `list_drafts_script` only shows open compose windows, not saved Exchange drafts

**Symptom:** After a reply draft is saved to Exchange Drafts by `reply_draft_script`, it
doesn't appear in the output of `outlook-agent drafts`.

**Root cause:** `list_drafts_script` only iterated `outgoing messages` (open compose
windows). After the fix to `reply_draft_script` (which now moves drafts to the Exchange
Drafts folder), the correct source is the Exchange Drafts mail folder.

**Fix:** `list_drafts_script` now checks the Exchange Drafts folder first (using the same
name-based folder search), then appends any open compose windows from `outgoing messages`.

---

## General: verify Classic Outlook is running before testing

Run `outlook-agent diagnostics` before any live test. The structured output shows:

- `outlook_installed` — Outlook found
- `outlook_running` — Outlook process running
- `outlook_mode` — `classic` or fails with remediation if `new`
- `automation_permission` — osascript can talk to Outlook
- `exchange_accounts` — at least one Exchange account configured
- `message_access` — can enumerate messages in Inbox
