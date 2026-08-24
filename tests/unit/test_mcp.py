"""Tests for the FastMCP tool functions against a fake container (no AppleScript, no LLM API).

The ``@mcp.tool`` decorator returns the underlying coroutine function, so each tool is
called directly after swapping the module-level container for a fake one.
"""

from __future__ import annotations

import pytest

from outlook_agent.config import Settings, StoreKind
from outlook_agent.main import Container, build_container
from outlook_agent.mcp import server

from ..conftest import FakeLLMProvider, FakeOutlookProvider


@pytest.fixture
def mcp_container(
    fake_provider: FakeOutlookProvider,
    fake_llm: FakeLLMProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> Container:
    settings = Settings(approval_store=StoreKind.MEMORY)
    container = build_container(settings, provider=fake_provider, llm=fake_llm)
    monkeypatch.setattr(server, "_container", container)
    return container


async def test_list_accounts(mcp_container: Container) -> None:
    accounts = await server.outlook_list_accounts()
    assert accounts[0]["email_address"] == "me@example.com"


async def test_list_folders(mcp_container: Container) -> None:
    folders = await server.outlook_list_folders()
    assert folders[0]["name"] == "Inbox"


async def test_list_emails(mcp_container: Container) -> None:
    summaries = await server.outlook_list_emails("1", "10")
    assert len(summaries) == 2


async def test_search_emails(mcp_container: Container) -> None:
    results = await server.outlook_search_emails("rollout")
    assert results
    assert all("rollout" in r["subject"].lower() for r in results)


async def test_get_email(mcp_container: Container) -> None:
    email = await server.outlook_get_email("100", "1", "10")
    assert email["body_text"] == "Hello world"


async def test_get_thread(mcp_container: Container) -> None:
    thread = await server.outlook_get_thread("900")
    assert thread["conversation_id"] == "900"


async def test_diagnostics(mcp_container: Container) -> None:
    report = await server.outlook_diagnostics()
    assert isinstance(report, dict)
    assert "outlook" in report


async def test_create_and_list_drafts(mcp_container: Container) -> None:
    created = await server.outlook_create_draft("1", "Subj", "Body", to=["x@y.com"])
    assert created["subject"] == "Subj"
    drafts = await server.outlook_list_drafts("1")
    assert any(d["draft_id"] == created["draft_id"] for d in drafts)


async def test_mark_read_direct(
    mcp_container: Container, fake_provider: FakeOutlookProvider
) -> None:
    result = await server.outlook_mark_read("1", "10", "100", read=True)
    assert result == {"status": "ok"}
    assert ("set_read", "100", True) in fake_provider.ops


async def test_prepare_send_then_confirm_executes(
    mcp_container: Container, fake_provider: FakeOutlookProvider
) -> None:
    draft = await server.outlook_create_draft("1", "Subj", "Body")
    token = await server.outlook_prepare_send("1", draft["draft_id"])

    result = await server.outlook_confirm_action(token["action_id"], token["token"])

    assert draft["draft_id"] in fake_provider.sent
    assert result is not None


async def test_prepare_delete_then_cancel(
    mcp_container: Container, fake_provider: FakeOutlookProvider
) -> None:
    token = await server.outlook_prepare_delete("1", "10", "100")
    pending = await server.outlook_pending_actions()
    assert any(p["action_id"] == token["action_id"] for p in pending)

    cancelled = await server.outlook_cancel_action(token["action_id"])
    assert cancelled == {"status": "cancelled"}
    assert ("delete", "100") not in fake_provider.ops


async def test_confirm_with_bad_token_rejected(mcp_container: Container) -> None:
    from outlook_agent.services.actions import InvalidApprovalToken

    draft = await server.outlook_create_draft("1", "Subj", "Body")
    token = await server.outlook_prepare_send("1", draft["draft_id"])

    with pytest.raises(InvalidApprovalToken):
        await server.outlook_confirm_action(token["action_id"], "not-the-token")


async def test_agent_summarize_email(mcp_container: Container) -> None:
    result = await server.agent_summarize_email("1", "10", "100")
    assert result == {"summary": "SUMMARY"}


async def test_agent_extract_action_items(mcp_container: Container) -> None:
    result = await server.agent_extract_action_items("1", "10", "100")
    assert "items" in result


async def test_agent_prepare_reply(mcp_container: Container) -> None:
    proposal = await server.agent_prepare_reply("1", "10", "100", "be brief")
    assert isinstance(proposal, dict)


async def test_list_events_contacts_tasks(mcp_container: Container) -> None:
    assert (await server.outlook_list_events("1"))[0]["subject"] == "Standup"
    assert (await server.outlook_list_contacts("1"))[0]["display_name"] == "Al"
    assert (await server.outlook_list_tasks("1"))[0]["subject"] == "Do it"
