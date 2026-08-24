"""Calendar domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .enums import ProviderName
from .recipient import Recipient


class EventResponse(StrEnum):
    """RSVP responses to a meeting invitation."""

    ACCEPT = "accept"
    DECLINE = "decline"
    TENTATIVE = "tentative"


class Calendar(BaseModel):
    """A calendar container."""

    provider: ProviderName
    account_id: str
    calendar_id: str
    name: str


class CalendarEvent(BaseModel):
    """A calendar event / meeting."""

    provider: ProviderName
    account_id: str
    calendar_id: str | None = None
    event_id: str
    subject: str | None = None
    location: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool = False
    organizer: Recipient | None = None
    attendees: list[Recipient] = Field(default_factory=list)
    body_text: str | None = None
    is_recurring: bool = False


class CalendarEventInput(BaseModel):
    """Fields used to create or update an event."""

    subject: str
    start: datetime
    end: datetime
    location: str | None = None
    body: str | None = None
    all_day: bool = False
    attendees: list[Recipient] = Field(default_factory=list)
