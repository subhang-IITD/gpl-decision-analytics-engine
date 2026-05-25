"""SQLAlchemy engine/session management.

Uses DATABASE_URL when provided (AWS RDS Postgres in production), else a local
SQLite file. The rest of the codebase only ever touches `get_session()` and
`Base`, so swapping the warehouse is a pure config change.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

_settings = get_settings()

# check_same_thread only matters for SQLite + multithreaded servers/Streamlit.
_connect_args = {"check_same_thread": False} if _settings.db.is_sqlite else {}

engine = create_engine(
    _settings.db.url,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=not _settings.db.is_sqlite,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables. Idempotent."""
    from db import schema  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
