"""Account and folder domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import ProviderName, SpecialFolderType


class Folder(BaseModel):
    """A mail folder with message and unread counts.

    ``folder_id`` is provider-scoped and not globally unique; always resolve folders in
    the context of their ``account_id``.
    """

    provider: ProviderName
    account_id: str
    folder_id: str
    name: str
    parent_id: str | None = None
    special_type: SpecialFolderType = SpecialFolderType.UNKNOWN
    message_count: int = 0
    unread_count: int = 0
    children: list[Folder] = Field(default_factory=list)
