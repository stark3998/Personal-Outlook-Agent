"""Mail listing, search, and single-message routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from outlook_agent.api.dependencies import get_mail_service
from outlook_agent.domain import Email, EmailRef, EmailSummary, ProviderName
from outlook_agent.services.mail import MailService

router = APIRouter(prefix="/api/v1", tags=["mail"])


@router.get("/mail", response_model=list[EmailSummary])
async def list_mail(
    service: Annotated[MailService, Depends(get_mail_service)],
    account_id: Annotated[str, Query()],
    folder_id: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EmailSummary]:
    """List message summaries in a folder."""
    return await service.list_emails(account_id, folder_id, limit=limit, offset=offset)


@router.get("/mail/search", response_model=list[EmailSummary])
async def search_mail(
    service: Annotated[MailService, Depends(get_mail_service)],
    q: Annotated[str, Query(min_length=1)],
    account_id: Annotated[str | None, Query()] = None,
    folder_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
) -> list[EmailSummary]:
    """Search messages by subject/sender/content."""
    return await service.search_emails(q, account_id=account_id, folder_id=folder_id, limit=limit)


@router.get("/mail/{item_id}", response_model=Email)
async def get_mail(
    service: Annotated[MailService, Depends(get_mail_service)],
    item_id: str,
    account_id: Annotated[str, Query()],
    folder_id: Annotated[str, Query()],
    conversation_id: Annotated[str | None, Query()] = None,
) -> Email:
    """Fetch a full message. Requires account and folder context to resolve identity."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
        conversation_id=conversation_id,
    )
    return await service.get_email(ref)
