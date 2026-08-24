"""Shared pytest fixtures: an in-memory fake provider for hermetic tests."""

from __future__ import annotations

import pytest

from outlook_agent.domain import (
    Account,
    Calendar,
    CalendarEvent,
    CalendarEventInput,
    Capability,
    Contact,
    Draft,
    DraftBody,
    DraftInput,
    Email,
    EmailRef,
    EmailSummary,
    Folder,
    Note,
    OutlookInfo,
    Permissions,
    ProviderCapabilities,
    ProviderName,
    Recipient,
    SpecialFolderType,
    Task,
)

_PROVIDER = ProviderName.OUTLOOK_APPLESCRIPT


class FakeOutlookProvider:
    """Deterministic OutlookProvider implementation for unit/integration tests."""

    def __init__(self) -> None:
        self._drafts: dict[str, Draft] = {}
        self.sent: list[str] = []
        self.ops: list[tuple] = []
        self._account = Account(
            provider=_PROVIDER, account_id="1", name="Test", email_address="me@example.com"
        )
        self._folder = Folder(
            provider=_PROVIDER,
            account_id="1",
            folder_id="10",
            name="Inbox",
            special_type=SpecialFolderType.INBOX,
            message_count=2,
            unread_count=1,
        )
        self._summaries = [
            EmailSummary(
                ref=EmailRef(
                    provider=_PROVIDER,
                    account_id="1",
                    folder_id="10",
                    item_id="100",
                    conversation_id="900",
                ),
                subject="Re: Entra rollout",
                sender=Recipient(name="Alice", address="alice@example.com"),
                is_read=False,
            ),
            EmailSummary(
                ref=EmailRef(
                    provider=_PROVIDER,
                    account_id="1",
                    folder_id="10",
                    item_id="101",
                    conversation_id="900",
                ),
                subject="Entra rollout",
                sender=Recipient(name="Bob", address="bob@example.com"),
                is_read=True,
            ),
        ]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supported=frozenset(
                {
                    Capability.MAIL_READ,
                    Capability.MAIL_SEARCH,
                    Capability.MAIL_THREAD,
                    Capability.MAIL_DRAFT,
                    Capability.MAIL_REPLY,
                    Capability.MAIL_SEND,
                    Capability.MAIL_ORGANIZE,
                    Capability.MAIL_MOVE,
                    Capability.MAIL_DELETE,
                    Capability.FOLDERS_READ,
                    Capability.FOLDERS_WRITE,
                    Capability.CALENDAR_READ,
                    Capability.CALENDAR_WRITE,
                    Capability.CONTACTS_READ,
                    Capability.TASKS_READ,
                    Capability.NOTES_READ,
                }
            )
        )

    async def probe_outlook(self) -> OutlookInfo:
        return OutlookInfo(installed=True, running=True, version="16.0", mode="classic")

    async def probe_permissions(self) -> Permissions:
        return Permissions(automation=True, accessibility=False)

    async def list_accounts(self) -> list[Account]:
        return [self._account]

    async def list_folders(self, account_id: str | None = None) -> list[Folder]:
        return [self._folder]

    async def list_emails(
        self, account_id: str, folder_id: str, *, limit: int = 25, offset: int = 0
    ) -> list[EmailSummary]:
        return self._summaries[offset : offset + limit]

    async def search_emails(
        self,
        query: str,
        *,
        account_id: str | None = None,
        folder_id: str | None = None,
        limit: int = 25,
    ) -> list[EmailSummary]:
        return [s for s in self._summaries if query.lower() in (s.subject or "").lower()][:limit]

    async def get_email(self, ref: EmailRef) -> Email:
        summary = next((s for s in self._summaries if s.ref.item_id == ref.item_id), None)
        base = summary.model_dump() if summary else {"ref": ref.model_dump()}
        return Email(**base, body_text="Hello world", body_html="<p>Hello world</p>")

    async def list_conversation(
        self, conversation_id: str, *, account_id: str | None = None
    ) -> list[EmailSummary]:
        return [s for s in self._summaries if s.ref.conversation_id == conversation_id]

    # --- Drafts & composition ---------------------------------------------------------

    async def create_draft(self, account_id: str, data: DraftInput) -> Draft:
        did = str(200 + len(self._drafts))
        draft = Draft(
            provider=_PROVIDER,
            account_id=account_id,
            draft_id=did,
            subject=data.subject,
            body_text=data.body.text,
            body_html=data.body.html,
            to=data.to,
            cc=data.cc,
            bcc=data.bcc,
        )
        self._drafts[did] = draft
        return draft

    async def get_draft(self, account_id: str, draft_id: str) -> Draft:
        return self._drafts[draft_id]

    async def list_drafts(self, account_id: str, *, limit: int = 25) -> list[Draft]:
        return list(self._drafts.values())[:limit]

    async def update_draft(self, account_id: str, draft_id: str, data: DraftInput) -> Draft:
        draft = self._drafts[draft_id]
        updated = draft.model_copy(update={"subject": data.subject, "body_text": data.body.text})
        self._drafts[draft_id] = updated
        return updated

    async def delete_draft(self, account_id: str, draft_id: str) -> None:
        self._drafts.pop(draft_id, None)

    async def create_reply_draft(
        self, ref: EmailRef, *, reply_all: bool = False, body: str | None = None
    ) -> Draft:
        return await self.create_draft(
            ref.account_id, DraftInput(subject="Re: reply", body=DraftBody(text=body))
        )

    async def create_forward_draft(
        self, ref: EmailRef, *, to: list[str], body: str | None = None
    ) -> Draft:
        return await self.create_draft(
            ref.account_id, DraftInput(subject="Fwd", body=DraftBody(text=body))
        )

    async def send_draft(self, account_id: str, draft_id: str) -> None:
        self.sent.append(draft_id)
        self._drafts.pop(draft_id, None)

    # --- Organization -----------------------------------------------------------------

    async def set_read(self, ref: EmailRef, *, read: bool) -> None:
        self.ops.append(("set_read", ref.item_id, read))

    async def set_flag(self, ref: EmailRef, *, flagged: bool) -> None:
        self.ops.append(("set_flag", ref.item_id, flagged))

    async def set_categories(self, ref: EmailRef, categories: list[str]) -> None:
        self.ops.append(("set_categories", ref.item_id, tuple(categories)))

    async def move_email(self, ref: EmailRef, *, target_folder_id: str) -> None:
        self.ops.append(("move", ref.item_id, target_folder_id))

    async def archive_email(self, ref: EmailRef) -> None:
        self.ops.append(("archive", ref.item_id))

    async def delete_email(self, ref: EmailRef) -> None:
        self.ops.append(("delete", ref.item_id))

    async def junk_email(self, ref: EmailRef) -> None:
        self.ops.append(("junk", ref.item_id))

    # --- Folders ----------------------------------------------------------------------

    async def create_folder(
        self, account_id: str, name: str, *, parent_id: str | None = None
    ) -> Folder:
        return Folder(provider=_PROVIDER, account_id=account_id, folder_id="99", name=name)

    async def rename_folder(self, account_id: str, folder_id: str, name: str) -> Folder:
        return Folder(provider=_PROVIDER, account_id=account_id, folder_id=folder_id, name=name)

    async def move_folder(self, account_id: str, folder_id: str, new_parent_id: str) -> Folder:
        return Folder(provider=_PROVIDER, account_id=account_id, folder_id=folder_id, name="x")

    async def delete_folder(self, account_id: str, folder_id: str) -> None:
        self.ops.append(("delete_folder", folder_id))

    async def empty_folder(self, account_id: str, folder_id: str) -> None:
        self.ops.append(("empty_folder", folder_id))

    # --- Calendar ---------------------------------------------------------------------

    async def list_calendars(self, account_id: str | None = None) -> list[Calendar]:
        return [Calendar(provider=_PROVIDER, account_id="1", calendar_id="c1", name="Cal")]

    async def list_events(self, account_id: str, *, limit: int = 25) -> list[CalendarEvent]:
        return [
            CalendarEvent(provider=_PROVIDER, account_id="1", event_id="e1", subject="Standup")
        ][:limit]

    async def get_event(self, account_id: str, event_id: str) -> CalendarEvent:
        return CalendarEvent(
            provider=_PROVIDER, account_id="1", event_id=event_id, subject="Standup"
        )

    async def create_event(self, account_id: str, data: CalendarEventInput) -> CalendarEvent:
        return CalendarEvent(
            provider=_PROVIDER,
            account_id=account_id,
            event_id="enew",
            subject=data.subject,
            start=data.start,
            end=data.end,
        )

    async def update_event(
        self, account_id: str, event_id: str, data: CalendarEventInput
    ) -> CalendarEvent:
        return await self.get_event(account_id, event_id)

    async def delete_event(self, account_id: str, event_id: str) -> None:
        self.ops.append(("delete_event", event_id))

    async def respond_to_event(self, account_id: str, event_id: str, response) -> None:
        self.ops.append(("respond", event_id, str(response)))

    # --- Contacts / Tasks / Notes -----------------------------------------------------

    async def list_contacts(self, account_id: str, *, limit: int = 50) -> list[Contact]:
        return [Contact(provider=_PROVIDER, account_id="1", contact_id="k1", display_name="Al")]

    async def search_contacts(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Contact]:
        return await self.list_contacts(account_id or "1", limit=limit)

    async def get_contact(self, account_id: str, contact_id: str) -> Contact:
        return Contact(provider=_PROVIDER, account_id="1", contact_id=contact_id, display_name="Al")

    async def list_tasks(self, account_id: str, *, limit: int = 50) -> list[Task]:
        return [Task(provider=_PROVIDER, account_id="1", task_id="t1", subject="Do it")]

    async def search_tasks(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Task]:
        return await self.list_tasks(account_id or "1", limit=limit)

    async def get_task(self, account_id: str, task_id: str) -> Task:
        return Task(provider=_PROVIDER, account_id="1", task_id=task_id, subject="Do it")

    async def list_notes(self, account_id: str, *, limit: int = 50) -> list[Note]:
        return [Note(provider=_PROVIDER, account_id="1", note_id="n1", title="Note")]

    async def search_notes(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Note]:
        return await self.list_notes(account_id or "1", limit=limit)

    async def get_note(self, account_id: str, note_id: str) -> Note:
        return Note(provider=_PROVIDER, account_id="1", note_id=note_id, title="Note")


class FakeLLMProvider:
    """Deterministic LLM for hermetic intelligence tests."""

    async def complete(self, messages, *, temperature: float = 0.2) -> str:
        return "ok"

    async def summarize(self, text: str, *, instructions: str | None = None) -> str:
        return "SUMMARY"

    async def classify(self, text: str, labels: list[str]) -> str:
        return labels[0] if labels else ""

    async def extract(self, text: str, what: str) -> list[str]:
        return ["Follow up with Alice", "Send the report"]

    async def generate_reply(self, context: str, instructions: str) -> str:
        return "Thanks — proposed reply body."


@pytest.fixture
def fake_provider() -> FakeOutlookProvider:
    return FakeOutlookProvider()


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()
