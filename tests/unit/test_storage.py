"""Unit tests for the SQLite cache/index and the sync service."""

from __future__ import annotations

import pytest

from outlook_agent.domain import EmailRef, EmailSummary, ProviderName, Recipient
from outlook_agent.storage.database import (
    create_db_engine,
    init_db,
    make_session_factory,
)
from outlook_agent.storage.factory import build_sync_service
from outlook_agent.storage.repositories import EmailCacheRepository
from tests.conftest import FakeOutlookProvider

_P = ProviderName.OUTLOOK_APPLESCRIPT


@pytest.fixture
def cache(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'cache.db'}")
    init_db(engine)
    return EmailCacheRepository(make_session_factory(engine))


def _summary(item_id: str, subject: str) -> EmailSummary:
    return EmailSummary(
        ref=EmailRef(provider=_P, account_id="1", folder_id="10", item_id=item_id),
        subject=subject,
        sender=Recipient(name="Al", address="al@example.com"),
        preview=f"notes regarding {subject.lower()}",
    )


def test_upsert_is_idempotent(cache: EmailCacheRepository) -> None:
    first = cache.upsert(_summary("100", "Entra rollout"))
    second = cache.upsert(_summary("100", "Entra rollout v2"))
    assert first == second
    assert cache.count() == 1


def test_fts_search_finds_by_subject(cache: EmailCacheRepository) -> None:
    cache.upsert(_summary("100", "Entra rollout"))
    cache.upsert(_summary("101", "Lunch plans"))
    results = cache.search("Entra")
    assert [r.ref.item_id for r in results] == ["100"]


def test_fts_search_finds_by_body(cache: EmailCacheRepository) -> None:
    cache.upsert(_summary("100", "Subject A"), body_text="quarterly access review")
    results = cache.search("access")
    assert [r.ref.item_id for r in results] == ["100"]


async def test_sync_folder_populates_cache(tmp_path) -> None:
    provider = FakeOutlookProvider()
    service = build_sync_service(provider, url=f"sqlite:///{tmp_path / 'sync.db'}")
    result = await service.sync_folder("1", "10")
    assert result.synced == 2
    assert result.cache_total == 2
