"""Factory that selects and constructs the active Outlook provider.

Provider selection:

* ``applescript`` — macOS classic Outlook via osascript.
* ``com`` — Windows classic Outlook via the COM Object Model.
* ``auto`` — pick by platform (Windows → COM, macOS → AppleScript).
* ``ui`` — deferred New Outlook UI fallback (placeholder).
"""

from __future__ import annotations

import sys

from outlook_agent.config import ProviderKind, Settings

from ..base import OutlookProvider
from .applescript.executor import AppleScriptExecutor
from .applescript.provider import OutlookAppleScriptProvider


def _build_applescript(settings: Settings) -> OutlookProvider:
    executor = AppleScriptExecutor(
        timeout=settings.applescript_timeout,
        large_timeout=settings.applescript_large_timeout,
    )
    return OutlookAppleScriptProvider(executor)


def _build_com() -> OutlookProvider:
    from .com.provider import OutlookCOMProvider

    return OutlookCOMProvider()


def build_provider(settings: Settings) -> OutlookProvider:
    """Construct the Outlook provider selected by configuration."""
    kind = settings.provider
    if kind is ProviderKind.AUTO:
        kind = ProviderKind.COM if sys.platform == "win32" else ProviderKind.APPLESCRIPT

    if kind is ProviderKind.APPLESCRIPT:
        return _build_applescript(settings)
    if kind is ProviderKind.COM:
        return _build_com()
    raise NotImplementedError(f"Provider '{settings.provider}' is not implemented yet.")
