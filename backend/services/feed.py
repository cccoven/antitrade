"""Feed queries + bookmarks for the radar page."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from models import FeedBriefing, FeedBookmark, FeedItem
from services.feed_language import briefing_content_matches_language
from services.market_data_runtime import get_market_data_gateway
from services.market_gateway import InstrumentSearch


def feed_symbol_labels(symbols: list[str]) -> dict[str, str]:
    gateway = get_market_data_gateway()
    labels: dict[str, str] = {}
    for instrument_id in symbols:
        instrument = gateway.resolve_instrument(InstrumentSearch(text=instrument_id))
        labels[instrument_id] = (
            instrument.display_symbol if instrument is not None else instrument_id
        )
    return labels


class FeedService:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _item_to_dict(row: FeedItem) -> dict:
        symbols = list(row.symbols or [])
        return {
            "id": row.id, "url": row.url, "source_key": row.source_key,
            "title": row.title, "summary": row.summary,
            "published_at": row.published_at, "fetched_at": row.fetched_at,
            "category": row.category, "symbols": symbols,
            "symbol_labels": feed_symbol_labels(symbols), "lang": row.lang,
        }

    def list_items(self, page: int = 1, page_size: int = 20,
                   category: str | None = None, source: str | None = None,
                   lang: str | None = None, q: str | None = None,
                   symbol: str | None = None) -> dict:
        stmt = select(FeedItem)
        count_stmt = select(func.count()).select_from(FeedItem)
        conds = []
        if category:
            conds.append(FeedItem.category == category)
        if source:
            conds.append(FeedItem.source_key == source)
        if lang:
            conds.append(FeedItem.lang == lang)
        if q:
            like = f"%{q}%"
            conds.append(FeedItem.title.ilike(like) | FeedItem.summary.ilike(like))
        if symbol:
            instrument = get_market_data_gateway().resolve_instrument(
                InstrumentSearch(text=symbol),
            )
            canonical_symbol = instrument.id if instrument is not None else symbol
            # symbols is a Postgres JSON column; cast to JSONB for containment.
            conds.append(cast(FeedItem.symbols, JSONB).contains([canonical_symbol]))
        total = self.session.execute(count_stmt.where(*conds)).scalar_one()
        rows = self.session.execute(
            stmt.where(*conds)
            # Newest first by publish time (the timeline rail shows published_at);
            # fall back to fetched_at when a source omits published_at.
            .order_by(func.coalesce(FeedItem.published_at, FeedItem.fetched_at).desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()
        items = [self._item_to_dict(r) for r in rows]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get_item(self, item_id: str) -> dict | None:
        row = self.session.execute(
            select(FeedItem).where(FeedItem.id == item_id)
        ).scalar_one_or_none()
        return self._item_to_dict(row) if row is not None else None

    def get_items_by_ids(self, item_ids: list[str]) -> dict[str, dict]:
        unique_ids = list(dict.fromkeys(item_ids))
        if not unique_ids:
            return {}
        rows = self.session.execute(
            select(FeedItem).where(FeedItem.id.in_(unique_ids))
        ).scalars().all()
        return {row.id: self._item_to_dict(row) for row in rows}

    def get_latest_briefing(self, lang: str) -> dict | None:
        rows = self.session.execute(
            select(FeedBriefing).where(FeedBriefing.lang == lang)
            .order_by(FeedBriefing.generated_at.desc()).limit(20)
        ).scalars().all()
        for row in rows:
            if briefing_content_matches_language(row.content, lang):
                return {
                    "id": row.id, "generated_at": row.generated_at, "lang": row.lang,
                    "window": row.window, "content": row.content, "model": row.model,
                }
        return None

    def list_bookmarks(self, user_id: str) -> list[dict]:
        rows = self.session.execute(
            select(FeedBookmark).where(FeedBookmark.user_id == user_id)
            .order_by(FeedBookmark.created_at.desc())
        ).scalars().all()
        return [{"id": r.id, "feed_item_id": r.feed_item_id, "created_at": r.created_at}
                for r in rows]

    def list_bookmarked_items(self, user_id: str, page: int = 1,
                              page_size: int = 20) -> dict:
        """Bookmarked news with full item content, newest bookmark first."""
        base = (
            select(FeedItem, FeedBookmark.id, FeedBookmark.created_at)
            .join(FeedBookmark, FeedBookmark.feed_item_id == FeedItem.id)
            .where(FeedBookmark.user_id == user_id)
        )
        total = self.session.execute(
            select(func.count()).select_from(FeedBookmark)
            .where(FeedBookmark.user_id == user_id)
        ).scalar_one()
        rows = self.session.execute(
            base.order_by(FeedBookmark.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        items = []
        for item, bookmark_id, bookmarked_at in rows:
            d = self._item_to_dict(item)
            d["bookmark_id"] = bookmark_id
            d["bookmarked_at"] = bookmarked_at
            items.append(d)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def add_bookmark(self, user_id: str, feed_item_id: str) -> dict | None:
        item = self.session.get(FeedItem, feed_item_id)
        if item is None:
            return None
        existing = self.session.execute(
            select(FeedBookmark).where(
                FeedBookmark.user_id == user_id,
                FeedBookmark.feed_item_id == feed_item_id)
        ).scalar_one_or_none()
        if existing:
            return {"id": existing.id, "feed_item_id": existing.feed_item_id,
                    "created_at": existing.created_at}
        bm = FeedBookmark(id=str(uuid4()), user_id=user_id, feed_item_id=feed_item_id,
                          created_at=datetime.now(timezone.utc).isoformat())
        self.session.add(bm)
        self.session.commit()
        return {"id": bm.id, "feed_item_id": bm.feed_item_id, "created_at": bm.created_at}

    def remove_bookmark(self, user_id: str, bookmark_id: str) -> bool:
        row = self.session.execute(
            select(FeedBookmark).where(
                FeedBookmark.id == bookmark_id, FeedBookmark.user_id == user_id)
        ).scalar_one_or_none()
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True
