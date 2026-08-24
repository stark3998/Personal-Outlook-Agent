"""ActionService — the mandatory gate for every write/destructive operation.

Flow (see docs/architecture.md and the project spec, Phase 10):

    prepare(...)  -> ApprovalToken        (snapshot target, store PENDING action)
    confirm(id, token)                    (validate -> re-read -> compare hash -> execute)
    cancel(id)                            (abandon a pending action)

The LLM may only *propose* actions via ``prepare``; execution requires a valid
``ApprovalToken`` presented to ``confirm``. Actions expire, and a target that changed
since preparation is rejected as stale.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from outlook_agent.domain import (
    Action,
    ActionResult,
    ActionStatus,
    ActionType,
    ApprovalToken,
    RiskLevel,
)
from outlook_agent.observability import get_logger
from outlook_agent.security import policy
from outlook_agent.security.approvals import ApprovalStore, new_action_id, new_token
from outlook_agent.security.audit import AuditEvent, AuditLog

_log = get_logger("outlook_agent.actions")


class ActionError(Exception):
    """Base class for action-lifecycle failures."""


class ActionNotFound(ActionError):
    """The referenced action id is unknown."""


class ActionExpired(ActionError):
    """The action's confirmation window has elapsed."""


class ActionStale(ActionError):
    """The target changed between preparation and confirmation."""


class InvalidApprovalToken(ActionError):
    """The presented confirmation token does not match."""


class ActionAlreadyResolved(ActionError):
    """The action is no longer pending (already executed/cancelled/expired)."""


class NoHandlerRegistered(ActionError):
    """No handler is registered for the action type."""


@runtime_checkable
class ActionHandler(Protocol):
    """Executes a specific :class:`ActionType` and snapshots its target.

    Handlers are the only place that knows how to touch a provider for writes; the
    ActionService stays provider-agnostic.
    """

    action_type: ActionType

    async def snapshot(self, action: Action) -> str | None:
        """Return a canonical string describing the current target state (or ``None``)."""
        ...

    async def execute(self, action: Action) -> ActionResult:
        """Perform the operation and return its result."""
        ...


def _hash(snapshot: str | None) -> str | None:
    if snapshot is None:
        return None
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


class ActionService:
    """Centralized prepare/confirm/cancel engine for controlled operations."""

    def __init__(
        self,
        store: ApprovalStore,
        audit: AuditLog,
        handlers: Iterable[ActionHandler] = (),
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._audit = audit
        self._clock = clock
        self._handlers: dict[ActionType, ActionHandler] = {}
        for handler in handlers:
            self.register(handler)

    def register(self, handler: ActionHandler) -> None:
        """Register a handler for its action type."""
        self._handlers[handler.action_type] = handler

    def _handler(self, action_type: ActionType) -> ActionHandler:
        handler = self._handlers.get(action_type)
        if handler is None:
            raise NoHandlerRegistered(f"No handler registered for {action_type.value}")
        return handler

    async def prepare(
        self,
        action_type: ActionType,
        *,
        summary: str,
        target: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        requested_by: str | None = None,
        correlation_id: str | None = None,
    ) -> ApprovalToken:
        """Prepare an action: snapshot the target and store it as PENDING."""
        handler = self._handler(action_type)
        risk = policy.risk_for(action_type)
        now = self._clock()
        action = Action(
            action_id=new_action_id(),
            action_type=action_type,
            risk_level=risk,
            summary=summary,
            target=target,
            payload=payload or {},
            requested_by=requested_by,
            created_at=now,
            expires_at=now + policy.confirmation_ttl(risk),
        )
        action.target_state_hash = _hash(await handler.snapshot(action))
        token = new_token()
        await self._store.save(action, token)
        _log.info(
            "action_prepared",
            action_id=action.action_id,
            action_type=action_type.value,
            risk=risk.value,
        )
        await self._audit.record(
            AuditEvent(
                event="prepare",
                action_id=action.action_id,
                action_type=action_type,
                risk_level=risk,
                actor=requested_by,
                target=target,
                correlation_id=correlation_id,
            )
        )
        return ApprovalToken(
            action_id=action.action_id,
            token=token,
            action_type=action_type,
            risk_level=risk,
            summary=summary,
            expires_at=action.expires_at,
        )

    async def confirm(
        self,
        action_id: str,
        token: str,
        *,
        authorized_by: str | None = None,
        correlation_id: str | None = None,
    ) -> ActionResult:
        """Confirm and execute a prepared action after full validation."""
        action = await self._store.get(action_id)
        if action is None:
            raise ActionNotFound(action_id)
        if action.status is not ActionStatus.PENDING:
            raise ActionAlreadyResolved(f"{action_id} is {action.status.value}")

        expected = await self._store.token_for(action_id)
        if expected is None or not _consteq(expected, token):
            raise InvalidApprovalToken(action_id)

        if self._clock() >= action.expires_at:
            await self._transition(action, ActionStatus.EXPIRED)
            raise ActionExpired(action_id)

        handler = self._handler(action.action_type)
        current_hash = _hash(await handler.snapshot(action))
        if current_hash != action.target_state_hash:
            await self._transition(action, ActionStatus.STALE)
            raise ActionStale(action_id)

        try:
            result = await handler.execute(action)
        except Exception as exc:  # provider/handler failure — record and surface.
            action.result = ActionResult(success=False, detail=str(exc))
            await self._transition(action, ActionStatus.FAILED)
            await self._audit_confirm(
                action, approved=True, actor=authorized_by, correlation_id=correlation_id
            )
            raise

        action.result = result
        await self._transition(
            action, ActionStatus.EXECUTED if result.success else ActionStatus.FAILED
        )
        _log.info(
            "action_confirmed",
            action_id=action.action_id,
            action_type=action.action_type.value,
            success=result.success,
        )
        await self._audit_confirm(
            action, approved=True, actor=authorized_by, correlation_id=correlation_id
        )
        return result

    async def cancel(self, action_id: str, *, actor: str | None = None) -> None:
        """Cancel a pending action."""
        action = await self._store.get(action_id)
        if action is None:
            raise ActionNotFound(action_id)
        if action.status is not ActionStatus.PENDING:
            raise ActionAlreadyResolved(f"{action_id} is {action.status.value}")
        await self._transition(action, ActionStatus.CANCELLED)
        await self._audit.record(
            AuditEvent(
                event="cancel",
                action_id=action.action_id,
                action_type=action.action_type,
                risk_level=action.risk_level,
                actor=actor,
                approved=False,
                target=action.target,
            )
        )

    async def pending(self) -> list[Action]:
        """Return all actions awaiting confirmation."""
        return await self._store.pending()

    async def _transition(self, action: Action, status: ActionStatus) -> None:
        action.status = status
        await self._store.update(action)

    async def _audit_confirm(
        self, action: Action, *, approved: bool, actor: str | None, correlation_id: str | None
    ) -> None:
        await self._audit.record(
            AuditEvent(
                event="confirm",
                action_id=action.action_id,
                action_type=action.action_type,
                risk_level=action.risk_level,
                actor=actor,
                approved=approved,
                target=action.target,
                result=action.result,
                correlation_id=correlation_id,
            )
        )


def _consteq(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)


# Re-exported for callers that want to catch the whole family.
__all__ = [
    "ActionAlreadyResolved",
    "ActionError",
    "ActionExpired",
    "ActionHandler",
    "ActionNotFound",
    "ActionService",
    "ActionStale",
    "InvalidApprovalToken",
    "NoHandlerRegistered",
    "RiskLevel",
]
