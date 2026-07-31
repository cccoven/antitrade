import os
import pathlib

os.environ.setdefault("LLM_PROVIDER", "demo")
os.environ.setdefault("SCHEDULER_ENABLED", "0")
os.environ.setdefault(
    "MFA_ENCRYPTION_KEY",
    "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
)

# macOS Docker Desktop exposes the socket at a non-standard path; help
# testcontainers find it when DOCKER_HOST is not already set.
_macos_sock = pathlib.Path.home() / ".docker" / "run" / "docker.sock"
if not os.environ.get("DOCKER_HOST") and _macos_sock.exists():
    os.environ["DOCKER_HOST"] = f"unix://{_macos_sock}"

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

import db as db_module
import models  # noqa: F401  (registers tables on Base.metadata)

_PRESETS = [
    ("证券", "asset", 10), ("现金", "asset", 20), ("保险/信托", "asset", 40),
    ("实物资产", "asset", 50), ("其他", "asset", 60), ("负债", "liability", 70),
]


@pytest.fixture(scope="session")
def _pg_engine():
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as pg:
        engine = create_engine(pg.get_connection_url(), future=True)
        with engine.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db_module.Base.metadata.create_all(engine)
        with engine.begin() as c:
            for n, k, o in _PRESETS:
                c.execute(
                    text("INSERT INTO portfolio_categories (id, user_id, name, kind, sort_order) "
                         "VALUES (:id, NULL, :n, :k, :o)"),
                    {"id": str(uuid.uuid4()), "n": n, "k": k, "o": o},
                )
        yield engine
        engine.dispose()


@pytest.fixture
def db(_pg_engine, monkeypatch):
    """A Session in a transaction that is rolled back after each test."""
    connection = _pg_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    monkeypatch.setattr(db_module, "engine", _pg_engine, raising=True)
    monkeypatch.setattr(db_module, "SessionLocal", lambda: session, raising=True)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def user_id(db):
    from models import User
    uid = str(uuid.uuid4())
    db.add(User(id=uid, email=f"{uid}@t.test", password="x", name="T",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    return uid
