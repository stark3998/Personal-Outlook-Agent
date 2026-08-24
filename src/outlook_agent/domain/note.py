"""Note domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .enums import ProviderName


class Note(BaseModel):
    """An Outlook note."""

    provider: ProviderName
    account_id: str
    note_id: str
    title: str | None = None
    body_text: str | None = None
    modified_at: datetime | None = None
