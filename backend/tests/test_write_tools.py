import asyncio
import json
import uuid
from datetime import datetime, timezone

from agents.tool_context import ToolContext

from services.agent import build_agent_tools
from services.journal import JournalService
from services.portfolio import PortfoliosService, EntryService
from services.strategies import StrategyService
from models import User


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


def _invoke(tool, args: dict) -> str:
    ctx = ToolContext(context=None, tool_name=tool.name, tool_call_id="test",
                      tool_arguments=json.dumps(args))
    return asyncio.run(tool.on_invoke_tool(ctx, json.dumps(args)))


def test_write_tools_present(db, user_id):
    names = {t.name for t in build_agent_tools(db, user_id)}
    assert {
        "create_trade", "update_trade", "delete_trades", "tag_trades",
        "create_portfolio", "update_portfolio", "delete_portfolio",
        "create_entry", "update_entry", "delete_entries",
        "create_strategy", "update_strategy", "delete_strategy",
        "remember_memory", "forget_memories",
        "create_automation_task", "update_automation_task",
        "delete_automation_task",
    } <= names


def test_write_tools_need_approval(db, user_id):
    write = {
        "create_trade", "update_trade", "delete_trades", "tag_trades",
        "create_portfolio", "update_portfolio", "delete_portfolio",
        "create_entry", "update_entry", "delete_entries",
        "create_strategy", "update_strategy", "delete_strategy",
        "remember_memory", "forget_memories",
        "create_automation_task", "update_automation_task",
        "delete_automation_task",
    }
    for t in build_agent_tools(db, user_id):
        if t.name in write:
            assert t.needs_approval is True, f"{t.name} must need approval"
        else:
            assert t.needs_approval is False, f"{t.name} must NOT need approval"


def test_delete_trades_executes(db, user_id):
    trade = JournalService(db).create_trade(
        symbol="BTCUSD", direction="long", pnl=100.0,
        open_time="2026-01-01T00:00:00Z", close_time="2026-01-01T01:00:00Z", user_id=user_id)
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "delete_trades"),
                             {"trade_ids": [trade["id"]]}))
    assert out["deleted"] == 1
    assert JournalService(db).get_trade(trade["id"], user_id=user_id) is None


def test_delete_trades_user_isolation(db, user_id):
    other = str(uuid.uuid4())
    db.add(User(id=other, email="w@t.test", password="x", name="W",
                created_at=datetime.now(timezone.utc).isoformat()))
    db.flush()
    trade = JournalService(db).create_trade(
        symbol="ETHUSD", direction="long", pnl=10.0,
        open_time="2026-01-01T00:00:00Z", close_time="2026-01-01T01:00:00Z", user_id=other)
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "delete_trades"),
                             {"trade_ids": [trade["id"]]}))
    assert out["deleted"] == 0
    assert JournalService(db).get_trade(trade["id"], user_id=other) is not None


def test_create_portfolio_and_entry(db, user_id):
    tools = build_agent_tools(db, user_id)
    p = json.loads(_invoke(_tool(tools, "create_portfolio"), {"name": "Main", "currency": "USD"}))
    assert p["portfolio"]["name"] == "Main"
    pid = p["portfolio"]["id"]
    e = json.loads(_invoke(_tool(tools, "create_entry"),
                           {"portfolio_id": pid, "name": "BTC", "category": "crypto", "amount": 500.0}))
    assert e["entry"]["name"] == "BTC"


def test_create_strategy(db, user_id):
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "create_strategy"),
                             {"title": "Breakout", "body": "buy highs", "tags": ["momentum"]}))
    assert out["strategy"]["title"] == "Breakout"


def test_update_trade_partial_and_returns_id(db, user_id):
    trade = JournalService(db).create_trade(
        symbol="BTCUSD", direction="long", pnl=100.0, notes="orig",
        open_time="2026-01-01T00:00:00Z", close_time="2026-01-01T01:00:00Z", user_id=user_id)
    out = json.loads(_invoke(_tool(build_agent_tools(db, user_id), "update_trade"),
                             {"trade_id": trade["id"], "pnl": 200.0}))
    assert out["trade"]["id"] == trade["id"]
    assert out["trade"]["pnl"] == 200.0
    assert out["trade"]["notes"] == "orig"  # untouched fields preserved
