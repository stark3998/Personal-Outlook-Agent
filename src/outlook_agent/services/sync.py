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
    new: int = 0
    removed: int = 0
    incremental: bool = False


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
            new=len(summaries),
            cache_total=self._cache.count(),
            at=now,
        )

    async def incremental_sync(
        self,
        account_id: str,
        folder_id: str,
        *,
        limit: int = 200,
        detect_deletions: bool = False,
    ) -> SyncResult:
        """Upsert only messages newer than the last sync, optionally pruning deletions.

        Only messages received after ``last_synced_at`` are re-cached, so repeat runs are
        cheap. When ``detect_deletions`` is set, cached rows for the folder no longer
        present in the pulled window are removed (accurate only when ``limit`` covers the
        whole folder).
        """
        since = self._last_synced_at(account_id, folder_id)
        summaries = await self._provider.list_emails(account_id, folder_id, limit=limit)
        new = 0
        newest = since
        present: set[str] = set()
        for summary in summaries:
            present.add(summary.ref.item_id)
            received = summary.received_at
            if since is not None and received is not None and received <= since:
                continue
            self._cache.upsert(summary)
            new += 1
            if received is not None and (newest is None or received > newest):
                newest = received

        removed = 0
        if detect_deletions:
            removed = self._cache.prune_missing(account_id, folder_id, present)

        now = datetime.now(UTC)
        self._record_state(account_id, folder_id, len(summaries), newest or now)
        return SyncResult(
            account_id=account_id,
            folder_id=folder_id,
            synced=new,
            new=new,
            removed=removed,
            cache_total=self._cache.count(),
            at=now,
            incremental=True,
        )

    def _last_synced_at(self, account_id: str, folder_id: str) -> datetime | None:
        with session_scope(self._factory) as session:
            state = session.execute(
                select(SyncState).where(
                    SyncState.account_id == account_id,
                    SyncState.folder_id == folder_id,
                )
            ).scalar_one_or_none()
            return state.last_synced_at if state else None

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
