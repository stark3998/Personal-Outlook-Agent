"""Agent intelligence routes — summaries, extraction, reply proposals."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from outlook_agent.api.dependencies import get_intelligence_service
from outlook_agent.domain import EmailRef, ProviderName
from outlook_agent.services.intelligence import ActionItems, IntelligenceService, ProposedReply

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


def _ref(account_id: str, folder_id: str, item_id: str, conversation_id: str | None) -> EmailRef:
    return EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
        conversation_id=conversation_id,
    )


class PrepareReplyRequest(BaseModel):
    account_id: str
    folder_id: str
    item_id: str
    instructions: str
    create_draft: bool = False


@router.get("/summarize/email", response_model=dict)
async def summarize_email(
    service: Annotated[IntelligenceService, Depends(get_intelligence_service)],
    account_id: Annotated[str, Query()],
    folder_id: Annotated[str, Query()],
    item_id: Annotated[str, Query()],
) -> dict[str, str]:
    """Summarize a single message."""
    return {"summary": await service.summarize_email(_ref(account_id, folder_id, item_id, None))}


@router.get("/summarize/thread", response_model=dict)
async def summarize_thread(
    service: Annotated[IntelligenceService, Depends(get_intelligence_service)],
    conversation_id: Annotated[str, Query()],
    account_id: Annotated[str | None, Query()] = None,
) -> dict[str, str]:
    """Summarize a conversation."""
    return {"summary": await service.summarize_thread(conversation_id, account_id=account_id)}


@router.get("/action-items", response_model=ActionItems)
async def extract_action_items(
    service: Annotated[IntelligenceService, Depends(get_intelligence_service)],
    account_id: Annotated[str, Query()],
    folder_id: Annotated[str, Query()],
    item_id: Annotated[str, Query()],
) -> ActionItems:
    """Extract action items from a message."""
    return await service.extract_action_items(_ref(account_id, folder_id, item_id, None))


@router.post("/prepare-reply", response_model=ProposedReply)
async def prepare_reply(
    service: Annotated[IntelligenceService, Depends(get_intelligence_service)],
    body: PrepareReplyRequest,
) -> ProposedReply:
    """Generate a reply proposal (optionally saved as a draft). Never sends."""
    ref = _ref(body.account_id, body.folder_id, body.item_id, None)
    return await service.prepare_reply(ref, body.instructions, create_draft=body.create_draft)
