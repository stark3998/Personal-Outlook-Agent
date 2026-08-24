"""Domain models — pure Pydantic v2 types with no I/O."""

from __future__ import annotations

from .account import Account
from .action import (
    Action,
    ActionResult,
    ActionStatus,
    ActionType,
    ApprovalToken,
    RiskLevel,
)
from .attachment import Attachment
from .calendar import Calendar, CalendarEvent, CalendarEventInput, EventResponse
from .capabilities import Capability, ProviderCapabilities
from .contact import Contact
from .diagnostics import (
    DiagnosticCheck,
    DiagnosticReport,
    HealthStatus,
    OutlookInfo,
    Permissions,
)
from .draft import Draft, DraftBody, DraftInput
from .email import Email, EmailRef, EmailSummary
from .enums import FlagStatus, Priority, ProviderName, SpecialFolderType
from .folder import Folder
from .note import Note
from .recipient import Recipient, RecipientKind
from .task import Task
from .thread import Thread

__all__ = [
    "Account",
    "Action",
    "ActionResult",
    "ActionStatus",
    "ActionType",
    "ApprovalToken",
    "Attachment",
    "Calendar",
    "CalendarEvent",
    "CalendarEventInput",
    "Capability",
    "Contact",
    "DiagnosticCheck",
    "DiagnosticReport",
    "Draft",
    "DraftBody",
    "DraftInput",
    "Email",
    "EmailRef",
    "EmailSummary",
    "EventResponse",
    "FlagStatus",
    "Folder",
    "HealthStatus",
    "Note",
    "OutlookInfo",
    "Permissions",
    "Priority",
    "ProviderCapabilities",
    "ProviderName",
    "Recipient",
    "RecipientKind",
    "RiskLevel",
    "SpecialFolderType",
    "Task",
    "Thread",
]
