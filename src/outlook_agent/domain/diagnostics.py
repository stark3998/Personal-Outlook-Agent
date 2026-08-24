"""Diagnostics domain models — structured, actionable health reporting."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Overall diagnostic status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class OutlookInfo(BaseModel):
    """Detected Outlook application state."""

    installed: bool = False
    running: bool = False
    version: str | None = None
    mode: str | None = None  # "classic" | "new" | None if undetectable


class Permissions(BaseModel):
    """macOS automation permissions relevant to the provider."""

    automation: bool = False
    accessibility: bool = False


class DiagnosticCheck(BaseModel):
    """A single check with an actionable message on failure."""

    name: str
    ok: bool
    detail: str | None = None
    remediation: str | None = None


class DiagnosticReport(BaseModel):
    """Structured diagnostics returned by DiagnosticsService."""

    status: HealthStatus
    outlook: OutlookInfo = Field(default_factory=OutlookInfo)
    permissions: Permissions = Field(default_factory=Permissions)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    checks: list[DiagnosticCheck] = Field(default_factory=list)
