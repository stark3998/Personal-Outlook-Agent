"""Application configuration (12-factor: env-driven).

Secrets must never be committed. Use `.env` locally (git-ignored) or macOS Keychain;
`.env.example` documents the available knobs.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderKind(StrEnum):
    """Which Outlook provider the platform should use."""

    APPLESCRIPT = "applescript"
    COM = "com"
    UI = "ui"
    AUTO = "auto"


class StoreKind(StrEnum):
    """Where prepared actions and audit events are persisted."""

    MEMORY = "memory"
    SQLITE = "sqlite"


class Settings(BaseSettings):
    """Runtime settings loaded from environment / `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="OUTLOOK_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider
    provider: ProviderKind = ProviderKind.AUTO
    applescript_timeout: float = 30.0
    applescript_large_timeout: float = 120.0

    # Storage
    approval_store: StoreKind = StoreKind.MEMORY
    database_url: str = "sqlite:///outlook_agent.db"

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    # Logging
    log_level: str = "INFO"
    log_json: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
