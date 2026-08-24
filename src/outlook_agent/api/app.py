"""FastAPI application factory."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from outlook_agent.config import Settings, get_settings
from outlook_agent.intelligence.base import LLMError
from outlook_agent.main import build_container
from outlook_agent.observability import configure_logging, set_correlation_id
from outlook_agent.providers.base import CapabilityUnavailable
from outlook_agent.providers.outlook.applescript.executor import AppleScriptError
from outlook_agent.providers.outlook.com.executor import ComError
from outlook_agent.services.actions import (
    ActionError,
    ActionExpired,
    ActionNotFound,
    ActionStale,
    InvalidApprovalToken,
)

from .routes import (
    accounts,
    actions,
    agent,
    calendar,
    diagnostics,
    drafts,
    health,
    mail,
    pim,
    threads,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application with routers and error handlers."""
    settings = settings or get_settings()
    configure_logging(json=settings.log_json, level=settings.log_level)
    app = FastAPI(title="personal-outlook-agent", version="0.1.0")
    app.state.container = build_container(settings)

    @app.middleware("http")
    async def _correlation_middleware(request: Request, call_next):  # noqa: ANN001, ANN202
        cid = request.headers.get("x-correlation-id") or uuid4().hex
        set_correlation_id(cid)
        response = await call_next(request)
        response.headers["x-correlation-id"] = cid
        return response

    app.include_router(health.router)
    app.include_router(diagnostics.router)
    app.include_router(accounts.router)
    app.include_router(mail.router)
    app.include_router(threads.router)
    app.include_router(drafts.router)
    app.include_router(actions.router)
    app.include_router(calendar.router)
    app.include_router(pim.router)
    app.include_router(agent.router)

    @app.exception_handler(CapabilityUnavailable)
    async def _capability_handler(_: Request, exc: CapabilityUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=501,
            content={"error": "capability_unavailable", "detail": str(exc)},
        )

    @app.exception_handler(AppleScriptError)
    async def _applescript_handler(_: Request, exc: AppleScriptError) -> JSONResponse:
        status = 503 if exc.error_type.value in {"not_running", "not_available"} else 502
        return JSONResponse(
            status_code=status,
            content={"error": exc.error_type.value, "detail": str(exc)},
        )

    @app.exception_handler(ComError)
    async def _com_handler(_: Request, exc: ComError) -> JSONResponse:
        unhealthy = {"not_available", "not_installed", "not_running"}
        status = 503 if exc.error_type.value in unhealthy else 502
        return JSONResponse(
            status_code=status,
            content={"error": exc.error_type.value, "detail": str(exc)},
        )

    @app.exception_handler(ActionError)
    async def _action_handler(_: Request, exc: ActionError) -> JSONResponse:
        status = 404 if isinstance(exc, ActionNotFound) else 409
        if isinstance(exc, InvalidApprovalToken):
            status = 403
        elif isinstance(exc, ActionExpired | ActionStale):
            status = 410
        return JSONResponse(
            status_code=status,
            content={"error": type(exc).__name__, "detail": str(exc)},
        )

    @app.exception_handler(LLMError)
    async def _llm_handler(_: Request, exc: LLMError) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"error": "llm_unavailable", "detail": str(exc)}
        )

    return app
