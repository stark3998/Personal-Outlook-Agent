"""Policy: risk classification and approval requirements for controlled actions."""

from __future__ import annotations

from datetime import timedelta

from outlook_agent.domain import ActionType, RiskLevel

# Actions that permanently remove or externally transmit data are the most dangerous.
_RISK: dict[ActionType, RiskLevel] = {
    ActionType.SEND: RiskLevel.HIGH,
    ActionType.REPLY: RiskLevel.HIGH,
    ActionType.REPLY_ALL: RiskLevel.HIGH,
    ActionType.FORWARD: RiskLevel.HIGH,
    ActionType.DELETE: RiskLevel.CRITICAL,
    ActionType.FOLDER_DELETE: RiskLevel.CRITICAL,
    ActionType.FOLDER_EMPTY: RiskLevel.CRITICAL,
    ActionType.CALENDAR_DELETE: RiskLevel.HIGH,
    ActionType.JUNK: RiskLevel.MEDIUM,
    ActionType.MOVE: RiskLevel.MEDIUM,
    ActionType.ARCHIVE: RiskLevel.MEDIUM,
    ActionType.FOLDER_MOVE: RiskLevel.MEDIUM,
    ActionType.FOLDER_RENAME: RiskLevel.MEDIUM,
    ActionType.FOLDER_CREATE: RiskLevel.LOW,
    ActionType.CALENDAR_CREATE: RiskLevel.MEDIUM,
    ActionType.CALENDAR_UPDATE: RiskLevel.MEDIUM,
    ActionType.CALENDAR_RESPOND: RiskLevel.LOW,
    ActionType.MARK_READ: RiskLevel.LOW,
    ActionType.MARK_UNREAD: RiskLevel.LOW,
    ActionType.SET_FLAG: RiskLevel.LOW,
    ActionType.CLEAR_FLAG: RiskLevel.LOW,
    ActionType.SET_CATEGORIES: RiskLevel.LOW,
}

_TTL: dict[RiskLevel, timedelta] = {
    RiskLevel.LOW: timedelta(minutes=15),
    RiskLevel.MEDIUM: timedelta(minutes=10),
    RiskLevel.HIGH: timedelta(minutes=5),
    RiskLevel.CRITICAL: timedelta(minutes=2),
}


def risk_for(action_type: ActionType) -> RiskLevel:
    """Return the configured risk level for an action type."""
    return _RISK.get(action_type, RiskLevel.HIGH)


def requires_approval(action_type: ActionType) -> bool:
    """Whether an action requires explicit confirmation.

    Every controlled action requires approval; there is no auto-execute path. Kept as a
    function so future policy (e.g. per-account trust) can refine it.
    """
    return action_type in _RISK


def confirmation_ttl(risk: RiskLevel) -> timedelta:
    """How long a prepared action of the given risk remains confirmable."""
    return _TTL.get(risk, timedelta(minutes=5))
