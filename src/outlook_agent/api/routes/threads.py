"""Thread route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from outlook_agent.api.dependencies import get_thread_service
from outlook_agent.domain import Thread
from outlook_agent.services.threads import ThreadService

router = APIRouter(prefix="/api/v1", tags=["threads"])


@router.get("/threads/{conversation_id}", response_model=Thread)
async def get_thread(
    service: Annotated[ThreadService, Depends(get_thread_service)],
    conversation_id: str,
    account_id: Annotated[str | None, Query()] = None,
) -> Thread:
    """Return the reconstructed thread for a conversation id."""
    return await service.get_thread(conversation_id, account_id=account_id)
