"""Strategy service — CRUD for user strategies via SQLAlchemy 2.0 session."""
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.orm import Session

from models import Strategy, Trade


class StrategyService:
    def __init__(self, session: Session):
        self.session = session

    def _reembed(self, user_id: str, strategy_id: str, body: str) -> None:
        try:
            from services.rag import embed_strategy
            embed_strategy(self.session, user_id, strategy_id, body)
        except Exception:
            self.session.rollback()
            logger.warning("strategy embedding failed for %s", strategy_id, exc_info=True)

    @staticmethod
    def _row_to_dict(row: Strategy) -> dict:
        d = {
            "id": row.id,
            "user_id": row.user_id,
            "title": row.title,
            "body": row.body,
            "tags": row.tags,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        if isinstance(d.get("tags"), str):
            try:
                d["tags"] = json.loads(d["tags"])
            except (json.JSONDecodeError, TypeError):
                d["tags"] = []
        return d

    def _performance_by_strategy(
        self,
        user_id: str,
        strategy_ids: list[str],
    ) -> dict[str, dict]:
        if not strategy_ids:
            return {}
        rows = self.session.execute(
            select(
                Trade.strategy_id,
                func.count(Trade.id).label("trade_count"),
                func.sum(case((Trade.pnl > 0, 1), else_=0)).label("wins"),
            )
            .where(
                Trade.user_id == user_id,
                Trade.strategy_id.in_(strategy_ids),
                Trade.pnl.isnot(None),
            )
            .group_by(Trade.strategy_id)
        ).all()
        return {
            row.strategy_id: {
                "trade_count": int(row.trade_count),
                "win_rate": float(row.wins or 0) / row.trade_count * 100,
            }
            for row in rows
        }

    def _with_performance(self, row: Strategy, performance: dict | None = None) -> dict:
        payload = self._row_to_dict(row)
        payload.update(performance or {"trade_count": 0, "win_rate": None})
        return payload

    def create_strategy(
        self,
        user_id: str,
        title: str = "",
        body: str = "",
        tags: list[str] | None = None,
    ) -> dict:
        sid = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags if tags is not None else [], ensure_ascii=False)
        strategy = Strategy(
            id=sid,
            user_id=user_id,
            title=title,
            body=body,
            tags=tags_json,
            created_at=now,
            updated_at=now,
        )
        self.session.add(strategy)
        self.session.commit()
        result = self.get_strategy(user_id, sid)
        self._reembed(user_id, sid, body)
        return result  # type: ignore[return-value]

    def get_strategy(self, user_id: str, strategy_id: str) -> dict | None:
        row = self.session.execute(
            select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            return None
        performance = self._performance_by_strategy(user_id, [row.id]).get(row.id)
        return self._with_performance(row, performance)

    def list_strategies(self, user_id: str) -> list[dict]:
        rows = self.session.execute(
            select(Strategy).where(Strategy.user_id == user_id).order_by(Strategy.updated_at.desc())
        ).scalars().all()
        performance = self._performance_by_strategy(user_id, [row.id for row in rows])
        return [self._with_performance(row, performance.get(row.id)) for row in rows]

    def list_strategy_options(self, user_id: str) -> list[dict]:
        rows = self.session.execute(
            select(Strategy.id, Strategy.title)
            .where(Strategy.user_id == user_id)
            .order_by(Strategy.updated_at.desc())
        ).all()
        return [{"id": r.id, "title": r.title} for r in rows]

    def patch_strategy(
        self,
        user_id: str,
        strategy_id: str,
        title: str | None = None,
        body: str | None = None,
        tags: list[str] | None = None,
    ) -> dict | None:
        existing = self.get_strategy(user_id, strategy_id)
        if existing is None:
            return None
        values: dict = {}
        if title is not None:
            values["title"] = title
        if body is not None:
            values["body"] = body
        if tags is not None:
            values["tags"] = json.dumps(tags, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()
        values["updated_at"] = now
        self.session.execute(
            update(Strategy)
            .where(Strategy.id == strategy_id, Strategy.user_id == user_id)
            .values(**values)
        )
        self.session.commit()
        result = self.get_strategy(user_id, strategy_id)
        if result is not None:
            self._reembed(user_id, strategy_id, result["body"])
        return result

    def delete_strategy(self, user_id: str, strategy_id: str) -> bool:
        existing = self.get_strategy(user_id, strategy_id)
        if existing is None:
            return False
        # Null out references in trades before deleting
        self.session.execute(
            update(Trade)
            .where(Trade.strategy_id == strategy_id, Trade.user_id == user_id)
            .values(strategy_id=None)
        )
        self.session.execute(
            delete(Strategy)
            .where(Strategy.id == strategy_id, Strategy.user_id == user_id)
        )
        self.session.commit()
        return True
