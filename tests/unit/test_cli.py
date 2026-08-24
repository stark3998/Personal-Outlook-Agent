"""Tests for the Typer CLI using CliRunner against a fake container."""

from __future__ import annotations

import asyncio
import json
import re

import pytest
from typer.testing import CliRunner

from outlook_agent.cli import main as cli_main
from outlook_agent.config import Settings, StoreKind
from outlook_agent.domain import DraftBody, DraftInput
from outlook_agent.main import Container, build_container

from ..conftest import FakeLLMProvider, FakeOutlookProvider

runner = CliRunner()


def _json_tail(output: str) -> object:
    """Parse the command's JSON result, tolerating leading structlog lines on stdout.

    Logging config is global and may emit either console lines (``<ts> [info] ...``) or
    JSON lines (``{...}``) depending on test order. The command result is always printed
    last as pretty JSON whose opening brace sits at column 0, so the final line-anchored
    ``{``/``[`` marks the payload start.
    """
    matches = list(re.finditer(r"^[\{\[]", output, re.MULTILINE))
    assert matches, output
    return json.loads(output[matches[-1].start() :])


@pytest.fixture
def container(
    fake_provider: FakeOutlookProvider,
    fake_llm: FakeLLMProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> Container:
    settings = Settings(approval_store=StoreKind.MEMORY)
    built = build_container(settings, provider=fake_provider, llm=fake_llm)
    monkeypatch.setattr(cli_main, "build_container", lambda *a, **k: built)
    return built


def test_accounts(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["accounts"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["email_address"] == "me@example.com"


def test_folders(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["folders"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["name"] == "Inbox"


def test_emails(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["emails", "--account-id", "1", "--folder-id", "10"])
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 2


def test_search(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["search", "rollout"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)


def test_read(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["read", "100", "--account-id", "1", "--folder-id", "10"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["body_text"] == "Hello world"


def test_diagnostics(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["diagnostics"])
    assert result.exit_code == 0
    assert isinstance(json.loads(result.stdout), dict)


def test_contacts(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["contacts", "--account-id", "1"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["display_name"] == "Al"


def test_events(container: Container) -> None:
    result = runner.invoke(cli_main.app, ["events", "--account-id", "1"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["subject"] == "Standup"


def test_summarize(container: Container) -> None:
    result = runner.invoke(
        cli_main.app, ["summarize", "100", "--account-id", "1", "--folder-id", "10"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"summary": "SUMMARY"}


def test_prepare_send_confirm_flow(
    container: Container, fake_provider: FakeOutlookProvider
) -> None:
    draft = asyncio.run(
        fake_provider.create_draft("1", DraftInput(subject="Hi", body=DraftBody(text="Body")))
    )

    prepared = runner.invoke(cli_main.app, ["prepare-send", draft.draft_id, "--account-id", "1"])
    assert prepared.exit_code == 0
    token = _json_tail(prepared.stdout)

    confirmed = runner.invoke(
        cli_main.app, ["confirm", token["action_id"], "--token", token["token"]]
    )
    assert confirmed.exit_code == 0
    assert draft.draft_id in fake_provider.sent


def test_cancel_flow(container: Container, fake_provider: FakeOutlookProvider) -> None:
    draft = asyncio.run(
        fake_provider.create_draft("1", DraftInput(subject="Hi", body=DraftBody(text="Body")))
    )
    prepared = runner.invoke(cli_main.app, ["prepare-send", draft.draft_id, "--account-id", "1"])
    token = _json_tail(prepared.stdout)

    cancelled = runner.invoke(cli_main.app, ["cancel", token["action_id"]])
    assert cancelled.exit_code == 0
    assert _json_tail(cancelled.stdout) == {"status": "cancelled"}
    assert draft.draft_id not in fake_provider.sent
