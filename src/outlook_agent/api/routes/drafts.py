"""Draft routes — compose drafts (safe) and prepare a gated send."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from outlook_agent.api.dependencies import get_draft_service
from outlook_agent.domain import ApprovalToken, Draft, DraftInput, EmailRef, ProviderName
from outlook_agent.services.drafts import DraftService

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])


@router.get("", response_model=list[Draft])
async def list_drafts(
    service: Annotated[DraftService, Depends(get_draft_service)],
    account_id: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> list[Draft]:
    """List saved drafts."""
    return await service.list_drafts(account_id, limit=limit)


@router.post("", response_model=Draft)
async def create_draft(
    service: Annotated[DraftService, Depends(get_draft_service)],
    account_id: Annotated[str, Query()],
    data: DraftInput,
) -> Draft:
    """Create a new draft."""
    return await service.create_draft(account_id, data)


@router.get("/{draft_id}", response_model=Draft)
async def get_draft(
    service: Annotated[DraftService, Depends(get_draft_service)],
    draft_id: str,
    account_id: Annotated[str, Query()],
) -> Draft:
    """Fetch a draft."""
    return await service.get_draft(account_id, draft_id)


@router.post("/{draft_id}/send", response_model=ApprovalToken)
async def prepare_send(
    service: Annotated[DraftService, Depends(get_draft_service)],
    draft_id: str,
    account_id: Annotated[str, Query()],
) -> ApprovalToken:
    """Prepare a gated send; confirm via /api/v1/actions/{id}/confirm."""
    return await service.prepare_send(account_id, draft_id)


@router.post("/reply", response_model=Draft)
async def reply(
    service: Annotated[DraftService, Depends(get_draft_service)],
    account_id: Annotated[str, Query()],
    folder_id: Annotated[str, Query()],
    item_id: Annotated[str, Query()],
    reply_all: Annotated[bool, Query()] = False,
    body: Annotated[str | None, Query()] = None,
) -> Draft:
    """Create a reply/reply-all draft (does not send)."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    return await service.reply(ref, reply_all=reply_all, body=body)
