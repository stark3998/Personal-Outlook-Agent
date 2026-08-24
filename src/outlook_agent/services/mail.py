"""MailService — mail reads plus organization (safe writes + gated destructive ops)."""

from __future__ import annotations

from outlook_agent.domain import (
    Account,
    ApprovalToken,
    Capability,
    Email,
    EmailRef,
    EmailSummary,
    Folder,
)
from outlook_agent.domain.action import ActionType
from outlook_agent.providers.base import CapabilityUnavailable, OutlookProvider
from outlook_agent.services.actions import ActionService


class MailService:
    """Coordinates mail reads and organization. Contains no provider-specific logic."""

    def __init__(self, provider: OutlookProvider, actions: ActionService | None = None) -> None:
        self._provider = provider
        self._actions = actions

    def _require(self, capability: Capability) -> None:
        if not self._provider.capabilities().has(capability):
            raise CapabilityUnavailable(capability)

    def _action_service(self) -> ActionService:
        if self._actions is None:
            raise RuntimeError("MailService requires an ActionService for gated operations")
        return self._actions

    async def list_accounts(self) -> list[Account]:
        """List configured accounts."""
        self._require(Capability.MAIL_READ)
        return await self._provider.list_accounts()

    async def list_folders(self, account_id: str | None = None) -> list[Folder]:
        """List folders, optionally scoped to one account."""
        self._require(Capability.FOLDERS_READ)
        return await self._provider.list_folders(account_id)

    async def list_emails(
        self, account_id: str, folder_id: str, *, limit: int = 25, offset: int = 0
    ) -> list[EmailSummary]:
        """List message summaries in a folder."""
        self._require(Capability.MAIL_READ)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        return await self._provider.list_emails(account_id, folder_id, limit=limit, offset=offset)

    async def search_emails(
        self,
        query: str,
        *,
        account_id: str | None = None,
        folder_id: str | None = None,
        limit: int = 25,
    ) -> list[EmailSummary]:
        """Search messages by subject/sender/content."""
        self._require(Capability.MAIL_SEARCH)
        limit = max(1, min(limit, 200))
        return await self._provider.search_emails(
            query, account_id=account_id, folder_id=folder_id, limit=limit
        )

    async def get_email(self, ref: EmailRef) -> Email:
        """Fetch a full message by reference."""
        self._require(Capability.MAIL_READ)
        return await self._provider.get_email(ref)

    # --- Organization: low-risk direct writes -----------------------------------------

    async def mark_read(self, ref: EmailRef, *, read: bool = True) -> None:
        """Mark a message read or unread."""
        self._require(Capability.MAIL_ORGANIZE)
        await self._provider.set_read(ref, read=read)

    async def set_flag(self, ref: EmailRef, *, flagged: bool = True) -> None:
        """Set or clear the follow-up flag."""
        self._require(Capability.MAIL_ORGANIZE)
        await self._provider.set_flag(ref, flagged=flagged)

    async def set_categories(self, ref: EmailRef, categories: list[str]) -> None:
        """Replace the categories on a message."""
        self._require(Capability.MAIL_ORGANIZE)
        await self._provider.set_categories(ref, categories)

    # --- Organization: gated destructive ops ------------------------------------------

    async def prepare_move(
        self, ref: EmailRef, target_folder_id: str, *, requested_by: str | None = None
    ) -> ApprovalToken:
        """Prepare a gated move to another folder."""
        self._require(Capability.MAIL_MOVE)
        return await self._action_service().prepare(
            ActionType.MOVE,
            summary=f"Move message {ref.item_id} to folder {target_folder_id}",
            target=ref.model_dump(mode="json"),
            payload={"target_folder_id": target_folder_id},
            requested_by=requested_by,
        )

    async def prepare_delete(
        self, ref: EmailRef, *, requested_by: str | None = None
    ) -> ApprovalToken:
        """Prepare a gated delete."""
        self._require(Capability.MAIL_DELETE)
        return await self._action_service().prepare(
            ActionType.DELETE,
            summary=f"Delete message {ref.item_id}",
            target=ref.model_dump(mode="json"),
            requested_by=requested_by,
        )

    async def prepare_junk(
        self, ref: EmailRef, *, requested_by: str | None = None
    ) -> ApprovalToken:
        """Prepare a gated move-to-junk."""
        self._require(Capability.MAIL_ORGANIZE)
        return await self._action_service().prepare(
            ActionType.JUNK,
            summary=f"Junk message {ref.item_id}",
            target=ref.model_dump(mode="json"),
            requested_by=requested_by,
        )
