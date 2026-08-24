"""Task domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .enums import ProviderName


class Task(BaseModel):
    """An Outlook task / to-do item."""

    provider: ProviderName
    account_id: str
    task_id: str
    subject: str | None = None
    body_text: str | None = None
    due_date: datetime | None = None
    completed: bool = False
    priority: int | None = None
