"""CalendarService — calendar reads (safe) and gated create/delete/respond."""

from __future__ import annotations

from outlook_agent.domain import (
    ApprovalToken,
    Calendar,
    CalendarEvent,
    CalendarEventInput,
    Capability,
    EventResponse,
)
from outlook_agent.domain.action import ActionType
from outlook_agent.providers.base import CapabilityUnavailable, OutlookProvider
from outlook_agent.services.actions import ActionService


class CalendarService:
    """List/get events (safe); create/delete/respond are ActionService-gated."""

    def __init__(self, provider: OutlookProvider, actions: ActionService) -> None:
        self._provider = provider
        self._actions = actions

    def _require(self, capability: Capability) -> None:
        if not self._provider.capabilities().has(capability):
            raise CapabilityUnavailable(capability)

    async def list_calendars(self, account_id: str | None = None) -> list[Calendar]:
        self._require(Capability.CALENDAR_READ)
        return await self._provider.list_calendars(account_id)

    async def list_events(self, account_id: str, *, limit: int = 25) -> list[CalendarEvent]:
        self._require(Capability.CALENDAR_READ)
        return await self._provider.list_events(account_id, limit=limit)

    async def get_event(self, account_id: str, event_id: str) -> CalendarEvent:
        self._require(Capability.CALENDAR_READ)
        return await self._provider.get_event(account_id, event_id)

    async def prepare_create(
        self, account_id: str, data: CalendarEventInput, *, requested_by: str | None = None
    ) -> ApprovalToken:
        self._require(Capability.CALENDAR_WRITE)
        return await self._actions.prepare(
            ActionType.CALENDAR_CREATE,
            summary=f"Create event '{data.subject}'",
            target={"account_id": account_id},
            payload={"event": data.model_dump(mode="json")},
            requested_by=requested_by,
        )

    async def prepare_delete(
        self, account_id: str, event_id: str, *, requested_by: str | None = None
    ) -> ApprovalToken:
        self._require(Capability.CALENDAR_WRITE)
        return await self._actions.prepare(
            ActionType.CALENDAR_DELETE,
            summary=f"Delete event {event_id}",
            target={"account_id": account_id, "event_id": event_id},
            requested_by=requested_by,
        )

    async def prepare_respond(
        self,
        account_id: str,
        event_id: str,
        response: EventResponse,
        *,
        requested_by: str | None = None,
    ) -> ApprovalToken:
        self._require(Capability.CALENDAR_WRITE)
        return await self._actions.prepare(
            ActionType.CALENDAR_RESPOND,
            summary=f"RSVP {response.value} to event {event_id}",
            target={"account_id": account_id, "event_id": event_id},
            payload={"response": response.value},
            requested_by=requested_by,
        )
