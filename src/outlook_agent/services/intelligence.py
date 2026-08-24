"""IntelligenceService — composite agent capabilities over the LLM + Outlook services.

All email-derived text is treated as untrusted: it is wrapped with the sanitization
boundary and passed only in the user role. Reply generation returns a proposed draft and
never sends.
"""

from __future__ import annotations

from pydantic import BaseModel

from outlook_agent.domain import (
    CalendarEvent,
    Draft,
    Email,
    EmailRef,
    EmailSummary,
    Thread,
)
from outlook_agent.intelligence.base import LLMProvider
from outlook_agent.security import sanitization
from outlook_agent.services.calendar import CalendarService
from outlook_agent.services.drafts import DraftService
from outlook_agent.services.mail import MailService
from outlook_agent.services.threads import ThreadService


class ActionItems(BaseModel):
    """Extracted action items for a message."""

    ref: EmailRef
    items: list[str]


class ProposedReply(BaseModel):
    """A generated reply proposal — an explicit draft, never auto-sent."""

    in_reply_to: EmailRef
    body: str
    injection_warning: bool = False
    draft: Draft | None = None


class MeetingPrep(BaseModel):
    """A meeting-preparation briefing assembled from an event and related mail."""

    event: CalendarEvent
    related: list[EmailSummary]
    briefing: str


