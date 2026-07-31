import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from models import FeedItem, FeedBriefing, FeedBookmark


def test_feed_item_roundtrip(db):
    now = datetime.now(timezone.utc).isoformat()
    item = FeedItem(
        id=str(uuid.uuid4()), url="https://ex.com/a", source_key="cnbc_top",
        title="BTC rallies", summary="...", published_at=now, fetched_at=now,
        category="crypto", symbols=["instrument:crypto:btc-usd"], lang="en",
    )
    db.add(item)
    db.flush()
    db.expire(item)
    got = db.get(FeedItem, item.id)
    assert got.symbols == ["instrument:crypto:btc-usd"]
    assert got.category == "crypto"


def test_feed_bookmark_unique(db, user_id):
    now = datetime.now(timezone.utc).isoformat()
    item = FeedItem(id=str(uuid.uuid4()), url="https://ex.com/b", source_key="s",
                    title="t", summary="", fetched_at=now, category="general",
                    symbols=[], lang="en")
    db.add(item)
    db.flush()
    db.add(FeedBookmark(id=str(uuid.uuid4()), user_id=user_id, feed_item_id=item.id, created_at=now))
    db.flush()
    # duplicate (user_id, feed_item_id) must violate uq_feed_bookmarks_user_item
    with pytest.raises(IntegrityError):
        db.add(FeedBookmark(id=str(uuid.uuid4()), user_id=user_id, feed_item_id=item.id, created_at=now))
        db.flush()
