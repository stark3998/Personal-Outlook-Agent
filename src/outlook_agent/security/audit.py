"""Audit log — records what was attempted, approved, and executed.

Audit events intentionally record *metadata only*. Message bodies, credentials, tokens,
and attachment contents are never written to the audit log.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from outlook_agent.domain import ActionResult, ActionType, RiskLevel


class AuditEvent(BaseModel):
    """A single audit record."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event: str  # e.g. "prepare" | "confirm" | "cancel" | "execute"
    action_id: str
    action_type: ActionType
    risk_level: RiskLevel
    actor: str | None = None
    approved: bool | None = None
    target: dict[str, Any] | None = None
    result: ActionResult | None = None
    correlation_id: str | None = None


@runtime_checkable
class AuditLog(Protocol):
    """Append-only audit sink."""

    async def record(self, event: AuditEvent) -> None:
        """Append an audit event."""
        ...

    async def events(self) -> list[AuditEvent]:
        """Return all recorded events (newest last)."""
        ...


class InMemoryAuditLog:
    """Process-local audit log."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    async def events(self) -> list[AuditEvent]:
        return list(self._events)
