"""Unit tests for the ActionService prepare/confirm/cancel lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from outlook_agent.domain import Action, ActionResult, ActionStatus, ActionType, RiskLevel
from outlook_agent.security.approvals import InMemoryApprovalStore
from outlook_agent.security.audit import InMemoryAuditLog
from outlook_agent.services.actions import (
    ActionExpired,
    ActionNotFound,
    ActionService,
    ActionStale,
    InvalidApprovalToken,
    NoHandlerRegistered,
)


class RecordingHandler:
    """A handler whose target state and execution outcome are controllable."""

    def __init__(self, action_type: ActionType = ActionType.DELETE) -> None:
        self.action_type = action_type
        self.state = "v1"
        self.executed = 0

    async def snapshot(self, action: Action) -> str | None:
        return self.state

    async def execute(self, action: Action) -> ActionResult:
        self.executed += 1
        return ActionResult(success=True, detail="done")


def _clock():
    holder = {"now": datetime(2026, 1, 1, tzinfo=UTC)}

    def now() -> datetime:
        return holder["now"]

    return holder, now


def _service(handler: RecordingHandler, now=None) -> ActionService:
    return ActionService(
        InMemoryApprovalStore(),
        InMemoryAuditLog(),
        [handler],
        clock=now or (lambda: datetime(2026, 1, 1, tzinfo=UTC)),
    )


async def test_prepare_and_confirm_executes() -> None:
    handler = RecordingHandler()
    service = _service(handler)
    token = await service.prepare(ActionType.DELETE, summary="delete msg", target={"id": "1"})
    result = await service.confirm(token.action_id, token.token)
    assert result.success is True
    assert handler.executed == 1


async def test_confirm_rejects_bad_token() -> None:
    handler = RecordingHandler()
    service = _service(handler)
    token = await service.prepare(ActionType.DELETE, summary="x")
    with pytest.raises(InvalidApprovalToken):
        await service.confirm(token.action_id, "wrong-token")
    assert handler.executed == 0


async def test_confirm_rejects_stale_target() -> None:
    handler = RecordingHandler()
    service = _service(handler)
    token = await service.prepare(ActionType.DELETE, summary="x")
    handler.state = "v2"  # target changed after preparation
    with pytest.raises(ActionStale):
        await service.confirm(token.action_id, token.token)
    assert handler.executed == 0


async def test_confirm_rejects_expired() -> None:
    handler = RecordingHandler()
    holder, now = _clock()
    service = _service(handler, now=now)
    token = await service.prepare(ActionType.DELETE, summary="x")
    holder["now"] = holder["now"] + timedelta(hours=1)
    with pytest.raises(ActionExpired):
        await service.confirm(token.action_id, token.token)


async def test_double_confirm_is_rejected() -> None:
    handler = RecordingHandler()
    service = _service(handler)
    token = await service.prepare(ActionType.DELETE, summary="x")
    await service.confirm(token.action_id, token.token)
    with pytest.raises(Exception):
        await service.confirm(token.action_id, token.token)
    assert handler.executed == 1


async def test_cancel_prevents_execution() -> None:
    handler = RecordingHandler()
    service = _service(handler)
    token = await service.prepare(ActionType.DELETE, summary="x")
    await service.cancel(token.action_id)
    with pytest.raises(Exception):
        await service.confirm(token.action_id, token.token)
    assert handler.executed == 0


async def test_unknown_action_raises() -> None:
    service = _service(RecordingHandler())
    with pytest.raises(ActionNotFound):
        await service.confirm("nope", "nope")


async def test_missing_handler_raises() -> None:
    service = ActionService(InMemoryApprovalStore(), InMemoryAuditLog(), [])
    with pytest.raises(NoHandlerRegistered):
        await service.prepare(ActionType.SEND, summary="x")


async def test_risk_level_assigned_from_policy() -> None:
    handler = RecordingHandler(ActionType.DELETE)
    service = _service(handler)
    token = await service.prepare(ActionType.DELETE, summary="x")
    assert token.risk_level is RiskLevel.CRITICAL


async def test_pending_tracks_open_actions() -> None:
    handler = RecordingHandler()
    service = _service(handler)
    token = await service.prepare(ActionType.DELETE, summary="x")
    pending = await service.pending()
    assert [a.action_id for a in pending] == [token.action_id]
    await service.confirm(token.action_id, token.token)
    assert await service.pending() == []


async def test_audit_records_prepare_and_confirm() -> None:
    handler = RecordingHandler()
    store, audit = InMemoryApprovalStore(), InMemoryAuditLog()
    service = ActionService(store, audit, [handler])
    token = await service.prepare(ActionType.DELETE, summary="x", requested_by="me")
    await service.confirm(token.action_id, token.token, authorized_by="me")
    events = await audit.events()
    assert [e.event for e in events] == ["prepare", "confirm"]
    assert events[-1].approved is True
    assert events[-1].result is not None and events[-1].result.success is True


def test_status_enum_roundtrip() -> None:
    assert ActionStatus("executed") is ActionStatus.EXECUTED
