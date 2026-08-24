"""SQLAlchemy engine/session setup for the local SQLite cache."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def create_db_engine(url: str = "sqlite:///outlook_agent.db") -> Engine:
    """Create the SQLite engine and enable sane pragmas."""
    engine = create_engine(url, future=True)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn: object, _record: object) -> None:  # sqlalchemy callback
        cur = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def init_db(engine: Engine) -> None:
    """Create ORM tables and the FTS5 virtual table."""
    Base.metadata.create_all(engine)
    from .fts import create_fts

    create_fts(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a configured session factory."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transactional session context manager."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
