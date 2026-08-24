"""Unit tests for thread reconstruction and capability gating."""

from __future__ import annotations

import pytest

from outlook_agent.domain import Capability, EmailRef, ProviderCapabilities, ProviderName
from outlook_agent.providers.base import CapabilityUnavailable
from outlook_agent.services.mail import MailService
from outlook_agent.services.threads import ThreadService, normalize_subject
from tests.conftest import FakeOutlookProvider


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Re: Hello", "Hello"),
        ("RE: FW: Re:  Hello", "Hello"),
        ("Fwd: Status", "Status"),
        ("No prefix", "No prefix"),
        (None, ""),
    ],
)
def test_normalize_subject(raw: str | None, expected: str) -> None:
    assert normalize_subject(raw) == expected


async def test_thread_assembly_orders_and_counts(fake_provider: FakeOutlookProvider) -> None:
    service = ThreadService(fake_provider)
    thread = await service.get_thread("900", account_id="1")
    assert thread.message_count == 2
    assert thread.unread_count == 1
    assert thread.normalized_subject == "Entra rollout"
    assert len(thread.participants) == 2


async def test_capability_gate_blocks_unsupported() -> None:
    class NoCaps(FakeOutlookProvider):
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(supported=frozenset())

    service = MailService(NoCaps())
    with pytest.raises(CapabilityUnavailable):
        await service.list_accounts()


async def test_get_email_uses_ref(fake_provider: FakeOutlookProvider) -> None:
    service = MailService(fake_provider)
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id="1",
        folder_id="10",
        item_id="100",
    )
    email = await service.get_email(ref)
    assert email.body_text == "Hello world"


def test_capabilities_map_is_stable() -> None:
    caps = ProviderCapabilities(supported=frozenset({Capability.MAIL_READ}))
    m = caps.as_map()
    assert m["mail.read"] is True
    assert m["mail.send"] is False
