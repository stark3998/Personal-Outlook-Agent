"""OutlookUIScriptingProvider — deferred New Outlook fallback (placeholder).

Advertises no capabilities yet, so services transparently report ``CapabilityUnavailable``
rather than failing. Implemented in Milestone 13.
"""

from __future__ import annotations

from outlook_agent.domain import OutlookInfo, Permissions, ProviderCapabilities


class OutlookUIScriptingProvider:
    """Placeholder provider for New Outlook via UI/Accessibility automation."""

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supported=frozenset())

    async def probe_outlook(self) -> OutlookInfo:
        return OutlookInfo(installed=False, running=False, mode="new")

    async def probe_permissions(self) -> Permissions:
        return Permissions(automation=False, accessibility=False)
