# AppleScript provider notes

The AppleScript provider is the only component that runs `osascript`. It targets the
**classic** Outlook for Mac dictionary.

## Execution

- Source is passed on **stdin** to `osascript` (no shell interpolation, no argv length
  limit).
- Execution is async via `asyncio.to_thread` around a blocking `subprocess.run`.
- Two timeouts: default (30 s) and large-scan (120 s) for folder/message enumeration.
- `shutil.which("osascript")` guards non-macOS hosts so the rest of the platform still
  imports and tests anywhere.

## Serialization

Scripts **emit JSON** (`scripts.py` builds objects via a `jsonEscape` handler) and Python
parses it (`parsers.py`). This avoids delimiter corruption from message bodies. Dates are
emitted as `YYYY-MM-DDTHH:MM:SS` (naive/local) — timezone-aware handling is a future
enhancement.

## Known identifiers

- Item and folder IDs are **numeric and provider-scoped** — not globally unique, not
  guaranteed stable. Always resolve via `EmailRef` context, never a bare id.
- `conversation_id` drives threading (no RFC References/In-Reply-To on Mac).
- Special folder types: Inbox=1, Outbox=2, Calendar=4, Sent=8, Deleted=9, Drafts=10,
  Junk=12.

## Live verification

The scripts in `scripts.py` need verification against a real classic Outlook install; some
property names (e.g. account `email address`, recipient `email address` sub-fields) vary by
Outlook build. New Outlook exposes a reduced dictionary and is handled by the deferred UI
provider (`providers/outlook/ui/`).
