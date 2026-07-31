import asyncio
from datetime import datetime, timezone
from threading import Barrier

from models import FeedItem
from services import market_briefing


def _overview(spy=0.8, qqq=1.1):
    return {
        "quotes": {
            "provider": "gateway",
            "items": [
                {"symbol": "SPY", "label": "S&P 500", "provider": "yahoo", "percent_change": spy, "as_of": "2026-07-16T08:00:00-04:00"},
                {"symbol": "QQQ", "label": "Nasdaq 100", "provider": "yahoo", "percent_change": qqq, "as_of": "2026-07-16T08:00:00-04:00"},
                {"symbol": "GLD", "label": "Gold", "provider": "yahoo", "percent_change": -0.2, "as_of": "2026-07-16T08:00:00-04:00"},
                {"symbol": "BTC/USD", "label": "Bitcoin", "provider": "yahoo", "percent_change": 0.5, "as_of": "2026-07-16T08:00:00-04:00"},
            ],
        },
        "macro": [
            {"series_id": "DGS2", "latest": {"date": "2026-07-15", "value": 4.1}},
            {"series_id": "DGS10", "latest": {"date": "2026-07-15", "value": 4.3}},
            {"series_id": "CPIAUCSL", "latest": {"date": "2026-06-01", "value": 320.0}},
        ],
        "states": {"risk": "risk_on"},
    }


def _calendar():
    event_at = datetime.now(timezone.utc)
    return {
        "provider": "forex_factory",
        "source_url": "https://www.forexfactory.com/calendar",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": [{
            "title": "CPI",
            "currency": "USD",
            "date": event_at.isoformat(),
            "impact": "high",
            "actual": None,
            "forecast": "2.6%",
            "previous": "2.7%",
        }],
    }


def test_daily_briefing_uses_rule_fallback_and_feed_news(db, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    db.add(FeedItem(
        id="feed-1",
        url="https://example.test/news",
        source_key="example",
        title="Fed officials speak later today",
        summary="Policy remarks are scheduled.",
        published_at=now,
        fetched_at=now,
        category="macro",
        symbols=[],
        lang="en",
    ))
    db.flush()
    market_briefing._BRIEFING_CACHE.clear()
    monkeypatch.setattr(market_briefing, "get_market_overview_snapshot", _overview)
    monkeypatch.setattr(market_briefing, "get_economic_calendar", _calendar)
    monkeypatch.setattr(market_briefing, "get_market_news", lambda: {
        "provider": "finnhub", "error": "news_data_not_configured", "items": [],
    })

    out = asyncio.run(market_briefing.get_daily_market_briefing(db, lang="en"))

    assert out["model"] == "rule"
    assert out["regime"]["bias"] == "bullish"
    assert out["regime"]["volatility"] == "event_driven"
    assert out["news"][0]["url"] == "https://example.test/news"
    assert {source["name"] for source in out["sources"]} >= {"Yahoo Finance", "FRED", "Forex Factory", "Radar RSS"}


def test_daily_briefing_fetches_independent_sources_concurrently(monkeypatch):
    barrier = Barrier(3, timeout=2)

    def overview():
        barrier.wait()
        return _overview()

    def calendar():
        barrier.wait()
        return _calendar()

    def news():
        barrier.wait()
        return {
            "provider": "finnhub",
            "items": [{
                "title": "Market headline",
                "summary": "Summary",
                "source": "Wire",
                "url": "https://example.test/story",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "related": "SPY",
            }],
        }

    market_briefing._BRIEFING_CACHE.clear()
    monkeypatch.setattr(market_briefing, "get_market_overview_snapshot", overview)
    monkeypatch.setattr(market_briefing, "get_economic_calendar", calendar)
    monkeypatch.setattr(market_briefing, "get_market_news", news)

    out = asyncio.run(market_briefing.get_daily_market_briefing(object(), lang="en"))

    assert out["model"] == "rule"


def test_daily_briefing_accepts_valid_llm_json(db, monkeypatch):
    class FakeProvider:
        async def complete(self, _prompt):
            return '''{
                "summary": "Signals support a cautious bullish bias.",
                "regime": {"bias": "bullish", "volatility": "normal", "risk": "risk_on", "confidence": "high"},
                "drivers": [{"label": "Nasdaq", "direction": "supportive", "detail": "Leading the broad market."}],
                "playbook": {"bullish": "Wait for confirmation.", "bearish": "Watch failed rebounds.", "no_trade": "Stand aside on conflict."}
            }'''

    market_briefing._BRIEFING_CACHE.clear()
    monkeypatch.setattr(market_briefing, "get_market_overview_snapshot", _overview)
    monkeypatch.setattr(market_briefing, "get_economic_calendar", _calendar)
    monkeypatch.setattr(market_briefing, "get_market_news", lambda: {
        "provider": "finnhub", "items": [{
            "title": "Market headline", "summary": "Summary", "source": "Wire",
            "url": "https://example.test/story", "published_at": datetime.now(timezone.utc).isoformat(),
            "related": "SPY",
        }],
    })
    monkeypatch.setattr("services.analyzer.create_provider", lambda: FakeProvider())

    out = asyncio.run(market_briefing.get_daily_market_briefing(db, lang="en", force_refresh=True))

    assert out["model"] == "FakeProvider"
    assert out["summary"] == "Signals support a cautious bullish bias."
    assert out["drivers"][0]["direction"] == "supportive"
