"""Convenience constructors for the storage/sync stack."""

from __future__ import annotations

from outlook_agent.providers.base import OutlookProvider
from outlook_agent.services.sync import SyncService

from .database import create_db_engine, init_db, make_session_factory
from .repositories import EmailCacheRepository


def build_sync_service(
    provider: OutlookProvider, *, url: str = "sqlite:///outlook_agent.db"
) -> SyncService:
    """Open (creating if needed) the cache database and return a SyncService."""
    engine = create_db_engine(url)
    init_db(engine)
    factory = make_session_factory(engine)
    cache = EmailCacheRepository(factory)
    return SyncService(provider, cache, factory)
