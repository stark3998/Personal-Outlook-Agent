"""Tests for FoundryLLMProvider using a mocked Agent Framework client (no network)."""

from __future__ import annotations

import pytest

from outlook_agent.intelligence import foundry
from outlook_agent.intelligence.base import LLMError, LLMMessage
from outlook_agent.intelligence.foundry import FoundryConfig, FoundryLLMProvider


class _FakeResponse:
    def __init__(self, text: str | None) -> None:
        self.text = text


class _FakeChatClient:
    """Stands in for agent_framework.openai.OpenAIChatClient."""

    last_instance: _FakeChatClient | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple] = []
        self.response: object = _FakeResponse("Done.")
        self.raise_exc: Exception | None = None
        _FakeChatClient.last_instance = self

    async def get_response(self, messages: object, **kw: object) -> object:
        self.calls.append((messages, kw))
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.response


def _configure(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    env = {
        "FOUNDRY_ENDPOINT": "https://example.openai.azure.com/",
        "FOUNDRY_DEPLOYMENT": "gpt-test",
        "FOUNDRY_API_KEY": "secret-key",
    }
    env.update(overrides)
    for key in (
        "FOUNDRY_ENDPOINT",
        "FOUNDRY_DEPLOYMENT",
        "FOUNDRY_API_VERSION",
        "FOUNDRY_API_KEY",
        "FOUNDRY_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def patched_client(monkeypatch: pytest.MonkeyPatch) -> type[_FakeChatClient]:
    _FakeChatClient.last_instance = None
    monkeypatch.setattr(foundry, "OpenAIChatClient", _FakeChatClient)
    return _FakeChatClient


async def test_complete_success_returns_text(
    monkeypatch: pytest.MonkeyPatch, patched_client: type[_FakeChatClient]
) -> None:
    _configure(monkeypatch)
    provider = FoundryLLMProvider(FoundryConfig())

    result = await provider.complete([LLMMessage(role="user", content="hello")])

    assert result == "Done."
    client = patched_client.last_instance
    assert client is not None
    assert client.kwargs["model"] == "gpt-test"
    assert client.kwargs["api_key"] == "secret-key"
    assert client.kwargs["azure_endpoint"] == "https://example.openai.azure.com"
    # temperature is forwarded through options
    assert client.calls[0][1]["options"] == {"temperature": 0.2}


async def test_access_token_used_when_no_api_key(
    monkeypatch: pytest.MonkeyPatch, patched_client: type[_FakeChatClient]
) -> None:
    _configure(monkeypatch, FOUNDRY_API_KEY="", FOUNDRY_ACCESS_TOKEN="tok-123")
    provider = FoundryLLMProvider(FoundryConfig())

    await provider.complete([LLMMessage(role="user", content="hi")])

    assert patched_client.last_instance.kwargs["api_key"] == "tok-123"


async def test_missing_credential_raises(
    monkeypatch: pytest.MonkeyPatch, patched_client: type[_FakeChatClient]
) -> None:
    _configure(monkeypatch, FOUNDRY_API_KEY="")
    provider = FoundryLLMProvider(FoundryConfig())

    with pytest.raises(LLMError, match="No Foundry credential"):
        await provider.complete([LLMMessage(role="user", content="hi")])


async def test_not_configured_raises(
    monkeypatch: pytest.MonkeyPatch, patched_client: type[_FakeChatClient]
) -> None:
    for key in ("FOUNDRY_ENDPOINT", "FOUNDRY_DEPLOYMENT", "FOUNDRY_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    provider = FoundryLLMProvider(FoundryConfig())

    with pytest.raises(LLMError, match="not configured"):
        await provider.complete([LLMMessage(role="user", content="hi")])


async def test_sdk_error_normalized(
    monkeypatch: pytest.MonkeyPatch, patched_client: type[_FakeChatClient]
) -> None:
    _configure(monkeypatch)
    provider = FoundryLLMProvider(FoundryConfig())
    # Trigger the client build, then make the call fail.
    client = provider._get_client()  # noqa: SLF001 - test drives internal client
    client.raise_exc = RuntimeError("boom")

    with pytest.raises(LLMError, match="Foundry request failed"):
        await provider.complete([LLMMessage(role="user", content="hi")])


async def test_bad_response_shape_raises(
    monkeypatch: pytest.MonkeyPatch, patched_client: type[_FakeChatClient]
) -> None:
    _configure(monkeypatch)
    provider = FoundryLLMProvider(FoundryConfig())
    client = provider._get_client()  # noqa: SLF001 - test drives internal client
    client.response = _FakeResponse(None)

    with pytest.raises(LLMError, match="Unexpected Foundry response shape"):
        await provider.complete([LLMMessage(role="user", content="hi")])


async def test_summarize_flows_through_complete(
    monkeypatch: pytest.MonkeyPatch, patched_client: type[_FakeChatClient]
) -> None:
    _configure(monkeypatch)
    provider = FoundryLLMProvider(FoundryConfig())

    result = await provider.summarize("a long email body")

    assert result == "Done."
    # system + user messages were sent
    sent_messages = patched_client.last_instance.calls[0][0]
    assert len(sent_messages) == 2


def test_config_configured_property(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    assert FoundryConfig().configured is True
    monkeypatch.delenv("FOUNDRY_ENDPOINT", raising=False)
    assert FoundryConfig().configured is False
