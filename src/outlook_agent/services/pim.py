"""ContactService, TaskService, NoteService — read-only PIM orchestration."""

from __future__ import annotations

from outlook_agent.domain import Capability, Contact, Note, Task
from outlook_agent.providers.base import CapabilityUnavailable, OutlookProvider


class _PimService:
    def __init__(self, provider: OutlookProvider) -> None:
        self._provider = provider

    def _require(self, capability: Capability) -> None:
        if not self._provider.capabilities().has(capability):
            raise CapabilityUnavailable(capability)


class ContactService(_PimService):
    """List/search/get contacts."""

    async def list_contacts(self, account_id: str, *, limit: int = 50) -> list[Contact]:
        self._require(Capability.CONTACTS_READ)
        return await self._provider.list_contacts(account_id, limit=limit)

    async def search_contacts(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Contact]:
        self._require(Capability.CONTACTS_READ)
        return await self._provider.search_contacts(query, account_id=account_id, limit=limit)

    async def get_contact(self, account_id: str, contact_id: str) -> Contact:
        self._require(Capability.CONTACTS_READ)
        return await self._provider.get_contact(account_id, contact_id)


class TaskService(_PimService):
    """List/search/get tasks."""

    async def list_tasks(self, account_id: str, *, limit: int = 50) -> list[Task]:
        self._require(Capability.TASKS_READ)
        return await self._provider.list_tasks(account_id, limit=limit)

    async def search_tasks(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Task]:
        self._require(Capability.TASKS_READ)
        return await self._provider.search_tasks(query, account_id=account_id, limit=limit)

    async def get_task(self, account_id: str, task_id: str) -> Task:
        self._require(Capability.TASKS_READ)
        return await self._provider.get_task(account_id, task_id)


class NoteService(_PimService):
    """List/search/get notes."""

    async def list_notes(self, account_id: str, *, limit: int = 50) -> list[Note]:
        self._require(Capability.NOTES_READ)
        return await self._provider.list_notes(account_id, limit=limit)

    async def search_notes(
        self, query: str, *, account_id: str | None = None, limit: int = 25
    ) -> list[Note]:
        self._require(Capability.NOTES_READ)
        return await self._provider.search_notes(query, account_id=account_id, limit=limit)

    async def get_note(self, account_id: str, note_id: str) -> Note:
        self._require(Capability.NOTES_READ)
        return await self._provider.get_note(account_id, note_id)
