"""Contacts, tasks, and notes read routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from outlook_agent.api.dependencies import (
    get_contact_service,
    get_note_service,
    get_task_service,
)
from outlook_agent.domain import Contact, Note, Task
from outlook_agent.services.pim import ContactService, NoteService, TaskService

router = APIRouter(prefix="/api/v1", tags=["pim"])


@router.get("/contacts", response_model=list[Contact])
async def list_contacts(
    service: Annotated[ContactService, Depends(get_contact_service)],
    account_id: Annotated[str, Query()],
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Contact]:
    """List or search contacts."""
    if q:
        return await service.search_contacts(q, account_id=account_id, limit=limit)
    return await service.list_contacts(account_id, limit=limit)


@router.get("/tasks", response_model=list[Task])
async def list_tasks(
    service: Annotated[TaskService, Depends(get_task_service)],
    account_id: Annotated[str, Query()],
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Task]:
    """List or search tasks."""
    if q:
        return await service.search_tasks(q, account_id=account_id, limit=limit)
    return await service.list_tasks(account_id, limit=limit)


@router.get("/notes", response_model=list[Note])
async def list_notes(
    service: Annotated[NoteService, Depends(get_note_service)],
    account_id: Annotated[str, Query()],
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Note]:
    """List or search notes."""
    if q:
        return await service.search_notes(q, account_id=account_id, limit=limit)
    return await service.list_notes(account_id, limit=limit)
