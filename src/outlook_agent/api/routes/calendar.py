"""Calendar routes (read) and gated create/delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from outlook_agent.api.dependencies import get_calendar_service
from outlook_agent.domain import (
    ApprovalToken,
    Calendar,
    CalendarEvent,
    CalendarEventInput,
)
from outlook_agent.services.calendar import CalendarService

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


@router.get("/calendars", response_model=list[Calendar])
async def list_calendars(
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    account_id: Annotated[str | None, Query()] = None,
) -> list[Calendar]:
    """List calendars."""
    return await service.list_calendars(account_id)


@router.get("/events", response_model=list[CalendarEvent])
async def list_events(
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    account_id: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> list[CalendarEvent]:
    """List upcoming events."""
    return await service.list_events(account_id, limit=limit)


@router.get("/events/{event_id}", response_model=CalendarEvent)
async def get_event(
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    event_id: str,
    account_id: Annotated[str, Query()],
) -> CalendarEvent:
    """Fetch an event."""
    return await service.get_event(account_id, event_id)


@router.post("/events", response_model=ApprovalToken)
async def prepare_create_event(
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    account_id: Annotated[str, Query()],
    data: CalendarEventInput,
) -> ApprovalToken:
    """Prepare a gated event creation; confirm via /api/v1/actions/{id}/confirm."""
    return await service.prepare_create(account_id, data)
