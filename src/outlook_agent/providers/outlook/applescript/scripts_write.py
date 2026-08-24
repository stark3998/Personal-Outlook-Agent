"""AppleScript builders for write and organization operations (Milestones 5 & 7).

All destructive/outbound operations here are invoked *only* via the ActionService.
These scripts target classic Outlook for Mac and **require live verification**; some verbs
(reply/forward) vary across Outlook builds.
"""

from __future__ import annotations

from .executor import quote
from .scripts import PRELUDE

_INT = "as integer"


def _recipient_lines(kind: str, addresses: list[str]) -> str:
    """Build ``make new recipient`` lines for a draft (kind: to/cc/bcc)."""
    verb = {"to": "to recipient", "cc": "cc recipient", "bcc": "bcc recipient"}[kind]
    lines: list[str] = []
    for addr in addresses:
        lines.append(
            f"        make new {verb} at newMsg with properties "
            f"{{email address:{{address:{quote(addr)}}}}}"
        )
    return "\n".join(lines)


def create_draft_script(
    subject: str,
    body: str,
    *,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    html: bool = False,
) -> str:
    """Create an outgoing message (draft) and return its id."""
    content_prop = "content" if html else "plain text content"
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set newMsg to make new outgoing message with properties {subject:"""
        + quote(subject)
        + ", "
        + content_prop
        + ":"
        + quote(body)
        + r"""}
"""
        + _recipient_lines("to", to)
        + "\n"
        + _recipient_lines("cc", cc)
        + "\n"
        + _recipient_lines("bcc", bcc)
        + r"""
    return (id of newMsg) as string
end tell
"""
    )


def send_draft_script(draft_id: str) -> str:
    """Send an existing outgoing message by id."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(draft_id)} {_INT})"
        + r"""
    send m
    return "sent"
end tell
"""
    )


def delete_message_script(item_id: str) -> str:
    """Move a message to Deleted Items (Outlook's ``delete`` verb)."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    delete m
    return "deleted"
end tell
"""
    )


def move_message_script(item_id: str, target_folder_id: str) -> str:
    """Move a message into another folder."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    set f to mail folder id """
        + f"({quote(target_folder_id)} {_INT})"
        + r"""
    move m to f
    return "moved"
end tell
"""
    )


def set_read_script(item_id: str, read: bool) -> str:
    """Mark a message read/unread."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    set is read of m to """
        + ("true" if read else "false")
        + r"""
    return "ok"
end tell
"""
    )


def set_flag_script(item_id: str, flagged: bool) -> str:
    """Set or clear the follow-up flag (FlagStatus 1 = flagged, 0 = none)."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    set todo flag of m to """
        + ("1" if flagged else "0")
        + r"""
    return "ok"
end tell
"""
    )


def set_categories_script(item_id: str, categories: list[str]) -> str:
    """Replace the categories on a message by name."""
    cat_refs = ", ".join(f"category {quote(c)}" for c in categories) or ""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    set category of m to {"""
        + cat_refs
        + r"""}
    return "ok"
end tell
"""
    )


def create_folder_script(name: str, parent_id: str | None) -> str:
    """Create a mail folder, optionally under a parent folder id."""
    if parent_id is None:
        make = f"make new mail folder with properties {{name:{quote(name)}}}"
    else:
        make = (
            f"make new mail folder at (mail folder id ({quote(parent_id)} {_INT})) "
            f"with properties {{name:{quote(name)}}}"
        )
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set f to """
        + make
        + r"""
    return (id of f) as string
end tell
"""
    )


def rename_folder_script(folder_id: str, name: str) -> str:
    """Rename a mail folder."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set f to mail folder id """
        + f"({quote(folder_id)} {_INT})"
        + r"""
    set name of f to """
        + quote(name)
        + r"""
    return (id of f) as string
end tell
"""
    )


def delete_folder_script(folder_id: str) -> str:
    """Delete a mail folder."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set f to mail folder id """
        + f"({quote(folder_id)} {_INT})"
        + r"""
    delete f
    return "deleted"
end tell
"""
    )


def empty_folder_script(folder_id: str) -> str:
    """Delete every message in a folder."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set f to mail folder id """
        + f"({quote(folder_id)} {_INT})"
        + r"""
    repeat with m in (messages of f)
        delete m
    end repeat
    return "emptied"
end tell
"""
    )


def _draft_object() -> str:
    """AppleScript fragment serializing outgoing message ``d`` to a JSON draft object."""
    return r"""
        set dId to ""
        set dSubject to ""
        set dText to ""
        try
            set dId to (id of d) as string
        end try
        try
            set dSubject to subject of d
        end try
        try
            set dText to plain text content of d
        end try
        set j to "{\"draft_id\":\"" & my jsonEscape(dId) & "\",\"subject\":\"" & my jsonEscape(dSubject) & "\",\"body_text\":\"" & my jsonEscape(dText) & "\"}"
"""


