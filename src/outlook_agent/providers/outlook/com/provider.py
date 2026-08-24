"""Windows COM implementation of the :class:`OutlookProvider` interface.

Drives the Outlook Object Model via ``win32com``. Identity mapping:

* ``account_id`` = Store ``StoreID``  (a mailbox/store is the account unit here)
* ``folder_id``  = MAPIFolder ``EntryID``
* ``item_id``    = item ``EntryID``

Items are resolved with ``namespace.GetItemFromID(item_id, account_id)`` and folders with
``namespace.GetFolderFromID(folder_id, account_id)``. Destructive/outbound methods are
invoked only via the ActionService.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    Priority,
    ProviderCapabilities,
    ProviderName,
    Recipient,
    RecipientKind,
    SpecialFolderType,
    Task,
)

from . import executor as ex
from .executor import ComError, ComErrorType, ComExecutor

_NAME = ProviderName.OUTLOOK_COM

_CAPABILITIES = frozenset(
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

_SPECIAL_BY_DEFAULT = {
    ex.OL_FOLDER_INBOX: SpecialFolderType.INBOX,
    ex.OL_FOLDER_OUTBOX: SpecialFolderType.OUTBOX,
    ex.OL_FOLDER_SENT: SpecialFolderType.SENT,
    ex.OL_FOLDER_DELETED: SpecialFolderType.DELETED,
    ex.OL_FOLDER_DRAFTS: SpecialFolderType.DRAFTS,
    ex.OL_FOLDER_JUNK: SpecialFolderType.JUNK,
    ex.OL_FOLDER_CALENDAR: SpecialFolderType.CALENDAR,
}


def _dt(value: Any) -> datetime | None:
    """Convert a pywintypes datetime to a plain datetime, guarding unset sentinels."""
    if value is None:
        return None
    try:
        year = int(value.year)
        if year < 1900 or year > 4000:
            return None
        return datetime(year, value.month, value.day, value.hour, value.minute, value.second)
    except (AttributeError, ValueError):
        return None


def _get(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:  # noqa: BLE001 - COM attribute access can raise
        return default


def _internet_message_id(item: Any) -> str | None:
    try:
        value = item.PropertyAccessor.GetProperty(
            "http://schemas.microsoft.com/mapi/proptag/0x1035001F"
        )
    except Exception:  # noqa: BLE001
        return None
    return str(value) if value else None


def _sender(item: Any) -> Recipient | None:
    name = _get(item, "SenderName")
    address = _get(item, "SenderEmailAddress")
    if not (name or address):
        return None
    return Recipient(name=name or None, address=address or None)


def _recipients(item: Any, kind_code: int, kind: RecipientKind) -> list[Recipient]:
    out: list[Recipient] = []
    recips = _get(item, "Recipients")
    if recips is None:
        return out
    try:
        count = recips.Count
    except Exception:  # noqa: BLE001
        return out
    for i in range(1, count + 1):
        r = recips.Item(i)
        if _get(r, "Type") != kind_code:
            continue
        out.append(
            Recipient(
                name=_get(r, "Name") or None,
                address=_get(r, "Address") or None,
                kind=kind,
            )
        )
    return out


def _summary(item: Any, account_id: str) -> EmailSummary:
    folder = _get(item, "Parent")
    folder_id = _get(folder, "EntryID", "")
    body = _get(item, "Body", "") or ""
    return EmailSummary(
        ref=EmailRef(
            provider=_NAME,
            account_id=account_id,
            folder_id=folder_id,
            item_id=_get(item, "EntryID", ""),
            conversation_id=_get(item, "ConversationID") or None,
            message_id=_internet_message_id(item),
        ),
        subject=_get(item, "Subject") or None,
        sender=_sender(item),
        preview=body[:200] or None,
        is_read=not bool(_get(item, "UnRead", False)),
        received_at=_dt(_get(item, "ReceivedTime")),
        sent_at=_dt(_get(item, "SentOn")),
        has_attachments=bool(_get(_get(item, "Attachments"), "Count", 0)),
        priority=Priority.NORMAL,
    )


def _email(item: Any, account_id: str) -> Email:
    summary = _summary(item, account_id)
    return Email(
        **summary.model_dump(),
        recipients=_recipients(item, 1, RecipientKind.TO),
        cc=_recipients(item, 2, RecipientKind.CC),
        body_text=_get(item, "Body") or None,
        body_html=_get(item, "HTMLBody") or None,
        size=int(_get(item, "Size", 0) or 0),
    )


def _special_map(namespace: Any) -> dict[str, SpecialFolderType]:
    """Map default-store folder EntryIDs to our SpecialFolderType."""
    out: dict[str, SpecialFolderType] = {}
    for default_id, special in _SPECIAL_BY_DEFAULT.items():
        try:
            folder = namespace.GetDefaultFolder(default_id)
            out[folder.EntryID] = special
        except Exception:  # noqa: BLE001, S112 - some default folders may be absent
            continue
    return out


def _walk_folders(
    folder: Any, account_id: str, parent_id: str | None, specials: dict[str, SpecialFolderType]
) -> list[Folder]:
    entry_id = _get(folder, "EntryID", "")
    out = [
        Folder(
            provider=_NAME,
            account_id=account_id,
            folder_id=entry_id,
            name=_get(folder, "Name", "") or "",
            parent_id=parent_id,
            special_type=specials.get(entry_id, SpecialFolderType.UNKNOWN),
            message_count=int(_get(_get(folder, "Items"), "Count", 0) or 0),
            unread_count=int(_get(folder, "UnReadItemCount", 0) or 0),
        )
    ]
    subfolders = _get(folder, "Folders")
    if subfolders is not None:
        for sub in subfolders:
            out.extend(_walk_folders(sub, account_id, entry_id, specials))
    return out


class OutlookCOMProvider:
    """Outlook provider backed by the Windows COM Object Model."""

    def __init__(self, executor: ComExecutor | None = None) -> None:
        self._exec = executor or ComExecutor()

    def capabilities(self) -> ProviderCapabilities:
        if not self._exec.available:
            return ProviderCapabilities(supported=frozenset())
        return ProviderCapabilities(supported=_CAPABILITIES)

    async def probe_outlook(self) -> OutlookInfo:
        if not self._exec.available:
            return OutlookInfo(installed=False, running=False)
        version = await self._exec.version()
        return OutlookInfo(
            installed=version is not None,
            running=version is not None,
            version=version,
            mode="classic" if version else None,
        )

    async def probe_permissions(self) -> Permissions:
        # A successful COM Dispatch implies the automation model is reachable.
        try:
            ok = await self._exec.is_running()
        except ComError:
            ok = False
        return Permissions(automation=ok, accessibility=False)

    # --- Reads ------------------------------------------------------------------------

    async def list_accounts(self) -> list[Account]:
        def fn(_app: Any, ns: Any) -> list[Account]:
            out: list[Account] = []
            for store in ns.Stores:
                out.append(
                    Account(
                        provider=_NAME,
                        account_id=_get(store, "StoreID", ""),
                        name=_get(store, "DisplayName", "") or "",
                    )
                )
            return out

        return await self._exec.run(fn)

    async def list_folders(self, account_id: str | None = None) -> list[Folder]:
        def fn(_app: Any, ns: Any) -> list[Folder]:
            specials = _special_map(ns)
            out: list[Folder] = []
            for root in ns.Folders:
                store_id = _get(root, "StoreID", "")
                if account_id is not None and store_id != account_id:
                    continue
                out.extend(_walk_folders(root, store_id, None, specials))
            return out

        return await self._exec.run(fn)

    async def list_emails(
        self, account_id: str, folder_id: str, *, limit: int = 25, offset: int = 0
    ) -> list[EmailSummary]:
        def fn(_app: Any, ns: Any) -> list[EmailSummary]:
            folder = ns.GetFolderFromID(folder_id, account_id)
            items = folder.Items
            items.Sort("[ReceivedTime]", True)
            out: list[EmailSummary] = []
            total = items.Count
            start = offset + 1
            for i in range(start, min(start + limit, total + 1)):
                out.append(_summary(items.Item(i), account_id))
            return out

        return await self._exec.run(fn)

    async def search_emails(
        self,
        query: str,
        *,
        account_id: str | None = None,
        folder_id: str | None = None,
        limit: int = 25,
    ) -> list[EmailSummary]:
        safe = query.replace("'", "''")
        dasl = f"@SQL=\"urn:schemas:httpmail:subject\" like '%{safe}%'"

        def fn(_app: Any, ns: Any) -> list[EmailSummary]:
            if folder_id and account_id:
                folder = ns.GetFolderFromID(folder_id, account_id)
            else:
                folder = ns.GetDefaultFolder(ex.OL_FOLDER_INBOX)
            store_id = account_id or _get(_get(folder, "Store"), "StoreID", "")
            items = folder.Items.Restrict(dasl)
            out: list[EmailSummary] = []
            for i in range(1, min(limit, items.Count) + 1):
                out.append(_summary(items.Item(i), store_id))
            return out

        return await self._exec.run(fn)

    async def get_email(self, ref: EmailRef) -> Email:
        def fn(_app: Any, ns: Any) -> Email:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            return _email(item, ref.account_id)

        return await self._exec.run(fn)

    async def list_conversation(
        self, conversation_id: str, *, account_id: str | None = None
    ) -> list[EmailSummary]:
        def fn(_app: Any, ns: Any) -> list[EmailSummary]:
            out: list[EmailSummary] = []
            inbox = ns.GetDefaultFolder(ex.OL_FOLDER_INBOX)
            store_id = account_id or _get(_get(inbox, "Store"), "StoreID", "")
            for folder in (inbox, ns.GetDefaultFolder(ex.OL_FOLDER_SENT)):
                for item in folder.Items:
                    if _get(item, "ConversationID") == conversation_id:
                        out.append(_summary(item, store_id))
            return out

        return await self._exec.run(fn)

    # --- Drafts & composition ---------------------------------------------------------

    async def create_draft(self, account_id: str, data: DraftInput) -> Draft:
        def fn(app: Any, _ns: Any) -> Draft:
            mail = app.CreateItem(ex.OL_MAIL_ITEM)
            if data.subject:
                mail.Subject = data.subject
            if data.body.html is not None:
                mail.HTMLBody = data.body.html
            elif data.body.text is not None:
                mail.Body = data.body.text
            mail.To = "; ".join(r.address for r in data.to if r.address)
            mail.CC = "; ".join(r.address for r in data.cc if r.address)
            mail.BCC = "; ".join(r.address for r in data.bcc if r.address)
            for path in data.attachments:
                mail.Attachments.Add(path)
            mail.Save()
            return Draft(
                provider=_NAME,
                account_id=account_id,
                draft_id=_get(mail, "EntryID", ""),
                subject=data.subject,
                body_text=data.body.text,
                body_html=data.body.html,
                to=data.to,
                cc=data.cc,
                bcc=data.bcc,
            )

        return await self._exec.run(fn)

    async def get_draft(self, account_id: str, draft_id: str) -> Draft:
        def fn(_app: Any, ns: Any) -> Draft:
            item = ns.GetItemFromID(draft_id, account_id)
            return Draft(
                provider=_NAME,
                account_id=account_id,
                draft_id=draft_id,
                subject=_get(item, "Subject") or None,
                body_text=_get(item, "Body") or None,
                body_html=_get(item, "HTMLBody") or None,
            )

        return await self._exec.run(fn)

    async def list_drafts(self, account_id: str, *, limit: int = 25) -> list[Draft]:
        def fn(_app: Any, ns: Any) -> list[Draft]:
            folder = ns.GetDefaultFolder(ex.OL_FOLDER_DRAFTS)
            out: list[Draft] = []
            items = folder.Items
            for i in range(1, min(limit, items.Count) + 1):
                item = items.Item(i)
                out.append(
                    Draft(
                        provider=_NAME,
                        account_id=account_id,
                        draft_id=_get(item, "EntryID", ""),
                        subject=_get(item, "Subject") or None,
                        body_text=_get(item, "Body") or None,
                    )
                )
            return out

        return await self._exec.run(fn)

    async def update_draft(self, account_id: str, draft_id: str, data: DraftInput) -> Draft:
        def fn(_app: Any, ns: Any) -> None:
            item = ns.GetItemFromID(draft_id, account_id)
            if data.subject is not None:
                item.Subject = data.subject
            if data.body.html is not None:
                item.HTMLBody = data.body.html
            elif data.body.text is not None:
                item.Body = data.body.text
            item.Save()

        await self._exec.run(fn)
        return await self.get_draft(account_id, draft_id)

    async def delete_draft(self, account_id: str, draft_id: str) -> None:
        await self._delete_item(account_id, draft_id)

    async def create_reply_draft(
        self, ref: EmailRef, *, reply_all: bool = False, body: str | None = None
    ) -> Draft:
        def fn(_app: Any, ns: Any) -> Draft:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            reply = item.ReplyAll() if reply_all else item.Reply()
            if body:
                reply.Body = body + (_get(reply, "Body", "") or "")
            reply.Save()
            return Draft(
                provider=_NAME,
                account_id=ref.account_id,
                draft_id=_get(reply, "EntryID", ""),
                in_reply_to=ref,
            )

        return await self._exec.run(fn)

    async def create_forward_draft(
        self, ref: EmailRef, *, to: list[str], body: str | None = None
    ) -> Draft:
        def fn(_app: Any, ns: Any) -> Draft:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            fwd = item.Forward()
            fwd.To = "; ".join(to)
            if body:
                fwd.Body = body + (_get(fwd, "Body", "") or "")
            fwd.Save()
            return Draft(
                provider=_NAME,
                account_id=ref.account_id,
                draft_id=_get(fwd, "EntryID", ""),
                in_reply_to=ref,
            )

        return await self._exec.run(fn)

    async def send_draft(self, account_id: str, draft_id: str) -> None:
        def fn(_app: Any, ns: Any) -> None:
            ns.GetItemFromID(draft_id, account_id).Send()

        await self._exec.run(fn)

    # --- Organization -----------------------------------------------------------------

    async def set_read(self, ref: EmailRef, *, read: bool) -> None:
        def fn(_app: Any, ns: Any) -> None:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            item.UnRead = not read
            item.Save()

        await self._exec.run(fn)

    async def set_flag(self, ref: EmailRef, *, flagged: bool) -> None:
        def fn(_app: Any, ns: Any) -> None:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            item.FlagStatus = 2 if flagged else 0  # 2 = olFlagMarked, 0 = olNoFlag
            item.Save()

        await self._exec.run(fn)

    async def set_categories(self, ref: EmailRef, categories: list[str]) -> None:
        def fn(_app: Any, ns: Any) -> None:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            item.Categories = "; ".join(categories)
            item.Save()

        await self._exec.run(fn)

    async def move_email(self, ref: EmailRef, *, target_folder_id: str) -> None:
        def fn(_app: Any, ns: Any) -> None:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            target = ns.GetFolderFromID(target_folder_id, ref.account_id)
            item.Move(target)

        await self._exec.run(fn)

    async def archive_email(self, ref: EmailRef) -> None:
        # No universal COM "archive"; move to a folder named "Archive" if present.
        def fn(_app: Any, ns: Any) -> None:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            root = ns.GetFolderFromID(ref.folder_id, ref.account_id).Store.GetRootFolder()
            for sub in root.Folders:
                if _get(sub, "Name", "").lower() == "archive":
                    item.Move(sub)
                    return
            raise ComError("No Archive folder found.", ComErrorType.UNKNOWN)

        await self._exec.run(fn)

    async def delete_email(self, ref: EmailRef) -> None:
        await self._delete_item(ref.account_id, ref.item_id)

    async def junk_email(self, ref: EmailRef) -> None:
        def fn(_app: Any, ns: Any) -> None:
            item = ns.GetItemFromID(ref.item_id, ref.account_id)
            item.Move(ns.GetDefaultFolder(ex.OL_FOLDER_JUNK))

        await self._exec.run(fn)

    async def _delete_item(self, account_id: str, item_id: str) -> None:
        def fn(_app: Any, ns: Any) -> None:
            ns.GetItemFromID(item_id, account_id).Delete()

        await self._exec.run(fn)

    # --- Folder management ------------------------------------------------------------

    async def create_folder(
        self, account_id: str, name: str, *, parent_id: str | None = None
    ) -> Folder:
        def fn(_app: Any, ns: Any) -> Folder:
            parent = (
                ns.GetFolderFromID(parent_id, account_id)
                if parent_id
                else ns.GetDefaultFolder(ex.OL_FOLDER_INBOX)
            )
            created = parent.Folders.Add(name)
            return Folder(
                provider=_NAME,
                account_id=account_id,
                folder_id=_get(created, "EntryID", ""),
                name=name,
                parent_id=parent_id,
            )

        return await self._exec.run(fn)

    async def rename_folder(self, account_id: str, folder_id: str, name: str) -> Folder:
        def fn(_app: Any, ns: Any) -> Folder:
            folder = ns.GetFolderFromID(folder_id, account_id)
            folder.Name = name
            return Folder(provider=_NAME, account_id=account_id, folder_id=folder_id, name=name)

        return await self._exec.run(fn)

    async def move_folder(self, account_id: str, folder_id: str, new_parent_id: str) -> Folder:
        def fn(_app: Any, ns: Any) -> Folder:
            folder = ns.GetFolderFromID(folder_id, account_id)
            target = ns.GetFolderFromID(new_parent_id, account_id)
            folder.MoveTo(target)
            return Folder(
                provider=_NAME,
                account_id=account_id,
                folder_id=folder_id,
                name=_get(folder, "Name", "") or "",
                parent_id=new_parent_id,
            )

        return await self._exec.run(fn)

    async def delete_folder(self, account_id: str, folder_id: str) -> None:
        def fn(_app: Any, ns: Any) -> None:
            ns.GetFolderFromID(folder_id, account_id).Delete()

        await self._exec.run(fn)

    async def empty_folder(self, account_id: str, folder_id: str) -> None:
        def fn(_app: Any, ns: Any) -> None:
            folder = ns.GetFolderFromID(folder_id, account_id)
            items = folder.Items
            while items.Count > 0:
                items.Item(1).Delete()

        await self._exec.run(fn)

    # --- Calendar ---------------------------------------------------------------------

    async def list_calendars(self, account_id: str | None = None) -> list[Calendar]:
        def fn(_app: Any, ns: Any) -> list[Calendar]:
            cal = ns.GetDefaultFolder(ex.OL_FOLDER_CALENDAR)
            store_id = account_id or _get(_get(cal, "Store"), "StoreID", "")
            return [
                Calendar(
                    provider=_NAME,
                    account_id=store_id,
                    calendar_id=_get(cal, "EntryID", ""),
                    name=_get(cal, "Name", "Calendar") or "Calendar",
                )
            ]

        return await self._exec.run(fn)

    async def list_events(self, account_id: str, *, limit: int = 25) -> list[CalendarEvent]:
        def fn(_app: Any, ns: Any) -> list[CalendarEvent]:
            cal = ns.GetDefaultFolder(ex.OL_FOLDER_CALENDAR)
            items = cal.Items
            items.Sort("[Start]")
            items.IncludeRecurrences = False
            out: list[CalendarEvent] = []
            for i in range(1, min(limit, items.Count) + 1):
                out.append(_event(items.Item(i), account_id))
            return out

        return await self._exec.run(fn)

    async def get_event(self, account_id: str, event_id: str) -> CalendarEvent:
        def fn(_app: Any, ns: Any) -> CalendarEvent:
            return _event(ns.GetItemFromID(event_id, account_id), account_id)

        return await self._exec.run(fn)

    async def create_event(self, account_id: str, data: CalendarEventInput) -> CalendarEvent:
        def fn(app: Any, _ns: Any) -> CalendarEvent:
            appt = app.CreateItem(ex.OL_APPOINTMENT_ITEM)
            appt.Subject = data.subject
            appt.Start = data.start.strftime("%Y-%m-%d %H:%M")
            appt.End = data.end.strftime("%Y-%m-%d %H:%M")
            if data.location:
                appt.Location = data.location
            if data.body:
                appt.Body = data.body
            appt.AllDayEvent = data.all_day
            appt.Save()
            return _event(appt, account_id)

        return await self._exec.run(fn)

    async def update_event(
        self, account_id: str, event_id: str, data: CalendarEventInput
    ) -> CalendarEvent:
        def fn(_app: Any, ns: Any) -> CalendarEvent:
            appt = ns.GetItemFromID(event_id, account_id)
            appt.Subject = data.subject
            appt.Start = data.start.strftime("%Y-%m-%d %H:%M")
            appt.End = data.end.strftime("%Y-%m-%d %H:%M")
            if data.location:
                appt.Location = data.location
            appt.Save()
            return _event(appt, account_id)

        return await self._exec.run(fn)

    async def delete_event(self, account_id: str, event_id: str) -> None:
        await self._delete_item(account_id, event_id)

    async def respond_to_event(
        self, account_id: str, event_id: str, response: EventResponse
    ) -> None:
        codes = {EventResponse.ACCEPT: 3, EventResponse.TENTATIVE: 2, EventResponse.DECLINE: 4}

        def fn(_app: Any, ns: Any) -> None:
            appt = ns.GetItemFromID(event_id, account_id)
            meeting = appt.Respond(codes[response], True)
            meeting.Send()

        await self._exec.run(fn)

    # --- Contacts / Tasks / Notes -----------------------------------------------------

    async def list_contacts(self, account_id: str, *, limit: int = 50) -> list[Contact]:
        return await self._exec.run(lambda _a, ns: _list_contacts(ns, account_id, limit, None))

    async def search_contacts(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Contact]:
        return await self._exec.run(
            lambda _a, ns: _list_contacts(ns, account_id or "", limit, query)
        )

    async def get_contact(self, account_id: str, contact_id: str) -> Contact:
        def fn(_app: Any, ns: Any) -> Contact:
            return _contact(ns.GetItemFromID(contact_id, account_id), account_id)

        return await self._exec.run(fn)

    async def list_tasks(self, account_id: str, *, limit: int = 50) -> list[Task]:
        return await self._exec.run(lambda _a, ns: _list_tasks(ns, account_id, limit, None))

    async def search_tasks(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Task]:
        return await self._exec.run(lambda _a, ns: _list_tasks(ns, account_id or "", limit, query))

    async def get_task(self, account_id: str, task_id: str) -> Task:
        def fn(_app: Any, ns: Any) -> Task:
            return _task(ns.GetItemFromID(task_id, account_id), account_id)

        return await self._exec.run(fn)

    async def list_notes(self, account_id: str, *, limit: int = 50) -> list[Note]:
        return await self._exec.run(lambda _a, ns: _list_notes(ns, account_id, limit, None))

    async def search_notes(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Note]:
        return await self._exec.run(lambda _a, ns: _list_notes(ns, account_id or "", limit, query))

    async def get_note(self, account_id: str, note_id: str) -> Note:
        def fn(_app: Any, ns: Any) -> Note:
            return _note(ns.GetItemFromID(note_id, account_id), account_id)

        return await self._exec.run(fn)


def _event(item: Any, account_id: str) -> CalendarEvent:
    return CalendarEvent(
        provider=_NAME,
        account_id=account_id,
        event_id=_get(item, "EntryID", ""),
        subject=_get(item, "Subject") or None,
        location=_get(item, "Location") or None,
        start=_dt(_get(item, "Start")),
        end=_dt(_get(item, "End")),
        all_day=bool(_get(item, "AllDayEvent", False)),
        body_text=_get(item, "Body") or None,
        is_recurring=bool(_get(item, "IsRecurring", False)),
    )


def _contact(item: Any, account_id: str) -> Contact:
    email = _get(item, "Email1Address")
    return Contact(
        provider=_NAME,
        account_id=account_id,
        contact_id=_get(item, "EntryID", ""),
        display_name=_get(item, "FullName") or None,
        first_name=_get(item, "FirstName") or None,
        last_name=_get(item, "LastName") or None,
        emails=[email] if email else [],
        company=_get(item, "CompanyName") or None,
    )


def _task(item: Any, account_id: str) -> Task:
    return Task(
        provider=_NAME,
        account_id=account_id,
        task_id=_get(item, "EntryID", ""),
        subject=_get(item, "Subject") or None,
        body_text=_get(item, "Body") or None,
        due_date=_dt(_get(item, "DueDate")),
        completed=bool(_get(item, "Complete", False)),
    )


def _note(item: Any, account_id: str) -> Note:
    return Note(
        provider=_NAME,
        account_id=account_id,
        note_id=_get(item, "EntryID", ""),
        title=_get(item, "Subject") or None,
        body_text=_get(item, "Body") or None,
        modified_at=_dt(_get(item, "LastModificationTime")),
    )


def _list_contacts(ns: Any, account_id: str, limit: int, query: str | None) -> list[Contact]:
    folder = ns.GetDefaultFolder(ex.OL_FOLDER_CONTACTS)
    store_id = account_id or _get(_get(folder, "Store"), "StoreID", "")
    out: list[Contact] = []
    for item in folder.Items:
        if len(out) >= limit:
            break
        if query and query.lower() not in (_get(item, "FullName", "") or "").lower():
            continue
        out.append(_contact(item, store_id))
    return out


def _list_tasks(ns: Any, account_id: str, limit: int, query: str | None) -> list[Task]:
    folder = ns.GetDefaultFolder(ex.OL_FOLDER_TASKS)
    store_id = account_id or _get(_get(folder, "Store"), "StoreID", "")
    out: list[Task] = []
    for item in folder.Items:
        if len(out) >= limit:
            break
        if query and query.lower() not in (_get(item, "Subject", "") or "").lower():
            continue
        out.append(_task(item, store_id))
    return out


def _list_notes(ns: Any, account_id: str, limit: int, query: str | None) -> list[Note]:
    folder = ns.GetDefaultFolder(ex.OL_FOLDER_NOTES)
    store_id = account_id or _get(_get(folder, "Store"), "StoreID", "")
    out: list[Note] = []
    for item in folder.Items:
        if len(out) >= limit:
            break
        if query and query.lower() not in (_get(item, "Subject", "") or "").lower():
            continue
        out.append(_note(item, store_id))
    return out
