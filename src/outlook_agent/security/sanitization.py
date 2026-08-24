"""Sanitization — the prompt-injection boundary for untrusted email content.

Email bodies, attachments, signatures, quoted replies, and external web content are
*data*, never instructions. This module makes that boundary explicit so intelligence
code (Milestone 9+) can wrap untrusted text before it is ever shown to an LLM, and can
never let it flow into a system/developer prompt.
"""

from __future__ import annotations

import re

_UNTRUSTED_OPEN = "<<<UNTRUSTED_EMAIL_CONTENT>>>"
_UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_EMAIL_CONTENT>>>"

# Heuristic markers of attempted instruction injection inside email content.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\b.{0,30}\b(instructions|context|prompt|prior|above)", re.I),
    re.compile(r"disregard\b.{0,30}\b(above|previous|system|instructions)", re.I),
    re.compile(r"you are now|new instructions:|system prompt", re.I),
    re.compile(r"\b(send|delete|forward|move|archive)\b.{0,40}\b(immediately|now|without)", re.I),
)


def wrap_untrusted(content: str) -> str:
    """Wrap untrusted content in explicit delimiters for safe LLM presentation."""
    return f"{_UNTRUSTED_OPEN}\n{content}\n{_UNTRUSTED_CLOSE}"


def looks_like_injection(content: str) -> bool:
    """Return whether content contains likely prompt-injection phrasing.

    A positive result does not block reasoning; it is a signal for callers to treat the
    content with extra caution and never act on embedded imperatives.
    """
    return any(p.search(content) for p in _INJECTION_PATTERNS)


def strip_boundary_markers(content: str) -> str:
    """Remove any pre-existing boundary markers an attacker may have embedded."""
    return content.replace(_UNTRUSTED_OPEN, "").replace(_UNTRUSTED_CLOSE, "")
