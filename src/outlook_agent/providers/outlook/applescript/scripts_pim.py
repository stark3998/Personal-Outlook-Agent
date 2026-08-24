"""AppleScript builders for calendar, contacts, tasks, and notes (Milestone 8).

Read builders emit JSON arrays/objects; the single write builder (event create) is
invoked only via the ActionService. All require live-Mac verification.
"""

from __future__ import annotations

from .executor import quote
from .scripts import PRELUDE

_INT = "as integer"


def list_calendars_script() -> str:
    """List calendars as a JSON array."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    repeat with c in calendars
        set cId to ""
        set cName to ""
        try
            set cId to (id of c) as string
        end try
        try
            set cName to name of c
        end try
        set end of outItems to "{\"calendar_id\":\"" & my jsonEscape(cId) & "\",\"name\":\"" & my jsonEscape(cName) & "\"}"
    end repeat
    set AppleScript's text item delimiters to ","
    set b to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & b & "]"
end tell
"""
    )


def _event_object() -> str:
    return r"""
        set eId to ""
        set eSub to ""
        set eLoc to ""
        set eStart to ""
        set eEnd to ""
        try
            set eId to (id of e) as string
        end try
        try
            set eSub to subject of e
        end try
        try
            set eLoc to location of e
        end try
        try
            set eStart to my isoDate(start time of e)
        end try
        try
            set eEnd to my isoDate(end time of e)
        end try
        set j to "{\"event_id\":\"" & my jsonEscape(eId) & "\",\"subject\":\"" & my jsonEscape(eSub) & "\",\"location\":\"" & my jsonEscape(eLoc) & "\",\"start\":\"" & eStart & "\",\"end\":\"" & eEnd & "\"}"
"""


def list_events_script(limit: int) -> str:
    """List calendar events as a JSON array."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set maxN to """
        + str(limit)
        + r"""
    repeat with e in (calendar events of (item 1 of calendars))
        if (count of outItems) >= maxN then exit repeat
"""
        + _event_object()
        + r"""
        set end of outItems to j
    end repeat
    set AppleScript's text item delimiters to ","
    set b to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & b & "]"
end tell
"""
    )


def get_event_script(event_id: str) -> str:
    """Fetch a single event as a JSON object."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set e to calendar event id """
        + f"({quote(event_id)} {_INT})"
        + "\n"
        + _event_object()
        + r"""
    return j
end tell
"""
    )


def create_event_script(
    subject: str, start_iso: str, end_iso: str, location: str, body: str
) -> str:
    """Create a calendar event and return its id.

    Dates are passed as ISO strings and coerced via ``date`` in AppleScript.
    """
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set e to make new calendar event with properties {subject:"""
        + quote(subject)
        + ", start time:date "
        + quote(start_iso)
        + ", end time:date "
        + quote(end_iso)
        + ", location:"
        + quote(location)
        + ", content:"
        + quote(body)
        + r"""}
    return (id of e) as string
end tell
"""
    )


def delete_event_script(event_id: str) -> str:
    """Delete a calendar event."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set e to calendar event id """
        + f"({quote(event_id)} {_INT})"
        + r"""
    delete e
    return "deleted"
end tell
"""
    )


def _contact_object() -> str:
    return r"""
        set cId to ""
        set cName to ""
        set cEmail to ""
        set cCompany to ""
        try
            set cId to (id of c) as string
        end try
        try
            set cName to display name of c
        end try
        try
            set cEmail to address of (item 1 of email addresses of c)
        end try
        try
            set cCompany to company of c
        end try
        set j to "{\"contact_id\":\"" & my jsonEscape(cId) & "\",\"display_name\":\"" & my jsonEscape(cName) & "\",\"email\":\"" & my jsonEscape(cEmail) & "\",\"company\":\"" & my jsonEscape(cCompany) & "\"}"
"""


def list_contacts_script(limit: int, query: str | None) -> str:
    """List or search contacts as a JSON array."""
    if query is None:
        source = "contacts"
    else:
        source = f"(contacts whose display name contains {quote(query)})"
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set maxN to """
        + str(limit)
        + r"""
    repeat with c in """
        + source
        + r"""
        if (count of outItems) >= maxN then exit repeat
"""
        + _contact_object()
        + r"""
        set end of outItems to j
    end repeat
    set AppleScript's text item delimiters to ","
    set b to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & b & "]"
end tell
"""
    )


def get_contact_script(contact_id: str) -> str:
    """Fetch a single contact as a JSON object."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set c to contact id """
        + f"({quote(contact_id)} {_INT})"
        + "\n"
        + _contact_object()
        + r"""
    return j
end tell
"""
    )


def _task_object() -> str:
    return r"""
        set tId to ""
        set tSub to ""
        set tDone to false
        try
            set tId to (id of t) as string
        end try
        try
            set tSub to subject of t
        end try
        try
            set tDone to completed of t
        end try
        set j to "{\"task_id\":\"" & my jsonEscape(tId) & "\",\"subject\":\"" & my jsonEscape(tSub) & "\",\"completed\":" & my jbool(tDone) & "}"
"""


def list_tasks_script(limit: int, query: str | None) -> str:
    """List or search tasks as a JSON array."""
    source = "tasks" if query is None else f"(tasks whose subject contains {quote(query)})"
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set maxN to """
        + str(limit)
        + r"""
    repeat with t in """
        + source
        + r"""
        if (count of outItems) >= maxN then exit repeat
"""
        + _task_object()
        + r"""
        set end of outItems to j
    end repeat
    set AppleScript's text item delimiters to ","
    set b to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & b & "]"
end tell
"""
    )


def get_task_script(task_id: str) -> str:
    """Fetch a single task as a JSON object."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set t to task id """
        + f"({quote(task_id)} {_INT})"
        + "\n"
        + _task_object()
        + r"""
    return j
end tell
"""
    )


def _note_object() -> str:
    return r"""
        set nId to ""
        set nTitle to ""
        set nText to ""
        try
            set nId to (id of n) as string
        end try
        try
            set nTitle to subject of n
        end try
        try
            set nText to plain text content of n
        end try
        set j to "{\"note_id\":\"" & my jsonEscape(nId) & "\",\"title\":\"" & my jsonEscape(nTitle) & "\",\"body_text\":\"" & my jsonEscape(nText) & "\"}"
"""


def list_notes_script(limit: int, query: str | None) -> str:
    """List or search notes as a JSON array."""
    source = "notes" if query is None else f"(notes whose subject contains {quote(query)})"
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set maxN to """
        + str(limit)
        + r"""
    repeat with n in """
        + source
        + r"""
        if (count of outItems) >= maxN then exit repeat
"""
        + _note_object()
        + r"""
        set end of outItems to j
    end repeat
    set AppleScript's text item delimiters to ","
    set b to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & b & "]"
end tell
"""
    )


def get_note_script(note_id: str) -> str:
    """Fetch a single note as a JSON object."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set n to note id """
        + f"({quote(note_id)} {_INT})"
        + "\n"
        + _note_object()
        + r"""
    return j
end tell
"""
    )
