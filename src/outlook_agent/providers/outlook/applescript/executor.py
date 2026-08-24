"""AppleScript executor — the single choke point for ``osascript`` invocation.

Design decisions (see docs/research/UPSTREAM_MATRIX.md):

* The script is passed to ``osascript`` on **stdin** (no shell interpolation, no argv
  length limit) — adapted from hasan-imam/mcp-outlook-applescript ``executor.ts``.
* Execution is async via ``asyncio.to_thread`` around a blocking ``subprocess.run`` —
  adapted from grokeverything/mega-outlook-mcp ``applescript/__init__.py``.
* Failures are classified into actionable categories.
* Non-macOS hosts are detected via ``shutil.which("osascript")`` so the rest of the
  platform (models, services, API) still imports and runs anywhere.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from enum import StrEnum

DEFAULT_TIMEOUT_SECONDS = 30.0
LARGE_SCAN_TIMEOUT_SECONDS = 120.0


class AppleScriptErrorType(StrEnum):
    """Actionable classification of an osascript failure."""

    NOT_AVAILABLE = "not_available"  # osascript missing (non-macOS)
    NOT_RUNNING = "not_running"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


_ERROR_PATTERNS: tuple[tuple[re.Pattern[str], AppleScriptErrorType], ...] = (
    (re.compile(r"not running|application isn'?t running", re.I), AppleScriptErrorType.NOT_RUNNING),
    (
        re.compile(r"not authoriz|permission denied|assistive access|-1743", re.I),
        AppleScriptErrorType.PERMISSION_DENIED,
    ),
    (re.compile(r"timed out|timeout", re.I), AppleScriptErrorType.TIMEOUT),
)


def _classify(message: str) -> AppleScriptErrorType:
    for pattern, kind in _ERROR_PATTERNS:
        if pattern.search(message):
            return kind
    return AppleScriptErrorType.UNKNOWN


class AppleScriptError(Exception):
    """Raised when an osascript invocation fails."""

    def __init__(self, message: str, error_type: AppleScriptErrorType) -> None:
        super().__init__(message)
        self.error_type = error_type


def escape(value: str) -> str:
    """Escape a Python string for safe embedding inside an AppleScript string literal.

    Escapes backslashes and double-quotes, and converts newlines into AppleScript
    concatenation so multi-line values never break the surrounding literal. The result
    is intended to sit *inside* an existing pair of quotes in a template.
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", '" & linefeed & "')
        .replace("\n", '" & linefeed & "')
        .replace("\r", '" & linefeed & "')
    )


def quote(value: str) -> str:
    """Return an escaped, fully-quoted AppleScript string literal."""
    return f'"{escape(value)}"'


def _osascript_path() -> str | None:
    return shutil.which("osascript")


class AppleScriptExecutor:
    """Runs AppleScript source via ``osascript`` and returns stdout."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        large_timeout: float = LARGE_SCAN_TIMEOUT_SECONDS,
    ) -> None:
        self._timeout = timeout
        self._large_timeout = large_timeout

    @property
    def available(self) -> bool:
        """Whether ``osascript`` exists on this host (i.e. we are on macOS)."""
        return _osascript_path() is not None

    async def run(self, script: str, *, large: bool = False) -> str:
        """Execute a script and return trimmed stdout, raising on failure."""
        timeout = self._large_timeout if large else self._timeout
        return await asyncio.to_thread(self._run_sync, script, timeout)

    def _run_sync(self, script: str, timeout: float) -> str:
        path = _osascript_path()
        if path is None:
            raise AppleScriptError(
                "osascript not found; the AppleScript provider requires macOS.",
                AppleScriptErrorType.NOT_AVAILABLE,
            )
        try:
            completed = subprocess.run(  # noqa: S603 - fixed executable, script via stdin
                [path],
                input=script,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AppleScriptError(
                f"osascript timed out after {timeout}s; is Outlook responsive?",
                AppleScriptErrorType.TIMEOUT,
            ) from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise AppleScriptError(detail or "unknown osascript error", _classify(detail))
        return completed.stdout.strip()

    async def is_outlook_running(self) -> bool:
        """Return whether Microsoft Outlook is currently running."""
        script = (
            'tell application "System Events" to '
            'return (name of processes) contains "Microsoft Outlook"'
        )
        try:
            out = await self.run(script)
        except AppleScriptError:
            return False
        return out.strip().lower() == "true"

    async def outlook_version(self) -> str | None:
        """Return Outlook's version string, or ``None`` if unavailable."""
        try:
            return await self.run('tell application "Microsoft Outlook" to get version')
        except AppleScriptError:
            return None
