"""SQLite FTS5 full-text index over cached emails.

The FTS table mirrors ``emails`` and is kept in sync by the repository on upsert. Using an
external-content-free contentless-ish table keeps the implementation simple and portable.
"""

from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
    email_id UNINDEXED,
    subject,
    sender,
    body_text
)
"""


def create_fts(engine: Engine) -> None:
    """Create the FTS5 virtual table if it does not exist."""
    with engine.begin() as conn:
        conn.execute(text(_CREATE))


def index_email(
    conn: Connection, *, email_id: int, subject: str, sender: str, body_text: str
) -> None:
    """Insert/replace an email's row in the FTS index."""
    conn.execute(text("DELETE FROM emails_fts WHERE email_id = :eid"), {"eid": email_id})
    conn.execute(
        text(
            "INSERT INTO emails_fts (email_id, subject, sender, body_text) "
            "VALUES (:eid, :subject, :sender, :body)"
        ),
        {"eid": email_id, "subject": subject, "sender": sender, "body": body_text},
    )


def search_ids(conn: Connection, query: str, *, limit: int = 25) -> list[int]:
    """Return email row ids matching an FTS query, best matches first."""
    rows = conn.execute(
        text("SELECT email_id FROM emails_fts WHERE emails_fts MATCH :q ORDER BY rank LIMIT :lim"),
        {"q": query, "lim": limit},
    ).fetchall()
    return [int(r[0]) for r in rows]
