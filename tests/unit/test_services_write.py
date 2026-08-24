"""Unit tests for write services gated through the ActionService."""

from __future__ import annotations

import pytest

from outlook_agent.domain import (
    CalendarEventInput,
    DraftBody,
    DraftInput,
    EmailRef,
    ProviderName,
)
from outlook_agent.security.approvals import InMemoryApprovalStore
from outlook_agent.security.audit import InMemoryAuditLog
from outlook_agent.services.actions import ActionService
from outlook_agent.services.calendar import CalendarService
from outlook_agent.services.drafts import DraftService
from outlook_agent.services.handlers import default_handlers
from outlook_agent.services.intelligence import IntelligenceService
from outlook_agent.services.mail import MailService
from outlook_agent.services.threads import ThreadService
from tests.conftest import FakeLLMProvider, FakeOutlookProvider

_P = ProviderName.OUTLOOK_APPLESCRIPT


def _actions(provider: FakeOutlookProvider) -> ActionService:
    return ActionService(InMemoryApprovalStore(), InMemoryAuditLog(), default_handlers(provider))


def _ref() -> EmailRef:
    return EmailRef(provider=_P, account_id="1", folder_id="10", item_id="100")


async def test_create_and_list_drafts(fake_provider: FakeOutlookProvider) -> None:
    service = DraftService(fake_provider, _actions(fake_provider))
    draft = await service.create_draft("1", DraftInput(subject="Hi", body=DraftBody(text="yo")))
    assert draft.subject == "Hi"
    listed = await service.list_drafts("1")
    assert any(d.draft_id == draft.draft_id for d in listed)


async def test_prepare_send_then_confirm_sends(fake_provider: FakeOutlookProvider) -> None:
    actions = _actions(fake_provider)
    service = DraftService(fake_provider, actions)
    draft = await service.create_draft("1", DraftInput(subject="Hi", body=DraftBody(text="yo")))
    token = await service.prepare_send("1", draft.draft_id)
    result = await actions.confirm(token.action_id, token.token)
    assert result.success is True
    assert draft.draft_id in fake_provider.sent


async def test_reply_creates_draft_without_sending(fake_provider: FakeOutlookProvider) -> None:
    service = DraftService(fake_provider, _actions(fake_provider))
    draft = await service.reply(_ref(), body="thanks")
    assert draft.draft_id
    assert fake_provider.sent == []


async def test_mark_read_is_direct(fake_provider: FakeOutlookProvider) -> None:
    service = MailService(fake_provider, _actions(fake_provider))
    await service.mark_read(_ref(), read=True)
    assert ("set_read", "100", True) in fake_provider.ops


async def test_prepare_delete_then_confirm_deletes(fake_provider: FakeOutlookProvider) -> None:
    actions = _actions(fake_provider)
    service = MailService(fake_provider, actions)
    token = await service.prepare_delete(_ref())
    await actions.confirm(token.action_id, token.token)
    assert ("delete", "100") in fake_provider.ops


async def test_prepare_delete_requires_action_service(fake_provider: FakeOutlookProvider) -> None:
    service = MailService(fake_provider)  # no ActionService injected
    with pytest.raises(RuntimeError):
        await service.prepare_delete(_ref())


async def test_calendar_create_gated(fake_provider: FakeOutlookProvider) -> None:
    from datetime import UTC, datetime

    actions = _actions(fake_provider)
    service = CalendarService(fake_provider, actions)
    data = CalendarEventInput(
        subject="Sync",
        start=datetime(2026, 2, 1, 9, tzinfo=UTC),
        end=datetime(2026, 2, 1, 10, tzinfo=UTC),
    )
    token = await service.prepare_create("1", data)
    result = await actions.confirm(token.action_id, token.token)
    assert result.success and result.data["event_id"] == "enew"


async def test_intelligence_summarize_and_extract(fake_provider: FakeOutlookProvider) -> None:
    actions = _actions(fake_provider)
    mail = MailService(fake_provider, actions)
    threads = ThreadService(fake_provider)
    drafts = DraftService(fake_provider, actions)
    svc = IntelligenceService(FakeLLMProvider(), mail, threads, drafts)
    assert await svc.summarize_email(_ref()) == "SUMMARY"
    items = await svc.extract_action_items(_ref())
    assert len(items.items) == 2


async def test_prepare_reply_returns_proposal_and_optional_draft(
    fake_provider: FakeOutlookProvider,
) -> None:
    actions = _actions(fake_provider)
    mail = MailService(fake_provider, actions)
    drafts = DraftService(fake_provider, actions)
    svc = IntelligenceService(FakeLLMProvider(), mail, ThreadService(fake_provider), drafts)
    proposal = await svc.prepare_reply(_ref(), "be brief", create_draft=True)
    assert proposal.body
    assert proposal.draft is not None
    assert fake_provider.sent == []  # never sends
