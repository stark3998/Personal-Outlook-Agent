"""SyncService — pull provider data into the local cache/index (on-demand).

Milestone 12 provides on-demand synchronization; background (launchd) and incremental
delta sync build on this. Outlook remains the source of truth — the cache is rebuildable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from outlook_agent.providers.base import OutlookProvider
from outlook_agent.storage.database import session_scope
from outlook_agent.storage.models import SyncState
from outlook_agent.storage.repositories import EmailCacheRepository


class SyncResult(BaseModel):
    """Summary of a sync run."""

    account_id: str
    folder_id: str
    synced: int
    cache_total: int
    at: datetime


class SyncService:
    """Synchronize folders into the SQLite cache on demand."""

    def __init__(
        self,
        provider: OutlookProvider,
        cache: EmailCacheRepository,
        factory: sessionmaker[Session],
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._factory = factory

    async def sync_folder(self, account_id: str, folder_id: str, *, limit: int = 200) -> SyncResult:
        """Pull summaries for a folder into the cache and record sync state."""
        summaries = await self._provider.list_emails(account_id, folder_id, limit=limit)
        for summary in summaries:
            self._cache.upsert(summary)
        now = datetime.now(UTC)
        self._record_state(account_id, folder_id, len(summaries), now)
        return SyncResult(
            account_id=account_id,
            folder_id=folder_id,
            synced=len(summaries),
            cache_total=self._cache.count(),
            at=now,
        )

    def _record_state(self, account_id: str, folder_id: str, count: int, when: datetime) -> None:
        with session_scope(self._factory) as session:
            state = session.execute(
                select(SyncState).where(
                    SyncState.account_id == account_id,
                    SyncState.folder_id == folder_id,
                )
            ).scalar_one_or_none()
            if state is None:
                state = SyncState(account_id=account_id, folder_id=folder_id)
                session.add(state)
            state.last_synced_at = when
            state.last_item_count = count
