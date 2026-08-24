"""SQLite-backed AuditLog — append-only persisted audit trail."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from outlook_agent.security.audit import AuditEvent

from .database import session_scope
from .models import AuditRecord


class SqliteAuditLog:
    """Persistent append-only audit log."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    async def record(self, event: AuditEvent) -> None:
        await asyncio.to_thread(self._record, event)

    async def events(self) -> list[AuditEvent]:
        return await asyncio.to_thread(self._events)

    def _record(self, event: AuditEvent) -> None:
        with session_scope(self._factory) as session:
            session.add(
                AuditRecord(
                    action_id=event.action_id,
                    event=event.event,
                    payload=event.model_dump_json(),
                )
            )

    def _events(self) -> list[AuditEvent]:
        with session_scope(self._factory) as session:
            records = session.execute(select(AuditRecord).order_by(AuditRecord.id)).scalars().all()
            return [AuditEvent.model_validate_json(r.payload) for r in records]
