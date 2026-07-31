import pathlib

from sqlalchemy import select

from models import FeedItem
from services.feed_ingest import ingest_entries
from services.feed_sources import FeedSource

_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "sample_feed.xml"


def _entries():
    import feedparser
    return feedparser.parse(_FIXTURE.read_text())["entries"]


def _source():
    return FeedSource("test_src", "https://example.com/rss", "en", "general")


def test_ingest_inserts_classified_items(db):
    n = ingest_entries(db, _source(), _entries())
    db.flush()
    rows = db.execute(select(FeedItem)).scalars().all()
    assert n == 2
    assert len(rows) == 2
    btc = next(r for r in rows if "Bitcoin" in r.title)
    assert btc.category == "crypto"
    assert "instrument:crypto:btc-usd" in btc.symbols
    assert btc.source_key == "test_src"


def test_ingest_dedupes_by_url(db):
    ingest_entries(db, _source(), _entries())
    db.flush()
    inserted_second = ingest_entries(db, _source(), _entries())
    db.flush()
    rows = db.execute(select(FeedItem)).scalars().all()
    assert inserted_second == 0
    assert len(rows) == 2


def test_ingest_skips_in_batch_duplicate_urls(db):
    entries = [
        {"title": "BTC one", "link": "https://example.com/dup", "summary": "a"},
        {"title": "BTC two", "link": "https://example.com/dup", "summary": "b"},
    ]
    n = ingest_entries(db, _source(), entries)
    db.flush()
    rows = db.execute(select(FeedItem)).scalars().all()
    assert n == 1
    assert len(rows) == 1


def test_ingest_uses_content_language_instead_of_source_label(db):
    entries = [{
        "title": "美联储维持利率不变",
        "link": "https://example.com/zh-from-en-source",
        "summary": "市场等待发布会。",
    }]

    ingest_entries(db, _source(), entries)
    db.flush()

    item = db.execute(select(FeedItem)).scalar_one()
    assert item.lang == "zh"


def test_repair_feed_languages_fixes_existing_mislabeled_items(db):
    from services.feed_ingest import repair_feed_item_languages

    item = FeedItem(
        id="mislabeled",
        url="https://example.com/mislabeled",
        source_key="test_src",
        title="黄金价格刷新历史高位",
        summary="投资者关注美联储政策。",
        published_at=None,
        fetched_at="2026-07-28T00:00:00+00:00",
        category="metals",
        symbols=[],
        lang="en",
    )
    db.add(item)
    db.flush()

    assert repair_feed_item_languages(db) == 1
    assert item.lang == "zh"
