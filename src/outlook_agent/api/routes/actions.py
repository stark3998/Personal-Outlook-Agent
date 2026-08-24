"""Action confirmation routes — the gated write flow (confirm/cancel/pending)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from outlook_agent.api.dependencies import get_action_service
from outlook_agent.domain import Action, ActionResult
from outlook_agent.services.actions import ActionService

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])


class ConfirmRequest(BaseModel):
    token: str
    authorized_by: str | None = None


@router.get("/pending", response_model=list[Action])
async def pending(
    service: Annotated[ActionService, Depends(get_action_service)],
) -> list[Action]:
    """List actions awaiting confirmation."""
    return await service.pending()


@router.post("/{action_id}/confirm", response_model=ActionResult)
async def confirm(
    action_id: str,
    body: ConfirmRequest,
    service: Annotated[ActionService, Depends(get_action_service)],
) -> ActionResult:
    """Confirm and execute a prepared action."""
    return await service.confirm(action_id, body.token, authorized_by=body.authorized_by)


@router.post("/{action_id}/cancel", status_code=204)
async def cancel(
    action_id: str,
    service: Annotated[ActionService, Depends(get_action_service)],
) -> None:
    """Cancel a pending action."""
    await service.cancel(action_id)
