"""AppleScript source templates for read-only Outlook operations.

Each builder returns a self-contained AppleScript program that **emits JSON** on stdout.
Emitting JSON (rather than delimiter-joined text) keeps parsing robust against message
bodies that contain arbitrary characters.

The scripts target **classic** Outlook for Mac's AppleScript dictionary (field names and
object model adapted from hasan-imam/mcp-outlook-applescript). They must be verified
against a live install; New Outlook exposes a reduced dictionary and is handled by the
deferred UI provider.
"""

from __future__ import annotations

from .executor import quote

# Reusable AppleScript handlers: JSON string escaping and ISO-8601 date formatting.
PRELUDE = r"""
on jsonEscape(t)
    if t is missing value then return ""
    set t to t as string
    set AppleScript's text item delimiters to ""
    set out to ""
    repeat with c in characters of t
        set ch to c as string
        set n to ASCII number ch
        if ch is "\"" then
            set out to out & "\\\""
        else if ch is "\\" then
            set out to out & "\\\\"
        else if n is 10 then
            set out to out & "\\n"
        else if n is 13 then
            set out to out & "\\n"
        else if n is 9 then
            set out to out & "\\t"
        else if n is less than 32 then
            set out to out
        else
            set out to out & ch
        end if
    end repeat
    return out
end jsonEscape

on pad2(n)
    set s to (n as integer) as string
    if (count of s) < 2 then set s to "0" & s
    return s
end pad2

on isoDate(d)
    if d is missing value then return ""
    try
        set y to year of d
        set mo to (month of d as integer)
        set dd to day of d
        set hh to hours of d
        set mm to minutes of d
        set ss to seconds of d
        return (y as string) & "-" & my pad2(mo) & "-" & my pad2(dd) & "T" & my pad2(hh) & ":" & my pad2(mm) & ":" & my pad2(ss)
    on error
        return ""
    end try
end isoDate

on jbool(b)
    if b then
        return "true"
    else
        return "false"
    end if
end jbool
"""


def list_accounts_script() -> str:
    """List Exchange/IMAP/POP accounts as a JSON array."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set allAccounts to {}
    try
        set allAccounts to allAccounts & (exchange accounts)
    end try
    try
        set allAccounts to allAccounts & (imap accounts)
    end try
    try
        set allAccounts to allAccounts & (pop accounts)
    end try
    repeat with acc in allAccounts
        set accId to ""
        set accName to ""
        set accEmail to ""
        try
            set accId to (id of acc) as string
        end try
        try
            set accName to name of acc
        end try
        try
            set accEmail to email address of acc
        end try
        set j to "{\"account_id\":\"" & my jsonEscape(accId) & "\",\"name\":\"" & my jsonEscape(accName) & "\",\"email_address\":\"" & my jsonEscape(accEmail) & "\"}"
        set end of outItems to j
    end repeat
    set AppleScript's text item delimiters to ","
    set body to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & body & "]"
end tell
"""
    )


def list_folders_script(account_id: str | None) -> str:
    """List mail folders (optionally for one account) as a JSON array."""
    account_filter = ""
    if account_id is not None:
        account_filter = (
            f'    if (({quote(account_id)}) is not "") and '
            "((accId as string) is not (" + quote(account_id) + ")) then return\n"
        )
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    repeat with f in mail folders
        set fId to ""
        set fName to ""
        set fParent to ""
        set fSpecial to 0
        set fAccount to ""
        set fCount to 0
        set fUnread to 0
        try
            set fId to (id of f) as string
        end try
        try
            set fName to name of f
        end try
        try
            set fSpecial to (folder type of f) as integer
        end try
        try
            set fCount to (count of messages of f)
        end try
        try
            set fUnread to (unread count of f)
        end try
        try
            set fAccount to (id of (account of f)) as string
        end try
