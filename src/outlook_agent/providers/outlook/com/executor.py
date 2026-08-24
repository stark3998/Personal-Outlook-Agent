"""COM executor — the single choke point for talking to Outlook on Windows.

Mirrors the AppleScript executor's contract (async, availability guard, classified
errors) but drives the Outlook Object Model via ``win32com``. Each call runs on a worker
thread that initializes COM for that thread, so the async services are never blocked and
apartment threading is respected.

``win32com``/``pythoncom`` are imported lazily so the rest of the platform (models,
services, API) imports and tests on any OS.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from enum import StrEnum
from typing import Any, TypeVar

try:  # pragma: no cover - import guard exercised only by platform
    import pythoncom
    import win32com.client

    _COM_IMPORTED = True
except ImportError:  # pragma: no cover
    pythoncom = None
    win32com = None
    _COM_IMPORTED = False

T = TypeVar("T")

# Outlook Object Model item type constants.
OL_MAIL_ITEM = 0
OL_APPOINTMENT_ITEM = 1
OL_CONTACT_ITEM = 2
OL_TASK_ITEM = 3
OL_NOTE_ITEM = 5

# Outlook default folder ids (namespace.GetDefaultFolder).
OL_FOLDER_DELETED = 3
OL_FOLDER_OUTBOX = 4
OL_FOLDER_SENT = 5
OL_FOLDER_INBOX = 6
OL_FOLDER_CALENDAR = 9
OL_FOLDER_CONTACTS = 10
OL_FOLDER_NOTES = 12
OL_FOLDER_TASKS = 13
OL_FOLDER_DRAFTS = 16
OL_FOLDER_JUNK = 23


class ComErrorType(StrEnum):
    """Actionable classification of a COM failure."""

    NOT_AVAILABLE = "not_available"  # pywin32 missing or not on Windows
    NOT_INSTALLED = "not_installed"  # Outlook COM server not registered
    NOT_RUNNING = "not_running"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"


class ComError(Exception):
    """Raised when an Outlook COM operation fails."""

    def __init__(self, message: str, error_type: ComErrorType) -> None:
        super().__init__(message)
        self.error_type = error_type


def _classify(exc: BaseException) -> ComErrorType:
    hresult = getattr(exc, "hresult", None) or getattr(exc, "args", [None])[0]
    text = str(exc).lower()
    if hresult == -2147221005 or "invalid class string" in text:
        return ComErrorType.NOT_INSTALLED
    if "server execution failed" in text or "rpc server" in text or hresult == -2147417846:
        return ComErrorType.NOT_RUNNING
    if "denied" in text or "not allowed" in text:
        return ComErrorType.PERMISSION_DENIED
    return ComErrorType.UNKNOWN


class ComExecutor:
    """Runs callables against a per-thread Outlook Application/MAPI namespace."""

    @property
    def available(self) -> bool:
        """Whether COM is usable here (pywin32 present and running on Windows)."""
        return _COM_IMPORTED and sys.platform == "win32"

    async def run(self, fn: Callable[[Any, Any], T]) -> T:
        """Execute ``fn(app, namespace)`` on a COM-initialized worker thread."""
        return await asyncio.to_thread(self._run_sync, fn)

    def _run_sync(self, fn: Callable[[Any, Any], T]) -> T:
        if not self.available:
            raise ComError(
                "Outlook COM requires Windows with pywin32 installed.",
                ComErrorType.NOT_AVAILABLE,
            )
        pythoncom.CoInitialize()
        try:
            app = win32com.client.Dispatch("Outlook.Application")
            namespace = app.GetNamespace("MAPI")
            return fn(app, namespace)
        except Exception as exc:  # noqa: BLE001 - re-raised as classified ComError
            if exc.__class__.__name__ == "com_error":
                raise ComError(str(exc), _classify(exc)) from exc
            raise
        finally:
            pythoncom.CoUninitialize()

    async def version(self) -> str | None:
        """Return the Outlook version string, or ``None`` if unavailable."""
        try:
            return await self.run(lambda app, _ns: str(app.Version))
        except ComError:
            return None

    async def is_running(self) -> bool:
        """Whether the Outlook COM server responded."""
        return (await self.version()) is not None
