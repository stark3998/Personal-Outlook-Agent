"""DiagnosticsService — structured, actionable health reporting."""

from __future__ import annotations

from outlook_agent.domain import (
    DiagnosticCheck,
    DiagnosticReport,
    HealthStatus,
    OutlookInfo,
    Permissions,
)
from outlook_agent.providers.base import OutlookProvider


class DiagnosticsService:
    """Probes the active provider and returns a structured report."""

    def __init__(self, provider: OutlookProvider) -> None:
        self._provider = provider

    async def report(self) -> DiagnosticReport:
        """Run all diagnostic checks and compute an overall status."""
        capabilities = self._provider.capabilities().as_map()
        outlook = await self._provider.probe_outlook()
        permissions = await self._provider.probe_permissions()
        checks = self._checks(outlook, permissions)
        status = self._status(checks)
        return DiagnosticReport(
            status=status,
            outlook=outlook,
            permissions=permissions,
            capabilities=capabilities,
            checks=checks,
        )

    @staticmethod
    def _checks(outlook: OutlookInfo, permissions: Permissions) -> list[DiagnosticCheck]:
        checks: list[DiagnosticCheck] = []
        checks.append(
            DiagnosticCheck(
                name="outlook_installed",
                ok=outlook.installed,
                detail=f"version={outlook.version}" if outlook.version else None,
                remediation=None if outlook.installed else "Install Microsoft Outlook for Mac.",
            )
        )
        checks.append(
            DiagnosticCheck(
                name="outlook_running",
                ok=outlook.running,
                remediation=None if outlook.running else "Launch Microsoft Outlook.",
            )
        )
        checks.append(
            DiagnosticCheck(
                name="automation_permission",
                ok=permissions.automation,
                remediation=(
                    None
                    if permissions.automation
                    else "Ensure classic Microsoft Outlook is installed and launched once. "
                    "macOS: grant Automation access (System Settings > Privacy & Security > "
                    "Automation). Windows: the COM automation model must be reachable."
                ),
            )
        )
        return checks

    @staticmethod
    def _status(checks: list[DiagnosticCheck]) -> HealthStatus:
        critical = {"outlook_installed", "automation_permission"}
        if any(not c.ok for c in checks if c.name in critical):
            return HealthStatus.UNHEALTHY
        if any(not c.ok for c in checks):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
