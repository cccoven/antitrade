import asyncio
import json

from agents.tool_context import ToolContext


def _invoke(tool, args: dict) -> str:
    ctx = ToolContext(context=None, tool_name=tool.name, tool_call_id="test",
                      tool_arguments=json.dumps(args))
    return asyncio.run(tool.on_invoke_tool(ctx, json.dumps(args)))


def test_all_tools_include_search(db, user_id):
    from services.agent import build_agent_tools
    names = sorted(t.name for t in build_agent_tools(db, user_id))
    assert "search_knowledge" in names
    assert {
        "get_stock_market_data",
        "get_forex_market_data",
        "get_crypto_market_data",
        "get_futures_market_data",
        "get_macro_data",
        "check_trade_opportunity",
    } <= set(names)
    assert len(names) == 39


def test_search_tool_recalls_created_strategy(db, user_id):
    from services.strategies import StrategyService
    from services.agent import build_agent_tools
    StrategyService(db).create_strategy(
        user_id=user_id, title="Gold", body="黄金日内趋势回调 gold intraday trend")
    tool = next(t for t in build_agent_tools(db, user_id) if t.name == "search_knowledge")
    out = json.loads(_invoke(tool, {"query": "黄金 趋势", "scope": "mine"}))
    assert any("黄金" in r["content"] for r in out["results"])


def test_create_strategy_survives_embed_failure(db, user_id, monkeypatch):
    monkeypatch.setattr("services.rag.create_embeddings",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    from services.strategies import StrategyService
    s = StrategyService(db).create_strategy(user_id=user_id, title="X", body="some body")
    assert s["id"]


def test_strategy_reembed_failure_preserves_previous_vectors(db, user_id, monkeypatch):
    from sqlalchemy import select
    from models import StrategyEmbedding
    from services.strategies import StrategyService

    service = StrategyService(db)
    strategy = service.create_strategy(
        user_id=user_id, title="Gold", body="original gold pullback strategy",
    )
    before = db.execute(
        select(StrategyEmbedding.content)
        .where(StrategyEmbedding.strategy_id == strategy["id"])
        .order_by(StrategyEmbedding.chunk_index)
    ).scalars().all()
    assert before

    monkeypatch.setattr(
        "services.rag.create_embeddings",
        lambda: (_ for _ in ()).throw(RuntimeError("embedding unavailable")),
    )
    updated = service.patch_strategy(
        user_id, strategy["id"], body="replacement body that cannot be embedded",
    )

    after = db.execute(
        select(StrategyEmbedding.content)
        .where(StrategyEmbedding.strategy_id == strategy["id"])
        .order_by(StrategyEmbedding.chunk_index)
    ).scalars().all()
    assert updated is not None
    assert updated["body"] == "replacement body that cannot be embedded"
    assert after == before
