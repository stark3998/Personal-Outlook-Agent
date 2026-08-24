"""Email domain models: reference/identity, summary, and full message."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .attachment import Attachment
from .enums import FlagStatus, Priority, ProviderName
from .recipient import Recipient


class EmailRef(BaseModel):
    """Enough context to uniquely resolve a message.

    Outlook item IDs are numeric and provider-scoped — not globally unique and not
    stable forever. Never rely on ``item_id`` alone; carry the surrounding context and
    stable hints (``message_id``, ``conversation_id``) where available.
    """

    provider: ProviderName
    account_id: str
    folder_id: str
    item_id: str
    message_id: str | None = None
    conversation_id: str | None = None


class EmailSummary(BaseModel):
    """Lightweight representation used in list and search results."""

    ref: EmailRef
    subject: str | None = None
    sender: Recipient | None = None
    preview: str | None = None
    is_read: bool = False
    received_at: datetime | None = None
    sent_at: datetime | None = None
    has_attachments: bool = False
    priority: Priority = Priority.NORMAL
    flag_status: FlagStatus = FlagStatus.NONE
    categories: list[str] = Field(default_factory=list)


class Email(EmailSummary):
    """Complete message including body content and recipients."""

    recipients: list[Recipient] = Field(default_factory=list)
    cc: list[Recipient] = Field(default_factory=list)
    body_text: str | None = None
    body_html: str | None = None
    size: int = 0
    attachments: list[Attachment] = Field(default_factory=list)
    # RFC 5322 threading headers when the provider can expose them.
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
