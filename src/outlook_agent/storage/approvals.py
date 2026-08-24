"""SQLite-backed ApprovalStore — prepared actions survive restarts and processes.

Satisfies the ``ApprovalStore`` protocol. Blocking SQLAlchemy calls are dispatched to a
worker thread so the async ActionService is never blocked.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from outlook_agent.domain import Action, ActionStatus

from .database import session_scope
from .models import ActionRecord


class SqliteApprovalStore:
    """Persistent approval store keyed by action id."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    async def save(self, action: Action, token: str) -> None:
        await asyncio.to_thread(self._save, action, token)

    async def get(self, action_id: str) -> Action | None:
        return await asyncio.to_thread(self._get, action_id)

    async def token_for(self, action_id: str) -> str | None:
        return await asyncio.to_thread(self._token_for, action_id)

    async def update(self, action: Action) -> None:
        await asyncio.to_thread(self._update, action)

    async def pending(self) -> list[Action]:
        return await asyncio.to_thread(self._pending)

    # --- blocking implementations ------------------------------------------------------

    def _save(self, action: Action, token: str) -> None:
        with session_scope(self._factory) as session:
            session.merge(
                ActionRecord(
                    action_id=action.action_id,
                    status=action.status.value,
                    token=token,
                    payload=action.model_dump_json(),
                )
            )

    def _get(self, action_id: str) -> Action | None:
        with session_scope(self._factory) as session:
            record = session.get(ActionRecord, action_id)
            return Action.model_validate_json(record.payload) if record else None

    def _token_for(self, action_id: str) -> str | None:
        with session_scope(self._factory) as session:
            record = session.get(ActionRecord, action_id)
            return record.token if record else None

    def _update(self, action: Action) -> None:
        with session_scope(self._factory) as session:
            record = session.get(ActionRecord, action.action_id)
            if record is not None:
                record.status = action.status.value
                record.payload = action.model_dump_json()

    def _pending(self) -> list[Action]:
        with session_scope(self._factory) as session:
            records = (
                session.execute(
                    select(ActionRecord).where(ActionRecord.status == ActionStatus.PENDING.value)
                )
                .scalars()
                .all()
            )
            return [Action.model_validate_json(r.payload) for r in records]
