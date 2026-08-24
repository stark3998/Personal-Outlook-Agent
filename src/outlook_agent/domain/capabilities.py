"""Provider capability system.

Providers advertise dotted capability keys (e.g. ``mail.read``). Services check
capabilities before dispatching so that differences between classic and New Outlook
never leak into interface (MCP/REST) schemas.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Capability(StrEnum):
    """Known capability keys."""

    MAIL_READ = "mail.read"
    MAIL_SEARCH = "mail.search"
    MAIL_THREAD = "mail.thread"
    MAIL_ATTACHMENTS = "mail.attachments"
    MAIL_DRAFT = "mail.draft"
    MAIL_REPLY = "mail.reply"
    MAIL_SEND = "mail.send"
    MAIL_ORGANIZE = "mail.organize"
    MAIL_MOVE = "mail.move"
    MAIL_DELETE = "mail.delete"
    FOLDERS_READ = "folders.read"
    FOLDERS_WRITE = "folders.write"
    CALENDAR_READ = "calendar.read"
    CALENDAR_WRITE = "calendar.write"
    CONTACTS_READ = "contacts.read"
    TASKS_READ = "tasks.read"
    NOTES_READ = "notes.read"


class ProviderCapabilities(BaseModel):
    """The set of capabilities a provider currently supports."""

    supported: frozenset[Capability] = Field(default_factory=frozenset)

    def has(self, capability: Capability) -> bool:
        """Return whether the given capability is supported."""
        return capability in self.supported

    def as_map(self) -> dict[str, bool]:
        """Return a stable ``{capability: bool}`` map over all known capabilities."""
        return {cap.value: cap in self.supported for cap in Capability}
