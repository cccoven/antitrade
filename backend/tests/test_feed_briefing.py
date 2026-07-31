import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from models import FeedItem, FeedBriefing
from services.feed_briefing import generate_briefing, build_rule_briefing


class _FakeProvider:
    def __init__(self, raw):
        self._raw = raw

    async def complete(self, prompt):
        return self._raw


def _seed(db, title, category, symbols):
    now = datetime.now(timezone.utc).isoformat()
    db.add(FeedItem(id=str(uuid.uuid4()), url=f"https://x/{uuid.uuid4()}",
                    source_key="s", title=title, summary="body",
                    published_at=now, fetched_at=now, category=category,
                    symbols=symbols, lang="en"))
    db.flush()


def test_rule_briefing_groups_by_category(db):
    _seed(db, "BTC up", "crypto", ["instrument:crypto:btc-usd"])
    _seed(db, "Fed holds", "macro", [])
    items = db.execute(select(FeedItem)).scalars().all()
    content = build_rule_briefing(items)
    cats = {s["category"] for s in content["sections"]}
    assert "crypto" in cats and "macro" in cats
    assert len(content["hot"]) >= 1


def test_generate_briefing_persists_row(db):
    _seed(db, "BTC up", "crypto", ["instrument:crypto:btc-usd"])
    briefing = generate_briefing(db, lang="en", window_hours=24)
    db.flush()
    assert briefing is not None
    rows = db.execute(select(FeedBriefing)).scalars().all()
    assert len(rows) == 1
    assert rows[0].lang == "en"
    assert rows[0].model == "rule"
    assert "hot" in rows[0].content and "sections" in rows[0].content


def test_generate_briefing_no_items_returns_none(db):
    assert generate_briefing(db, lang="en", window_hours=24) is None


def _seed_lang(db, title, lang):
    now = datetime.now(timezone.utc).isoformat()
    db.add(FeedItem(id=str(uuid.uuid4()), url=f"https://x/{uuid.uuid4()}",
                    source_key="s", title=title, summary="body",
                    published_at=now, fetched_at=now, category="general",
                    symbols=[], lang=lang))
    db.flush()


def test_generate_briefing_scopes_to_language(db):
    # An "en" briefing must never fold in zh items — titles pass through verbatim,
    # so mixing languages would leak the wrong script into the hot list.
    _seed_lang(db, "中文标题", "zh")
    _seed_lang(db, "English headline", "en")
    briefing = generate_briefing(db, lang="en", window_hours=24)
    db.flush()
    assert briefing is not None
    titles = [h["title"] for h in briefing.content["hot"]]
    assert titles == ["English headline"]


def test_generate_briefing_returns_none_when_only_other_lang(db):
    _seed_lang(db, "中文标题", "zh")
    assert generate_briefing(db, lang="en", window_hours=24) is None


def test_generate_briefing_rejects_mislabeled_source_items(db):
    _seed_lang(db, "美联储维持利率不变", "en")
    assert generate_briefing(db, lang="en", window_hours=24) is None


def test_llm_briefing_parses_valid_json(db, monkeypatch):
    import services.feed_briefing as fb

    raw = '{"hot": [{"title": "X", "sources": 2}], "sections": [{"category": "crypto", "points": ["X"]}]}'
    # create_provider is imported inside _llm_briefing from services.analyzer; patch there.
    monkeypatch.setattr("services.analyzer.create_provider", lambda: _FakeProvider(raw))
    _seed(db, "X", "crypto", ["instrument:crypto:btc-usd"])
    rows = db.execute(select(FeedItem)).scalars().all()
    result = asyncio.run(fb._llm_briefing(rows, "en"))
    assert result is not None
    content, model = result
    assert content["hot"][0]["title"] == "X"
    assert model == "_FakeProvider"


def test_llm_briefing_rejects_wrong_output_language(db, monkeypatch):
    import services.feed_briefing as fb

    raw = (
        '{"hot": [{"title": "比特币上涨", "sources": 1}], '
        '"sections": [{"category": "crypto", "points": [{"text": "市场风险偏好增强"}]}]}'
    )
    monkeypatch.setattr("services.analyzer.create_provider", lambda: _FakeProvider(raw))
    _seed(db, "Bitcoin rises", "crypto", [])
    rows = db.execute(select(FeedItem)).scalars().all()

    assert asyncio.run(fb._llm_briefing(rows, "en")) is None


def test_llm_briefing_rejects_wrong_shape(db, monkeypatch):
    import services.feed_briefing as fb

    monkeypatch.setattr("services.analyzer.create_provider", lambda: _FakeProvider('{"foo": 1}'))
    _seed(db, "X", "crypto", [])
    rows = db.execute(select(FeedItem)).scalars().all()
    assert asyncio.run(fb._llm_briefing(rows, "en")) is None  # missing hot/sections → None


def test_llm_briefing_rejects_malformed_section(db, monkeypatch):
    import services.feed_briefing as fb

    # hot/sections present, but a section is missing its required "points" list.
    raw = '{"hot": [], "sections": [{"category": "crypto"}]}'
    monkeypatch.setattr("services.analyzer.create_provider", lambda: _FakeProvider(raw))
    _seed(db, "X", "crypto", [])
    rows = db.execute(select(FeedItem)).scalars().all()
    assert asyncio.run(fb._llm_briefing(rows, "en")) is None  # malformed section → None


def test_rule_briefing_carries_item_ids(db):
    _seed(db, "BTC up", "crypto", [])
    items = db.execute(select(FeedItem)).scalars().all()
    content = build_rule_briefing(items)
    assert content["hot"][0]["id"] == items[0].id
    pt = content["sections"][0]["points"][0]
    assert pt["text"] == "BTC up" and pt["id"] == items[0].id


def test_llm_briefing_resolves_refs_to_ids(db, monkeypatch):
    import services.feed_briefing as fb

    # Model references source items by their [index]; we map back to real ids.
    raw = ('{"hot": [{"title": "H", "sources": 1, "ref": 0}], '
           '"sections": [{"category": "crypto", "points": [{"text": "P", "ref": 0}]}]}')
    monkeypatch.setattr("services.analyzer.create_provider", lambda: _FakeProvider(raw))
    _seed(db, "X", "crypto", [])
    rows = db.execute(select(FeedItem)).scalars().all()
    content, _ = asyncio.run(fb._llm_briefing(rows, "en"))
    assert content["hot"][0]["id"] == rows[0].id
    assert "ref" not in content["hot"][0]
    assert content["sections"][0]["points"][0] == {"text": "P", "id": rows[0].id}


def test_llm_briefing_normalizes_legacy_string_points(db, monkeypatch):
    import services.feed_briefing as fb

    # Older/other models may emit plain-string points; normalize without an id.
    raw = '{"hot": [{"title": "X", "sources": 2}], "sections": [{"category": "crypto", "points": ["X"]}]}'
    monkeypatch.setattr("services.analyzer.create_provider", lambda: _FakeProvider(raw))
    _seed(db, "X", "crypto", [])
    rows = db.execute(select(FeedItem)).scalars().all()
    content, _ = asyncio.run(fb._llm_briefing(rows, "en"))
    assert content["sections"][0]["points"][0] == {"text": "X"}


def test_resolve_refs_ignores_out_of_range(db):
    import services.feed_briefing as fb

    _seed(db, "X", "crypto", [])
    rows = db.execute(select(FeedItem)).scalars().all()
    content = fb._resolve_refs(
        {"hot": [{"title": "H", "ref": 99}], "sections": []}, rows,
    )
    assert "id" not in content["hot"][0]  # bad index → no id, stays non-clickable
