"""Enumerations mirroring Outlook for Mac's internal numeric representations.

Values are sourced from the classic Outlook AppleScript dictionary (see
docs/research/UPSTREAM_MATRIX.md).
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class SpecialFolderType(IntEnum):
    """Outlook's built-in special folder identifiers."""

    UNKNOWN = 0
    INBOX = 1
    OUTBOX = 2
    CALENDAR = 4
    SENT = 8
    DELETED = 9
    DRAFTS = 10
    JUNK = 12


class Priority(IntEnum):
    """Message priority levels."""

    HIGH = 1
    NORMAL = 3
    LOW = 5


class FlagStatus(IntEnum):
    """Follow-up flag state."""

    NONE = 0
    FLAGGED = 1
    COMPLETED = 2


class ProviderName(StrEnum):
    """Identifies which provider produced a domain object."""

    OUTLOOK_APPLESCRIPT = "outlook.applescript"
    OUTLOOK_UI = "outlook.ui"
