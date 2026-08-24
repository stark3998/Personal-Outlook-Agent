"""Diagnostics route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from outlook_agent.api.dependencies import get_diagnostics_service
from outlook_agent.domain import DiagnosticReport
from outlook_agent.services.diagnostics import DiagnosticsService

router = APIRouter(prefix="/api/v1", tags=["diagnostics"])


@router.get("/diagnostics", response_model=DiagnosticReport)
async def diagnostics(
    service: Annotated[DiagnosticsService, Depends(get_diagnostics_service)],
) -> DiagnosticReport:
    """Return a structured diagnostic report."""
    return await service.report()
