"""Factory that selects and constructs the active Outlook provider."""

from __future__ import annotations

from outlook_agent.config import ProviderKind, Settings

from ..base import OutlookProvider
from .applescript.executor import AppleScriptExecutor
from .applescript.provider import OutlookAppleScriptProvider


def build_provider(settings: Settings) -> OutlookProvider:
    """Construct the Outlook provider selected by configuration.

    The UI provider is deferred (Milestone 13); ``auto`` currently resolves to
    AppleScript.
    """
    if settings.provider in (ProviderKind.APPLESCRIPT, ProviderKind.AUTO):
        executor = AppleScriptExecutor(
            timeout=settings.applescript_timeout,
            large_timeout=settings.applescript_large_timeout,
        )
        return OutlookAppleScriptProvider(executor)
    raise NotImplementedError(f"Provider '{settings.provider}' is not implemented yet.")
