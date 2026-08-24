"""Tests for structured logging: redaction and correlation ids."""

from __future__ import annotations

from outlook_agent.observability import get_correlation_id, set_correlation_id
from outlook_agent.observability.logging import _redact


def test_redacts_sensitive_keys() -> None:
    event = {
        "event": "x",
        "body_text": "secret email content",
        "api_key": "abc",
        "authorization": "Bearer t",
        "subject": "ok to keep",
    }
    out = _redact(None, "info", dict(event))
    assert out["body_text"] == "«redacted»"
    assert out["api_key"] == "«redacted»"
    assert out["authorization"] == "«redacted»"
    assert out["subject"] == "ok to keep"


def test_correlation_id_roundtrip() -> None:
    set_correlation_id("cid-123")
    assert get_correlation_id() == "cid-123"