"""
        + account_filter
        + r"""
        set j to "{\"folder_id\":\"" & my jsonEscape(fId) & "\",\"name\":\"" & my jsonEscape(fName) & "\",\"account_id\":\"" & my jsonEscape(fAccount) & "\",\"parent_id\":\"" & my jsonEscape(fParent) & "\",\"special_type\":" & (fSpecial as string) & ",\"message_count\":" & (fCount as string) & ",\"unread_count\":" & (fUnread as string) & "}"
        set end of outItems to j
    end repeat
    set AppleScript's text item delimiters to ","
    set body to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & body & "]"
end tell
"""
    )


def _summary_object_builder() -> str:
    """AppleScript fragment building a JSON summary object from variable ``m``."""
    return r"""
        set mId to ""
        set mSubject to ""
        set mSender to ""
        set mSenderAddr to ""
        set mPreview to ""
        set mRead to false
        set mReceived to ""
        set mSent to ""
        set mHasAttach to false
        set mConv to ""
        set mFolder to ""
        try
            set mId to (id of m) as string
        end try
        try
            set mSubject to subject of m
        end try
        try
            set theSender to sender of m
            set mSender to name of theSender
            set mSenderAddr to address of theSender
        end try
        try
            set mPreview to (plain text content of m)
            if (count of mPreview) > 200 then set mPreview to (text 1 thru 200 of mPreview)
        end try
        try
            set mRead to is read of m
        end try
        try
            set mReceived to my isoDate(time received of m)
        end try
        try
            set mSent to my isoDate(time sent of m)
        end try
        try
            set mHasAttach to (count of attachments of m) > 0
        end try
        tell m
            try
                set mConv to conversation id as string
            end try
        end tell
        try
            set mFolder to (id of (folder of m)) as string
        end try
        set j to "{\"item_id\":\"" & my jsonEscape(mId) & "\",\"folder_id\":\"" & my jsonEscape(mFolder) & "\",\"conversation_id\":\"" & my jsonEscape(mConv) & "\",\"subject\":\"" & my jsonEscape(mSubject) & "\",\"sender_name\":\"" & my jsonEscape(mSender) & "\",\"sender_address\":\"" & my jsonEscape(mSenderAddr) & "\",\"preview\":\"" & my jsonEscape(mPreview) & "\",\"is_read\":" & my jbool(mRead) & ",\"received_at\":\"" & mReceived & "\",\"sent_at\":\"" & mSent & "\",\"has_attachments\":" & my jbool(mHasAttach) & "}"
"""


def list_emails_script(account_id: str, folder_id: str, *, limit: int, offset: int) -> str:
    """List message summaries in a folder as a JSON array (newest first)."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set theFolder to mail folder id """
        + f"({quote(folder_id)} as integer)"
        + r"""
    set msgs to messages of theFolder
    set total to count of msgs
    set startIdx to """
        + str(offset + 1)
        + r"""
    set endIdx to """
        + str(offset + limit)
        + r"""
    if endIdx > total then set endIdx to total
    if startIdx > total then set startIdx to total + 1
    repeat with i from startIdx to endIdx
        set m to item i of msgs
"""
        + _summary_object_builder()
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


def search_emails_script(
    query: str, *, account_id: str | None, folder_id: str | None, limit: int
) -> str:
    """Search messages by subject/sender/content as a JSON array."""
    if folder_id is not None:
        scope = "set searchFolders to {mail folder id (" + quote(folder_id) + " as integer)}"
    else:
        scope = "set searchFolders to mail folders"
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set q to """
        + quote(query)
        + r"""
    set maxN to """
        + str(limit)
        + r"""
    """
        + scope
        + r"""
    repeat with theFolder in searchFolders
        if (count of outItems) >= maxN then exit repeat
        try
            set msgs to (messages of theFolder whose subject contains q)
        on error
            set msgs to {}
        end try
        repeat with m in msgs
            if (count of outItems) >= maxN then exit repeat
"""
        + _summary_object_builder()
        + r"""
            set end of outItems to j
        end repeat
    end repeat
    set AppleScript's text item delimiters to ","
    set body to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & body & "]"
