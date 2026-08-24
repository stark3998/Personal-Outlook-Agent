"""Structured logging with correlation IDs and sensitive-data redaction.

Uses structlog. Every log line can carry a correlation id (per request/operation). A
redaction processor guarantees that email bodies, credentials, tokens, and attachment
contents are never emitted, even if a caller accidentally binds them.
"""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any, cast

import structlog

# Correlation id for the current request/operation; empty when unset.
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

# Keys whose values must never be logged (substring match, case-insensitive).
_REDACT_SUBSTRINGS = (
    "body",
    "content",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "attachment",
)
_REDACTED = "«redacted»"


def set_correlation_id(value: str) -> None:
    """Bind a correlation id for the current context."""
    _correlation_id.set(value)


def get_correlation_id() -> str:
    """Return the current correlation id (or empty string)."""
    return _correlation_id.get()


def _add_correlation_id(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    cid = _correlation_id.get()
    if cid:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


def _redact(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        lowered = key.lower()
        if any(sub in lowered for sub in _REDACT_SUBSTRINGS):
            event_dict[key] = _REDACTED
    return event_dict


_configured = False


def configure_logging(*, json: bool = True, level: str = "INFO") -> None:
    """Configure structlog once. Safe to call repeatedly."""
    global _configured
    if _configured:
        return
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    renderer = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_correlation_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
