"""Provider interfaces — the boundary application services depend on.

Services must depend only on :class:`OutlookProvider`; they must never know whether the
concrete provider uses AppleScript, UI scripting, IMAP, or anything else.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from outlook_agent.domain import (
    Account,
    Calendar,
    CalendarEvent,
    CalendarEventInput,
    Capability,
    Contact,
    Draft,
    DraftInput,
    Email,
    EmailRef,
    EmailSummary,
    EventResponse,
    Folder,
    Note,
    OutlookInfo,
    Permissions,
    ProviderCapabilities,
    Task,
)


class ProviderError(Exception):
    """Base class for provider-layer failures."""


class CapabilityUnavailable(ProviderError):
    """Raised when a requested capability is not supported by the active provider."""

    def __init__(self, capability: Capability) -> None:
        super().__init__(f"Capability not available: {capability.value}")
        self.capability = capability


@runtime_checkable
class OutlookProvider(Protocol):
    """Provider-agnostic contract for Outlook access.

    The read-only vertical slice requires the members below. Write/destructive
    operations are added in later milestones and always flow through the ActionService.
    """

    def capabilities(self) -> ProviderCapabilities:
        """Return the capabilities this provider currently supports."""
        ...

    async def probe_outlook(self) -> OutlookInfo:
        """Detect Outlook install/running state and version."""
        ...

    async def probe_permissions(self) -> Permissions:
        """Detect macOS automation/accessibility permissions."""
        ...

    async def list_accounts(self) -> list[Account]:
        """List configured Outlook accounts."""
        ...

    async def list_folders(self, account_id: str | None = None) -> list[Folder]:
        """List folders, optionally scoped to a single account."""
        ...

    async def list_emails(
        self,
        account_id: str,
        folder_id: str,
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> list[EmailSummary]:
        """List message summaries in a folder (newest first)."""
        ...

    async def search_emails(
        self,
        query: str,
        *,
        account_id: str | None = None,
        folder_id: str | None = None,
        limit: int = 25,
    ) -> list[EmailSummary]:
        """Search messages by subject/sender/content."""
        ...

    async def get_email(self, ref: EmailRef) -> Email:
        """Fetch a full message including body and recipients."""
        ...

    async def list_conversation(
        self, conversation_id: str, *, account_id: str | None = None
    ) -> list[EmailSummary]:
        """List message summaries belonging to a conversation."""
        ...

    # --- Drafts & composition (Milestone 5) ---------------------------------------

    async def create_draft(self, account_id: str, data: DraftInput) -> Draft:
        """Create a new draft and return it."""
        ...

    async def get_draft(self, account_id: str, draft_id: str) -> Draft:
        """Fetch a draft by id."""
        ...

    async def list_drafts(self, account_id: str, *, limit: int = 25) -> list[Draft]:
        """List saved drafts."""
        ...

    async def update_draft(self, account_id: str, draft_id: str, data: DraftInput) -> Draft:
        """Update an existing draft."""
        ...

    async def delete_draft(self, account_id: str, draft_id: str) -> None:
        """Delete a draft."""
        ...

    async def create_reply_draft(
        self, ref: EmailRef, *, reply_all: bool = False, body: str | None = None
    ) -> Draft:
        """Create a reply (or reply-all) draft for a message."""
        ...

    async def create_forward_draft(
        self, ref: EmailRef, *, to: list[str], body: str | None = None
    ) -> Draft:
        """Create a forward draft for a message."""
        ...

    async def send_draft(self, account_id: str, draft_id: str) -> None:
        """Send an existing draft."""
        ...

    # --- Organization (Milestone 7) ------------------------------------------------

    async def set_read(self, ref: EmailRef, *, read: bool) -> None:
        """Mark a message read or unread."""
        ...

    async def set_flag(self, ref: EmailRef, *, flagged: bool) -> None:
        """Set or clear the follow-up flag on a message."""
        ...

    async def set_categories(self, ref: EmailRef, categories: list[str]) -> None:
        """Replace the categories on a message."""
        ...

    async def move_email(self, ref: EmailRef, *, target_folder_id: str) -> None:
        """Move a message to another folder."""
        ...

    async def archive_email(self, ref: EmailRef) -> None:
        """Archive a message."""
        ...

    async def delete_email(self, ref: EmailRef) -> None:
        """Delete a message (to Deleted Items)."""
        ...

    async def junk_email(self, ref: EmailRef) -> None:
        """Move a message to Junk."""
        ...

    # --- Folder management (Milestone 7) -------------------------------------------

    async def create_folder(
        self, account_id: str, name: str, *, parent_id: str | None = None
    ) -> Folder:
        """Create a folder."""
        ...

    async def rename_folder(self, account_id: str, folder_id: str, name: str) -> Folder:
        """Rename a folder."""
        ...

    async def move_folder(self, account_id: str, folder_id: str, new_parent_id: str) -> Folder:
        """Move a folder under a new parent."""
        ...

    async def delete_folder(self, account_id: str, folder_id: str) -> None:
        """Delete a folder."""
        ...

    async def empty_folder(self, account_id: str, folder_id: str) -> None:
        """Permanently empty a folder."""
        ...

    # --- Calendar (Milestone 8) ----------------------------------------------------

    async def list_calendars(self, account_id: str | None = None) -> list[Calendar]:
        """List calendars."""
        ...

    async def list_events(self, account_id: str, *, limit: int = 25) -> list[CalendarEvent]:
        """List upcoming calendar events."""
        ...

    async def get_event(self, account_id: str, event_id: str) -> CalendarEvent:
        """Fetch a single event."""
        ...

    async def create_event(self, account_id: str, data: CalendarEventInput) -> CalendarEvent:
        """Create a calendar event."""
        ...

    async def update_event(
        self, account_id: str, event_id: str, data: CalendarEventInput
    ) -> CalendarEvent:
        """Update a calendar event."""
        ...

    async def delete_event(self, account_id: str, event_id: str) -> None:
        """Delete a calendar event."""
        ...

    async def respond_to_event(
        self, account_id: str, event_id: str, response: EventResponse
    ) -> None:
        """RSVP to a meeting."""
        ...

    # --- Contacts / Tasks / Notes (Milestone 8) ------------------------------------

    async def list_contacts(self, account_id: str, *, limit: int = 50) -> list[Contact]:
        """List contacts."""
        ...

    async def search_contacts(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Contact]:
        """Search contacts."""
        ...

    async def get_contact(self, account_id: str, contact_id: str) -> Contact:
        """Fetch a contact."""
        ...

    async def list_tasks(self, account_id: str, *, limit: int = 50) -> list[Task]:
        """List tasks."""
        ...

    async def search_tasks(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Task]:
        """Search tasks."""
        ...

    async def get_task(self, account_id: str, task_id: str) -> Task:
        """Fetch a task."""
        ...

    async def list_notes(self, account_id: str, *, limit: int = 50) -> list[Note]:
        """List notes."""
        ...

    async def search_notes(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Note]:
        """Search notes."""
        ...

    async def get_note(self, account_id: str, note_id: str) -> Note:
        """Fetch a note."""
        ...
