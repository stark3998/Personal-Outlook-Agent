"""SQLAlchemy ORM models for the local cache/index."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for cache tables."""


class EmailRecord(Base):
    """Cached message summary/body, keyed by provider identity."""

    __tablename__ = "emails"
    __table_args__ = (UniqueConstraint("account_id", "item_id", name="uq_email_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    folder_id: Mapped[str] = mapped_column(String(64), index=True)
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender: Mapped[str | None] = mapped_column(String(256), nullable=True)
    preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SyncState(Base):
    """Per-folder synchronization bookkeeping."""

    __tablename__ = "sync_state"
    __table_args__ = (UniqueConstraint("account_id", "folder_id", name="uq_sync_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    folder_id: Mapped[str] = mapped_column(String(64), index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_item_count: Mapped[int] = mapped_column(default=0)


class ActionRecord(Base):
    """Persisted prepared action + its confirmation token (JSON blob)."""

    __tablename__ = "actions"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    token: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)  # Action serialized as JSON


class AuditRecord(Base):
    """Append-only persisted audit event (JSON blob)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[str] = mapped_column(String(64), index=True)
    event: Mapped[str] = mapped_column(String(32))
    payload: Mapped[str] = mapped_column(Text)  # AuditEvent serialized as JSON