class IntelligenceService:
    """Summaries, extraction, reply proposals, and inbox analytics.

    Depends only on other services (never a concrete provider). Every email-derived string
    is wrapped with the sanitization boundary before it reaches the LLM.
    """

    def __init__(
        self,
        llm: LLMProvider,
        mail: MailService,
        threads: ThreadService,
        drafts: DraftService,
        calendar: CalendarService | None = None,
    ) -> None:
        self._llm = llm
        self._mail = mail
        self._threads = threads
        self._drafts = drafts
        self._calendar = calendar

    @staticmethod
    def _email_text(email: Email) -> str:
        parts = [f"Subject: {email.subject or ''}"]
        if email.sender:
            parts.append(f"From: {email.sender.address or email.sender.name or ''}")
        parts.append(email.body_text or "")
        return "\n".join(parts)

    async def summarize_email(self, ref: EmailRef) -> str:
        """Summarize a single message."""
        email = await self._mail.get_email(ref)
        content = sanitization.wrap_untrusted(self._email_text(email))
        return await self._llm.summarize(content)

    async def summarize_thread(self, conversation_id: str, *, account_id: str | None = None) -> str:
        """Summarize a whole conversation."""
        thread: Thread = await self._threads.get_thread(conversation_id, account_id=account_id)
        joined = "\n\n---\n\n".join(
            f"{m.sender.address if m.sender else ''}: {m.preview or m.subject or ''}"
            for m in thread.messages
        )
        return await self._llm.summarize(sanitization.wrap_untrusted(joined))

    async def extract_action_items(self, ref: EmailRef) -> ActionItems:
        """Extract action items from a message."""
        email = await self._mail.get_email(ref)
        content = sanitization.wrap_untrusted(self._email_text(email))
        items = await self._llm.extract(content, "action items")
        return ActionItems(ref=ref, items=items)

    async def prepare_reply(
        self, ref: EmailRef, instructions: str, *, create_draft: bool = False
    ) -> ProposedReply:
        """Generate a reply proposal. Optionally save it as a draft. Never sends."""
        email = await self._mail.get_email(ref)
        raw = self._email_text(email)
        proposal = ProposedReply(
            in_reply_to=ref,
            body=await self._llm.generate_reply(sanitization.wrap_untrusted(raw), instructions),
            injection_warning=sanitization.looks_like_injection(raw),
        )
        if create_draft:
            proposal.draft = await self._drafts.reply(ref, body=proposal.body)
        return proposal

    # --- Composite inbox analytics (Phase 16) -----------------------------------------

    async def _my_addresses(self) -> set[str]:
        accounts = await self._mail.list_accounts()
        return {a.email_address.lower() for a in accounts if a.email_address}

    @staticmethod
    def _is_me(summary: EmailSummary, mine: set[str]) -> bool:
        addr = summary.sender.address if summary.sender else None
        return bool(addr and addr.lower() in mine)

    async def summarize_inbox(self, account_id: str, folder_id: str, *, limit: int = 20) -> str:
        """Summarize the most recent messages in a folder as an inbox digest."""
        summaries = await self._mail.list_emails(account_id, folder_id, limit=limit)
        lines = [
            f"- {s.subject or '(no subject)'} — from "
            f"{(s.sender.name or s.sender.address) if s.sender else 'unknown'}"
            f"{' [unread]' if not s.is_read else ''}"
            for s in summaries
        ]
        digest = sanitization.wrap_untrusted("\n".join(lines))
        return await self._llm.summarize(
            digest, instructions="Summarize this inbox into themes and what needs attention."
        )

    async def find_unanswered(
        self, account_id: str, folder_id: str, *, limit: int = 50
    ) -> list[EmailSummary]:
        """Return inbox messages from others that have no later reply from me."""
        mine = await self._my_addresses()
        summaries = await self._mail.list_emails(account_id, folder_id, limit=limit)
        unanswered: list[EmailSummary] = []
        for s in summaries:
            if self._is_me(s, mine):
                continue
            if not await self._replied_after(s, mine):
                unanswered.append(s)
        return unanswered

    async def find_followups(
        self, account_id: str, sent_folder_id: str, *, limit: int = 50
    ) -> list[EmailSummary]:
        """Return messages I sent that are the latest in their thread (awaiting a reply)."""
        mine = await self._my_addresses()
        sent = await self._mail.list_emails(account_id, sent_folder_id, limit=limit)
        followups: list[EmailSummary] = []
        for s in sent:
            thread = await self._thread_for(s)
            if not thread.messages:
                continue
            last = thread.messages[-1]
            if self._is_me(last, mine) and last.ref.item_id == s.ref.item_id:
                followups.append(s)
        return followups

    async def find_promised_actions(
        self, account_id: str, sent_folder_id: str, *, limit: int = 25
    ) -> list[str]:
        """Use the LLM to detect commitments I made in recently sent mail."""
        sent = await self._mail.list_emails(account_id, sent_folder_id, limit=limit)
        joined = "\n\n---\n\n".join(f"{s.subject or ''}: {s.preview or ''}" for s in sent)
        return await self._llm.extract(
            sanitization.wrap_untrusted(joined), "commitments or promises the sender made"
        )

    async def meeting_prep(self, account_id: str, event_id: str) -> MeetingPrep:
        """Assemble a briefing for an upcoming event from related mail."""
        if self._calendar is None:
            raise RuntimeError("meeting_prep requires a CalendarService")
        event = await self._calendar.get_event(account_id, event_id)
        related: list[EmailSummary] = []
        if event.subject:
            related = await self._mail.search_emails(event.subject, limit=10)
        context = sanitization.wrap_untrusted(
            f"Meeting: {event.subject}\nWhen: {event.start}\nLocation: {event.location}\n\n"
            + "\n".join(f"- {r.subject}: {r.preview or ''}" for r in related)
        )
        briefing = await self._llm.summarize(
            context, instructions="Prepare me for this meeting: context, open items, questions."
        )
        return MeetingPrep(event=event, related=related, briefing=briefing)

    async def _thread_for(self, summary: EmailSummary) -> Thread:
        conv = summary.ref.conversation_id
        if conv:
            return await self._threads.get_thread(conv, account_id=summary.ref.account_id)
        return Thread(messages=[summary], message_count=1)

    async def _replied_after(self, summary: EmailSummary, mine: set[str]) -> bool:
        thread = await self._thread_for(summary)
        anchor = summary.received_at
        for m in thread.messages:
            if not self._is_me(m, mine):
                continue
            when = m.sent_at or m.received_at
            if anchor is None or (when is not None and when >= anchor):
                return True
        return False
