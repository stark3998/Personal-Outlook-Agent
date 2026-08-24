"""Recipient and attachment domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class RecipientKind(StrEnum):
    """Recipient role on a message."""

    TO = "to"
    CC = "cc"
    BCC = "bcc"


class Recipient(BaseModel):
    """A single message recipient or sender."""

    name: str | None = None
    address: str | None = None
    kind: RecipientKind = RecipientKind.TO
