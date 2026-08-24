"""Thread (conversation) domain model.

Outlook for Mac exposes a numeric ``conversation_id`` but not RFC References/In-Reply-To.
A thread is therefore reconstructed from ``conversation_id`` plus subject normalization
and participant overlap (see ThreadService).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .email import EmailSummary
from .recipient import Recipient


class Thread(BaseModel):
    """An ordered conversation of messages."""

    conversation_id: str | None = None
    normalized_subject: str | None = None
    messages: list[EmailSummary] = Field(default_factory=list)
    participants: list[Recipient] = Field(default_factory=list)
    message_count: int = 0
    unread_count: int = 0
    has_attachments: bool = False
    latest_at: datetime | None = None