end tell
"""
    )


def get_email_script(folder_id: str, item_id: str) -> str:
    """Fetch a full message (body + recipients) as a JSON object."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set m to message id """
        + f"({quote(item_id)} as integer)"
        + r"""
    set mId to ""
    set mSubject to ""
    set mSender to ""
    set mSenderAddr to ""
    set mRead to false
    set mReceived to ""
    set mSent to ""
    set mHasAttach to false
    set mConv to ""
    set mFolder to ""
    set mText to ""
    set mHtml to ""
    set toList to {}
    set ccList to {}
    try
        set mId to (id of m) as string
    end try
    try
        set mSubject to subject of m
    end try
    try
        set theSender to sender of m
        set mSender to name of theSender
        set mSenderAddr to address of theSender
    end try
    try
        set mRead to is read of m
    end try
    try
        set mReceived to my isoDate(time received of m)
    end try
    try
        set mSent to my isoDate(time sent of m)
    end try
    try
        set mHasAttach to (count of attachments of m) > 0
    end try
    tell m
        try
            set mConv to conversation id as string
        end try
    end tell
    try
        set mFolder to (id of (folder of m)) as string
    end try
    try
        set mText to plain text content of m
    end try
    try
        set mHtml to content of m
    end try
    try
        repeat with r in (to recipients of m)
            set rn to ""
            set ra to ""
            try
                set rn to name of (email address of r)
            end try
            try
                set ra to address of (email address of r)
            end try
            set end of toList to "{\"name\":\"" & my jsonEscape(rn) & "\",\"address\":\"" & my jsonEscape(ra) & "\"}"
        end repeat
    end try
    try
        repeat with r in (cc recipients of m)
            set rn to ""
            set ra to ""
            try
                set rn to name of (email address of r)
            end try
            try
                set ra to address of (email address of r)
            end try
            set end of ccList to "{\"name\":\"" & my jsonEscape(rn) & "\",\"address\":\"" & my jsonEscape(ra) & "\"}"
        end repeat
    end try
    set AppleScript's text item delimiters to ","
    set toJson to toList as string
    set ccJson to ccList as string
    set AppleScript's text item delimiters to ""
    return "{\"item_id\":\"" & my jsonEscape(mId) & "\",\"folder_id\":\"" & my jsonEscape(mFolder) & "\",\"conversation_id\":\"" & my jsonEscape(mConv) & "\",\"subject\":\"" & my jsonEscape(mSubject) & "\",\"sender_name\":\"" & my jsonEscape(mSender) & "\",\"sender_address\":\"" & my jsonEscape(mSenderAddr) & "\",\"is_read\":" & my jbool(mRead) & ",\"received_at\":\"" & mReceived & "\",\"sent_at\":\"" & mSent & "\",\"has_attachments\":" & my jbool(mHasAttach) & ",\"body_text\":\"" & my jsonEscape(mText) & "\",\"body_html\":\"" & my jsonEscape(mHtml) & "\",\"to\":[" & toJson & "],\"cc\":[" & ccJson & "]}"
end tell
"""
    )


def list_conversation_script(conversation_id: str, *, limit: int = 100) -> str:
    """List summaries belonging to a conversation id as a JSON array."""
    return (
        PRELUDE
        + r"""
tell application "Microsoft Outlook"
    set outItems to {}
    set convId to """
        + f"({quote(conversation_id)} as integer)"
        + r"""
    set maxN to """
        + str(limit)
        + r"""
    repeat with theFolder in mail folders
        if (count of outItems) >= maxN then exit repeat
        try
            set msgs to (messages of theFolder whose conversation id is convId)
        on error
            set msgs to {}
        end try
        repeat with m in msgs
            if (count of outItems) >= maxN then exit repeat
"""
        + _summary_object_builder()
        + r"""
            set end of outItems to j
        end repeat
    end repeat
    set AppleScript's text item delimiters to ","
    set body to outItems as string
    set AppleScript's text item delimiters to ""
    return "[" & body & "]"
end tell
"""
    )
