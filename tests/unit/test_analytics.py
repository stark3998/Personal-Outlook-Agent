"""Unit tests for the composite agent-intelligence analytics (Phase 16)."""

from __future__ import annotations

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


def _svc(provider: FakeOutlookProvider) -> IntelligenceService:
    actions = ActionService(InMemoryApprovalStore(), InMemoryAuditLog(), default_handlers(provider))
    mail = MailService(provider, actions)
    return IntelligenceService(
        FakeLLMProvider(),
        mail,
        ThreadService(provider),
        DraftService(provider, actions),
        CalendarService(provider, actions),
    )


async def test_summarize_inbox(fake_provider: FakeOutlookProvider) -> None:
    svc = _svc(fake_provider)
    assert await svc.summarize_inbox("1", "10") == "SUMMARY"


async def test_find_unanswered_returns_others_messages(fake_provider: FakeOutlookProvider) -> None:
    # Fake inbox holds messages from Alice/Bob (not me), none answered by me.
    svc = _svc(fake_provider)
    unanswered = await svc.find_unanswered("1", "10")
    assert {s.ref.item_id for s in unanswered} == {"100", "101"}


async def test_find_followups_empty_when_i_am_not_last(fake_provider: FakeOutlookProvider) -> None:
    svc = _svc(fake_provider)
    assert await svc.find_followups("1", "10") == []


async def test_find_promised_actions(fake_provider: FakeOutlookProvider) -> None:
    svc = _svc(fake_provider)
    items = await svc.find_promised_actions("1", "10")
    assert len(items) == 2


async def test_meeting_prep(fake_provider: FakeOutlookProvider) -> None:
    svc = _svc(fake_provider)
    prep = await svc.meeting_prep("1", "e1")
    assert prep.event.subject == "Standup"
    assert prep.briefing == "SUMMARY"
