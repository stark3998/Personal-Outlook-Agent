"""FoundryLLMProvider — chat completions via the Microsoft Agent Framework.

Uses ``agent_framework.openai.OpenAIChatClient`` pointed at an Azure OpenAI / Foundry
deployment. Configuration is read from env vars; nothing is hard-coded and no secret is
committed. This keeps the ``LLMBase`` interface while delegating transport, retries, and
message handling to the official Microsoft SDK.
"""

from __future__ import annotations

import os

from agent_framework import Message
from agent_framework.openai import OpenAIChatClient

from .base import LLMBase, LLMError, LLMMessage


class FoundryConfig:
    """Foundry / Azure OpenAI connection settings read from the environment."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("FOUNDRY_ENDPOINT", "").rstrip("/")
        self.deployment = os.getenv("FOUNDRY_DEPLOYMENT", "")
        self.api_version = os.getenv("FOUNDRY_API_VERSION", "2024-10-21")
        self.api_key = os.getenv("FOUNDRY_API_KEY", "") or os.getenv("FOUNDRY_ACCESS_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.deployment)


class FoundryLLMProvider(LLMBase):
    """Chat completions against a Foundry/Azure OpenAI deployment via the Agent Framework."""

    def __init__(self, config: FoundryConfig | None = None) -> None:
        self._cfg = config or FoundryConfig()
        self._client: OpenAIChatClient | None = None

    def _get_client(self) -> OpenAIChatClient:
        if self._client is None:
            if not self._cfg.configured:
                raise LLMError("Foundry is not configured (FOUNDRY_ENDPOINT/FOUNDRY_DEPLOYMENT).")
            if not self._cfg.api_key:
                raise LLMError(
                    "No Foundry credential: set FOUNDRY_API_KEY or FOUNDRY_ACCESS_TOKEN."
                )
            self._client = OpenAIChatClient(
                model=self._cfg.deployment,
                api_key=self._cfg.api_key,
                azure_endpoint=self._cfg.endpoint,
                api_version=self._cfg.api_version,
            )
        return self._client

    async def complete(self, messages: list[LLMMessage], *, temperature: float = 0.2) -> str:
        client = self._get_client()
        af_messages = [Message(m.role, [m.content]) for m in messages]
        try:
            response = await client.get_response(af_messages, options={"temperature": temperature})
        except LLMError:
            raise
        except Exception as exc:  # normalize SDK/transport failures
            raise LLMError(f"Foundry request failed: {exc}") from exc
        text = getattr(response, "text", None)
        if text is None:
            raise LLMError("Unexpected Foundry response shape")
        return str(text)
