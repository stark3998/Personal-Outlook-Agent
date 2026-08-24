"""FastAPI dependency wiring.

The container is created once and stored on ``app.state``; dependencies expose the
individual services so route handlers stay thin.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from outlook_agent.main import Container
from outlook_agent.services.actions import ActionService
from outlook_agent.services.calendar import CalendarService
from outlook_agent.services.diagnostics import DiagnosticsService
from outlook_agent.services.drafts import DraftService
from outlook_agent.services.folders import FolderService
from outlook_agent.services.intelligence import IntelligenceService
from outlook_agent.services.mail import MailService
from outlook_agent.services.pim import ContactService, NoteService, TaskService
from outlook_agent.services.threads import ThreadService


def get_container(request: Request) -> Container:
    """Return the application container from app state."""
    return cast(Container, request.app.state.container)


def get_mail_service(
    container: Annotated[Container, Depends(get_container)],
) -> MailService:
    """Provide the MailService."""
    return container.mail


def get_thread_service(
    container: Annotated[Container, Depends(get_container)],
) -> ThreadService:
    """Provide the ThreadService."""
    return container.threads


def get_diagnostics_service(
    container: Annotated[Container, Depends(get_container)],
) -> DiagnosticsService:
    """Provide the DiagnosticsService."""
    return container.diagnostics


def get_action_service(
    container: Annotated[Container, Depends(get_container)],
) -> ActionService:
    """Provide the ActionService."""
    return container.actions


def get_draft_service(
    container: Annotated[Container, Depends(get_container)],
) -> DraftService:
    """Provide the DraftService."""
    return container.drafts


def get_folder_service(
    container: Annotated[Container, Depends(get_container)],
) -> FolderService:
    """Provide the FolderService."""
    return container.folders


def get_calendar_service(
    container: Annotated[Container, Depends(get_container)],
) -> CalendarService:
    """Provide the CalendarService."""
    return container.calendar


def get_contact_service(
    container: Annotated[Container, Depends(get_container)],
) -> ContactService:
    """Provide the ContactService."""
    return container.contacts


def get_task_service(
    container: Annotated[Container, Depends(get_container)],
) -> TaskService:
    """Provide the TaskService."""
    return container.tasks


def get_note_service(
    container: Annotated[Container, Depends(get_container)],
) -> NoteService:
    """Provide the NoteService."""
    return container.notes


def get_intelligence_service(
    container: Annotated[Container, Depends(get_container)],
) -> IntelligenceService:
    """Provide the IntelligenceService."""
    return container.intelligence
