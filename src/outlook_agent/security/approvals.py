"""Approval store — persistence boundary for prepared actions.

An in-memory implementation is provided for the current process; a SQLite-backed store
(surviving restarts, shareable with the CLI) is a later milestone. Both satisfy the
:class:`ApprovalStore` protocol so the ActionService is agnostic.
"""

from __future__ import annotations

import secrets
from typing import Protocol, runtime_checkable

from outlook_agent.domain import Action


def new_action_id() -> str:
    """Generate an unguessable action id."""
    return secrets.token_urlsafe(12)


def new_token() -> str:
    """Generate an unguessable confirmation token."""
    return secrets.token_urlsafe(24)


@runtime_checkable
class ApprovalStore(Protocol):
    """Storage for prepared actions and their confirmation tokens."""

    async def save(self, action: Action, token: str) -> None:
        """Persist a newly-prepared action with its confirmation token."""
        ...

    async def get(self, action_id: str) -> Action | None:
        """Return the action, or ``None`` if unknown."""
        ...

    async def token_for(self, action_id: str) -> str | None:
        """Return the confirmation token for an action, or ``None``."""
        ...

    async def update(self, action: Action) -> None:
        """Persist a status/result change for an existing action."""
        ...

    async def pending(self) -> list[Action]:
        """Return all actions still awaiting confirmation."""
        ...


class InMemoryApprovalStore:
    """Process-local approval store. Tokens are stored separately from the action."""

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}
        self._tokens: dict[str, str] = {}

    async def save(self, action: Action, token: str) -> None:
        self._actions[action.action_id] = action
        self._tokens[action.action_id] = token

    async def get(self, action_id: str) -> Action | None:
        return self._actions.get(action_id)

    async def token_for(self, action_id: str) -> str | None:
        return self._tokens.get(action_id)

    async def update(self, action: Action) -> None:
        self._actions[action.action_id] = action

    async def pending(self) -> list[Action]:
        from outlook_agent.domain import ActionStatus

        return [a for a in self._actions.values() if a.status is ActionStatus.PENDING]
