import uuid
from datetime import datetime, timezone

from models import FeedItem
from services.feed import FeedService


def _seed(db, title="t", category="general", symbols=None, lang="en"):
    now = datetime.now(timezone.utc).isoformat()
    item = FeedItem(id=str(uuid.uuid4()), url=f"https://x/{uuid.uuid4()}",
                    source_key="s", title=title, summary="body",
                    published_at=now, fetched_at=now, category=category,
                    symbols=symbols or [], lang=lang)
    db.add(item)
    db.flush()
    return item


def test_list_items_filters_by_category(db):
    _seed(db, category="crypto")
    _seed(db, category="macro")
    svc = FeedService(db)
    result = svc.list_items(category="crypto")
    assert result["total"] == 1
    assert result["items"][0]["category"] == "crypto"


def test_list_items_pagination(db):
    for _ in range(3):
        _seed(db)
    svc = FeedService(db)
    page = svc.list_items(page=1, page_size=2)
    assert len(page["items"]) == 2
    assert page["total"] == 3


def test_list_items_filters_by_symbol(db):
    _seed(db, symbols=["instrument:crypto:btc-usd"])
    _seed(db, symbols=["instrument:spot:xau-usd"])
    svc = FeedService(db)
    result = svc.list_items(symbol="BTCUSD")
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert "instrument:crypto:btc-usd" in result["items"][0]["symbols"]
    assert result["items"][0]["symbol_labels"] == {
        "instrument:crypto:btc-usd": "BTC/USD",
    }


def test_get_latest_briefing_returns_newest_or_none(db):
    import uuid
    from models import FeedBriefing
    svc = FeedService(db)
    assert svc.get_latest_briefing("en") is None
    db.add(FeedBriefing(id=str(uuid.uuid4()), generated_at="2026-07-01T00:00:00+00:00",
                        lang="en", window="6h", content={"hot": [], "sections": []}, model="rule"))
    db.add(FeedBriefing(id=str(uuid.uuid4()), generated_at="2026-07-01T06:00:00+00:00",
                        lang="en", window="6h", content={"hot": [], "sections": []}, model="rule"))
    db.flush()
    latest = svc.get_latest_briefing("en")
    assert latest is not None
    assert latest["generated_at"] == "2026-07-01T06:00:00+00:00"


def test_get_latest_briefing_skips_wrong_language_content(db):
    import uuid
    from models import FeedBriefing

    db.add(FeedBriefing(
        id=str(uuid.uuid4()),
        generated_at="2026-07-01T05:00:00+00:00",
        lang="en",
        window="6h",
        content={
            "hot": [{"title": "Fed holds rates", "sources": 1}],
            "sections": [{"category": "macro", "points": [{"text": "Rates unchanged"}]}],
        },
        model="rule",
    ))
    db.add(FeedBriefing(
        id=str(uuid.uuid4()),
        generated_at="2026-07-01T06:00:00+00:00",
        lang="en",
        window="6h",
        content={
            "hot": [{"title": "美联储维持利率不变", "sources": 1}],
            "sections": [{"category": "macro", "points": [{"text": "利率保持不变"}]}],
        },
        model="rule",
    ))
    db.flush()

    latest = FeedService(db).get_latest_briefing("en")

    assert latest is not None
    assert latest["generated_at"] == "2026-07-01T05:00:00+00:00"


def test_bookmark_add_list_remove(db, user_id):
    item = _seed(db)
    svc = FeedService(db)
    bm = svc.add_bookmark(user_id, item.id)
    assert svc.list_bookmarks(user_id)[0]["feed_item_id"] == item.id
    assert svc.remove_bookmark(user_id, bm["id"]) is True
    assert svc.list_bookmarks(user_id) == []


def test_add_bookmark_idempotent(db, user_id):
    item = _seed(db)
    svc = FeedService(db)
    svc.add_bookmark(user_id, item.id)
    svc.add_bookmark(user_id, item.id)  # duplicate → no error, single row
    assert len(svc.list_bookmarks(user_id)) == 1
