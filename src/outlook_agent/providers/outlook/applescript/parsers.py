"""Parsers converting AppleScript JSON output into domain models.

Includes a small HTML-to-text stripper adapted from
hasan-imam/mcp-outlook-applescript ``parsers/html-stripper.ts``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from outlook_agent.domain import (
    Account,
    Calendar,
    CalendarEvent,
    Contact,
    Draft,
    Email,
    EmailRef,
    EmailSummary,
    Folder,
    Note,
    ProviderName,
    Recipient,
    RecipientKind,
    SpecialFolderType,
    Task,
)
from outlook_agent.domain.enums import FlagStatus, Priority

_PROVIDER = ProviderName.OUTLOOK_APPLESCRIPT

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def strip_html(html: str) -> str:
    """Best-effort HTML → plain text conversion for previews/fallback bodies."""
    if not html:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = _TAG_RE.sub("", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    text = _WS_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n\n", text)
    return text.strip()


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ``YYYY-MM-DDTHH:MM:SS`` string (naive/local) into a datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_accounts(raw: str) -> list[Account]:
    """Parse the JSON emitted by ``list_accounts_script``."""
    data = _loads_array(raw)
    return [
        Account(
            provider=_PROVIDER,
            account_id=str(item.get("account_id", "")),
            name=str(item.get("name", "")),
            email_address=item.get("email_address") or None,
        )
        for item in data
    ]


def parse_folders(raw: str) -> list[Folder]:
    """Parse the JSON emitted by ``list_folders_script``."""
    data = _loads_array(raw)
    folders: list[Folder] = []
    for item in data:
        folders.append(
            Folder(
                provider=_PROVIDER,
                account_id=str(item.get("account_id", "")),
                folder_id=str(item.get("folder_id", "")),
                name=str(item.get("name", "")),
                parent_id=item.get("parent_id") or None,
                special_type=_special_type(item.get("special_type")),
                message_count=int(item.get("message_count", 0) or 0),
                unread_count=int(item.get("unread_count", 0) or 0),
            )
        )
    return folders


def parse_summaries(raw: str, *, account_id: str) -> list[EmailSummary]:
    """Parse a JSON array of message summaries."""
    return [_summary_from(item, account_id=account_id) for item in _loads_array(raw)]


def parse_email(raw: str, *, account_id: str) -> Email:
    """Parse a single full-message JSON object."""
    item = json.loads(raw) if raw.strip() else {}
    summary = _summary_from(item, account_id=account_id)
    body_html = item.get("body_html") or None
    body_text = item.get("body_text") or None
    if not body_text and body_html:
        body_text = strip_html(body_html)
    return Email(
        **summary.model_dump(),
        recipients=_recipients(item.get("to"), RecipientKind.TO),
        cc=_recipients(item.get("cc"), RecipientKind.CC),
        body_text=body_text,
        body_html=body_html,
    )


def _summary_from(item: dict[str, Any], *, account_id: str) -> EmailSummary:
    sender_name = item.get("sender_name") or None
    sender_addr = item.get("sender_address") or None
    sender = (
        Recipient(name=sender_name, address=sender_addr, kind=RecipientKind.TO)
        if (sender_name or sender_addr)
        else None
    )
    ref = EmailRef(
        provider=_PROVIDER,
        account_id=account_id,
        folder_id=str(item.get("folder_id", "")),
        item_id=str(item.get("item_id", "")),
        conversation_id=(str(item["conversation_id"]) if item.get("conversation_id") else None),
    )
    return EmailSummary(
        ref=ref,
        subject=item.get("subject") or None,
        sender=sender,
        preview=item.get("preview") or None,
        is_read=bool(item.get("is_read", False)),
        received_at=_parse_dt(item.get("received_at")),
        sent_at=_parse_dt(item.get("sent_at")),
        has_attachments=bool(item.get("has_attachments", False)),
        priority=Priority.NORMAL,
        flag_status=FlagStatus.NONE,
    )


def _recipients(raw: Any, kind: RecipientKind) -> list[Recipient]:
    if not isinstance(raw, list):
        return []
    out: list[Recipient] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        name = r.get("name") or None
        address = r.get("address") or None
        if name or address:
            out.append(Recipient(name=name, address=address, kind=kind))
    return out


def _special_type(value: Any) -> SpecialFolderType:
    try:
        return SpecialFolderType(int(value))
    except (ValueError, TypeError):
        return SpecialFolderType.UNKNOWN


def _loads_array(raw: str) -> list[dict[str, Any]]:
    if not raw or not raw.strip():
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array from AppleScript output")
    return [item for item in data if isinstance(item, dict)]


def _obj(raw: str) -> dict[str, Any]:
    return json.loads(raw) if raw.strip() else {}


def parse_draft(raw: str, *, account_id: str) -> Draft:
    """Parse a single draft JSON object."""
    item = _obj(raw)
    return Draft(
        provider=_PROVIDER,
        account_id=account_id,
        draft_id=str(item.get("draft_id", "")),
        subject=item.get("subject") or None,
        body_text=item.get("body_text") or None,
    )


def parse_drafts(raw: str, *, account_id: str) -> list[Draft]:
    """Parse a JSON array of drafts."""
    return [
        Draft(
            provider=_PROVIDER,
            account_id=account_id,
            draft_id=str(item.get("draft_id", "")),
            subject=item.get("subject") or None,
            body_text=item.get("body_text") or None,
        )
        for item in _loads_array(raw)
    ]


def parse_calendars(raw: str, *, account_id: str) -> list[Calendar]:
    """Parse a JSON array of calendars."""
    return [
        Calendar(
            provider=_PROVIDER,
            account_id=account_id,
            calendar_id=str(item.get("calendar_id", "")),
            name=str(item.get("name", "")),
        )
        for item in _loads_array(raw)
    ]


def _event_from(item: dict[str, Any], *, account_id: str) -> CalendarEvent:
    return CalendarEvent(
        provider=_PROVIDER,
        account_id=account_id,
        event_id=str(item.get("event_id", "")),
        subject=item.get("subject") or None,
        location=item.get("location") or None,
        start=_parse_dt(item.get("start")),
        end=_parse_dt(item.get("end")),
    )


def parse_events(raw: str, *, account_id: str) -> list[CalendarEvent]:
    """Parse a JSON array of events."""
    return [_event_from(i, account_id=account_id) for i in _loads_array(raw)]


def parse_event(raw: str, *, account_id: str) -> CalendarEvent:
    """Parse a single event JSON object."""
    return _event_from(_obj(raw), account_id=account_id)


def _contact_from(item: dict[str, Any], *, account_id: str) -> Contact:
    email = item.get("email")
    return Contact(
        provider=_PROVIDER,
        account_id=account_id,
        contact_id=str(item.get("contact_id", "")),
        display_name=item.get("display_name") or None,
        emails=[email] if email else [],
        company=item.get("company") or None,
    )


def parse_contacts(raw: str, *, account_id: str) -> list[Contact]:
    """Parse a JSON array of contacts."""
    return [_contact_from(i, account_id=account_id) for i in _loads_array(raw)]


def parse_contact(raw: str, *, account_id: str) -> Contact:
    """Parse a single contact JSON object."""
    return _contact_from(_obj(raw), account_id=account_id)


def _task_from(item: dict[str, Any], *, account_id: str) -> Task:
    return Task(
        provider=_PROVIDER,
        account_id=account_id,
        task_id=str(item.get("task_id", "")),
        subject=item.get("subject") or None,
        completed=bool(item.get("completed", False)),
    )


def parse_tasks(raw: str, *, account_id: str) -> list[Task]:
    """Parse a JSON array of tasks."""
    return [_task_from(i, account_id=account_id) for i in _loads_array(raw)]


def parse_task(raw: str, *, account_id: str) -> Task:
    """Parse a single task JSON object."""
    return _task_from(_obj(raw), account_id=account_id)


def _note_from(item: dict[str, Any], *, account_id: str) -> Note:
    return Note(
        provider=_PROVIDER,
        account_id=account_id,
        note_id=str(item.get("note_id", "")),
        title=item.get("title") or None,
        body_text=item.get("body_text") or None,
    )


def parse_notes(raw: str, *, account_id: str) -> list[Note]:
    """Parse a JSON array of notes."""
    return [_note_from(i, account_id=account_id) for i in _loads_array(raw)]


def parse_note(raw: str, *, account_id: str) -> Note:
    """Parse a single note JSON object."""
    return _note_from(_obj(raw), account_id=account_id)
