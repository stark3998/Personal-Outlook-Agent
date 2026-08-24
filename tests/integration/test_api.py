"""Integration tests for the FastAPI layer using the fake provider."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from outlook_agent.api.app import create_app
from outlook_agent.main import build_container
from tests.conftest import FakeLLMProvider, FakeOutlookProvider


@pytest.fixture
def client() -> TestClient:
    provider = FakeOutlookProvider()
    app = create_app()
    app.state.container = build_container(provider=provider, llm=FakeLLMProvider())
    return TestClient(app)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_diagnostics(client: TestClient) -> None:
    body = client.get("/api/v1/diagnostics").json()
    assert body["status"] == "healthy"
    assert body["capabilities"]["mail.read"] is True


def test_accounts_and_folders(client: TestClient) -> None:
    assert client.get("/api/v1/accounts").json()[0]["account_id"] == "1"
    assert client.get("/api/v1/folders").json()[0]["name"] == "Inbox"


def test_list_and_search_and_get(client: TestClient) -> None:
    listed = client.get("/api/v1/mail", params={"account_id": "1", "folder_id": "10"}).json()
    assert len(listed) == 2

    found = client.get("/api/v1/mail/search", params={"q": "Entra"}).json()
    assert len(found) == 2

    email = client.get("/api/v1/mail/100", params={"account_id": "1", "folder_id": "10"}).json()
    assert email["body_text"] == "Hello world"


def test_thread(client: TestClient) -> None:
    thread = client.get("/api/v1/threads/900", params={"account_id": "1"}).json()
    assert thread["message_count"] == 2
    assert thread["normalized_subject"] == "Entra rollout"


def test_draft_create_and_gated_send(client: TestClient) -> None:
    created = client.post(
        "/api/v1/drafts",
        params={"account_id": "1"},
        json={"subject": "Hi", "body": {"text": "yo"}},
    ).json()
    draft_id = created["draft_id"]

    token = client.post(f"/api/v1/drafts/{draft_id}/send", params={"account_id": "1"}).json()
    assert token["action_type"] == "send"

    pending = client.get("/api/v1/actions/pending").json()
    assert any(a["action_id"] == token["action_id"] for a in pending)

    result = client.post(
        f"/api/v1/actions/{token['action_id']}/confirm",
        json={"token": token["token"]},
    ).json()
    assert result["success"] is True


def test_confirm_bad_token_is_forbidden(client: TestClient) -> None:
    created = client.post(
        "/api/v1/drafts", params={"account_id": "1"}, json={"subject": "x", "body": {}}
    ).json()
    token = client.post(
        f"/api/v1/drafts/{created['draft_id']}/send", params={"account_id": "1"}
    ).json()
    resp = client.post(f"/api/v1/actions/{token['action_id']}/confirm", json={"token": "wrong"})
    assert resp.status_code == 403


def test_calendar_and_pim_reads(client: TestClient) -> None:
    assert client.get("/api/v1/calendar/events", params={"account_id": "1"}).json()
    assert client.get("/api/v1/contacts", params={"account_id": "1"}).json()
    assert client.get("/api/v1/tasks", params={"account_id": "1"}).json()
    assert client.get("/api/v1/notes", params={"account_id": "1"}).json()


def test_agent_summarize_and_prepare_reply(client: TestClient) -> None:
    summary = client.get(
        "/api/v1/agent/summarize/email",
        params={"account_id": "1", "folder_id": "10", "item_id": "100"},
    ).json()
    assert summary["summary"] == "SUMMARY"

    proposal = client.post(
        "/api/v1/agent/prepare-reply",
        json={
            "account_id": "1",
            "folder_id": "10",
            "item_id": "100",
            "instructions": "be brief",
            "create_draft": True,
        },
    ).json()
    assert proposal["body"]
    assert proposal["draft"] is not None
