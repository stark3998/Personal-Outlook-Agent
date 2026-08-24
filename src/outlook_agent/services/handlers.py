"""ActionHandlers — bind gated operations to provider writes.

Each handler snapshots its target (for the stale-state check) and executes the provider
call on confirmation. Handlers are the only place the ActionService touches a provider for
writes; the service itself stays provider-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from outlook_agent.domain import (
    Action,
    ActionResult,
    ActionType,
    CalendarEventInput,
    EmailRef,
    EventResponse,
)
from outlook_agent.providers.base import OutlookProvider

if TYPE_CHECKING:
    from outlook_agent.services.actions import ActionHandler


def _ref(action: Action) -> EmailRef:
    assert action.target is not None
    return EmailRef.model_validate(action.target)


class SendDraftHandler:
    action_type = ActionType.SEND

    def __init__(self, provider: OutlookProvider) -> None:
        self._p = provider

    async def snapshot(self, action: Action) -> str | None:
        t = action.target or {}
        draft = await self._p.get_draft(t["account_id"], t["draft_id"])
        return f"{draft.subject}|{draft.body_text}"

    async def execute(self, action: Action) -> ActionResult:
        t = action.target or {}
        await self._p.send_draft(t["account_id"], t["draft_id"])
        return ActionResult(success=True, detail="sent")


class _EmailSnapshotHandler:
    """Base for handlers operating on a single message, with a state snapshot."""

    action_type: ActionType

    def __init__(self, provider: OutlookProvider) -> None:
        self._p = provider

    async def snapshot(self, action: Action) -> str | None:
        email = await self._p.get_email(_ref(action))
        return f"{email.ref.folder_id}|{email.is_read}|{email.subject}"


class DeleteEmailHandler(_EmailSnapshotHandler):
    action_type = ActionType.DELETE

    async def execute(self, action: Action) -> ActionResult:
        await self._p.delete_email(_ref(action))
        return ActionResult(success=True, detail="deleted")


class MoveEmailHandler(_EmailSnapshotHandler):
    action_type = ActionType.MOVE

    async def execute(self, action: Action) -> ActionResult:
        await self._p.move_email(_ref(action), target_folder_id=action.payload["target_folder_id"])
        return ActionResult(success=True, detail="moved")


class ArchiveEmailHandler(_EmailSnapshotHandler):
    action_type = ActionType.ARCHIVE

    async def execute(self, action: Action) -> ActionResult:
        await self._p.archive_email(_ref(action))
        return ActionResult(success=True, detail="archived")


class JunkEmailHandler(_EmailSnapshotHandler):
    action_type = ActionType.JUNK

    async def execute(self, action: Action) -> ActionResult:
        await self._p.junk_email(_ref(action))
        return ActionResult(success=True, detail="junked")


class DeleteFolderHandler:
    action_type = ActionType.FOLDER_DELETE

    def __init__(self, provider: OutlookProvider) -> None:
        self._p = provider

    async def snapshot(self, action: Action) -> str | None:
        return None  # folder identity is stable; no meaningful pre-read snapshot

    async def execute(self, action: Action) -> ActionResult:
        t = action.target or {}
        await self._p.delete_folder(t["account_id"], t["folder_id"])
        return ActionResult(success=True, detail="folder deleted")


class EmptyFolderHandler(DeleteFolderHandler):
    action_type = ActionType.FOLDER_EMPTY

    async def execute(self, action: Action) -> ActionResult:
        t = action.target or {}
        await self._p.empty_folder(t["account_id"], t["folder_id"])
        return ActionResult(success=True, detail="folder emptied")


class CreateEventHandler:
    action_type = ActionType.CALENDAR_CREATE

    def __init__(self, provider: OutlookProvider) -> None:
        self._p = provider

    async def snapshot(self, action: Action) -> str | None:
        return None

    async def execute(self, action: Action) -> ActionResult:
        t = action.target or {}
        data = CalendarEventInput.model_validate(action.payload["event"])
        event = await self._p.create_event(t["account_id"], data)
        return ActionResult(success=True, detail="event created", data={"event_id": event.event_id})


class DeleteEventHandler:
    action_type = ActionType.CALENDAR_DELETE

    def __init__(self, provider: OutlookProvider) -> None:
        self._p = provider

    async def snapshot(self, action: Action) -> str | None:
        t = action.target or {}
        event = await self._p.get_event(t["account_id"], t["event_id"])
        return f"{event.subject}|{event.start}"

    async def execute(self, action: Action) -> ActionResult:
        t = action.target or {}
        await self._p.delete_event(t["account_id"], t["event_id"])
        return ActionResult(success=True, detail="event deleted")


class RespondEventHandler:
    action_type = ActionType.CALENDAR_RESPOND

    def __init__(self, provider: OutlookProvider) -> None:
        self._p = provider

    async def snapshot(self, action: Action) -> str | None:
        return None

    async def execute(self, action: Action) -> ActionResult:
        t = action.target or {}
        await self._p.respond_to_event(
            t["account_id"], t["event_id"], EventResponse(action.payload["response"])
        )
        return ActionResult(success=True, detail="responded")


def default_handlers(provider: OutlookProvider) -> list[ActionHandler]:
    """Construct the standard set of handlers bound to a provider."""
    return [
        SendDraftHandler(provider),
        DeleteEmailHandler(provider),
        MoveEmailHandler(provider),
        ArchiveEmailHandler(provider),
        JunkEmailHandler(provider),
        DeleteFolderHandler(provider),
        EmptyFolderHandler(provider),
        CreateEventHandler(provider),
        DeleteEventHandler(provider),
        RespondEventHandler(provider),
    ]
