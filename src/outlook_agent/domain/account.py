"""Account domain model."""

from __future__ import annotations

from pydantic import BaseModel

from .enums import ProviderName


class Account(BaseModel):
    """An Outlook account (Exchange, IMAP, etc.)."""

    provider: ProviderName
    account_id: str
    name: str
    email_address: str | None = None
    account_type: str | None = None
