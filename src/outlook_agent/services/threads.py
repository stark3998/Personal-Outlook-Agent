"""ThreadService — reconstruct conversations from Outlook's conversation id.

Outlook for Mac exposes a numeric ``conversation_id`` but not RFC References/In-Reply-To,
so threading combines conversation grouping with subject normalization and temporal
ordering (see docs/architecture.md).
"""

from __future__ import annotations

import re

from outlook_agent.domain import Capability, EmailRef, EmailSummary, Recipient, Thread
from outlook_agent.providers.base import CapabilityUnavailable, OutlookProvider

_SUBJECT_PREFIX_RE = re.compile(r"^\s*(re|fw|fwd|aw|wg)\s*:\s*", re.IGNORECASE)


def normalize_subject(subject: str | None) -> str:
    """Strip reply/forward prefixes and collapse whitespace for thread grouping."""
    if not subject:
        return ""
    text = subject
    prev = None
    while prev != text:
        prev = text
        text = _SUBJECT_PREFIX_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


class ThreadService:
    """Builds :class:`Thread` objects from provider conversation data."""

    def __init__(self, provider: OutlookProvider) -> None:
        self._provider = provider

    def _require(self, capability: Capability) -> None:
        if not self._provider.capabilities().has(capability):
            raise CapabilityUnavailable(capability)

    async def get_thread(self, conversation_id: str, *, account_id: str | None = None) -> Thread:
        """Assemble a thread for a conversation id."""
        self._require(Capability.MAIL_THREAD)
        messages = await self._provider.list_conversation(conversation_id, account_id=account_id)
        return self._assemble(conversation_id, messages)

    async def get_thread_for_email(self, ref: EmailRef) -> Thread:
        """Assemble the thread that contains the given message."""
        self._require(Capability.MAIL_THREAD)
        conv = ref.conversation_id
        if conv is None:
            email = await self._provider.get_email(ref)
            conv = email.ref.conversation_id
        if conv is None:
            single = await self._provider.get_email(ref)
            return self._assemble(None, [single])
        messages = await self._provider.list_conversation(conv, account_id=ref.account_id)
        return self._assemble(conv, messages)

    def _assemble(self, conversation_id: str | None, messages: list[EmailSummary]) -> Thread:
        ordered = sorted(
            messages,
            key=lambda m: (m.received_at is None, m.received_at),
        )
        participants = self._participants(ordered)
        latest = ordered[-1].received_at if ordered else None
        subject = next((normalize_subject(m.subject) for m in ordered if m.subject), None)
        return Thread(
            conversation_id=conversation_id,
            normalized_subject=subject,
            messages=ordered,
            participants=participants,
            message_count=len(ordered),
            unread_count=sum(1 for m in ordered if not m.is_read),
            has_attachments=any(m.has_attachments for m in ordered),
            latest_at=latest,
        )

    @staticmethod
    def _participants(messages: list[EmailSummary]) -> list[Recipient]:
        seen: dict[str, Recipient] = {}
        for m in messages:
            if m.sender is None:
                continue
            key = (m.sender.address or m.sender.name or "").lower()
            if key and key not in seen:
                seen[key] = m.sender
        return list(seen.values())
