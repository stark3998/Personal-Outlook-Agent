"""Contact domain model."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import ProviderName


class Contact(BaseModel):
    """An address-book contact."""

    provider: ProviderName
    account_id: str
    contact_id: str
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    company: str | None = None
