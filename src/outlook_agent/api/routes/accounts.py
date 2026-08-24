"""Accounts and folders routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from outlook_agent.api.dependencies import get_mail_service
from outlook_agent.domain import Account, Folder
from outlook_agent.services.mail import MailService

router = APIRouter(prefix="/api/v1", tags=["mail"])


@router.get("/accounts", response_model=list[Account])
async def list_accounts(
    service: Annotated[MailService, Depends(get_mail_service)],
) -> list[Account]:
    """List configured Outlook accounts."""
    return await service.list_accounts()


@router.get("/folders", response_model=list[Folder])
async def list_folders(
    service: Annotated[MailService, Depends(get_mail_service)],
    account_id: Annotated[str | None, Query()] = None,
) -> list[Folder]:
    """List folders, optionally scoped to one account."""
    return await service.list_folders(account_id)
