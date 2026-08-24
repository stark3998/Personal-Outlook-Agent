"""Attachment domain model (metadata only; contents fetched on demand)."""

from __future__ import annotations

from pydantic import BaseModel


class Attachment(BaseModel):
    """Metadata for a single email attachment."""

    index: int
    name: str
    size: int = 0
    content_type: str | None = None
