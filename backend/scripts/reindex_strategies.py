"""Re-embed all (or one user's) strategies into strategy_embeddings.

Run from backend/:  ./.venv/bin/python scripts/reindex_strategies.py [--user <id>]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import SessionLocal  # noqa: E402
from models import Strategy  # noqa: E402
from services.rag import embed_strategy  # noqa: E402
from sqlalchemy import select  # noqa: E402


def main() -> int:
    user = None
    if "--user" in sys.argv:
        user = sys.argv[sys.argv.index("--user") + 1]
    session = SessionLocal()
    try:
        stmt = select(Strategy)
        if user:
            stmt = stmt.where(Strategy.user_id == user)
        rows = session.execute(stmt).scalars().all()
        for s in rows:
            embed_strategy(session, s.user_id, s.id, s.body)
            print(f"  reindexed {s.id} {s.title}")
        print(f"Reindexed {len(rows)} strategies.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
