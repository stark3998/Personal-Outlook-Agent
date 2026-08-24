"""AppleScript implementation of the :class:`OutlookProvider` interface."""

from __future__ import annotations

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
    ProviderName,
    SpecialFolderType,
    Task,
)

from . import scripts, scripts_pim, scripts_write
from .executor import AppleScriptError, AppleScriptExecutor
from .parsers import (
    parse_accounts,
    parse_calendars,
    parse_contact,
    parse_contacts,
    parse_draft,
    parse_drafts,
    parse_email,
    parse_event,
    parse_events,
    parse_folders,
    parse_note,
    parse_notes,
    parse_summaries,
    parse_task,
    parse_tasks,
)

_READ_CAPABILITIES = frozenset(
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


class OutlookAppleScriptProvider:
    """Outlook provider backed by classic Outlook's AppleScript dictionary.

    Destructive/outbound operations are exposed here but must be invoked only via the
    ActionService (see services/handlers.py). Some verbs require live-Mac verification.
    """

    def __init__(self, executor: AppleScriptExecutor | None = None) -> None:
        self._exec = executor or AppleScriptExecutor()
        self._name = ProviderName.OUTLOOK_APPLESCRIPT

    def capabilities(self) -> ProviderCapabilities:
        if not self._exec.available:
            return ProviderCapabilities(supported=frozenset())
        return ProviderCapabilities(supported=_READ_CAPABILITIES)

    async def probe_outlook(self) -> OutlookInfo:
        if not self._exec.available:
            return OutlookInfo(installed=False, running=False)
        running = await self._exec.is_outlook_running()
        version = await self._exec.outlook_version() if running else None
        return OutlookInfo(
            installed=version is not None or running,
            running=running,
            version=version,
            mode="classic" if version else None,
        )

    async def probe_permissions(self) -> Permissions:
        if not self._exec.available:
            return Permissions(automation=False, accessibility=False)
        # A successful scripted read implies Automation permission was granted.
        try:
            await self._exec.run('tell application "Microsoft Outlook" to get name')
            automation = True
        except AppleScriptError:
            automation = False
        return Permissions(automation=automation, accessibility=False)

    async def list_accounts(self) -> list[Account]:
        raw = await self._exec.run(scripts.list_accounts_script())
        return parse_accounts(raw)

    async def list_folders(self, account_id: str | None = None) -> list[Folder]:
        raw = await self._exec.run(scripts.list_folders_script(account_id), large=True)
        return parse_folders(raw)

    async def list_emails(
        self,
        account_id: str,
        folder_id: str,
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> list[EmailSummary]:
        raw = await self._exec.run(
            scripts.list_emails_script(account_id, folder_id, limit=limit, offset=offset),
            large=True,
        )
        return parse_summaries(raw, account_id=account_id)

    async def search_emails(
        self,
        query: str,
        *,
        account_id: str | None = None,
        folder_id: str | None = None,
        limit: int = 25,
    ) -> list[EmailSummary]:
        raw = await self._exec.run(
            scripts.search_emails_script(
                query, account_id=account_id, folder_id=folder_id, limit=limit
            ),
            large=True,
        )
        return parse_summaries(raw, account_id=account_id or "")

    async def get_email(self, ref: EmailRef) -> Email:
        raw = await self._exec.run(scripts.get_email_script(ref.folder_id, ref.item_id))
        return parse_email(raw, account_id=ref.account_id)

    async def list_conversation(
        self, conversation_id: str, *, account_id: str | None = None
    ) -> list[EmailSummary]:
        raw = await self._exec.run(scripts.list_conversation_script(conversation_id), large=True)
        return parse_summaries(raw, account_id=account_id or "")

    # --- Drafts & composition ---------------------------------------------------------

    async def create_draft(self, account_id: str, data: DraftInput) -> Draft:
        body = data.body.html or data.body.text or ""
        raw = await self._exec.run(
            scripts_write.create_draft_script(
                data.subject or "",
                body,
                to=[r.address for r in data.to if r.address],
                cc=[r.address for r in data.cc if r.address],
                bcc=[r.address for r in data.bcc if r.address],
                html=data.body.html is not None,
            )
        )
        return Draft(
            provider=self._name,
            account_id=account_id,
            draft_id=raw.strip(),
            subject=data.subject,
            body_text=data.body.text,
            body_html=data.body.html,
            to=data.to,
            cc=data.cc,
            bcc=data.bcc,
        )

    async def get_draft(self, account_id: str, draft_id: str) -> Draft:
        raw = await self._exec.run(scripts_write.get_draft_script(draft_id))
        return parse_draft(raw, account_id=account_id)

    async def list_drafts(self, account_id: str, *, limit: int = 25) -> list[Draft]:
        raw = await self._exec.run(scripts_write.list_drafts_script(limit), large=True)
        return parse_drafts(raw, account_id=account_id)

    async def update_draft(self, account_id: str, draft_id: str, data: DraftInput) -> Draft:
        await self._exec.run(
            scripts_write.update_draft_script(draft_id, data.subject, data.body.text)
        )
        return await self.get_draft(account_id, draft_id)

    async def delete_draft(self, account_id: str, draft_id: str) -> None:
        await self._exec.run(scripts_write.delete_message_script(draft_id))

    async def create_reply_draft(
        self, ref: EmailRef, *, reply_all: bool = False, body: str | None = None
    ) -> Draft:
        raw = await self._exec.run(
            scripts_write.reply_draft_script(ref.item_id, reply_all, body or "")
        )
        return Draft(
            provider=self._name,
            account_id=ref.account_id,
            draft_id=raw.strip(),
            in_reply_to=ref,
        )

    async def create_forward_draft(
        self, ref: EmailRef, *, to: list[str], body: str | None = None
    ) -> Draft:
        raw = await self._exec.run(scripts_write.forward_draft_script(ref.item_id, to, body or ""))
        return Draft(
            provider=self._name,
            account_id=ref.account_id,
            draft_id=raw.strip(),
            in_reply_to=ref,
        )

    async def send_draft(self, account_id: str, draft_id: str) -> None:
        await self._exec.run(scripts_write.send_draft_script(draft_id))

    # --- Organization -----------------------------------------------------------------

    async def set_read(self, ref: EmailRef, *, read: bool) -> None:
        await self._exec.run(scripts_write.set_read_script(ref.item_id, read))

    async def set_flag(self, ref: EmailRef, *, flagged: bool) -> None:
        await self._exec.run(scripts_write.set_flag_script(ref.item_id, flagged))

    async def set_categories(self, ref: EmailRef, categories: list[str]) -> None:
        await self._exec.run(scripts_write.set_categories_script(ref.item_id, categories))

    async def move_email(self, ref: EmailRef, *, target_folder_id: str) -> None:
        await self._exec.run(scripts_write.move_message_script(ref.item_id, target_folder_id))

    async def archive_email(self, ref: EmailRef) -> None:
        # Outlook for Mac has no dedicated archive verb; treat as a no-op placeholder that
        # providers implementing UI scripting may override. Live verification required.
        raise NotImplementedError("archive is not supported by the AppleScript provider")

    async def delete_email(self, ref: EmailRef) -> None:
        await self._exec.run(scripts_write.delete_message_script(ref.item_id))

    async def junk_email(self, ref: EmailRef) -> None:
        await self._exec.run(
            scripts_write.move_to_special_script(ref.item_id, int(SpecialFolderType.JUNK))
        )

    # --- Folder management ------------------------------------------------------------

    async def create_folder(
        self, account_id: str, name: str, *, parent_id: str | None = None
    ) -> Folder:
        raw = await self._exec.run(scripts_write.create_folder_script(name, parent_id))
        return Folder(
            provider=self._name,
            account_id=account_id,
            folder_id=raw.strip(),
            name=name,
            parent_id=parent_id,
        )

    async def rename_folder(self, account_id: str, folder_id: str, name: str) -> Folder:
        await self._exec.run(scripts_write.rename_folder_script(folder_id, name))
        return Folder(provider=self._name, account_id=account_id, folder_id=folder_id, name=name)

    async def move_folder(self, account_id: str, folder_id: str, new_parent_id: str) -> Folder:
        # Folder move is not exposed by the classic AppleScript dictionary; UI fallback only.
        raise NotImplementedError("move_folder requires the UI provider")

    async def delete_folder(self, account_id: str, folder_id: str) -> None:
        await self._exec.run(scripts_write.delete_folder_script(folder_id))

    async def empty_folder(self, account_id: str, folder_id: str) -> None:
        await self._exec.run(scripts_write.empty_folder_script(folder_id), large=True)

    # --- Calendar ---------------------------------------------------------------------

    async def list_calendars(self, account_id: str | None = None) -> list[Calendar]:
        raw = await self._exec.run(scripts_pim.list_calendars_script())
        return parse_calendars(raw, account_id=account_id or "")

    async def list_events(self, account_id: str, *, limit: int = 25) -> list[CalendarEvent]:
        raw = await self._exec.run(scripts_pim.list_events_script(limit), large=True)
        return parse_events(raw, account_id=account_id)

    async def get_event(self, account_id: str, event_id: str) -> CalendarEvent:
        raw = await self._exec.run(scripts_pim.get_event_script(event_id))
        return parse_event(raw, account_id=account_id)

    async def create_event(self, account_id: str, data: CalendarEventInput) -> CalendarEvent:
        raw = await self._exec.run(
            scripts_pim.create_event_script(
                data.subject,
                data.start.strftime("%Y-%m-%dT%H:%M:%S"),
                data.end.strftime("%Y-%m-%dT%H:%M:%S"),
                data.location or "",
                data.body or "",
            )
        )
        return CalendarEvent(
            provider=self._name,
            account_id=account_id,
            event_id=raw.strip(),
            subject=data.subject,
            location=data.location,
            start=data.start,
            end=data.end,
        )

    async def update_event(
        self, account_id: str, event_id: str, data: CalendarEventInput
    ) -> CalendarEvent:
        raise NotImplementedError("update_event requires live verification")

    async def delete_event(self, account_id: str, event_id: str) -> None:
        await self._exec.run(scripts_pim.delete_event_script(event_id))

    async def respond_to_event(
        self, account_id: str, event_id: str, response: EventResponse
    ) -> None:
        raise NotImplementedError("respond_to_event requires live verification")

    # --- Contacts / Tasks / Notes -----------------------------------------------------

    async def list_contacts(self, account_id: str, *, limit: int = 50) -> list[Contact]:
        raw = await self._exec.run(scripts_pim.list_contacts_script(limit, None), large=True)
        return parse_contacts(raw, account_id=account_id)

    async def search_contacts(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Contact]:
        raw = await self._exec.run(scripts_pim.list_contacts_script(limit, query), large=True)
        return parse_contacts(raw, account_id=account_id or "")

    async def get_contact(self, account_id: str, contact_id: str) -> Contact:
        raw = await self._exec.run(scripts_pim.get_contact_script(contact_id))
        return parse_contact(raw, account_id=account_id)

    async def list_tasks(self, account_id: str, *, limit: int = 50) -> list[Task]:
        raw = await self._exec.run(scripts_pim.list_tasks_script(limit, None), large=True)
        return parse_tasks(raw, account_id=account_id)

    async def search_tasks(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Task]:
        raw = await self._exec.run(scripts_pim.list_tasks_script(limit, query), large=True)
        return parse_tasks(raw, account_id=account_id or "")

    async def get_task(self, account_id: str, task_id: str) -> Task:
        raw = await self._exec.run(scripts_pim.get_task_script(task_id))
        return parse_task(raw, account_id=account_id)

    async def list_notes(self, account_id: str, *, limit: int = 50) -> list[Note]:
        raw = await self._exec.run(scripts_pim.list_notes_script(limit, None), large=True)
        return parse_notes(raw, account_id=account_id)

    async def search_notes(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Note]:
        raw = await self._exec.run(scripts_pim.list_notes_script(limit, query), large=True)
        return parse_notes(raw, account_id=account_id or "")

    async def get_note(self, account_id: str, note_id: str) -> Note:
        raw = await self._exec.run(scripts_pim.get_note_script(note_id))
        return parse_note(raw, account_id=account_id)
