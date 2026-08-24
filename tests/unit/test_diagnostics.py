"""Tests for enhanced diagnostics access checks."""

from __future__ import annotations

from outlook_agent.domain import HealthStatus, OutlookInfo, Permissions, ProviderCapabilities
from outlook_agent.services.diagnostics import DiagnosticsService
from tests.conftest import FakeOutlookProvider


async def test_report_includes_access_checks_when_running(
    fake_provider: FakeOutlookProvider,
) -> None:
    report = await DiagnosticsService(fake_provider).report()
    names = {c.name for c in report.checks}
    assert {"account_access", "folder_access", "message_access"} <= names
    assert report.status is HealthStatus.HEALTHY
    assert all(c.ok for c in report.checks)


async def test_access_checks_skipped_when_not_running() -> None:
    class Down(FakeOutlookProvider):
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(supported=frozenset())

        async def probe_outlook(self) -> OutlookInfo:
            return OutlookInfo(installed=False, running=False)

        async def probe_permissions(self) -> Permissions:
            return Permissions(automation=False, accessibility=False)

    report = await DiagnosticsService(Down()).report()
    names = {c.name for c in report.checks}
    assert "account_access" not in names
    assert report.status is HealthStatus.UNHEALTHY


async def test_access_check_failure_is_degraded_not_crash() -> None:
    class Flaky(FakeOutlookProvider):
        async def list_accounts(self):  # type: ignore[override]
            raise RuntimeError("boom")

    report = await DiagnosticsService(Flaky()).report()
    account_check = next(c for c in report.checks if c.name == "account_access")
    assert account_check.ok is False
    assert report.status is HealthStatus.DEGRADED
