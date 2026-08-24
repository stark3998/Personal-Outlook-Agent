"""FoundryLLMProvider — chat completions via Azure OpenAI / Microsoft Foundry.

Uses ``openai.AsyncAzureOpenAI`` pointed at an Azure OpenAI / Foundry deployment.
Configuration is read from Settings (preferred) or falls back to os.getenv() so the
class works standalone without a Settings instance. The Agent Framework SDK's
``OpenAIChatClient`` targets the newer Responses API which some Azure resources do not
yet support; the chat-completions path is universally available.
"""

from __future__ import annotations

import os

import openai

from .base import LLMBase, LLMError, LLMMessage


class FoundryConfig:
    """Foundry / Azure OpenAI connection settings.

    Values may be passed explicitly (preferred — sourced from Settings) or fall back to
    os.getenv() so existing callers without a Settings instance still work.
    """

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.endpoint = (endpoint or os.getenv("FOUNDRY_ENDPOINT", "")).rstrip("/")
        self.deployment = deployment or os.getenv("FOUNDRY_DEPLOYMENT", "")
        self.api_version = api_version or os.getenv("FOUNDRY_API_VERSION", "2024-10-21")
        self.api_key = (
            api_key
            or os.getenv("FOUNDRY_API_KEY", "")
            or os.getenv("FOUNDRY_ACCESS_TOKEN", "")
        )

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.deployment)


class FoundryLLMProvider(LLMBase):
    """Chat completions against a Foundry/Azure OpenAI deployment."""

    def __init__(self, config: FoundryConfig | None = None) -> None:
        self._cfg = config or FoundryConfig()
        self._client: openai.AsyncAzureOpenAI | None = None

    def _get_client(self) -> openai.AsyncAzureOpenAI:
        if self._client is None:
            if not self._cfg.configured:
                raise LLMError("Foundry is not configured (FOUNDRY_ENDPOINT/FOUNDRY_DEPLOYMENT).")
            if not self._cfg.api_key:
                raise LLMError(
                    "No Foundry credential: set FOUNDRY_API_KEY or FOUNDRY_ACCESS_TOKEN."
                )
            self._client = openai.AsyncAzureOpenAI(
                azure_endpoint=self._cfg.endpoint,
                api_key=self._cfg.api_key,
                api_version=self._cfg.api_version,
            )
        return self._client

    async def complete(self, messages: list[LLMMessage], *, temperature: float = 0.2) -> str:
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self._cfg.deployment,
                messages=[{"role": m.role, "content": m.content} for m in messages],  # type: ignore[misc]
                temperature=temperature,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Foundry request failed: {exc}") from exc
        text = response.choices[0].message.content
        if text is None:
            raise LLMError("Foundry returned an empty completion.")
        return text