def get_draft_script(draft_id: str) -> str:
    """Fetch a single draft as a JSON object."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set d to message id """
        + f"({quote(draft_id)} {_INT})"
        + "\n"
        + _draft_object()
        + r"""
    return j
end tell
"""
    )


def list_drafts_script(limit: int) -> str:
    """List drafts as a JSON array.

    Checks the Exchange Drafts folder first (where ``reply_draft_script`` saves drafts),
    then falls back to ``outgoing messages`` (open compose windows).
    """
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set maxN to """
        + str(limit)
        + "\n"
        + _find_exchange_drafts_folder()
        + r"""
    -- Exchange Drafts folder (server-side drafts saved by reply_draft_script)
    if draftFolder is not missing value then
        set dc to count of draftFolder
        repeat with i from dc to 1 by -1
            if (count of outItems) >= maxN then exit repeat
            set d to message i of draftFolder
"""
        + _draft_object()
        + r"""
            set end of outItems to j
        end repeat
    end if
    -- Also include open compose windows (outgoing messages not yet saved)
    repeat with d in outgoing messages
        if (count of outItems) >= maxN then exit repeat
"""
        + _draft_object()
        + r"""
        set end of outItems to j
    end repeat
    set AppleScript's text item delimiters to ","
    set body to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & body & "]"
end tell
"""
    )


def update_draft_script(draft_id: str, subject: str | None, body: str | None) -> str:
    """Update subject and/or plain-text content of a draft."""
    sets = ""
    if subject is not None:
        sets += f"    set subject of d to {quote(subject)}\n"
    if body is not None:
        sets += f"    set plain text content of d to {quote(body)}\n"
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set d to message id """
        + f"({quote(draft_id)} {_INT})"
        + "\n"
        + sets
        + r"""    return (id of d) as string
end tell
"""
    )


def _find_exchange_drafts_folder() -> str:
    """AppleScript fragment that sets ``draftFolder`` to the Exchange Drafts folder."""
    return r"""
    set draftFolder to missing value
    repeat with f in mail folders
        set fn to ""
        try
            set fn to name of f
        end try
        if fn is "Drafts" then
            set hasAcct to false
            try
                set unused to id of (account of f)
                set hasAcct to true
            end try
            if hasAcct then
                set draftFolder to f
                exit repeat
            end if
        end if
    end repeat
"""


def reply_draft_script(item_id: str, reply_all: bool, body: str) -> str:
    """Create a reply (or reply-all) draft and save it to the Exchange Drafts folder.

    Uses ``content`` (HTML property) to inject the body because Outlook compose windows
    render HTML — setting ``plain text content`` alone does not update the visible area.
    After setting the body the draft is moved to the Exchange Drafts mail folder so it
    appears in Outlook's Drafts sidebar. The compose window remains open for review.
    """
    opts = " with reply to all" if reply_all else ""
    body_html = f"<p>{body}</p><hr/>"
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    set newMsg to reply to m"""
        + opts
        + r"""
    -- Inject AI text into HTML body (compose window renders HTML, not plain text)
    try
        set existHtml to content of newMsg
        set content of newMsg to """
        + quote(body_html)
        + r""" & existHtml
    on error
        -- Fall back to plain text if HTML property unavailable
        try
            set plain text content of newMsg to """
        + quote(body)
        + r""" & return & (plain text content of newMsg)
        end try
    end try
    -- Move to Exchange Drafts folder so it appears in Outlook's Drafts sidebar
    set replySubj to subject of newMsg
"""
        + _find_exchange_drafts_folder()
        + r"""
    if draftFolder is not missing value then
        move newMsg to draftFolder
        -- Find the saved draft by subject (most recent matching item)
        set dc to count of draftFolder
        repeat with i from dc to 1 by -1
            set d to message i of draftFolder
            set ds to ""
            try
                set ds to subject of d
            end try
            if ds is replySubj then
                return (id of d) as string
            end if
        end repeat
    end if
    -- Fall back: return the outgoing message id if the move failed
    return (id of newMsg) as string
end tell
"""
    )


def forward_draft_script(item_id: str, to: list[str], body: str) -> str:
    """Create a forward draft for a message and return its id."""
    rcpts = "\n".join(
        "    make new to recipient at newMsg with properties "
        f"{{email address:{{address:{quote(a)}}}}}"
        for a in to
    )
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    set newMsg to forward m
    try
        set plain text content of newMsg to """
        + quote(body)
        + r""" & (plain text content of newMsg)
    end try
"""
        + rcpts
        + r"""
    return (id of newMsg) as string
end tell
"""
    )


def move_to_special_script(item_id: str, folder_type: int) -> str:
    """Move a message to a special folder by numeric folder type (e.g. Junk=12)."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} {_INT})"
        + r"""
    set target to missing value
    repeat with f in mail folders
        try
            if (folder type of f) is """
        + str(folder_type)
        + r""" then
                set target to f
                exit repeat
            end if
        end try
    end repeat
    if target is missing value then error "special folder not found"
    move m to target
    return "ok"
end tell
"""
    )
