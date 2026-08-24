"""Composition root — wires configuration, provider, and services together.

This is the single place providers and services are constructed. Interfaces (MCP, REST,
CLI) receive a fully-built :class:`Container` and never construct providers themselves.
"""

from __future__ import annotations

from dataclasses import dataclass

from outlook_agent.config import Settings, StoreKind, get_settings
from outlook_agent.intelligence.base import LLMProvider
from outlook_agent.intelligence.foundry import FoundryLLMProvider
from outlook_agent.providers.base import OutlookProvider
from outlook_agent.providers.outlook.factory import build_provider
from outlook_agent.security.approvals import ApprovalStore, InMemoryApprovalStore
from outlook_agent.security.audit import AuditLog, InMemoryAuditLog
from outlook_agent.services.actions import ActionService
from outlook_agent.services.calendar import CalendarService
from outlook_agent.services.diagnostics import DiagnosticsService
from outlook_agent.services.drafts import DraftService
from outlook_agent.services.folders import FolderService
from outlook_agent.services.handlers import default_handlers
from outlook_agent.services.intelligence import IntelligenceService
from outlook_agent.services.mail import MailService
from outlook_agent.services.pim import ContactService, NoteService, TaskService
from outlook_agent.services.threads import ThreadService


@dataclass(frozen=True)
class Container:
    """Holds the constructed services shared by every interface."""

    settings: Settings
    provider: OutlookProvider
    llm: LLMProvider
    mail: MailService
    threads: ThreadService
    diagnostics: DiagnosticsService
    actions: ActionService
    drafts: DraftService
    folders: FolderService
    calendar: CalendarService
    contacts: ContactService
    tasks: TaskService
    notes: NoteService
    intelligence: IntelligenceService


def _build_stores(settings: Settings) -> tuple[ApprovalStore, AuditLog]:
    """Construct the approval store + audit log per configuration."""
    if settings.approval_store is StoreKind.SQLITE:
        from outlook_agent.storage.approvals import SqliteApprovalStore
        from outlook_agent.storage.audit import SqliteAuditLog
        from outlook_agent.storage.database import (
            create_db_engine,
            init_db,
            make_session_factory,
        )

        engine = create_db_engine(settings.database_url)
        init_db(engine)
        factory = make_session_factory(engine)
        return SqliteApprovalStore(factory), SqliteAuditLog(factory)
    return InMemoryApprovalStore(), InMemoryAuditLog()


def build_container(
    settings: Settings | None = None,
    *,
    provider: OutlookProvider | None = None,
    llm: LLMProvider | None = None,
) -> Container:
    """Build the application container from settings.

    ``provider`` and ``llm`` may be injected (e.g. fakes in tests); otherwise they are
    constructed from configuration.
    """
    settings = settings or get_settings()
    provider = provider or build_provider(settings)
    store, audit = _build_stores(settings)
    actions = ActionService(store, audit, default_handlers(provider))
    llm = llm or FoundryLLMProvider()
    mail = MailService(provider, actions)
    threads = ThreadService(provider)
    drafts = DraftService(provider, actions)
    return Container(
        settings=settings,
        provider=provider,
        llm=llm,
        mail=mail,
        threads=threads,
        diagnostics=DiagnosticsService(provider),
        actions=actions,
        drafts=drafts,
        folders=FolderService(provider, actions),
        calendar=CalendarService(provider, actions),
        contacts=ContactService(provider),
        tasks=TaskService(provider),
        notes=NoteService(provider),
        intelligence=IntelligenceService(llm, mail, threads, drafts),
    )


def run_api() -> None:
    """Entry point for ``outlook-agent-api``: serve the FastAPI app with uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "outlook_agent.api.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
