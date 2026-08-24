"""Action / approval domain models.

Every write or destructive operation is represented as an :class:`Action` that must be
explicitly prepared and then confirmed (see services/actions.py). The LLM cannot bypass
this flow: it can only *propose* actions, never execute them directly.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(StrEnum):
    """The catalog of controlled operations."""

    SEND = "send"
    REPLY = "reply"
    REPLY_ALL = "reply_all"
    FORWARD = "forward"
    DELETE = "delete"
    MOVE = "move"
    ARCHIVE = "archive"
    JUNK = "junk"
    MARK_READ = "mark_read"
    MARK_UNREAD = "mark_unread"
    SET_FLAG = "set_flag"
    CLEAR_FLAG = "clear_flag"
    SET_CATEGORIES = "set_categories"
    FOLDER_CREATE = "folder_create"
    FOLDER_RENAME = "folder_rename"
    FOLDER_MOVE = "folder_move"
    FOLDER_DELETE = "folder_delete"
    FOLDER_EMPTY = "folder_empty"
    CALENDAR_CREATE = "calendar_create"
    CALENDAR_UPDATE = "calendar_update"
    CALENDAR_DELETE = "calendar_delete"
    CALENDAR_RESPOND = "calendar_respond"


class RiskLevel(StrEnum):
    """How dangerous an action is; drives TTL and confirmation emphasis."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionStatus(StrEnum):
    """Lifecycle state of a prepared action."""

    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    STALE = "stale"
    FAILED = "failed"


class ActionResult(BaseModel):
    """Outcome of executing a confirmed action."""

    success: bool
    detail: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    """A prepared, controlled operation awaiting (or past) confirmation.

    ``target_state_hash`` captures a snapshot of the target at preparation time so that
    confirmation can reject the action if the target changed in the meantime.
    """

    action_id: str
    action_type: ActionType
    risk_level: RiskLevel
    status: ActionStatus = ActionStatus.PENDING
    summary: str
    target: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    target_state_hash: str | None = None
    requested_by: str | None = None
    created_at: datetime
    expires_at: datetime
    result: ActionResult | None = None


class ApprovalToken(BaseModel):
    """The credential returned by ``prepare`` and required by ``confirm``.

    Confirmation requires both the ``action_id`` and this opaque ``token``, so an action
    cannot be confirmed by guessing its id alone.
    """

    action_id: str
    token: str
    action_type: ActionType
    risk_level: RiskLevel
    summary: str
    expires_at: datetime
