"""FolderService — folder reads and management (destructive ops gated)."""

from __future__ import annotations

from outlook_agent.domain import ApprovalToken, Capability, Folder
from outlook_agent.domain.action import ActionType
from outlook_agent.providers.base import CapabilityUnavailable, OutlookProvider
from outlook_agent.services.actions import ActionService


class FolderService:
    """List/create/rename folders (safe) and prepare gated delete/empty."""

    def __init__(self, provider: OutlookProvider, actions: ActionService) -> None:
        self._provider = provider
        self._actions = actions

    def _require(self, capability: Capability) -> None:
        if not self._provider.capabilities().has(capability):
            raise CapabilityUnavailable(capability)

    async def list_folders(self, account_id: str | None = None) -> list[Folder]:
        self._require(Capability.FOLDERS_READ)
        return await self._provider.list_folders(account_id)

    async def create_folder(
        self, account_id: str, name: str, *, parent_id: str | None = None
    ) -> Folder:
        self._require(Capability.FOLDERS_WRITE)
        return await self._provider.create_folder(account_id, name, parent_id=parent_id)

    async def rename_folder(self, account_id: str, folder_id: str, name: str) -> Folder:
        self._require(Capability.FOLDERS_WRITE)
        return await self._provider.rename_folder(account_id, folder_id, name)

    async def prepare_delete(
        self, account_id: str, folder_id: str, *, requested_by: str | None = None
    ) -> ApprovalToken:
        self._require(Capability.FOLDERS_WRITE)
        return await self._actions.prepare(
            ActionType.FOLDER_DELETE,
            summary=f"Delete folder {folder_id}",
            target={"account_id": account_id, "folder_id": folder_id},
            requested_by=requested_by,
        )

    async def prepare_empty(
        self, account_id: str, folder_id: str, *, requested_by: str | None = None
    ) -> ApprovalToken:
        self._require(Capability.FOLDERS_WRITE)
        return await self._actions.prepare(
            ActionType.FOLDER_EMPTY,
            summary=f"Empty folder {folder_id}",
            target={"account_id": account_id, "folder_id": folder_id},
            requested_by=requested_by,
        )
