import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest

from agents.tool_context import ToolContext

from services.agent import build_agent_tools
from services.journal import JournalService
from models import User


def _seed_trade(db, user_id, symbol="BTCUSD", pnl=100.0):
    JournalService(db).create_trade(
        symbol=symbol, direction="long", pnl=pnl, open_time="2026-01-01T00:00:00Z",
        close_time="2026-01-01T01:00:00Z", user_id=user_id,
    )


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


def _invoke(tool, args: dict) -> str:
    """Call an Agents SDK FunctionTool synchronously with a JSON args dict."""
    ctx = ToolContext(context=None, tool_name=tool.name, tool_call_id="test",
                      tool_arguments=json.dumps(args))
    return asyncio.run(tool.on_invoke_tool(ctx, json.dumps(args)))


def test_all_tools_present(db, user_id):
    names = {t.name for t in build_agent_tools(db, user_id)}
    assert len(names) == 39
    assert {"get_journal_stats", "list_trades", "search_knowledge",
            "list_feed_news", "get_market_briefing", "get_daily_review",
            "list_memories", "remember_memory", "forget_memories"} <= names
    assert {"list_automation_tasks", "get_automation_task", "list_agent_findings",
            "create_automation_task", "update_automation_task",
            "delete_automation_task"} <= names
    assert {"get_stock_market_data", "get_forex_market_data",
            "get_crypto_market_data", "get_futures_market_data",
            "get_macro_data", "check_trade_opportunity"} <= names


def test_market_tools_delegate(db, user_id, monkeypatch):
    monkeypatch.setattr("services.market_research.get_market_snapshot", lambda kind, symbol, interval: {
        "asset_class": kind, "symbol": symbol, "interval": interval,
    })
    tools = build_agent_tools(db, user_id)
    out = json.loads(_invoke(_tool(tools, "get_forex_market_data"), {"symbol": "EURUSD"}))
    assert out == {"asset_class": "forex", "symbol": "EURUSD", "interval": "1day"}


def test_get_journal_stats(db, user_id):
    _seed_trade(db, user_id, pnl=100.0)
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "get_journal_stats"), {}))
    assert out["total_trades"] == 1 and out["total_pnl"] == 100.0
    assert "equity_curve" not in out


def test_list_trades_caps_limit(db, user_id):
    for _ in range(3):
        _seed_trade(db, user_id)
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "list_trades"), {"limit": 999}))
    assert len(out["trades"]) == 3
    assert set(out["trades"][0]) <= {"symbol", "direction", "pnl", "open_time", "close_time", "tags", "notes"}


def test_user_isolation(db, user_id):
    other = str(uuid.uuid4())
    db.add(User(id=other, email="o@t.test", password="x", name="O",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    _seed_trade(db, other, pnl=500.0)
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "get_journal_stats"), {}))
    assert out["total_trades"] == 0


def test_unknown_portfolio(db, user_id):
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "get_portfolio_summary"), {"portfolio_id": "nope"}))
    assert out == {"error": "not_found"}


def test_missing_required_arg(db, user_id):
    # The SDK validates against the tool schema and returns an error string
    # (rather than raising) when a required arg is missing.
    tool = _tool(build_agent_tools(db, user_id), "get_strategy")
    out = _invoke(tool, {})
    assert "strategy_id" in out and "required" in out.lower()


def test_database_tools_use_and_close_an_independent_session(db, user_id, monkeypatch):
    import db as db_module
    from sqlalchemy.orm import Session

    created = []

    class TrackingSession(Session):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def factory():
        tool_session = TrackingSession(
            bind=db.get_bind(), expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        created.append(tool_session)
        return tool_session

    monkeypatch.setattr(db_module, "SessionLocal", factory)
    out = json.loads(_invoke(
        _tool(build_agent_tools(db, user_id), "list_portfolios"), {},
    ))

    assert out == {"portfolios": []}
    assert len(created) == 1
    assert created[0] is not db
    assert created[0].closed is True
