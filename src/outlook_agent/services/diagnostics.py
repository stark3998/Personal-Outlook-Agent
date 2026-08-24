"""DiagnosticsService — structured, actionable health reporting."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

from outlook_agent.domain import (
    Capability,
    DiagnosticCheck,
    DiagnosticReport,
    HealthStatus,
    OutlookInfo,
    Permissions,
    SpecialFolderType,
)
from outlook_agent.providers.base import OutlookProvider

T = TypeVar("T")


class DiagnosticsService:
    """Probes the active provider and returns a structured report."""

    def __init__(self, provider: OutlookProvider) -> None:
        self._provider = provider

    async def report(self) -> DiagnosticReport:
        """Run all diagnostic checks and compute an overall status."""
        capabilities = self._provider.capabilities().as_map()
        outlook = await self._provider.probe_outlook()
        permissions = await self._provider.probe_permissions()
        checks = self._base_checks(outlook, permissions)
        # Live access probes only make sense once Outlook is actually reachable.
        if outlook.running:
            checks.extend(await self._access_checks())
        status = self._status(checks)
        return DiagnosticReport(
            status=status,
            outlook=outlook,
            permissions=permissions,
            capabilities=capabilities,
            checks=checks,
        )

    @staticmethod
    def _base_checks(outlook: OutlookInfo, permissions: Permissions) -> list[DiagnosticCheck]:
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

    async def _access_checks(self) -> list[DiagnosticCheck]:
        """Attempt real reads to confirm end-to-end access. Failures are non-critical."""
        caps = self._provider.capabilities()
        checks: list[DiagnosticCheck] = []

        accounts_ok, accounts_detail, accounts = await self._probe(
            "account_access", self._provider.list_accounts()
        )
        checks.append(accounts_ok)

        folders_ok, _folders_detail, folders = await self._probe(
            "folder_access", self._provider.list_folders()
        )
        checks.append(folders_ok)

        if caps.has(Capability.MAIL_ATTACHMENTS):
            checks.append(
                DiagnosticCheck(name="attachment_access", ok=True, detail="capability reported")
            )

        # Message read: pick an inbox folder if we can and read a single item.
        inbox = None
        if isinstance(folders, list):
            inbox = next((f for f in folders if f.special_type is SpecialFolderType.INBOX), None)
        if inbox is not None:
            msg_ok, _detail, _msgs = await self._probe(
                "message_access",
                self._provider.list_emails(inbox.account_id, inbox.folder_id, limit=1),
            )
            checks.append(msg_ok)
        else:
            checks.append(
                DiagnosticCheck(
                    name="message_access",
                    ok=False,
                    detail="no Inbox folder detected",
                    remediation="Verify the account has an Inbox and folders are accessible.",
                )
            )
        return checks

    @staticmethod
    async def _probe(
        name: str, coro: Awaitable[list[T]]
    ) -> tuple[DiagnosticCheck, str | None, list[T] | None]:
        try:
            result = await coro
        except Exception as exc:  # noqa: BLE001 - any provider failure is a failed check
            return (
                DiagnosticCheck(name=name, ok=False, detail=type(exc).__name__),
                None,
                None,
            )
        detail = f"{len(result)} items"
        return DiagnosticCheck(name=name, ok=True, detail=detail), detail, result

    @staticmethod
    def _status(checks: list[DiagnosticCheck]) -> HealthStatus:
        critical = {"outlook_installed", "automation_permission"}
        if any(not c.ok for c in checks if c.name in critical):
            return HealthStatus.UNHEALTHY
        if any(not c.ok for c in checks):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
