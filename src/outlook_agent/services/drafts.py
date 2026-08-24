"""DraftService — draft composition. Sending is gated through the ActionService."""

from __future__ import annotations

from outlook_agent.domain import ApprovalToken, Capability, Draft, DraftInput, EmailRef
from outlook_agent.domain.action import ActionType
from outlook_agent.providers.base import CapabilityUnavailable, OutlookProvider
from outlook_agent.services.actions import ActionService


class DraftService:
    """Create/read/update drafts (safe) and prepare a gated send."""

    def __init__(self, provider: OutlookProvider, actions: ActionService) -> None:
        self._provider = provider
        self._actions = actions

    def _require(self, capability: Capability) -> None:
        if not self._provider.capabilities().has(capability):
            raise CapabilityUnavailable(capability)

    async def create_draft(self, account_id: str, data: DraftInput) -> Draft:
        self._require(Capability.MAIL_DRAFT)
        return await self._provider.create_draft(account_id, data)

    async def get_draft(self, account_id: str, draft_id: str) -> Draft:
        self._require(Capability.MAIL_DRAFT)
        return await self._provider.get_draft(account_id, draft_id)

    async def list_drafts(self, account_id: str, *, limit: int = 25) -> list[Draft]:
        self._require(Capability.MAIL_DRAFT)
        return await self._provider.list_drafts(account_id, limit=limit)

    async def update_draft(self, account_id: str, draft_id: str, data: DraftInput) -> Draft:
        self._require(Capability.MAIL_DRAFT)
        return await self._provider.update_draft(account_id, draft_id, data)

    async def delete_draft(self, account_id: str, draft_id: str) -> None:
        self._require(Capability.MAIL_DRAFT)
        await self._provider.delete_draft(account_id, draft_id)

    async def reply(
        self, ref: EmailRef, *, reply_all: bool = False, body: str | None = None
    ) -> Draft:
        """Create a reply/reply-all draft (does not send)."""
        self._require(Capability.MAIL_REPLY)
        return await self._provider.create_reply_draft(ref, reply_all=reply_all, body=body)

    async def forward(self, ref: EmailRef, *, to: list[str], body: str | None = None) -> Draft:
        """Create a forward draft (does not send)."""
        self._require(Capability.MAIL_REPLY)
        return await self._provider.create_forward_draft(ref, to=to, body=body)

    async def prepare_send(
        self, account_id: str, draft_id: str, *, requested_by: str | None = None
    ) -> ApprovalToken:
        """Prepare a gated send. Confirm via ActionService to actually send."""
        self._require(Capability.MAIL_SEND)
        return await self._actions.prepare(
            ActionType.SEND,
            summary=f"Send draft {draft_id}",
            target={"account_id": account_id, "draft_id": draft_id},
            requested_by=requested_by,
        )
