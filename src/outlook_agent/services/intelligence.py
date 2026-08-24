"""IntelligenceService — composite agent capabilities over the LLM + Outlook services.

All email-derived text is treated as untrusted: it is wrapped with the sanitization
boundary and passed only in the user role. Reply generation returns a proposed draft and
never sends.
"""

from __future__ import annotations

from pydantic import BaseModel

from outlook_agent.domain import Draft, Email, EmailRef, Thread
from outlook_agent.intelligence.base import LLMProvider
from outlook_agent.security import sanitization
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


class IntelligenceService:
    """Summaries, extraction, and reply proposals. Depends only on interfaces."""

    def __init__(
        self,
        llm: LLMProvider,
        mail: MailService,
        threads: ThreadService,
        drafts: DraftService,
    ) -> None:
        self._llm = llm
        self._mail = mail
        self._threads = threads
        self._drafts = drafts

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
