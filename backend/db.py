"""SQLAlchemy engine, session factory, and FastAPI session dependency."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session, closes it after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
