"""Repositories over the SQLite cache/index."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from outlook_agent.domain import EmailRef, EmailSummary, ProviderName, Recipient

from . import fts
from .database import session_scope
from .models import EmailRecord


class EmailCacheRepository:
    """Upsert and search cached emails, keeping the FTS index in sync."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def upsert(self, summary: EmailSummary, *, body_text: str | None = None) -> int:
        """Insert or update a cached email; returns its row id."""
        with session_scope(self._factory) as session:
            record = self._find(session, summary.ref)
            if record is None:
                record = EmailRecord(
                    account_id=summary.ref.account_id,
                    item_id=summary.ref.item_id,
                )
                session.add(record)
            self._apply(record, summary, body_text)
            session.flush()
            self._reindex(session, record)
            return record.id

    def search(self, query: str, *, limit: int = 25) -> list[EmailSummary]:
        """Full-text search the cache and return summaries."""
        with session_scope(self._factory) as session:
            ids = fts.search_ids(session.connection(), query, limit=limit)
            if not ids:
                return []
            records = list(
                session.execute(select(EmailRecord).where(EmailRecord.id.in_(ids))).scalars().all()
            )
            order = {rid: i for i, rid in enumerate(ids)}
            records.sort(key=lambda r: order.get(r.id, 1_000_000))
            return [self._to_summary(r) for r in records]

    def count(self) -> int:
        """Return the number of cached emails."""
        with session_scope(self._factory) as session:
            return session.query(EmailRecord).count()

    @staticmethod
    def _find(session: Session, ref: EmailRef) -> EmailRecord | None:
        return session.execute(
            select(EmailRecord).where(
                EmailRecord.account_id == ref.account_id,
                EmailRecord.item_id == ref.item_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def _apply(record: EmailRecord, summary: EmailSummary, body_text: str | None) -> None:
        record.folder_id = summary.ref.folder_id
        record.conversation_id = summary.ref.conversation_id
        record.message_id = summary.ref.message_id
        record.subject = summary.subject
        record.sender = summary.sender.address or summary.sender.name if summary.sender else None
        record.preview = summary.preview
        record.is_read = summary.is_read
        record.received_at = summary.received_at
        if body_text is not None:
            record.body_text = body_text

    @staticmethod
    def _reindex(session: Session, record: EmailRecord) -> None:
        fts.index_email(
            session.connection(),
            email_id=record.id,
            subject=record.subject or "",
            sender=record.sender or "",
            body_text=record.body_text or record.preview or "",
        )

    @staticmethod
    def _to_summary(record: EmailRecord) -> EmailSummary:
        sender = Recipient(address=record.sender) if record.sender else None
        return EmailSummary(
            ref=EmailRef(
                provider=ProviderName.OUTLOOK_APPLESCRIPT,
                account_id=record.account_id,
                folder_id=record.folder_id,
                item_id=record.item_id,
                conversation_id=record.conversation_id,
                message_id=record.message_id,
            ),
            subject=record.subject,
            sender=sender,
            preview=record.preview,
            is_read=record.is_read,
            received_at=record.received_at,
        )
