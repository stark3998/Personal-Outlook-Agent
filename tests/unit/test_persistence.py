"""Tests for the persistent SQLite approval store + audit log across service instances."""

from __future__ import annotations

import pytest

from outlook_agent.domain import ActionType, DraftInput
from outlook_agent.security.approvals import new_action_id
from outlook_agent.services.actions import ActionService
from outlook_agent.services.handlers import default_handlers
from outlook_agent.storage.approvals import SqliteApprovalStore
from outlook_agent.storage.audit import SqliteAuditLog
from outlook_agent.storage.database import (
    create_db_engine,
    init_db,
    make_session_factory,
)
from tests.conftest import FakeOutlookProvider


@pytest.fixture
def factory(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'actions.db'}")
    init_db(engine)
    return make_session_factory(engine)


async def test_prepare_and_confirm_across_instances(factory) -> None:
    provider = FakeOutlookProvider()
    store = SqliteApprovalStore(factory)
    audit = SqliteAuditLog(factory)

    # "Process A" prepares.
    svc_a = ActionService(store, audit, default_handlers(provider))
    draft = await provider.create_draft("1", DraftInput())
    token = await svc_a.prepare(
        ActionType.SEND, summary="send", target={"account_id": "1", "draft_id": draft.draft_id}
    )

    # A fresh ActionService (simulating another process) sees the pending action and confirms.
    svc_b = ActionService(SqliteApprovalStore(factory), SqliteAuditLog(factory),
                          default_handlers(provider))
    pending = await svc_b.pending()
    assert [a.action_id for a in pending] == [token.action_id]
    result = await svc_b.confirm(token.action_id, token.token)
    assert result.success is True
    assert draft.draft_id in provider.sent


async def test_audit_persists(factory) -> None:
    provider = FakeOutlookProvider()
    store, audit = SqliteApprovalStore(factory), SqliteAuditLog(factory)
    svc = ActionService(store, audit, default_handlers(provider))
    token = await svc.prepare(
        ActionType.DELETE,
        summary="del",
        target={
            "provider": "outlook.applescript",
            "account_id": "1",
            "folder_id": "10",
            "item_id": "100",
        },
    )
    await svc.confirm(token.action_id, token.token)
    events = await SqliteAuditLog(factory).events()
    assert [e.event for e in events] == ["prepare", "confirm"]


async def test_unknown_action_not_persisted(factory) -> None:
    store = SqliteApprovalStore(factory)
    assert await store.get(new_action_id()) is None
