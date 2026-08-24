"""Draft domain model and draft composition inputs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .attachment import Attachment
from .email import EmailRef
from .enums import ProviderName
from .recipient import Recipient


class DraftBody(BaseModel):
    """Body content for a draft; both plain text and HTML may be supplied."""

    text: str | None = None
    html: str | None = None


class DraftInput(BaseModel):
    """Fields used to create or update a draft."""

    subject: str | None = None
    body: DraftBody = Field(default_factory=DraftBody)
    to: list[Recipient] = Field(default_factory=list)
    cc: list[Recipient] = Field(default_factory=list)
    bcc: list[Recipient] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)  # local file paths to attach


class Draft(BaseModel):
    """A saved draft message."""

    provider: ProviderName
    account_id: str
    draft_id: str
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    to: list[Recipient] = Field(default_factory=list)
    cc: list[Recipient] = Field(default_factory=list)
    bcc: list[Recipient] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    # Set when the draft is a reply/forward of an existing message.
    in_reply_to: EmailRef | None = None
