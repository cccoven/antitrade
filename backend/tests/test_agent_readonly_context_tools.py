import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest

from agents.tool_context import ToolContext

from services.agent import build_agent_tools
from services.journal import JournalService
from models import User, FeedItem, FeedBriefing


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


def _invoke(tool, args: dict) -> str:
    ctx = ToolContext(context=None, tool_name=tool.name, tool_call_id="test",
                      tool_arguments=json.dumps(args))
    return asyncio.run(tool.on_invoke_tool(ctx, json.dumps(args)))


def _seed_feed_item(db, title="BTC surges", category="crypto", lang="zh",
                    summary="A summary", source_key="coindesk",
                    published_at="2026-07-09T00:00:00Z", symbols=None):
    item = FeedItem(
        id=str(uuid.uuid4()),
        url=f"https://news.test/{uuid.uuid4()}",
        source_key=source_key, title=title, summary=summary,
        published_at=published_at, fetched_at="2026-07-09T00:00:00Z",
        category=category, symbols=symbols or ["BTCUSD"], lang=lang,
    )
    db.add(item)
    db.flush()
    return item


def test_list_feed_news_compact_fields(db, user_id):
    _seed_feed_item(db, title="BTC surges", category="crypto")
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "list_feed_news"), {}))
    assert len(out["news"]) == 1
    item = out["news"][0]
    assert set(item) == {"title", "source_key", "published_at", "category", "summary", "symbols"}
    assert item["title"] == "BTC surges"


def _seed_briefing(db, lang="zh", content=None):
    b = FeedBriefing(
        id=str(uuid.uuid4()),
        generated_at="2026-07-09T00:00:00Z",
        lang=lang, window="6h",
        content=content or {"hot": [{"title": "BTC", "sources": 3, "ref": 1}], "sections": {}},
        model="demo",
    )
    db.add(b)
    db.flush()
    return b


def test_list_feed_news_caps_limit(db, user_id):
    for _ in range(35):
        _seed_feed_item(db)
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "list_feed_news"), {"limit": 999}))
    assert len(out["news"]) == 30


def test_list_feed_news_category_filter(db, user_id):
    _seed_feed_item(db, category="crypto", lang="zh")
    _seed_feed_item(db, category="forex", lang="zh")
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "list_feed_news"), {"category": "forex"}))
    assert len(out["news"]) == 1
    assert out["news"][0]["category"] == "forex"


def test_list_feed_news_empty(db, user_id):
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "list_feed_news"), {}))
    assert out == {"news": []}


def test_get_market_briefing_present(db, user_id):
    _seed_briefing(db, lang="zh")
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "get_market_briefing"), {}))
    assert out["briefing"]["window"] == "6h"
    assert out["briefing"]["content"]["hot"][0]["title"] == "BTC"
    assert set(out["briefing"]) == {"generated_at", "window", "content"}


def test_get_market_briefing_attaches_citable_sources(db, user_id):
    hot_source = _seed_feed_item(db, title="BTC surges", source_key="coindesk")
    point_source = _seed_feed_item(db, title="Fed holds rates", source_key="reuters")
    _seed_briefing(db, content={
        "hot": [{"title": "BTC momentum", "sources": 1, "id": hot_source.id}],
        "sections": [{"category": "macro", "points": [
            {"text": "Rates remain unchanged", "id": point_source.id},
        ]}],
    })

    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "get_market_briefing"), {}))
    hot = out["briefing"]["content"]["hot"][0]
    point = out["briefing"]["content"]["sections"][0]["points"][0]

    assert hot["source"] == {"title": "BTC surges", "source_key": "coindesk"}
    assert point["source"] == {"title": "Fed holds rates", "source_key": "reuters"}
    assert "id" not in hot and "id" not in point


def test_get_market_briefing_absent(db, user_id):
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "get_market_briefing"), {}))
    assert out == {"briefing": None}


def _seed_trade_on(db, user_id, date="2026-07-09", pnl=100.0):
    JournalService(db).create_trade(
        symbol="BTCUSD", direction="long", pnl=pnl,
        open_time=f"{date}T00:00:00Z", close_time=f"{date}T01:00:00Z",
        user_id=user_id,
    )


def test_get_daily_review_bundle(db, user_id):
    JournalService(db).upsert_daily_review(
        user_id=user_id, review_date="2026-07-09", body="held discipline today")
    _seed_trade_on(db, user_id, date="2026-07-09", pnl=100.0)
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "get_daily_review"), {"date": "2026-07-09"}))
    dr = out["daily_review"]
    assert dr["date"] == "2026-07-09"
    assert dr["review"]["body"] == "held discipline today"
    assert len(dr["trades"]) == 1
    assert set(dr["trades"][0]) <= {"symbol", "direction", "pnl", "open_time", "close_time", "tags", "notes"}
    assert "equity_curve" not in dr["stats"]


def test_get_daily_review_empty_date(db, user_id):
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "get_daily_review"), {"date": "2026-01-01"}))
    dr = out["daily_review"]
    assert dr["review"]["body"] == ""
    assert dr["trades"] == []


@pytest.mark.parametrize("value", ["yesterday", "2026/07/09", "2026-07-09T00:00:00Z"])
def test_get_daily_review_rejects_invalid_date(db, user_id, value):
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "get_daily_review"), {"date": value}))

    assert out == {"error": "invalid_date", "expected": "YYYY-MM-DD"}


def test_get_daily_review_scope_isolation(db, user_id):
    other = str(uuid.uuid4())
    db.add(User(id=other, email="o@t.test", password="x", name="O",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    JournalService(db).upsert_daily_review(
        user_id=other, review_date="2026-07-09", body="OTHER user's private review")
    _seed_trade_on(db, other, date="2026-07-09", pnl=999.0)
    tools = build_agent_tools(db, user_id, lang="zh")
    out = json.loads(_invoke(_tool(tools, "get_daily_review"), {"date": "2026-07-09"}))
    dr = out["daily_review"]
    assert dr["review"]["body"] == ""
    assert dr["trades"] == []
